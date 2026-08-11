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
- Creates/deletes/renames CUSTOM sets, whose commands are fully editable — a
  built-in action, a RECORDED chord/special key, or TYPED TEXT (the
  `paste_text` mechanism the Claude set is built from — a string pasted into
  the focused PC box, with an optional "press Enter afterwards"), each with
  an optional icon.
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
  [Controls Order](controls_order.md) (THE STRUCTURE LAW, moved there in
  build round R5, 2026-08-07 — first split out to
  [Controls Widgets](controls_widgets.md) on 2026-08-05). The box is
  captioned **Arrangement** and its two lists are **D-pad (landscape)** and
  **Stack (portrait)** (owner's own names, 2026-08-06) — repeating
  `top · left · right · bottom` in the title said the same thing the rows
  below already spell out. The single **Default** button sits in its own row
  UNDER the lists: beside them it charged the whole box its width, and the
  content paid.
- **Chooses the ORDER the sets ride the phone's wheel in** (owner build
  round R5, 2026-08-07: "he chooses the ORDER of the sets around the phone's
  category wheel") — a separate small dialog, the "Wheel order…" button
  under the set list. Position 1 sits at 12 o'clock, the rest follow
  clockwise; stored as `wheel_order` (a list of set names) in actions.json.
  Full spec: [Controls Order](controls_order.md).

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
list asks for grows with it). The mark is DRAWN, never a font glyph: this
project has already paid for a glyph that came out a blunt cross on the
owner's own device.

The tick sits in its own strip on the **left**, with the icon and name
indented past it, and the row's background is painted across the full width
first, so the strip belongs to the selected row instead of leaving a gap
beside it.

**The mark itself is `controls_widgets.paint_check`** (2026-08-07), the one
box this app draws — shared with the pool table and matched to the QSS
checkbox. It used to be a bare checkmark with **nothing at all** drawn for a
set that is switched OFF, so "off" and "not switchable" looked identical, and
a screen carrying three different tick affordances had no way to say which of
them was a control. The owner's own rule of 2026-08-06 survives the change,
carried by the FILL instead of by the ink: a `required` set shows the accent
WASH (riding, and not his to switch), a set he switched on shows the solid
accent, a set he switched off shows the empty box.

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
longest command name / chord / TYPED TEXT / "Built-in: …" entry + the wider of
the Record button and the "Press Enter afterwards" checkbox — build round R6,
2026-08-07, once the Text row existed); height = the TALLER COLUMN — left is
the set list's rows plus its button row plus the arrangement box, right is the
pool rows plus the detail form's four VISIBLE rows (Shortcut and Text never
show together, so the row count stays four) plus the actions row — with the
fixed furniture on top. It is a FLOOR: since 2026-08-07 both columns state
their own need (`_fit_set_list`, `CommandTable._fit_rows`), so
`settle_minimum` has the truth to grow from. `ChordRecorder` measures its own
two lines.

### THE REFLOW — what two independent graders bought (2026-08-07)

The first grader failed this window because the pool table scrolled while the
set list beside it held a large idle block. The answer then was a raised
minimum (ten rows) — and the second grader measured the SAME hole again: **3
of 13 commands behind a scrollbar, ~253 px of idle set list, ~90 px more in
the Arrangement box.** The ladder says reflow (step 2) BEFORE raise (step 3),
and the reflow had been tried once and reverted, so it went back in properly:

- **The Arrangement box is a LEFT-column box now.** Everything on the left
  answers "which set, and how does it ride" — pick it, make it, order the
  wheel, arrange its four buttons; everything on the right answers "which
  commands". The "Wheel order" button rides the New set / Delete row rather
  than a full-width row of its own, because height is the axis this window is
  short of and width it has to spare.
- **`_fit_set_list` declares the list's HEIGHT**, not only its width. That is
  why the first attempt failed: Qt quotes a `QListWidget`'s
  `minimumSizeHint` at a couple of rows however many it holds, so the settle
  loop had nothing to grow the window for and the reflow simply moved the
  starvation from one column to the other (the list scrolled and clipped
  "Explorer" mid-row). A column that does not state its need cannot be given
  its share. `ROWS_SHOWN` caps the declaration exactly as
  `CommandTable.ROWS_SHOWN` caps the pool's — the raise must still fit the
  declared 1280×1000 frame. **It is the shipped file's own row count and it
  moves when that file does:** it was 15 (thirteen sets plus two headings) and
  became **16** on 2026-08-11, when `Claude Tools` joined (task 219). The
  runtime Qt audit convicted this window of BUG A the same run the set was
  added — the list scrolled while the pool table beside it held 145 px of idle
  space — so a set added to `actions.json` raises this number in the SAME
  commit, or the ladder's first step is skipped by arithmetic.
