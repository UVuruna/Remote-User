# Traffic Zoom

**Module:** [Traffic Zoom (module)](../traffic_zoom.py) ·
**Folder:** [gui](../___gui.md) · **Flow:** [traffic_zoom](../__flow/traffic_zoom.md)

## Purpose

The Traffic chart's TIME WINDOW as pure arithmetic (owner requests
2026-08-15, T104 + T105): the FULL span the picker selected and the VIEW
inside it that the plot shows. No Qt. Both the chart (pixels → seconds) and
the window (what to READ for a zoomed file-backed span) ask this one object,
so the two can never disagree about what is being looked at.

## The zoom is 2D (owner decision 2026-08-15, option B)

His words: "može pravi 2D zoom — na taj način neće uvek Y skala biti od MIN
do MAX već da vidimo detaljnije krivu" (lang-ok: owner quote), and of the
three ways to tell a rectangle from a move he chose **B**: *while zoomed the
drag only MOVES the slice; in the full view the drag only ZOOMS.* So:

- `y_lo` / `y_hi` — the rate window; `None` = automatic (0 .. the visible
  peak's top gridline, the old picture to the pixel). A rectangle with
  height (≥ `DRAG_MIN_PX` tall) sets it; a flat one leaves Y automatic.
- `y_cap` — the ceiling a pan or a zoom-out may reach: the WHOLE span's own
  top gridline, written by the chart at every paint (only the paint knows
  the ladder).
- `pan(dt, dy)` — shifts the view, clamped inside the full span and inside
  `0..y_cap`; the chart calls it from the press-time view on every mouse
  move (never incrementally — an incremental pan drifts) and re-reads a
  file-backed span ONCE, on release.
- `zoom_in_at` / `zoom_out_at(anchor, y_anchor)` — the wheel and − / +
  scale the rate window too, around the mouse or its middle, but only once a
  rectangle has set it: an automatic Y stays automatic.
- `reset()` — full span AND automatic Y.
- `px_to_rate(y, top, bottom, y_lo, y_hi)` — the inverse of `y_of`.

## Key Functions

- `ViewRange.set_full(start, end)` — a new full span. A view that WAS the
  whole span follows it; a zoomed view is kept and clamped inside it (the
  live "Last hour" span slides every second and must not drop his zoom).
- `zoom_in(anchor)` / `zoom_out(anchor)` — halve / double around the anchor
  (unix time; the middle when None), keeping the anchor at the same fraction
  of the view so the second under the mouse stays put; `reset()`.
- `set_view(start, end)` — the drawn rectangle: edges clamped to the full
  span FIRST (a drag past the plot means "to the end", never "the whole
  span"), then widened to `MIN_SPAN_S`.
- `px_to_time(x, plot_left, plot_right, start, end)` — the inverse of the
  chart's `x_of`; `is_drag(x0, x1)` — the `DRAG_MIN_PX` rule.

## Constants

`MIN_SPAN_S = 10` (a narrower view holds too few seconds to draw),
`MIN_Y_SPAN = 64` B/s (narrower is a line, not a curve), `ZOOM_FACTOR = 2`,
`DRAG_MIN_PX = 6`.

## Gate

`tests/test_traffic_zoom.py` — the view never leaves the span, never
narrows past the floor, keeps its anchor, survives a sliding live span, and
a click is not a drag; each proven by planting its own defect.
