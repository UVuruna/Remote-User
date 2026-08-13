"""How a window declares the minimum size it truly needs.

One responsibility, one implementation — because the same settle loop was
copied into three windows and the same lie was in all three copies.

THE LIE (owner's screenshots, 2026-08-06). Qt's `minimumSizeHint()` quotes a
WRAPPING label at the height of one line. The main window's QR card holds two
of them (the pairing URL, the four-line Tailscale guidance), so the column's
"minimum" came out 48 px short of what it needs at its real width. And a
layout that is short of space does not clip — **it overlaps**: every widget
still reports its full size while the link is painted straight across the QR
code. That is how a guard measuring SIZES could report PASS over a window the
owner had photographed twice.

THE TRUTH is `heightForWidth`: at THIS width, how tall must this column be?
Measured on the owner's own machine — hint 835, truth 883, and the QR card
handed 332 px against a minimum of 348.

Two further rules learned the same day, both encoded here:

- **Measure while SHOWN.** A hidden widget has no real metrics, and a button
  `show()`n on a hidden parent counts for nothing — 43 px of update button, in
  the main window's case.
- **Measure with the REAL font.** The theme reaches a dialog through its
  parent's stylesheet and Qt resolves QSS fonts only when a widget is
  polished, which happens on show.

AND THE OTHER HALF OF THE SAME LAW (owner report 2026-08-12, his own Settings
window with its top cut off): a window that is the right SIZE is still
unreadable when part of it is off the screen. Qt places a child window from
the size it has BEFORE the show, and then the settle above GROWS it in place —
so a parent sitting high or far right leaves the grown dialog's edge past the
screen bounds, and nothing in the measurement can see that. `clamp_to_screen`
is the answer, and it belongs here beside the settle it corrects: one
implementation, called wherever a window's geometry is final.
"""

