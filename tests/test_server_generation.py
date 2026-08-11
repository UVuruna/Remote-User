"""Server Generation Gate: a superseded server run owns NOTHING.

Regression proof for the live failure of 2026-08-09, read out of the owner's
own `%LOCALAPPDATA%\\VibeCoder\\server.log` while his GUI showed **STOPPED**
under a phone that was streaming perfectly:

    19:13:52  Started server process [20120]        <- run A
    19:15:04  Shutting down                         <- Apply & restart
    19:15:14  ERROR Server thread did not stop within 10s
    19:15:14  Started server process [20120]        <- run B, serving fine
    19:15:52  Finished server process [20120]       <- run A, 38 s LATE
    19:15:52  ERROR Exception in ASGI application / CancelledError
    19:15:52  Notice channel gone

`stop()` gives up after `timeout` and clears `_thread` — by design, so the
owner is never held hostage by a drain that will not finish. What was missing
is the other half: the thread it gave up on keeps running, and its own
teardown wrote over the LIVE server's world.

    _run:     self.state = "stopped"     -> the STOPPED pill he photographed
    _serve:   self.release_windows()     -> the live layout dropped out of the
                                            always-on-top band mid-session
    _serve:   stream.shutdown()          -> the live encoder killed

Every one of those names is shared, and by the time the ghost reaches them
they belong to the run that took over. So each run now carries a GENERATION,
and only the current one may touch shared state.

What is proven here — with the REAL `ServerController`, its REAL `start()`,
`stop()`, `_run()` and `_serve()`, and NO uvicorn, NO ffmpeg, NO dxcam, NO
Win32 (fakes on the same contracts):

1. A run that outlives its own `stop()` and finishes AFTER the next run is
   serving changes nothing: the state stays "running", the live windows keep
   their band, and the live stream keeps encoding.
2. A `stop()` that gives up on a thread gives up its uvicorn WITH it —
   otherwise that abandoned object is the next stop()'s target and the same
   pill returns one press later.
3. A run superseded while still SETTING UP never reaches the socket: it does
   not publish its pairing over the live run's, and it never binds the port a
   second time.
4. A superseded run that finishes by CRASHING does not report "failed"
   either — a ghost's death says nothing about the live server.
5. ...and the CURRENT run still tears itself down completely — state
   "stopped", windows released, stream shut down — without which this gate
   would pass with the whole teardown deleted.

Checks 2 and 3 came from an adversarial review of the first fix, and both were
real: the first version guarded only the TEARDOWN. `run_blocking()`'s finally
carries the same guard for symmetry; it is deliberately NOT checked here (it
needs the CLI entry point mixed with `start()`/`stop()` on one controller,
which nothing does) — an asymmetry is simply how the guarded half gets copied
wrong later.

Run:  .venv\\Scripts\\python tests/test_server_generation.py
"""

import asyncio
import sys
import threading
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

from config import SETTINGS  # noqa: E402


# ── The fakes ───────────────────────────────────────────────────────────────
# One rule for all of them: same contract as the real thing, none of the
# machine. A gate about WHICH run tears down must not depend on this PC having
# a GPU, a monitor or a VPN.

class FakeUvicorn:
    """A server whose `serve()` ends exactly when the test says so.

    `obeys_exit=False` is the live failure itself: uvicorn draining a
    connection that will not close, so `force_exit` lands and `serve()` still
    runs on for another 38 seconds.
    """

    instances: list["FakeUvicorn"] = []

    def __init__(self, config):
        self.config = config
        self.should_exit = False
        self.force_exit = False
        self.obeys_exit = True
        self.released = False
        self.crash = False
        self.serving = False
        FakeUvicorn.instances.append(self)

    def release(self) -> None:
        self.released = True

    async def serve(self):
        self.serving = True
        try:
            while not self.released and not (self.force_exit and self.obeys_exit):
                await asyncio.sleep(0.005)
            if self.crash:
                raise RuntimeError("ghost run died on the way out")
        finally:
            self.serving = False


class FakeStream:
    """The H.264 manager as `_serve` uses it."""

    instances: list["FakeStream"] = []

    def __init__(self, *_a, **_kw):
        FakeStream.instances.append(self)
        self.mode = "h264"
        self.width = 1920
        self.height = 1080
        self.monitor_index = 0
        self.shut_down = False

    def shutdown(self) -> None:
        self.shut_down = True


