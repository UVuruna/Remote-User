# View Anchor

**Script:** [View Anchor (script)](../view-anchor.js) ·
**Folder:** [client](../___client.md)

## Purpose

WHERE the letterboxed picture sits on the phone screen — the pure
fit-and-anchor math. When a layout carries an aspect ratio narrower than the
phone's, the fitted picture no longer fills the screen; the layout's `pos`
(0 = flush top/left of the slack axis, 0.5 = centred, 1 = flush bottom/right)
decides where it sits between the letterbox bars. Loads right before
[Render](render.md), which runs it.

## Why it exists (owner decree 2026-08-09 — the Move handle's FOURTH round)

Three rounds implemented the Move handle by sliding WINDOWS along the free
axis of the PC monitor, and three rounds of gates measured window rects there
— a screen the owner never sees. The server crops the layout's region and
streams the SAME picture wherever the windows sit inside the monitor, so his
tablet stayed centred every time: he dragged the handle to the TOP, pressed
Apply, nothing he could see moved. The position that exists FOR HIM is where
the picture lands on his own screen. So the server now always centres the
windows ([Grids](../../server/__about/grids.md)), `pos` rides `layout_state`
unchanged, and THIS module is the one place it acts.

## Key Functions

- `fitAnchorView(canvasW, canvasH, region, pos)` — the HOME transform
  (`{scale, tx, ty}`) for a region fitted into the canvas and anchored at
  fraction `pos` of the free-axis slack. Only one axis ever has slack — the
  fit pins the other — so a single fraction covers both orientations. A
  non-number `pos` (an old server) means centred; out-of-range values stop at
  the edges. [Render](render.md)'s `computeViewHome` calls it with
  `viewBounds()` and `layoutAnchorPos()` ([State](state.md)).
- `fitAnchorRect(canvasW, canvasH, region, pos)` — the rect the region is
  DRAWN into at home, computed THROUGH `fitAnchorView` (one source, so the
  transform the page uses and the rect the gate proves can never disagree).
  This is the surface `tests/test_view_anchor.py` drives.

## Design Decisions

- **Pure by design** (no DOM, no socket, no bridge — the
  [Caret](caret.md) / [Voice](voice.md) pattern): the gate runs the module
  WHOLE in node, computing the geometry the owner judges instead of a stored
  number. A DOM reference here would make the rule unprovable again, and the
  gate's purity check fails the build on one.
- **The anchor is the fitted-view WALL, not a pan** — it moves `viewHome`,
  so it is both the default framing on every layout switch and the baseline
  pinch-zoom bottoms out at (`clampView`). Zoomed in past fit there is no
  slack, and the anchor is moot by construction.

## Used by

- [Render](render.md) — `computeViewHome()`
- `tests/test_view_anchor.py` — the gate, fail-closed in `setup/build.py`
