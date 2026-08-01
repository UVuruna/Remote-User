# SVG To ICO

**Script:** [SVG To ICO (script)](../svg_to_ico.py) ·
**Flow:** [diagram](../__flow/svg_to_ico.md)

## Purpose

Renders the project's SVG logo(s) into multi-resolution Windows `.ico` files
(root SHIP.md pipeline Step 1): `assets/logo.svg` → `setup/icon.ico`
(EXE icon, taskbar, Add/Remove Programs) and `assets/logo-setup.svg`
(falling back to `logo.svg` when the setup-specific variant doesn't exist)
→ `setup/icon-setup.ico` (the NSIS installer wizard icon). Runs standalone
(`python setup/svg_to_ico.py`) or as Step 1 inside `build.py`.

## Connections

### Uses
- `assets/logo.svg` / `assets/logo-setup.svg` — source vector art at the
  project root
- PySide6 `QSvgRenderer` / `QPainter` / `QImage` (rendering) and Pillow
  `Image` (Lanczos downscale + multi-frame ICO encoding) — no
  project-internal imports

### Used by
- [Build Orchestrator](build.md) — Step 1, invoked as
  `subprocess.run([sys.executable, "setup/svg_to_ico.py"])` before
  PyInstaller runs, since the EXE embeds `icon.ico` and the NSIS wizard
  embeds `icon-setup.ico`

## Functions

### `_render_svg_to_pil(renderer, size) -> Image.Image`
Renders one square frame at `size`, supersampled for sharpness: factor 4 for
`size <= 64`, factor 2 for `size <= 128`, factor 1 (no supersampling) above
that. Draws into an ARGB32 `QImage` at `size * factor` with antialiasing and
smooth-pixmap-transform render hints via `QPainter`, converts the raw BGRA
buffer to a Pillow `Image`, then Lanczos-downscales back down to `size` when
a supersample factor > 1 was used.

### `_svg_to_ico(svg_path, ico_path) -> None`
Loads `svg_path` into one `QSvgRenderer` (raises `RuntimeError` if invalid),
renders every size in `ICO_SIZES = [16, 32, 48, 64, 128, 256]` through
`_render_svg_to_pil` (prints a warning if any frame renders fully
transparent — `getextrema()[3] == (0, 0)`), reverses the frame list so the
LARGEST frame is first (Windows uses the first frame as the primary icon),
and saves all frames as one multi-resolution `.ico` via Pillow's
`Image.save(format="ICO", append_images=...)`.

### `generate_icons() -> Path`
Entry point. Lazily creates the single `QGuiApplication` instance
`QSvgRenderer` needs to render at all (even off-screen), raises
`FileNotFoundError` if `assets/logo.svg` is missing, then calls
`_svg_to_ico` twice: `LOGO_SVG → ICO_PATH` and
`(LOGO_SETUP_SVG if it exists else LOGO_SVG) → ICO_SETUP_PATH`. Returns the
main icon's path.
