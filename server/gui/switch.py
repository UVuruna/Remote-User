"""The sun/moon theme pill, and the cover that hides the repaint under it.

Build round R3 (owner-approved 2026-08-07). Ported to Qt from the owner's own
PromptPainter switch (`Gadgets/PromptPainter/gui/switch.py`), keeping the two
things that make that one feel deliberate rather than jumpy:

  1. **The knob slides on a smoothstep over ~600 ms.** Slow enough to be a
     gesture, eased so it never starts or stops with a jerk. The animation is
     driven LINEARLY and shaped in `_knob_x` — Qt's easing enum has no
     smoothstep and a custom-curve callback is a per-frame trip into Python
     for nothing when the same curve is three characters of arithmetic.
  2. **The theme change itself is never SEEN.** A window re-styled live goes
     through a repaint cascade — cards, shadows, item delegates, the traffic
     chart — and watching that happen looks like a bug. So the switch grabs a
     picture of every open window FIRST, lays it over the real thing, changes
     the palette underneath it, and fades the stale picture out over ~300 ms.
     The user sees one cross-fade; the cascade happens behind it.

The pill carries no text, so it is the one control in this app allowed a hard
size — declared through `sizeHint`/`minimumSizeHint` and a Fixed size policy
rather than `setFixedSize`, which THE SPACE & LEGIBILITY LAW bans outright
(`tests/test_layout_law.py`) because it also freezes text-bearing widgets.

The sun and the moon are DRAWN with QPainter, never a font glyph — the same
rule the phone's Move handle earned on 2026-08-05, when ✥ came out a blunt
cross on the owner's device.
"""

import logging
import math

from PySide6.QtCore import (
    Property, QEasingCurve, QPropertyAnimation, QPointF, QRectF, QSize, Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QLabel, QWidget

from config import save_user_settings
from gui.theme import TOKENS, apply_theme

logger = logging.getLogger(__name__)

# Geometry of the pill, in logical px. A 26 px track beside a 13 px label row
# reads as a control, not as a second heading.
TRACK_W = 54
TRACK_H = 26
KNOB_INSET = 3
SLIDE_MS = 600          # the owner's own switch timing
COVER_FADE_MS = 300     # how long the stale snapshot takes to disappear


def _smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


class ThemeSwitch(QWidget):
    """Sun/moon pill. Left = moon = dark, right = sun = light.

    It does not decide anything by itself: a click emits `picked` with the
    theme name, and whoever owns the setting saves it and calls
    `flip_theme()`. Two of these exist at once (the main window's top bar and
    the Settings window's Appearance card), so each one is told the current
    theme with `set_theme_name` instead of reading a state of its own — a
    switch that remembered its own position would drift from its twin.
    """

    picked = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._slide = 0.0          # 0 = dark (left), 1 = light (right)
        self._on = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(self.sizePolicy().Policy.Fixed,
                           self.sizePolicy().Policy.Fixed)
        self.setToolTip("Switch between the dark and the light theme")
        self.setAccessibleName("Theme")
        self._anim = QPropertyAnimation(self, b"slide", self)
        self._anim.setDuration(SLIDE_MS)
        # LINEAR here on purpose — the smoothstep is applied in _knob_x, so
        # the curve is exactly the owner's, not Qt's nearest enum.
        self._anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.Linear))

    # -- geometry ----------------------------------------------------------

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt override
        return QSize(TRACK_W, TRACK_H)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt override
        return self.sizeHint()

    # -- the animated property ---------------------------------------------

    def _get_slide(self) -> float:
        return self._slide

    def _set_slide(self, value: float) -> None:
        self._slide = value
        self.update()

    slide = Property(float, _get_slide, _set_slide)

    # -- state -------------------------------------------------------------

    def set_theme_name(self, name: str, animate: bool = False) -> None:
        """Reflect a theme the switch did not choose (construction, or the
        twin switch in the other window being clicked)."""
        target = 1.0 if name == "light" else 0.0
        self._on = target > 0.5
        if not animate:
            self._anim.stop()
            self._set_slide(target)
            return
        self._anim.stop()
        self._anim.setStartValue(self._slide)
        self._anim.setEndValue(target)
        self._anim.start()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 — Qt override
        if event.button() != Qt.MouseButton.LeftButton:
            return
        name = "dark" if self._on else "light"
        self.set_theme_name(name, animate=True)
        self.picked.emit(name)

    # -- drawing -----------------------------------------------------------

    def _knob_x(self) -> float:
        travel = self.width() - TRACK_H
        return KNOB_INSET + travel * _smoothstep(max(0.0, min(1.0, self._slide)))

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        h = self.height()
        radius = h / 2

        track = _token_color("surface2")
        painter.setPen(QPen(_token_color("border"), 1))
        painter.setBrush(track)
        painter.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, h - 1),
                                radius, radius)

        # The two destinations, drawn dim on the track: moon on the left,
        # sun on the right, so the pill says what it does while standing
        # still. The knob then covers whichever one is current.
        dim = _token_color("text2")
        dim.setAlpha(150)
        self._moon(painter, QPointF(h / 2, h / 2), h * 0.20, dim, track)
        self._sun(painter, QPointF(self.width() - h / 2, h / 2), h * 0.17, dim)

        # The knob itself — the one accent, carrying the ACTIVE symbol.
        knob_d = h - 2 * KNOB_INSET
        cx = self._knob_x() + knob_d / 2
        accent = _token_color("accent")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawEllipse(QPointF(cx, h / 2), knob_d / 2, knob_d / 2)
        ink = _token_color("onAccent")
        if self._slide > 0.5:
            self._sun(painter, QPointF(cx, h / 2), knob_d * 0.24, ink)
        else:
            self._moon(painter, QPointF(cx, h / 2), knob_d * 0.28, ink, accent)

        painter.end()

    def _moon(self, painter: QPainter, centre: QPointF, r: float,
              color: QColor, behind: QColor) -> None:
        """A crescent: a filled disc with a second disc punched out of it by
        painting `behind` — whatever the crescent is sitting ON — over its
        edge. Drawn, never a glyph. A clip path per frame would be the other
        way; two ellipses are cheaper and read identically at this size."""
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(centre, r, r)
        painter.setBrush(behind)
        painter.drawEllipse(QPointF(centre.x() + r * 0.55, centre.y() - r * 0.15),
                            r * 0.85, r * 0.85)

    def _sun(self, painter: QPainter, centre: QPointF, r: float,
             color: QColor) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(centre, r, r)
        # Eight thin rays with a clear gap to the disc. Thicker or closer (the
        # first attempt: width r*0.28 starting at r*1.5) and the whole thing
        # read as a COG rather than a sun on the light theme's filled knob —
        # caught by opening the shot, which is what that gate is for.
        pen = QPen(color)
        pen.setWidthF(max(1.0, r * 0.20))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for i in range(8):
            angle = i * math.pi / 4
            direction = QPointF(math.cos(angle), math.sin(angle))
            painter.drawLine(centre + direction * (r * 1.75),
                             centre + direction * (r * 2.45))


