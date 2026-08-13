"""Window layouts: enumerate app windows, arrange them phone-shaped, focus.

Phase F+ step 1 (spec: ROADMAP → Layouts & Tab Control). The phone composes
LAYOUTS live from open windows: solo (one window sized to the phone's aspect)
or a grid template (2x1 / 1x2 / 2x2) whose combined region matches the phone.
The registry lives for the server's lifetime — the phone may disconnect and
return, the layout list survives (owner decision 2026-08-02).

Everything here is blocking ctypes/Win32 — the web layer calls it via
asyncio.to_thread. Members are LIVE window references (hwnds): a member the
user moved or resized at the desk is re-read (and re-placed if its aspect
drifted) at every focus; a closed member silently drops out of its layout.
"""

import ctypes
import ctypes.wintypes as wintypes
import json
import logging
import os
import time

import agents
from config import SETTINGS
from grids import (  # the layout GEOMETRY lives there (THE STRUCTURE LAW)
    GRID_CELLS, GRID_TEMPLATES, _cells, _normalize, at_rect, layout_region,
    normalize_grid,
)
# Imported BY NAME on purpose: the tests that fake a windowless PC patch
# `window_manager.icon_data_uri`, and a name bound here is exactly what the
# four call sites below read at call time (THE STRUCTURE LAW split 2026-08-08).
from window_icons import icon_data_uri

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
kernel32 = ctypes.windll.kernel32

GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
DWMWA_CLOAKED = 14
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_TRANSITIONS_FORCEDISABLED = 3
SW_RESTORE = 9
SW_MINIMIZE = 6
WM_CLOSE = 0x0010        # what the window's OWN ✕ sends — the app decides
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
# HWND_* are sentinel HANDLES, not flags — wrap them so ctypes passes a full
# pointer-width value on x64 (a bare -1 would be a 32-bit int argument).
HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)
HWND_TOP = wintypes.HWND(0)       # front of the NORMAL band — a momentary raise
WS_EX_TOPMOST = 0x00000008
VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


# Window classes that are shell chrome, never layout material.
_SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

_EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _process_path(hwnd: int) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    buf = ctypes.create_unicode_buffer(1024)
    size = wintypes.DWORD(1024)
    ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
    kernel32.CloseHandle(handle)
    return buf.value if ok else ""


def _process_name(hwnd: int) -> str:
    return os.path.basename(_process_path(hwnd))


def _title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def _class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _is_cloaked(hwnd: int) -> bool:
    """UWP ghosts and minimized store apps stay 'visible' but cloaked."""
    cloaked = wintypes.DWORD()
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED,
                                 ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return bool(cloaked.value)


def _frame_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """The VISIBLE bounds (DWM extended frame — excludes the invisible resize
    borders GetWindowRect includes). This is what the phone's crop must frame."""
    r = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS,
                                    ctypes.byref(r), ctypes.sizeof(r)) != 0:
        if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return None
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def _border_offsets(hwnd: int) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) invisible-border thickness: the difference
    between GetWindowRect and the DWM frame. SetWindowPos speaks GetWindowRect
    coordinates, our targets are visible-frame coordinates — placement must
    compensate or every window sits ~7 px off its cell."""
    wr = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(wr))
    fr = _frame_rect(hwnd)
    if fr is None:
        return (0, 0, 0, 0)
    fl, ft, fw, fh = fr
    return (fl - wr.left, ft - wr.top, wr.right - (fl + fw), wr.bottom - (ft + fh))


def is_alive(hwnd: int) -> bool:
    return bool(user32.IsWindow(hwnd)) and bool(user32.IsWindowVisible(hwnd)) \
        and not _is_cloaked(hwnd)


def is_listable(hwnd: int) -> bool:
    """Is this a window a layout could actually hold?

    THE ONE ANSWER TO THAT QUESTION (owner report 2026-08-13, his point 3): the
    phone offered him "a layout with it?" for things that are not windows he can
    do anything with — and when he tapped, the creation list did not even carry
    them, because that list is built from `list_windows` and the offer was not.
    A question the app cannot honour is worse than no question.

    The test used to live INSIDE `list_windows`'s callback, where nothing else
    could reach it, so every other pass that wanted "a real window" wrote its
    own weaker version — `layout_popup._top_level_hwnds` is `IsWindowVisible`
    and nothing more, which is how a tool window with a title ended up wearing
    a chip. It is a function now, and the offer paths ask it."""
    if not user32.IsWindowVisible(hwnd):
        return False
    if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
        return False
    if not _title(hwnd) or _is_cloaked(hwnd):
        return False
    if _class_name(hwnd) in _SHELL_CLASSES:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value != os.getpid()


def list_windows(exclude: set[int] | None = None) -> list[dict]:
    """Top-level app windows a layout can hold: visible, titled, not shell
    chrome, not tool windows, not this server's own process."""
    out: list[dict] = []
    exclude = exclude or set()

    @_EnumWindowsProc
    def callback(hwnd, _lparam):
        if hwnd in exclude or not is_listable(hwnd):
            return True
        title = _title(hwnd)
        path = _process_path(hwnd)
        out.append({"hwnd": hwnd, "title": title,
                    "process": os.path.basename(path),
                    "icon": icon_data_uri(path)})
        return True

    user32.EnumWindows(callback, 0)
    return out


