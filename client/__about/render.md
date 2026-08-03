# Render

**Script:** [Render (script)](../render.js) ·
**Flow:** [diagram](../__flow/render.md)

## Purpose

Canvas drawing (view transform, virtual cursor) and the dual-mode frame
pipeline: JPEG two-layer bitmaps (base + zoomed detail) or H.264 via
MediaSource Extensions (MSE). Second of the six client scripts to load (after
[State](state.md)).

## Connections

### Uses
- [State](state.md) — `canvas`, `ctx`, `monitor`, `baseRect`, `view`,
  `baseBitmap`/`detailBitmap`/`detailRegion`, `streamMode`, `cursorPos`
- [Input Geometry](input-geometry.md) — `offsetDistancePx()` used by
  `computeBaseRect()` to size the edge margin

### Used by
- [Controls](controls.md) implicitly (nothing calls into render.js directly
  from there, but `redraw()`/`computeBaseRect()` are triggered by state
  changes controls.js causes, e.g. mode toggles)
- [Gestures](gestures.md) — pinch/pan call `redraw()`, `scheduleViewport()`,
  `drawnRect()`
- [Connection](connection.md) — the `config` message handler calls
  `initMse()`/`teardownMse()`, `computeBaseRect()`, `redraw()`; frame bytes
  arriving over the socket are handed to `onFrame()` (JPEG) or pushed into
  `mseQueue`/`pumpMse()` (H.264)

## Key Functions

- `computeBaseRect()` — fits the monitor image into the canvas minus an
  edge margin (sized by the cursor offset, see [Input Geometry (flow)](../__flow/input-geometry.md))
  so the pointer can reach every PC-screen corner.
- `drawnRect()` — `baseRect` transformed by the current pan/zoom `view`.
- `clampView()` — keeps pan/zoom within bounds; snaps back to identity at
  scale ≤ 1.
- `redraw()` — draws the current frame (video element in H.264 mode, base +
  detail bitmaps in JPEG mode) plus the virtual cursor.
- `drawCursor(D)` — draws a fixed-screen-size arrow at the PC cursor position
  (server-streamed; capture never contains the real pointer).
- `updateViewport()` — sizes the canvas to `visualViewport`, publishes the
  `--kb`/`--vtop` CSS variables (keyboard-aware layout), and runs on every
  resize plus once at load.
- `currentViewport()` / `scheduleViewport()` — JPEG-mode region streaming:
  computes the visible region (with margin) and sends it to the server
  (throttled), so zoomed frames arrive at native sharpness.
- `onFrame(buffer)` — JPEG mode: splits an incoming binary message into its
  4-float region header + JPEG bytes, routes to base or detail bitmap by
  whether the region covers the full frame.
- `initMse(codec)` / `teardownMse()` / `pumpMse()` / `onMseUpdateEnd()` /
  `renderLoop()` — H.264 mode: opens a `MediaSource`, appends arriving fMP4
  chunks in order, keeps playback near the live edge, trims old buffered
  history, and drives a `requestAnimationFrame` loop that calls `redraw()`.

## Design Decisions

- **Two-layer JPEG rendering** — a full-monitor base frame is always drawn
  (so panning/zooming never flashes blank) with a sharp zoomed-region overlay
  on top when scaled up.
- **MSE append failures never freeze silently** — a decode/quota error closes
  the socket; auto-reconnect (see [Connection](connection.md)) brings a fresh
  stream rather than a stuck frozen page.
- **`video` (the offscreen H.264 element) is declared inside this file, after
  `redraw()`'s first reference to it.** Safe because the initial synchronous
  `updateViewport()` call (also in this file) runs while `streamMode` still
  defaults to `"jpeg"`, so `redraw()`'s H.264 branch — the only place `video`
  is read — is never entered before `video` exists. By the time `streamMode`
  can ever become `"h264"` (only via an async `config` message), the whole
  page has finished loading.
## Layouts (Phase F+ step 1)
`applyLayoutView()` implements layout focus client-side: it zooms/translates
the view so `layoutRegion` fills the canvas (minus the same cursor-offset
margin `computeBaseRect` reserves, keeping the region's far edges reachable).
While locked, `clampView()` backs off — the layout transform owns the view —
and `updateViewport` + every stream reset re-apply it. Streaming itself is
untouched: full-frame H.264 stays cheap (ROADMAP measurement), and the JPEG
path narrows through the existing `viewport` region mechanism.

## Offset system removed (owner 2026-08-02)
The cursor-offset system (handedness diagonal, finger calibration, reserved
edge margins) is GONE — the pointer sits exactly under the finger, the image
aspect-fits the FULL canvas, and a focused layout touches all four screen
edges. Any offset/margin description in this doc's diagrams predating
2026-08-02 is historical.

## The locked region is CLIPPED (owner 2026-08-03)
Since a layout can carry its own aspect ratio ([Layouts](layouts.md)), its
region no longer fills the screen — and `redraw()` was still painting the
whole monitor frame, so the desktop behind the layout showed through in the
leftover bars. `redraw()` now clips to the region rect while `viewLocked()`,
leaving the theme background (`#0f172a`) everywhere else. The PC cursor is
clamped to the very same rect in
[Input Geometry](input-geometry.md) (`toRemoteClamped`), so the empty space is
not reachable either: a focused layout is one window, whole — nothing of the
desktop is visible or touchable.

## The keyboard no longer squeezes the picture (owner 2026-08-03)
`updateViewport()` used to size the canvas to the CURRENT viewport, so the
soft keyboard (the shell runs `adjustResize`) shortened the canvas and the
whole picture was re-fitted into it — the layout visibly deformed. The canvas
now keeps the FULL height of the current orientation (`fullView`, remembered
across keyboard openings — the width is the tell: it changes only on rotation)
and is simply lifted by `kbShift` with a CSS transform, so its bottom edge —
the row being typed into — sits right above the keyboard while the top runs
off screen. Touch coordinates add the same shift back in `toCanvasPx`
([State](state.md)).
