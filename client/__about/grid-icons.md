# Grid Icons

**Script:** [Grid Icons (script)](../grid-icons.js) ·
**Folder:** [client](../___client.md)

## Purpose

WHAT SHAPE a layout is, as a drawing — the pure geometry behind every little
grid diagram the phone shows. One silhouette per **(member count, arrangement,
orientation)**, returned as rects and as SVG/`Path2D` path data. Loads before
[Grids](grids.md), which delegates the creation panel's chips to it, and
before [Layouts](layouts.md), whose list draws each row's shape with it.

## Why it exists (owner request 2026-08-09, task 164)

A row in the layout list carried a name and nothing about its shape, so a solo
window, a two-split and a four-grid read identically until he opened one. The
row now draws the real arrangement from what `layout_state` already carries —
`grid`, `members`, `orient`.

The rule it obeys is older than the request. The catalogue arrived on
2026-08-07 as a **sheet of drawings** (`UV/grid_variations.png`) with an
instruction attached: *"GRID kada korisnik bira budu skice ... a ne tekstovi
tipa 'GRID 2x1'"* — a grid is chosen, and now also **recognised**, by LOOKING.
And never with a font glyph: he has already been shipped a character that came
out wrong on his own phone (the ✥ move handle rendered as a blunt cross,
2026-08-05). [Icons](icons.md) is the app's stroked 24×24 half of that rule,
[Cursor Shapes](cursor-shapes.md) its canvas half; this is the third family,
separate because a grid icon is a *partition of a box* whose own aspect leans
with the orientation, not a symbol on a fixed square.

## The catalogue — his sheet, exactly

Two columns (LANDSCAPE, PORTRAIT), three rows (2, 3, 4 windows):

| Windows | Arrangements | Names |
|---------|--------------|-------|
| 1 (solo) | 1 — no grid at all | `null` |
| 2 | 1 | `2` |
| 3 | **4** | `3-top`, `3-bottom`, `3-left`, `3-right` |
| 4 | 1 | `4` |

**6 grid shapes + solo = 7, and 14 with the orientations.** The asymmetry is
the rule: only a THREE has an arrangement to choose (`gridIconChoices`), a two
and a four may flip portrait/landscape and nothing else — there is only one
sane way to cut a region into two or into four.

Only `2` changes its **partition** with orientation (the server splits a
portrait region into rows and a landscape one into columns). The other six keep
their partition and lean their **box** instead — which is load-bearing, not
decoration: on a fixed square a portrait three and a landscape three would be
drawn pixel-for-pixel identical, the exact "choose by reading, not by looking"
failure the drawings exist to kill.

## Key Functions

- `gridIconBox(orient)` — the viewBox, `[30, 20]` landscape / `[20, 30]`
  portrait.
- `gridIconShape(count, grid)` — which shape to draw, and how many of its
  cells. Never throws: a known name wins; an unknown name with a real count
  falls back to the default shape for that count (the server's own default, so
  a layout from a NEWER server still draws the right number of windows);
  anything else is the solo rectangle.
- `gridIconRects(count, grid, orient)` — the cells in viewBox units, in
  **member order**, each `{x, y, w, h, r}`. Cell *k* is member *k*, which is
  what lets a panel point at a window by pointing at its square.
- `gridIconPath(count, grid, orient, cells?)` — the drawing as one path `d`
  (also valid for `new Path2D`). The optional index array is how one cell is
  drawn lit and the rest faint, without a second geometry.
- `gridIconSvg(count, grid, orient, opts?)` — the markup for `innerHTML`.
  `opts.cell` lights one member; `opts.className` adds a class.
- `gridIconChoices(count, grid)` — the four three-arrangements, or `[]`.

## Design Decisions

- **Pure by design** (no DOM, no socket, no bridge — the [Caret](caret.md) /
  [View Anchor](view-anchor.md) pattern): `tests/test_grid_icons.py` runs the
  module WHOLE in node. It builds markup, which is a string; it must never
  reach a document, and the gate's purity check fails the build on one.
- **The picture is compared to the DESK.** The gate checks every partition,
  number for number and in member order, against the real
  [`server/grids.py`](../../server/__about/grids.md) `_cells` — the arithmetic
  that actually places his windows. `grids.js` has carried a note since it was
  split off ("if one changes, the other must") and nothing had ever checked it.
- **Fewer live members than cells draws fewer cells.** A window closed at the
  desk is pruned and the template is left alone; `LayoutRegistry.focus` then
  places the survivors into the FIRST cells. A four holding three really does
  show three quadrants and a gap, so the picture says so instead of pretending
  to be a tidy three.
- **One copy of the shapes on this side.** `grids.js` delegates
  `gridSketch`/`soloSketch`/`orientBox` here and `GRID_THREE` is this module's
  list — the partitions were about to have a third copy.

## Used by

- [Grids](grids.md) — the creation panel's chips and the merge chooser
- [Layouts](layouts.md) — **wired 2026-08-09**: each list row's shape button
  (`gridIconSvg(lay.members, lay.grid, lay.orient)`, a `<span>` for a solo),
  the member chooser's per-row badge (`{cell: k}` — one cell lit, the rest at
  0.3 opacity, which is what lets him point at a WINDOW by pointing at its
  square) and the one arrangement a 4→3 asks about (`gridIconChoices`)
- `tests/test_grid_icons.py` — the gate, fail-closed in `setup/build.py` (0s/6)
- `tests/test_layout_audit.py` — `__memberCells` proves on the LIVE page that
  every member row lights a different square; a pure module can say the paths
  differ, only the page can say they reached four different rows
