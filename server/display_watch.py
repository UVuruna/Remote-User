"""The one source of "the displays changed" — reacting to the EVENT, never a timer (owner ruling: plugging in
a monitor takes real time, it is not a millisecond event; polling for it is the guessing CLAUDE.md constraint
15 forbids everywhere else in this codebase).

WHY THIS EXISTS (constraint 30, measured — a 3.8-hour dead picture on the owner's machine): `dxcam.DXFactory`
enumerates its outputs ONCE, at import time, for the process's life. Unplug or plug in a monitor and every
live dxcam object keeps describing a desktop that no longer exists, and nothing notices —
`settings_window.py`'s monitor list is filled once, when the window is BUILT, from that same stale singleton
via `output_count()`; reopening Settings does not help, only a restart does. This module lets the app react
WITHOUT one: it watches Windows' own display-change signals and tells whoever is listening — capture, the
GUI, the phone — that the desktop just moved.

THIS MODULE REPORTS, IT DOES NOT ACT. It never touches `dxcam` and never calls `capture_recovery` — those
decide what a change MEANS for a live camera (constraint 30's ladder). This only answers "what does Windows
say is true about the monitors right now", kept separate so a bug in one is never reachable through the other.

THE SCALING TRAP (read twice before touching `scale_pct`). This server declares `PER_MONITOR_AWARE_V2`
(constraint 2) so it sees PHYSICAL pixels — what dxcam captures and the injector lands clicks on. A 4K monitor
at 150% is still 3840x2160 to dxcam and to us; "2560x1440" is only the LOGICAL size Windows reports to a
DPI-UNAWARE process, and we are not one. `scale_pct` is recorded purely as INFORMATION and must NEVER be
folded into, or used to derive, a resolution anywhere — `width`/`height` are always the physical rect,
`scale_pct` a separate field precisely so nobody combines them.

TWO EVENT SOURCES, ONE OUTCOME. `gui_main.py` runs a `QGuiApplication`, and Qt already turns Windows' display
messages into signals — `screenAdded`, `screenRemoved`, `primaryScreenChanged`, per-screen `geometryChanged` /
`logicalDotsPerInchChanged` — so we just listen. The headless CLI (`main.py`) has no QApplication, so it uses
`focus_hook.py`'s trick for the foreground hook: a message-only window on its own thread, catching
`WM_DISPLAYCHANGE` (resolution/count) and `WM_DPICHANGED` (scaling). Both paths funnel into `_check()`, which
re-reads the truth (`snapshot()`) and diffs it against the last state — the event only ever says "look again",
because Windows' payloads here are partial and a fresh read is cheap and correct.

THE WNDPROC-THUNK LESSON (`focus_hook.py`'s trap, copied): a ctypes callback is a real code pointer Windows
calls as long as its window class stays registered, and `RegisterClassW` keeps that registration for the
PROCESS's life — recreating the callback on every `start()` crashes the SECOND run, calling into a thunk
Python already freed. So the WNDPROC and window class are created exactly ONCE, at module scope.

NEITHER SOURCE MAY EVER RAISE INTO A CALLER — this watches the desktop, it must not take the server down over
a bad enumeration. Every entry point swallows and logs.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
# shcore is 8.1+; PER_MONITOR_AWARE_V2 (constraint 2) already requires 8.1+.
shcore = ctypes.WinDLL("shcore", use_last_error=True)

MONITORINFOF_PRIMARY = 1
MDT_EFFECTIVE_DPI = 0  # GetDpiForMonitor's "what does this monitor really show" mode

MonitorEnumProc = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

shcore.GetDpiForMonitor.restype = ctypes.c_long  # HRESULT
shcore.GetDpiForMonitor.argtypes = [wintypes.HMONITOR, ctypes.c_int,
                                    ctypes.POINTER(wintypes.UINT), ctypes.POINTER(wintypes.UINT)]

class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

@dataclass(frozen=True)
class DisplayInfo:
    """One monitor, read fresh. `index` is enumeration order (matches
    `monitors.py`'s convention). left/top/width/height are PHYSICAL pixels,
    never scaled. scale_pct is a SEPARATE fact (100 = no scaling) — never
    combine it with width/height (see the module docstring)."""
    index: int
    left: int
    top: int
    width: int
    height: int
    primary: bool
    scale_pct: int

# An ordered snapshot of every monitor, index 0..N-1.
DisplaySnapshot = tuple[DisplayInfo, ...]

def _scale_percent(hmonitor) -> int:
    """GetDpiForMonitor ÷ 96, as a percent. Falls back to 100 on any failure."""
    dpi_x = wintypes.UINT(0)
    dpi_y = wintypes.UINT(0)
    try:
        hr = shcore.GetDpiForMonitor(hmonitor, MDT_EFFECTIVE_DPI,
                                      ctypes.byref(dpi_x), ctypes.byref(dpi_y))
    except OSError:
        return 100
    if hr != 0 or dpi_x.value == 0:
        return 100
    return round(dpi_x.value / 96 * 100)

def snapshot() -> DisplaySnapshot:
    """The CURRENT truth, read now — never a remembered one (constraint 13).
    Safe from any thread; `EnumDisplayMonitors` is synchronous and reentrant."""
    entries: list[DisplayInfo] = []

    @MonitorEnumProc
    def callback(hmonitor, _hdc, _lprect, _lparam):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            return True  # skip a monitor Windows won't describe; don't abort the rest
        r = info.rcMonitor
        entries.append(DisplayInfo(
            index=len(entries), left=r.left, top=r.top,
            width=r.right - r.left, height=r.bottom - r.top,
            primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
            scale_pct=_scale_percent(hmonitor)))
        return True

    try:
        user32.EnumDisplayMonitors(None, None, callback, 0)
    except OSError:
        logger.exception("display_watch: EnumDisplayMonitors failed")
    return tuple(entries)

@dataclass(frozen=True)
class DisplayDiff:
    """What a consumer needs: monitors that appeared, went, or changed in
    place (old, new pairs at the same index), plus the new whole snapshot —
    so capture can tell "is the one I'm using one of the ones that vanished"."""
    added: tuple[DisplayInfo, ...]
    removed: tuple[DisplayInfo, ...]
    changed: tuple[tuple[DisplayInfo, DisplayInfo], ...]
    snapshot: DisplaySnapshot

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

def _diff(old: DisplaySnapshot, new: DisplaySnapshot) -> DisplayDiff:
    old_by_index = {d.index: d for d in old}
    new_by_index = {d.index: d for d in new}
    added = tuple(new_by_index[i] for i in sorted(new_by_index.keys() - old_by_index.keys()))
    removed = tuple(old_by_index[i] for i in sorted(old_by_index.keys() - new_by_index.keys()))
    changed = tuple(
        (old_by_index[i], new_by_index[i])
        for i in sorted(old_by_index.keys() & new_by_index.keys())
        if old_by_index[i] != new_by_index[i]
    )
    return DisplayDiff(added=added, removed=removed, changed=changed, snapshot=new)

# WM_DISPLAYCHANGE / WM_DPICHANGED (headless): message-only window, the
# focus_hook.py shape — one WNDPROC thunk and one window class, both created
# ONCE at module scope and never rebuilt.
WM_DISPLAYCHANGE = 0x007E
WM_DPICHANGED = 0x02E0
WM_QUIT = 0x0012
HWND_MESSAGE = -3

_WNDPROC_TYPE = ctypes.WINFUNCTYPE(
    ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long,
    wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)

user32.DefWindowProcW.restype = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
user32.CreateWindowExW.restype = wintypes.HWND
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint]

# The lone active headless watcher — the module-level WNDPROC can't carry
# `self` (it's a bare C callback), so it routes through here instead.
_active_winapi_watch: "DisplayWatch | None" = None

def _wndproc(hwnd, msg, wparam, lparam):
    if msg in (WM_DISPLAYCHANGE, WM_DPICHANGED) and _active_winapi_watch is not None:
        try:
            _active_winapi_watch._check()  # noqa: SLF001 — module-internal callback
        except Exception:
            logger.exception("display_watch: a display-change reaction raised")
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

_WNDPROC = _WNDPROC_TYPE(_wndproc)  # created ONCE — see the module docstring
_CLASS_NAME = "VibeCoderDisplayWatchMsgWnd"
_class_registered = False

class _WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT), ("lpfnWndProc", _WNDPROC_TYPE),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
    ]

def _ensure_class_registered() -> None:
    global _class_registered
    if _class_registered:
        return
    wc = _WNDCLASSW()
    wc.lpfnWndProc = _WNDPROC
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.lpszClassName = _CLASS_NAME
    # A second RegisterClassW with the same name fails harmlessly (already
    # registered from an earlier watch in this process) — never fatal.
    user32.RegisterClassW(ctypes.byref(wc))
    _class_registered = True

class DisplayWatch:
    """Subscribers get a `DisplayDiff` whenever a fresh `snapshot()` differs from the previous one. `start()`
    picks Qt (if a `QGuiApplication` is already running) or else the headless WM_DISPLAYCHANGE window, and
    logs which. `stop()` is idempotent, safe from any thread. Neither may raise."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._callbacks: list = []
        self._last: DisplaySnapshot | None = None
        self._source: str | None = None
        self._qt_app = None                          # Qt bookkeeping
        self._qt_connected_screens: set = set()
        self._thread: threading.Thread | None = None  # headless bookkeeping
        self._tid = 0
        self._hwnd = 0
        self._ready = threading.Event()

    def subscribe(self, callback) -> None:
        """`callback(diff: DisplayDiff)`, called whenever the displays differ from the last known state."""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def unsubscribe(self, callback) -> None:
        with self._lock:
            self._callbacks[:] = [c for c in self._callbacks if c != callback]

    @property
    def source(self) -> str | None:
        """"qt" / "winapi" / None (not started or neither available)."""
        return self._source

    @property
    def last_snapshot(self) -> DisplaySnapshot | None:
        return self._last

    def start(self) -> None:
        """Idempotent. Picks a source and logs which; never raises."""
        with self._lock:
            if self._source is not None:
                return
            try:
                self._last = snapshot()
            except Exception:
                logger.exception("display_watch: initial snapshot failed")
                self._last = ()
            # Qt first (the GUI process already has one running), else headless.
            for name, starter, label in (("qt", self._try_start_qt, "Qt screen signals"),
                                         ("winapi", self._start_winapi, "a WM_DISPLAYCHANGE window")):
                try:
                    if starter():
                        self._source = name
                        logger.info("display_watch: watching via %s", label)
                        return
                except Exception:
                    logger.exception("display_watch: %s event source failed to attach", name)
            logger.warning("display_watch: no event source available — changes will not be noticed until the next snapshot() call")

    def stop(self) -> None:
        """THE exit call — idempotent, safe from any thread."""
        with self._lock:
            self._callbacks.clear()
            if self._source == "qt":
                self._stop_qt()
            elif self._source == "winapi":
                self._stop_winapi()
            self._source = None

    def _check(self) -> None:
        """An event fired: re-read the truth and, if it moved, tell everyone. Never raises."""
        try:
            new = snapshot()
        except Exception:
            logger.exception("display_watch: snapshot on change-event failed")
            return
        with self._lock:
            old = self._last if self._last is not None else new
            if new == old:
                return
            self._last = new
            callbacks = tuple(self._callbacks)
        diff = _diff(old, new)
        for cb in callbacks:
            try:
                cb(diff)
            except Exception:
                # One bad subscriber must never silence the others, or the watch.
                logger.exception("display_watch: a subscriber raised")

    def _try_start_qt(self) -> bool:
        try:
            from PySide6.QtGui import QGuiApplication
        except ImportError:
            return False
        app = QGuiApplication.instance()
        if app is None:
            return False
        app.screenAdded.connect(self._on_qt_screen_added)
        app.screenRemoved.connect(self._on_qt_event)
        app.primaryScreenChanged.connect(self._on_qt_event)
        for screen in app.screens():  # each already-open screen, too
            self._connect_qt_screen(screen)
        self._qt_app = app
        return True

    def _connect_qt_screen(self, screen) -> None:
        # Defensive: a screen added later must also get these per-screen
        # connections, which is why screenAdded routes through this too.
        key = id(screen)
        if key in self._qt_connected_screens:
            return
        screen.geometryChanged.connect(self._on_qt_event)
        screen.logicalDotsPerInchChanged.connect(self._on_qt_event)
        self._qt_connected_screens.add(key)

    def _on_qt_screen_added(self, screen) -> None:
        self._connect_qt_screen(screen)
        self._on_qt_event()

    def _on_qt_event(self, *_args) -> None:
        self._check()

    def _stop_qt(self) -> None:
        app = self._qt_app
        self._qt_app = None
        self._qt_connected_screens.clear()
        if app is None:
            return
        # Disconnect never-fatal: an already-gone/disconnected signal just raises.
        for sig, slot in ((app.screenAdded, self._on_qt_screen_added),
                          (app.screenRemoved, self._on_qt_event),
                          (app.primaryScreenChanged, self._on_qt_event)):
            try:
                sig.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        for screen in app.screens():
            for sig in (screen.geometryChanged, screen.logicalDotsPerInchChanged):
                try:
                    sig.disconnect(self._on_qt_event)
                except (RuntimeError, TypeError):
                    pass

    def _start_winapi(self) -> bool:
        global _active_winapi_watch
        if _active_winapi_watch is not None and _active_winapi_watch is not self:
            logger.warning("display_watch: another watch already owns the headless event source in this process")
            return False
        _active_winapi_watch = self
        self._ready.clear()
        self._thread = threading.Thread(target=self._run_winapi, name="display-watch", daemon=True)
        self._thread.start()
        self._ready.wait(1.0)
        return bool(self._hwnd)

    def _run_winapi(self) -> None:
        _ensure_class_registered()
        self._tid = kernel32.GetCurrentThreadId()
        hwnd = user32.CreateWindowExW(0, _CLASS_NAME, _CLASS_NAME, 0, 0, 0, 0, 0,
                                      wintypes.HWND(HWND_MESSAGE), None,
                                      kernel32.GetModuleHandleW(None), None)
        self._hwnd = hwnd or 0
        self._ready.set()
        if not hwnd:
            logger.error("display_watch: CreateWindowExW failed (error %s)", ctypes.get_last_error())
            return
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            user32.DestroyWindow(hwnd)
            self._hwnd = 0

    def _stop_winapi(self) -> None:
        global _active_winapi_watch
        if _active_winapi_watch is self:
            _active_winapi_watch = None
        thread = self._thread
        self._thread = None
        if thread is None or not thread.is_alive():
            self._tid = 0
            return
        if self._tid and not user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0):
            logger.warning("display_watch: WM_QUIT to the watch thread was refused (error %s)", ctypes.get_last_error())
        thread.join(0.25)
        if thread.is_alive():
            logger.error("display_watch: the watch thread did not stop within 0.25s — its window is still live")
        self._tid = 0

    # No module-level atexit: unlike focus_hook.py's one process-wide hook, a
    # DisplayWatch is owned by its caller (gui_main.py / main.py), which must
    # stop() it through the same exit paths that module funnels through.
