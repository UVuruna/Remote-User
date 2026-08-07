# Input Geometry

**Script:** [Input Geometry (script)](../input-geometry.js) ·
**Flow:** [diagram](../__flow/input-geometry.md)

## Purpose

Maps a finger's canvas-pixel position to the PC's normalized (0–1) monitor
coordinates, and drives scroll-wheel momentum after a scroll gesture ends.
Third of the six client scripts to load (after [Render](render.md), before
[Controls](controls.md)).

## Connections

### Uses
- [State](state.md) — scroll tunables, `send`
- [Render](render.md) — `drawnRect()` (coordinate mapping basis)

### Used by
- [Gestures](gestures.md) — every pointer handler calls `toRemoteClamped`,
  `sendCursor`, `startScrollInertia`/`cancelScrollInertia`
- [Gamepad](gamepad.md) — the left stick's already-normalized point goes
  through `clampRemote`, the same fence a finger uses

## Key Functions

- `clampRemote(x, y)` — the one fence around a PC coordinate: `[0, 1]`, and
  inside a focused layout that layout's own region. Split out of
  `toRemoteClamped` on 2026-08-07 (build round G1) so the gamepad's left stick,
  which arrives already normalized, is fenced by the SAME rule as a finger
  rather than by a second copy of it — see [Gamepad](gamepad.md).
- `toRemoteClamped(px, py)` — canvas-px point → PC-normalized point, through
  `drawnRect()` and then `clampRemote`.
- `sendCursor(remote)` — sets `cursorPos` optimistically, sends
  `pointer_move`, redraws immediately (zero round-trip lag; the server's
  `cursor` echo corrects it later).
- `startScrollInertia(vel, pos)` / `cancelScrollInertia()` — exponential-decay
  scroll fling after a scroll gesture ends with velocity.

## Design Decisions

- **The pointer sits exactly under the finger** (owner decision 2026-08-02) —
  no diagonal offset, no calibration, no reserved edge margin. `toRemoteClamped`
  is a straight mapping; see below.
## Layouts (Phase F+ step 1)
`toRemoteClamped` additionally clamps into `layoutRegion` while a layout is
focused — the finger may travel past the framed window's edge, the PC cursor
never does (the phone sees ONLY that region).

## The cursor-offset system is gone (owner 2026-08-02, remnants finished 2026-08-07)
This file used to calibrate a fixed diagonal offset from the finger's measured
contact size (`sampleFinger`, `startCalibration`, `offsetDistancePx`,
`offsetRemote`, `toRemoteMaybeOffset`) and steer the PC cursor away from the
touch point along a handedness diagonal (`hand`: `"left"`/`"right"`). The
owner reversed that design on 2026-08-02 — the pointer sits exactly under the
finger — and on 2026-08-07 ordered every remaining trace removed as dead
weight, not kept as a compatibility shim: the `calibrate` built-in action, the
server's `config.hand` field, and the docs describing the old algorithm as if
it still ran. None of it exists anymore. The focus going forward is a
gamepad-first app, not finger handedness.
