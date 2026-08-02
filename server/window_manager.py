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

Whole windows only in step 1 — tab extraction (context menu / Explorer path /
SendInput drag, probe-verified 2026-08-02) is step 2.
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import os

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
kernel32 = ctypes.windll.kernel32

GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
DWMWA_CLOAKED = 14
DWMWA_EXTENDED_FRAME_BOUNDS = 9
SW_RESTORE = 9
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

GRID_TEMPLATES = {
    "2x1": (2, 1),  # two columns
    "1x2": (1, 2),  # two rows
    "2x2": (2, 2),
}

# Window classes that are shell chrome, never layout material.
_SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}

_EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _process_name(hwnd: int) -> str:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    buf = ctypes.create_unicode_buffer(1024)
    size = wintypes.DWORD(1024)
    ok = kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
    kernel32.CloseHandle(handle)
    return os.path.basename(buf.value) if ok else ""


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
        out.append({"hwnd": hwnd, "title": title, "process": _process_name(hwnd)})
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
    return {"hwnd": root, "title": title, "process": _process_name(root)}


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


def _region_rect(mon_rect, aspect: float) -> tuple[int, int, int, int]:
    """Largest rect of the given aspect (w/h) centered in the work area — the
    area the phone will frame; solo windows fill it, grids subdivide it."""
    wl, wt, ww, wh = _work_area(mon_rect)
    w = min(ww, int(wh * aspect))
    h = int(w / aspect)
    if h > wh:
        h = wh
        w = int(h * aspect)
    return (wl + (ww - w) // 2, wt + (wh - h) // 2, w, h)


def place_window(hwnd: int, rect: tuple[int, int, int, int]) -> None:
    """Restore + move/size so the VISIBLE frame lands on rect. Apps with a
    minimum size simply end up larger — the phone letterboxes (owner-accepted)."""
    x, y, w, h = rect
    user32.ShowWindow(hwnd, SW_RESTORE)
    bl, bt, br, bb = _border_offsets(hwnd)
    user32.SetWindowPos(hwnd, 0, x - bl, y - bt, w + bl + br, h + bt + bb,
                        SWP_NOZORDER | SWP_NOACTIVATE)


def raise_window(hwnd: int) -> None:
    """Bring to front + give focus. Windows refuses SetForegroundWindow to
    background processes under some timing — the standard Alt-nudge unlocks
    it; we run elevated, so this combination is reliable in practice."""
    user32.ShowWindow(hwnd, SW_RESTORE)
    if not user32.SetForegroundWindow(hwnd):
        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        user32.SetForegroundWindow(hwnd)


def _cells(region, template: str) -> list[tuple[int, int, int, int]]:
    cols, rows = GRID_TEMPLATES[template]
    x, y, w, h = region
    cw, ch = w // cols, h // rows
    return [(x + c * cw, y + r * ch, cw, ch)
            for r in range(rows) for c in range(cols)]


def _normalize(rect, mon_rect) -> dict:
    ml, mt, mw, mh = mon_rect
    x, y, w, h = rect
    return {
        "x": max(0.0, min(1.0, (x - ml) / mw)),
        "y": max(0.0, min(1.0, (y - mt) / mh)),
        "w": max(0.0, min(1.0, w / mw)),
        "h": max(0.0, min(1.0, h / mh)),
    }


class Layout:
    """One phone screen: member windows + the orientation/aspect it was built
    for. Members are ordered — grid cell order for grids, [window] for solo."""

    def __init__(self, name: str, process: str, members: list[int],
                 template: str | None, orient: str, aspect: float):
        self.name = name
        self.process = process
        self.members = members
        self.template = template  # None = solo
        self.orient = orient      # "portrait" | "wide"
        self.aspect = aspect      # w/h the layout was last arranged for


class LayoutRegistry:
    """Session-scoped layout list (server lifetime — survives phone drops).
    All methods are blocking; the web layer wraps them in to_thread."""

    def __init__(self):
        self.layouts: list[Layout] = []

    def prune(self) -> None:
        """Closing a member at the desk removes it from its layout (owner
        rule); a layout with no live members disappears."""
        for lay in self.layouts:
            lay.members = [h for h in lay.members if is_alive(h)]
        self.layouts = [lay for lay in self.layouts if lay.members]

    def create(self, target: int, mode: str, template: str | None,
               fill: list[int], orient: str, device_ratio: float,
               mon_rect: tuple[int, int, int, int]) -> int | None:
        """Arrange the windows and register the layout. Returns its index, or
        None when the target window died between pick and create.
        device_ratio = the phone's short/long side ratio; the layout's chosen
        orientation turns it into the actual w/h aspect."""
        if not is_alive(target):
            return None
        aspect = device_ratio if orient == "portrait" else 1.0 / device_ratio
        members = [target] + [h for h in fill if is_alive(h) and h != target]
        if mode == "grid" and template in GRID_TEMPLATES:
            cells = _cells(_region_rect(mon_rect, aspect), template)
            members = members[:len(cells)]
            for hwnd, cell in zip(members, cells):
                place_window(hwnd, cell)
        else:
            template = None
            members = members[:1]
            place_window(target, _region_rect(mon_rect, aspect))
        name = _title(target) or "Window"
        self.layouts.append(Layout(name, _process_name(target), members,
                                   template, orient, aspect))
        return len(self.layouts) - 1

    def focus(self, index: int, device_ratio: float,
              mon_rect: tuple[int, int, int, int]) -> dict | None:
        """Raise the layout's windows and return the FRESH monitor-normalized
        region to frame. Re-arranges when the connecting device's aspect
        drifted from what the layout was built for (tablet vs phone — owner
        2026-08-02). Returns None when the layout is gone (pruned)."""
        self.prune()
        if not 0 <= index < len(self.layouts):
            return None
        lay = self.layouts[index]
        aspect = device_ratio if lay.orient == "portrait" else 1.0 / device_ratio
        if abs(aspect - lay.aspect) > 0.05:
            lay.aspect = aspect  # different device — rebuild the arrangement
            if lay.template:
                for hwnd, cell in zip(lay.members,
                                      _cells(_region_rect(mon_rect, aspect), lay.template)):
                    place_window(hwnd, cell)
            else:
                place_window(lay.members[0], _region_rect(mon_rect, aspect))
        for hwnd in lay.members:
            raise_window(hwnd)
        if lay.template:
            cells = _cells(_region_rect(mon_rect, lay.aspect), lay.template)
            region = cells[0]
            x2 = max(c[0] + c[2] for c in cells[:len(lay.members)])
            y2 = max(c[1] + c[3] for c in cells[:len(lay.members)])
            region = (region[0], region[1], x2 - region[0], y2 - region[1])
        else:
            region = _frame_rect(lay.members[0])
            if region is None:
                return None
        return _normalize(region, mon_rect)

    def remove(self, index: int) -> None:
        """Deleting a layout leaves the desktop exactly as it is (owner rule —
        no auto-return of windows)."""
        if 0 <= index < len(self.layouts):
            del self.layouts[index]

    def state(self, active: int | None, region: dict | None) -> dict:
        """The layout_state payload. Prune first so the phone never lists a
        dead layout."""
        self.prune()
        if active is not None and not 0 <= active < len(self.layouts):
            active, region = None, None
        return {
            "type": "layout_state",
            "layouts": [{"name": lay.name, "process": lay.process,
                         "orient": lay.orient} for lay in self.layouts],
            "active": active,
            "region": region,
            "orient": self.layouts[active].orient if active is not None else None,
        }
