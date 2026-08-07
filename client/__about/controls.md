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
- [State](state.md) — `send`, tunables
- [Render](render.md) — `redraw()`, `computeBaseRect()`, `clampView()`
  (mode changes re-trigger a draw)

### Used by
- [Connection](connection.md) — the `actions` message handler calls
  `renderGroup("left"/"right")`; the `config` handler calls
  `updateAnywhereBanner()`/`refreshUpdateBanner()`
- [Gestures](gestures.md) — reads `keyboardOpen()`
- [Gamepad](gamepad.md) — every pad button acts through `buttonPress`, and the
  D-pad/face arrows find their targets through `groupButton`
- [Layouts](layouts.md) — every layout button is wired through `keepFocus`,
  and it uses `svg`, `showToast` and `IN_APP` from here

## Key Functions & Data

- `svg(name)` — wraps one fragment of the icon table in the shared `<svg>`
  (viewBox, stroke width, caps). The TABLE itself moved to
  [Icons](icons.md) on 2026-08-05, when the owner approved a face for every
  pool command that had none — 97 icons, and the desktop editor parses the
  same file.
- `BUILTINS` — the registry of built-in actions — label, icon, and dispatch
  kind. Kinds: `hold` (Click/Right/Middle plus the side `x1`/`x2` — Btn 4 and
  Btn 5 on a 5-button mouse, owner 2026-08-05 — all CLICK/HOLD mouse buttons),
  `mode` (scroll/drag toggles), `kb`, `mic`, `key-off` (enter/esc — switch
  keyboard+mic OFF, then press the real key; `newrow` is deliberately a plain
  `send` of shift+enter so a line break never interrupts dictation),
  `pick` (gallery/camera/files),
  `shot` (the viewed region), `region` (the free frame — see [Region](region.md)),
  `send`, `upload`, `anywhere`, `quality`, `dictation`, `sets`.
  A button may override a built-in's NAME (`btn.label || b.label`, owner
  2026-08-05): the side buttons carry whatever the user's mouse driver put on
  them, so the face must be allowed to say "Back". Only the name — the
  action stays ours.
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
  layout focus (`visibleAppSets`, owner 2026-08-04 — and since 2026-08-05
  MORE THAN ONE may match: `appSetMatches` adds an optional `title` test on
  top of `process`, which is how the Claude set singles out Claude Code
  inside VSCode and rides BESIDE the VSCode set — the one case where two app
  sets are on the wheel at once, and both are wanted; `appSetOn` is each app
  set's own per-device switch in the picker), hard
  cap `WHEEL_MAX` (8) with non-required sets bumped from the END. The
  Settings → Sets overlay (`openSetsPanel`/`setsRow`) locks required rows and
  blocks enabling past the cap (`visibleCount`).
- **The title test is a WORD, and a document never matches** (`titleMatches`,
  `DOC_TITLE`; owner 2026-08-06): the Claude set may appear for the Claude
  CONVERSATION and for nothing else. Substring matching gave it to an open
  `CLAUDE.md`, to a transcript, to any file whose name carries the word. The
  test now needs a word boundary, `title` may be a LIST of spellings
  (`["claude code", "claude"]`), and a title that looks like a file name —
  an extension, with or without a `— App Name` tail — is refused outright.
- **App sets pay for their seat** (`appSetReserve`; owner 2026-08-06): they
  used to charge nothing, so the picker promised eight while the wheel
  silently dropped two. The charge is not "how many are ticked" but the
  largest group that can appear TOGETHER — sets are grouped by `process`, so
  ticking Chrome, Explorer and VSCode costs one slot while VSCode + Claude
  costs two. Tick both and six of the eight slots are left for the rest.
- Command pools (`btnId`, `activeButtons`; owner 2026-08-05): a set's
  `buttons` list is its POOL and may hold more than the four a D-pad shows —
  the reserves (VSCode's Markdown preview, Explorer's tab hops, Edit's Save…).
  A pool command may also be a TYPED one (owner 2026-08-05): `{text, enter}`
  sends `paste_text`, which the PC pastes into the focused box and follows
  with Enter — the Claude set's `/usage`, `/model`, `/effort`, which are not
  shortcuts at all.
  `active` names the four that ride, BY ID (`id | action | chord | key |
  label`), so a later version inserting or reordering pool commands cannot
  silently re-point the owner's choice the way indices would; no `active` =
  the first four, which is the pre-pool behaviour. The desktop Controls editor
  is where the four are ticked ([Controls Editor](../../server/gui/__about/controls_editor.md)).
  Reserve names are longer than the shipped four, so `.ctl .lbl` WRAPS onto a
  second row instead of eliding (THE SPACE & LEGIBILITY LAW; the phone audit
  proves the wrapped label stays inside its 58 px button).
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
  2026-08-04). The server injects the Ctrl+V itself. Opening any picker —
  and starting the mic — calls `markExcursion()` ([State](state.md)) first,
  so the hide that follows is announced as an excursion and the PC does not
  pack the layout away underneath a gallery pick (owner 2026-08-05).
- `keepFocus(el, onTap)` — the shared button-press primitive: fires on
  `pointerup` (touch grants transient user activation only at UP — needed by
  the file picker/IME) plus a `pointercancel` rescue when travel stayed under
  `CANCEL_TAP_SLOP` (Android steals edge-zone touches and ends them with a
  cancel — an up-only handler silently never fires there).
- `ACTIVATORS` / `buttonPress(el, down)` — **one activation per button**
  (build round G1, 2026-08-07). `keepFocus` and `holdButton` each register
  exactly ONE activator per element, and `buttonPress` is the single door a
  GAMEPAD press comes in by ([Gamepad](gamepad.md)) — a hold button's `hold`
  IS what its pointerdown/pointerup run, a tap button's `tap` IS what its
  pointerup and pointercancel rescue run. Nothing is duplicated, which is the
  point: constraint 9 is in CLAUDE.md because a second, parallel button path
  is precisely what killed every control on the real device once already.
  `down` follows the physical press, so a held pad arrow holds the PC button
  exactly like a finger; every other button acts on the RELEASE. It also
  paints `.held` while a pad key is down, so the screen always shows what the
  pad did (build round G2) — the same glow a finger earns on a hold button, no
  new styling.
- `groupButton(side, pos)` — the button sitting in one D-pad slot
  (`"up"`/`"left"`/`"right"`/`"down"`), found by the grid area
  `makeActionButton` stamps on it. The pad's arrows therefore press what the
  owner SEES in that direction even when a set carries its own `order_land` /
  `order_port` arrangement.
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
`quality` state. The update banner compares against `config.apk_version` — the
APK the PC actually serves.

## Device prefs bridge + Quality overrides (owner 2026-08-05)

- `prefGet`/`prefSet` — per-device storage through the shell's
  `Android.prefGet/prefSet` (SharedPreferences), with localStorage as the
  dev-browser fallback and migration source. Root cause it kills: localStorage
  is keyed by ORIGIN and the shell alternates between the LAN and Tailscale
  addresses, so bare localStorage silently split the device's saved state into
  two diverging copies (the sets picker "rotated" between two states). Used by
  `setsPrefs`, `qualityPrefs` and the anywhere-banner flag.
- The Quality button opens a PANEL (panels.js) instead of cycling:
  `qualityPrefs` (fps/res/bitrate/auto) → `effectiveQuality` (auto on cellular
  = the saving profile) → `quality {fps, res, bitrate}` to the server, which
  re-opens this client's encoder; restated on every connect.
- **The overlay panels moved out** (2026-08-05, same STRUCTURE-LAW split as
  layouts): Sets picker + Quality panel live in [Panels](panels.md); this file
  keeps their state/prefs logic, panels.js keeps their DOM.
- `__voiceInfo(text)` — diagnostic line from the shell, forwarded SILENTLY
  to the PC's server log as `client_log` (owner round 2, angrily: evidence
  for the developer, never a panel flashed at the user).
