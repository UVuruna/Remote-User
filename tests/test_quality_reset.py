"""Quality Reset Gate: changing the bitrate may NEVER kill the app.

The owner's #1 report of 2026-08-10, in his words: "pada cele aplikacije to
jest strima prenosa podataka ukoliko se u settingsu promeni kvalitet
bit rate-a" (lang-ok: owner quote) -- changing the bitrate quality in settings
brings the whole application, that is the data stream, down.

WHAT IT REALLY WAS. A bitrate lives inside a running ffmpeg's flags, so the
only way to apply the phone's quality panel is to close that client's encoder
and open a new one. With one client -- the normal case, "one device at a time"
is a hard rule -- closing it emptied `H264Manager._sessions`, so
`_stop_source_if_idle` tore dxcam DOWN and `open_session` built it again for a
change that never touched capture at all. The new encoder then had no frames,
and ffmpeg cannot write an init segment before it has encoded one; past
`h264_head_timeout` the open raised, and `_stream_h264` answered a failed
RE-open exactly as it answers a failed FIRST open -- `ws.close(1011)`. That
socket carries input, layouts, dictation and presence as well as pictures, so
one slow encoder restart ended everything and the phone reconnected.

His own %LOCALAPPDATA%\\RemoteUser\\server.log, 2026-08-10:

    20:29:33,516 INFO  h264_streamer: H.264 session opened - 1 active,
                                      codec avc1.4D4032, 3840x2160
    20:30:21,267 INFO  h264_streamer: H.264 session closed - 0 active
    20:30:21,267 INFO  dxcam.dxcam:   Frame buffer build(start): 3840x2160
    20:30:42,895 ERROR web: H.264 session failed to open: ffmpeg produced no
                            init segment in time
    20:30:43,160 INFO  uvicorn.error: 192.168.0.30:54526 - "WebSocket /ws"
                                      [accepted]        <- the app had died

Zero "stream backlog" warnings and zero ffmpeg errors in that whole file, so
the 20:30:21 close was neither a slow client nor a dying encoder -- and the
`Frame buffer build(start)` on the same millisecond is capture being rebuilt,
which is what a reset does and a pause does not. The same close-and-reopen
rides EVERY connection (the page restates its saved quality right after auth):
19:29:30,138 opened avc1.4D4034 -> 19:29:30,274 closed -> 19:29:31,514 opened
avc1.4D4032, a different H.264 LEVEL because a different bitrate.

WHAT IS PROVEN HERE -- with the REAL `H264Manager`, the REAL `H264Session`,
the REAL `web._stream_h264` loop and the REAL `web._receive_input` handler,
and no dxcam, no ffmpeg and no 4K (the fakes of test_stream_lifecycle.py):

1. A bitrate change reaches the new encoder as a new `-b:v`.
2. ...and does NOT recycle capture: dxcam is started ONCE for the connection.
3. A re-open that misses the head timeout does not close the socket -- the
   stream comes back by itself.
4. ...but a re-open that never recovers still gives up, so this can never
   become the 2026-07-29 error loop (171 open failures in 90 s).
5. A FIRST open that fails is still fatal at once, with no retries: there is
   no stream to keep and nothing that socket could still do.
6. A phone that has GONE still stops capture -- the hold must not defeat
   "nothing runs while nobody is watching" (owner 2026-08-05).
7. The change is SAID in the server log, end to end through the real message
   handler. His crash could not be dated in his own log because this was the
   one cause of a close-and-reopen that wrote nothing.

Run:  .venv\\Scripts\\python tests/test_quality_reset.py
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import h264_streamer  # noqa: E402
import test_stream_lifecycle as L  # noqa: E402
import web  # noqa: E402
from config import SETTINGS  # noqa: E402

HEAD_TIMEOUT = 0.6      # short enough for a gate, long enough for a real spawn
STALL = HEAD_TIMEOUT * 4  # an encoder that will certainly miss it


class ScriptedFfmpeg(L.FakeFfmpeg):
    """`FakeFfmpeg` with a delay PER SPAWN instead of one for the class.

    A reset is two encoders in a row, and the whole subject here is one of them
    being late — a single class-wide `head_delay` cannot say "the second one
    stalls". The list is read at construction (the last entry repeats), so the
    reading can never race the thread that acts on it."""

    delays: list[float] = []

    def __init__(self, cmd, **kwargs):
        i = len(L.FakeFfmpeg.instances)
        d = ScriptedFfmpeg.delays or [0.0]
        self.head_wait = d[i] if i < len(d) else d[-1]
        super().__init__(cmd, **kwargs)

    def _produce(self) -> None:
        if self._stop.wait(self.head_wait):
            self._out.eof()
            return
        self._out.feed(L.INIT_SEGMENT)
        while not self._stop.wait(L.FakeFfmpeg.frag_interval):
            self._out.feed(L.FRAGMENT)
        self._out.eof()


class TalkingWs(L.FakeWs):
    """A socket the RECEIVE loop can read from: `feed` queues one client
    message, and the loop ends with a disconnect when the script runs out."""

    def __init__(self):
        super().__init__()
        self.inbox: list[str] = []

    def feed(self, msg: dict) -> None:
        self.inbox.append(json.dumps(msg))

    async def receive_text(self) -> str:
        for _ in range(200):
            if self.inbox:
                return self.inbox.pop(0)
            await asyncio.sleep(0.01)
        raise web.WebSocketDisconnect(1000)


class LogWatch(logging.Handler):
    """Every `web` record, so a check can prove a sentence was written."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.lines: list[str] = []

    def emit(self, record) -> None:
        self.lines.append(record.getMessage())


