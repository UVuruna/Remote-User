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
- `#filepick` — hidden `<input type="file" accept="image/*">` for phone → PC
  image upload
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

- [Web Layer](../../server/__about/web.md) — served at `/` for desktop browsers and
  the APK's WebView (`RemoteUserApp` User-Agent marker); plain Android
  browsers get [Install Funnel](install.md) instead
- [Tests (folder)](../../tests/___tests.md) — the input-pipeline gate drives
  this exact page end-to-end in real headless Chromium
