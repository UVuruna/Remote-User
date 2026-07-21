"""Puts a captured BGR frame into the Windows clipboard as a CF_DIB image.

The owner takes a "screenshot" from the tablet and pastes it on the PC —
into a chat, an editor, anywhere that accepts a pasted image.
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import time

import numpy as np

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Explicit signatures — ctypes defaults truncate 64-bit handles/pointers to int.
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]

CF_DIB = 8
GMEM_MOVEABLE = 0x0002
BI_RGB = 0
OPEN_RETRIES = 5  # another app may briefly hold the clipboard


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


def copy_image(frame_bgr: np.ndarray) -> bool:
    """Writes the frame to the clipboard. Returns False (logged) on failure."""
    height, width = frame_bgr.shape[:2]
    # 32-bit BGRX rows need no 4-byte padding; DIB rows are bottom-up.
    bgra = np.dstack([frame_bgr, np.full((height, width, 1), 255, np.uint8)])
    pixels = np.ascontiguousarray(bgra[::-1]).tobytes()

    header = BITMAPINFOHEADER(
        biSize=ctypes.sizeof(BITMAPINFOHEADER),
        biWidth=width,
        biHeight=height,
        biPlanes=1,
        biBitCount=32,
        biCompression=BI_RGB,
        biSizeImage=len(pixels),
    )
    payload = bytes(header) + pixels

    for attempt in range(OPEN_RETRIES):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05 * (attempt + 1))
    else:
        logger.error("Clipboard is locked by another application")
        return False

    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
        if not handle:
            logger.error("GlobalAlloc failed for %d bytes", len(payload))
            return False
        locked = kernel32.GlobalLock(handle)
        ctypes.memmove(locked, payload, len(payload))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(CF_DIB, handle):
            kernel32.GlobalFree(handle)
            logger.error("SetClipboardData failed: %s", ctypes.get_last_error())
            return False
        logger.info("Screenshot %dx%d copied to clipboard", width, height)
        return True
    finally:
        user32.CloseClipboard()
