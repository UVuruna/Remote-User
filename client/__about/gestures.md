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
- [Controls](controls.md) — `inputOff()` (a primary tap on the stream
  switches keyboard AND mic OFF by itself — owner 2026-08-04, reversing the
  old keep-focus rule), `scheduleViewport()`

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
## Pinch works in layout focus too (owner 2026-08-04)
Two fingers pinch in EVERY mode. Layout focus used to return early on the
second pointer; now it only changes where the zoom bottoms out: the pinch
scale is clamped to `[viewHome.scale, viewHome.scale * ZOOM_MAX]` instead of
`[1, ZOOM_MAX]`, so maximum zoom-out is exactly the layout's own framing
(the region fitted to the screen) and everything above it behaves as on the
desktop. Panning is bounded by `clampView()` to the region rect — see
[Render](render.md).

## Font-zoom staircase (owner 2026-08-05, layout focus ONLY)

Pinching out PAST the fitted view no longer dead-ends: the finger position is
mapped to steps (`FONT_ZOOM_STEP` = 1.2× pinch per step, `FONT_ZOOM_MAX` cap)
and each step below the floor sends `chord ctrl+minus` — the layout window's
own content shrinks, so an article wider than the region becomes fully
visible. Pinching back in undoes the applied steps with `ctrl+plus` (the
`=`/`+` key). Steps already applied are tracked per layout in `fontZoomByLayout`
([State](state.md); indices shift on `layout_remove`). The effect is whatever
the focused app does with Ctrl+-/= — browsers and editors scale, Explorer
cycles its view modes, image viewers may ignore it (owner accepted). The
desktop pinch path is untouched (`viewLocked()` gates the whole branch).

### One pinch, one side (owner 2026-08-06)

The fitted view with the content at 100% is a **wall**, not a point on one
continuous scale — a single pinch may only travel on the side it started on:

```
                     WALL
   font staircase      ║      visual zoom
  <-----------------   ║   ----------------->
  text 40% ... 100%    ║   1x ........... MAX
```

- started zoomed in (`view.scale` > fitted) → `side = "zoom"`: closing the
  fingers stops at the fitted view, the content is never touched;
- started with the content shrunk (`fontZoomSteps() > 0`) → `side = "font"`:
  the view stays at the fitted framing and spreading walks the content back up
  to exactly 100%, then stops;
- started ON the wall → `side = null` until the fingers travel
  `PINCH_SIDE_DEADZONE` (0.25 steps) in one direction: spread commits to
  `"zoom"`, close commits to `"font"`. Nothing moves inside the deadzone, so
  jitter cannot pick the mode.

The side is decided once, in `beginPinch()`, and holds for the whole gesture —
crossing therefore costs a finger lift. Rationale: with the two modes joined
into one slide, the state the owner wants most often — content at exactly
100% — was nearly impossible to land on, since the same finger motion sailed
straight through it.

## Input switchers auto-OFF (owner 2026-08-04)
The primary `pointerdown` on the canvas calls `inputOff()` — tapping the
stream is the natural "done typing/dictating", so the keyboard and mic
switchers turn OFF without a manual toggle. (The old rule was the opposite —
`preventDefault` to keep the field focused; the owner reversed it.)

## Offset system removed (owner 2026-08-02)
The cursor-offset system (handedness diagonal, finger calibration, reserved
edge margins) is GONE — the pointer sits exactly under the finger, the image
aspect-fits the FULL canvas, and a focused layout touches all four screen
edges. Any offset/margin description in this doc's diagrams predating
2026-08-02 is historical.
