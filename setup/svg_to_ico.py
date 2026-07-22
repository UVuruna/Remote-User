"""Generate multi-resolution ICOs from the project logo (root CLAUDE spec):

  assets/logo.svg        -> setup/icon.ico        (EXE, taskbar, Add/Remove)
  assets/logo-setup.svg  -> setup/icon-setup.ico  (NSIS wizard; falls back to logo.svg)

Renders with anti-aliased QPainter + supersampled Lanczos downscale for crisp
small sizes. Called by build.py; can run standalone:
    python setup/svg_to_ico.py

Requires: PySide6, Pillow.
"""

import sys
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

SETUP_DIR = Path(__file__).parent
PROJECT_DIR = SETUP_DIR.parent

LOGO_SVG = PROJECT_DIR / "assets" / "logo.svg"
LOGO_SETUP_SVG = PROJECT_DIR / "assets" / "logo-setup.svg"  # optional variant
ICO_PATH = SETUP_DIR / "icon.ico"
ICO_SETUP_PATH = SETUP_DIR / "icon-setup.ico"

ICO_SIZES = [16, 32, 48, 64, 128, 256]


def _render_svg_to_pil(renderer: QSvgRenderer, size: int) -> Image.Image:
    """Render the SVG at `size`, supersampled for small sizes (4x under 64 px,
    2x under 128 px) then Lanczos-downscaled for maximum sharpness."""
    factor = 4 if size <= 64 else 2 if size <= 128 else 1
    render_size = size * factor

    qimage = QImage(QSize(render_size, render_size), QImage.Format.Format_ARGB32)
    qimage.fill(Qt.GlobalColor.transparent)
    painter = QPainter(qimage)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    img = Image.frombytes("RGBA", (render_size, render_size),
                          qimage.bits().tobytes(), "raw", "BGRA")
    if factor > 1:
        img = img.resize((size, size), Image.Resampling.LANCZOS)
    return img


def _svg_to_ico(svg_path: Path, ico_path: Path) -> None:
    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise RuntimeError(f"Failed to load SVG: {svg_path}")

    frames = []
    for size in ICO_SIZES:
        img = _render_svg_to_pil(renderer, size)
        if img.getextrema()[3] == (0, 0):
            print(f"  WARNING: {size}x{size} frame is fully transparent!")
        frames.append(img)

    frames.reverse()  # largest first — Windows uses it as the primary
    frames[0].save(str(ico_path), format="ICO", append_images=frames[1:])
    print(f"  {ico_path.name} ({ico_path.stat().st_size / 1024:.0f} KB) <- {svg_path.name}")


def generate_icons() -> Path:
    """Both ICOs; returns the main icon path."""
    if QGuiApplication.instance() is None:
        QGuiApplication(sys.argv)  # QSvgRenderer needs a QGuiApplication
    if not LOGO_SVG.exists():
        raise FileNotFoundError(f"SVG not found: {LOGO_SVG}")

    _svg_to_ico(LOGO_SVG, ICO_PATH)
    setup_svg = LOGO_SETUP_SVG if LOGO_SETUP_SVG.exists() else LOGO_SVG
    _svg_to_ico(setup_svg, ICO_SETUP_PATH)
    return ICO_PATH


if __name__ == "__main__":
    print("Generating ICOs from SVG:")
    generate_icons()
    print(f"Sizes: {', '.join(f'{s}x{s}' for s in ICO_SIZES)}")