def window_at(mon_rect: tuple[int, int, int, int], nx: float, ny: float) -> dict | None:
    """The top-level app window under a monitor-normalized point (the phone's
    pick tap). Returns the same dict shape as list_windows, or None."""
    left, top, width, height = mon_rect
    pt = wintypes.POINT(int(left + nx * width), int(top + ny * height))
    hwnd = user32.WindowFromPoint(pt)
    if not hwnd:
        return None
    root = user32.GetAncestor(hwnd, GA_ROOT)
    if not root or not is_alive(root):
        return None
    title = _title(root)
    if not title or _class_name(root) in _SHELL_CLASSES:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(root, ctypes.byref(pid))
    if pid.value == os.getpid():
        return None
    path = _process_path(root)
    return {"hwnd": root, "title": title,
            "process": os.path.basename(path), "icon": icon_data_uri(path)}


def window_at_hwnd(hwnd: int) -> dict | None:
    """Info dict (same shape as list_windows) for a known hwnd, or None when
    the window died meanwhile."""
    if not is_alive(hwnd):
        return None
    path = _process_path(hwnd)
    return {"hwnd": hwnd, "title": _title(hwnd),
            "process": os.path.basename(path), "icon": icon_data_uri(path)}


def _work_area(mon_rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Work area (taskbar excluded) of the monitor containing mon_rect."""
    left, top, width, height = mon_rect
    r = wintypes.RECT(left, top, left + width, top + height)
    hmon = user32.MonitorFromRect(ctypes.byref(r), 2)  # MONITOR_DEFAULTTONEAREST

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
        return mon_rect
    w = info.rcWork
    return (w.left, w.top, w.right - w.left, w.bottom - w.top)


# --- Making the move INVISIBLE (owner rule, hardened 2026-08-03) ------------
# The phone's cube overlay exists so the user NEVER sees windows moving: it
# covers the whole rearrangement and fades out onto the finished picture. Two
# Windows facts broke that and are handled here, at the source:
#   1. `ShowWindow(SW_RESTORE)` / `SW_MINIMIZE` return IMMEDIATELY while DWM
#      still plays the slide-up/slide-down transition — which the screen
#      capture faithfully records. `freeze_transitions` turns that animation
#      OFF per window (DWMWA_TRANSITIONS_FORCEDISABLED), so restore and
#      minimize are instantaneous, with nothing to watch.
#   2. Even without the transition, the app itself re-lays-out after the
#      resize. `wait_settled` blocks until the window is really out of the
#      taskbar and its visible frame has stopped changing, so the server only
#      reports "done" when the desk truly is done.
#   3. "Stopped moving" alone was still a lie twice (owner 2026-08-04): a
#      window PAUSED mid-restore reads as settled, and a timeout used to log a
#      warning and carry on as if placed. `wait_landed` therefore verifies the
#      POSITION — the frame rect must actually match the commanded rect (apps
#      with a larger minimum size are owner-accepted, so only smaller/off-spot
#      fails) — and every placement reports success honestly.

SETTLE_TIMEOUT_S = 1.5
SETTLE_POLL_S = 0.03
SETTLE_STABLE_READS = 4
PLACE_RETRIES = 1        # one extra SetWindowPos when the first shot missed
# How long a closing window is given to actually go. Longer than a placement:
# an app saving a file or tearing down a render process legitimately takes a
# moment, and the phone would rather wait than be told a lie. Anything still
# standing after this is REPORTED, not fought (`close_windows`).
CLOSE_TIMEOUT_S = 2.5


def freeze_transitions(hwnd: int, disabled: bool = True) -> None:
    """Disable (or restore) DWM's minimize/restore animation for one window."""
    val = wintypes.BOOL(1 if disabled else 0)
    dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TRANSITIONS_FORCEDISABLED,
                                 ctypes.byref(val), ctypes.sizeof(val))


