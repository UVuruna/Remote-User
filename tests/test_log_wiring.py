"""LOG WIRING GATE — the four modules of 2026-08-16/17 are actually CALLED.

`session_log.py`, `log_shipper.py`, `log_summary.py` and `display_watch.py`
each have their own gate proving they WORK. This one proves nothing about
them: it proves they are WIRED — that `server_core.py` really opens a file,
really repairs the previous run's before it does, really closes it once
however the process ends; that a display change really reaches the Settings
window's monitor list AND capture's DXGI re-enumeration; that the captured
monitor disappearing really moves the picture; and that a phone's `auth`
really writes `session.connect`.

WHY A SEPARATE GATE AT ALL, and it is the actions.json lesson of 2026-08-07
restated: a pure module nobody calls is a feature that does not exist. Every
defect this gate exists to catch is invisible in the modules' own tests —
they would all stay green while the app never wrote a line.

THE ORDER IS THE CENTRAL PROMISE. A run that ended without us leaves a file
with NO FOOTER, and that missing footer is the only way the next start can
recognise it (`session_log.is_unclosed`). Repair and sweep therefore have to
finish BEFORE a new file exists — open first and the sweep ships a log that
is still being written.

NO REAL DESKTOP AND NO REAL CAMERA (the `tests/test_capture_recovery.py`
rule): `dxcam` is REPLACED in `sys.modules` before `capture` imports it, and
`display_watch.snapshot` / the Win32 pieces are replaced by fakes, so nothing
here can touch the owner's monitors.

Run:  .venv\\Scripts\\python tests/test_log_wiring.py
"""

import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

# ── fakes installed BEFORE the modules under test import them ────────────────


class FakeCamera:
    def __init__(self, index=0):
        self.index = index
        self.width, self.height = 1920, 1080
        self.is_released = False

    def start(self, **kw):
        pass

    def stop(self):
        pass

    def release(self):
        self.is_released = True

    def grab(self):
        return object()

    def get_latest_frame(self):
        return object()


class _SingletonMeta(type):
    _instances: dict = {}

    def __call__(cls, *a, **kw):
        if cls not in _SingletonMeta._instances:
            _SingletonMeta._instances[cls] = super().__call__(*a, **kw)
        return _SingletonMeta._instances[cls]


class FakeDXFactory(metaclass=_SingletonMeta):
    def __init__(self):
        self.devices = ["fake-device"]


sys.modules["dxcam"] = types.SimpleNamespace(
    create=lambda output_idx=0, output_color="BGR": FakeCamera(output_idx),
    output_info=lambda: "Device[0] Output[0]:",
    DXFactory=FakeDXFactory,
)

import capture  # noqa: E402
import capture_recovery  # noqa: E402
import display_watch  # noqa: E402
import log_shipper  # noqa: E402
import log_summary  # noqa: E402
import session_log  # noqa: E402


SERVER = Path(__file__).resolve().parent.parent / "server"


def _source(name: str) -> str:
    return (SERVER / name).read_text(encoding="utf-8")


def _display(index, w=1920, h=1080, primary=True, scale=100):
    return display_watch.DisplayInfo(index=index, left=0, top=0, width=w,
                                     height=h, primary=primary, scale_pct=scale)


def _diff(added=(), removed=(), changed=(), snapshot=()):
    return display_watch.DisplayDiff(added=tuple(added), removed=tuple(removed),
                                     changed=tuple(changed),
                                     snapshot=tuple(snapshot))


# ── 1. the repair-then-open ORDER ────────────────────────────────────────────