def install_fakes() -> None:
    L.install_fakes()
    h264_streamer.subprocess.Popen = ScriptedFfmpeg
    object.__setattr__(SETTINGS, "h264_queue_chunks", 64)
    object.__setattr__(SETTINGS, "h264_head_timeout", HEAD_TIMEOUT)
    object.__setattr__(SETTINGS, "h264_reopen_tries", 4)
    object.__setattr__(SETTINGS, "h264_reopen_pause_s", 0.05)


def fresh(delays: list[float]) -> h264_streamer.H264Manager:
    ScriptedFfmpeg.delays = delays
    manager = L.fresh_manager()
    L.FakeFfmpeg.frag_interval = 0.01
    return manager


def bitrate_of(proc) -> str:
    return proc.cmd[proc.cmd.index("-b:v") + 1]


async def until(test, tries: int = 400) -> bool:
    """Poll a condition on the running loop — every check here is waiting for
    an encoder on another thread, never for a fixed number of seconds."""
    for _ in range(tries):
        await asyncio.sleep(0.02)
        if test():
            return True
    return False


async def stream_until_live(manager, ws, conn) -> asyncio.Task:
    task = asyncio.create_task(web._stream_h264(ws, manager, "t", conn))
    assert await until(lambda: ws.chunks >= 2), "the stream never got going"
    return task


async def teardown(manager, task) -> None:
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await asyncio.sleep(0.2)
    for proc in L.FakeFfmpeg.instances:
        proc.force_stop()
    manager.shutdown()


def send_quality(conn, manager, quality: dict) -> None:
    """What `web._receive_input`'s `quality` branch does to the stream loop."""
    conn["quality"] = quality
    conn["reset_stream"]()


# ── The checks ──────────────────────────────────────────────────────────────

def check_bitrate_change_reaches_the_encoder() -> bool:
    """The phone picks "low"; the next ffmpeg must actually carry it. Without
    this the rest of the gate would pass with the feature deleted."""
    manager = fresh([0.0])
    result = {}

    async def run():
        ws, conn = L.FakeWs(), {"quality": None}
        task = await stream_until_live(manager, ws, conn)
        send_quality(conn, manager, {"fps": 0, "res": "full", "bitrate": "low"})
        ok = await until(lambda: len(L.FakeFfmpeg.instances) >= 2)
        result["spawns"] = [bitrate_of(p) for p in L.FakeFfmpeg.instances]
        result["ok"] = ok and ws.closed_code is None
        await teardown(manager, task)

    asyncio.run(run())
    # The FIRST is the desktop's own bitrate, the SECOND the phone's step of
    # it (config.bitrate_for_level: "low" is 10% of 12M).
    return (result.get("ok") and len(result["spawns"]) >= 2
            and result["spawns"][0] == SETTINGS.h264_bitrate
            and result["spawns"][1] == "1200k")


