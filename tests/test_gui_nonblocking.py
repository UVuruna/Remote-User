"""GUI Non-Blocking Gate: the desktop window's own header must be true.

[Main Window](../server/gui/main_window.py) has always opened with "the window
never blocks". On 2026-08-12 that was measured and it was false in the two
worst places it could be:

  * `pairing.pairing_urls()` — a UDP socket with a 1 s timeout plus the
    Tailscale CLI with a 3 s one, called STRAIGHT from the 1 s refresh timer
    every fifth tick for as long as Tailscale is not signed in. Up to ~4 s of
    frozen window, over and over, in exactly the state a first-time user sits
    in while he waits for this window to tell him his phone can reach the PC.
  * `ServerController.stop()` — joins the server thread for up to 10 s, and
    the tray's Quit called it inline: ten seconds of a dead window after he
    had already chosen to leave.

Both now go through [Off-thread](../server/gui/offthread.py). What is proven
here is the only thing that matters to him — TIME ON THE GUI THREAD — measured
with a call that deliberately takes seconds, so a regression that moves either
one back inline cannot pass. The methods are driven UNBOUND against a stub,
which is deliberate: it is the scheduling that is under test, not Qt, and a
gate that had to build the whole window would be the first thing skipped.

The two promises that go with them are here too, because dropping either would
be silent: a quit still releases the desk's windows FIRST (owner decree
2026-08-05 — nothing may be left nailed above his desk because a quit was
slow), and it still leaves even if the stop never finishes.

Run:  .venv\\Scripts\\python tests/test_gui_nonblocking.py
"""

import sys
import threading
import time
import types
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

from gui import offthread  # noqa: E402

# Server control (start / stop / restart / quit) became a MIXIN on
# 2026-08-18 (VC-R3). This gate reads whichever file now holds each call
# site: the pairing worker is still the window's, the quit is the mixin's.
MAIN_WINDOW_SERVER = (PROJECT / "server" / "gui" / "main_window_server.py"
                      ).read_text(encoding="utf-8")
MAIN_WINDOW = (PROJECT / "server" / "gui" / "main_window.py").read_text(
    encoding="utf-8")

SLOW = 1.5   # what a blocking call costs; the real ones are 4 s and 10 s
FAST = 0.25  # what "did not block" means, generously


class _FakeTimer:
    """Only what `_quit` asks of a QTimer: start it, stop it, and be able to
    fire. Nothing here needs a Qt event loop to prove a call did not block."""

    def __init__(self, *a):
        self.interval = None
        self.stopped = False
        self._fn = None
        self.timeout = types.SimpleNamespace(connect=self._connect)

    def _connect(self, fn):
        self._fn = fn

    def start(self, ms=None):
        self.interval = ms

    def stop(self):
        self.stopped = True

    def fire(self):
        if self._fn:
            self._fn()


def _stub(stop_delay=0.0):
    """A stand-in for the window: the attributes the two methods touch, and a
    controller whose stop() takes as long as the real one can."""
    order = []

    def stop():
        order.append("stop-start")
        time.sleep(stop_delay)
        order.append("stop-done")

    controller = types.SimpleNamespace(
        info=types.SimpleNamespace(token="t", qr_url="old", lan_url="",
                                   tailscale_ip=None),
        stop=stop,
        release_windows=lambda: order.append("release"),
    )
    return types.SimpleNamespace(
        controller=controller, order=order,
        _pairing_busy=False, _quitting=False,
        _timer=_FakeTimer(), tray=types.SimpleNamespace(hide=lambda: None),
    )


def check_the_pairing_probe_does_not_run_on_the_gui_thread():
    import gui.main_window as mw

    slow_calls = []

    def slow_probe(info):
        slow_calls.append(info)
        time.sleep(SLOW)
        info.qr_url = "new"

    real = offthread.refresh_pairing
    offthread.refresh_pairing = slow_probe
    try:
        win = _stub()
        started = time.monotonic()
        mw.MainWindow._refresh_pairing(win)
        took = time.monotonic() - started
        assert took < FAST, (
            f"the pairing probe held the GUI thread for {took:.2f}s — that is "
            "the frozen window a first-time user sits in front of")
        # …and it really did run, off to the side, and really did land.
        for _ in range(100):
            time.sleep(0.05)
            if not win._pairing_busy:
                break
        assert slow_calls, "the probe never ran at all"
        assert win.controller.info.qr_url == "new", \
            "the worker's answer never reached the controller's info"
        assert not win._pairing_busy, "the busy flag was never cleared"
        # A second tick while one is in flight must not pile up a second probe.
        win._pairing_busy = True
        mw.MainWindow._refresh_pairing(win)
        assert len(slow_calls) == 1, "a slow probe was started twice"
    finally:
        offthread.refresh_pairing = real
    print(f"  the pairing probe returns in {took * 1000:.0f} ms and answers "
          "from the side")