- **Result, measured:** 723×956 → **733×950**, with all fifteen list rows AND
  all thirteen pool rows visible, no scrollbar anywhere, in both palettes.
  What remains is ~124 px of empty grid under the pool's last row — the right
  column is now the SHORTER one, and its stretch lands in the table, directly
  above its own "Add command" button. Nothing is hidden by it.
- **And the tooth was fixed with the window** — `tests/test_layout_audit_qt.py`
  could not see this failure at all: its SCROLL+SLACK check counted only
  `QSpacerItem`s on the path up to the window, and this slack was a stretched
  SIBLING. `idle_view_slack` now measures every item view's viewport against
  its own rows. Self-tested by rebuilding the pre-round layout, which the
  audit now fails, naming the idle list and its 356 px.

The measurement happens in `showEvent`, not in `__init__`: the theme reaches
this dialog through its parent's stylesheet and Qt resolves the QSS font and
padding only when the widget is polished. Measured in the constructor, every
string came out in the DEFAULT font — about 8% narrower than the theme's —
and the wheel checkbox and the set list were cut at the resulting minimum.
The audit caught exactly that, once its factory started applying the theme
the way the app does.

The command table takes the right column's free height (no widget carries a
hard size), and every editor field owns a full-width row — the two failures the
law names (a list scrolling beside empty space, a shortcut rendered "ift+tab")
cannot recur here. Proof: [tests/test_layout_audit_qt.py](../../../tests/___tests.md).

## Connections

### Uses
- [Controls Data](controls_data.md) — every actions.json path/parse/merge
  function, plus `natural_order`/`effective_wheel_order` (build round R5).
  This module owns NONE of that plumbing itself since 2026-08-07 — it calls
  in, it does not implement
- [Controls Widgets](controls_widgets.md) — `CommandDetail`, `CommandTable`,
  `icon_for`
- [Controls Order](controls_order.md) — `OrderList` (per-set arrangement) and
  `WheelOrderDialog` (the new global wheel order)
- [Config](../../__about/config.md) — indirectly, through Controls Data
- client/icons.js / client/controls.js — indirectly, through
  `load_client_icons`/`load_client_builtins`
  ([Icons](../../../client/__about/icons.md),
  [Controls](../../../client/__about/controls.md))

### Used by
- `gui/main_window.py` (see [GUI (subfolder)](../___gui.md)) — the
  "Controls…" button opens `ControlsEditor(self).exec()`

## Classes

- **`SectionDelegate`** — paints the set list's three section headings and
  each set's own wheel tick (stays in THIS module — it is the set list's own
  presentation, not a reusable widget the way the command/order widgets are).
- **`ControlsEditor`** — the dialog: set list (built-ins and app sets
  flagged), `_store_current` writes screen → RAM on every selection change,
  `_tick_changed` keeps the D-pad at four and says so on screen when a fifth
  is tried, `_open_wheel_order` opens `WheelOrderDialog` (build round R5,
  2026-08-07) and writes its result into `self.data["wheel_order"]` on OK,
  `_save` validates (empty sets warned, shown-by-default clamped to
  `WHEEL_MAX`) and writes the file.

The command-editing widgets (`ChordRecorder`, `CommandDetail`,
`CommandTable`) live in [Controls Widgets](controls_widgets.md); the
arrangement/order widgets (`SlotList`, `OrderList`, `WheelRing`,
`WheelOrderDialog`) live in [Controls Order](controls_order.md); every
actions.json path/parse/merge FUNCTION lives in
[Controls Data](controls_data.md) — this module (since build round R5,
2026-08-07) owns only the WINDOW that assembles them.

## The third command kind (build round R6, 2026-08-07)

The pool table (`CommandTable.fill`) already read a typed command correctly
("types · /usage"); the detail panel below it did not — `CommandDetail` had
no branch for `{"text": …}` at all, so the SAME selected row showed "Shortcut
(chord)" with an empty field and a live Record button. One window told two
contradicting stories about one button — an independent grader's screenshot
of the ControlsEditor found it directly, three centimetres under the fixed
half of the same bug. Full detail: [Controls Widgets](controls_widgets.md).
The fix touches only the detail form (a third `Does` option, a Text row that
shows exactly when the Shortcut row does not); nothing about SAVING,
MERGING or the wheel changed, so this window's minimum barely moved
(723×956 unchanged in practice — the two rows are mutually exclusive, so the
detail form still shows exactly four rows at a time).

## App sets charge the wheel here too (owner 2026-08-06)

`_save()` used to state that app sets never charge the wheel count — written
2026-08-05 and reversed by the owner the next day. That line was the DESKTOP
half of what he found on his phone: nine sets ticked under a cap of eight.

The editor now computes the same reserve the phone does — the largest group of
app sets sharing a `process`, because Chrome, Explorer and VSCode can never
appear together while VSCode and Claude always do — and leaves
`WHEEL_MAX - reserve` for everything else. The message says which, and why,
instead of quietly switching sets off.