def check_a_quality_change_does_not_recycle_capture() -> bool:
    """THE root cause. dxcam must be started ONCE for this connection — the
    reset is one ffmpeg swapped for another, and capture never enters into it.
    A rebuilt source is what starved the new encoder of its first frame."""
    manager = fresh([0.0])
    result = {}

    async def run():
        ws, conn = L.FakeWs(), {"quality": None}
        task = await stream_until_live(manager, ws, conn)
        send_quality(conn, manager, {"fps": 0, "res": "full", "bitrate": "mid"})
        await until(lambda: len(L.FakeFfmpeg.instances) >= 2)
        # ...and the new session really is streaming, so this is not a count
        # taken before the reset finished.
        at = ws.chunks
        result["streaming"] = await until(lambda: ws.chunks > at + 2)
        result["starts"] = manager._source.starts
        result["running"] = manager._source.running
        await teardown(manager, task)

    asyncio.run(run())
    return (result.get("streaming") and result["starts"] == 1
            and result["running"] is True
            and manager._source.running is False)   # ...and it stops at the end


def check_a_slow_reopen_does_not_kill_the_socket() -> bool:
    """The owner's crash. The encoder opened for the new bitrate misses the
    head timeout; the socket — which carries input, layouts and dictation —
    must survive, and the picture must come back by itself."""
    manager = fresh([0.0, STALL, 0.0])
    result = {}

    async def run():
        ws, conn = L.FakeWs(), {"quality": None}
        task = await stream_until_live(manager, ws, conn)
        send_quality(conn, manager, {"fps": 0, "res": "full", "bitrate": "low"})
        at = ws.chunks
        result["recovered"] = await until(lambda: ws.chunks > at + 2)
        result["closed"] = ws.closed_code
        result["spawns"] = len(L.FakeFfmpeg.instances)
        result["bitrate"] = bitrate_of(L.FakeFfmpeg.instances[-1])
        await teardown(manager, task)

    asyncio.run(run())
    # Three encoders: the original, the one that stalled, the one that worked
    # — and the one that worked carries the bitrate he asked for.
    return (result.get("recovered") and result["closed"] is None
            and result["spawns"] == 3 and result["bitrate"] == "1200k")


def check_a_reopen_that_never_recovers_gives_up() -> bool:
    """...and the retry is BOUNDED. An encoder that is permanently broken must
    end the socket, not spin — the 2026-07-29 log wrote 171 open failures in
    90 seconds because nothing ever stopped trying."""
    manager = fresh([0.0, STALL])
    result = {}

    async def run():
        ws, conn = L.FakeWs(), {"quality": None}
        task = await stream_until_live(manager, ws, conn)
        send_quality(conn, manager, {"fps": 0, "res": "full", "bitrate": "low"})
        result["gave_up"] = await until(lambda: ws.closed_code is not None)
        result["closed"] = ws.closed_code
        result["spawns"] = len(L.FakeFfmpeg.instances)
        await teardown(manager, task)

    asyncio.run(run())
    # One good encoder + exactly `h264_reopen_tries` doomed ones.
    return (result.get("gave_up") and result["closed"] == 1011
            and result["spawns"] == 1 + SETTINGS.h264_reopen_tries)


def check_a_first_open_failure_is_still_fatal() -> bool:
    """The other side of the same rule. A connection whose very first encoder
    fails has no stream to protect — it must be told at once, with no retries
    that only delay the honest answer."""
    manager = fresh([STALL])
    result = {}

    async def run():
        ws, conn = L.FakeWs(), {"quality": None}
        task = asyncio.create_task(web._stream_h264(ws, manager, "t", conn))
        result["closed_fast"] = await until(lambda: ws.closed_code is not None)
        result["closed"] = ws.closed_code
        result["spawns"] = len(L.FakeFfmpeg.instances)
        await teardown(manager, task)

    asyncio.run(run())
    return (result.get("closed_fast") and result["closed"] == 1011
            and result["spawns"] == 1)


