"""Return Speed Gate: nothing in the return path waits for its own sake.

Measured from the owner's own `server.log` of 2026-08-12, ten instrumented
layout returns: median 3,443 ms of loading overlay, of which 1,800 ms came
AFTER the server had already logged that the windows had landed. The desk was
done and the phone was still showing a spinning cube. Three of the waits in
that gap were the app's own and none of them was work:

1. The encoder rebuild ran AFTER `layout_state` went out. `layout_state` is
   what arms the phone's settle watcher, so the watcher spent the whole ffmpeg
   spawn (~470 ms on his PC) unable to score a single sample — the new session
   had not decoded a frame yet. Ending the session BEFORE the send overlaps the
   two instead of queueing them.
2. A DELIBERATE session end paid the error-loop brake. `_h264_loop` sleeps a
   full second whenever a session dies younger than two seconds, which is the
   correct answer to the 2026-07-29 storm (171 open failures in 90 s) and the
   wrong answer to a layout change, which is a healthy session ending on
   purpose. The brake now reads a mark the closing code sets, not the clock.
3. One user layout switch was done TWICE. On a fresh connection the server
   sends an interim `layout_state` with `active: null` and only then focuses
   the layout it remembers — and `active: null` is exactly the trigger the
   phone's own restore waits for, so it asked for the same focus a round trip
   later. His log: 11 of 60 "Layout N focused" lines within one second of the
   previous, 17 of 57 encoder opens discarded inside five seconds. Each
   duplicate is another whole rebuild inside the overlay he is watching.

And one wait outside that path, same shape: `recents.open_entry` slept before
it first looked for the window it had just opened.

THE RULE NONE OF THIS MAY WEAKEN (owner 2026-08-03, said more than once): the
overlay drops on EVIDENCE — the streamed picture standing still — never on a
timer. Nothing here touches the settle constants, and the client half of this
round makes the evidence STRICTER, not looser (tests/test_picture_hold.py).

What is proven here:

  * the choke point ends the mismatched session BEFORE it sends the state;
  * a planned close skips the pacing sleep, and a FAILURE STORM still does not
    (driven with the real `web._stream_h264` over the real manager, an encoder
    that dies the instant it is born, and the wall clock as the witness);
  * the interim frame CARRIES the resume, and the page stands down on it;
  * one retry per layout, however many focuses arrive;
  * `recents.open_entry` returns a window that is already there without
    sleeping first.

Run:  .venv\\Scripts\\python tests/test_return_speed.py
"""

import asyncio
import json
import sys
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tests"))
sys.path.insert(0, str(PROJECT / "server"))

import layout_api  # noqa: E402
import recents  # noqa: E402
import web  # noqa: E402

import test_stream_lifecycle as sl  # noqa: E402  — the real loop's harness

CONNECTION = (PROJECT / "client" / "connection.js").read_text(encoding="utf-8")

HIS_REGION = {"x": 0.3736979166666667, "y": 0.000462962962962963,
              "w": 0.25234375, "h": 0.9708333333333333}


# ── 1. The reset comes first ────────────────────────────────────────────────
class _OrderWs:
    """Records the ORDER of everything the choke point does."""

    def __init__(self, log):
        self.log = log

    async def send_text(self, text: str) -> None:
        self.log.append("state:" + json.loads(text)["type"])


class _Layouts:
    def __init__(self, active=0):
        self._active = active

    def state(self, active, region):
        return {"type": "layout_state", "layouts": [], "active": active,
                "region": region, "orient": "landscape"}


def check_the_encoder_is_rebuilt_before_the_phone_is_told():
    log = []
    conn = {"active": 0, "region": HIS_REGION, "stream_region": None,
            "reset_stream": lambda: log.append("reset")}
    asyncio.run(layout_api.send_layout_state(_OrderWs(log), _Layouts(), conn))
    assert log == ["reset", "state:layout_state"], (
        "the encoder rebuild no longer overlaps the phone's catch-up: " + str(log))
    # …and the unchanged case still sends exactly one thing and resets nothing.
    log.clear()
    conn = {"active": 0, "region": HIS_REGION, "stream_region": HIS_REGION,
            "reset_stream": lambda: log.append("reset")}
    asyncio.run(layout_api.send_layout_state(_OrderWs(log), _Layouts(), conn))
    assert log == ["state:layout_state"], log
    print("  the session ends BEFORE the state frame, and only on a real change")


