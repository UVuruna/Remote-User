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
"""

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget

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