def check_quit_does_not_wait_for_the_server_on_the_gui_thread():
    import gui.main_window as mw
    # `_quit` reads QTimer and QGuiApplication out of the ServerControl
    # mixin's own globals since 2026-08-18 (VC-R3) — patching main_window's
    # would silently stop patching what the code under test reads.
    import gui.main_window_server as mws

    quit_called = []
    real_timer, real_app = mws.QTimer, mws.QGuiApplication
    mws.QTimer = _FakeTimer
    mws.QGuiApplication = types.SimpleNamespace(
        instance=lambda: types.SimpleNamespace(
            quit=lambda: quit_called.append(time.monotonic())))
    try:
        win = _stub(stop_delay=SLOW)
        started = time.monotonic()
        mw.MainWindow._quit(win)
        took = time.monotonic() - started
        assert took < FAST, (
            f"Quit held the GUI thread for {took:.2f}s — the window sits dead "
            "on his screen after he has already asked to leave")
        # THE DESK FIRST (owner decree 2026-08-05).
        assert win.order and win.order[0] == "release", (
            f"the windows were not released before the stop: {win.order}")
        # It has NOT quit yet — a poll that fires early would kill the server
        # mid-stop, which is what the whole wait is for.
        win._quit_timer.fire()
        assert not quit_called, "the app quit while the server was still stopping"
        for _ in range(100):
            time.sleep(0.05)
            win._quit_timer.fire()
            if quit_called:
                break
        assert quit_called, "the app never quit once the server had stopped"
        assert "stop-done" in win.order, "the stop never completed"
        assert win._quit_timer.stopped, "the poll timer was left running"
        # A second Quit (tray menu twice, a fast double click) starts nothing.
        before = len(win.order)
        mw.MainWindow._quit(win)
        assert len(win.order) == before, "a second Quit re-ran the shutdown"
    finally:
        mws.QTimer, mws.QGuiApplication = real_timer, real_app
    print(f"  Quit returns in {took * 1000:.0f} ms and leaves when the server "
          "is really down")


def check_a_wedged_stop_still_lets_the_app_leave():
    """The other half of the same promise: polling instead of waiting must not
    become waiting forever."""
    real_wait = offthread.QUIT_WAIT_S
    offthread.QUIT_WAIT_S = 0.4
    try:
        never = threading.Event()
        controller = types.SimpleNamespace(stop=never.wait)  # stops when told
        finished = offthread.stop_server(controller)
        assert not finished(), "a stop that has not finished reported finished"
        time.sleep(0.5)
        assert finished(), (
            "a wedged stop never reached its deadline — the app would sit on "
            "his screen with no way out")
    finally:
        never.set()
        offthread.QUIT_WAIT_S = real_wait
    print("  a wedged stop still gives up, on time")


def check_nothing_slow_is_left_inline():
    """The call sites, read once — a worker that someone later 'simplifies'
    back into the tick is the whole regression."""
    assert "offthread.run(offthread.refresh_pairing" in MAIN_WINDOW, \
        "the pairing probe is no longer handed to a worker"
    assert "pairing.pairing_urls" not in MAIN_WINDOW, \
        "main_window calls pairing_urls directly again — that is up to 4 s on " \
        "the GUI thread, every fifth tick"
    quit_body = MAIN_WINDOW_SERVER[
        MAIN_WINDOW_SERVER.index("    def _quit(self)"):]
    assert "self.controller.stop()" not in quit_body, \
        "the quit joins the server thread inline again — up to 10 s of frozen " \
        "window after he has asked to leave. (The restart WORKER may call it: " \
        "it is already on a thread.)"
    assert "offthread.stop_server(self.controller)" in MAIN_WINDOW_SERVER
    # And the header may not go back to claiming something untrue.
    head = MAIN_WINDOW[:MAIN_WINDOW.index('"""', 3)]
    assert "offthread" in head, \
        "the module header no longer says where the blocking work went"
    print("  no slow call is left on the window's own thread")


def main():
    print("GUI NON-BLOCKING GATE - the window's own header must be true")
    check_nothing_slow_is_left_inline()
    check_the_pairing_probe_does_not_run_on_the_gui_thread()
    check_quit_does_not_wait_for_the_server_on_the_gui_thread()
    check_a_wedged_stop_still_lets_the_app_leave()
    print("OK - all GUI non-blocking checks passed")


def test_gate():
    main()


if __name__ == "__main__":
    sys.exit(main())
