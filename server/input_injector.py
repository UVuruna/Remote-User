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
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000
WHEEL_DELTA = 120

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

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

# Structural keys the client may send as `key_special` or inside a chord.
VK_CODES = {
    "enter": 0x0D,
    "return": 0x0D,
    "backspace": 0x08,
    "tab": 0x09,
    "escape": 0x1B,
    "esc": 0x1B,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "space": 0x20,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
}

# Modifiers usable in a chord ("ctrl+win+alt+1").
MODIFIER_VKS = {
    "ctrl": 0x11, "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B, "meta": 0x5B, "super": 0x5B,
}


def vk_for_key(token: str) -> int | None:
    """Virtual-key code for a single chord token (letter, digit, F-key, or name)."""
    token = token.lower()
    if len(token) == 1:
        ch = token.upper()
        if "A" <= ch <= "Z" or "0" <= ch <= "9":
            return ord(ch)
    if token in VK_CODES:
        return VK_CODES[token]
    if token in MODIFIER_VKS:  # a modifier used alone, e.g. "win"
        return MODIFIER_VKS[token]
    if token.startswith("f") and token[1:].isdigit():
        n = int(token[1:])
        if 1 <= n <= 24:
            return 0x6F + n  # F1 = 0x70
    return None


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

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

    def set_monitor_rect(self, rect: tuple[int, int, int, int]) -> None:
        """Called when the streamed monitor changes."""
        self.monitor_rect = rect
        logger.info("Injector now targeting monitor rect %s", rect)

    def cursor_norm(self) -> tuple[float, float] | None:
        """Current cursor position normalized to the captured monitor — the
        inverse of the injection mapping, used for the client-drawn virtual
        cursor (DXGI frames never contain the pointer). Values fall outside
        0-1 when the cursor is on another monitor. None when Windows refuses
        the read (e.g. secure desktop during a UAC prompt)."""
        pt = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(pt)):
            return None
        left, top, w, h = self.monitor_rect
        return ((pt.x - left) / w, (pt.y - top) / h)

    def _to_absolute(self, x_norm: float, y_norm: float) -> tuple[int, int]:
        mon_left, mon_top, mon_w, mon_h = self.monitor_rect
        virt_left, virt_top, virt_w, virt_h = self.virtual_rect
        px = mon_left + x_norm * mon_w
        py = mon_top + y_norm * mon_h
        abs_x = round((px - virt_left) / virt_w * 65535)
        abs_y = round((py - virt_top) / virt_h * 65535)
        return abs_x, abs_y

    def _send(self, flags: int, abs_x: int = 0, abs_y: int = 0, mouse_data: int = 0) -> None:
        inp = INPUT(type=INPUT_MOUSE)
        # mouseData is a DWORD but Windows reads it as signed for wheel deltas.
        inp.mi = MOUSEINPUT(abs_x, abs_y, mouse_data & 0xFFFFFFFF, flags, 0, None)
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

    def wheel(self, x_norm: float, y_norm: float, ticks: float) -> None:
        """Moves the cursor to the gesture point (the wheel targets the window
        under the cursor), then scrolls by the given number of wheel ticks."""
        self.move(x_norm, y_norm)
        self._send(MOUSEEVENTF_WHEEL, mouse_data=round(ticks * WHEEL_DELTA))

    def _send_key(self, vk: int, scan: int, flags: int) -> None:
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.ki = KEYBDINPUT(vk, scan, flags, 0, None)
        sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        if sent != 1:
            logger.error("SendInput (key) failed: %s", ctypes.get_last_error())

    def type_text(self, text: str) -> None:
        """Injects arbitrary Unicode text via VK_PACKET. Surrogate pairs work —
        each UTF-16 code unit is sent as its own down+up event."""
        data = text.encode("utf-16-le")
        for i in range(0, len(data), 2):
            unit = int.from_bytes(data[i:i + 2], "little")
            self._send_key(0, unit, KEYEVENTF_UNICODE)
            self._send_key(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)

    def press_key(self, name: str) -> None:
        """Presses a structural key (Enter, Backspace, arrows…) by VK code."""
        vk = VK_CODES.get(name.lower())
        if vk is None:
            logger.error("Unknown special key %r from client", name)
            return
        self._send_key(vk, 0, 0)
        self._send_key(vk, 0, KEYEVENTF_KEYUP)

    def press_chord(self, chord: str) -> None:
        """Presses a key combination like 'ctrl+c' or 'ctrl+win+alt+1': all but
        the last token are modifiers, held down while the final key is tapped,
        then released in reverse order."""
        tokens = [t.strip() for t in chord.split("+") if t.strip()]
        if not tokens:
            logger.error("Empty chord from client")
            return
        *mod_names, main_name = tokens
        mod_vks = []
        for name in mod_names:
            vk = MODIFIER_VKS.get(name.lower())
            if vk is None:
                logger.error("Unknown modifier %r in chord %r", name, chord)
                return
            mod_vks.append(vk)
        main_vk = vk_for_key(main_name)
        if main_vk is None:
            logger.error("Unknown key %r in chord %r", main_name, chord)
            return
        for vk in mod_vks:
            self._send_key(vk, 0, 0)
        self._send_key(main_vk, 0, 0)
        self._send_key(main_vk, 0, KEYEVENTF_KEYUP)
        for vk in reversed(mod_vks):
            self._send_key(vk, 0, KEYEVENTF_KEYUP)
        logger.info("Chord fired: %s", chord)
