# Layout creation

**Scripts:** [layout-create.js](../layout-create.js) ·
[layout-create.css](../layout-create.css) ·
**Flow:** [diagrams](../__flow/layout-create.md) ·
**Folder:** [Client](../___client.md) ·
**Living with layouts:** [Layouts](layouts.md)

One feature, two files, one doc — the `layouts.css`/`layouts.js` precedent.
The stylesheet holds only what the creation panel's ROWS need beyond the
layout list's own (`.lay-item` / `.lay-item-main`, reused rather than copied):
the indent a tab wears under its window, the dim an unavailable control wears,
and `touch-action` put back, because a row here is never carried and the list
must still scroll.

## Purpose

Making a layout — and only that. The source chooser, the armed canvas tap, the
slot panel, and the single `layout_create` that ends the session.

Split out of [Layouts](layouts.md) on 2026-08-08, when the ✕ chooser (task 116)
pushed `layouts.js` past THE STRUCTURE LAW's 1,000 lines. The boundary is a
responsibility, not an arithmetic cut: this file is a WIZARD. It owns one piece
of state (`creating`), gathers slots across several taps, and is finished the
moment the layout exists. `layouts.js` is everything you do once layouts DO
exist — the bar, the list, rename, the aspect panel, the ✕.

Both halves render into the same overlay (`#layout-panel`) and share its
vocabulary, so the phone never has two competing card styles.

## Connections

### Uses

- [Layouts](layouts.md) — `layPanel`, `closeLayoutPanel`, `layChip`,
  `chooserBtn`, `nameField`, `showLayLoading` / `hideLayLoading`, and the
  `.lay-item` / `.lay-item-main` ROW markup its stylesheet owns. (`titleChip`
  and `.lay-chip.lay-title` — the wrapping title pill both lists used to be
  made of — were DELETED on 2026-08-09: this panel was their only caller, and
  task 168 turned both lists into real rows.)
- [Controls](controls.md) — `keepFocus`, `svg`, `showToast`
- [State](state.md) — `send`, `layoutArm`
- [Loading](loading.md) — `creating` (the session object lives there)
- [Grids](grids.md) — `GRID_CELLS`, how many slots a template needs

### Used by

- [Gestures](gestures.md) — an armed canvas tap sends `layout_pick`, then
  calls `refreshNewlayButton()`
- [Connection](connection.md) — `handleLayoutOffer(msg)` on every
  `layout_offer` frame
- [Layouts](layouts.md) — the backdrop tap cancels a creation session rather
  than closing the panel under it

## Key Functions & Data

| Name | What it does |
|------|--------------|
| `creating` | The whole session: `{source, entries, slots, name, mode, grid, orient, awaitingTap}`. `null` when no layout is being made. Declared in [Loading](loading.md), which needs it for the overlay. |
| `newCreation(source)` | A fresh session, `"list"` or `"tap"`. |
| `openSourceChooser()` | The two-act card: **From a list** (`layout_list`) or **Tap a window**. |
| `armNextTap()` | `layoutArm = true` — the NEXT canvas tap picks a window instead of moving the cursor. One shot. |
| `handleLayoutOffer(msg)` | Both answers: `entries` (the whole list) or one tapped `target`/`tab`. |
| `slotFromOffer` / `slotFromEntry` | The two sources reduced to ONE slot shape, so the panel below never asks where a slot came from. |
| `cellsNeeded()` | How many slots this mode still wants — 1 for solo, the template's cell count for a grid. |
| `availableMembers()` | How many members this desktop can really fill — the cap on the shape chooser AND the count in the list header. `null` for the tap source, where nothing is enumerated. |
| `ownTabConflict(slot)` | Is this slot the window of a chosen tab, or the tab of a chosen window? Those two cannot stand together. |
| `entryRow(opts)` | One row of either list: `{label, icon, tab, note, selected, off, onTap}`. A tab is drawn indented and carries no app icon. |
| `renderCreationPanel()` | The slot panel: mode, orientation, the chosen slots, the name field, Create. |
| `cancelCreation(silent)` | Ends the session and clears `layoutArm` — the + button's second tap, the backdrop tap, and Cancel all land here. |
| `refreshNewlayButton()` | Lights the + button while a session or an armed tap is live. |

## Design Decisions

- **Two sources, one slot shape.** A window picked from the list and a window
  tapped on the stream reach the panel as the same object. Everything after
  the pick is written once.

