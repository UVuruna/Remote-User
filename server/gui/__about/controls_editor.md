# Controls Editor

**Script:** [Controls Editor (script)](../controls_editor.py) ·
**Flow:** [diagram](../__flow/controls_editor.md)

## Purpose

The desktop Controls editor (ROADMAP Phase G1, owner spec 2026-08-05): a
dialog that edits the USER copy of `actions.json` — end users never hand-edit
files. Creates/deletes/renames CUSTOM sets (4 buttons each: a built-in action
or a RECORDED chord, with an optional icon), chooses which sets the phone's
wheel shows by default (Mouse/Input/Settings are `required` and locked ON;
every other shipped or custom set toggles, `WHEEL_MAX` = 8 total), and
rearranges ANY set's buttons per orientation
(`order_land` — landscape cross, `order_port` — portrait column) with a reset
to the shipped default. The phone re-reads `actions.json` on every
connection, so changes need no restart; the phone's own Settings → Sets
picker can override the defaults per device.

## Connections

### Uses
- [Config](../../__about/config.md) — `SETTINGS.actions_path`/`client_dir`,
  `USER_DIR`, `FROZEN`, `apply()` (repointing the running server at the user
  copy the first time it is seeded)
- client/controls.js — `load_client_icons()` parses `const ICONS = {...}` out
  of it, so the icon set has exactly one source of truth
  ([Controls](../../../client/__about/controls.md))

### Used by
- `gui/main_window.py` (see [GUI (subfolder)](../___gui.md)) — the
  "Controls…" button opens `ControlsEditor(self).exec()`

## Classes

- **`ChordRecorder`** — a tiny modal that captures ONE key combination from
  the PC keyboard (`keyPressEvent`: modifiers + a key the injector knows —
  letters/digits, F-keys, `QT_NAMED_KEYS`) and returns it as a chord string
  (`ctrl+shift+p`). Chords are recorded, never typed (owner spec). Esc alone
  cancels.
- **`ButtonRow`** — one of a custom set's four buttons: kind combo (chord /
  built-in from `BUILTIN_ACTIONS`), label, icon combo (rendered previews),
  chord field + Record. `dump()` returns the actions.json entry or `None`
  when incomplete.
- **`OrderList`** — four buttons in slot order with ↑/↓; identity order is
  returned but written as "no entry" (default needs no JSON).
- **`ControlsEditor`** — the dialog: set list (built-ins flagged, arrangement
  editable for ALL sets; content editable only for custom), `_store_current`
  writes screen → RAM on every selection change, `_save` validates (empty
  sets warned, shown-by-default clamped to `WHEEL_MAX`) and writes the file.

## Functions

- `user_actions_path()`: the writable actions.json — dev: the repo file;
  installed: seeds the %LOCALAPPDATA% copy from the bundled default on first
  use and repoints the running server via `config.apply`
- `load_client_icons()`: `{name: svg fragment}` parsed from client
  controls.js; `{}` on any surprise (names without previews, never a crash)
- `icon_for(body)`: one fragment → `QIcon` via `QSvgRenderer` (48 px, stroke
  `ICON_STROKE`)