from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class WrapLabel(QLabel):
    """A QLabel that really gets the height its wrapped text needs.

    THE LADDER'S REFLOW STEP WAS MUTE IN THIS CODEBASE, and it was mute
    silently (found 2026-08-13, the first time the Traffic window was
    photographed with real data in it — the audit read its device legend as
    ELIDED, "needs 48px height, has 32"). `setWordWrap(True)` only permits a
    QLabel to wrap. It does not make the parent layout ALLOCATE the second
    line: a wrapped QLabel's `minimumSizeHint` is one line tall, and a
    QVBoxLayout squeezed by a stretching sibling — here the chart, which
    takes every spare pixel by design — hands it exactly that. Setting
    `sizePolicy().setHeightForWidth(True)` is not enough either; it changes
    what the layout MAY ask for, not the floor below which the label refuses
    to be squeezed.

    So the floor is stated outright: on every resize, and after every text
    change, the label's own `heightForWidth` at its current width becomes its
    minimum height. That is a real measurement of the real string in the real
    font at the real width, never an estimate of how many lines some text
    "should" take.

    It lives in `sizing.py` rather than beside its first caller because the
    defect is not the Traffic window's: any window with a wrapping label under
    a stretching sibling has it, and the responsibility for how big a thing
    has to be is this module's.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setWordWrap(True)
        policy = self.sizePolicy()
        policy.setHeightForWidth(True)
        policy.setVerticalPolicy(QSizePolicy.Policy.Minimum)
        self.setSizePolicy(policy)

    def _claim_height(self) -> None:
        width = self.width()
        if width <= 0:
            return
        needed = self.heightForWidth(width)
        if needed > 0 and needed != self.minimumHeight():
            self.setMinimumHeight(needed)

    def minimumSizeHint(self) -> QSize:        # noqa: N802 (Qt's own name)
        """AND THE WINDOW'S OWN MINIMUM MUST HEAR ABOUT IT (ladder step 3).
        `setMinimumHeight` alone fixes the label inside a window that is
        already big enough; it does not raise the FLOOR the window declares,
        because `sizing.settle_minimum` grows a window by re-measuring what
        its children say they need, and a wrapped QLabel's own
        `minimumSizeHint` is one line tall however long its text is. Without
        this override the Traffic window's minimum stayed at a height its own
        device legend could not fit in — reflow solved the roomy case and left
        the smallest one exactly as broken."""
        hint = super().minimumSizeHint()
        width = self.width()
        if width > 0:
            needed = self.heightForWidth(width)
            if needed > 0:
                return QSize(hint.width(), max(hint.height(), needed))
        return hint

    def resizeEvent(self, event) -> None:      # noqa: N802 (Qt's own name)
        super().resizeEvent(event)
        self._claim_height()

    def setText(self, text: str) -> None:      # noqa: N802 (Qt's own name)
        super().setText(text)
        # A LONGER STRING IS A TALLER LABEL, and this one's text changes once
        # a second: the device legend grows a row the moment a second device
        # connects, which is precisely when the old code ran out of height.
        self._claim_height()

# ═══════════════════════════ SETTLE PARAMETERS ═══════════════════════════
# Wrapped text makes height depend on width, which makes the measurement
# circular: measure at a candidate size, grow, measure again. It settles in
# two or three passes; the cap only stops a pathological layout from spinning.
SETTLE_ROUNDS = 6


# ═══════════════════════════ THE MEASUREMENT ═══════════════════════════
def content_widget(window: QWidget) -> QWidget:
    """The widget whose layout holds the window's column. A QMainWindow keeps
    it one level down, behind `centralWidget()`; a dialog IS it."""
    central = getattr(window, "centralWidget", None)
    return (central() if callable(central) and central() is not None else window)


def required_size(window: QWidget) -> QSize:
    """What this window needs RIGHT NOW, at its current width — the honest
    answer, with `heightForWidth` asked wherever the layout can answer it."""
    hint = window.minimumSizeHint()
    content = content_widget(window)
    column = content.layout()
    height = hint.height()
    if column is not None and column.hasHeightForWidth():
        chrome = max(0, window.height() - content.height())
        height = max(height, column.heightForWidth(content.width()) + chrome)
    return QSize(hint.width(), height)


def settle_minimum(window: QWidget, floor: QSize, keep: QSize | None = None) -> QSize:
    """Declare the minimum `window` needs for the content it holds now, never
    below `floor` (the window's own measured-strings estimate).

    `keep` is the size never to shrink below — pass the owner's current window
    size at runtime so a re-measure cannot pull his window smaller, and an
    empty size at construction. Returns the declared minimum.
    """
    keep = window.size() if keep is None else keep
    size = QSize(floor)
    for _ in range(SETTLE_ROUNDS):
        window.setMinimumSize(size)
        window.resize(size)
        layout = window.layout()
        if layout is not None:
            layout.activate()
        needs = required_size(window)
        grown = QSize(max(size.width(), needs.width()),
                      max(size.height(), needs.height()))
        if grown == size:
            break
        size = grown
    window.setMinimumSize(size)
    if not (window.isMaximized() or window.isFullScreen()):
        window.resize(max(keep.width(), size.width()),
                      max(keep.height(), size.height()))
    return size


# ═══════════════════════════ AND ON THE SCREEN ═══════════════════════════
def clamp_to_screen(window: QWidget) -> None:
    """Pull a window back inside the screen it opened on.

    Qt positions a child window from the size it had BEFORE the show, and
    `settle_minimum` then grows it where it stands — so the growth all happens
    on the bottom and right edges, and a dialog opened from a parent near the
    top of the display ends with its own top edge above the desktop (owner
    report 2026-08-12: the Settings window's first card was cut off).

    `availableGeometry`, not `geometry` — the taskbar is not screen the user
    can read a card in. `frameGeometry`, not `geometry` — the title bar is part
    of what must stay reachable, and it is exactly the part that goes missing.

    THE ORDER OF THE TWO CLAMPS IS THE WHOLE CARE. A window taller than the
    screen cannot satisfy both edges, and the inner `max` decides which one
    wins: the TOP-LEFT, because that is where the title bar and the first
    card are. Pushing the bottom edge into view on such a window would post
    its top off the top — the very defect this exists to fix, in a mirror.

    AND THE SCREEN IS FOUND BY POINT, never by `QWidget.screen()`. That call
    is the obvious one and it CRASHES the Qt audit — a hard access violation a
    few windows later, reported inside whatever unrelated native call happened
    to run next (`BaseCapture.output_count()`, in the run that found it). The
    binding hands back a QScreen that Python then owns, and the second window
    to ask leaves Qt holding a dangling one. `QGuiApplication.screenAt` asks
    the question this function actually means anyway — which display is this
    window ON — and returns a screen the application keeps.
    """
    geo = window.frameGeometry()
    screen = (QGuiApplication.screenAt(geo.center())
              or QGuiApplication.primaryScreen())
    if screen is None:                       # a headless run has neither
        return
    avail = screen.availableGeometry()
    x = min(max(geo.x(), avail.x()),
            max(avail.x(), avail.x() + avail.width() - geo.width()))
    y = min(max(geo.y(), avail.y()),
            max(avail.y(), avail.y() + avail.height() - geo.height()))
    window.move(x, y)