def check_repair_and_sweep_run_before_the_file_is_opened() -> bool:
    """The central promise, driven through the REAL `_start_use_log`.

    Not a source read: this calls the controller's own method with
    `session_log`/`log_shipper` spied on, and asserts the order the app really
    executes. An order proven by reading a file is an order that survives the
    lines being swapped inside a helper.
    """
    import server_core

    order: list[str] = []
    real_repair = server_core.session_log.repair_unclosed
    real_sweep = log_shipper.SHIPPER.sweep
    real_start = server_core.LOG.start
    real_state = server_core.LOG.state
    real_snapshot = server_core.display_watch.snapshot
    try:
        server_core.session_log.repair_unclosed = \
            lambda *a, **kw: order.append("repair") or []
        log_shipper.SHIPPER.sweep = lambda *a, **kw: order.append("sweep")
        server_core.LOG.start = lambda **facts: order.append(("start", facts))
        server_core.LOG.state = lambda kind, **f: order.append(("state", kind, f))
        server_core.display_watch.snapshot = lambda: (_display(0),)

        ctl = server_core.ServerController.__new__(server_core.ServerController)
        import threading
        ctl._log_lock = threading.Lock()
        info = server_core.ServerInfo(
            mode="h264", encoder="h264_nvenc", monitor_width=1920,
            monitor_height=1080, port=8000, token="t", qr_url="", lan_url="",
            tailscale_ip=None)
        ctl._start_use_log(info)
    finally:
        server_core.session_log.repair_unclosed = real_repair
        log_shipper.SHIPPER.sweep = real_sweep
        server_core.LOG.start = real_start
        server_core.LOG.state = real_state
        server_core.display_watch.snapshot = real_snapshot

    names = [o if isinstance(o, str) else o[0] for o in order]
    if names[:3] != ["repair", "sweep", "start"]:
        return False
    # And the HEADER carries only what cannot change while the process lives.
    facts = order[2][1]
    if set(facts) != {"app_version", "install_id", "process_start"}:
        return False
    # Everything observable is STATE, never header.
    states = {o[1] for o in order if o[0] == "state"}
    return {"pc", "app"} <= states


def check_the_repair_skips_the_file_we_just_opened() -> bool:
    """Belt to the ordering's braces: `skip=` is really passed, and it is
    really `LOG.path`. Without it, an edit that ever moved `LOG.start()` above
    the repair would fail SILENTLY — which is the exact class of failure this
    whole feature exists to make visible.

    THE SPY TAKES `**kw` AND ASKS WHETHER THE KEY WAS THERE AT ALL, and that
    is the only reason this check is worth anything. Its first version named
    `skip` as a defaulted parameter and compared it with `LOG.path` — both
    None at this point in a fresh process — so deleting the argument from the
    product passed it just as happily. Planting the defect is what found that;
    until then the check was measuring nothing."""
    import server_core

    seen: dict = {}
    real = server_core.session_log.repair_unclosed
    real_sweep = log_shipper.SHIPPER.sweep
    real_start = server_core.LOG.start
    real_state = server_core.LOG.state
    real_snapshot = server_core.display_watch.snapshot
    try:
        def spy(*args, **kw):
            seen["skip_passed"] = "skip" in kw
            seen["skip"] = kw.get("skip")
            return []
        server_core.session_log.repair_unclosed = spy
        log_shipper.SHIPPER.sweep = lambda *a, **kw: None
        server_core.LOG.start = lambda **f: None
        server_core.LOG.state = lambda *a, **kw: None
        server_core.display_watch.snapshot = lambda: ()

        ctl = server_core.ServerController.__new__(server_core.ServerController)
        import threading
        ctl._log_lock = threading.Lock()
        ctl._start_use_log(server_core.ServerInfo(
            mode="jpeg", encoder=None, monitor_width=1, monitor_height=1,
            port=1, token="t", qr_url="", lan_url="", tailscale_ip=None))
    finally:
        server_core.session_log.repair_unclosed = real
        log_shipper.SHIPPER.sweep = real_sweep
        server_core.LOG.start = real_start
        server_core.LOG.state = real_state
        server_core.display_watch.snapshot = real_snapshot
    return seen.get("skip_passed") is True and seen.get("skip") == server_core.LOG.path


# ── 2. closing, idempotent across the four exits ─────────────────────────────


