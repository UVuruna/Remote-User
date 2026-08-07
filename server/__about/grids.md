# Grids — the geometry of a layout

[← server](../___server.md) · code: [grids.py](../grids.py) · flow: [__flow/grids.md](../__flow/grids.md)

Pure arithmetic: the rect the phone frames, and the cells a grid cuts it into.
No window handles, no Windows API, nothing that can fail — which is why the
layout audit checks it with numbers instead of a screenshot of two windows.

Split out of [Window Manager](window_manager.md) on 2026-08-07 (THE STRUCTURE
LAW): that module both drove real windows and computed where they should go,
and the owner's grid catalogue of the same day pushed it past 1,000 lines.

## The owner's catalogue (2026-08-07, delivered as a drawing)

TWO, THREE or FOUR windows. **Orientation decides what "2" means and nothing
else** — his rule: two and four may change only portrait/landscape, because
there is one sane way to cut a region into two or four. A THREE has four
arrangements: its single window takes the top, bottom, left or right edge, and
the pair splits what is left ACROSS that edge, so no cell is ever a sliver.

| grid | cells | shape |
|---|---|---|
| `2` | 2 | two columns in landscape, two rows in portrait |
| `3-top` | 3 | a full bar on top, two side by side below |
| `3-bottom` | 3 | two side by side on top, a full bar below |
| `3-left` | 3 | a full bar down the left, two stacked on the right |
| `3-right` | 3 | two stacked on the left, a full bar down the right |
| `4` | 4 | 2×2 |

`normalize_grid` maps the pre-2026-08-07 names (`2x1`/`1x2` → `2`, `2x2` → `4`)
so layouts made by an older version keep their shape.

## Key functions

- `layout_region(work_area, aspect, ratio, pos)` — the rect the phone frames.
  The DEVICE shape gives the outer box; a per-layout `ratio` may only make the
  region SMALLER inside it, and `pos` slides that smaller region along the one
  free axis (0.5 = centred — the Move handle of the phone's resize panel).
  **The caller supplies `work_area`** (`window_manager._work_area`); this
  module never asks the operating system anything.
- `_cells(region, grid, orient)` — the member rects, in MEMBER ORDER. Cell 1
  is the one a merge keeps as the layout's own window.
- `_fit_rect(box, aspect, pos)` — the largest rect of an aspect inside a box,
  placed at `pos` of the slack. Everything above is built from it.
- `at_rect(rect, target)` — is a window's visible frame ON the rect it was
  commanded to take? Top-left within `PLACE_TOLERANCE_PX` (8, DWM frame
  rounding), size at least the cell (a bigger minimum size is owner-accepted —
  the phone letterboxes). Moved here from `window_manager` on 2026-08-07: it
  is pure arithmetic, and it is now asked twice — once by `wait_landed` while
  placing, and once by `_standing` before a focus decides whether the
  arrangement it REMEMBERS is the arrangement the desk actually holds.
- `_normalize(rect, mon_rect)` — a rect as monitor-normalized 0–1, which is
  the only coordinate space the phone is ever told about.

## Used by
- [Window Manager](window_manager.md) — placement and the state frame
- [Layout API](layout_api.md) — the grid names offered to the phone
- `tests/test_layout_audit.py` — "every shape tiles its region exactly"
