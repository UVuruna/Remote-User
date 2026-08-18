"""CAPTURE RECOVERY GATE — the blue-canvas failure (owner report 2026-08-16).

He connected from the tablet, everything answered — his running applications
were listed, a layout was really built on the PC — except the picture, which
stayed the plain `--canvas-bg` blue for the whole session. dxcam's capture
thread had parked itself inside an infinite output-recovery loop
(`Output is not attached to desktop.`, retried every ~12 s for 3.8 hours in
his own log) and nothing above it noticed: no exception ever left dxcam, so
the server looked healthy while the one thing he wanted was dead.

The fix is `server/capture_recovery.py` (the ladder: abandon the parked
camera without waiting for it, reopen, re-enumerate DXGI if reopening still
grabs nothing) driven by a `CaptureGuard` that judges by the only honest
fact — did a frame arrive — wired into `server/capture.py`
(`frame_age`/`rebuild_camera`/`_fresh_camera`/the `start()` escalation) and
`server/h264_streamer.py` (`H264Manager._guard`, `_picture_is_wanted`,
`shutdown()`), and told to the phone by `server/web.py`
(`capture_recovery.phone_notice`).

THIS GATE NEVER TOUCHES A REAL DESKTOP OR OPENS A REAL CAMERA (the
`tests/test_birth_radial.py` rule, restated in this project's CLAUDE.md): the
`dxcam` module is REPLACED in `sys.modules` — a `types.SimpleNamespace` fake,
installed before `capture` or `capture_recovery` import it — the same
technique `tests/test_capture_handover.py` uses, and for the same reason: both
modules do `import dxcam` at module scope, so patching the one object in
`sys.modules` reaches both without touching either file.

`CaptureGuard.tick()` is deliberately public and clock-injectable ("split out
of the thread so a gate can drive it with its own clock instead of sleeping
through real seconds" — its own docstring) — checks 1-5 drive it directly,
with a fake capture object, and start no real thread at all.

Run:  .venv\\Scripts\\python tests/test_capture_recovery.py
"""

import sys
import threading
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))


# ── The fake dxcam module — installed BEFORE capture/capture_recovery import it ──

class FakeCamera:
    """dxcam's DXCamera, reduced to what capture.py + capture_recovery.py
    touch: width/height, is_released, start/stop/release/grab/get_latest_frame."""

    def __init__(self, index=0, *, will_grab=True):
        self.index = index
        self.width, self.height = 3840, 2160
        self.is_released = False
        self._will_grab = will_grab
        self.release_calls = 0

    def start(self, **kwargs):
        pass

    def stop(self):
        pass

    def release(self):
        self.release_calls += 1
        self.is_released = True

    def grab(self):
        return _FRAME if self._will_grab else None

    def get_latest_frame(self):
        time.sleep(0.005)  # never a tight spin in the capture thread
        return _FRAME


class Factory:
    """Controls what `dxcam.create()` hands back — a queue of prepared
    cameras/exceptions for rungs under test, falling back to an ordinary
    working camera so setup calls (BaseCapture.__init__) never need one."""

    def __init__(self):
        self.creates = 0
        self.queue: list = []

    def create(self, output_idx=0, output_color="BGR"):
        self.creates += 1
        if self.queue:
            item = self.queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return FakeCamera(output_idx)

    def reset(self):
        self.creates = 0
        self.queue = []


FACTORY = Factory()


class _SingletonMeta(type):
    """Reproduces the ONE shape `capture_recovery.reenumerate_dxgi` reaches
    into: a metaclass-cached singleton with an `_instances` dict the function
    pops from to force a fresh instance."""
    _instances: dict = {}

    def __call__(cls, *a, **kw):
        if cls not in _SingletonMeta._instances:
            _SingletonMeta._instances[cls] = super().__call__(*a, **kw)
        return _SingletonMeta._instances[cls]


class FakeDXFactory(metaclass=_SingletonMeta):
    def __init__(self):
        self.devices = ["fake-device"]


sys.modules["dxcam"] = types.SimpleNamespace(
    create=lambda output_idx=0, output_color="BGR": FACTORY.create(output_idx, output_color),
    output_info=lambda: "Device[0] Output[0]:",
    DXFactory=FakeDXFactory,
)

import numpy as np  # noqa: E402

_FRAME = np.zeros((16, 16, 3), dtype=np.uint8)

import capture  # noqa: E402
import capture_recovery  # noqa: E402
import h264_streamer  # noqa: E402

