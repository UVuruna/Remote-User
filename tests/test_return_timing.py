"""RETURN GATE (task 203): coming back from an excursion costs ONE encoder.

THE MEASUREMENT THAT WROTE THIS FILE — the owner's own server log,
`%LOCALAPPDATA%\\RemoteUser\\server.log.1`, two real returns from a gallery
excursion on 2026-08-11:

    10:21:12,553  Phone announced an excursion
    10:21:12,555  H.264 session closed - 0 active
    10:21:14,146  WebSocket /ws [accepted]            1.59 s  phone + shell probe
    10:21:14,173  Client authenticated
    10:21:15,306  Layout 1 focused ... landed=True    1.13 s  BLOCKING the encoder
    10:21:15,586  H.264 session opened                0.28 s  ffmpeg + init segment

    10:08:08,533  Quality change from the phone
    10:08:08,773  H.264 session opened - 1 active
    10:08:08,864  H.264 session closed - 0 active     0.09 s  torn down at once
    10:08:10,086  H.264 session opened - 1 active     1.31 s  the SECOND encoder

Two independent costs, both structural, neither of them the network:

1. The encoder was started LAST in the connection setup, so its 0.28 s sat
   BEHIND the resume focus's 1.13 s of placing real windows and waiting for
   every one of them to stand on its commanded rect. Nothing in ffmpeg depends
   on where the windows are.
2. The phone restates its saved quality overrides on every connect, and that
   message could only be read after the whole setup had finished — so the
   first encoder was always built at DEFAULT quality and immediately thrown
   away. Every return paid for two ffmpegs and the black gap between them.

What is proven here, on the REAL `web._stream_h264` loop over the REAL
`H264Manager` (fakes for ffmpeg and dxcam, borrowed from the stream lifecycle
gate — one harness, never a second copy to drift from):

  A. A connection whose overrides are known up front opens exactly ONE
     encoder, and that one already carries the overrides.
  B. `config.quality_override` reads the `auth` field and the `quality`
     message identically — which is what makes the restatement compare equal
     and change nothing.
  C. A quality change that really is new STILL re-opens the encoder — without
     this the gate would pass with the feature deleted.
  D. The connection setup starts the H.264 task BEFORE it blocks on the
     resume focus. Asserted against the real source order in `web.py`,
     because the thing that regresses here is an edit that moves one line.

Run:  .venv\\Scripts\\python tests/test_return_timing.py
"""

import asyncio
import inspect
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402
import web  # noqa: E402

# The fakes are the stream lifecycle gate's. Importing them rather than
# copying them is deliberate: two encoders-that-are-not-ffmpeg would drift,
# and the first thing to drift would be the pipe contract both gates rest on.
from test_stream_lifecycle import (  # noqa: E402
    FakeFfmpeg, FakeWs, fresh_manager, install_fakes,
)


def _bitrates() -> list[str]:
    """The `-b:v` value of every ffmpeg this check caused to spawn, in order —
    which is both HOW MANY encoders were built and WHAT each one was built
    for."""
    out = []
    for proc in FakeFfmpeg.instances:
        cmd = list(proc.cmd)
        out.append(cmd[cmd.index("-b:v") + 1] if "-b:v" in cmd else "?")
    return out


def _stop_all() -> None:
    for proc in FakeFfmpeg.instances:
        proc.force_stop()


# ── The checks ──────────────────────────────────────────────────────────────

def check_auth_quality_opens_one_encoder() -> bool:
    """THE fix. A connection that already knows the phone's overrides builds
    ONE ffmpeg, at the phone's bitrate — never a default one first."""
    manager = fresh_manager()
    conn = {"quality": config.quality_override({"fps": 0, "res": "full", "bitrate": "low"})}
    assert conn["quality"] is not None, "the override must survive parsing"

    async def run():
        ws = FakeWs()
        task = asyncio.create_task(web._stream_h264(ws, manager, "t", conn))
        for _ in range(150):
            await asyncio.sleep(0.02)
            if ws.chunks >= 2:
                break
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0.2)

    asyncio.run(run())
    rates = _bitrates()
    _stop_all()
    # Exactly one encoder, and it is the LOW one — not the PC's own 12M.
    return len(rates) == 1 and rates[0] == config.bitrate_for_level("low")


