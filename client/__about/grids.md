# Grids (phone) — the shapes, drawn

[← client](../___client.md) · code: [grids.js](../grids.js)

The grid catalogue as the phone shows it: which shapes exist, what each one
looks like, and the one panel that asks the owner to choose between them.
Mirrors [server/grids.py](../../server/__about/grids.md) shape for shape — if
one changes, the other must.

Split out of [Layouts](layouts.md) on 2026-08-07 (THE STRUCTURE LAW) when the
owner's grid sheet pushed that file past 1,000 lines. Loaded BEFORE layouts.js:
`GRID_CELLS` is a const the list and the creation panel read at runtime.

> **The drawings moved out on 2026-08-09** (owner request, task 164 — the
> layout LIST now draws each row's shape too). The partitions, the outer box
> and `GRID_THREE` live in [Grid Icons](grid-icons.md), a PURE module whose
> gate runs it whole and compares every partition to `server/grids.py` number
> for number; the three functions below are one-line delegations now. This
> file keeps what it always was about — which shapes exist, and the panels
> that OFFER them. The move happened because the partitions were about to have
> a third copy, and this page's own warning ("if one changes, the other must")
> had never been checked by anything.

## What it holds
- `GRID_CELLS` / `GRID_THREE` / `GRID_LEGACY` / `gridOf(g)` — the catalogue and
  the mapping for layouts made before 2026-08-07. `GRID_CELLS` maps a shape to
  a COUNT (how many windows fit — the wheel-cap's question); `GRID_THREE` is
  [Grid Icons](grid-icons.md)' own list, held once because "only a three has an
  arrangement" is a rule and a re-derived rule is one a panel can get wrong.
- `orientBox(orient)` — the 2x2-unit outer box every sketch is drawn on:
  `30x20` for landscape, `20x30` for portrait (round 3, 2026-08-07,
  re-reading his own sheet: the landscape column draws EVERY shape — 2, 3, AND
  4 — in a landscape-leaning box, the portrait column in a tall one; the cell
  partition inside a three or a four is the SAME shape, only the box changes).
  Now `gridIconBox`.
- `gridSketch(grid, orient)` — the shape as a small inline SVG, laid out on
  `orientBox(orient)`; now `gridIconSvg`. **A grid choice is a picture,
  not a word** (owner 2026-08-07 — he sent a sheet of drawings, not a list of
  names), and it is drawn rather than written for the same reason every icon
  in this project is: a font glyph came out a blunt cross on his device once
  already. Round 1 (2026-08-07) got the cell PARTITION right (already graded
  9/10 for the arrangement chips) but drew every partition on a fixed square
  box, so only `"2"` — whose partition genuinely flips with orientation — was
  actually distinguishable landscape vs. portrait; a landscape THREE and a
  portrait THREE were pixel-identical, distinguished only by which chip was
  lit. Round 3 (2026-08-07, same day) fixed the box itself to lean wide/tall
  with `orient`, exactly like his sheet — the partition inside stays whatever
  it already was, additive, `"2"`'s existing flip untouched.
- `gridChip(...)` — that sketch as a tappable chip.
- `soloSketch(orient)` — the "only one window" picture: a single rectangle
  filling `orientBox(orient)` — a solo window has no cells to split, so the
  box shape is the only picture its orientation has to show. This is the
  function round 3 made the rest of the catalogue consistent with; now
  `gridIconSvg(1, null, orient)`.
- `shapeChip(sketchHtml, caption, selected, onTap)` — a drawing with a small
  caption under it (a numeral for a count, "Portrait"/"Landscape" for an
  orientation). The drawing is still what is tapped and lit; the caption only
  echoes it — never the other way round.
- `orientChips(sketchFor, current, onPick)` — the orientation picker itself:
  `sketchFor(orient)` drawn once per orientation, side by side, the chosen one
  lit. Used for BOTH the creation panel's own orientation row and the layout
  settings panel's "Shape:" row (owner round 2, 2026-08-07: orientation is
  exactly the column of his sheet, so it is picked as a picture too — never
  read as the words "Portrait"/"Landscape"). Since round 3, the two pictures
  it draws for a THREE or a FOUR are genuinely different shapes (wide vs.
  tall box), not just differently lit copies of the same one.
- `mergeLayouts(source, target)` — dropping one layout onto another. 1+1 and
  1+3 have exactly one possible shape, so nothing is asked; **1+2 becomes a
  THREE and a three has four arrangements**, which is the one case where he
  chooses. A full four refuses, and the list greys it while a drag is in
  flight so the refusal is visible before the finger arrives.

## Used by
- [Layouts](layouts.md) — the creation panel's count row AND its orientation
  row (`shapeChip` / `soloSketch` / `orientChips`), the layout list's drag,
  the layout settings panel's "Shape:" row (`orientChips` + `gridChip` for a
  THREE's arrangement)