def check_close_is_idempotent_across_the_four_exits() -> bool:
    """Tray Quit, Qt aboutToQuit, atexit and the console handler ALL reach
    `release_windows()`. Four exits must not footer one file four times, and
    the summary must be written exactly once — for the one file that really
    closed."""
    import server_core
    import threading

    closes: list[str] = []
    summaries: list = []
    offered: list = []
    real_close = server_core.LOG.close
    real_summary = server_core.log_summary.write_summary
    real_offer = log_shipper.SHIPPER.offer
    try:
        state = {"open": True}

        def close(reason="stop"):
            closes.append(reason)
            if not state["open"]:
                return None          # exactly what SessionLog.close does
            state["open"] = False
            return Path("fake.jsonl")
        server_core.LOG.close = close
        server_core.log_summary.write_summary = \
            lambda p: summaries.append(p) or Path("fake.summary.json")
        log_shipper.SHIPPER.offer = lambda p: offered.append(p)

        ctl = server_core.ServerController.__new__(server_core.ServerController)
        ctl._log_lock = threading.Lock()
        for _ in range(4):
            ctl.close_use_log("stop")
    finally:
        server_core.LOG.close = real_close
        server_core.log_summary.write_summary = real_summary
        log_shipper.SHIPPER.offer = real_offer
    return len(closes) == 4 and len(summaries) == 1 and len(offered) == 2


def check_release_windows_closes_the_use_log() -> bool:
    """The close must sit in the funnel every documented exit passes, not in
    one of them. `release_windows()` IS that funnel (constraint 10)."""
    import server_core
    import threading

    calls: list = []
    real = server_core.ServerController.close_use_log
    try:
        server_core.ServerController.close_use_log = \
            lambda self, reason="stop": calls.append(reason)
        ctl = server_core.ServerController.__new__(server_core.ServerController)
        ctl._log_lock = threading.Lock()
        ctl._display_watch = None
        ctl.release_windows()
    finally:
        server_core.ServerController.close_use_log = real
    return calls == ["stop"]


# ── 3. a display diff really reaches BOTH consumers ──────────────────────────


def check_display_diff_reaches_capture_reenumeration() -> bool:
    """A monitor arriving must re-enumerate DXGI, or `dxcam` keeps describing
    the desktop it saw at import (constraint 30) and the new monitor can never
    be opened."""
    calls: list = []
    real = capture_recovery.reenumerate_dxgi
    try:
        capture_recovery.reenumerate_dxgi = lambda: calls.append(True) or True
        capture.on_display_change(
            _diff(added=(_display(1),), snapshot=(_display(0), _display(1))))
    finally:
        capture_recovery.reenumerate_dxgi = real
    return calls == [True]


def check_capture_is_subscribed_to_the_watch() -> bool:
    """The reaction above is only real if the server actually subscribes it.
    Read at the composition root, because that is the only place the wire
    exists."""
    src = _source("server_core.py")
    return ("from capture import on_display_change" in src
            and "watch.subscribe(capture_on_display_change)" in src
            and "watch.start()" in src)


def check_settings_window_repopulates_on_a_display_change() -> bool:
    """The Settings window's monitor list is filled once, when the window is
    BUILT, from an enumeration dxcam made at import — so a monitor plugged in
    mid-run never appeared and reopening the window did not help. It must
    subscribe while open, marshal the callback to the GUI thread, and
    UNSUBSCRIBE on close (a dead window's callback must not be held)."""
    src = (SERVER / "gui" / "settings_window.py").read_text(encoding="utf-8")
    return ("displays_changed = Signal()" in src
            and "watch.subscribe(self._emit_displays_changed)" in src
            and "self.displays_changed.emit()" in src
            and "unsubscribe(self._emit_displays_changed)" in src
            and "def done(self, result: int)" in src
            and "self._fill_monitors(self._monitor_combo)" in src)