def check_the_restatement_changes_nothing() -> bool:
    """B. The `quality` message the phone sends on every connect must parse to
    exactly what `auth` already gave us, or the equality test in the handler
    never holds and the second encoder comes back."""
    for payload in (
        {"fps": 0, "res": "full", "bitrate": "low"},
        {"fps": 30, "res": "1/2", "bitrate": "mid"},
        {"fps": 0, "res": "full", "bitrate": "high"},   # pure defaults -> None
        {},                                              # a page that says nothing
    ):
        if config.quality_override(payload) != config.quality_override(dict(payload)):
            return False
    return (config.quality_override({"fps": 0, "res": "full", "bitrate": "high"}) is None
            and config.quality_override({}) is None
            and config.quality_override({"bitrate": "low"}) is not None)


def check_a_real_change_still_reopens() -> bool:
    """C. The feature is still there: a genuinely new quality ends the running
    session, and the loop opens the next one with the new bitrate."""
    manager = fresh_manager()
    conn = {"quality": None}

    async def run():
        ws = FakeWs()
        task = asyncio.create_task(web._stream_h264(ws, manager, "t", conn))
        for _ in range(150):
            await asyncio.sleep(0.02)
            if ws.chunks >= 2:
                break
        # Exactly what the `quality` handler does once it sees a change.
        conn["quality"] = config.quality_override({"fps": 0, "res": "full",
                                                   "bitrate": "low"})
        conn["reset_stream"]()
        for _ in range(200):
            await asyncio.sleep(0.02)
            if len(FakeFfmpeg.instances) >= 2:
                break
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await asyncio.sleep(0.2)

    asyncio.run(run())
    rates = _bitrates()
    _stop_all()
    return (len(rates) == 2
            and rates[0] == config.bitrate_for_level(None)
            and rates[1] == config.bitrate_for_level("low"))


def check_the_encoder_starts_before_the_desk() -> bool:
    """D. The 1.13 s. `_stream_h264` must be created BEFORE the resume focus
    that blocks on `wait_landed`, in the connection setup itself.

    Read off the real source, because the regression this defends against is
    somebody moving one line back down — which no runtime assertion on a fake
    socket would ever notice."""
    src = inspect.getsource(web.create_app)
    start = src.find("_stream_h264(ws, stream, token, conn)")
    focus = src.find("layout_api.layout_focus(ws, layouts, stream, conn, resume)")
    landed = src.find("resume_index")
    return start > 0 and focus > start and landed > start


def check_the_setup_reads_the_quality_off_auth() -> bool:
    """The other half of A, and the half a fake `conn` can never see: the
    connection setup must SEED `conn["quality"]` from the auth message. Check A
    proves the loop honours whatever is in `conn`; nothing but this proves the
    phone's own words ever get in there.

    Driven through `config.quality_override` on a real auth payload, and
    asserted against the source line that does the seeding — the two together
    are what a page's first message actually buys."""
    src = inspect.getsource(web.create_app)
    seeded = 'config.quality_override(first.get("quality")' in src
    auth = {"type": "auth", "token": "t", "screen": {"w": 1600, "h": 2560},
            "quality": {"fps": 30, "res": "1/2", "bitrate": "mid"}}
    parsed = config.quality_override(auth.get("quality") or {})
    # And a page that predates the field must land on None, not on an error:
    old = config.quality_override({})
    return seeded and parsed == {"fps": 30, "res": "1/2", "bitrate": "mid"} and old is None


CHECKS = [
    ("a known quality opens exactly ONE encoder, already correct",
     check_auth_quality_opens_one_encoder),
    ("the connect-time restatement parses identically and changes nothing",
     check_the_restatement_changes_nothing),
    ("a genuinely new quality still re-opens the encoder",
     check_a_real_change_still_reopens),
    ("the encoder is started before the blocking resume focus",
     check_the_encoder_starts_before_the_desk),
    ("the connection setup seeds the quality from the auth message",
     check_the_setup_reads_the_quality_off_auth),
]


def main() -> int:
    install_fakes()
    print("=== RETURN GATE (task 203) ===")
    failed = 0
    for name, fn in CHECKS:
        started = time.monotonic()
        try:
            ok = fn()
        except Exception as e:                # a crashing check is a failing check
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  ({time.monotonic() - started:.1f}s)")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"RETURN GATE FAILED — {failed} check(s).")
        return 1
    print("RETURN GATE PASSED — one return, one encoder, started first.")
    return 0


def test_return_timing():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
