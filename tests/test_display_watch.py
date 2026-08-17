"""DISPLAY WATCH GATE — proves `server/display_watch.py`'s public contract
without ever touching a real monitor or opening a real window.

`display_watch.py` calls three raw Win32 entry points to build a snapshot:
`user32.EnumDisplayMonitors`, `user32.GetMonitorInfoW`, `shcore.GetDpiForMonitor`.
None of them carry explicit `.argtypes` strong enough to stop us — this gate
REPLACES all three attributes on the already-imported `user32`/`shcore`
WinDLL objects with genuine ctypes callback functions (`ctypes.WINFUNCTYPE`
wrapping a plain Python implementation), the exact same mechanism
`display_watch.py` itself uses for `MonitorEnumProc`. That is what lets a
fake correctly receive `ctypes.byref(...)` arguments and write through them —
a bare Python function substituted for a ctypes entry point cannot do that,
because `byref()` objects are only meaningful across a real ctypes FFI call.

This is the same "replace the platform primitive before/after import" rule
`test_capture_recovery.py` follows for `dxcam` — just one layer lower, since
`display_watch.py` talks to raw `ctypes.WinDLL` objects instead of a Python
package that can be swapped whole in `sys.modules`.

`DisplayWatch._check()`/`.start()` call the FREE function `snapshot()` by its
module-global name, so most of the diff/subscriber checks below monkeypatch
`display_watch.snapshot` directly (a fake returning a canned tuple) rather
than faking Win32 at all — the cheapest, most direct seam for logic that has
nothing to do with monitor enumeration.

Run:  .venv\\Scripts\\python tests/test_display_watch.py
"""

import ctypes
import ctypes.wintypes as wintypes
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import display_watch as dw  # noqa: E402


# ═══════════════════════════ FAKE WIN32 PRIMITIVES ═══════════════════════════
# Real ctypes function-pointer types so `ctypes.byref(...)` marshalling inside
# display_watch.py keeps working against our Python implementations.

_ENUM_FUNC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HDC, ctypes.POINTER(wintypes.RECT),
                                 dw.MonitorEnumProc, wintypes.LPARAM)
_GET_MONITOR_INFO_FUNC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR,
                                            ctypes.POINTER(dw.MONITORINFO))
_GET_DPI_FUNC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HMONITOR, ctypes.c_int,
                                   ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.UINT))

# The fake desktop: ordered list of {left, top, width, height, primary, scale_pct}.
# Mutated per-check; `install_fake_desktop` rebuilds the three fakes from it.
_DESKTOP: list[dict] = []

_real_enum = dw.user32.EnumDisplayMonitors
_real_get_monitor_info = dw.user32.GetMonitorInfoW
_real_get_dpi = dw.shcore.GetDpiForMonitor


def install_fake_desktop(monitors: list[dict]) -> None:
    """Replace the three Win32 entry points `snapshot()` reads, so it sees
    exactly `monitors` (in order) and nothing a real desktop would add."""
    _DESKTOP[:] = monitors

    def fake_enum(_hdc, _lprect, proc, _lparam):
        for hmon in range(1, len(_DESKTOP) + 1):
            if not proc(hmon, 0, None, 0):
                break
        return 1

    def fake_get_monitor_info(hmon, info_ptr):
        if not (1 <= hmon <= len(_DESKTOP)):
            return 0
        m = _DESKTOP[hmon - 1]
        info = info_ptr[0]
        info.rcMonitor.left, info.rcMonitor.top = m["left"], m["top"]
        info.rcMonitor.right = m["left"] + m["width"]
        info.rcMonitor.bottom = m["top"] + m["height"]
        info.dwFlags = dw.MONITORINFOF_PRIMARY if m["primary"] else 0
        return 1

    def fake_get_dpi(hmon, _dpi_type, dpi_x_ptr, dpi_y_ptr):
        m = _DESKTOP[hmon - 1] if 1 <= hmon <= len(_DESKTOP) else {"scale_pct": 100}
        dpi = round(m["scale_pct"] / 100 * 96)
        dpi_x_ptr[0] = dpi
        dpi_y_ptr[0] = dpi
        return 0  # S_OK

    dw.user32.EnumDisplayMonitors = _ENUM_FUNC(fake_enum)
    dw.user32.GetMonitorInfoW = _GET_MONITOR_INFO_FUNC(fake_get_monitor_info)
    dw.shcore.GetDpiForMonitor = _GET_DPI_FUNC(fake_get_dpi)


def restore_real_win32() -> None:
    dw.user32.EnumDisplayMonitors = _real_enum
    dw.user32.GetMonitorInfoW = _real_get_monitor_info
    dw.shcore.GetDpiForMonitor = _real_get_dpi


def _mon(left=0, top=0, width=1920, height=1080, primary=True, scale_pct=100) -> dict:
    return {"left": left, "top": top, "width": width, "height": height,
            "primary": primary, "scale_pct": scale_pct}


# ═══════════════════════════ CHECKS 1-3: snapshot() itself, real Win32 faked ═══════════════════════════

