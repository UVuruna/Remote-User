# Controls

**Script:** [Controls (script)](../controls.js) ·
**Flow:** [diagram](../__flow/controls.md)

## Purpose

Everything that isn't the canvas itself: icons, the built-in action registry,
touch-mode toggle buttons, invisible keyboard capture, the "access from
anywhere" Tailscale wizard, the in-app update banner, phone→PC image upload,
the two configurable D-pad control groups, the tap-based category wheel,
corner buttons (Move/Hide) and the toast pill. Fourth of the seven client
scripts to load (after [Input Geometry](input-geometry.md), before
[Layouts](layouts.md)).

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
- [Layouts](layouts.md) — every layout button is wired through `keepFocus`,
  and it uses `svg`, `showToast` and `IN_APP` from here

## Key Functions & Data

- `ICONS` / `svg(name)` — inline SVG path fragments for control icons
  (owner-approved set 2026-08-04: mouse-button faces for click/middle, mic,
  enter/esc, attach/gallery/shot/folder, edit-set icons, monitor2,
  undo/redo/find/del for hand-edited files).
- `BUILTINS` — the registry of built-in actions — label, icon, and dispatch
  kind. Kinds: `hold` (Click/Right/Middle — CLICK/HOLD mouse buttons),
  `mode` (scroll/drag toggles), `kb`, `mic`, `key-off` (enter/esc — switch
  keyboard+mic OFF, then press the real key; `newrow` is deliberately a plain
  `send` of shift+enter so a line break never interrupts dictation),
  `pick` (gallery/camera/files),
  `shot` (region screenshot), `send`, `upload`, `calibrate`, `anywhere`,
  `quality`.
- `holdButton(el, button)` — the CLICK/HOLD primitive (owner 2026-08-04):
  `press {button, down:true}` on pointerdown, `down:false` on
  pointerup/pointercancel — a tap clicks, a held finger holds the PC button
  (what the old Drag toggle did); cancel always releases so no PC button can
  stay stuck.
- Mic switcher (`micStart/micStop/toggleMic`, `__voiceResult`, `__voiceEnd`)
  — direct voice input via the shell's `Android.startVoice()` bridge
  (SpeechRecognizer); recognized text goes out as `key_text`. Only one of
  mic/keyboard is ever ON; `inputOff()` (Enter/Esc buttons, a tap on the
  stream) switches both OFF.
- `shotRegion()` — the monitor-normalized rect the phone is LOOKING at
  (zoom/layout aware) — sent with `screenshot {paste:true}` by the Shot
  button; the server crops, fills the clipboard and injects Ctrl+V itself.
- Wheel composition (`allCats`, `refreshCategories`; owner 2026-08-05,
  revised same day): `required` categories (Mouse/Input/Settings) ALWAYS +
  toggleable shipped sets and custom sets (`setOn`: phone choice from
  localStorage wins over the desktop `enabled` default) + the app set in
  layout focus (`visibleAppSets`, owner 2026-08-04; charges nothing), hard
  cap `WHEEL_MAX` (8) with non-required sets bumped from the END. The
  Settings → Sets overlay (`openSetsPanel`/`setsRow`) locks required rows and
  blocks enabling past the cap (`visibleCount`).
- Per-orientation button arrangement (owner 2026-08-05): a set may carry
  `order_land` (slots T·L·R·B) / `order_port` (column top→bottom) from the
  desktop editor; `renderGroup` applies the one matching the current
  orientation (invalid orders fall back to the shipped default) and a
  `matchMedia("(orientation: portrait)")` listener re-renders on rotation.
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
- Phone → PC upload (`uploadPicked`, the `PICKERS` change handlers) — one
  image POSTs to `/upload` (bitmap paste); several files or any non-image
  POST to `/upload_files` (pasted as REAL files via CF_HDROP). Gallery and
  Files inputs allow multi-select; Camera captures directly (owner
  2026-08-04). The server injects the Ctrl+V itself.
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
- **The layout feature moved out** (2026-08-03) — the layout bar, list,
  aspect panel, creation flow and loading cube used to live at the end of this
  file and now have their own script and doc: [Layouts](layouts.md). This file
  crossed 1,000 lines (THE STRUCTURE LAW) and the split follows the
  responsibility line: what is left drives the PC directly, what left composes
  and frames windows on it.

## Step 3 additions (owner spec 2026-08-02)
`next_input` builtin (jump to the next text box — dictation workflow) and the
`quality` cycle (full → reduced → auto-on-mobile-data via
`Android.transport()`; persisted in localStorage, restated on every connect).
The update banner compares against `config.apk_version` — the APK the PC
actually serves.
