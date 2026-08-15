# Traffic Zoom — Flow

**About:** [description](../__about/traffic_zoom.md)

```
picker / refresh ──► view.set_full(full_start, full_end)
                        ├─ was whole  → view := full
                        └─ was zoomed → view clamped inside full

button + / wheel up ─► zoom_in(anchor)  ─┐
button − / wheel dn ─► zoom_out(anchor) ─┼─► _zoom_by(factor, anchor)
                                          │     new_span := clamp(cur·factor, MIN_SPAN_S..full)
                                          │     keep anchor's FRACTION → start/end → _clamp
drag release ────────► set_view(t0, t1)   │     edges clamped to full, widened to MIN_SPAN_S
Reset ───────────────► reset()            ┘

changed? ──► TrafficChart._view_changed ──► zoomed ──► TrafficWindow._on_zoomed
                                                         └─ file-backed: re-read [start, end]
                                                            under key "kind|start-end"
```