class Released:
    """Counts `window_manager.release_all()` — the call that drops the always-
    on-top band the owner's layout is standing in."""

    def __init__(self):
        self.count = 0

    def __call__(self) -> None:
        self.count += 1


def install_fakes():
    """Patch server_core's own namespace, and return the module plus the
    release counter. Nothing here reaches Windows."""
    fake_h264 = types.ModuleType("h264_streamer")
    fake_h264.H264Manager = FakeStream
    sys.modules["h264_streamer"] = fake_h264

    import server_core

    released = Released()
    server_core.window_manager.release_all = released
    server_core.window_manager.repair_stranded = lambda: None
    server_core.window_manager.LayoutRegistry = lambda *a, **k: object()
    server_core.foreground_lock.repair_stranded = lambda: None
    server_core.foreground_lock.apply = lambda _on: None
    server_core.update_handover.announce = lambda: None
    server_core.focus_hook.stop = lambda: None
    server_core.encoders.detect_encoder = lambda: "h264_test"
    server_core.monitors.rect_for_size = lambda *a, **k: (0, 0, 1920, 1080)
    server_core.InputInjector = lambda **kw: object()
    server_core.pairing.generate_token = lambda: "tok"
    server_core.pairing.pairing_urls = lambda _t: {
        "qr": "u", "lan": "u", "tailscale_ip": None}
    server_core.create_app = lambda *a, **kw: object()
    # 202 registers the window-offer route on the app at _serve; this gate's
    # app is a bare object on purpose (routes are not its subject), so the
    # registration is stubbed like every other collaborator above.
    server_core.layout_popup.register = lambda *a, **kw: None
    server_core.recents.register = lambda *a, **kw: None
    server_core.traffic.METER.start = lambda: None
    server_core.uvicorn = types.SimpleNamespace(
        Server=FakeUvicorn, Config=lambda *a, **kw: object())

    object.__setattr__(SETTINGS, "use_h264", True)
    object.__setattr__(SETTINGS, "foreground_lock", False)
    return server_core, released


