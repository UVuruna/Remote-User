# Traffic Axis — Flow

**About:** [description](../__about/traffic_axis.md)

## One paint of the Y axis

```
TrafficChart.paintEvent
 │
 ├─ peak    := max(1024, every point's out_max / in_max)
 ├─ ticks   := _y_ticks(peak)            1/2/5 x 10^n ladder, scored so the
 │                                       COUNT lands in [4, 5] — not merely
 │                                       the nearest round step
 ├─ axis_max := ticks[-1]
 ├─ unit, div := _axis_unit(axis_max)    ONE unit, read off the TOP gridline
 │                                       (Finding 2, 2026-08-07 — never per
 │                                       tick, or one axis reads in three
 │                                       different units)
 ├─ draw `unit` ONCE, top-left of the plot
 └─ for each tick:  _format_axis_value(tick, div)   → a bare number
```

## One paint of the X axis

```
span := end - start
 │
 ├─ _x_ticks(start, end, X_TICK_COUNT)   evenly spaced moments
 └─ _x_label(t, span)
       span <= 1 h    → %H:%M:%S     seconds matter at 2 minutes
       span <= 24 h   → %H:%M        "Last 10 hours" / "Today" live here
       otherwise      → %b %d        a date matters at four months
```

## Where the numbers come from

```
traffic.METER.history()      ─┐
traffic_history.read_history ─┴→ Point list → TrafficChart._coalesce
                                                      │
                                                      └→ this module: labels
```

Nothing flows back: every function here is pure, takes numbers, returns text
(or a `QColor`), and is called at PAINT time so a theme flip is followed
rather than cached.