def wait_settled(hwnd: int, timeout_s: float = SETTLE_TIMEOUT_S) -> bool:
    """Block until the window is out of the taskbar and its visible frame has
    stopped moving (or the timeout — never hang the session on one app).
    Returns whether it really settled — callers must not pretend on False."""
    deadline = time.monotonic() + timeout_s
    last = None
    stable = 0
    while time.monotonic() < deadline:
        if user32.IsIconic(hwnd) or not user32.IsWindow(hwnd):
            last, stable = None, 0
        else:
            rect = _frame_rect(hwnd)
            if rect is not None and rect == last:
                stable += 1
                if stable >= SETTLE_STABLE_READS:
                    return True
            else:
                last, stable = rect, 0
        time.sleep(SETTLE_POLL_S)
    logger.warning("Window %#x never settled within %.1fs", hwnd, timeout_s)
    return False


def _standing(hwnds, targets) -> bool:
    """Are the members REALLY on the rects their layout claims? `arranged_*`
    records an INTENTION, never a measurement, so a member that has since
    moved (app re-layout, a restore out of the taskbar, a snap, a placement
    that did not take) turns it into a lie — and a guard that trusts it stops
    placing the windows for good. See `LayoutRegistry.focus`."""
    for hwnd, target in zip(hwnds, targets):
        rect = None if user32.IsIconic(hwnd) else _frame_rect(hwnd)
        if rect is None or not at_rect(rect, target):
            return False
    return True


def wait_landed(hwnd: int, target: tuple[int, int, int, int],
                timeout_s: float = SETTLE_TIMEOUT_S) -> bool:
    """Block until the window's visible frame IS the commanded rect and has
    stayed there through consecutive reads. This — not "stopped moving" — is
    what layout_state's promise rests on (owner 2026-08-04)."""
    deadline = time.monotonic() + timeout_s
    last = None
    stable = 0
    while time.monotonic() < deadline:
        rect = None
        if user32.IsWindow(hwnd) and not user32.IsIconic(hwnd):
            rect = _frame_rect(hwnd)
        if rect is not None and rect == last and at_rect(rect, target):
            stable += 1
            if stable >= SETTLE_STABLE_READS:
                return True
        else:
            last, stable = rect, 0
        time.sleep(SETTLE_POLL_S)
    return False


