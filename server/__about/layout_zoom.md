# Layout Zoom

**Script:** [Layout Zoom (script)](../layout_zoom.py)

## Purpose

The T76 zoom arithmetic: WHAT the encoder crops to, and WHAT resolution step
the pinch has earned. Split out of [Layout API](layout_api.md) on 2026-08-18
(THE STRUCTURE LAW, VC-R6).

Every function here is pure — a dict in, a number or a dict out — and none of
them calls anything else in the layout protocol. That is the whole reason this
is the seam: these are the numbers the owner corrected across FIVE rounds
(`docs/DECISIONS.md` section 27), `tests/test_zoom_crop.py` drives them check
by check, and a file they shared with thirty protocol handlers is a file where
a later patch aimed at a handler can reach them by accident.

**Nothing here was rewritten.** Every body is byte-identical to the one that
stood in `layout_api.py`. On this file the audit's own risk note is the point:
round 5 of T76 exists because a documented rule measured the wrong thing, and
a split is not the place to have an opinion about which one.

## The rule, in one sentence

THE ZOOM RAISES THE RESOLUTION, IT NEVER MOVES THE CROP (the owner's own
design, round 3 of T76, delivered as eight diagrams). The stream always covers
the whole picture — desktop = full frame, layout = the layout's region — and
the pinch changes only the resolution that picture is encoded at, in quantized
powers of two, clamped at native. A PAN keeps the rect's size, therefore the
step, therefore the session: free, forever.

## What stayed next door, and why

`layout_api.zoom_region` — the HANDLER — did not move. It re-enters
`send_layout_state`, the one choke point that decides whether the running
session still matches, and moving a caller of that choke point out of the
module that owns it would be a second teardown path. That is exactly what the
2026-08-07 orphan was made of.

## Connections

### Uses
- nothing. Pure arithmetic over the connection dict.

### Used by
- [Layout API](layout_api.md) — `zoom_region` (the guards) and
  `send_layout_state` (the choke point's two derivations)
- [Web Layer](web.md) — when it opens an H.264 session
- [WS Commands](ws_commands.md) — the `viewport` command's own note
- [H.264 Streamer](h264_streamer.md) — the step it is opened with

## Functions

- `ZOOM_MIN_DELTA` — how far the rect must move before the wire is consulted
- `ZOOM_MAX_STEP` — the cap; past native there is nothing left to raise
- `ZOOM_STEP_SLACK` — how much magnification is "none" (round 5, 2026-08-18):
  float noise in the phone's own canvas arithmetic must not buy a rebuild
- `_norm(rect)` / `_is_full(r)` — a wire rect clamped into the unit square
- `stream_crop(conn)` — the ONE derivation of the crop, asked by both callers
  so the equality at the choke point stays exact
- `zoom_step(conn)` — the ONE derivation of the step; since round 5 it is
  earned from DRAWN pixels over PANEL pixels, long-to-long and short-to-short,
  because a FRACTION of the picture cannot say how blurry it is — the two
  agree only when the picture fills the screen, and his tablet in portrait
  letterboxes
- `_drawn_of(msg)` / `_drawn_moved(a, b)` / `_rect_delta(a, b)` — the guards