def check_the_watch_really_delivers_to_two_subscribers() -> bool:
    """Both consumers on ONE watch: a real `DisplayWatch`, driven through its
    own `_check()`, must call both callbacks with the same diff."""
    watch = display_watch.DisplayWatch()
    got: list = []
    watch.subscribe(lambda d: got.append(("a", d)))
    watch.subscribe(lambda d: got.append(("b", d)))
    watch._last = (_display(0),)
    real = display_watch.snapshot
    try:
        display_watch.snapshot = lambda: (_display(0), _display(1))
        watch._check()
    finally:
        display_watch.snapshot = real
    return ([n for n, _ in got] == ["a", "b"]
            and got[0][1].added and got[0][1].added[0].index == 1)


# ── 4. the captured monitor disappearing moves capture ───────────────────────


class _FakeOwner:
    """What `capture.on_display_change` needs of a live capture."""

    def __init__(self, index):
        self.monitor_index = index
        self.moved_to = None
        self._running = True

    def switch_to(self, index):
        self.moved_to = index
        self.monitor_index = index
        return True


def check_the_captured_monitor_vanishing_moves_capture() -> bool:
    """A monitor we already KNOW is gone must not be waited out by the stall
    ladder — the picture moves to a survivor, and to a SURVIVOR (never back to
    the index that just went)."""
    owner = _FakeOwner(1)
    real = capture_recovery.reenumerate_dxgi
    try:
        capture_recovery.reenumerate_dxgi = lambda: True
        with capture._OWNERS_LOCK:
            capture._OWNERS.clear()
            capture._OWNERS[1] = owner
        capture.on_display_change(
            _diff(removed=(_display(1),), snapshot=(_display(0),)))
    finally:
        capture_recovery.reenumerate_dxgi = real
        with capture._OWNERS_LOCK:
            capture._OWNERS.clear()
    return owner.moved_to == 0


def check_a_surviving_monitor_is_never_moved() -> bool:
    """The other half of the same promise: a change that did not take the
    captured monitor away must move nothing at all."""
    owner = _FakeOwner(0)
    real = capture_recovery.reenumerate_dxgi
    try:
        capture_recovery.reenumerate_dxgi = lambda: True
        with capture._OWNERS_LOCK:
            capture._OWNERS.clear()
            capture._OWNERS[0] = owner
        capture.on_display_change(
            _diff(removed=(_display(1),), snapshot=(_display(0),)))
    finally:
        capture_recovery.reenumerate_dxgi = real
        with capture._OWNERS_LOCK:
            capture._OWNERS.clear()
    return owner.moved_to is None


# ── 5. session.connect is really written on auth ─────────────────────────────


class _FakeWS:
    def __init__(self, host):
        self.headers = {"host": host}


def check_session_connect_is_written_on_auth() -> bool:
    """`presence.log_connect` must write ONE `session.connect` carrying the
    device, the screen and the LINK — and the link must be MEASURED off the
    Host header against the live Tailscale address, never remembered."""
    import presence

    written: list = []
    real_record = session_log.LOG.record
    real_ts = presence.pairing.get_tailscale_ip
    try:
        session_log.LOG.record = lambda kind, **f: written.append((kind, f))
        presence.pairing.get_tailscale_ip = lambda: "100.64.0.5"
        presence.log_connect(_FakeWS("100.64.0.5:8000"),
                             {"panel": {"w": 2400}, "quality": {}},
                             {"w": 1600, "h": 2560, "model": "SM-X200"})
        presence.log_connect(_FakeWS("192.168.1.7:8000"), {}, {"model": "P"})
    finally:
        session_log.LOG.record = real_record
        presence.pairing.get_tailscale_ip = real_ts
    if [k for k, _ in written] != ["session.connect", "session.connect"]:
        return False
    first, second = written[0][1], written[1][1]
    return (first["device"] == "SM-X200" and first["link"] == "tailscale"
            and first["screen"] == {"w": 1600, "h": 2560}
            and second["link"] == "lan")


def check_web_calls_log_connect_on_auth() -> bool:
    """And the page really reaches it — the wire, at its one site, beside the
    traffic meter's own `note_device`."""
    src = _source("web.py")
    return "presence.log_connect(ws, first, screen)" in src


