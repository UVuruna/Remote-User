# Controls Editor — Widgets

**Script:** [Controls Widgets (script)](../controls_widgets.py) ·
**Flow:** [diagram](../__flow/controls_widgets.md)

## Purpose

The widgets the [Controls Editor](controls_editor.md) is assembled from. They
were split out of the dialog module when it reached the STRUCTURE LAW's
1,000-line threshold (2026-08-05): the dialog owns *loading, assembling and
saving* `actions.json`, this module owns *the pieces the owner touches*.

| Widget | What it is |
|--------|------------|
| `ChordRecorder` | a modal that RECORDS a key combination from the PC keyboard (chords are pressed, never typed) |
| `SlotDelegate` | draws an arrangement row as rich text (the portrait ordinals' superscript) |
| `SlotList` | a list that asks for exactly the height of its rows (SPACE & LEGIBILITY, ladder step 1) |
| `OrderList` | one orientation's arrangement: the fixed slot ladder + the four commands + Up/Down |
| `CommandDetail` | the selected pool command — one field per full-width row |
| `CommandTable` | the set's whole POOL with a tick on the four that ride the D-pad |

Shared with the dialog and defined here, because they describe how a command
is DRAWN or IDENTIFIED: `icon_for()` (client icon fragment → `QIcon`),
`button_id()` (a command's stable identity — what `active` stores),
`DPAD_SLOTS`, `LAND_SLOTS` / `PORT_SLOTS`, `BUILTIN_ACTIONS`, `QT_NAMED_KEYS`
and the `KIND_*` markers. The dependency runs one way: the dialog imports
this module, never the reverse.

## The slot ladder belongs to the POSITION (owner fix 2026-08-05)

`OrderList` shows *where* each of the four active buttons sits. The first
version wrote the slot name into the item's own text, so raising a command
carried its old name up with it and the left column read
`Top · Left · Bottom · Right` — the owner's screenshot. Now an item holds
only the command (`INDEX_ROLE` = its index into the active four, `LABEL_ROLE`
= what the phone will print on it) and `_relabel()` re-draws the ladder from
the row numbers after every move. The ladder therefore cannot reorder — only
the commands travel through it.

The two orientations get different ladders, because a portrait column has no
left and no right:

```
Landscape (D-pad cross)        Portrait (column)
  Top     · Sidebar              1ˢᵗ · Sidebar
  Left    · Palette              2ⁿᵈ · Palette
  Right   · Find                 3ʳᵈ · Find
  Bottom  · Terminal             4ᵗʰ · Terminal
```

The ordinals are real superscript, built by Qt's rich text out of the
dialog's own font (`SlotDelegate`) — never a special character. That is the
same day's ✥ lesson: a glyph that renders on the build machine can arrive as
a blunt box on the owner's device, so nothing user-visible may depend on
exotic font coverage. The delegate measures the RENDERED width
(`QTextDocument.idealWidth`), so the runtime layout audit's item-view check
still sees the truth instead of the markup.

## Connections

### Uses
- [Config](../../__about/config.md) — nothing directly; the paths and the
  client-table parsing stayed with the dialog
- `client/controls.js` — indirectly: the icon fragments and built-in labels
  the dialog parses are what `icon_for()` and `CommandDetail` draw

### Used by
- [Controls Editor](controls_editor.md) — the dialog imports every widget,
  `icon_for`, `button_id` and the slot/kind constants
- `tests/test_layout_audit_qt.py` — `ChordRecorder` is one of the three
  audited windows

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
