# Zoom Crop

**Script:** [Zoom Crop (script)](../zoom-crop.js) ·
**Folder:** [client](../___client.md)

## Purpose

The two rules the phone's PINCH needs before it may ask the PC for a smaller,
sharper picture: the **floor** a crop may never widen past, and the **settle**
that keeps one region change per finished gesture. Pure — no DOM, no socket —
so `tests/test_zoom_crop.py` runs it whole (the [View Anchor](view-anchor.md)
pattern). Loads right before [Render](render.md), which measures the canvas
and runs it.

## Why it exists (owner report 2026-08-14, T76)

In translation: *"why is downscaling done even when the picture is zoomed —
when we zoom on the phone we are enlarging that downscaled resolution so the
picture is blurry, even though the whole screen does not need to be sent then
either, because we are in a slice just like in layout mode"*. He is right that
he asked for this at the very start.

The machinery had existed WHOLE since 2026-08-12 — the encoder crop, the
`stream_region` the page maps the video onto, the decode ceiling sized by the
crop, the one choke point that ends a mismatched session — and it was only
ever fed by a **focused layout**. The `viewport` message the pinch has always
sent was discarded outright in H.264 mode, and the project's own docs stated
that as a deliberate rule ("JPEG mode only"), which is what made the gap
unfindable for a whole round. So a zoom magnified pixels that had already been
through the panel-ceiling downscale, and asked the PC for nothing.

Nothing new was invented for the fix: the settled rect feeds the SAME path,
through `layout_api.stream_crop` on the server.

## Key Functions

- `zoomFloorRect(visible, floor, margin)` — the visible rect widened by the
  margin and then held to its floor, **in that order**, so the margin can never
  be what widens the crop past a layout. On the desktop the floor is the whole
  frame; in layout focus it is [State](state.md)'s `layoutRegion`. An empty
  intersection returns the floor itself — a rect that has drifted off the
  layout (a stale one from the layout just left) falls back to what the layout
  frames, never to nothing.
- `zoomRectDelta(a, b)` — how far one rect moved from another, as the largest
  edge move. A missing side is a whole change: the full frame is a different
  picture, not a nearby one.
- `zoomSettleStep(prev, ev)` — one tick of the settle watcher.
  `prev = {sample, changedAt}`, `ev = {now, pointersDown, rect, settleMs}`,
  and `settled` is true only on the tick where the hand has been off the glass
  AND the transform unmoved for the whole threshold.

## The rules

- **The layout's region is the FLOOR, never the ceiling.** Zooming in narrows
  further; zooming back out lands on exactly the layout's own crop and no
  wider. A wider crop would stream windows the layout exists to keep off his
  screen, and would break the model that makes `layout_state`'s region
  trustworthy at all. The server clamps it a second time, independently
  ([Layout API](../../server/__about/layout_api.md) `stream_crop`) — the page
  is not trusted with a promise about what the PC shows.
- **The gesture is WATCHED, never timed.** Every region change rebuilds this
  client's ffmpeg and the picture blinks once, so the rect goes out only when
  the gesture has stopped. That is an OBSERVATION and not the estimate
  constraint 15 forbids: constraint 15 is about guessing how long *another
  program* needs, and this measures the owner's own hand — a pointer still
  down, or a transform that moved since the last sample, is a fact this page
  can read. `ZOOM_SETTLE_MS` (280 ms, sampled every 60 — [State](state.md)) is
  the give-up point of that observation; a gesture that never stops never
  sends, however long it runs. A pause mid-pinch with the finger still down is
  deliberately NOT a settle, and only the pointer state can say so, because
  the rect is as still then as it will be after the lift.
- **A drift too small to see is not worth a blink.** Under `ZOOM_MIN_DELTA`
  (0.02) nothing reaches the wire; the server holds the same threshold, so the
  rule survives an older or a newer page.

## Gate

`tests/test_zoom_crop.py` (fail-closed in `setup/gates.py`, 0b13/6) drives
both functions whole in node — a full pinch tick by tick, including the pause
mid-gesture — and ends every geometric check at the PIXELS the real
`H264Session` would encode, never at a variable's value (constraint 13's
lesson, and [View Anchor](view-anchor.md)'s).
