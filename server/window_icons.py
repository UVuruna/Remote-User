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


# A STORE APP'S EXE HAS NO ICON IN IT (owner report 2026-08-08, with his
# lang-ok: his own words, quoted — "zasto stoji genericka ikona ako program
# vec zna ikonu image previewera kojeg je napravljen layout").
#
# MEASURED before answering: `SHGetFileInfoW` on
# ...\WindowsApps\Microsoft.Windows.Photos_...\Microsoft.Photos.exe returns a
# 516-byte GENERIC document glyph, against 1,188 for Code.exe and 2,080 for
# chrome.exe — and that glyph is exactly what he photographed. So the program
# did NOT already know the icon: it asked the executable, and a packaged app's
# executable genuinely carries none. The real one lives in the package, as PNG
# assets named by its manifest.
#
# No WinRT for this: the package root is the folder directly under
# WindowsApps on the exe's own path, `AppxManifest.xml` sits in it, and both
# are plain file reads. That keeps this module ctypes-and-files, as it was.
_APPX_ROOT = "windowsapps"
# Scale suffixes, best first. `targetsize-32` is authored for exactly the size
# we draw; scale-100 on a Square44x44Logo is 44px, the next honest thing. The
# plain name (no `altform`) is the colourful icon Windows shows in Start —
# `altform-unplated` drops the tile plate and `theme-light` is drawn for a
# light background, and the phone has BOTH themes, so neither is a safe pick.
_APPX_PREFERRED = ("targetsize-32", "targetsize-48", "scale-100", "scale-125",
                   "scale-150", "scale-200")


def _appx_asset(exe_path: str):
    """The PNG a packaged app's manifest names for its small icon, or None."""
    import re
    from pathlib import Path

    path = Path(exe_path)
    parts = [p.lower() for p in path.parts]
    if _APPX_ROOT not in parts:
        return None
    root = Path(*path.parts[:parts.index(_APPX_ROOT) + 2])
    manifest = root / "AppxManifest.xml"
    if not manifest.exists():
        return None
    text = manifest.read_text(encoding="utf-8", errors="replace")
    # Square44x44Logo is the Start-menu/taskbar icon — the one a person means
    # by "the app's icon". `Logo` (the 150x150 tile) is the fallback for an
    # older manifest that never declared the small one.
    for attr in ("Square44x44Logo", "Square30x30Logo", "Logo"):
        match = re.search(attr + r'="([^"]+)"', text)
        if not match:
            continue
        named = root / match.group(1).replace("\\", "/")
        # The name in the manifest is a STEM: what is on disk is one file per
        # scale (PhotosAppList.scale-200.png), and the bare name usually does
        # not exist at all. Measured on his own PC: 55 files, none of them the
        # name the manifest gives.
        if named.exists():
            return named
        siblings = sorted(named.parent.glob(named.stem + "*.png"))
        if not siblings:
            continue
        plain = [f for f in siblings if "altform" not in f.name]
        pool = plain or siblings
        for suffix in _APPX_PREFERRED:
            for candidate in pool:
                if suffix in candidate.name:
                    return candidate
        return pool[0]
    return None


def _packaged_icon(exe_path: str) -> str | None:
    """A Store app's REAL icon, read from its package, as a PNG data URI."""
    try:
        asset = _appx_asset(exe_path)
        if asset is None:
            return None
        from PIL import Image

        with Image.open(asset) as img:
            icon = img.convert("RGBA")
            if icon.size != (_ICON_SIZE, _ICON_SIZE):
                icon = icon.resize((_ICON_SIZE, _ICON_SIZE), Image.LANCZOS)
            buf = io.BytesIO()
            icon.save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception as e:  # noqa: BLE001 — falls through to the shell route
        logger.warning("Packaged icon unreadable for %s: %s", exe_path, e)
        return None


def icon_data_uri(exe_path: str) -> str | None:
    """The exe's icon as a PNG data URI (cached per path; None on any
    failure — the phone falls back to text-only chips)."""
    if not exe_path:
        return None
    if exe_path in _icon_cache:
        return _icon_cache[exe_path]
    # The package FIRST, and only for a packaged app: `_appx_asset` returns
    # None for every ordinary exe, so a Win32 app pays one path-parts check.
    packaged = _packaged_icon(exe_path)
    if packaged:
        _icon_cache[exe_path] = packaged
        return packaged
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
