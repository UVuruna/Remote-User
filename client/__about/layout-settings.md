# Layout Settings

**Script:** [Layout settings (script)](../layout-settings.js) ·
**Flow:** [the layout list's diagram](../__flow/layouts.md)

## Purpose

Everything a layout that ALREADY EXISTS can be asked: the per-layout **⚙
sheet** and the panels it opens — Rename, Aspect ratio (with its Move handle),
Orientation, Arrangement, and the door to the member chooser.

Split out of [Layouts](layouts.md) on 2026-08-09, when that file crossed THE
STRUCTURE LAW's 1,000 lines. The seam is the one
[Layout Create](layout-create.md) was cut on: `layouts.js` is what you use to
LIVE with the layouts that exist (the bar, the list, the drag, the ✕, the
member chooser), `layout-create.js` MAKES one, and this file CHANGES one's
properties.

## Why it exists (owner 2026-08-09, task 175)

Every act on an existing layout kept arriving as its own icon on the list's
row — a rename pencil, an aspect chip, then the drawn shape badge — and task
165 was about to add a fourth. His instruction was to put all of it under one
common settings icon instead of one icon per thing
(*"sve to treba ubaciti pod neku zajedničku settings ikonicu"* — lang-ok: owner quote),
and the portrait list had been honestly graded **6/10** for exactly that
crowding. The row is `[icon][⭐][name][shape][⚙]` now: the two facts it can
carry at a glance, plus one door.

The second half of the same task is a thing he could not do **at all** before:
a layout built portrait had to be DELETED and made again to become landscape.

## Connections

### Uses
- [Layouts](layouts.md) — `layPanel`, `closeLayoutPanel`, `layChip`, `layRow`,
  `nameField`, `openLayoutPicker`, `openMemberPanel`, and `HOLD_DRAG_SLOP`
  **at load** (the Move handle's tap slop is derived from the row hold's — one
  digitizer, one number), which is why it loads immediately after it
- [Grids](grids.md) / [Grid Icons](grid-icons.md) — `gridSketch`, `soloSketch`,
  `orientChips`, `gridChip`, `gridIconChoices`
- [Controls](controls.md) — `keepFocus`, `svg`, `showToast`
- [State](state.md) — `send`, `layouts`

### Used by
- [Layouts](layouts.md) — the row's ⚙ calls `openLayoutSettings(index)`, and
  `closeLayoutPanel()` calls `forgetLayoutSettings()` (the overlay is ONE
  element with several contents; only the content's own file knows what state
  it left behind)
- [Layout API](../../server/__about/layout_api.md) /
  [Web Layer](../../server/__about/web.md) — the other end of
  `layout_rename`, `layout_aspect` and `layout_grid`

## Key Functions & Data

- **`openLayoutSettings(index)`** — the sheet. Its content follows what the
  layout IS: a SOLO layout has no window to throw out and no arrangement to
  choose, so neither is drawn — a control that cannot act is a promise the
  panel cannot keep (the same rule that makes a solo row's shape badge a plain
  `<span>`). The rows are the list's own `.lay-item` markup via `layRow`, so
  the ellipsis, the badge sizing and the kin rule are written once; `lay-menu`
  only puts `touch-action` back, because a row of the LAYOUT LIST is a drag
  surface and this one is never carried.
- **`sendLayoutShape(index, grid, orient)`** — the one sender for both
  pickers. Sends `layout_grid {index, grid, orient}`, closes the sheet and
  raises the loading cube, because real windows move on the PC. A tap on what
  is already true sends nothing.
- **`openRenamePanel(index)`** — the name, and nothing else since task 175
  (between 2026-08-07 and today it also carried the shape chooser, because the
  row had no other door to put them behind).
- **`openAspectPanel` / `renderAspectPanel` / `updateAspectPreview` /
  `aspFrac` / `clampAspect` / `dragAspect` / `dragMove` / `ratioPair` /
  `devicePair` / `ratioLabel`** — the aspect-ratio panel, moved here whole.
  Its rules are unchanged and are documented in [Layouts](layouts.md) →
  Design Decisions (the shrink-only clamp, the continuous ratio, the whole
  preview as the drag surface, the Move handle and its double-tap).
- **`forgetLayoutSettings()`** — what `closeLayoutPanel` calls to drop
  `aspecting`.

## Design Decisions

- **Two kinds of control, and the difference is deliberate.** Rename, Aspect
  ratio and Take one window out are DOORS — they open the panel that owns that
  act, with its own Apply. Orientation and Arrangement are the act ITSELF: one
  tap sends it, closes the sheet and raises the cube, because they are
  single-choice pickers and the owner's rule for those is that picking IS the
  command (*"korisnik odabere a program automatski odradi"*, 2026-08-05 —
  lang-ok: owner quote). A sheet that mixed pending state with doors would
  need an Apply that some of its rows ignore.
- **Cancel is one step back, and the chain is list → ⚙ sheet → panel.** The
  row's shape badge is a SHORTCUT into that chain (it opens the member chooser
  directly), so backing out of it lands on that layout's sheet rather than on
  the list — breadcrumb behaviour, one rule, no state to keep.
- **A picture per choice, never the word alone.** `orientChips` draws the
  layout's OWN shape once per orientation, and the arrangement chips are the
  four drawings of his sheet — the rule the grid catalogue was delivered under
  (2026-08-07: the choice is made by LOOKING, never by reading "3-left").
- **`gridIconChoices` is asked, never re-derived.** A 2 and a 4 have exactly
  one arrangement each and a 3 has four; the asymmetry lives once, in the pure
  module, so no panel can offer him a choice that does not exist.
- **The card takes two columns in landscape** (`card-columns`), measured: this
  is the "panel of many SHORT items" side of the `panels.css` rule — its rows
  carry fixed labels, not window titles — and in one column the fullest sheet
  is 121 px taller than a 915×412 phone allows, which is BUG A with 155 px of
  width standing idle. The sub-heading (the layout's NAME) is the one long
  string, so it takes the list row's own treatment: one line, cut by CSS, with
  the full name one tap away in the Rename card directly below it.
- **`layout_grid` needed nothing new on the server** — the message has existed
  since 2026-08-07 for a three's arrangement. What it did NOT have was a gate:
  no test in this project drove it, so "the server already has it" was a claim
  about a name. `tests/test_layout_shape.py` now asserts the RECTS, because a
  shape change the phone shows and the PC ignores is the Move handle's bug in
  a new place.