def check_snapshot_separates_pixels_and_scale() -> bool:
    """A plain 1080p@100% monitor: fields land where the module promises."""
    install_fake_desktop([_mon()])
    try:
        snap = dw.snapshot()
    finally:
        restore_real_win32()
    if len(snap) != 1:
        return False
    d = snap[0]
    return (d.index == 0 and d.left == 0 and d.top == 0 and d.width == 1920
            and d.height == 1080 and d.primary is True and d.scale_pct == 100)


def check_4k_at_150pct_stays_physical() -> bool:
    """THE TRAP, asserted explicitly: a 4K monitor at 150% scaling is still
    3840x2160 — scaling must NEVER be folded into the reported resolution."""
    install_fake_desktop([_mon(width=3840, height=2160, scale_pct=150)])
    try:
        snap = dw.snapshot()
    finally:
        restore_real_win32()
    d = snap[0]
    return d.width == 3840 and d.height == 2160 and d.scale_pct == 150


def check_snapshot_reads_multiple_monitors_in_order() -> bool:
    install_fake_desktop([_mon(width=1920, height=1080, primary=True),
                          _mon(left=1920, width=2560, height=1440, primary=False, scale_pct=125)])
    try:
        snap = dw.snapshot()
    finally:
        restore_real_win32()
    return (len(snap) == 2 and snap[0].index == 0 and snap[1].index == 1
            and snap[0].primary and not snap[1].primary
            and snap[1].width == 2560 and snap[1].scale_pct == 125)


# ═══════════════════════════ CHECKS 4-11: DisplayWatch, snapshot() faked whole ═══════════════════════════

def _patch_snapshot(sequence: list[tuple]):
    """`display_watch.snapshot` is a module-global the DisplayWatch methods
    call by name — replacing it here reaches every caller with no Win32
    involved at all. `sequence` is popped left-to-right; the last value
    repeats once exhausted."""
    calls = {"n": 0}

    def fake():
        i = min(calls["n"], len(sequence) - 1)
        calls["n"] += 1
        return sequence[i]

    dw.snapshot = fake
    return calls


def _restore_snapshot():
    dw.snapshot = dw.__dict__.get("_orig_snapshot", dw.snapshot)


_ORIG_SNAPSHOT = dw.snapshot  # captured once, before any check ever patches it


def check_added_monitor_fires_once_with_right_diff() -> bool:
    base = (dw.DisplayInfo(0, 0, 0, 1920, 1080, True, 100),)
    added = base + (dw.DisplayInfo(1, 1920, 0, 1920, 1080, False, 100),)
    _patch_snapshot([base])
    watch = dw.DisplayWatch()
    diffs = []
    watch.subscribe(lambda d: diffs.append(d))
    try:
        watch.start()  # takes `base` as the initial state — must not fire
        dw.snapshot = lambda: added
        watch._check()  # simulate the OS event firing
    finally:
        watch.stop()
        dw.snapshot = _ORIG_SNAPSHOT
    return (len(diffs) == 1 and len(diffs[0].added) == 1 and diffs[0].added[0].index == 1
            and diffs[0].removed == () and diffs[0].changed == ())


def check_removed_monitor_fires_once_and_names_it() -> bool:
    base = (dw.DisplayInfo(0, 0, 0, 1920, 1080, True, 100),
            dw.DisplayInfo(1, 1920, 0, 1920, 1080, False, 100))
    removed = (dw.DisplayInfo(0, 0, 0, 1920, 1080, True, 100),)
    _patch_snapshot([base])
    watch = dw.DisplayWatch()
    diffs = []
    watch.subscribe(lambda d: diffs.append(d))
    try:
        watch.start()
        dw.snapshot = lambda: removed
        watch._check()
    finally:
        watch.stop()
        dw.snapshot = _ORIG_SNAPSHOT
    return (len(diffs) == 1 and len(diffs[0].removed) == 1 and diffs[0].removed[0].index == 1
            and diffs[0].added == () and diffs[0].changed == ())


def check_resolution_change_fires() -> bool:
    base = (dw.DisplayInfo(0, 0, 0, 1920, 1080, True, 100),)
    resized = (dw.DisplayInfo(0, 0, 0, 2560, 1440, True, 100),)
    _patch_snapshot([base])
    watch = dw.DisplayWatch()
    diffs = []
    watch.subscribe(lambda d: diffs.append(d))
    try:
        watch.start()
        dw.snapshot = lambda: resized
        watch._check()
    finally:
        watch.stop()
        dw.snapshot = _ORIG_SNAPSHOT
    if len(diffs) != 1 or len(diffs[0].changed) != 1:
        return False
    old, new = diffs[0].changed[0]
    return old.width == 1920 and new.width == 2560