# ── 2. The pacing sleep ─────────────────────────────────────────────────────
class _DyingFfmpeg(sl.FakeFfmpeg):
    """An encoder that writes its init segment and dies at once — a session
    that is over milliseconds after it opened, with the socket perfectly
    healthy. That is the shape of the 2026-07-29 storm."""

    def _produce(self) -> None:
        self._out.feed(sl.INIT_SEGMENT)
        self._out.eof()


def _install(popen) -> None:
    sl.install_fakes()
    import h264_streamer
    h264_streamer.subprocess.Popen = popen


def check_a_planned_close_skips_the_brake():
    _install(sl.FakeFfmpeg)
    manager = sl.fresh_manager()
    conn: dict = {}
    took = []

    async def run():
        ws = sl.FakeWs()
        task = asyncio.create_task(web._stream_h264(ws, manager, "t", conn))
        for _ in range(200):                    # wait for a real live session
            await asyncio.sleep(0.02)
            if ws.chunks >= 1 and conn.get("reset_stream"):
                break
        assert ws.chunks >= 1, "the stream never got going"
        assert len(sl.FakeFfmpeg.instances) == 1
        started = time.monotonic()
        conn["reset_stream"]()                  # a layout region change
        for _ in range(200):
            await asyncio.sleep(0.02)
            if len(sl.FakeFfmpeg.instances) == 2:
                break
        took.append(time.monotonic() - started)
        task.cancel()
        await sl._drain(task)

    asyncio.run(run())
    for proc in sl.FakeFfmpeg.instances:
        proc.force_stop()
    assert len(sl.FakeFfmpeg.instances) == 2, "the loop never reopened"
    assert took[0] < 0.6, (
        f"a deliberate reset still paid the error-loop brake: {took[0]:.2f}s "
        "— that is the second the owner waits for on every layout switch")
    print(f"  a planned close reopens in {took[0] * 1000:.0f} ms, not ~1,000")


def check_a_failure_storm_is_still_paced():
    """THE HALF THAT MAY NOT BE LOST. The brake exists for 2026-07-29: 171
    session opens in 90 seconds. Here every session dies the instant it is
    born, and NOBODY planned it — so the loop must still be held to about one
    per second, exactly as before."""
    _install(_DyingFfmpeg)
    manager = sl.fresh_manager()

    async def run():
        task = asyncio.create_task(
            web._stream_h264(sl.FakeWs(), manager, "t", {}))
        await asyncio.sleep(2.5)
        task.cancel()
        await sl._drain(task)

    asyncio.run(run())
    opens = len(sl.FakeFfmpeg.instances)
    for proc in sl.FakeFfmpeg.instances:
        proc.force_stop()
    assert opens >= 2, "nothing reopened at all — the storm case proves nothing"
    assert opens <= 4, (
        f"{opens} encoder opens in 2.5 s — the 2026-07-29 error loop is back")
    print(f"  an unplanned death storm is still paced: {opens} opens in 2.5 s")


# ── 3. One focus per switch ─────────────────────────────────────────────────
def check_the_interim_frame_carries_the_resume_and_the_page_stands_down():
    sent = []

    class _Ws:
        async def send_text(self, text):
            sent.append(json.loads(text))

    asyncio.run(layout_api.send_layout_state(
        _Ws(), _Layouts(), {"active": None, "region": None}, resuming=2))
    assert sent[-1].get("resuming") == 2, (
        "the interim frame no longer says a resume is in flight — the phone "
        "will ask for the same focus a round trip later")
    sent.clear()
    # Absent by default: a frame that says nothing about a resume must change
    # nothing, so an older page keeps its own restore exactly as it was.
    asyncio.run(layout_api.send_layout_state(
        _Ws(), _Layouts(), {"active": None, "region": None}))
    assert "resuming" not in sent[-1], "every frame now claims a resume"

    web_src = (PROJECT / "server" / "web.py").read_text(encoding="utf-8")
    assert "send_layout_state(ws, layouts, conn, resuming=resume)" in web_src, \
        "the connection's interim frame does not carry the resume it is about to do"
    assert web_src.index("resume = await asyncio.to_thread(layouts.resume_index)") \
        < web_src.index("send_layout_state(ws, layouts, conn, resuming=resume)"), \
        "the resume is read AFTER the frame it has to ride on"
    assert "msg.resuming !== undefined" in CONNECTION, \
        "the page ignores the field and still sends its own duplicate focus"
    stand_down = CONNECTION.index("msg.resuming !== undefined")
    own_restore = CONNECTION.index("layoutActive === null && layoutRestore")
    assert stand_down < own_restore, \
        "the stand-down branch is BELOW the restore it exists to prevent"
    # The overlay and the rotation lock are the two things that must survive
    # the stand-down: the same seconds still pass, and he still watches them.
    branch = CONNECTION[stand_down:own_restore]
    assert "showLayLoading" in branch and "orientationRestoring = true" in branch, \
        "standing down dropped the overlay or the rotation lock with the send"
    assert "send({ type: \"layout_focus\"" not in branch, \
        "the stand-down branch still sends the duplicate focus"
    print("  the interim frame names the resume, and the page stands down on it")