def check_leave_carries_its_reason() -> bool:
    """`session.leave` is written INSIDE `presence.leave_session` — the one
    place all three of its callers pass through — and it carries the reason
    the caller already knew rather than a guess made here."""
    import presence
    import asyncio

    written: list = []
    real = session_log.LOG.record
    try:
        session_log.LOG.record = lambda kind, **f: written.append((kind, f))

        class _Layouts:
            def minimize_members(self, session_end=False):
                pass

            def clear_topmost(self):
                pass

        conn: dict = {"device": "SM-X200"}
        asyncio.run(presence.leave_session(_Layouts(), conn, reason="lock"))
        asyncio.run(presence.leave_session(_Layouts(), conn, reason="lock"))
    finally:
        session_log.LOG.record = real
    # Written once — `leave_session` is idempotent, and a use log must not
    # turn one leave into two.
    leaves = [f for k, f in written if k == "session.leave"]
    return len(leaves) == 1 and leaves[0].get("reason") == "lock"


# ── 6. one notice, one record, at the one choke ──────────────────────────────


def check_notify_deliver_records_the_carrier_once() -> bool:
    """`notify.deliver()` is the single choke every notice passes. ONE record,
    naming which carrier took it and whether it had waited — never one per
    branch, because three copies of one fact drift."""
    import asyncio
    import notify

    written: list = []
    real = session_log.LOG.record
    try:
        session_log.LOG.record = lambda kind, **f: written.append((kind, f))
        notify._pending.clear()
        import time as _time
        # No page, no waiting channel → the queue takes it. Raised NOW, so it
        # has not waited; then one raised an hour ago, which has.
        carrier = asyncio.run(notify.deliver(
            {"agent": "A", "event": "waiting", "at": _time.time()}))
        asyncio.run(notify.deliver(
            {"agent": "B", "event": "finished", "at": _time.time() - 3600}))
    finally:
        session_log.LOG.record = real
        notify._pending.clear()
    if carrier != "held" or len(written) != 2:
        return False
    kind, fields = written[0]
    return (kind == "notice.held" and fields["agent"] == "A"
            and fields["event"] == "waiting" and fields["waited"] is False
            and written[1][1]["waited"] is True)


CHECKS = [
    ("repair and sweep run BEFORE the new file is opened",
     check_repair_and_sweep_run_before_the_file_is_opened),
    ("the repair is told to skip the live file", check_the_repair_skips_the_file_we_just_opened),
    ("closing is idempotent across the four exits — one footer, one summary",
     check_close_is_idempotent_across_the_four_exits),
    ("release_windows() — the exit funnel — closes the use log",
     check_release_windows_closes_the_use_log),
    ("a display change re-enumerates DXGI", check_display_diff_reaches_capture_reenumeration),
    ("capture is really subscribed to the watch", check_capture_is_subscribed_to_the_watch),
    ("the open Settings window repopulates on a display change, and lets go on close",
     check_settings_window_repopulates_on_a_display_change),
    ("one watch delivers one diff to both subscribers",
     check_the_watch_really_delivers_to_two_subscribers),
    ("the captured monitor vanishing moves capture to a survivor",
     check_the_captured_monitor_vanishing_moves_capture),
    ("a change that spares the captured monitor moves nothing",
     check_a_surviving_monitor_is_never_moved),
    ("session.connect is written on auth, with the link measured",
     check_session_connect_is_written_on_auth),
    ("web.py really calls log_connect on auth", check_web_calls_log_connect_on_auth),
    ("session.leave carries its caller's reason, exactly once",
     check_leave_carries_its_reason),
    ("notify.deliver writes ONE notice record naming the carrier",
     check_notify_deliver_records_the_carrier_once),
]


def main() -> int:
    print("=== LOG WIRING GATE ===")
    failed = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as e:  # a crashing check is a failing check
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"LOG WIRING GATE FAILED — {failed} check(s).")
        return 1
    print("LOG WIRING GATE PASSED — the use log is opened, closed once, "
          "shipped, and the displays reach everything that needs them.")
    return 0


def test_log_wiring():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
