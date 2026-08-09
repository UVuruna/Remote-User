"""The GEOMETRY of a layout: the region the phone frames, and the cells a
grid cuts it into. Pure arithmetic — no window handles, no Windows API.

Split out of `window_manager.py` on 2026-08-07 (THE STRUCTURE LAW): that
module drove real windows AND computed where they should go, and the owner's
grid catalogue of the same day — two, three or four windows, with four
arrangements for three — pushed it past 1,000 lines. The seam is honest:
everything here can be tested with numbers alone, which is exactly what the
layout audit does with it.

The caller supplies the box (`window_manager._work_area`); nothing here asks
the operating system anything.
"""

# ═══════════════════════════ GRIDS ═══════════════════════════
# The owner's grid catalogue (2026-08-07, delivered as a drawing):
# TWO, THREE or FOUR windows, and for THREE there are four arrangements —
# the single window takes one full edge and the pair shares the rest.
#
#   "2"        "3-top"      "3-bottom"    "3-left"     "3-right"      "4"
#   ┌───┬───┐  ┌───────┐    ┌───┬───┐    ┌───┬───┐    ┌───┬───┐    ┌───┬───┐
#   │ 1 │ 2 │  │   1   │    │ 1 │ 2 │    │   │ 2 │    │ 1 │   │    │ 1 │ 2 │
#   │   │   │  ├───┬───┤    ├───┴───┤    │ 1 ├───┤    ├───┤ 3 │    ├───┼───┤
#   └───┴───┘  │ 2 │ 3 │    │   3   │    │   │ 3 │    │ 2 │   │    │ 3 │ 4 │
#              └───┴───┘    └───────┘    └───┴───┘    └───┴───┘    └───┴───┘
#
# ORIENTATION decides what "2" means — and only that (his rule: 2 and 4 can
# change nothing but portrait/landscape, 3 also picks its arrangement). A
# landscape "2" is two columns; a portrait "2" is two rows, because splitting a
# tall region down the middle gives two slivers.
#
# The old names "2x1"/"1x2"/"2x2" are still read so layouts made before this
# version keep their shape.
GRID_CELLS = {"2": 2, "3-top": 3, "3-bottom": 3, "3-left": 3, "3-right": 3, "4": 4}
GRID_TEMPLATES = tuple(GRID_CELLS)
_LEGACY_GRIDS = {"2x1": "2", "1x2": "2", "2x2": "4"}

def _fit_rect(box, aspect: float) -> tuple[int, int, int, int]:
    """Largest rect of the given aspect (w/h) inside `box`, CENTERED. Until
    2026-08-09 it also took a `pos` fraction that slid the rect along the
    free axis — the Move handle. That parameter moved WINDOWS on the PC
    monitor, a screen the owner never sees, while the picture on his phone
    stayed centred: the server crops the region and streams the same picture
    wherever the windows sit inside the monitor. The anchor lives on the
    PHONE now (client/view-anchor.js, owner decree 2026-08-09), so nothing
    here takes a position any more — legacy is removed, never kept."""
    bl, bt, bw, bh = box
    w = min(bw, int(bh * aspect))
    h = int(w / aspect)
    if h > bh:
        h = bh
        w = int(h * aspect)
    return (bl + (bw - w) // 2, bt + (bh - h) // 2, w, h)


def layout_region(work_area, aspect: float,
                  ratio: tuple[int, int] | None = None
                  ) -> tuple[int, int, int, int]:
    """The rect the phone frames. The DEVICE shape (`aspect`) gives the outer
    box; a per-layout ratio override may only make the region SMALLER inside
    it (owner decision 2026-08-03: portrait keeps the phone's width and the
    region may only get shorter, landscape keeps its height and the region may
    only get narrower — the unused strip stays black on the phone). Anything
    that would grow past the phone's own shape is clamped by the same fit.
    The shrunken region is always CENTERED on the monitor (owner decree
    2026-08-09): the Move handle's `pos` anchors the letterboxed picture ON
    THE PHONE and no longer moves any window here — see `_fit_rect`.

    `work_area` is the monitor's usable rect, supplied by the caller — this
    module never asks the operating system for anything."""
    box = _fit_rect(work_area, aspect)   # the phone-shaped box, centered
    if ratio and ratio[0] > 0 and ratio[1] > 0:
        return _fit_rect(box, ratio[0] / ratio[1])
    return box


PLACE_TOLERANCE_PX = 8   # DWM frame rounding; anything past this is "not there"


def at_rect(rect, target) -> bool:
    """Is a window's visible frame ON the rect it was commanded to take?
    Honestly: top-left within tolerance, size at least the cell (apps with a
    bigger minimum size end up larger — owner-accepted, the phone letterboxes).
    Pure arithmetic, so it lives here with the rest of the geometry."""
    x, y, w, h = rect
    tx, ty, tw, th = target
    return (abs(x - tx) <= PLACE_TOLERANCE_PX
            and abs(y - ty) <= PLACE_TOLERANCE_PX
            and w >= tw - PLACE_TOLERANCE_PX
            and h >= th - PLACE_TOLERANCE_PX)


def normalize_grid(grid: str | None) -> str | None:
    """A stored or incoming grid name → one this version knows, or None for a
    solo layout. Layouts made before 2026-08-07 carry `2x1`/`1x2`/`2x2`."""
    if not grid:
        return None
    grid = _LEGACY_GRIDS.get(grid, grid)
    return grid if grid in GRID_CELLS else None


def _split(rect, n: int, vertical: bool) -> list[tuple[int, int, int, int]]:
    """`rect` cut into `n` equal strips — down its middle when `vertical`."""
    x, y, w, h = rect
    if vertical:
        cw = w // n
        return [(x + i * cw, y, cw, h) for i in range(n)]
    ch = h // n
    return [(x, y + i * ch, w, ch) for i in range(n)]


def _cells(region, grid: str,
           orient: str = "landscape") -> list[tuple[int, int, int, int]]:
    """The member rects of a grid, in MEMBER ORDER — cell 1 first, which is the
    one a solo-to-grid merge keeps as the layout's own window.

    The single window of a THREE takes a full edge and the pair splits what is
    left ACROSS that edge, so no cell is ever a sliver: a bar along the top is
    followed by two side-by-side, a bar down the left by two stacked.
    """
    grid = normalize_grid(grid) or "2"
    x, y, w, h = region
    if grid == "4":
        return [(x, y, w // 2, h // 2), (x + w // 2, y, w // 2, h // 2),
                (x, y + h // 2, w // 2, h // 2),
                (x + w // 2, y + h // 2, w // 2, h // 2)]
    if grid == "2":
        # Orientation decides, and nothing else does (owner 2026-08-07).
        return _split(region, 2, vertical=orient != "portrait")
    side = grid.split("-")[1]                       # top | bottom | left | right
    vertical = side in ("left", "right")            # the bar runs down a side
    first, second = _split(region, 2, vertical=vertical)
    bar, rest = (first, second) if side in ("top", "left") else (second, first)
    pair = _split(rest, 2, vertical=not vertical)   # …split ACROSS the bar
    return [bar, *pair] if side in ("top", "left") else [*pair, bar]



def _normalize(rect, mon_rect) -> dict:
    ml, mt, mw, mh = mon_rect
    x, y, w, h = rect
    return {
        "x": max(0.0, min(1.0, (x - ml) / mw)),
        "y": max(0.0, min(1.0, (y - mt) / mh)),
        "w": max(0.0, min(1.0, w / mw)),
        "h": max(0.0, min(1.0, h / mh)),
    }


