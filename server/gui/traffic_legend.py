"""The legend swatch: a colour mark DRAWN with QPainter, never a font glyph.

Split out of `gui/traffic_window.py` on 2026-08-18 (THE STRUCTURE LAW). It is
its own module because it is a WIDGET with its own painting rules, used by two
different parts of that window (the series/band legend and the per-device
rows) and by nothing else — the window itself owns layout and refresh, not
pixels.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from gui.theme import TOKENS
from gui.traffic_axis import _alpha


class LegendMark(QWidget):
    """One legend/status swatch — DRAWN with QPainter, never a font glyph or
    emoji. This project's rule holds on desktop exactly as it does on the
    phone: the owner's phone once rendered a glyph mark (✥) as a blunt
    cross, and DESIGN.md's icon rule ("a mark is drawn, never a font
    character") applies here too, not just to SVG toolbar icons.

    `color_fn` is a CALLABLE, not a QColor — same reason `out_color()` /
    `in_color()` are functions: a color captured once at construction
    would freeze whichever palette was active when the window was built and
    never follow a runtime theme flip (DESIGN.md → Live theme switching).
    """

    def __init__(self, color_fn, kind: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._color_fn = color_fn
        self._kind = kind
        self.setFixedSize(20, 14)  # layout-law: exempt - a fixed-size decorative colour swatch, never a text-carrying widget; its sibling QLabel carries the real content and wraps freely

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self._color_fn()
        rect = QRectF(self.rect()).adjusted(1, 2, -1, -2)
        if self._kind == "series":
            # Mirrors what the chart itself draws for this series — a faded
            # fill under a solid line — so the swatch reads as "this IS that
            # line's colour", not an arbitrary decoration.
            fill = QColor(color)
            fill.setAlpha(46)
            painter.fillRect(rect, fill)
            painter.setPen(QPen(color, 2))
            top = rect.top() + 2
            painter.drawLine(QPointF(rect.left(), top), QPointF(rect.right(), top))
        elif self._kind == "band":
            painter.fillRect(rect, color)
            painter.setPen(QPen(_alpha(TOKENS["text2"], 60), 1))
            painter.drawRect(rect)
        elif self._kind == "dotted":
            painter.setPen(QPen(color, 2, Qt.PenStyle.DotLine))
            y = rect.center().y()
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        elif self._kind == "dot":
            d = min(rect.width(), rect.height())
            circle = QRectF(rect.center().x() - d / 2, rect.center().y() - d / 2, d, d)
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(circle)
        painter.end()
