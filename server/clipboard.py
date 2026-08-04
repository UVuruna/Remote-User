"""Puts phone-sent content into the Windows clipboard, ready to paste.

Two payloads (owner 2026-08-04):
- one image → CF_DIB bitmap (pastes into any image-accepting box), and
- a list of FILES (several images, or any type — PDF…) → CF_HDROP, exactly
  what Explorer's own Copy puts there, so Ctrl+V drops real files into
  Explorer, mail, messengers.
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import time
from pathlib import Path

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
CF_HDROP = 15
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


class DROPFILES(ctypes.Structure):
    """Header of the CF_HDROP payload — a UTF-16 double-NUL file list follows."""
    _fields_ = [
        ("pFiles", wintypes.DWORD),  # offset of the file list from struct start
        ("pt", wintypes.POINT),
        ("fNC", wintypes.BOOL),
        ("fWide", wintypes.BOOL),    # 1 = the list is UTF-16
    ]


def _set_clipboard(fmt: int, payload: bytes, what: str) -> bool:
    """Opens the clipboard (with retries — another app may briefly hold it),
    replaces its content with one global-memory payload, closes it."""
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
        if not user32.SetClipboardData(fmt, handle):
            kernel32.GlobalFree(handle)
            logger.error("SetClipboardData failed: %s", ctypes.get_last_error())
            return False
        logger.info("%s copied to clipboard", what)
        return True
    finally:
        user32.CloseClipboard()


def copy_image(frame_bgr: np.ndarray) -> bool:
    """Writes the frame to the clipboard as a CF_DIB bitmap."""
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
    return _set_clipboard(CF_DIB, bytes(header) + pixels, f"Image {width}x{height}")


def copy_files(paths: list[Path]) -> bool:
    """Puts real files on the clipboard (CF_HDROP) — Ctrl+V then drops them
    into whatever has focus, exactly like Copy in Explorer. Used for
    multi-file and non-image phone uploads (owner 2026-08-04)."""
    if not paths:
        return False
    listing = "".join(f"{Path(p).resolve()}\0" for p in paths) + "\0"
    header = DROPFILES(pFiles=ctypes.sizeof(DROPFILES), fNC=False, fWide=True)
    payload = bytes(header) + listing.encode("utf-16-le")
    return _set_clipboard(CF_HDROP, payload, f"{len(paths)} file(s)")
