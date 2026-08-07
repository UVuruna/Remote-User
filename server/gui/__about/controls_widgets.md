# Controls Editor — Command Widgets

**Script:** [Controls Widgets (script)](../controls_widgets.py) ·
**Flow:** [diagram](../__flow/controls_widgets.md)

## Purpose

The COMMAND-editing widgets the [Controls Editor](controls_editor.md) is
assembled from — "what does a command DO and how is it EDITED". First split
out of the dialog module when it reached the STRUCTURE LAW's 1,000-line
threshold (2026-08-05); split AGAIN in build round R5 (2026-08-07), when the
owner's "choose the wheel order" round pushed the dialog module back toward
the threshold — the arrangement/order widgets (`SlotList`, `SlotDelegate`,
`OrderList`, and the new wheel-order ring) answer a different question
("WHERE does a thing sit") and moved to
[Controls Order](controls_order.md); the pure data plumbing (`button_id`,
`DPAD_SLOTS`, every actions.json path/parse/merge function) moved to
[Controls Data](controls_data.md), the one place that needed it with no
`QApplication` in sight.

| Widget | What it is |
|--------|------------|
| `RowDelegate` | takes a selected row's painting away from the native style — see below |
| `CheckDelegate` | the pool table's "On" column, drawn with `paint_check` |
| `ChordRecorder` | a modal that RECORDS a key combination from the PC keyboard (chords are pressed, never typed) |
| `CommandDetail` | the selected pool command — one field per full-width row; on a built-in row every field is read-only EXCEPT the name (owner 2026-08-05) |
| `CommandTable` | the set's whole POOL with a tick on the four that ride the D-pad |

Defined here because they describe how a command is DRAWN: `icon_for()`
(client icon fragment → `QIcon`), `BUILTIN_ACTIONS`, `QT_NAMED_KEYS` and the
`KIND_*` markers. `button_id()` — a command's stable identity — moved to
[Controls Data](controls_data.md) in round R5 (`CommandTable` imports it back
from there). The dependency still runs one way: the dialog imports this
module, never the reverse.

## Connections

### Uses
- [Controls Data](controls_data.md) — `button_id()`
- `client/controls.js` — indirectly: the icon fragments and built-in labels
  the dialog parses are what `icon_for()` and `CommandDetail` draw

### Used by
- [Controls Editor](controls_editor.md) — `CommandDetail`, `CommandTable`,
  `icon_for`
- `tests/test_layout_audit_qt.py` — `ChordRecorder` is one of the audited
  windows

## Design Decisions

- **The widgets know nothing about the file.** Nothing here reads or writes
  `actions.json`; `CommandDetail.dump()` returns a plain dict and the dialog
  decides where it goes. That is what makes the split honest rather than
  cosmetic.
- **`BUILTIN_ACTIONS` is a FALLBACK only.** The real list of built-in actions
  is the client's `BUILTINS` table, parsed at open time; this constant exists
  for the case where `client/controls.js` cannot be read.
- **The pool table turns Qt's eliding OFF** (`ElideNone`) — the law demands
  that nothing the owner must read is cut, and Qt's default is to truncate
  item text silently.
- **`CommandTable.ROWS_SHOWN` is 13** — the largest pool the shipped file has
  (Claude). It was 6, then 10, and at 10 an independent grader measured three
  of thirteen commands behind a scrollbar with ~253 px of idle set list beside
  them. The raise is ladder step 3 and it only became affordable once step 2
  was actually done: the Arrangement box moved into that idle column
  ([Controls Editor](controls_editor.md)). A longer pool scrolls, which is the
  ladder's own last step rather than a shortcut past its first.

## ONE TICK, ONE SELECTION (2026-08-07)

An independent grader counted **three tick affordances on one screen** — a bare
checkmark glyph in the set list (and NOTHING at all for a set that is switched
off, so "off" and "not switchable" looked identical), a native empty square in
the commands table, and the QSS-styled blue box under both — plus **two
accents**, because a selected row wore the WINDOWS system accent (gold on the
owner's PC) against this app's blue.

Both are answered here, and both had to be answered in PAINTING rather than in
QSS: a stylesheet reaches `QCheckBox::indicator` and nothing inside an item
view, because an item is not a widget.

- **`paint_check(painter, rect, on, locked)`** — one 16 px box, radius 5,
  matching the QSS checkbox exactly, in three readable states: empty (off and
  switchable), accent-filled (riding), accent WASH with a dim tick (riding and
  `required`, not the owner's to switch — his own rule of 2026-08-06 that a
  tick must not promise a choice he does not have). Used by the pool table's
  `CheckDelegate` and by the set list's `SectionDelegate`.
- **`RowDelegate.take_selection`** fills a selected row in `accentDim` and
  CLEARS `State_Selected` before anything else paints. Two fills, and the
  first one is load-bearing: the view has already drawn the native selection
  under the delegate, and `accentDim` is a 14–16 % wash, so a single
  translucent fill left the gold bar showing straight through (still measured
  at (197, 210, 101) after the first attempt). The card colour goes down to
  ERASE, the wash on top to colour. `SectionDelegate` and `SlotDelegate`
  ([Controls Order](controls_order.md)) both inherit it.

## Build round R3 (2026-08-07) — themes

`ICON_STROKE = "#cbd5e1"` was the last hardcoded colour in the GUI package —
a pale slate that reads correctly on the dark list and all but disappears on a
white one. It is `icon_stroke()` now, returning `TOKENS["text2"]`, read at
draw time for the same reason `theme.qss()` is a function.
