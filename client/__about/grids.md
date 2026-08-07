# Grids (phone) — the shapes, drawn

[← client](../___client.md) · code: [grids.js](../grids.js)

The grid catalogue as the phone shows it: which shapes exist, what each one
looks like, and the one panel that asks the owner to choose between them.
Mirrors [server/grids.py](../../server/__about/grids.md) shape for shape — if
one changes, the other must.

Split out of [Layouts](layouts.md) on 2026-08-07 (THE STRUCTURE LAW) when the
owner's grid sheet pushed that file past 1,000 lines. Loaded BEFORE layouts.js:
`GRID_CELLS` is a const the list and the creation panel read at runtime.

## What it holds
- `GRID_CELLS` / `GRID_THREE` / `GRID_LEGACY` / `gridOf(g)` — the catalogue and
  the mapping for layouts made before 2026-08-07.
- `gridSketch(grid, orient)` — the shape as a small inline SVG of real
  rectangles. **A grid choice is a picture, not a word** (owner 2026-08-07 — he
  sent a sheet of drawings, not a list of names), and it is drawn rather than
  written for the same reason every icon in this project is: a font glyph came
  out a blunt cross on his device once already.
- `gridChip(...)` — that sketch as a tappable chip.
- `mergeLayouts(source, target)` — dropping one layout onto another. 1+1 and
  1+3 have exactly one possible shape, so nothing is asked; **1+2 becomes a
  THREE and a three has four arrangements**, which is the one case where he
  chooses. A full four refuses, and the list greys it while a drag is in
  flight so the refusal is visible before the finger arrives.

## Used by
- [Layouts](layouts.md) — the creation panel, the layout list's drag, the
  layout settings panel
