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


def list_windows(exclude: set[int] | None = None) -> list[dict]:
    """Top-level app windows a layout can hold: visible, titled, not shell
    chrome, not tool windows, not this server's own process."""
    own_pid = os.getpid()
    out: list[dict] = []
    exclude = exclude or set()

    @_EnumWindowsProc
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd) or hwnd in exclude:
            return True
        if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        title = _title(hwnd)
        if not title or _is_cloaked(hwnd) or _class_name(hwnd) in _SHELL_CLASSES:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == own_pid:
            return True
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


class Layout:
    """One phone screen: member windows + the orientation/aspect it was built
    for. Members are ordered — grid cell order for grids, [window] for solo."""

    def __init__(self, name: str, process: str, members: list[int],
                 template: str | None, orient: str, aspect: float,
                 icon: str | None = None, source: int = 0, folder: str = ""):
        self.name = name
        self.process = process
        # WHERE this layout's project is READ FROM — never the answer itself.
        # `source` is the window an extracted tab was torn out of (0 = none);
        # `folder` is the project its title named at creation, the last resort
        # for when that window is gone. This used to be the window's TITLE,
        # frozen — see `project()` and __about/window_manager.md.
        self.source = source
        self.folder = folder
        self.members = members
        # WHICH member holds the keyboard (owner 2026-08-06). The phone types
        # into one window of a grid, and every re-focus used to hand the
        # keyboard to whichever member sat LAST in this list — so a dictation
        # interrupted by one excursion continued in the other agent's session.
        # Kept in the registry, not in the connection: an excursion closes the
        # socket, and the target must outlive it. See focus_guard.
        self.last_member: int = members[0] if members else 0
        self.template = template  # None = solo
        self.orient = orient      # "portrait" | "landscape" (owner 2026-08-07:
                                  # never "wide" again — one name per thing)
        self.aspect = aspect      # w/h the layout was last arranged for
        self.icon = icon          # target app's icon (PNG data URI) for the bar
        # Owner-chosen W:H for THIS layout (None = the phone's own shape) and
        # the region's position along the free axis (0–1, 0.5 = centered —
        # owner 2026-08-05, the Move handle). `arranged_*` is what the windows
        # currently stand in — a change is what makes the next focus re-place
        # them (owner 2026-08-03).
        self.ratio: tuple[int, int] | None = None
        self.pos: float = 0.5
        self.arranged_ratio: tuple[int, int] | None = None
        self.arranged_pos: float = 0.5

    def project(self) -> str:
        """The project folder this layout's window belongs to, MEASURED every
        call — an extracted tab's own window can be titled bare `Visual Studio
        Code`, so the window it was torn OUT of is asked next, live. `folder`
        is the last resort (that source closed): a FOLDER is not an answer —
        what is LIVE in it comes from the process table, every frame."""
        seen = [h for h in (self.members[0] if self.members else 0, self.source)
                if h and is_alive(h)]
        return agents.first_folder(_title(h) for h in seen) or self.folder


