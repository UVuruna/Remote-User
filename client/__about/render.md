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

- `computeBaseRect()` — aspect-fits the monitor image into the FULL canvas,
  centered, no reserved margin (owner 2026-08-02 — the pointer sits under the
  finger, so the image touches all four screen edges).
- `drawnRect()` — `baseRect` transformed by the current pan/zoom `view`.
- `clampView()` — keeps pan/zoom within bounds; snaps back to identity at
  scale ≤ 1.
- `redraw()` — draws the current frame (video element in H.264 mode, base +
  detail bitmaps in JPEG mode) plus the virtual cursor.
- `drawCursor(D)` — draws the PC cursor at its streamed position (capture
  never contains the real pointer), fixed screen size, in the SHAPE the PC is
  really showing — see below.
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
Layout focus is client-side: the view is bound to `layoutRegion`. Streaming
itself is
untouched: full-frame H.264 stays cheap (ROADMAP measurement), and the JPEG
path narrows through the existing `viewport` region mechanism.

## The cursor has the shape the PC's cursor has (owner request 2026-08-09, task 142)

`drawCursor` drew one fixed arrow, so from the tablet a draggable window edge,
a text box, a link and plain background all looked the same — the one job a
cursor has. The server now names the live system cursor
([Cursor Shape](../../server/__about/cursor_shape.md)) as the optional `shape`
field on the `cursor` message, and the silhouettes live in
[Cursor Shapes](cursor-shapes.md) — pure, so its gate runs it whole.

Two things here deliberately did NOT change, and both are load-bearing:

- **The translate.** Every shape's own ORIGIN is its hotspot, so translating
  to the commanded point and drawing the coordinates straight is correct for
  all of them — an arrow still points with its tip, a resize arrow is centred
  on the edge.
- **The white fill + black outline + soft shadow.** That treatment is what
  keeps the pointer legible over a white document AND a dark editor; every new
  shape inherits it rather than re-deciding it. All polygons of a shape go
  into ONE path, filled nonzero (so a reverse-wound polygon is a hole, e.g.
  the ring of `no`) and stroked once.

The name is held in `cursorShapeName`, beside `cursorPos` and not on it: the
finger writes that object itself while steering
([Gestures](gestures.md) / [Input Geometry](input-geometry.md) move the
pointer optimistically, before the PC answers), so carrying the shape on it
would flick back to an arrow on every touch — precisely when he is reaching
for the edge he wants to grab. An unknown or absent name draws the exact arrow
this page always drew.

## The cursor-offset system is gone (owner 2026-08-02, remnants finished 2026-08-07)
The pointer sits exactly under the finger, the image aspect-fits the FULL
canvas, and a focused layout touches all four screen edges — no handedness
diagonal, no finger calibration, no reserved edge margin. Removed for good on
2026-08-07, along with `config.hand` and the `calibrate` action.

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

## One zoom model for both modes (owner 2026-08-04)
Layout focus is no longer a hard view lock — "there is no reason for zoom to
be missing there". Three small functions carry it:

- `viewBounds()` — the rect the view may ever show, in unscaled base-canvas
  px: `baseRect` on the desktop, the `layoutRegion` sub-rect in layout focus.
- `computeViewHome()` → `viewHome` — the MAXIMUM ZOOM-OUT transform:
  `{scale: 1, tx: 0, ty: 0}` on the desktop; in layout focus the bounds rect
  fitted into the full canvas and ANCHORED along the free axis by the focused
  layout's own `pos` ([View Anchor](view-anchor.md) `fitAnchorView`, fed with
  `layoutAnchorPos()` from [State](state.md) — owner decree 2026-08-09: the
  Move handle acts on the phone's letterbox, the server always centres the
  windows). Recomputed on every `updateViewport()` (rotation, keyboard) so
  the framing survives a resize, and re-anchored by the `resetViewHome()`
  every `layout_state` triggers.
- `resetViewHome()` — snap back out; called on a stream reset and on every
  `layout_state` (a layout switch always starts fully zoomed out).

