# Input Geometry

**Script:** [Input Geometry (script)](../input-geometry.js) ·
**Flow:** [diagram](../__flow/input-geometry.md)

## Purpose

Maps a finger's canvas-pixel position to the PC's normalized (0–1) monitor
coordinates, calibrates the fixed cursor-offset distance from the finger's
measured touch contact size, and drives scroll-wheel momentum after a scroll
gesture ends. Third of the six client scripts to load (after
[Render](render.md), before [Controls](controls.md)).

## Connections

### Uses
- [State](state.md) — `hand`, cursor-offset tunables (`CURSOR_OFFSET_*`,
  `CURSOR_CALIB_SAMPLES`), scroll tunables, `send`
- [Render](render.md) — `drawnRect()` (coordinate mapping basis),
  `computeBaseRect()`/`clampView()`/`redraw()` (re-run after calibration
  changes the offset distance)

### Used by
- [Gestures](gestures.md) — every pointer handler calls
  `toRemoteMaybeOffset`/`offsetRemote`/`toRemoteClamped`, `sampleFinger`,
  `sendCursor`, `startScrollInertia`/`cancelScrollInertia`
- [Controls](controls.md) — the `calibrate` built-in action calls
  `startCalibration()`

## Key Functions

- `toRemoteClamped(px, py)` — canvas-px point → PC-normalized point, clamped
  to `[0, 1]`, through `drawnRect()`.
- `sampleFinger(e)` — feeds one touch sample into calibration; locks
  `fingerRadiusPx` at the MAX contact radius seen over
  `CURSOR_CALIB_SAMPLES` samples (max, not median — a light press
  under-reports contact size).
- `startCalibration()` — re-arms calibration (Settings → Calibrate),
  resetting to the fallback offset until re-measured.
- `offsetDistancePx()` — the constant per-session offset distance:
  `fingerRadiusPx + CURSOR_OFFSET_MARGIN`, clamped to `[MIN, MAX]`, or the
  fallback until calibrated.
- `offsetRemote(p)` — finger point → PC point placed one offset away, in the
  fixed handedness diagonal (315° right-handed / 45° left-handed).
- `toRemoteMaybeOffset(p, offset)` — dispatches to `offsetRemote` (touch) or
  `toRemoteClamped` (mouse/pen — no offset).
- `sendCursor(remote)` — sets `cursorPos` optimistically, sends
  `pointer_move`, redraws immediately (zero round-trip lag; the server's
  `cursor` echo corrects it later).
- `startScrollInertia(vel, pos)` / `cancelScrollInertia()` — exponential-decay
  scroll fling after a scroll gesture ends with velocity.

## Design Decisions

- **The pointer never sits on the finger.** A fixed diagonal offset (not a
  radial angle — that was the pre-2026-07-26 design) keeps the PC cursor
  visible and the aiming direction constant, building muscle memory.
- **Calibration takes the MAX, not the median or first sample** — a light
  first touch under-reports contact radius and would place the pointer too
  close, partly hidden by the finger.
## Layouts (Phase F+ step 1)
`toRemoteClamped` additionally clamps into `layoutRegion` while a layout is
focused — the finger may travel past the framed window's edge, the PC cursor
never does (the phone sees ONLY that region).

## Offset system removed (owner 2026-08-02)
The cursor-offset system (handedness diagonal, finger calibration, reserved
edge margins) is GONE — the pointer sits exactly under the finger, the image
aspect-fits the FULL canvas, and a focused layout touches all four screen
edges. Any offset/margin description in this doc's diagrams predating
2026-08-02 is historical.
