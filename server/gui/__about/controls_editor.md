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
- **Renames the BUTTONS of any set, shipped ones included** (owner
  2026-08-05). What a button does stays ours; what it is called is his — the
  side buttons `Btn 4` / `Btn 5` carry whatever the user's mouse driver put on
  them, so the face has to be able to say "Back" or "Undo". The Name field is
  the only live field on a built-in row; its placeholder shows the phone's own
  name, and clearing the field drops the override instead of freezing today's
  default into the file. `merge_shipped_pools` carries the renames across a
  version's pool refresh, matched BY COMMAND ID.
- Chooses which sets the phone's wheel shows by default (Mouse/Input/Settings
  are `required` and locked ON; every other shipped or custom set toggles,
  `WHEEL_MAX` = 8 total; app sets DO charge the count on the phone since
  2026-08-06 — see [Controls](../../../client/__about/controls.md)).
- Rearranges the four ACTIVE buttons per orientation (`order_land` — landscape
  cross, `order_port` — portrait column) with a reset to the shipped default.
  The slot ladder is fixed and belongs to the POSITION — `Top · Left · Right ·
  Bottom` in landscape, `1ˢᵗ … 4ᵗʰ` in portrait (owner 2026-08-05); only the
  commands travel through it. The widgets themselves live in
  [Controls Widgets](controls_widgets.md) (THE STRUCTURE LAW split of the
  same day). The box is captioned **Arrangement** and its two lists are
  **D-pad (landscape)** and **Stack (portrait)** (owner's own names,
  2026-08-06) — repeating `top · left · right · bottom` in the title said the
  same thing the rows below already spell out. The single **Default** button
  sits in its own row UNDER the lists: beside them it charged the whole box
  its width, and the content paid.

## The set list — three sections (owner 2026-08-06)

One flat list of twelve names said nothing about WHEN a set appears, which is
the only thing that separates them. `SECTIONS` is the display order and the
headings: **Standard** (always in the wheel) → **App-aware** (only while a
matching layout is focused) → **Custom** (made here). The names match the
vocabulary of CLAUDE.md and ACTIONS.md, so the editor and the docs speak one
language.

