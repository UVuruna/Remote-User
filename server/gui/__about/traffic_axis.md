# Traffic Axis

**Script:** [Traffic Axis (script)](../traffic_axis.py) ·
**Flow:** [diagram](../__flow/traffic_axis.md)

## Purpose

How a byte count and a moment in time become the WORDS on the Traffic chart's
axes — and nothing else.

Split out of [Traffic Window](traffic_window.md) on 2026-08-14 at THE
STRUCTURE LAW's wall, and split by **responsibility** rather than by line
count: everything here is a pure function of numbers to text (plus `_alpha`,
a theme colour at an alpha the QSS cannot express). Nothing here knows there
is a window, a chart, a CSV or a span — `traffic_window.py` owns the widget,
[Traffic History](../../__about/traffic_history.md) owns the file, and this
owns the labels. Which also means every rule below can be checked by calling
it, with no Qt widget built.

## The rules it holds

**One axis, one unit.** The 2026-08-07 independent grade (Finding 2) caught a
single Y axis reading "1.5 kB/s" over "1000 B/s" over "500 B/s" — three
gridlines, three units, because every tick called `human_rate()` on its own
value. `_axis_unit` reads ONE unit off the axis's own top gridline;
`_format_axis_value` labels every tick as a bare number in it, and the unit
is drawn once, top-left of the plot. The unit boundaries are the same ladder
`human_bytes()` uses, so the axis and every other number the window prints
can never disagree about where "kB" starts.

**Round gridlines, 4–5 of them** (the owner's own ask). `_y_ticks` scores
every step on the 1 / 2 / 5 × 10ⁿ ladder by how many gridlines it would
produce and prefers a step that lands the count inside `[Y_TICK_MIN,
Y_TICK_MAX]` over the merely "nearest round number" — the naive single-formula
pick put a real peak of 1024 at exactly 3 lines, one short of the floor,
because 1/2/5 steps are coarse near round-number boundaries.

**Time granularity follows the span.** `_x_label` prints seconds at two
minutes, minutes up to a day, and a date beyond it — a four-month span
labelled `%H:%M:%S` says nothing.

## Connections

### Uses
- [Theme](theme.md) — read at CALL time, never captured at import: a colour
  cached at module level would freeze whichever palette was active when the
  file was first imported and never follow a runtime theme flip

### Used by
- [Traffic Window](traffic_window.md) — the chart's whole axis and hover
  labelling

## Functions
- `human_bytes(n)` / `human_rate(n)`: bytes as the owner reads them
- `_y_ticks(peak, min_ticks, max_ticks)`: the 1/2/5 × 10ⁿ gridline ladder
- `_x_ticks(start, end, count)`: evenly-spaced times across the span
- `_axis_unit(axis_max)` / `_format_axis_value(value, divisor)`: one unit for
  the whole axis, bare numbers under it
- `_x_label(t, span_s)`: the time granularity that span deserves
- `_alpha(hex_color, alpha)`: a theme colour at an alpha QSS cannot give it