def wait_minimized(hwnds: list[int], timeout_s: float = SETTLE_TIMEOUT_S) -> None:
    """Block until every listed window is really iconic — the Desktop view
    must not appear while members are still sliding down (owner 2026-08-03)."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if all(not user32.IsWindow(h) or user32.IsIconic(h) for h in hwnds):
            return
        time.sleep(SETTLE_POLL_S)
    logger.warning("Some layout members never minimized within %.1fs", timeout_s)


def close_windows(hwnds: list[int],
                  timeout_s: float = CLOSE_TIMEOUT_S) -> list[int]:
    """Ask each window to close, POLITELY, and report which ones are still
    standing (owner 2026-08-08, task 116 — the layout's ✕ now offers this as
    one of two acts).

    `WM_CLOSE` is the same thing the window's own ✕ does: the app decides. A
    document with unsaved work puts up its "save changes?" dialog and the
    window lives until the owner answers it — which is exactly right, and the
    reason nothing here ever reaches for TerminateProcess. We are the phone
    pressing a button on his behalf; we are not a task manager.

    Posted, never sent: `SendMessageW` blocks this thread until the target's
    message loop answers, and a target that puts up a MODAL dialog does not
    answer until the owner does — one hung app would hold the whole layout
    thread for as long as he takes to read it.

    The survivors are the point of the return value. The phone must be able to
    say "one window is asking about unsaved work" instead of claiming the
    close happened; a claim we did not verify is the habit this project keeps
    paying for."""
    for hwnd in hwnds:
        if is_alive(hwnd):
            # Out of the always-on-top band FIRST: a save dialog is a separate
            # window, and its parent must not be hovering over it.
            drop_topmost(hwnd)
            freeze_transitions(hwnd, False)
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        alive = [h for h in hwnds if is_alive(h)]
        if not alive:
            return []
        time.sleep(SETTLE_POLL_S)
    alive = [h for h in hwnds if is_alive(h)]
    if alive:
        logger.info("Close refused (or still asking) by %d window(s): %s",
                    len(alive), ", ".join(repr(_title(h)) for h in alive))
    return alive


def place_window(hwnd: int, rect: tuple[int, int, int, int]) -> bool:
    """Restore + move/size so the VISIBLE frame lands on rect, VERIFIED. Apps
    with a minimum size simply end up larger — the phone letterboxes
    (owner-accepted). Layout members go TOPMOST the moment they are touched
    (owner decree 2026-08-04: a layout is NEVER below any other window, not
    even mid-creation); `drop_topmost` is the other half of that lifecycle.
    Returns whether the window really stands on the commanded rect — a False
    must reach the phone as a toast, never be shrugged off."""
    x, y, w, h = rect
    freeze_transitions(hwnd)
    user32.ShowWindow(hwnd, SW_RESTORE)
    for _ in range(PLACE_RETRIES + 1):
        # Borders re-read per attempt — the first SetWindowPos can change them
        # (e.g. a maximized window dropping back to a sizable frame).
        bl, bt, br, bb = _border_offsets(hwnd)
        user32.SetWindowPos(hwnd, HWND_TOPMOST,
                            x - bl, y - bt, w + bl + br, h + bt + bb,
                            SWP_NOACTIVATE)
        mark_topmost(hwnd)  # the ledger owes this window a way back down
        if wait_landed(hwnd, rect):
            return True
    logger.warning("Window %#x refused rect %s (stands at %s)",
                   hwnd, rect, _frame_rect(hwnd))
    return False


def raise_window(hwnd: int, topmost: bool = True) -> None:
    """Bring to front + give focus. Windows refuses SetForegroundWindow to a
    background process under some timings (a freshly created layout stayed
    BEHIND — owner report 2026-08-02), so this stacks every known unlock:
    explicit z-top first (works regardless of focus rules), then plain
    SetForegroundWindow, then the AttachThreadInput trick, then the Alt
    nudge.

    `topmost` is the difference between the two jobs this function was doing
    under one name, and conflating them cost the owner a second stranded
    window (audit 2026-08-05):

    - True — "this is what the phone shows". TOPMOST, not HWND_TOP (owner
      decree 2026-08-04): HWND_TOP cannot pass an always-on-top window (Task
      Manager, a player), and a layout member must be above EVERYTHING.
    - False — "bring this forward for a moment": tab extraction raising the
      source window, `next_input` moving keyboard focus. Those windows are in
      no layout, so NOTHING would ever have lowered them again; they simply
      stayed nailed above the owner's desk for the rest of the Windows
      session. A momentary raise gets HWND_TOP and no ledger entry."""
    freeze_transitions(hwnd)  # no slide-up out of the taskbar to watch
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(hwnd, HWND_TOPMOST if topmost else HWND_TOP, 0, 0, 0, 0,
                        SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW)
    if topmost:
        mark_topmost(hwnd)  # the ledger owes this window a way back down
    else:
        freeze_transitions(hwnd, False)  # not ours to keep animation-free
    wait_settled(hwnd)
    if user32.SetForegroundWindow(hwnd):
        return
    fg = user32.GetForegroundWindow()
    if fg:
        fg_tid = user32.GetWindowThreadProcessId(fg, None)
        our_tid = kernel32.GetCurrentThreadId()
        user32.AttachThreadInput(our_tid, fg_tid, True)
        user32.BringWindowToTop(hwnd)
        ok = user32.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(our_tid, fg_tid, False)
        if ok:
            return
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
    user32.SetForegroundWindow(hwnd)


# --- The topmost ledger (owner decree 2026-08-05) ---------------------------
# The always-on-top band is ours only while we are running to take it back,
# and twice now the owner has come to his desk to find HIS Chrome and HIS
# VSCode nailed above everything with nothing left alive to fix them. So every
# hwnd we push up there is written down, and there are exactly two ways out —
# one for each way this process can end:
#
#   1. We get to run code (tray Quit, server stop, Apply & restart, Ctrl+C, an
#      unhandled crash, Windows logoff): `release_all()` walks the ledger and
#      hands every window back. It is wired into ALL of those paths and is
#      idempotent — being called three times on the way out is the design.
#   2. We do NOT (Task Manager kill, a power cut): nothing inside the process
#      can help, so the ledger is mirrored to disk on every change and
#      `repair_stranded()` reads it at the next start. By then a handle may
#      have been recycled onto a stranger's window, so an entry is acted on
#      ONLY while its window still runs the same executable it did when we
#      raised it; anything else is forgotten, untouched.

_topmost: dict[int, str] = {}   # hwnd -> exe path at the moment we raised it


def _ledger_save() -> None:
    """Mirror the ledger to disk. Best effort by design: a repair note we
    cannot write must never stop the layout the owner just asked for."""
    try:
        SETTINGS.topmost_ledger_path.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.topmost_ledger_path.write_text(
            json.dumps({"pid": os.getpid(),
                        "windows": [{"hwnd": hwnd, "exe": exe}
                                    for hwnd, exe in _topmost.items()]}),
            encoding="utf-8")
    except OSError as e:
        logger.warning("Topmost ledger not written: %s", e)


def mark_topmost(hwnd: int) -> None:
    """Write down that WE put this window into the always-on-top band."""
    if hwnd in _topmost:
        return
    _topmost[hwnd] = _process_path(hwnd)
    _ledger_save()


def drop_topmost(hwnd: int) -> bool:
    """Back to the normal z-band. Called whenever a window stops being what
    the phone shows (desktop focus, another layout, removal, disconnect, the
    app exiting) — a layout member must never stay always-on-top for the owner
    AT the desk.

    VERIFIED, and the ledger entry survives a failure on purpose: SetWindowPos
    can be refused (a window at a higher integrity level, a hung owning
    thread), and a window we failed to lower is exactly the one the next
    start's repair has to know about. Forgetting it because we asked once is
    how "solved" becomes "still topmost" (owner, twice)."""
    if not user32.IsWindow(hwnd):
        if _topmost.pop(hwnd, None) is not None:
            _ledger_save()   # the window is gone; nothing left to lower
        return True
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                        SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
    if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST:
        logger.warning("Window %#x REFUSED to leave the always-on-top band "
                       "(%r) — kept in the ledger for the next repair",
                       hwnd, _title(hwnd))
        return False
    if _topmost.pop(hwnd, None) is not None:
        _ledger_save()
    return True


def release_all() -> None:
    """Every window we ever raised, back to the normal band — THE exit call.
    Wired into the server teardown, the GUI's Quit, Qt's aboutToQuit, atexit
    and the CLI's signal handlers, because the owner's rule is that nothing
    of ours may outlive us up there. Idempotent and cheap when empty."""
    if not _topmost:
        return
    logger.info("Releasing %d window(s) from the always-on-top band", len(_topmost))
    for hwnd in list(_topmost):
        drop_topmost(hwnd)   # a refusal keeps its own entry — see drop_topmost
        # These windows stop being layout material here, so they also get
        # their own DWM minimize/restore animation back — we only ever froze
        # it to keep the phone from watching them slide around.
        freeze_transitions(hwnd, False)
    _ledger_save()


def repair_stranded() -> None:
    """Put right what a killed previous run left standing. Runs once at start,
    before anything of ours can raise a window. Identity is checked first: an
    hwnd is only touched while it still runs the executable it ran when we
    raised it, so a recycled handle can never cost a stranger's window its
    z-order."""
    path = SETTINGS.topmost_ledger_path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if data.get("pid") == os.getpid():
        return  # our own file, this very run
    repaired = 0
    for entry in data.get("windows") or []:
        try:
            hwnd, exe = int(entry.get("hwnd", 0)), entry.get("exe") or ""
        except (TypeError, ValueError):
            continue
        if not hwnd or not user32.IsWindow(hwnd) or _process_path(hwnd) != exe:
            continue  # gone, or the handle now belongs to someone else
        user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE)
        repaired += 1
    if repaired:
        logger.warning("Repaired %d window(s) a previous run left always-on-top",
                       repaired)
    try:
        path.unlink()
    except OSError:
        pass

# --- The layout registry moved out (THE STRUCTURE LAW, 2026-08-09) ----------
# `Layout` + `LayoutRegistry` live in layout_registry.py since the pos-anchor
# round pushed this module past 1,000 lines; the seam is the one grids.py was
# cut on — this module DRIVES windows, the registry holds session state and
# policy. Re-exported here so every caller (web, server_core, layout_api, the
# gates) keeps one import path, and imported at the BOTTOM on purpose: the
# registry reaches back into this module for every desk primitive (lazily,
# via the module object, so the tests' fakes still land), and by this line
# everything it needs exists. Never import layout_registry directly — first,
# it would find this module half-initialized and fail loudly.
from layout_registry import Layout, LayoutRegistry  # noqa: E402,F401
