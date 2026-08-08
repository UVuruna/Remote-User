# Window icons

**Folder:** [Server](../___server.md) ·
**Caller:** [Window Manager](window_manager.md)

## Purpose

One job: turn an executable's path into a PNG data URI the phone can draw
beside a window or tab name (owner request 2026-08-02 — the layout list shows
the REAL app icon, not a generic square).

Split out of [Window Manager](window_manager.md) on 2026-08-08 (THE STRUCTURE
LAW — that file had reached its 1,000-line ceiling and this was never window
management). Nothing here knows what a window is: it is shell + GDI work on a
FILE PATH, and its failure mode is its own.

## Connections

### Uses

- `shell32.SHGetFileInfoW` — the icon handle for a path
- `gdi32` + `user32.DrawIconEx` — draw it into a 32×32 top-down BGRA DIB
- `PIL.Image` — that buffer to PNG bytes

### Used by

- [Window Manager](window_manager.md) — `list_windows`, `window_at`,
  `window_at_hwnd` and `LayoutRegistry.create`, all through the name imported
  into that module

## Key Functions & Data

| Name | What it does |
|------|--------------|
| `icon_data_uri(exe_path)` | The icon as `data:image/png;base64,…`, or `None`. |
| `_icon_cache` | Per PATH, not per window — one Chrome icon is read once however many windows the phone lists. Negative results are cached too, so a path that has no icon is not retried on every frame. |

## A Store app's icon is in its PACKAGE (owner 2026-08-08)

His screenshot: a generic glyph on a layout made from the Photos window, and
the fair question — why, when the program already knows the app.

MEASURED before it was answered, because his premise was reasonable and wrong.
`SHGetFileInfoW` on
`...\WindowsApps\Microsoft.Windows.Photos_...\Microsoft.Photos.exe` returns a
**516-byte generic document glyph**, against 1,188 for `Code.exe` and 2,080 for
`chrome.exe` — and that glyph is exactly what he photographed. The program did
not already know the icon: it asked the executable, and a packaged app's
executable carries no icon resource at all.

So `_appx_asset` reads `AppxManifest.xml` from the package root on the exe's
own path and takes `Square44x44Logo` (falling back to `Square30x30Logo`, then
`Logo`). The name in the manifest is a **stem**: what ships is one file per
scale, and the bare name usually does not exist — 55 asset files on the owner's
PC, none of them `PhotosAppList.png`. Plain names beat `altform` variants
(`unplated` drops the tile plate, `theme-light` is drawn for a light
background, and the phone has both themes); `targetsize-32` beats the scales
because it is authored for the size we draw.

Everything fails through to the shell route, so a generic icon still beats no
layout. No WinRT: package root, manifest and asset are all plain file reads.

Verified on the owner's live desktop — Photos 1,766 bytes and the real teal
glyph, `Code.exe` and `chrome.exe` byte-identical to before. Gate: two checks
in `tests/test_layout_protocol.py` over a fake package on disk.

## Design Decisions

- **An icon is decoration, never a failure.** Every error inside is swallowed
  into a `warning` and a `None`; the phone falls back to a text-only chip. A
  layout must never fail to appear because a picture could not be read.

- **The ctypes signatures are declared explicitly.** Without `restype` /
  `argtypes`, ctypes truncates `HDC`/`HBITMAP` to `c_int` and `DrawIconEx` /
  `SelectObject` overflow on x64 — hit live on 2026-08-02, and the reason
  those eight lines exist.

- **Top-down DIB** (`biHeight` negative) so the buffer hands straight to
  `Image.frombuffer` in `BGRA` order with no row flip.
