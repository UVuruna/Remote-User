# Zoom Crop

**Script:** [Zoom Crop (script)](../zoom-crop.js) ·
**Folder:** [client](../___client.md)

## Purpose

The two rules the phone's PINCH needs before it may ask the PC for a sharper
picture: the **floor** the reported rect may never widen past, and the
**settle** that keeps one report per finished gesture. Pure — no DOM, no
socket — so `tests/test_zoom_crop.py` runs it whole (the
[View Anchor](view-anchor.md) pattern). Loads right before
[Render](render.md), which measures the canvas and runs it.

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
unfindable for a whole round.

## This module's job changed TWICE in one day — corrected in place

**Round 2** (built and shipped 2026-08-14, morning) made the settled rect a
CROP: it fed `layout_api.stream_crop`, narrowing the encoder's crop to the
intersection of the layout's region and the pinch rect. It was condemned live
within hours — no base layer under a crop-only stream showed the canvas
background during a pan, a settled PAN rebuilt ffmpeg (a 1–2 s stall) for
every step with no throttle, and a decoder error caught in that storm
reconnected with the zoom erased entirely.

**Round 3** (the owner's own design, same day) is what ships now: the encoder
crop stays FIXED at the focused layout's region (or the full frame at the
desktop) — nothing this module reports ever narrows it again. What the
settled rect drives instead is a **resolution step**
(`layout_api.zoom_step`, server-side): a zoomed phone is looking at only
`1/step` of the picture per axis, so the panel is no longer the honest
ceiling on encoded pixels, and the step raises `H264Session._scale_size`'s
cap toward native. A pan that stays inside the same step rebuilds nothing —
only a step CROSSING resets the session, which is what removes round 2's
per-pan stall and its dependence on a base layer that was never built.


**Round 5 (owner report 2026-08-18 — his tablet held in PORTRAIT, and the
picture at ~2x "not even a quarter of the resolution the desktop delivers",
which is exactly what it was: 1922x1080 magnified).** The rounds-3/4 rule
above — "a zoomed phone is looking at only `1/step` of the picture per axis",
so the step was the LARGER visible fraction of the rect, quantized — is TRUE
of a picture that fills the screen and FALSE of a letterboxed one: a 16:9
monitor on a portrait panel stands 1200x675 in a 1200x1920 canvas, so its
full height is in view up to 2.84x and the height fraction reads 1.0 —
the step stayed 1 through every zoom he ever used (his log: not one `zoom`
session between 19:35 and 19:41 while he zoomed and photographed). What
blur IS is one number: panel pixels lit per encoded pixel, and a fraction of
the picture cannot say it. So the settled send now carries **`drawn {w, h}`**
— the canvas px the WHOLE picture is drawn at (canvas px are panel px) — and
`zoom_step` is the smallest power of two that brings the encoded picture up
to that drawn size: `ratio = drawn base / panel`, long side to long and short
to short — the mirror of `_scale_size`, so the two cancel exactly. On his
tablet: 1.5x → step 1 (ratio 0.94, still one-to-one), 2.07x → step 2 (=
native — the 4K his desktop delivers), 6x → step 4 (the same wall). The
`ZOOM_MIN_DELTA` guard on both sides now also asks whether the drawn size
moved (`zoomDrawnMoved`, 2 % slack), because a 1.2x pinch on a landscape
phone keeps its margin-widened rect at the full frame — the rect guard alone
swallowed it — and yet lights every encoded pixel 1.2x. A page that sends no
`drawn` (older) is decided by the fraction rule, byte for byte. The sentence
above is kept because it is the evidence: it read as a decision, and a rule
that measures a FRACTION was never asked what a fraction of a letterboxed
picture means. Gate: section 13 of `tests/test_zoom_crop.py`, his exact
numbers, each check proven by planting its own defect.

The two rules below — the floor and the settle — **survive unchanged in
shape**; only their PURPOSE changed. The rect this module produces is no
longer a crop request — it is a MEASUREMENT of what the phone is really
looking at, which the server turns into a step. The floor still stops that
measurement from ever claiming the phone watches past the layout's own
region (a false measurement would earn a resolution step the region never
justifies); the settle still stops a mid-gesture rect from costing a blink,
because a step crossing still rebuilds ffmpeg exactly as a crop change did.

## Key Functions

- `zoomFloorRect(visible, floor, margin)` — the visible rect widened by the
  margin and then held to its floor, **in that order**, so the margin can never
  be what widens the measurement past a layout. On the desktop the floor is
  the whole frame; in layout focus it is [State](state.md)'s `layoutRegion`.
  An empty intersection returns the floor itself — a rect that has drifted off
  the layout (a stale one from the layout just left) falls back to what the
  layout frames, never to nothing.
- `zoomRectDelta(a, b)` — how far one rect moved from another, as the largest
  edge move. A missing side is a whole change: the full frame is a different
  picture, not a nearby one.
- `zoomSettleStep(prev, ev)` — one tick of the settle watcher.
  `prev = {sample, changedAt}`, `ev = {now, pointersDown, rect, settleMs}`,
  and `settled` is true only on the tick where the hand has been off the glass
  AND the transform unmoved for the whole threshold.

## The rules

- **The layout's region is the FLOOR the measurement may never widen past.**
  Zooming in narrows the reported rect further; zooming back out reports
  exactly the layout's own region and no wider. A wider report would claim
  the phone is watching windows the layout exists to keep off his screen, and
  would earn a resolution step the region never justifies. The server holds
  the same floor independently
  ([Layout API](../../server/__about/layout_api.md) `zoom_step`) — the page
  is not trusted with a promise about what the PC encodes.
- **The gesture is WATCHED, never timed.** A step crossing rebuilds this
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
`H264Session` would encode (round 3: the step's effect on `_scale_size`,
never a narrower crop), never at a variable's value (constraint 13's lesson,
and [View Anchor](view-anchor.md)'s).