def check_scaling_only_change_fires_and_leaves_resolution() -> bool:
    base = (dw.DisplayInfo(0, 0, 0, 3840, 2160, True, 100),)
    rescaled = (dw.DisplayInfo(0, 0, 0, 3840, 2160, True, 150),)
    _patch_snapshot([base])
    watch = dw.DisplayWatch()
    diffs = []
    watch.subscribe(lambda d: diffs.append(d))
    try:
        watch.start()
        dw.snapshot = lambda: rescaled
        watch._check()
    finally:
        watch.stop()
        dw.snapshot = _ORIG_SNAPSHOT
    if len(diffs) != 1 or len(diffs[0].changed) != 1:
        return False
    old, new = diffs[0].changed[0]
    return (old.scale_pct == 100 and new.scale_pct == 150
            and old.width == new.width == 3840 and old.height == new.height == 2160)


def check_identical_snapshot_fires_nothing() -> bool:
    base = (dw.DisplayInfo(0, 0, 0, 1920, 1080, True, 100),)
    same = (dw.DisplayInfo(0, 0, 0, 1920, 1080, True, 100),)  # equal by value, new tuple
    _patch_snapshot([base])
    watch = dw.DisplayWatch()
    diffs = []
    watch.subscribe(lambda d: diffs.append(d))
    try:
        watch.start()
        dw.snapshot = lambda: same
        watch._check()
        watch._check()  # twice — still nothing
    finally:
        watch.stop()
        dw.snapshot = _ORIG_SNAPSHOT
    return diffs == []


def check_raising_subscriber_does_not_stop_others_or_watch() -> bool:
    base = (dw.DisplayInfo(0, 0, 0, 1920, 1080, True, 100),)
    changed = (dw.DisplayInfo(0, 0, 0, 2560, 1440, True, 100),)
    _patch_snapshot([base])
    watch = dw.DisplayWatch()
    seen = []

    def bad(_diff):
        raise RuntimeError("a subscriber having a bad day")

    watch.subscribe(bad)
    watch.subscribe(lambda d: seen.append(d))
    try:
        watch.start()
        dw.snapshot = lambda: changed
        watch._check()  # must not raise OUT of this call
        # the watch itself must still be usable afterwards
        changed2 = (dw.DisplayInfo(0, 0, 0, 1280, 720, True, 100),)
        dw.snapshot = lambda: changed2
        watch._check()
    finally:
        watch.stop()
        dw.snapshot = _ORIG_SNAPSHOT
    return len(seen) == 2


def check_stop_twice_is_safe() -> bool:
    base = (dw.DisplayInfo(0, 0, 0, 1920, 1080, True, 100),)
    _patch_snapshot([base])
    watch = dw.DisplayWatch()
    try:
        watch.start()
        watch.stop()
        watch.stop()  # must not raise
    finally:
        dw.snapshot = _ORIG_SNAPSHOT
    return watch.source is None


def check_unsubscribe_stops_future_callbacks() -> bool:
    base = (dw.DisplayInfo(0, 0, 0, 1920, 1080, True, 100),)
    changed = (dw.DisplayInfo(0, 0, 0, 2560, 1440, True, 100),)
    _patch_snapshot([base])
    watch = dw.DisplayWatch()
    seen = []
    cb = lambda d: seen.append(d)  # noqa: E731
    watch.subscribe(cb)
    watch.unsubscribe(cb)
    try:
        watch.start()
        dw.snapshot = lambda: changed
        watch._check()
    finally:
        watch.stop()
        dw.snapshot = _ORIG_SNAPSHOT
    return seen == []


CHECKS = [
    ("snapshot() separates physical pixels from scaling", check_snapshot_separates_pixels_and_scale),
    ("THE TRAP: 4K at 150% still reports 3840x2160", check_4k_at_150pct_stays_physical),
    ("snapshot() reads several monitors in enumeration order", check_snapshot_reads_multiple_monitors_in_order),
    ("an added monitor fires once with the right diff", check_added_monitor_fires_once_with_right_diff),
    ("a removed monitor fires once and names it", check_removed_monitor_fires_once_and_names_it),
    ("a resolution change fires", check_resolution_change_fires),
    ("a scaling-only change fires and never alters resolution", check_scaling_only_change_fires_and_leaves_resolution),
    ("an identical snapshot fires nothing", check_identical_snapshot_fires_nothing),
    ("a raising subscriber never silences others or the watch", check_raising_subscriber_does_not_stop_others_or_watch),
    ("stop() twice is safe", check_stop_twice_is_safe),
    ("unsubscribe stops future callbacks", check_unsubscribe_stops_future_callbacks),
]


def main() -> int:
    print("=== DISPLAY WATCH GATE ===")
    failed = 0
    for name, fn in CHECKS:
        started = time.monotonic()
        try:
            ok = fn()
        except Exception as e:  # a crashing check is a failing check
            ok = False
            print(f"  ERROR {name}: {e!r}")
        finally:
            restore_real_win32()      # a check that raised mid-patch must not
            dw.snapshot = _ORIG_SNAPSHOT  # leak a fake into the next check
        print(f"  {'PASS' if ok else 'FAIL'}  {name}  ({time.monotonic() - started:.2f}s)")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"DISPLAY WATCH GATE FAILED — {failed} check(s).")
        return 1
    print("DISPLAY WATCH GATE PASSED — display changes are reported, never guessed at.")
    return 0


def test_display_watch():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