# ONE PROCESS, TWO FAKE DXCAMS (task VC-T, 2026-08-18). `sys.modules["dxcam"]`
# is set here BEFORE `capture` is imported, which is right — but its sibling
# gate does the same with a fake of its own, and `capture.py` does
# `import dxcam` at module level, so whichever gate imported `capture` FIRST
# binds its fake into it for the whole run. Alone, each gate passes; together,
# one of them drove its own factory while `capture` used the other's.
#
# Re-binding the module attribute is the fix and it costs nothing: this gate's
# fake is the one `capture` uses while this gate runs, and `tests/conftest.py`
# puts back whatever was there when the test ends.
_MY_DXCAM = sys.modules["dxcam"]


def _reset():
    capture.dxcam = capture_recovery.dxcam = _MY_DXCAM  # see the note above _MY_DXCAM
    FACTORY.reset()
    capture._OWNERS.clear()
    _SingletonMeta._instances.clear()


class DummyCapture(capture.BaseCapture):
    """A concrete BaseCapture — `_process` is never exercised by these checks,
    only real enough to satisfy the abstract method."""

    def _process(self, frame) -> None:
        pass


def _new_dummy():
    return DummyCapture()


# ── Checks 1-5: CaptureGuard.tick(), driven directly — no threads, no dxcam ──

class FakeCaptureObj:
    """What CaptureGuard actually needs of a capture: `frame_age()` and
    `rebuild_camera()`. Not `capture.py` at all — the guard's contract is
    proven in isolation, exactly as its own docstring invites."""

    def __init__(self):
        self.age = 0.0
        self.rebuild_calls = 0

    def frame_age(self) -> float:
        return self.age

    def rebuild_camera(self) -> bool:
        self.rebuild_calls += 1
        return True


def check_healthy_never_rebuilds() -> bool:
    cap = FakeCaptureObj()
    cap.age = 0.1
    states = []
    guard = capture_recovery.CaptureGuard(
        cap, is_wanted=lambda: True, on_state=lambda ok, d: states.append((ok, d)))
    for _ in range(5):
        guard.tick()
    return cap.rebuild_calls == 0 and states == []


def check_stall_rebuilds_and_announces_once() -> bool:
    cap = FakeCaptureObj()
    cap.age = capture_recovery.STALL_SECONDS + 1.0
    states = []
    guard = capture_recovery.CaptureGuard(
        cap, is_wanted=lambda: True, on_state=lambda ok, d: states.append(ok))
    guard.tick()
    guard.tick()  # still stalled, still inside cooldown — must NOT re-announce
    guard.tick()
    return cap.rebuild_calls == 1 and states == [False]


def check_cooldown_holds_then_releases() -> bool:
    cap = FakeCaptureObj()
    cap.age = capture_recovery.STALL_SECONDS + 1.0
    # Starts at a NONZERO time deliberately: `_last_attempt` is 0.0 before the
    # first rebuild, and 0.0 is falsy in Python — a clock that itself starts
    # at 0.0 would make the guard's `if self._last_attempt and ...` cooldown
    # check silently no-op on its very first real cooldown window, which
    # `time.monotonic()` never does in production but a naive fake clock can.
    t = [1000.0]
    guard = capture_recovery.CaptureGuard(
        cap, is_wanted=lambda: True, cooldown_s=20.0, clock=lambda: t[0])
    guard.tick()
    if cap.rebuild_calls != 1:
        return False
    t[0] = 1010.0  # inside the 20 s cooldown
    guard.tick()
    if cap.rebuild_calls != 1:
        return False
    t[0] = 1020.1  # past it
    guard.tick()
    return cap.rebuild_calls == 2


def check_not_wanted_never_stalls() -> bool:
    cap = FakeCaptureObj()
    cap.age = 999999.0  # arbitrarily old
    guard = capture_recovery.CaptureGuard(cap, is_wanted=lambda: False)
    for _ in range(5):
        guard.tick()
    return cap.rebuild_calls == 0


def check_recovery_announces_true_once_after_down() -> bool:
    cap = FakeCaptureObj()
    states = []
    guard = capture_recovery.CaptureGuard(
        cap, is_wanted=lambda: True, on_state=lambda ok, d: states.append(ok))
    cap.age = capture_recovery.STALL_SECONDS + 1.0
    guard.tick()  # goes down
    cap.age = 0.1
    guard.tick()  # recovers
    guard.tick()  # stays healthy — no repeat
    if states != [False, True]:
        return False
    # ...and a guard that was NEVER down must never announce True either.
    cap2 = FakeCaptureObj()
    cap2.age = 0.1
    states2 = []
    guard2 = capture_recovery.CaptureGuard(
        cap2, is_wanted=lambda: True, on_state=lambda ok, d: states2.append(ok))
    guard2.tick()
    guard2.tick()
    return states2 == []