A heading is a TITLE, not a bold set name: `SectionDelegate` paints it
centered, a quarter larger than the rows it governs, and draws the horizontal
**rule** that separates it from the section above (owner 2026-08-06 — "LINIJA
KOJA RAZDVAJA"; the first heading divides nothing, so it gets no rule). The
rule's colour comes from the palette's TEXT with alpha, never `mid()` — on
this dialog's dark theme `mid()` is a hair off the background and the line was
invisible.

A section in `HIDE_WHEN_EMPTY` (**Custom**) is not shown at all while it holds
nothing — owner 2026-08-06: a heading over an apologetic "(none yet)" line is
a placeholder, not information. The **New set** button is the invitation; the
section is born with its first set.

## The tick — which sets are actually on the wheel (owner 2026-08-06)

The list named twelve sets and said nothing about which of them the phone
shows. The state existed only in one checkbox on the other side of the dialog,
so reading it meant clicking every set in turn — and the owner had asked for
the mark once already, in the round before. Each set row now carries its own
answer: `CHECK_ROLE` holds it, `SectionDelegate._paint_tick` draws it, and
`MARK` reserves its column so a set name can never be painted underneath it (THE SPACE & LEGIBILITY LAW — the width the
list asks for grows with it). The mark is DRAWN, three points and a round pen,
never a font glyph: this project has already paid for a glyph that came out a
blunt cross on the owner's own device.

The tick sits in its own strip on the **left**, with the icon and name
indented past it, and it has two colours — the owner's own rule (2026-08-06):
**grey** where the set is `required` and he could not turn it off if he wanted
to (Mouse, Input, Settings), **white** where it is on and his to switch. A tick
that looked the same in both cases would promise him a choice he does not have.
The row's background is painted across the full width first, so the strip
belongs to the selected row instead of leaving a gap beside it.

**App-aware sets are ticked too**, and their checkbox is live. They were left
blank on the reasoning that they ride only in layout focus — but the phone
reads the SAME `enabled` flag for them (`appSetOn` in client/sets.js), so a
blank row hid a switch that already worked, and a dead checkbox refused an edit
the file accepted. A switched-off app set also stops charging a wheel slot.
The list's caption says it once ("Sets — ticked = on the phone's wheel"), and
`_mark_current()` keeps the row and the form's checkbox saying the same thing
the instant either changes (the form writes into `self.data` only on the way
out, so the row cannot be re-read from there).

Headings are rows with `NoItemFlags` — Qt may never let the selection land on
one. `self._rows` is the bridge that makes that safe: row → entry index, or
`None` for a heading. The list's `currentRowChanged` goes to
`_row_selected`, the ONLY place that translates rows into entry indices;
everything else in the dialog (`_current`, `_reload_list(select=…)`,
`_select`) speaks entries. Mixing the two is what would put one set's data on
another set's screen.

An app-set row's suffix names the CONDITION, not the process: two sets share
`code`, so `Claude   (code · “claude code”)` is the useful line and
`VSCode   (code)` is the unconditional one.

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
caption, four slots and its two button rows (the ↑↓ pair and the Default
button, which moved under the lists on 2026-08-06) + the fixed furniture.
With the shipped actions.json
that is **1363 × 715** (dev machine, theme font 13 px, 2026-08-06); it moves
with the content, which is the point. `ChordRecorder` measures its own two
lines: **406 × 58**.

The measurement happens in `showEvent`, not in `__init__`: the theme reaches
this dialog through its parent's stylesheet and Qt resolves the QSS font and
padding only when the widget is polished. Measured in the constructor, every
string came out in the DEFAULT font — about 8% narrower than the theme's —
and the wheel checkbox and the set list were cut at the resulting minimum.
The audit caught exactly that, once its factory started applying the theme
the way the app does.

The command table takes the window's free height (no widget carries a hard
size), and every editor field owns a full-width row — the two failures the law
names (a list scrolling beside empty space, a shortcut rendered "ift+tab")
cannot recur here. Proof: [tests/test_layout_audit_qt.py](../../../tests/___tests.md).

## Connections

### Uses
- [Config](../../__about/config.md) — `SETTINGS.actions_path`/`client_dir`,
  `USER_DIR`, `BUNDLE_DIR`, `PROJECT_ROOT`, `FROZEN`, `apply()` (repointing the
  running server at the user copy the first time it is seeded)
- client/icons.js — `load_client_icons()` parses `const ICONS` out of it
  ([Icons](../../../client/__about/icons.md)); client/controls.js —
  `load_client_builtins()` parses `const BUILTINS`
  ([Controls](../../../client/__about/controls.md)). Icons AND built-in labels
  therefore have exactly one source of truth, the phone's own
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
  (Does / Shortcut + Record / Name / Icon). On a built-in or app-set row every
  field is read-only EXCEPT the Name, which anyone may override (owner
  2026-08-05); the fields always show the real inherited values.
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
- `load_client_table(name, line_re, source)`: one `const NAME = {...}` table
  out of a client script (`controls.js` by default, `icons.js` for the icon
  set); `{}` on any surprise (never a crash)
- `load_client_icons()` / `load_client_builtins()`: `{name: svg fragment}` and
  `{action: (label, icon)}` built on top of it
- `icon_for(body)`: one fragment → `QIcon` via `QSvgRenderer` (48 px, stroke
  `ICON_STROKE`)

## App sets charge the wheel here too (owner 2026-08-06)

`_save()` used to state that app sets never charge the wheel count — written
2026-08-05 and reversed by the owner the next day. That line was the DESKTOP
half of what he found on his phone: nine sets ticked under a cap of eight.

The editor now computes the same reserve the phone does — the largest group of
app sets sharing a `process`, because Chrome, Explorer and VSCode can never
appear together while VSCode and Claude always do — and leaves
`WHEEL_MAX - reserve` for everything else. The message says which, and why,
instead of quietly switching sets off.
