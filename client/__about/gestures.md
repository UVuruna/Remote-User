# Gestures

**Script:** [Gestures (script)](../gestures.js) ·
**Flow:** [diagram](../__flow/gestures.md)

## Purpose

Canvas pointer-event handling: pinch-zoom (two fingers, always) and the
single-active-finger gesture dispatch driven by `touchMode`
(move/drag/scroll/pan). Fifth of the six client scripts to load (after
[Controls](controls.md), before [Connection](connection.md) — it needs
everything defined in the first four files).

## Connections

### Uses
- [State](state.md) — `pointers`, `pinch`, `primary`, `touchMode`,
  `cursorPos`, `send`
- [Render](render.md) — `drawnRect()`, `redraw()`, `video`/`streamMode`
  (autoplay unlock on first touch)
- [Input Geometry](input-geometry.md) — `toRemoteMaybeOffset`, `sendCursor`,
  `sampleFinger`, `startScrollInertia`/`cancelScrollInertia`
- [Controls](controls.md) — `keyboardOpen()` (a tap must not blur the
  keyboard field), `scheduleViewport()`

### Used by
- Nothing downstream — this is where raw touch input becomes protocol
  messages sent via `send()` (see [Connection](connection.md) for the socket
  itself)

## Key Functions

- `firstTwoPointers()` / `beginPinch()` — starts a pinch: cancels any active
  drag/move gesture cleanly first (releases a held button, restores the
  cursor), then records the pinch's start distance/scale/focal point.
- `canvas` `pointerdown` handler — ghost-pointer self-heal (a new primary
  pointer wipes all pointer/pinch/primary state — Android WebView
  occasionally loses a `pointerup`), then dispatches by `touchMode`: `drag`
  sends `pointer_down`, `move` sends the steering cursor, `scroll` primes
  momentum tracking.
- `canvas` `pointermove` handler — pinch scaling/panning when 2+ fingers are
  down, otherwise per-mode single-finger tracking (drag/move steer the
  cursor, scroll accumulates tick deltas, pan moves the local view).
- `endPointer(e)` / `pointerup`/`pointercancel` listeners — releases a drag
  (`pointer_up`), starts scroll fling, clears `primary`.

## Design Decisions

- **Nothing on the canvas is a tap** (owner decision 2026-07-26, hardened) —
  every gesture here either steers the cursor or is a toggle mode; clicking
  is only ever the explicit Click/Right buttons in
  [Controls](controls.md). This file enforces that by construction: no
  handler here ever sends `click`.
- **Ghost-pointer self-heal** — every new `isPrimary` `pointerdown` wipes
  `pointers`/`pinch`/`primary` first, because a lost `pointerup`/`pointercancel`
  (a real, live Android WebView bug) used to turn every later tap into a
  phantom pinch until page refresh.
- **Two fingers always pinch**, regardless of `touchMode` — pinch cannot leak
  a click or drag to the PC.
## Layouts (Phase F+ step 1)
An armed layout pick intercepts the primary `pointerdown`: it sends
`layout_pick` with the tapped monitor-normalized point and injects NOTHING.
While the view is locked to a layout region, two fingers do nothing (pinch
disabled — the layout transform owns the view).

## Offset system removed (owner 2026-08-02)
The cursor-offset system (handedness diagonal, finger calibration, reserved
edge margins) is GONE — the pointer sits exactly under the finger, the image
aspect-fits the FULL canvas, and a focused layout touches all four screen
edges. Any offset/margin description in this doc's diagrams predating
2026-08-02 is historical.
