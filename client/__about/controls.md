# Controls

**Script:** [Controls (script)](../controls.js) ·
**Flow:** [diagram](../__flow/controls.md)

## Purpose

Everything that isn't the canvas itself: icons, the built-in action registry,
touch-mode toggle buttons, invisible keyboard capture, the "access from
anywhere" Tailscale wizard, the in-app update banner, phone→PC image upload,
the two configurable D-pad control groups, the tap-based category wheel,
corner buttons (Move/Hide) and the toast pill. Fourth of the six client
scripts to load (after [Input Geometry](input-geometry.md), before
[Gestures](gestures.md)).

**Kept as one file, not split further:** the wizard section calls
`keepFocus(anywhereBanner, openWizard)` at the top level, textually BEFORE
`keepFocus` itself is defined further down (in the D-pad section). This only
works because of `function`-declaration hoisting, which is scoped to a
single `<script>`/file — splitting a script boundary between that call and
`keepFocus`'s definition would throw `ReferenceError` at page load. See
[client/__about/state.md](state.md) and [Client (folder)](../___client.md)
for the split's general load-order reasoning.

## Connections

### Uses
- [State](state.md) — `send`, tunables, `hand`
- [Render](render.md) — `redraw()`, `computeBaseRect()`, `clampView()`
  (calibration/mode changes re-trigger a draw)
- [Input Geometry](input-geometry.md) — `startCalibration()` (the
  `calibrate` built-in)

### Used by
- [Connection](connection.md) — the `actions` message handler calls
  `renderGroup("left"/"right")`; the `config` handler calls
  `updateAnywhereBanner()`/`refreshUpdateBanner()`
- [Gestures](gestures.md) — reads `keyboardOpen()`

## Key Functions & Data

- `ICONS` / `svg(name)` — inline SVG path fragments for control icons.
- `BUILTINS` — the registry of built-in actions (`click`, `right`, `drag`,
  `scroll`, `keyboard`, `monitor`, `snap`, `upload`, `calibrate`,
  `anywhere`) — label, icon, and dispatch kind (`send`/`mode`/`kb`/`upload`/
  `calibrate`/`anywhere`).
- `setMode(mode)` / `refreshModeButtons()` — the single-active `touchMode`
  toggle and its button-state mirroring.
- Keyboard capture (`kbInput`, `keyboardOpen`, `toggleKeyboard`,
  `sendTyped`) — an invisible `<textarea>`; typed/dictated text is diffed
  against the previous value and replayed as `key_text`/`backspace`; Enter
  and IME-committed `"\n"` become the `shift+enter` chord (new row, never
  "send" — see [Client (folder)](../___client.md) Design Decisions).
- "Access from anywhere" wizard (`openWizard`, `closeWizard`, `wizProbe`,
  `updateAnywhereBanner`) — a guided one-time Tailscale setup; polls `/ping`
  on the Tailscale URL until the phone joins the mesh.
- In-app update (`versionNumbers`, `isNewer`, `refreshUpdateBanner`) —
  compares the server's `app_version` against the APK shell's own version
  (`window.Android.appVersion()`), shown only `IN_APP`.
- Phone → PC upload (`filePick` change handler) — POSTs the chosen image to
  `/upload`; the server pastes it into the PC's focused control.
- `keepFocus(el, onTap)` — the shared button-press primitive: fires on
  `pointerup` (touch grants transient user activation only at UP — needed by
  the file picker/IME) plus a `pointercancel` rescue when travel stayed under
  `CANCEL_TAP_SLOP` (Android steals edge-zone touches and ends them with a
  cancel — an up-only handler silently never fires there).
- `makeButton`/`makeActionButton`/`renderGroup` — builds a D-pad group's
  buttons from the current `actions.json` category.
- `openWheel`/`backdropCancel`/`closeWheel` — the tap-based category picker
  (no hold/drag).
- Corner buttons (`panBtn`, `hideBtn`) and `showToast(text)`.

## Design Decisions

- **`keepFocus`, never bare `click`/`pointerup`** — every control in this
  file uses it; see the class-level note above and
  [Client (folder)](../___client.md) for the full 2026-07-26 incident this
  defends against.
- **The wizard/update-banner/upload/D-pad/wheel/corner/toast block stays one
  file** — a direct consequence of the `keepFocus` hoisting dependency
  above; this is a structural constraint of the split, not an arbitrary
  grouping choice.
## Layouts (Phase F+ step 1)
The Layout (+) corner button ARMS a one-shot window pick (no switcher mode —
owner 2026-08-02); the top-center layout bar (`‹ name ›` + ✕) cycles
Desktop → layout 1 → … and removes the focused layout; `openLayoutPanel`
builds the creation card from `layout_offer` (Only this / Grid 2x1·1x2·2x2 +
open windows to fill the cells + Portrait/Wide); `applyOrientationLock`
drives the shell's `Android.lockOrientation` bridge (layout focus = rotation
locked, desktop = free). The old Move/pan corner button is GONE (owner
2026-08-02).
