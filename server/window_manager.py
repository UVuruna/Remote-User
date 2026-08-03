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
import time

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


# --- App icons (the phone shows the real app icon next to tab/window names,
# owner request 2026-08-02) ---------------------------------------------------

_ICON_SIZE = 32
_icon_cache: dict[str, str | None] = {}


class _SHFILEINFO(ctypes.Structure):
    _fields_ = [("hIcon", wintypes.HICON), ("iIcon", ctypes.c_int),
                ("dwAttributes", wintypes.DWORD),
                ("szDisplayName", ctypes.c_wchar * 260),
                ("szTypeName", ctypes.c_wchar * 80)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long),
                ("biHeight", ctypes.c_long), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


def icon_data_uri(exe_path: str) -> str | None:
    """The exe's icon as a PNG data URI (cached per path; None on any
    failure — the phone falls back to text-only chips)."""
    if not exe_path:
        return None
    if exe_path in _icon_cache:
        return _icon_cache[exe_path]
    uri = None
    try:
        import base64
        import io

        from PIL import Image

        gdi32 = ctypes.windll.gdi32
        # 64-bit handles: without explicit types ctypes truncates HDC/HBITMAP
        # to c_int and DrawIconEx/SelectObject overflow (hit live 2026-08-02).
        gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
        gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
        gdi32.CreateDIBSection.restype = ctypes.c_void_p
        gdi32.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_uint, ctypes.c_void_p,
                                           ctypes.c_void_p, ctypes.c_uint]
        gdi32.SelectObject.restype = ctypes.c_void_p
        gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
        gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
        user32.GetDC.restype = ctypes.c_void_p
        user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        user32.DrawIconEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        info = _SHFILEINFO()
        SHGFI_ICON = 0x100
        if ctypes.windll.shell32.SHGetFileInfoW(exe_path, 0, ctypes.byref(info),
                                                ctypes.sizeof(info), SHGFI_ICON):
            hdc = user32.GetDC(0)
            memdc = gdi32.CreateCompatibleDC(hdc)
            bmi = _BITMAPINFOHEADER(ctypes.sizeof(_BITMAPINFOHEADER),
                                    _ICON_SIZE, -_ICON_SIZE, 1, 32, 0,
                                    0, 0, 0, 0, 0)
            bits = ctypes.c_void_p()
            hbmp = gdi32.CreateDIBSection(memdc, ctypes.byref(bmi), 0,
                                          ctypes.byref(bits), None, 0)
            old = gdi32.SelectObject(memdc, hbmp)
            user32.DrawIconEx(memdc, 0, 0, info.hIcon, _ICON_SIZE, _ICON_SIZE,
                              0, None, 3)  # DI_NORMAL
            raw = ctypes.string_at(bits, _ICON_SIZE * _ICON_SIZE * 4)
            gdi32.SelectObject(memdc, old)
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(memdc)
            user32.ReleaseDC(0, hdc)
            user32.DestroyIcon(info.hIcon)
            img = Image.frombuffer("RGBA", (_ICON_SIZE, _ICON_SIZE), raw,
                                   "raw", "BGRA", 0, 1)
            buf = io.BytesIO()
            img.save(buf, "PNG")
            uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:  # noqa: BLE001 — icons are decoration, never a failure
        logger.warning("Icon extraction failed for %s: %s", exe_path, e)
    _icon_cache[exe_path] = uri
    return uri


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