- **The armed tap is one shot.** `layoutArm` clears the moment the tap is
  spent, so a forgotten arm can never turn a later cursor move into a pick.

- **A grid takes one tap per cell.** `cellsNeeded()` is what the panel counts
  against, and its label says which cell is being asked for — "Tap window 2 of
  4" — because a silent wait for more taps reads as a broken button.

- **The shape chooser is capped by what can fill it** (owner report
  2026-08-09, task 166: *"it offers a grid of 4 when the desktop holds 3"*).
  There was no cap of any kind — the 2/3/4 chips were an unconditional
  literal, `cellsNeeded()` read the mode and never looked at what was open,
  and the token `entries.length` appeared nowhere in the client.

  **The quantity is not `entries.length`**, and that is the whole subtlety: a
  VS Code with three tabs emits FOUR entries (the window plus its tabs) and
  still cannot yield four independent members. What a window is worth is *the
  tabs that can be extracted, plus the window itself only if at least one tab
  stays in it* — take k of its N tabs and you hold k windows plus the original
  while `k < N`, which is **N** either way. So a window offering N ≥ 2 tabs is
  worth N, a window offering none is worth 1, and `availableMembers()` sums
  that over the windows. (Since task 167 the server never offers a lone tab; a
  `1` could only come from an older PC, and 1 is the honest answer for it too.)

  A shape that cannot be filled is not drawn, the missing chips are explained
  in one line, and a chosen shape the desk can no longer fill is stepped down
  rather than left unreachable.

- **An unavailable control says so, twice.** A not-ready Create used to carry
  no disabled state, no dimming and no word: it looked live and swallowed the
  tap, which is the half the owner actually feels. It is dimmed (`lc-off`,
  `aria-disabled`) **and** it answers a tap with what is missing — "Pick one
  more window first". It deliberately stays tappable: a truly disabled button
  cannot answer, and "why is nothing happening" is the complaint.

- **A window and one of its own tabs cannot both be chosen** (task 167). The
  tab is torn out of the very window standing in the cell beside it, so the
  layout would hold one window twice — and when extraction fails (six visible
  seconds of synthetic mouse drag) the fallback IS that window, so both cells
  name it outright. Conflicting rows are dimmed and refuse with a word. Two
  different tabs of one window are fine and are the point of tab layouts.

- **A tab is drawn INDENTED under its window, in both lists** (owner
  2026-08-09, task 168, in translation): *"the indentation stays — a column.
  It does not have to be the same row as its parent, because a sub-tab of a
  window does NOT belong to the same kin group as its parent; that is exactly
  why a minimal indent is allowed… Right now there are arrows, but that is
  less noticeable and less intuitive."*

  Both lists were a wrapping FLOW of pills, which has no per-row box to indent
  at all — a tab was marked by a literal `"↳ "` glued to its title. They are
  real rows now; his kin ruling is what makes the narrower child legal under
  task 163, and the indent is exactly the icon column (20 px icon + 10 px gap)
  so a tab's title lands under its parent's title while its box sits visibly
  further in. In the CHOSEN list the parent is never a row beside it — a
  window and its own tab can no longer be chosen together — and the indent
  there says the thing that still matters at a glance: this member is a tab.
  Slot ORDER is never re-grouped; slot 1 names the layout and each one after
  it is a cell.

- **The icon belongs to the window.** It used to be drawn for the wrong one of
  the two: a tab wore its PARENT's app icon among the chosen slots and no icon
  at all in the list below — the same tab drawn two ways, one of them claiming
  to be an app. A tab is marked by the indent and by nothing else.

- **A minimized window says why it shows no tabs.** Windows reports it as
  having no size, so it enumerates zero tabs whatever it holds; the server
  refuses to ask and sends `tabs_hidden` ([UIA](../../server/__about/uia.md)),
  and the row carries a `minimized` note with one line under the list. A list
  that silently changes shape between two openings is the defect.

- **The name is prefilled and overridable** (owner 2026-08-05): the first
  slot's window title is offered, an empty field keeps it, and anything he
  types wins. `Layout.title` on the server keeps the ORIGINAL title whatever
  he renames it to — the app-set match reads that, never the name.

- **The loading overlay covers the real work, not the reply.** Tab extraction
  takes visible seconds on the PC; `showLayLoading` opens before the message
  goes out and closes when the streamed screen actually stops moving
  ([Loading](loading.md)).
