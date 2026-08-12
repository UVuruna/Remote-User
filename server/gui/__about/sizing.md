# Sizing

**Script:** [Sizing (script)](../sizing.py) ·
**Flow:** [diagram](../__flow/sizing.md)

## Purpose

How a window declares the minimum size it truly needs — one implementation for
every window in the app (THE STRUCTURE LAW: the same settle loop had been
copied into three files, and the same lie was in all three copies).

**The lie** (owner's screenshots, 2026-08-06 — and the reason the first fix of
that day did not fix it): Qt's `minimumSizeHint()` quotes a WRAPPING label at
the height of ONE line. The main window's QR card holds two of them — the
pairing URL and the four-line Tailscale guidance — so the column's "minimum"
came out 48 px short of what it needs at its real width. And **a layout that is
short of space does not clip, it OVERLAPS**: every widget still reports its
full size while the link is painted straight across the QR code. That is how a
guard measuring sizes reported PASS over a window the owner had photographed
twice.

Measured on his own machine, at his real 125% scaling: hint 835, truth 883, and
the QR card handed 332 px against a minimum of 348.

**The truth** is `heightForWidth`: at THIS width, how tall must this column be?

Two further rules learned the same day and encoded here:

- **Measure while SHOWN.** A hidden widget has no real metrics, and a button
  `show()`n on a hidden parent counts for nothing — 43 px of update button, in
  the main window's case.
- **Measure with the REAL font.** The theme reaches a dialog through its
  parent's stylesheet, and Qt resolves QSS fonts only when a widget is
  polished, which happens on show.

## …and on the screen (owner report 2026-08-12)

A window that is the right SIZE is still unreadable when part of it is off the
display, and the settle above is exactly what puts it there. Qt places a child
window from the size it has BEFORE the show; the settle then GROWS it where it
stands, so all the growth lands on the bottom and right edges. Open Settings
from a parent sitting high on the screen and the grown dialog's own top edge —
title bar and first card — ends up above the desktop. That is the screenshot he
sent.

`clamp_to_screen(window)` pulls it back, and is called at the point each
window's geometry is FINAL (the second-pass `_resettle`, or the settle in
`showEvent` for the two windows that have no second pass). Three details are
load-bearing:

- **`availableGeometry`, not `geometry`** — the taskbar is not screen anybody
  can read a card in.
- **`frameGeometry`, not `geometry`** — the title bar is part of what must stay
  reachable, and it is precisely the part that goes missing.
- **The TOP-LEFT wins.** A window taller than the screen cannot satisfy both
  edges; the inner `max` decides, and it decides for the corner where the title
  bar and the first card are. Forcing the bottom edge into view on such a
  window would post its top off the top — the same defect in a mirror.

**Never `QWidget.screen()`.** It is the obvious call and it CRASHES the Qt
audit: a hard access violation a few windows later, reported inside whatever
unrelated native call ran next (`BaseCapture.output_count()`, in the run that
found it — which is why the traceback pointed at monitor enumeration and not at
this file). The binding hands back a QScreen that Python then owns, and the
second window to ask leaves Qt holding a dangling one. `QGuiApplication
.screenAt(centre)` asks the question this function actually means — which
display is this window ON — and returns a screen the application keeps.

## Connections

### Uses
- Nothing project-internal (leaf module) — only `PySide6.QtCore.QSize`,
  `PySide6.QtGui.QGuiApplication` and `PySide6.QtWidgets.QWidget`

### Used by
- [Main Window](main_window.md) — `_settle_minimum()`, re-run on every content
  change and on `showEvent`. Not clamped: it is the window the OWNER placed,
  and moving it under him is a different kind of surprise
- [Controls Editor](controls_editor.md) — settle + `clamp_to_screen`, on first show
- [Traffic Window](traffic_window.md) — settle + `clamp_to_screen`, on first show
- [Settings Window](settings_window.md) — settle on show, then `_resettle` +
  `clamp_to_screen` once the real geometry is in place (and on every later
  content change)

## Contents

- `SETTLE_ROUNDS` — wrapped text makes height depend on width, which makes the
  measurement circular: measure at a candidate size, grow, measure again. It
  settles in two or three passes; the cap only stops a pathological layout
  from spinning
- `content_widget(window)` — the widget whose layout holds the column
  (`centralWidget()` for a `QMainWindow`, the window itself for a dialog)
- `required_size(window)` — what the window needs at its CURRENT width, with
  `heightForWidth` asked wherever the layout can answer it
- `settle_minimum(window, floor, keep)` — declare it. `floor` is the window's
  own measured-strings estimate (`_computed_minimum()`), `keep` the size never
  to shrink below — the owner's current window size at runtime, an empty size
  at construction. A maximized or full-screen window is never resized
- `clamp_to_screen(window)` — and then put it back ON the screen it opened on
  (see above). Idempotent, and a no-op on a window that already fits

## Guarded by

`tests/test_layout_audit_qt.py`, which since the same day checks **OVERLAP**
(no two cells of one layout may intersect — nothing had ever checked position,
only size) and measures with the **real platform fonts** instead of the
offscreen substitutes that hid the defect.
