# `design_pics.js` — the mini diagrams

One little picture per **kind of number**, drawn beside its row in the design
lab. Owner round 2, 2026-08-19: *"nicer descriptions, and even with a little
picture if that helps"*.

A sentence answers *what is this for*. A picture answers *which way does it
move* — and for a corner radius, a gap between two things, a ring or a halo the
picture is the faster of the two, and the one you can read without stopping.

## One drawing per meaning, not per row

`gap` is the same picture under an icon's label and between two cards, because
it is the same idea. That is why the id lives on the row
(`tools/design_groups.py` → `pic`) and the drawing lives here: twenty pictures
serve seventy-five rows, and a new row costs nothing.

| family | ids |
|--------|-----|
| the face | `size` `radius` `icon` `edge` `swatch` |
| text | `label` `ink` `width` |
| distance | `gap` `space` |
| around the shape | `ring` `glow` `scale` |
| a shadow's own numbers | `shift-x` `shift-y` `blur` `strength` |
| the two shadow colours | `shadow-light` `shadow-dark` |
| small round things | `dot` `pill` `sets` |

## They are the lab's chrome, never a specimen

Two classes — `base` for the shape, `hot` for the quantity being tuned — styled
in `tools/design_lab.css` from the workshop's own grey palette. Nothing here can
be mistaken for the product, and the product's colours never reach it.

The one exception is deliberate: **`shadow-light` and `shadow-dark` are drawn in
literal black and white**, because black and white ARE the subject of those two
rows. Both sit on a mid-grey card, which is what lets each of them be seen at
all — a black letter with a black shadow on a dark panel is exactly the defect
the row exists to tune, and it would also have been an invisible diagram.

## A missing picture is a missing picture, never a broken page

`pic(id)` returns `null` for an id it does not know and the row is built without
one. The gate is what makes sure that never happens quietly:
[tests/test_design_lab.py](../../tests/test_design_lab.py) reads the ids out of
this file and fails on any row naming a drawing that is not in it.

Up: [tools/___tools.md](../___tools.md) ·
Beside: [design_groups.md](design_groups.md)