# ── Check 6: abandon_camera — prompt release vs. a parked one ──────────────

def check_abandon_camera_prompt_vs_hung() -> bool:
    prompt = types.SimpleNamespace(release=lambda: None)
    ok = capture_recovery.abandon_camera(prompt, wait_s=0.3)
    if ok is not True or hasattr(prompt, "_is_released"):
        return False

    class HangingCamera:
        def release(self_inner):
            threading.Event().wait(5)  # never set inside this check — parked

    hung = HangingCamera()
    ok2 = capture_recovery.abandon_camera(hung, wait_s=0.15)
    return ok2 is False and getattr(hung, "_is_released", False) is True


# ── Checks 7-9: capture.py's rebuild ladder, through the fake dxcam module ──

def check_rebuild_escalates_through_reenumerate() -> bool:
    _reset()
    cap = _new_dummy()
    # rung 'reopen' constructs fine but yields no frame — the trap this
    # module exists to refuse ("reports the blue screen as fixed").
    FACTORY.queue = [FakeCamera(will_grab=False)]
    if cap._fresh_camera("probe") is not None:
        return False  # a camera that cannot grab must never be accepted
    FACTORY.queue = [FakeCamera(will_grab=False), FakeCamera(will_grab=True)]
    ok = cap.rebuild_camera()
    good = cap._camera
    cap.close()
    return ok is True and good is not None and good.width == 3840


def check_rebuild_restores_previous_on_total_failure() -> bool:
    _reset()
    cap = _new_dummy()
    previous = cap._camera
    FACTORY.queue = [FakeCamera(will_grab=False), FakeCamera(will_grab=False)]
    ok = cap.rebuild_camera()
    restored = cap._camera is previous
    cap.close()
    return ok is False and restored


def check_start_escalates_when_double_start_fails() -> bool:
    _reset()
    cap = _new_dummy()

    class DoubleFailCamera:
        def __init__(self):
            self.start_calls = 0

        def start(self, **kwargs):
            self.start_calls += 1
            raise RuntimeError("Capture is already running. Call stop() first.")

        def stop(self):
            raise RuntimeError("bare double-stop")  # dxcam's real behaviour

        def get_latest_frame(self):
            time.sleep(0.005)
            return _FRAME

    cap._camera = DoubleFailCamera()
    rebuild_calls = []
    real_rebuild = cap.rebuild_camera

    def spy_rebuild(_already_stopped=False):
        rebuild_calls.append(_already_stopped)
        cap._camera = FakeCamera(will_grab=True)
        return True

    cap.rebuild_camera = spy_rebuild
    try:
        cap.start()  # must NOT raise the same "already running" error again
        ok = len(rebuild_calls) == 1 and cap._running is True
    finally:
        cap.rebuild_camera = real_rebuild
        cap.stop()
        cap.close()
    return ok


# ── Checks 10-11: H264Manager, capture patched out entirely ────────────────

class FakeSource:
    """Stands in for RawFrameSource — not `capture.py` at all, per the task's
    own instruction, so the manager's own logic is what is under test."""

    def __init__(self):
        self.width = self.height = 100
        self.stream_w = self.stream_h = 100
        self.monitor_index = 0
        self.started = False

    def frame_age(self) -> float:
        return 0.0

    def rebuild_camera(self) -> bool:
        return True

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.started = False

    @staticmethod
    def output_count() -> int:
        return 1


def _fake_manager():
    real = h264_streamer.RawFrameSource
    h264_streamer.RawFrameSource = FakeSource
    try:
        return h264_streamer.H264Manager("libx264")
    finally:
        h264_streamer.RawFrameSource = real


def check_picture_is_wanted_states() -> bool:
    mgr = _fake_manager()
    try:
        if mgr._picture_is_wanted() is not False:
            return False  # source not running yet
        mgr._shut_down = True
        if mgr._picture_is_wanted() is not False:
            return False
        mgr._shut_down = False
        mgr._source_running = True
        if mgr._picture_is_wanted() is not False:
            return False  # nobody connected
        token = object()
        mgr._sessions.add(token)
        live = mgr._picture_is_wanted() is True
        mgr._sessions.discard(token)
        hold = object()
        with mgr._holds_lock:
            mgr._holds.add(hold)
        held = mgr._picture_is_wanted() is True
        with mgr._holds_lock:
            mgr._holds.discard(hold)
        return live and held
    finally:
        mgr._sessions.clear()
        mgr.shutdown()