def _fit_rect(box, aspect: float) -> tuple[int, int, int, int]:
    """Largest rect of the given aspect (w/h) centered inside `box`."""
    bl, bt, bw, bh = box
    w = min(bw, int(bh * aspect))
    h = int(w / aspect)
    if h > bh:
        h = bh
        w = int(h * aspect)
    return (bl + (bw - w) // 2, bt + (bh - h) // 2, w, h)


def _region_rect(mon_rect, aspect: float) -> tuple[int, int, int, int]:
    """Largest rect of the given aspect (w/h) centered in the work area — the
    area the phone will frame; solo windows fill it, grids subdivide it."""
    return _fit_rect(_work_area(mon_rect), aspect)


def layout_region(mon_rect, aspect: float,
                  ratio: tuple[int, int] | None = None) -> tuple[int, int, int, int]:
    """The rect the phone frames. The DEVICE shape (`aspect`) gives the outer
    box; a per-layout ratio override may only make the region SMALLER inside
    it (owner decision 2026-08-03: portrait keeps the phone's width and the
    region may only get shorter, landscape keeps its height and the region may
    only get narrower — the unused strip stays black on the phone). Anything
    that would grow past the phone's own shape is clamped by the same fit."""
    box = _region_rect(mon_rect, aspect)
    if ratio and ratio[0] > 0 and ratio[1] > 0:
        return _fit_rect(box, ratio[0] / ratio[1])
    return box


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

SETTLE_TIMEOUT_S = 1.5
SETTLE_POLL_S = 0.03
SETTLE_STABLE_READS = 2


def freeze_transitions(hwnd: int, disabled: bool = True) -> None:
    """Disable (or restore) DWM's minimize/restore animation for one window."""
    val = wintypes.BOOL(1 if disabled else 0)
    dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_TRANSITIONS_FORCEDISABLED,
                                 ctypes.byref(val), ctypes.sizeof(val))


def wait_settled(hwnd: int, timeout_s: float = SETTLE_TIMEOUT_S) -> None:
    """Block until the window is out of the taskbar and its visible frame has
    stopped moving (or the timeout — never hang the session on one app)."""
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
                    return
            else:
                last, stable = rect, 0
        time.sleep(SETTLE_POLL_S)
    logger.warning("Window %#x never settled within %.1fs", hwnd, timeout_s)


