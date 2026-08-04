# State

**Script:** [State (script)](../state.js)

## Purpose

Tunables (zoom limits, scroll fling constants, cursor-offset bounds, timing
constants), the shared mutable state every other client script reads and
writes (canvas/context refs, connection/view/gesture state, calibration
state), and the three primitives everything else is built on: `setStatus`
(status pill), `toCanvasPx` (pointer event → canvas-px point) and `send`
(JSON WebSocket send with the "dead socket → visible reconnect" fallback).

Loads FIRST of the six client scripts (see [Client (folder)](../___client.md))
— every other script assumes these globals already exist.

## Connections

### Uses
- Nothing (no dependencies — this is the base of the load order)

### Used by
- [Render](render.md), [Input Geometry](input-geometry.md), [Controls](controls.md),
  [Gestures](gestures.md), [Connection](connection.md) — all read/write this
  file's `let`/`const` bindings as shared global state (classic `<script>`
  tags in one page share one lexical scope — this is not a module with
  exports; there is no import/export anywhere in the client)

## Key State & Functions

- **Tunables** — `ZOOM_MAX`, scroll fling constants, `VIEWPORT_MARGIN`,
  `RECONNECT_MS`, MSE live-edge constants (`LIVE_MAX_BEHIND_S` etc.), and the
  cursor-offset bounds (`CURSOR_OFFSET_MARGIN/MIN/MAX/FALLBACK`,
  `CURSOR_CALIB_SAMPLES`) — see [Input Geometry (flow)](../__flow/input-geometry.md)
  for how the offset bounds are used.
- **DOM/connection refs** — `canvas`, `ctx`, `statusEl`, `token` (from the URL
  query string, delivered by the QR/pairing link).
- **View/stream state** — `monitor`, `baseRect`, `view` (pan/zoom transform),
  `baseBitmap`/`detailBitmap`/`detailRegion` (JPEG mode), `ws`, `streamMode`
  (`"h264"` default-overridden-to `"jpeg"` at declaration, actually set from
  the server's `config` message), `cursorPos`, `hand`.
- **Gesture state** — `touchMode` (single active mode: move/drag/scroll/pan),
  `pointers` (Map of active PointerEvents), `pinch`, `primary` (the steering
  finger).
- **Calibration state** — `fingerRadiusPx`, `fingerMaxPx`,
  `fingerSampleCount`, `calibrating`.
- **Region-streaming state** — `lastSentViewport`, `viewportTimer`.
- `setStatus(cls, text)` — sets the status pill's class + text.
- Global `error`/`unhandledrejection` listeners route uncaught page errors
  into the status pill (visible, never a silent dead page).
- `toCanvasPx(e)` — PointerEvent → canvas-px point (`clientX/Y * devicePixelRatio`).
- `send(msg)` — JSON-encodes and sends on `ws` if open; otherwise (unless the
  4401 "link expired" state is active) flips the status pill to
  "Reconnecting…" and calls `ensureConnected()` (defined in
  [Connection](connection.md), loaded later — safe because `send` only
  *references* it inside a function body, and it is always defined by the
  time `send` is actually invoked at runtime, well after all six scripts have
  finished loading).

## Design Decisions

- **One shared global scope, on purpose.** The client has "no framework, no
  build step" (project CLAUDE.md). Converting this into ES modules would
  require explicit `export`/`import` for ~40 cross-referenced bindings — a
  much larger, riskier rewrite for a project that intentionally has no build
  step. Classic `<script>` tags loaded in order are semantically identical to
  one concatenated file (same shared lexical scope), which is what this split
  preserves. See [Client (folder)](../___client.md) Design Decisions for the
  full god-file-split rationale.
## Layouts (Phase F+ step 1)
`layouts` / `layoutActive` / `layoutRegion` mirror the server's `layout_state`
(the server owns the list — it survives phone disconnects); `layoutArm` is the
one-shot "next canvas tap picks a window" flag set by the Layout (+) button;
`viewLocked()` selects the view's bounds rect (see [Render](render.md)) and
the cursor clamp — it no longer disables gestures: since owner 2026-08-04
pinch zoom/pan works in layout focus too, bottoming out at the layout's own
framing.
`send()` also refuses to auto-reconnect after a 4409 takeover (one device at a
time — a background reconnect would steal the session back in a loop).

## `kbShift` (owner 2026-08-03)
The canvas keeps its full height when the soft keyboard opens and is shifted
up instead of being squeezed ([Render](render.md)). Pointer events are
reported against the VISIBLE viewport, so `toCanvasPx` adds `kbShift` back to
land in canvas space — every gesture goes through it, so this is the single
place that needs to know.