`clampView()` then works off `viewHome` in both modes instead of the literal
`1`: below `viewHome.scale` the view snaps back to home exactly, above it the
scale is capped at `viewHome.scale * ZOOM_MAX` and the translation is bounded
so the drawn bounds rect always covers where that rect sits at home — no
letterbox bar, and in layout focus no neighbouring desktop, can creep in at an
edge. With `viewHome = {1, 0, 0}` the bounds reduce to the previous desktop
formula unchanged.

## The keyboard no longer squeezes the picture (owner 2026-08-03)
`updateViewport()` used to size the canvas to the CURRENT viewport, so the
soft keyboard (the shell runs `adjustResize`) shortened the canvas and the
whole picture was re-fitted into it — the layout visibly deformed. The canvas
now keeps the FULL height of the current orientation (`fullView`, remembered
across keyboard openings — the width is the tell: it changes only on rotation).

It is never lifted by the KEYBOARD'S HEIGHT either (owner 2026-08-07,
withdrawing his own 2026-08-03 request after living with it): a keyboard-sized
lift carried the very line he was typing off the TOP of the screen, because
the row he types into is almost never at the bottom of the PC's picture —
*"izbaci tekst koji se kuca iz vidokruga"*. What it IS lifted by is the
caret's own **shortfall** — see [Caret](caret.md) — which is 0 most of the
time and lands in `kbShift` ([State](state.md)) so every touch keeps mapping
onto the picture it can see. `--kb` is unchanged: the phone's own controls
still lift clear of the keys.

## The keyboard-height pipe, and why it lives beside `updateViewport`

`window.__imeHeight(cssPx)` is the shell's only way in ([Insets](../../android/__about/Insets.md)).
Under edge-to-edge on targetSdk 35 Android stops resizing the window for the
IME, so the page's own `innerHeight - visualViewport.height` returns **0 with
the keyboard wide open** — five rounds of caret work were handed that zero and
correctly returned a rise of 0. `updateViewport()` takes the LARGER of the two
readings, because a zero from either must never beat a real measurement.

The receiver sits **immediately after `updateViewport()`**, deliberately. It
used to live at the bottom of this file among the MSE starve-recovery code, and
a revert of that streaming block took it with it as collateral — the commit
message never mentioned the keyboard, nothing in the repo calls a `window.*`
global, and `imeHeight` silently stayed 0 for another release. Physical
adjacency to code with a different lifetime is what cost that, and
[the gate](../../tests/test_caret_lift.py) now asserts the receiver's position
between `updateViewport` and `initMse`.

## Order inside `updateViewport()` (2026-08-09)

The caret rise is computed **last**, after `computeBaseRect()`,
`computeViewHome()` and `clampView()`: the rule is measured against the rect
the picture is really drawn into, so the canvas must already be resized and the
home transform re-fitted, or a rotation would grade the caret against the
previous orientation's picture. `drawnRect()` returns the **un-risen** rect —
`redraw()` subtracts `caretRise` from its own copy at draw time — so feeding it
back in cannot compound.

`reportKeyboard()` then writes one `client_log` line per keyboard **open** and
one per **close** — never one per page load, which is what the previous attempt
did and why the evidence was always missing. It is debounced by
`KB_REPORT_SETTLE_MS` ([State](state.md) → Tunables): Android animates the IME
in and fires the inset listener on every frame of it, so an un-settled report
would bury the answer under twenty half-open keyboards and print a rise
computed against a keyboard that was still moving. A close earns a line because
`ime=0 browser=0` is only observable if a zero can reach the log at all.

```
[keyboard] ime=<px> browser=<px> caret=<y|unknown> pic=<y>+<h> kbTop=<px> rise=<px> dpr=<n>
```

It discriminates the ways this can still be wrong: `ime=0 browser=0` is the
shell not reaching the page, `caret=unknown` is the PC unable to see the caret
in that app, and `caret=0.951 rise=0` is arithmetic. A real rise is
hand-checkable against `pic` and `kbTop` on the same line.
