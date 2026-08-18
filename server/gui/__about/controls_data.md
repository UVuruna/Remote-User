# Controls Editor — Data

**Script:** [Controls Data (script)](../controls_data.py) ·
**Flow:** [diagram](../__flow/controls_data.md)

## Purpose

actions.json plumbing for the Controls editor, with **no Qt** in this module
— split out of `controls_editor.py` and `controls_widgets.py` in build round
R5 (2026-08-07, the owner's "choose the wheel order" round pushed the dialog
module toward the 1,000-line threshold again). Everything here is a plain
function over `dict`/`Path`:

- the writable/shipped actions.json PATHS (`user_actions_path`,
  `shipped_actions_path`);
- parsing the client's own tables so the editor never keeps a second copy of
  truth (`load_client_table`, `load_client_icons`, `load_client_builtins`);
- a command's stable identity (`button_id`) and the ≤4 that ride the D-pad
  (`active_buttons`);
- the MIGRATION (`merge_shipped_pools`) that carries everything a new version
  invents into an owner's own copy — which is seeded once at install and never
  replaced — while his `active` / `order_*` / `enabled` / `wheel_order` /
  renames / `custom_sets` survive;
- **new this round:** `natural_order` (today's set order, straight from the
  file's own sections — the DEFAULT `wheel_order`) and `effective_wheel_order`
  (the owner's saved order, extended with any set it does not mention,
  appended at the end).

The split's honesty test: `tests/test_controls_sets.py` already imported
`merge_shipped_pools`/`active_buttons` directly, with no `QApplication` in
sight — this module is exactly what that test was already exercising.

## Connections

### Uses
- [Config](../../__about/config.md) — `SETTINGS.actions_path`/`client_dir`,
  `USER_DIR`, `BUNDLE_DIR`, `PROJECT_ROOT`, `FROZEN`, `apply()` (repointing
  the running server at the user copy the first time it is seeded)
- client/icons.js — `load_client_icons()` parses `const ICONS` out of it
  ([Icons](../../../client/__about/icons.md)); client/controls.js —
  `load_client_builtins()` parses `const BUILTINS`
  ([Controls](../../../client/__about/controls.md))
- the SHIPPED actions.json — `merge_shipped_pools()` refreshes every
  built-in pool from it, and `natural_order()` reads its section order as
  the default `wheel_order` ([Actions](../../../ACTIONS.md))

### Used by
- [Controls Editor](controls_editor.md) — the WINDOW: loads/saves through
  these functions, never re-implements them
- [Controls Widgets](controls_widgets.md) — `CommandTable` uses `button_id`
- [Controls Order](controls_order.md) — `active_buttons`' sibling constant
  `DPAD_SLOTS` sizes the D-pad ladder's four fixed slots
- `server/actions_api.py` — `_merge_shipped_actions()` imports
  `merge_shipped_pools` FROM HERE once per server start (FROZEN only) to keep
  a phone-visible default change from sitting unmerged until the owner happens
  to open the editor. It read the same name off `controls_editor` until
  2026-08-18, which pulled PySide6 onto the HEADLESS path and left the merge
  silently skipped when the import failed — this module is Qt-free precisely
  so that caller does not have to be

- `tests/test_controls_sets.py` — every pure-data guard imports straight
  from here now, not through the dialog module

## Functions

- `user_actions_path()` / `shipped_actions_path()`: the writable copy and
  the source-of-truth shipped file (see [Controls Editor](controls_editor.md)
  for the seeding story)
- `load_client_table(name, line_re, source)` / `load_client_icons()` /
  `load_client_builtins()`: one client script's `const NAME = {...}` table,
  parsed — `{}` on any surprise, never a crash
- `button_id(btn)`: a command's stable identity — `id`, else action / chord /
  key / label
- `active_buttons(s)`: the ≤4 commands on the D-pad — mirrors the client's
  `activeButtons()`
- `merge_shipped_pools(data, shipped)`: **the migration**, governed by THE
  OWNERSHIP RULE below. Named for pools only because `server/web.py` imports
  it under that name and that file sits on the STRUCTURE LAW's line limit;
  its responsibility is the whole file. Runs top-level keys first, then every
  built-in and app set matched BY NAME (`_merge_set`), then adds any set the
  owner has never had. A set he has that we no longer ship is left alone —
  it may be a set that moved, and silently deleting a wheel entry is the
  failure this module exists to stop
- `_merge_set(mine, ship)`: one set, migrated onto the shipped version of
  itself; carries his button RENAMES across by command ID and drops an
  `active` that points at a command the refreshed pool no longer has
- `natural_order(data)`: every set's name, in the order the FILE itself
  lists them (`SECTION_KEYS` = categories, app_sets, custom_sets) — the
  shipped default `wheel_order`, and the fallback for a set an owner's saved
  order does not mention
- `effective_wheel_order(data)`: the owner's `wheel_order` filtered to sets
  the file still has, extended with any it does not mention (appended at
  the end) — never mutates `data`

## Design Decisions

- **No Qt import here, on purpose.** The dependency runs one way: the Qt
  modules (`controls_editor.py`, `controls_widgets.py`, `controls_order.py`)
  import FROM here; nothing here imports a widget. That is what makes the
  split real rather than a line-count trim — every function is callable, and
  every guard test runnable, with no `QApplication` anywhere.
- **THE OWNERSHIP RULE (2026-08-07) — a rule, never a list of field names.**
  This is the fix for a failure the owner reported across four or five
  releases. The merge used to copy a HARDCODED LIST of fields
  (`name, icon, required, process, title`), so every field invented after that
  list was written silently never arrived in a user's file. The Claude app set
  gained `"agent": "claude"` on 2026-08-06; his copy never did; the set could
  then only match by TITLE, and Claude Code names its VS Code tab after the
  CONVERSATION — his title reads *"Voditi agente i kontrolisati grid skice -
  Vibe Coder - Visual Studio Code [Administrator]"*, so the condition was
  unsatisfiable forever. The same engine had already kept "Anywhere" in his
  Settings set after the update that replaced it, and `wheel_order` was one
  release from joining them.

  The list is therefore **inverted**. It no longer names what WE deliver — a
  list like that can only ever be out of date — it names what HE OWNS:

  | | Keys | On merge |
  |---|---|---|
  | **HIS** (set) | `active`, `order_land`, `order_port`, `enabled` — plus button `label` renames, carried by command ID | kept exactly if present; **seeded** from shipped if absent |
  | **HIS** (top-level) | `wheel_order`, `left`, `right`, and `custom_sets` entirely | same |
  | **OURS** | *everything else, including fields nobody has invented yet* | always taken from shipped; **deleted** if shipped retired it |

  A key he has edited that we also changed: if it is HIS, his wins; if it is
  OURS, ours wins — because the commands of built-in and app sets are ours by
  product decision (owner 2026-08-05: he picks from the pool, he does not
  rewrite it), and `label` is the one documented exception.

  Seeding is what finally delivers `wheel_order` to a file that predates it:
  a default he has never expressed an opinion about is not an opinion to
  protect. Deleting a retired key is the mirror image of the same disease —
  a field the PC no longer honours must not sit in his file lying to the
  phone (the per-layout Claude tick list was exactly such a key).

  **The one discipline this demands:** a new key the owner may edit MUST be
  added to `OWNER_SET_KEYS` or `OWNER_TOP_KEYS` in the same commit that makes
  it editable. The editor and the phone must never be the only places that
  know.

  Gate: `tests/test_actions_migration.py`, in `run_guards.py` and fail-closed
  in `setup/build.py` (0h/6). It starts from the owner's REAL older file
  shape, and it plants a field name nobody has invented — because a gate that
  tested for `agent` would have to be rewritten for every future field, and
  the one it was not rewritten for would ship broken.
- **Why every existing guard was green through all of it.** They built their
  "user file" with `user = copy(shipped)`. A user file made out of the shipped
  file already has every new field, so the guards proved the repo's
  actions.json to itself and could not fail. Any future guard over this
  function must start from an OLDER shape or it proves nothing.