def check_guard_stopped_by_shutdown() -> bool:
    mgr = _fake_manager()
    guard = mgr._guard
    running_before = guard._thread is not None
    mgr.shutdown()
    return running_before and guard._thread is None


# ── Check 12: capture_recovery.phone_notice ─────────────────────────────────

def check_phone_notice_sends_and_swallows_errors() -> bool:
    import asyncio

    sent = []

    async def good_toast(ws, text):
        sent.append((ws, text))

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    try:
        ws = object()
        notice = capture_recovery.phone_notice(ws, loop, good_toast)
        notice(True, "")
        notice(False, "")
        for _ in range(50):
            if len(sent) >= 2:
                break
            time.sleep(0.02)
        if len(sent) != 2 or sent[0][1] != "The PC's picture is back" \
                or sent[1][1] != "The PC lost its picture":
            return False

        async def raising_toast(ws, text):
            raise RuntimeError("socket is already gone")

        notice2 = capture_recovery.phone_notice(ws, loop, raising_toast)
        # `notice()` schedules its coroutine fire-and-forget
        # (`run_coroutine_threadsafe`, never awaited by the caller), so an
        # exception INSIDE it can never reach this thread by raising out of
        # `notice2(...)` — a swallow-or-not defect would be invisible to a
        # bare "did this call raise" assertion. Spy on the scheduling call
        # instead and read the concurrent.futures.Future it produces: `None`
        # means `_send` swallowed the exception (the contract); a real
        # exception means it leaked, which is the defect this proves.
        real_schedule = asyncio.run_coroutine_threadsafe
        captured: list = []

        def spy(coro, lp):
            fut = real_schedule(coro, lp)
            captured.append(fut)
            return fut

        capture_recovery.asyncio.run_coroutine_threadsafe = spy
        try:
            notice2(True, "")
        finally:
            capture_recovery.asyncio.run_coroutine_threadsafe = real_schedule
        if not captured:
            return False  # notice() must always schedule something
        return captured[0].exception(timeout=2.0) is None
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=2)
        loop.close()


def check_a_failed_open_runs_the_ladder_and_reports_honestly() -> bool:
    """T135 — HIS RECONNECT LOOP (owner report 2026-08-17), at the boundary
    the loop actually ran through.

    His server.log, six cycles one every six seconds, 09:24:02 to 09:24:26:
    a dead camera (`AttributeError: 'NoneType' has no 'AcquireNextFrame'`),
    then `H.264 session failed to open`, then `Client disconnected`, then
    `Client authenticated` a second later — forever, because a new CONNECTION
    has never fixed DXGI. `CaptureGuard` could not save him: it judges by the
    frame clock while a session STREAMS, and here no session ever opened.

    So the ladder needed a second door, and this drives it: a failed open must
    RUN the ladder, and must report what really happened — True only when a
    camera that produced a frame is installed, False when it could not, so the
    caller closes the socket and the phone is told instead of being left to
    flap.

    PLANTED, separately:
      * `recover_for_open` returning True unconditionally — the false True is
        caught, which matters more than the false False: it would send the
        caller back to retry a session against a camera that still cannot
        grab, i.e. rebuild his loop with an extra step in it.
      * `rebuild_camera` never called at all (the pre-fix state, where the
        open-failure path simply closed the socket) — the ladder-ran check
        fails.
    """
    _reset()
    cap = _new_dummy()
    calls = []
    real = cap.rebuild_camera
    cap.rebuild_camera = lambda *a, **k: (calls.append(1), real(*a, **k))[1]

    # (a) the ladder finds a camera that really grabs -> True, and it RAN.
    FACTORY.queue = [FakeCamera(will_grab=True)]
    healed = capture_recovery.recover_for_open(cap, RuntimeError("no init segment"))
    ran = bool(calls)

    # (b) every rung fails -> False, never an optimistic True.
    FACTORY.queue = [FakeCamera(will_grab=False), FakeCamera(will_grab=False)]
    hopeless = capture_recovery.recover_for_open(cap, RuntimeError("no init segment"))

    # (c) a capture that RAISES must not take the connection down with it.
    class _Raiser:
        def rebuild_camera(self):
            raise OSError("device removed")
    raised = capture_recovery.recover_for_open(_Raiser(), RuntimeError("x"))

    # (d) no capture at all is False, not a crash.
    none_case = capture_recovery.recover_for_open(None, RuntimeError("x"))
    cap.close()

    if not ran:
        print("    the ladder was never run on a failed open")
        return False
    if healed is not True:
        print(f"    a recovered camera reported {healed!r}, not True")
        return False
    if hopeless is not False:
        print(f"    an unrecoverable camera reported {hopeless!r} — a false True "
              f"sends the caller back into the owner's own loop")
        return False
    if raised is not False or none_case is not False:
        print("    a raising or missing capture must be False, never an exception")
        return False
    return True