def wait_minimized(hwnds: list[int], timeout_s: float = SETTLE_TIMEOUT_S) -> None:
    """Block until every listed window is really iconic — the Desktop view
    must not appear while members are still sliding down (owner 2026-08-03)."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if all(not user32.IsWindow(h) or user32.IsIconic(h) for h in hwnds):
            return
        time.sleep(SETTLE_POLL_S)
    logger.warning("Some layout members never minimized within %.1fs", timeout_s)


def place_window(hwnd: int, rect: tuple[int, int, int, int]) -> None:
    """Restore + move/size so the VISIBLE frame lands on rect. Apps with a
    minimum size simply end up larger — the phone letterboxes (owner-accepted).
    Returns once the window has actually landed (see wait_settled)."""
    x, y, w, h = rect
    freeze_transitions(hwnd)
    user32.ShowWindow(hwnd, SW_RESTORE)
    bl, bt, br, bb = _border_offsets(hwnd)
    user32.SetWindowPos(hwnd, 0, x - bl, y - bt, w + bl + br, h + bt + bb,
                        SWP_NOZORDER | SWP_NOACTIVATE)
    wait_settled(hwnd)


def raise_window(hwnd: int) -> None:
    """Bring to front + give focus. Windows refuses SetForegroundWindow to a
    background process under some timings (a freshly created layout stayed
    BEHIND — owner report 2026-08-02), so this stacks every known unlock:
    explicit z-top first (works regardless of focus rules), then plain
    SetForegroundWindow, then the AttachThreadInput trick, then the Alt
    nudge."""
    freeze_transitions(hwnd)  # no slide-up out of the taskbar to watch
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0,  # HWND_TOP
                        0x0001 | 0x0002 | 0x0040)  # NOSIZE|NOMOVE|SHOWWINDOW
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
                 template: str | None, orient: str, aspect: float,
                 icon: str | None = None):
        self.name = name
        self.process = process
        self.members = members
        self.template = template  # None = solo
        self.orient = orient      # "portrait" | "wide"
        self.aspect = aspect      # w/h the layout was last arranged for
        self.icon = icon          # target app's icon (PNG data URI) for the bar
        # Owner-chosen W:H for THIS layout (None = the phone's own shape).
        # `arranged` is what the windows currently stand in — a changed ratio
        # is what makes the next focus re-place them (owner 2026-08-03).
        self.ratio: tuple[int, int] | None = None
        self.arranged_ratio: tuple[int, int] | None = None


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
               mon_rect: tuple[int, int, int, int],
               name: str | None = None) -> int | None:
        """Arrange the windows and register the layout. Returns its index, or
        None when the target window died between pick and create.
        device_ratio = the phone's short/long side ratio; the layout's chosen
        orientation turns it into the actual w/h aspect."""
        if not is_alive(target):
            return None
        aspect = device_ratio if orient == "portrait" else 1.0 / device_ratio
        members = [target] + [h for h in fill if is_alive(h) and h != target]
        if mode == "grid" and template in GRID_TEMPLATES:
            cells = _cells(layout_region(mon_rect, aspect), template)
            members = members[:len(cells)]
            for hwnd, cell in zip(members, cells):
                place_window(hwnd, cell)
        else:
            template = None
            members = members[:1]
            place_window(target, layout_region(mon_rect, aspect))
        name = name or _title(target) or "Window"
        self.layouts.append(Layout(name, _process_name(target), members,
                                   template, orient, aspect,
                                   icon_data_uri(_process_path(target))))
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
        if abs(aspect - lay.aspect) > 0.05 or lay.arranged_ratio != lay.ratio:
            # A different device, or the owner changed this layout's aspect —
            # rebuild the arrangement.
            lay.aspect = aspect
            lay.arranged_ratio = lay.ratio
            region = layout_region(mon_rect, aspect, lay.ratio)
            if lay.template:
                for hwnd, cell in zip(lay.members, _cells(region, lay.template)):
                    place_window(hwnd, cell)
            else:
                place_window(lay.members[0], region)
        for hwnd in lay.members:
            raise_window(hwnd)
        if lay.template:
            cells = _cells(layout_region(mon_rect, lay.aspect, lay.ratio), lay.template)
            region = cells[0]
            x2 = max(c[0] + c[2] for c in cells[:len(lay.members)])
            y2 = max(c[1] + c[3] for c in cells[:len(lay.members)])
            region = (region[0], region[1], x2 - region[0], y2 - region[1])
        else:
            region = _frame_rect(lay.members[0])
            if region is None:
                return None
        return _normalize(region, mon_rect)

    def minimize_members(self) -> None:
        """Desktop position (owner 2026-08-02): every window that belongs to
        ANY layout gets minimized — the full-desktop view shows the desktop
        and only the windows that are NOT layout material. Focusing a layout
        later restores its own members (place/raise SW_RESTORE)."""
        self.prune()
        members = [h for lay in self.layouts for h in lay.members]
        for hwnd in members:
            freeze_transitions(hwnd)  # no slide-down to watch
            user32.ShowWindow(hwnd, SW_MINIMIZE)
        # Only report Desktop once they are ALL really gone (owner 2026-08-03).
        wait_minimized(members)

    def set_ratio(self, index: int, w: int, h: int) -> bool:
        """Store this layout's owner-chosen W:H (0/0 = back to the phone's own
        shape). Only stored — the next focus re-places the windows, which is
        what the caller does right after (owner 2026-08-03)."""
        if not 0 <= index < len(self.layouts):
            return False
        self.layouts[index].ratio = (w, h) if w > 0 and h > 0 else None
        return True

    def member_hwnds(self) -> set[int]:
        """Every window that already belongs to SOME layout — the creation
        list hides them (owner 2026-08-03: one window cannot be shown twice)."""
        self.prune()
        return {h for lay in self.layouts for h in lay.members}

    def remove(self, index: int) -> None:
        """Deleting a layout leaves the desktop exactly as it is (owner rule —
        no auto-return of windows). Its windows get their normal Windows
        minimize/restore animation back — we only froze it while they were
        layout material."""
        if 0 <= index < len(self.layouts):
            for hwnd in self.layouts[index].members:
                freeze_transitions(hwnd, False)
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
                         "orient": lay.orient, "icon": lay.icon,
                         "ratio": list(lay.ratio) if lay.ratio else None}
                        for lay in self.layouts],
            "active": active,
            "region": region,
            "orient": self.layouts[active].orient if active is not None else None,
        }
