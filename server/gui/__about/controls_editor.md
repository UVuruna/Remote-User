# Controls Editor

**Script:** [Controls Editor (script)](../controls_editor.py) ·
**Flow:** [diagram](../__flow/controls_editor.md)

## Purpose

The desktop Controls editor (ROADMAP Phase G1, owner spec 2026-08-05): a
dialog that edits the USER copy of `actions.json` — end users never hand-edit
files. What it does:

- **Picks the four commands each set puts on the phone's D-pad.** Every set
  carries a POOL (`buttons`) that may hold more than four commands — the
  RESERVES (VSCode's Markdown preview and tab hops, Explorer's tabs, Edit's
  Save…) — and `active` names the chosen four by ID (owner 2026-08-05). The
  pool of a built-in or app set is OURS: the owner picks from it, he does not
  rewrite it (owner decision 2026-08-05).
- Creates/deletes/renames CUSTOM sets, whose commands are fully editable (a
  built-in action or a RECORDED chord/special key, with an optional icon).
- Chooses which sets the phone's wheel shows by default (Mouse/Input/Settings
  are `required` and locked ON; every other shipped or custom set toggles,
  `WHEEL_MAX` = 8 total; app sets never charge the count — they ride with a
  focused layout).
- Rearranges the four ACTIVE buttons per orientation (`order_land` — landscape
  cross, `order_port` — portrait column) with a reset to the shipped default.

App-aware sets (`app_sets`, VSCode/Chrome/Explorer) appear in the editor for
the first time — their pools are where the owner's per-app reserves live.
The phone re-reads `actions.json` on every connection, so changes need no
restart; the phone's own Settings → Sets picker can override the defaults per
device.

**Built-in rows tell the truth** (owner report 2026-08-05 — "kako NO ICON kad
svi imaju ikonu?"): a built-in action's name and icon live in the client's
`BUILTINS` table, so the editor parses that table and SHOWS the real values
(greyed, because they are inherited) instead of an empty placeholder.

## Layout — the computed minimum (SPACE & LEGIBILITY LAW)

`_computed_minimum()` measures, it never guesses: width = the set list's
widest real entry (`sizeHintForColumn`) + the detail form (caption + the
longest command name / chord / "Built-in: …" entry + the Record button);
height = six pool rows + the detail form's four rows + the arrangement's
caption and four slots + the fixed furniture. With the shipped actions.json
that is **1224 × 646** (dev machine, Segoe UI 13 px, 2026-08-05); it moves
with the content, which is the point. `ChordRecorder` measures its own two
lines: **406 × 58**.

The command table takes the window's free height (no widget carries a hard
size), and every editor field owns a full-width row — the two failures the law
names (a list scrolling beside empty space, a shortcut rendered "ift+tab")
cannot recur here. Proof: [tests/test_layout_audit_qt.py](../../../tests/___tests.md).

## Connections

### Uses
- [Config](../../__about/config.md) — `SETTINGS.actions_path`/`client_dir`,
  `USER_DIR`, `BUNDLE_DIR`, `PROJECT_ROOT`, `FROZEN`, `apply()` (repointing the
  running server at the user copy the first time it is seeded)
- client/controls.js — `load_client_icons()` and `load_client_builtins()`
  parse `const ICONS` / `const BUILTINS` out of it, so icons AND built-in
  labels have exactly one source of truth
  ([Controls](../../../client/__about/controls.md))
- the SHIPPED actions.json — `merge_shipped_pools()` refreshes every built-in
  pool from it on open ([Actions](../../../ACTIONS.md))

### Used by
- `gui/main_window.py` (see [GUI (subfolder)](../___gui.md)) — the
  "Controls…" button opens `ControlsEditor(self).exec()`

## Classes

- **`ChordRecorder`** — a tiny modal that captures ONE key combination from
  the PC keyboard (`keyPressEvent`: modifiers + a key the injector knows —
  letters/digits, F-keys, `QT_NAMED_KEYS`) and returns it as a chord string
  (`ctrl+shift+p`). Chords are recorded, never typed (owner spec). Esc alone
  cancels.
- **`SlotList`** — a `QListWidget` whose size hint is exactly the height of
  its rows. This is what replaced the hard height that made the arrangement
  lists scroll while the dialog stood empty (ladder step 1).
- **`OrderList`** — the four ACTIVE buttons in slot order with ↑/↓, one per
  orientation; identity order is returned but written as "no entry" (the
  shipped default needs no JSON).
- **`CommandDetail`** — the selected command, ONE field per full-width row
  (Does / Shortcut + Record / Name / Icon). Read-only for built-in and app
  sets, and always showing the real inherited values.
- **`CommandTable`** — the set's whole pool: tick, name (+ icon), does
  (built-in / chord / key), shortcut. Item truncation is turned OFF (the law),
  columns size to content except the name column, which stretches.
- **`ControlsEditor`** — the dialog: set list (built-ins and app sets
  flagged), `_store_current` writes screen → RAM on every selection change,
  `_tick_changed` keeps the D-pad at four and says so on screen when a fifth
  is tried, `_save` validates (empty sets warned, shown-by-default clamped to
  `WHEEL_MAX`) and writes the file.

## Functions

- `user_actions_path()`: the writable actions.json — dev: the repo file;
  installed: seeds the %LOCALAPPDATA% copy from the bundled default on first
  use and repoints the running server via `config.apply`
- `shipped_actions_path()`: the actions.json we SHIP, still reachable after
  the repoint — the source every built-in pool is refreshed from
- `merge_shipped_pools(data, shipped)`: built-in and app sets take their
  `buttons` from the shipped file while the owner's `active` / `order_*` /
  `enabled` survive. Without it an owner who already has a user copy would
  never receive the reserve commands a new version adds (the 2026-08-05 root
  cause of "Settings still shows Anywhere")
- `button_id(btn)`: the stable identity `active` stores — explicit `id`, else
  action / chord / key / label. IDs, not indices, so inserting a pool command
  in a later version cannot silently re-point the owner's choice
- `active_buttons(s)`: the ≤4 commands on the D-pad — mirrors the client's
  `activeButtons()`; no `active` = the first four (pre-pool behaviour)
- `load_client_table(name, line_re)`: one `const NAME = {...}` table out of
  client controls.js; `{}` on any surprise (never a crash)
- `load_client_icons()` / `load_client_builtins()`: `{name: svg fragment}` and
  `{action: (label, icon)}` built on top of it
- `icon_for(body)`: one fragment → `QIcon` via `QSvgRenderer` (48 px, stroke
  `ICON_STROKE`)