- `__voiceState(state)` + `refreshMicButtons()` — the Mic button wears the
  `dl` look (dashed, pulsing) while the chosen language's on-device model
  downloads; dictation keeps working online meanwhile.
- `micStart()` opens the dictation setup card ([Panels](panels.md)) instead
  of listening when no language was ever chosen; the `dictation` builtin
  (Settings → Language, replacing `anywhere` in the defaults) reopens it.

## The composition rules left (2026-08-06)

`controls.js` hit 1 000 lines, so everything that answers *"which sets exist
on this phone right now, and may they all fit"* — the per-device prefs, the
app-aware matching, the cap of 8 — moved to **[sets.js](sets.md)**, loaded
before this file. What stays here is the wheel, the D-pad groups and what a
button DOES. `groups` (which category each side shows) stayed with them.

## Build round R3 (2026-08-07) — themes

Two calls into [theme.js](theme.md), and nothing else changed here:

- `refreshCategories()` starts with `resetSetColors()` — a fresh set list may
  hold a custom set that has never been given a colour, and the map is rebuilt
  once rather than per button.
- `renderGroup(side)` and `openWheel(side)` call `paintSet(el, cat.name)`. The
  element painted is the one that OWNS the set — the D-pad GROUP, or a wheel
  item — so its four buttons, its category button and all their labels inherit
  `--set-color` / `--set-ink` / `--set-glow` in one write instead of five. A
  no-op in every theme but `colored`.
