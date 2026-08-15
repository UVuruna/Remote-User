# Traffic Chart — Flow

**About:** [description](../__about/traffic_chart.md)

## One drag (T105)

```
mousePressEvent (left, inside the plot)
 │   _drag_x0 = _drag_x1 = x
 ├─ mouseMoveEvent ── _drag_x1 = x ── update()
 │       └─ paintEvent → _paint_drag: band [x0..x1] × plot height,
 │                        "HH:MM:SS – HH:MM:SS" card once past DRAG_MIN_PX
 └─ mouseReleaseEvent
       ├─ not is_drag(x0, x1)  → nothing (a click)
       └─ is_drag              → t0, t1 := px_to_time(x0 / x1 over the PLOT)
                                  view.set_view(t0, t1)   (clamped, ≥ MIN_SPAN_S)
                                  _view_changed() → start/end := view; zoomed.emit()
                                        └─ TrafficWindow._on_zoomed → re-read for the view
```

## One paint

```
paintEvent
 ├─ plot rect, panel fill, "Reading traffic.csv…" if loading
 ├─ visible := points inside [view.start, view.end]
 ├─ pts := _coalesce(visible, plot width);  peak, y-ticks, x-ticks
 ├─ idle band, the two series (per-device colour once >1 device ever seen)
 ├─ if dragging → _paint_drag
 └─ elif hovering → _paint_hover: nearest point, crosshair, card
        lines: time · PC→phone · phone→PC · who was connected
               · device: <label>            (T106)
               · quality / slice / zoom     (traffic_stream.hover_lines)
```
