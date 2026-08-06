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

## Connections

### Uses
- Nothing project-internal (leaf module) — only `PySide6.QtCore.QSize` and
  `PySide6.QtWidgets.QWidget`

### Used by
- [Main Window](main_window.md) — `_settle_minimum()`, re-run on every content
  change and on `showEvent`
- [Controls Editor](controls_editor.md) — once, on first show
- [Traffic Window](traffic_window.md) — once, on first show

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

## Guarded by

`tests/test_layout_audit_qt.py`, which since the same day checks **OVERLAP**
(no two cells of one layout may intersect — nothing had ever checked position,
only size) and measures with the **real platform fonts** instead of the
offscreen substitutes that hid the defect.