def check_an_away_phone_still_stops_capture() -> bool:
    """The hold may not buy capture a life of its own. A phone that has gone
    pauses the loop, and dxcam stops with the session it was feeding (owner
    2026-08-05: a stream nobody can see is exactly the traffic he went looking
    for)."""
    manager = fresh([0.0])
    result = {}

    async def run():
        ws, conn = L.FakeWs(), {"quality": None}
        task = await stream_until_live(manager, ws, conn)
        conn["paused"] = True            # what the `away` handler does...
        conn["reset_stream"]()           # ...to the stream loop
        result["stopped"] = await until(lambda: manager._source.running is False)
        # ...and it comes back when he does.
        conn["paused"] = False
        result["resumed"] = await until(lambda: manager._source.running is True)
        await teardown(manager, task)

    asyncio.run(run())
    return bool(result.get("stopped") and result.get("resumed"))


def check_the_quality_change_is_logged_end_to_end() -> bool:
    """Through the REAL `_receive_input`, from a real `quality` message.

    Two things at once, and both are why this check exists rather than a
    narrower one: the message must reach the encoder as a new `-b:v` (a reset
    driven by hand proves the loop, not the handler), and the change must be
    SAID in the log. His 20:30:21 close had no cause written anywhere — the
    quality branch was the one path that reset the stream in silence."""
    manager = fresh([0.0])
    watch = LogWatch()
    web_log = logging.getLogger("web")
    web_log.addHandler(watch)
    # ...and it must be ALLOWED to speak: the root logger defaults to WARNING,
    # so an unraised `web` logger drops every INFO before a handler sees it —
    # a check that forgot this would call the sentence missing when it is not.
    level, _ = web_log.level, web_log.setLevel(logging.INFO)
    result = {}

    async def run():
        ws, conn = TalkingWs(), {"quality": None, "seen": time.monotonic(),
                                 "away": None, "left": False}
        task = await stream_until_live(manager, ws, conn)
        ws.feed({"type": "quality", "fps": 15, "res": "1/2", "bitrate": "mid"})
        receiver = asyncio.create_task(
            web._receive_input(ws, None, manager, "t", object(), conn))
        result["reopened"] = await until(lambda: len(L.FakeFfmpeg.instances) >= 2)
        cmd = L.FakeFfmpeg.instances[-1].cmd
        result["bitrate"] = bitrate_of(L.FakeFfmpeg.instances[-1])
        result["filters"] = cmd[cmd.index("-vf") + 1] if "-vf" in cmd else ""
        receiver.cancel()
        await asyncio.gather(receiver, return_exceptions=True)
        await teardown(manager, task)

    asyncio.run(run())
    web_log.removeHandler(watch)
    web_log.setLevel(level)
    said = any("Quality change from the phone" in line for line in watch.lines)
    # "mid" is 40% of the desktop's 12M, and the panel's other two axes ride
    # the same message — a log line alone would not prove the message ARRIVED.
    return (result.get("reopened") and said and result["bitrate"] == "4800k"
            and "fps=15" in result["filters"] and "scale=" in result["filters"])


CHECKS = [
    ("a bitrate change reaches the encoder", check_bitrate_change_reaches_the_encoder),
    ("a quality change does NOT recycle capture",
     check_a_quality_change_does_not_recycle_capture),
    ("a slow re-open does not kill the socket",
     check_a_slow_reopen_does_not_kill_the_socket),
    ("a re-open that never recovers still gives up",
     check_a_reopen_that_never_recovers_gives_up),
    ("a FIRST open failure is still fatal at once",
     check_a_first_open_failure_is_still_fatal),
    ("an away phone still stops capture", check_an_away_phone_still_stops_capture),
    ("the change is logged, end to end through the real handler",
     check_the_quality_change_is_logged_end_to_end),
]


def main() -> int:
    install_fakes()
    print("=== QUALITY RESET GATE ===")
    failed = 0
    for name, fn in CHECKS:
        started = time.monotonic()
        try:
            ok = fn()
        except Exception as e:            # a crashing check is a failing check
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  ({time.monotonic() - started:.1f}s)")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"QUALITY RESET GATE FAILED — {failed} check(s).")
        return 1
    print("QUALITY RESET GATE PASSED — changing the bitrate cannot kill the app.")
    return 0


def test_quality_reset():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
