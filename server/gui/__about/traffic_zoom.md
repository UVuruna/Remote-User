# Traffic Zoom

**Module:** [Traffic Zoom (module)](../traffic_zoom.py) ·
**Folder:** [gui](../___gui.md) · **Flow:** [traffic_zoom](../__flow/traffic_zoom.md)

## Purpose

The Traffic chart's TIME WINDOW as pure arithmetic (owner requests
2026-08-15, T104 + T105): the FULL span the picker selected and the VIEW
inside it that the plot shows. No Qt. Both the chart (pixels → seconds) and
the window (what to READ for a zoomed file-backed span) ask this one object,
so the two can never disagree about what is being looked at.

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
`ZOOM_FACTOR = 2`, `DRAG_MIN_PX = 6`.

## Gate

`tests/test_traffic_zoom.py` — the view never leaves the span, never
narrows past the floor, keeps its anchor, survives a sliding live span, and
a click is not a drag; each proven by planting its own defect.
