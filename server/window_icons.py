"""The real app icon behind a window, as a PNG data URI for the phone.

Split out of [Window Manager](window_manager.md) on 2026-08-08 (THE STRUCTURE
LAW — that file had reached its ceiling and this was never window management):
nothing here knows what a window IS. It takes an executable's PATH and returns
a picture, which is shell + GDI work, and its failure mode is its own — an
icon is decoration, so every error ends as `None` and a text-only chip on the
phone, never as a failed layout.

The cache is per PATH, not per window: one Chrome icon is read once however
many windows the phone lists.
"""

import base64
import ctypes
import ctypes.wintypes as wintypes
import io
import logging

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

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
