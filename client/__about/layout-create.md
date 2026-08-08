# Layout creation

**Flow:** [diagrams](../__flow/layout-create.md) ·
**Folder:** [Client](../___client.md) ·
**Living with layouts:** [Layouts](layouts.md)

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
  `titleChip`, `chooserBtn`, `showLayLoading` / `hideLayLoading`
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

- **The name is prefilled and overridable** (owner 2026-08-05): the first
  slot's window title is offered, an empty field keeps it, and anything he
  types wins. `Layout.title` on the server keeps the ORIGINAL title whatever
  he renames it to — the app-set match reads that, never the name.

- **The loading overlay covers the real work, not the reply.** Tab extraction
  takes visible seconds on the PC; `showLayLoading` opens before the message
  goes out and closes when the streamed screen actually stops moving
  ([Loading](loading.md)).
