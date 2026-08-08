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