def _token_color(name: str) -> QColor:
    """A palette token as a QColor, read LIVE (never cached in a module
    constant — see gui/theme.py). `rgba(r, g, b, a)` is parsed by hand:
    QColor understands `#rrggbb` and CSS names, not the QSS rgba() form the
    tokens use for translucent values."""
    raw = TOKENS[name]
    if raw.startswith("rgba"):
        parts = [p.strip() for p in raw[raw.index("(") + 1:raw.rindex(")")].split(",")]
        return QColor(int(parts[0]), int(parts[1]), int(parts[2]),
                      int(round(float(parts[3]) * 255)))
    return QColor(raw)


# ═══════════════════════════ THE COVER TRANSITION ═══════════════════════════
def flip_theme(name: str) -> str:
    """Change the palette under a snapshot of every open window.

    This is the whole point of the pattern: `theme.apply_theme` re-styles the
    application, and Qt then re-polishes every widget in every window — cards
    lose and regain their shadow colour, item delegates re-measure, the
    traffic chart repaints. Doing that in front of the user looks like a
    glitch. Doing it under a still picture of the previous state, and fading
    that picture out, looks like a transition.

    Falls back to a plain switch when there is no window to cover (a headless
    guard run, or the app starting up) — the flip must never depend on the
    decoration.
    """
    app = QApplication.instance()
    if app is None:
        return apply_theme(name)
    covers = [_cover(window) for window in app.topLevelWidgets()
              if window.isVisible() and window.width() > 1 and window.height() > 1]
    applied = apply_theme(name)
    for cover in covers:
        if cover is not None:
            _fade_out(cover)
    return applied


def choose_theme(name: str) -> None:
    """What a click on EITHER pill does: persist the choice, flip the whole
    application under the cover, and move every switch in the app to match.

    One function rather than a handler per window (and no parent/child
    plumbing between them): there are two switches for the same single
    setting, and "who called me" is not information either of them should
    have to carry. Finding the twins through `allWidgets` costs one walk on a
    click a user makes a few times a year.
    """
    save_user_settings({"ui_theme": name})
    flip_theme(name)
    app = QApplication.instance()
    if app is None:
        return
    for widget in app.allWidgets():
        if isinstance(widget, ThemeSwitch):
            widget.set_theme_name(name, animate=True)


def _cover(window: QWidget) -> QLabel | None:
    """A frozen picture of `window`, laid over it. Child widget + opacity
    effect, deliberately NOT a translucent frameless top-level: rules/GUI.md
    bans those (they take move/resize away from DWM) and a child cannot fall
    out of sync with the window it covers."""
    shot = window.grab()
    if shot.isNull():
        logger.warning("Theme cover: could not grab %s", window.objectName() or window)
        return None
    label = QLabel(window)
    label.setPixmap(shot)
    label.setGeometry(0, 0, window.width(), window.height())
    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    label.show()
    label.raise_()
    return label


def _fade_out(label: QLabel) -> None:
    effect = QGraphicsOpacityEffect(label)
    effect.setOpacity(1.0)
    label.setGraphicsEffect(effect)
    animation = QPropertyAnimation(effect, b"opacity", label)
    animation.setDuration(COVER_FADE_MS)
    animation.setStartValue(1.0)
    animation.setEndValue(0.0)
    animation.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))
    animation.finished.connect(label.deleteLater)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
