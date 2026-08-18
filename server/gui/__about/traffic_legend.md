# Traffic Legend

**Script:** [Traffic Legend (script)](../traffic_legend.py)

## Purpose

One legend/status swatch, DRAWN with QPainter - never a font glyph or emoji.
Split out of [Traffic Window](traffic_window.md) on 2026-08-18 (THE STRUCTURE
LAW): the window owns layout and refresh, this owns pixels, and two different
parts of that window use it (the series/band legend and the per-device rows).

The rule it exists for is DESIGN.md's icon rule - *a mark is drawn, never a
font character*. The owner's phone once rendered a glyph mark as a blunt cross,
and the desktop is no different.

`color_fn` is a CALLABLE, not a `QColor`: a colour captured once at
construction would freeze whichever palette was active when the window was
built and never follow a runtime theme flip.

## Connections

### Uses
- [Theme](theme.md) - `TOKENS` at paint time, never at construction
- [Traffic Axis](traffic_axis.md) - `_alpha` for the band swatch's border

### Used by
- [Traffic Window](traffic_window.md) - the legend grid, the per-device rows
  and the recording dot

## Classes

- `LegendMark(color_fn, kind, parent=None)` - a fixed 20x14 widget; `kind` is
  one of `series` (a faded fill under a solid line, mirroring the chart),
  `band` (a filled rectangle with a hairline border), `dotted` (a dotted rule)
  or `dot` (a filled circle).