class _RetryWs:
    async def send_text(self, text): pass


class _RetryLayouts(_Layouts):
    """A layout whose members refuse their exact rect — `placed` False is what
    arms the retry at all."""

    layouts = [object(), object()]

    def focus(self, index, ratio, rect):
        return (HIS_REGION, False)


class _Stream:
    width, height, monitor_index = 3840, 2160, 0


def check_one_retry_per_layout_however_many_focuses_arrive():
    """Driven through the REAL `layout_focus`, three times, on a layout whose
    placement refuses — which is the only path that arms a retry. Before the
    mark, a duplicated focus (see the check above for how one arrives) armed
    two 1.2 s re-places, and both passed the `active` guard: two placement
    passes and two more state frames, each of which the phone answers with a
    fresh viewport. That is the encoder-discard signature in his log."""
    armed = []
    real_retry = layout_api._retry_place
    layout_api.mon_rect = lambda stream: (0, 0, 3840, 2160)

    async def spy(ws, layouts, stream, conn, index):
        armed.append(index)
        await real_retry(ws, layouts, stream, conn, index)

    layout_api._retry_place = spy
    conn = {"active": None, "region": None, "ratio": None}
    layouts = _RetryLayouts()
    try:
        async def run():
            for _ in range(3):
                await layout_api.layout_focus(_RetryWs(), layouts, _Stream(),
                                              conn, 1)
            await asyncio.sleep(1.6)           # the retry's own 1.2 s and then some
        asyncio.run(run())
    finally:
        layout_api._retry_place = real_retry
    assert armed == [1], (
        f"{len(armed)} re-place tasks armed for one layout: {armed}")
    assert not conn.get("retry_place"), "the retry never cleared its own mark"
    print("  one automatic re-place per layout, and it clears its mark")


# ── 4. recents: look first, sleep after ─────────────────────────────────────
def check_recents_returns_a_window_that_is_already_there():
    windows = {}

    recents._visible_hwnds = lambda: dict(windows)
    recents.wm.window_at_hwnd = lambda hwnd: {"hwnd": hwnd, "title": "Explorer",
                                              "process": "explorer.exe",
                                              "icon": None}
    recents._command = lambda app, kind, target: ["explorer.exe"]

    opens_a_window = [True]

    class _Popen:
        def __init__(self, cmd, **kw):
            if opens_a_window[0]:
                windows[4242] = "explorer.exe"  # the window is up on return

    recents.subprocess.Popen = _Popen
    started = time.monotonic()
    info = recents.open_entry("explorer|new|")
    took = time.monotonic() - started
    assert info.get("hwnd") == 4242, info
    assert took < recents.OPEN_POLL_S / 2, (
        f"{took * 1000:.0f} ms to notice a window that was already open — the "
        f"poll still sleeps before it looks ({recents.OPEN_POLL_S * 1000:.0f} ms)")
    # …and a window that never appears still gives up, on time, with a reason.
    windows.clear()
    opens_a_window[0] = False
    recents.OPEN_TIMEOUT_S = 0.4
    started = time.monotonic()
    out = recents.open_entry("explorer|new|")
    assert "error" in out, out
    assert time.monotonic() - started >= 0.3, "the timeout stopped waiting at all"
    print(f"  an instant window is returned in {took * 1000:.0f} ms, and a "
          "missing one still times out")


def main():
    print("RETURN SPEED GATE - nothing in the return path waits for its own sake")
    check_the_encoder_is_rebuilt_before_the_phone_is_told()
    check_the_interim_frame_carries_the_resume_and_the_page_stands_down()
    check_one_retry_per_layout_however_many_focuses_arrive()
    check_recents_returns_a_window_that_is_already_there()
    check_a_planned_close_skips_the_brake()
    check_a_failure_storm_is_still_paced()
    print("OK - all return speed checks passed")


def test_gate():
    main()


if __name__ == "__main__":
    sys.exit(main())
