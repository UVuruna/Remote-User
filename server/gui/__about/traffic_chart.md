# Traffic Chart

**Module:** [Traffic Chart (module)](../traffic_chart.py) ·
**Folder:** [gui](../___gui.md) · **Flow:** [traffic_chart](../__flow/traffic_chart.md)

## Purpose

The Traffic window's PICTURE: axes, the grey "nobody connected" band, the two
series (PC → phone, phone → PC, coloured per device once this PC has seen
more than one), the faint peak hairline on downsampled spans, the hover
crosshair with its card — and, since 2026-08-15 (owner requests T104–T106),
the **zoom**: a mouse drag draws a rectangle over the plot and zooms the time
axis to it, the wheel and the window's − / + / Reset step it, and the hover
card names what the encoder was DOING at that second.

Split off [Traffic Window](traffic_window.md) on 2026-08-15 at THE
STRUCTURE LAW's wall, by responsibility: the window owns the numbers, the
picker and the recording footer; this owns the picture. Where the two meet
is one object — [Traffic Zoom](traffic_zoom.md)'s `ViewRange`, held as
`chart.view`: the chart maps pixels through it, the window decides what to
READ for it.

## Key Pieces

- `out_color()` / `in_color()` — FUNCTIONS, read at paint (live theme
  switching); `CHART_MIN`, `HOVER_MARGIN`.
- `_point_from_sample(sample)` — a live per-second `traffic.Sample` as a
  `Point` (avg == max, and the sample's `stream` descriptor carried along).
- `_coalesce(points, target)` — at most one point per pixel; the device AND
  the stream descriptor of the last ACTIVE point win a merged pixel and
  carry forward across quiet ones (the same rule the disk reader applies —
  `tests/test_traffic_devices.py` holds the two to each other).
- `TrafficChart(QWidget)`:
  - `set_data(points, start, end, label, downsampled, loading)` — `start`/`end`
    is the FULL span the picker selected; `view.set_full` keeps a zoomed view
    inside it, and only points inside the view are drawn (a zoom of a live
    span costs no re-read).
  - `zoom_in()` / `zoom_out()` / `zoom_reset()` — around the hovered second
    when there is one; `zoomed` (Signal) fires whenever the view changed.
  - `mousePressEvent` / `mouseMoveEvent` / `mouseReleaseEvent` — the drag:
    the band is painted the full plot height WHILE the button is held, with
    the seconds it spans written above it; release past `DRAG_MIN_PX` zooms,
    a click zooms nothing. `wheelEvent` zooms toward the mouse.
  - `_paint_hover` — the card: time, both rates (+ peak on downsampled spans),
    who was connected, then (T106) `device: <name>` and
    [Traffic Stream](../../__about/traffic_stream.md)'s `hover_lines` — the
    quality (fps · res · bitrate), the slice (crop → sent size) and the zoom
    step; "stream: not recorded" for a second written before the columns
    existed. Flips sides so it never leaves the widget.

## Design Decisions

- **The zoom is a TIME window; the y-axis follows the visible peak.** Owner
  words: a dragged "square" zooms that section — since the plot's y-axis is
  always scaled to what is visible, zooming the time axis also zooms the
  amplitude of that section, and one axis is one rule.
- **A drag rectangle is visible while it is drawn** — his own phrase
  ("vizuelno se prikazuje dok to radimo" — lang-ok: owner quote); a
  translucent accent band with a dashed edge and the spanned seconds in a
  card above it.
- **A click is not a drag** (`traffic_zoom.DRAG_MIN_PX`) — the crosshair
  hover must never zoom the graph to ten seconds on a twitch.

## Gates

`tests/test_traffic_zoom.py` (fail-closed in `setup/gates.py`): the drag
zooms to the drawn seconds through REAL mouse events, a click zooms nothing,
the rectangle is visible mid-drag (pixels compared), only the view is drawn,
and the hover card names device and stream. `tests/test_traffic_devices.py`
still holds `_coalesce` against the disk reader.
