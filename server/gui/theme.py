"""Design tokens + QSS for the desktop app.

Follows root DESIGN.md (dark-first, soft depth, one accent) with the same
slate/cyan palette as the web client (client/style.css) — one product, one
look. All values live HERE (root Rule #4); component code never hardcodes a
color or radius.
"""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

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

QComboBox {{
    background: {surface2};
    border: 1px solid {border};
    border-radius: {radiusControl};
    padding: 6px 10px;
    min-width: 140px;
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
""".format(font=FONT_STACK, **TOKENS)


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
