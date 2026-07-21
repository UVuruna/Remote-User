"""Physical monitor enumeration — rects in virtual-desktop coordinates.

The injector needs the captured monitor's position within the virtual desktop;
dxcam only exposes its resolution. Monitors are matched to dxcam outputs by
size (unambiguous on mixed-resolution setups), falling back to enumeration
order, which matches DXGI output order on typical single-GPU machines.
"""

import ctypes
import ctypes.wintypes as wintypes
import logging

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

MONITORINFOF_PRIMARY = 1

MonitorEnumProc = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
    ctypes.POINTER(wintypes.RECT), wintypes.LPARAM,
)


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT),
        ("dwFlags", wintypes.DWORD),
    ]


def enumerate_monitors() -> list[dict]:
    """Active monitors as {left, top, width, height, primary} dicts."""
    monitors: list[dict] = []

    @MonitorEnumProc
    def callback(hmonitor, _hdc, _lprect, _lparam):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hmonitor, ctypes.byref(info))
        r = info.rcMonitor
        monitors.append({
            "left": r.left,
            "top": r.top,
            "width": r.right - r.left,
            "height": r.bottom - r.top,
            "primary": bool(info.dwFlags & MONITORINFOF_PRIMARY),
        })
        return True

    user32.EnumDisplayMonitors(None, None, callback, 0)
    return monitors


def rect_for_size(width: int, height: int, fallback_index: int) -> tuple[int, int, int, int]:
    """Rect (left, top, width, height) of the monitor matching the given size.
    Ambiguous sizes fall back to enumeration order; a miss falls back to primary."""
    monitors = enumerate_monitors()
    matches = [m for m in monitors if m["width"] == width and m["height"] == height]
    if len(matches) == 1:
        m = matches[0]
    elif fallback_index < len(monitors):
        m = monitors[fallback_index]
        logger.warning(
            "Monitor size %dx%d matched %d monitors — using enumeration index %d",
            width, height, len(matches), fallback_index,
        )
    else:
        m = next(m for m in monitors if m["primary"])
        logger.warning("No monitor matches %dx%d — falling back to primary", width, height)
    return (m["left"], m["top"], m["width"], m["height"])