def wait_for(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def fresh_controller(server_core):
    FakeUvicorn.instances.clear()
    FakeStream.instances.clear()
    return server_core.ServerController()


# ── The checks ──────────────────────────────────────────────────────────────

def check_ghost_run_changes_nothing(server_core, released) -> bool:
    """The photographed bug: run A outlives its stop, run B serves, A finishes
    late — and B is untouched."""
    ctl = fresh_controller(server_core)
    ctl.start()
    if not wait_for(lambda: ctl.state == "running"):
        return False
    ghost = FakeUvicorn.instances[-1]
    ghost.obeys_exit = False                      # the drain that will not end
    ghost_stream = ctl.info                        # run A's published info

    ctl.stop(timeout=0.3)                          # gives up; the thread lives on
    if not ghost.serving:
        return False                               # the premise must really hold

    ctl.start()                                    # run B
    if not wait_for(lambda: ctl.state == "running"):
        return False
    live = FakeUvicorn.instances[-1]
    live_stream = FakeStream.instances[-1]
    live_info = ctl.info
    if live is ghost or live_info is ghost_stream:
        return False
    released_before = released.count
    live_loop = ctl.loop

    ghost.release()                                # …and NOW run A unwinds
    if not wait_for(lambda: not ghost.serving):
        return False
    time.sleep(0.2)                                # let its teardown finish

    return (ctl.state == "running"                 # the pill he photographed
            and ctl.info is live_info              # the live pairing survived
            and ctl.loop is live_loop              # the live loop still reachable
            and ctl._uvicorn is live               # stop() can still stop B
            and released.count == released_before  # his windows kept their band
            and not live_stream.shut_down          # the live encoder still runs
            and live.serving)                      # B never noticed


def check_ghost_crash_is_not_failed(server_core, released) -> bool:
    """A superseded run that dies on the way out must not report FAILED."""
    ctl = fresh_controller(server_core)
    ctl.start()
    if not wait_for(lambda: ctl.state == "running"):
        return False
    ghost = FakeUvicorn.instances[-1]
    ghost.obeys_exit = False
    ghost.crash = True

    ctl.stop(timeout=0.3)
    ctl.start()
    if not wait_for(lambda: ctl.state == "running"):
        return False

    ghost.release()
    if not wait_for(lambda: not ghost.serving):
        return False
    time.sleep(0.2)
    return ctl.state == "running" and ctl.error is None


def check_the_live_run_still_tears_down(server_core, released) -> bool:
    """Without this, the gate would pass with the whole teardown deleted."""
    ctl = fresh_controller(server_core)
    ctl.start()
    if not wait_for(lambda: ctl.state == "running"):
        return False
    stream = FakeStream.instances[-1]
    released_before = released.count

    ctl.stop(timeout=2.0)
    if not wait_for(lambda: ctl.state == "stopped"):
        return False
    return (ctl._uvicorn is None
            and ctl.loop is None
            and released.count > released_before
            and stream.shut_down)


def check_a_stop_that_gives_up_gives_up_the_instance(server_core, released) -> bool:
    """`stop()` clears `_thread` when it gives up — it must give up that run's
    uvicorn with it. Left in place, that abandoned object is the NEXT stop()'s
    target: the "wait for the instance to exist" branch is skipped (the name is
    not None), the exit flags land on the ghost, and the join times out against
    a live thread nobody asked to stop — ending on state="stopped" over a
    serving server. The same pill, one press later."""
    ctl = fresh_controller(server_core)
    ctl.start()
    if not wait_for(lambda: ctl.state == "running"):
        return False
    ghost = FakeUvicorn.instances[-1]
    ghost.obeys_exit = False

    ctl.stop(timeout=0.3)
    if ctl._uvicorn is not None:                   # the abandoned instance
        ghost.release()
        return False

    ghost.release()
    wait_for(lambda: not ghost.serving)
    return True


def check_superseded_during_startup_never_serves(server_core, released) -> bool:
    """A run can be superseded while still SETTING UP — encoder detection,
    pairing and a UIA probe take real time on a busy PC. It must never reach
    the socket: two runs binding the same port is a crash, and its info/loop
    would be published over the live run's."""
    ctl = fresh_controller(server_core)
    gate = threading.Event()
    real_token = server_core.pairing.generate_token

    def slow_token():
        gate.wait(3.0)
        return real_token()

    server_core.pairing.generate_token = slow_token
    try:
        ctl.start()                                # run A: stuck in setup
        time.sleep(0.1)
        if FakeUvicorn.instances:
            return False                           # the premise: no socket yet
        ctl.stop(timeout=0.2)                      # gives up on a starting run

        server_core.pairing.generate_token = real_token
        ctl.start()                                # run B
        if not wait_for(lambda: ctl.state == "running"):
            return False
        live = FakeUvicorn.instances[-1]
        live_info = ctl.info

        gate.set()                                 # …and NOW run A finishes setup
        time.sleep(0.3)
        return (len(FakeUvicorn.instances) == 1     # A never built a server
                and ctl.info is live_info           # nor published its pairing
                and ctl.state == "running"
                and live.serving)
    finally:
        gate.set()
        server_core.pairing.generate_token = real_token


CHECKS = [
    ("a run that outlives its stop changes nothing", check_ghost_run_changes_nothing),
    ("a stop that gives up gives up the instance too",
     check_a_stop_that_gives_up_gives_up_the_instance),
    ("a run superseded during startup never serves",
     check_superseded_during_startup_never_serves),
    ("a superseded run's crash is not FAILED", check_ghost_crash_is_not_failed),
    ("the live run still tears itself down", check_the_live_run_still_tears_down),
]


def main() -> int:
    server_core, released = install_fakes()
    print("=== SERVER GENERATION GATE ===")
    failed = 0
    for name, fn in CHECKS:
        started = time.monotonic()
        try:
            ok = fn(server_core, released)
        except Exception as e:            # a crashing check is a failing check
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  ({time.monotonic() - started:.1f}s)")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"SERVER GENERATION GATE FAILED — {failed} check(s).")
        return 1
    print("SERVER GENERATION GATE PASSED — a superseded run owns nothing.")
    return 0


def test_server_generation():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
