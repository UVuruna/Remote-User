"""Mouse injection via Win32 SendInput.

Receives coordinates normalized 0-1 within the captured monitor and maps them
to the 0-65535 absolute range of the entire virtual desktop, as SendInput
requires. The process MUST be per-monitor DPI aware before this module is used
(main.py declares it) — otherwise Windows silently rescales coordinates.
"""

import ctypes
import ctypes.wintypes as wintypes
import logging

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

# SendInput constants
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

# GetSystemMetrics indices
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

BUTTON_FLAGS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


class InputInjector:
    """Maps monitor-normalized coordinates to virtual-desktop absolutes and injects."""

    def __init__(self, monitor_rect: tuple[int, int, int, int]):
        """monitor_rect: (left, top, width, height) of the captured monitor in pixels."""
        self.monitor_rect = monitor_rect
        self.virtual_rect = (
            user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CYVIRTUALSCREEN),
        )
        logger.info("Injector ready — monitor=%s virtual=%s", monitor_rect, self.virtual_rect)

    def _to_absolute(self, x_norm: float, y_norm: float) -> tuple[int, int]:
        mon_left, mon_top, mon_w, mon_h = self.monitor_rect
        virt_left, virt_top, virt_w, virt_h = self.virtual_rect
        px = mon_left + x_norm * mon_w
        py = mon_top + y_norm * mon_h
        abs_x = round((px - virt_left) / virt_w * 65535)
        abs_y = round((py - virt_top) / virt_h * 65535)
        return abs_x, abs_y

    def _send(self, flags: int, abs_x: int = 0, abs_y: int = 0) -> None:
        inp = INPUT(type=INPUT_MOUSE)
        inp.mi = MOUSEINPUT(abs_x, abs_y, 0, flags, 0, None)
        sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        if sent != 1:
            logger.error("SendInput failed: %s", ctypes.get_last_error())

    def move(self, x_norm: float, y_norm: float) -> None:
        abs_x, abs_y = self._to_absolute(x_norm, y_norm)
        self._send(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, abs_x, abs_y)

    def button_down(self, x_norm: float, y_norm: float, button: str) -> None:
        down, _ = BUTTON_FLAGS[button]
        abs_x, abs_y = self._to_absolute(x_norm, y_norm)
        self._send(
            MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | down, abs_x, abs_y
        )

    def button_up(self, x_norm: float, y_norm: float, button: str) -> None:
        _, up = BUTTON_FLAGS[button]
        abs_x, abs_y = self._to_absolute(x_norm, y_norm)
        self._send(
            MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK | up, abs_x, abs_y
        )
