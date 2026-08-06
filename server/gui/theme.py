"""Design tokens + QSS for the desktop app.

Follows root DESIGN.md (dark-first, soft depth, one accent) with the same
slate/cyan palette as the web client (client/style.css) — one product, one
look. All values live HERE (root Rule #4); component code never hardcodes a
color or radius.
"""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from config import BUNDLE_DIR, FROZEN, PROJECT_ROOT

# ═══════════════════════════ ASSET PATHS ═══════════════════════════
# QSS reaches assets by PATH, so it needs the one the app is actually running
# from. Forward slashes and quotes: the installed path holds spaces
# ("C:/Program Files/Remote User/…") and a bare url() would break on them.
ASSET_URL = ((BUNDLE_DIR if FROZEN else PROJECT_ROOT) / "assets").as_posix()

# ═══════════════════════════ DESIGN TOKENS ═══════════════════════════
TOKENS = {
    # Surfaces (elevation steps lighter, never flat gray)
    "surface0": "#0F172A",
    "surface1": "#1E293B",
    "surface2": "#273449",
    "border": "rgba(255, 255, 255, 0.10)",
    # Text
    "text": "#F5F5F5",
    "text2": "#A8B3C5",
    # One accent family (matches the client)
    "accent": "#38BDF8",
    "accentDark": "#0EA5E9",
    "accentDim": "rgba(56, 189, 248, 0.16)",
    # Semantic
    "success": "#22C55E",
    "warning": "#F59E0B",
    "error": "#EF4444",
    # Shape
    "radiusControl": "8px",
    "radiusCard": "14px",
}

# Inter is the design-system typeface; the stack degrades to Segoe UI Variable
# (modern Win11 face) when Inter is not installed on the machine.
FONT_STACK = '"Inter", "Segoe UI Variable Display", "Segoe UI", sans-serif'

# ═══════════════════════════ STYLESHEET (QSS) ═══════════════════════════
QSS = """
QWidget {{
    background: {surface0};
    color: {text};
    font-family: {font};
    font-size: 13px;
}}

QFrame#card {{
    background: {surface1};
    border: 1px solid {border};
    border-radius: {radiusCard};
}}

QLabel {{ background: transparent; border: none; }}
QLabel#h1 {{ font-size: 20px; font-weight: 700; }}
QLabel#caption {{ color: {text2}; font-size: 12px; }}
QLabel#url {{ color: {text2}; font-size: 12px; }}
QLabel#qr {{ background: white; border-radius: 10px; }}

/* Status pill — colored by the `state` dynamic property */
QLabel#pill {{
    border-radius: 999px;
    padding: 4px 14px;
    font-weight: 600;
    font-size: 12px;
}}
QLabel#pill[state="running"]  {{ background: rgba(34, 197, 94, 0.16);  color: {success}; border: 1px solid rgba(34, 197, 94, 0.4); }}
QLabel#pill[state="starting"] {{ background: rgba(245, 158, 11, 0.16); color: {warning}; border: 1px solid rgba(245, 158, 11, 0.4); }}
QLabel#pill[state="stopped"]  {{ background: rgba(168, 179, 197, 0.12); color: {text2};  border: 1px solid {border}; }}
QLabel#pill[state="failed"]   {{ background: rgba(239, 68, 68, 0.16);  color: {error};  border: 1px solid rgba(239, 68, 68, 0.4); }}

QPushButton {{
    background: {surface2};
    border: 1px solid {border};
    border-radius: {radiusControl};
    padding: 8px 16px;
    font-weight: 600;
}}
QPushButton:hover   {{ border-color: {accent}; color: {accent}; }}
QPushButton:pressed {{ background: {surface1}; }}
QPushButton:disabled {{ color: {text2}; background: {surface1}; }}

QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {accent}, stop:1 {accentDark});
    border: none;
    color: #06212E;
}}
QPushButton#primary:hover  {{ background: {accent}; color: #06212E; }}
QPushButton#primary:disabled {{ background: {surface2}; color: {text2}; }}

QPushButton#danger {{
    background: rgba(239, 68, 68, 0.14);
    border: 1px solid rgba(239, 68, 68, 0.45);
    color: {error};
}}
QPushButton#danger:hover {{ background: rgba(239, 68, 68, 0.24); color: {error}; }}

/* min-width is a FLOOR for an empty combo, never a claim on space: at 140px
   two combos in one row held 280px while the shortcut field beside them was
   squeezed to "ift+tab" (owner screenshot 2026-08-05). Qt already sizes a
   combo to its longest item; the floor only keeps an empty one clickable.
   THE SPACE & LEGIBILITY LAW — no neighbour holds slack next to a starving
   element. */
QComboBox {{
    background: {surface2};
    border: 1px solid {border};
    border-radius: {radiusControl};
    padding: 6px 10px;
    min-width: 92px;
}}
QComboBox:hover {{ border-color: {accent}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {text2};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {surface2};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {accentDim};
    selection-color: {accent};
    outline: none;
}}

/* Checkboxes. Unstyled, a QCheckBox took the QWidget rule above and carried
   the WINDOW's background into the card it sits in — a darker block around
   the label, plus Windows' own gray tick box (owner screenshot 2026-08-06).
   The label is transparent, and the box is the same control surface as a
   combo, filled with the one accent when it is on. */
QCheckBox {{ background: transparent; spacing: 9px; }}
QCheckBox:disabled {{ color: {text2}; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {border};
    border-radius: 5px;
    background: {surface2};
}}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{
    background: {accent};
    border: 1px solid {accent};
    image: url("{assets}/check.svg");
}}
QCheckBox::indicator:disabled {{ background: {surface1}; border-color: {border}; }}
QCheckBox::indicator:checked:disabled {{ background: {accentDim}; }}

QMenu {{
    background: {surface1};
    border: 1px solid {border};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{ padding: 7px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {accentDim}; color: {accent}; }}

QToolTip {{
    background: {surface2};
    color: {text};
    border: 1px solid {border};
    padding: 4px 8px;
}}
""".format(font=FONT_STACK, assets=ASSET_URL, **TOKENS)


# ═══════════════════════════ HELPERS ═══════════════════════════
def card_shadow(widget: QWidget) -> None:
    """Soft ambient card shadow per DESIGN.md — Qt's defaults ARE the dated
    look (blur 1, offset 8/8), so parameters are always set explicitly."""
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(28)
    shadow.setOffset(0, 6)
    shadow.setColor(QColor(0, 0, 0, 55))
    widget.setGraphicsEffect(shadow)


def repolish(widget: QWidget) -> None:
    """Re-applies QSS after a dynamic property change (Qt caches styles)."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