def check_the_open_failure_path_calls_the_ladder_before_closing() -> bool:
    """The WIRING, at the method boundary — because the check above proves the
    ladder works and says nothing about whether anything calls it, which is
    exactly the state that shipped: the ladder existed for months while the
    open-failure path closed the socket without ever asking it.

    PLANTED: `H264Manager.recover_capture` removed, or wired to something
    other than its own source — this fails at the attribute or on the source
    identity.
    """
    import h264_streamer
    if not hasattr(h264_streamer.H264Manager, "recover_capture"):
        print("    H264Manager has no recover_capture — the open-failure path "
              "has nothing to call")
        return False
    seen = {}
    real = capture_recovery.recover_for_open
    def _spy(cap, err):
        seen["cap"] = cap
        return True
    capture_recovery.recover_for_open = _spy
    try:
        mgr = object.__new__(h264_streamer.H264Manager)
        sentinel = object()
        mgr._source = sentinel
        out = h264_streamer.H264Manager.recover_capture(mgr, RuntimeError("x"))
    finally:
        capture_recovery.recover_for_open = real
    if seen.get("cap") is not sentinel:
        print("    the manager handed the ladder something other than its own source")
        return False
    if out is not True:
        print("    the manager did not return the ladder's own verdict")
        return False
    # And web.py must actually call it on the first failed open, before close.
    web = (Path(__file__).resolve().parent.parent / "server" / "web.py").read_text(
        encoding="utf-8")
    if "manager.recover_capture" not in web:
        print("    web.py never calls recover_capture — the ladder has no door "
              "onto the failure the owner actually hit")
        return False
    return True


CHECKS = [
    ("a healthy capture never rebuilds", check_healthy_never_rebuilds),
    ("a stall while watched rebuilds and announces ok=False once",
     check_stall_rebuilds_and_announces_once),
    ("the cooldown holds a second tick, then releases past it",
     check_cooldown_holds_then_releases),
    ("nobody watching never counts as a stall, however old the frame",
     check_not_wanted_never_stalls),
    ("recovery announces ok=True once, only after having been down",
     check_recovery_announces_true_once_after_down),
    ("abandon_camera: prompt release True/unmarked, hung release False/marked",
     check_abandon_camera_prompt_vs_hung),
    ("rebuild_camera escalates past a camera that cannot grab, to re-enumerate",
     check_rebuild_escalates_through_reenumerate),
    ("rebuild_camera restores the previous camera when every rung fails",
     check_rebuild_restores_previous_on_total_failure),
    ("start() escalates to rebuild_camera on a double dxcam refusal",
     check_start_escalates_when_double_start_fails),
    ("H264Manager._picture_is_wanted reads shutdown/running/sessions/holds",
     check_picture_is_wanted_states),
    ("H264Manager.shutdown() stops the guard", check_guard_stopped_by_shutdown),
    ("phone_notice sends both states and swallows a raising toast",
     check_phone_notice_sends_and_swallows_errors),
    ("a failed OPEN runs the ladder and reports honestly (T135)",
     check_a_failed_open_runs_the_ladder_and_reports_honestly),
    ("the open-failure path really calls the ladder (T135 wiring)",
     check_the_open_failure_path_calls_the_ladder_before_closing),
]


def main() -> int:
    print("=== CAPTURE RECOVERY GATE ===")
    failed = 0
    for name, fn in CHECKS:
        started = time.monotonic()
        try:
            ok = fn()
        except Exception as e:  # a crashing check is a failing check
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  ({time.monotonic() - started:.1f}s)")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"CAPTURE RECOVERY GATE FAILED — {failed} check(s).")
        return 1
    print("CAPTURE RECOVERY GATE PASSED — a dead camera is replaced, and the "
          "phone is told.")
    return 0


def test_capture_recovery():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
