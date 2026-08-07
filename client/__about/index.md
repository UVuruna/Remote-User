# Page Shell

**Script:** [Page Shell (script)](../index.html)

## Purpose

The tablet page's DOM shell — every element the client's six scripts (State,
Render, Input Geometry, Controls, Gestures, Connection — see
[Client (folder)](../___client.md) for the split) drive by id, and every
element `style.css` styles by id/class. No logic of its own: a locked
viewport (`user-scalable=no` — pinch drives the client's own zoom, never the
browser's), the canvas the stream is drawn onto, an offscreen `<video>` MSE
decode surface, the fixed corner buttons, the two configurable D-pad groups,
the category wheel, the invisible keyboard-capture textarea, the phone → PC
file picker, and the "access from anywhere" banner + guided wizard overlay.

## Structure

- `#status` — connection-state pill (connecting / connected / disconnected)
- `#screen` — the canvas the stream (H.264 frames drawn from `#vid`, or JPEG
  bitmaps) is rendered onto
- `#vid` — offscreen `<video>`, the H.264/MSE decode surface; never shown
  directly, only drawn onto `#screen`
- `#btn-pan` (top-left, "Move") / `#btn-hide` (top-right, "Hide") — fixed
  corner buttons
- `#group-left` / `#group-right` — the two D-pad control groups, filled at
  runtime from `actions.json`'s categories
- `#wheel` — the tap-based category-picker overlay
- `#kb` — the invisible but real-size keyboard-capture textarea (typed /
  dictated text goes to the PC's focused box)
- `#filepick` — hidden `<input type="file" accept="image/*">` for the legacy
  single-image upload action
- `#pick-gallery` / `#pick-camera` / `#pick-files` — the Attach set's hidden
  inputs (owner 2026-08-04): gallery and Files carry `multiple` (several picks
  paste as real files on the PC), camera carries `capture` (the shell opens
  the camera directly)
- `#sets-panel` — the Settings → Sets overlay (which custom sets ride in the
  wheel on this phone; creation is desktop-only)
- `#anywhere-banner` / `#wizard` (`#wiz-step-1/2/3`) — the guided "access from
  anywhere" (Tailscale) banner and its step-by-step overlay
- `#update-banner` — shown inside the APK when the PC server carries a newer
  app version than this shell

## Connections

### Uses

- [Style](style.md) — stylesheet, `/static/style.css`
- Six classic `<script>` tags, loaded in this exact order (one shared global
  scope, no build step — see [Client (folder)](../___client.md) Design
  Decisions): [State](state.md), [Render](render.md),
  [Input Geometry](input-geometry.md), [Controls](controls.md),
  [Gestures](gestures.md), [Connection](connection.md)

### Used by

- [Web Layer](../../server/__about/web.md) — served at `/` ONLY to the APK's
  WebView (`RemoteUserApp` User-Agent marker); every browser on every device
  gets [Install Funnel](install.md) instead (owner rule, hardened 2026-08-02)
- [Tests (folder)](../../tests/___tests.md) — the input-pipeline gate drives
  this exact page end-to-end in real headless Chromium

## Layouts (Phase F+ step 1)
The top-left corner button is now **Layout (+)** (the Move/pan button is gone
— owner 2026-08-02); `#layout-bar` sits top-center (hidden until a layout
exists; big SVG arrows outside a framed name button that opens the layout list, + ✕); `#layout-panel` is the empty container controls.js
fills with the creation card.

## Build round R3 (2026-08-07) — themes

Two tags, in the two places order matters (build round R3):

- `theme.css` is linked FIRST, before `style.css` and `layouts.css` — it owns
  every colour token those two read.
- `theme.js` loads right after `controls.js`: it uses that file's
  `prefGet`/`prefSet` and `IN_APP`, and it must run before anything paints a
  control, because it applies the cached look at load time.

See [theme.css + theme.js](theme.md).
