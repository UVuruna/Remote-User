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
drag release ────────► set_view(t0, t1, r0, r1)  edges clamped, widened to the floors; r = rate window
zoomed drag ─────────► pan(dt, dy)         │     from the press-time view; clamped to full and 0..y_cap
Reset ───────────────► reset()            ┘

changed? ──► TrafficChart._view_changed ──► zoomed ──► TrafficWindow._on_zoomed
                                                         └─ file-backed: re-read [start, end]
                                                            under key "kind|start-end"
```
