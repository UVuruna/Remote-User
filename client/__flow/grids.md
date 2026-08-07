# Flow — grids (phone)

```
CREATION PANEL
    "Two" / "Three" / "Four"  →  c.grid = "2" | "3-top" | "4"
    IF three:  four gridChip sketches → c.grid = 3-top | 3-bottom | 3-left | 3-right
    Create  →  layout_create {slots, grid, orient, …}

LAYOUT SETTINGS  (the pencil: name + shape)
    Portrait / Landscape        → orient
    IF the layout is a THREE:   four sketches → shape
    Save  →  layout_grid {index, grid, orient}   (only when something changed)

DRAG A ROW  (hold 380 ms, then move)
    every full layout (4 windows) greys out            ← the refusal, before the finger
    over the MIDDLE of a row      → that row lights up  ← drop = grid
    over the TOP/BOTTOM 28% edge  → a gap line          ← drop = reorder
    release
        on a row  → mergeLayouts(from, over)
        on a gap  → layout_reorder {source, before}

mergeLayouts(source, target)
    size = cells(target) + 1
    size == 2 or 4  →  layout_merge {source, target}         # one possible shape
    size == 3       →  ask: four sketches → layout_merge {source, target, grid}
```

Every shape here is drawn by `gridSketch`, never named — the owner sent a sheet
of drawings, and a picture is what he picks from.
