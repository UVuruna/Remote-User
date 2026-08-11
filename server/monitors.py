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


def describe(active_index: int, active_width: int, active_height: int,
             count: int) -> list[dict]:
    """The monitor list the PHONE names its Desktop rows after (owner
    2026-08-09, task 155: "tu ce pisati monitor jedan ta i ta rezolucija,
    monitor 2 i tako dalje" — lang-ok: owner quote).

    One entry per capturable output, `{index, width, height, primary}`, in the
    order `stream.switch_to` takes — which is why `count` comes from the
    capture source and not from this enumeration: DXGI is what decides how many
    monitors can be STREAMED, and a phone offered a row it cannot open would be
    a button that does nothing.

    THE ACTIVE MONITOR'S SIZE IS NEVER GUESSED. Its width/height come from the
    live stream, because that is the one output whose real capture geometry we
    know; the others are read from `enumerate_monitors`, under the same
    "enumeration order matches DXGI output order" assumption `rect_for_size`
    has always made (see the module docstring). A monitor the enumeration
    cannot name at all is still listed with a zero size rather than dropped —
    the phone falls back to plain "Monitor N", and a row that exists is the
    only way to reach that screen.
    """
    found = enumerate_monitors()
    out: list[dict] = []
    for index in range(max(0, count)):
        if index == active_index:
            width, height, primary = active_width, active_height, False
            if index < len(found):
                primary = found[index]["primary"]
        elif index < len(found):
            width = found[index]["width"]
            height = found[index]["height"]
            primary = found[index]["primary"]
        else:
            width = height = 0
            primary = False
        out.append({"index": index, "width": width, "height": height,
                    "primary": primary})
    return out


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