class LayoutRegistry:
    """Session-scoped layout list (server lifetime — survives phone drops).
    All methods are blocking; the web layer wraps them in to_thread."""

    def __init__(self):
        self.layouts: list[Layout] = []
        # The layout the phone was last working in (owner 2026-08-05): the app
        # leaving work mode minimizes everything, and the next session comes
        # back HERE instead of on the desktop. Server-side on purpose — the
        # client's own memory dies with the page when the app is closed.
        # (index, name) — the name guards against the list having shifted.
        self.last_focus: tuple[int, str] | None = None

    def prune(self) -> list[int]:
        """Closing a member at the desk removes it from its layout (owner
        rule); a layout with no live members disappears. Returns the surviving
        layouts' ORIGINAL indices, so a caller holding one (the focused
        layout) can follow it instead of pointing at whatever slid into its
        place.

        CLOSED, not merely HIDDEN (audit 2026-08-05). This used to prune on
        `is_alive`, which is also false for a CLOAKED window — and Windows
        cloaks every window sitting on another VIRTUAL DESKTOP, and Store apps
        while minimized. So the owner pressing Win+Ctrl+Right at his desk
        silently DELETED his layout, and its members — still on screen, still
        always-on-top — were forgotten by the only list that could have
        lowered them. Only a window that no longer exists is pruned now, and
        even that one is handed back clean on the way out."""
        for lay in self.layouts:
            alive = []
            for hwnd in lay.members:
                if user32.IsWindow(hwnd):
                    alive.append(hwnd)
                else:
                    drop_topmost(hwnd)
            lay.members = alive
            if alive and lay.last_member not in alive:
                lay.last_member = alive[0]  # the typing target closed at the desk
        kept = [i for i, lay in enumerate(self.layouts) if lay.members]
        self.layouts = [self.layouts[i] for i in kept]
        return kept

    def create(self, target: int, mode: str, template: str | None,
               fill: list[int], orient: str, device_ratio: float,
               mon_rect: tuple[int, int, int, int], name: str | None = None,
               source: int = 0) -> tuple[int, bool] | None:
        """Arrange the windows and register the layout. Returns (index, all
        members verified on their rects), or None when the target window died
        between pick and create. device_ratio = the phone's short/long side
        ratio; the layout's chosen orientation turns it into the actual w/h
        aspect."""
        if not is_alive(target):
            return None
        aspect = device_ratio if orient == "portrait" else 1.0 / device_ratio
        members = [target] + [h for h in fill if is_alive(h) and h != target]
        placed = True
        template = normalize_grid(template) if mode == "grid" else None
        if template:
            cells = _cells(layout_region(_work_area(mon_rect), aspect), template, orient)
            members = members[:len(cells)]
            for hwnd, cell in zip(members, cells):
                placed = place_window(hwnd, cell) and placed
        else:
            template = None
            members = members[:1]
            placed = place_window(target, layout_region(_work_area(mon_rect), aspect))
        # `source` = the window a tab was torn out of (0 = whole window); the
        # project is LOGGED, so HIS log says what the wheel will offer.
        title = _title(target) or ""
        name = name or title or "Window"
        folder = agents.first_folder([title, _title(source) if source else ""])
        logger.info("Layout %r from %#x (tab source %#x): title %r, project %r",
                    name, target, source, title, folder)
        self.layouts.append(Layout(name, _process_name(target), members,
                                   template, orient, aspect,
                                   icon_data_uri(_process_path(target)),
                                   source, folder))
        return len(self.layouts) - 1, placed

    def focus(self, index: int, device_ratio: float,
              mon_rect: tuple[int, int, int, int]) -> tuple[dict, bool] | None:
        """Raise the layout's windows and return (FRESH monitor-normalized
        region to frame, every member verified on its rect). Re-arranges when
        the connecting device's aspect drifted from what the layout was built
        for (tablet vs phone — owner 2026-08-02). Returns None when the layout
        is gone (pruned). Members of every OTHER layout drop out of the
        topmost band — only what the phone shows is above the world.

        The drop pass runs FIRST, before any early return (audit 2026-08-05):
        it used to sit after them, so focusing a layout whose window had been
        closed at the desk returned None with the PREVIOUS layout still nailed
        above everything, and the phone then showed the desktop over it."""
        self.prune()
        for other in self.layouts:
            for hwnd in other.members:
                if not (0 <= index < len(self.layouts)) or other is not self.layouts[index]:
                    drop_topmost(hwnd)
        if not 0 <= index < len(self.layouts):
            return None
        lay = self.layouts[index]
        placed = True
        aspect = device_ratio if lay.orient == "portrait" else 1.0 / device_ratio
        # WHERE THE MEMBERS BELONG — computed fresh on every focus. It is pure
        # arithmetic (grids.py), so asking is cheaper than remembering wrong.
        region = layout_region(_work_area(mon_rect), aspect, lay.ratio, lay.pos)
        targets = (_cells(region, lay.template, lay.orient)[:len(lay.members)]
                   if lay.template else [region])
        members = lay.members[:len(targets)]
        # AND THE ARRANGEMENT IS VERIFIED, NEVER MERELY REMEMBERED (owner
        # 2026-08-07, the Move handle's second round: "uvek ostavi centrirano").
        # `arranged_*` alone used to be the guard, written from an INTENTION
        # before place_window was even called — so once a member left its rect,
        # every later Apply of the same position matched the remembered value
        # and re-placed NOTHING. A claim about windows is MEASURED (the law
        # layout_state already lives by, owner 2026-08-04).
        if (abs(aspect - lay.aspect) > 0.05 or lay.arranged_ratio != lay.ratio
                or lay.arranged_pos != lay.pos or not _standing(members, targets)):
            lay.aspect = aspect
            for hwnd, cell in zip(members, targets):
                placed = place_window(hwnd, cell) and placed
            # Only an arrangement that LANDED is written down; a refusal leaves
            # the note unwritten so the next focus tries again.
            lay.arranged_ratio = lay.ratio if placed else None
            lay.arranged_pos = lay.pos if placed else -1.0
            if not placed:
                logger.warning("Layout %r did not take its arrangement "
                               "(ratio=%s pos=%.3f) — it will be retried",
                               lay.name, lay.ratio, lay.pos)
        # The member that holds the KEYBOARD is raised last, so it is the one
        # left in the foreground (owner 2026-08-06). Raising in plain list
        # order handed the keyboard to whatever sat last in the grid, and an
        # excursion — a picker, a permission dialog — re-focuses the layout on
        # every reconnect: his dictation resumed in the other window.
        order = [h for h in lay.members if h != lay.last_member]
        if lay.last_member in lay.members:
            order.append(lay.last_member)
        for hwnd in order:
            raise_window(hwnd)
        self.last_focus = (index, lay.name)  # where the next session resumes
        if lay.template:
            # The union of the cells the members actually occupy — the same
            # `targets` that were just placed, never a second computation of
            # them (one source, so the frame can never disagree with the desk).
            x2 = max(c[0] + c[2] for c in targets)
            y2 = max(c[1] + c[3] for c in targets)
            region = (targets[0][0], targets[0][1],
                      x2 - targets[0][0], y2 - targets[0][1])
        else:
            region = _frame_rect(lay.members[0])
            if region is None:
                return None
        return _normalize(region, mon_rect), placed

    def minimize_members(self) -> None:
        """Desktop position (owner 2026-08-02): every window that belongs to
        ANY layout gets minimized — the full-desktop view shows the desktop
        and only the windows that are NOT layout material. Focusing a layout
        later restores its own members (place/raise SW_RESTORE)."""
        self.prune()
        members = [h for lay in self.layouts for h in lay.members]
        for hwnd in members:
            freeze_transitions(hwnd)  # no slide-down to watch
            # Out of the topmost band FIRST — a member the owner later restores
            # from the taskbar at the desk must come back as a normal window.
            # (drop_topmost gives its DWM animation back at the same time; the
            # freeze above only has to outlive this one minimize.)
            drop_topmost(hwnd)
            user32.ShowWindow(hwnd, SW_MINIMIZE)
        # Only report Desktop once they are ALL really gone (owner 2026-08-03).
        wait_minimized(members)

    def forget_focus(self) -> None:
        """The user DELIBERATELY chose the full desktop — that is the state the
        next session must resume into, so there is nothing to come back to."""
        self.last_focus = None

    def resume_index(self) -> int | None:
        """The layout a returning phone should land in (owner 2026-08-05), or
        None for the desktop. Both the index AND the name must still match —
        a list that changed while the phone was away resumes on the desktop
        rather than on the wrong window."""
        self.prune()
        if self.last_focus is None:
            return None
        index, name = self.last_focus
        if 0 <= index < len(self.layouts) and self.layouts[index].name == name:
            return index
        self.last_focus = None
        return None

    def rename(self, index: int, name: str) -> bool:
        """Owner-typed name (owner 2026-08-05). The auto name — the target
        window's title — is only the default; this replaces it for good."""
        name = name.strip()[:80]
        if not name or not 0 <= index < len(self.layouts):
            return False
        self.layouts[index].name = name
        if self.last_focus and self.last_focus[0] == index:
            self.last_focus = (index, name)  # keep the resume pointer valid
        return True

    def set_ratio(self, index: int, w: int, h: int, pos: float = 0.5) -> bool:
        """Store this layout's owner-chosen W:H (0/0 = back to the phone's own
        shape) and the region's free-axis position (owner 2026-08-05 — the
        Move handle; 0.5 = centered). Only stored — the next focus re-places
        the windows, which is what the caller does right after."""
        if not 0 <= index < len(self.layouts):
            return False
        self.layouts[index].ratio = (w, h) if w > 0 and h > 0 else None
        self.layouts[index].pos = max(0.0, min(1.0, pos))
        return True

    def set_grid(self, index: int, grid: str, orient: str | None = None) -> bool:
        """This layout's grid ARRANGEMENT and/or orientation (owner 2026-08-07).

        His rule, exactly: a two- or four-window grid may change nothing but
        portrait/landscape, because there is only one sane way to cut a region
        into two or four. A THREE has four arrangements — the single window
        takes the top, bottom, left or right edge — and that choice belongs in
        the same panel as the name and the aspect. Only stored; the focus that
        follows re-places the windows."""
        if not 0 <= index < len(self.layouts):
            return False
        lay = self.layouts[index]
        wanted = normalize_grid(grid)
        # A grid may only be re-arranged INTO A SHAPE OF THE SAME SIZE. Asking
        # a three-window layout to become a "4" would leave a cell with no
        # window in it, and asking a four to become a "2" would orphan two.
        if wanted and lay.template and GRID_CELLS[wanted] == len(lay.members):
            lay.template = wanted
        if orient in ("portrait", "landscape"):
            lay.orient = orient
        lay.arranged_pos = -1.0   # force the next focus to re-place, always
        return True

    def merge(self, source: int, target: int, grid: str | None = None) -> bool:
        """Drag one layout's window onto another and they become a GRID (owner
        2026-08-07, "like holding a file in Explorer and dragging it into a
        folder"). The source layout DISAPPEARS — his answer to the first
        question, and the only one consistent with the standing rule that a
        window belongs to exactly one layout.

        Sizes: 1+1 -> 2, 1+2 -> 3 (he picks which of the four arrangements),
        1+3 -> 4 (no choice exists, so none is offered). A full four refuses,
        which is why the phone greys it while a drag is in flight."""
        if not (0 <= source < len(self.layouts) and 0 <= target < len(self.layouts)):
            return False
        if source == target:
            return False
        src, dst = self.layouts[source], self.layouts[target]
        members = dst.members + [h for h in src.members if h not in dst.members]
        if len(members) > 4 or len(members) < 2:
            return False
        wanted = normalize_grid(grid)
        if not wanted or GRID_CELLS[wanted] != len(members):
            # The phone did not name a shape, or named one of the wrong size:
            # take the only sane default for this count. Three defaults to a
            # bar along the top, which is the first drawing on his sheet.
            wanted = {2: "2", 3: "3-top", 4: "4"}[len(members)]
        dst.members = members
        dst.template = wanted
        dst.arranged_pos = -1.0     # the shape changed — re-place on focus
        self.layouts.pop(source)
        if self.last_focus and self.last_focus[0] == source:
            self.last_focus = None
        return True

    def reorder(self, source: int, before: int) -> bool:
        """Move a layout to another position in the list (owner 2026-08-07:
        dropping BETWEEN two rows reorders, dropping ON a row makes a grid —
        "kao kada u eksploreru držiš fajl"). Nothing on the PC moves."""
        if not 0 <= source < len(self.layouts):
            return False
        before = max(0, min(len(self.layouts), before))
        lay = self.layouts.pop(source)
        if before > source:
            before -= 1
        self.layouts.insert(before, lay)
        self.last_focus = None      # the indices it pointed at just moved
        return True

    def member_hwnds(self) -> set[int]:
        """Every window that already belongs to SOME layout — the creation
        list hides them (owner 2026-08-03: one window cannot be shown twice)."""
        self.prune()
        return {h for lay in self.layouts for h in lay.members}

    def remove(self, index: int, close: bool = False) -> list[int]:
        """Deleting a layout leaves the desktop exactly as it is (owner rule —
        no auto-return of windows). Its windows get their normal Windows
        minimize/restore animation back — we only froze it while they were
        layout material — and leave the topmost band.

        `close=True` is the owner's SECOND act (2026-08-08, task 116): the
        same removal, plus every member window is asked to close for real.
        "Brisanje layouta ga samo obrise iz nase liste ali ostavlja prozor na
        desktopu. Nekad hocemo to, a nekad hocemo bas da zatvorimo sve tu."

        The flag DEFAULTS to the harmless act on purpose. Two different things
        wore one button until today, and of the two only one cannot be undone;
        a page from before this round — or a message that lost the field on
        the way — must land on the one that leaves his windows alone.

        Returns the members that are still standing, which is empty for a
        plain removal and, after a close, the ones asking about unsaved work.
        The caller tells the phone; see `close_windows`."""
        alive: list[int] = []
        if 0 <= index < len(self.layouts):
            members = list(self.layouts[index].members)
            if close:
                # close_windows drops topmost and unfreezes each window itself
                # — it must do that BEFORE posting, so it owns both halves.
                alive = close_windows(members)
            else:
                for hwnd in members:
                    freeze_transitions(hwnd, False)
                    drop_topmost(hwnd)
            del self.layouts[index]
            # The resume pointer rides on INDICES — the removed one is gone,
            # every higher one shifted down by one.
            if self.last_focus is not None:
                last, name = self.last_focus
                self.last_focus = (None if last == index
                                   else (last - 1, name) if last > index
                                   else (last, name))
        return alive

    def clear_topmost(self) -> None:
        """Every window back to the normal z-band — the phone hung up, nothing
        is being shown, no window may stay always-on-top at the desk.

        Goes through the LEDGER, not through the member lists: a window that
        fell out of its layout (closed, cloaked, extracted as a tab) is
        exactly the one no member list can still name, and exactly the one
        that used to stay stranded up there."""
        release_all()

    def state(self, active: int | None, region: dict | None) -> dict:
        """The layout_state payload. Prune first so the phone never lists a
        dead layout — and FOLLOW the focused layout through that prune.

        The focus used to be a bare index, so closing a window at the desk
        slid the list down under it and the phone was suddenly focused on —
        and one ✕ away from removing — a layout it had never chosen (audit
        2026-08-05). `prune` returns the surviving original indices, which is
        exactly the map the focus needs."""
        kept = self.prune()
        # One process-table snapshot for every layout in the frame, not one
        # per layout (owner 2026-08-07 — see agents.agents_in).
        live = agents.live_agents()
        if active is not None:
            active = kept.index(active) if active in kept else None
            if active is None:
                region = None
        if active is not None and not 0 <= active < len(self.layouts):
            active, region = None, None
        return {
            "type": "layout_state",
            "layouts": [{"name": lay.name, "process": lay.process,
                         # Both READ, never remembered: prune just ran, so the
                         # member is alive and can be asked. `agents` is the
                         # ONLY answer to "does the Claude wheel belong here"
                         # (server/agents.py; `project()` is what lets an
                         # EXTRACTED tab be asked at all).
                         "title": _title(lay.members[0]),
                         "agents": agents.agents_in(lay.project(), live),
                         # WHICH grid, so the phone can draw its shape and
                         # offer the arrangement choice for a three
                         # (owner 2026-08-07). None = a solo layout.
                         "grid": lay.template,
                         "members": len(lay.members),
                         "orient": lay.orient, "icon": lay.icon,
                         "ratio": list(lay.ratio) if lay.ratio else None,
                         "pos": round(lay.pos, 3)}
                        for lay in self.layouts],
            "active": active,
            "region": region,
            "orient": self.layouts[active].orient if active is not None else None,
        }
