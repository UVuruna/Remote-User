# Layouts

**Script:** [Layouts (script)](../layouts.js) ·
**Flow:** [diagram](../__flow/layouts.md)

## Purpose

The whole phone-side layout feature (Phase F+): the loading animation, the
top-center layout bar, the layout LIST, the per-layout ASPECT RATIO panel and
the creation flow (source chooser → slots → Create). Fifth of the seven client
scripts to load — after [Controls](controls.md) (whose `keepFocus`, `svg`,
`showToast` and `IN_APP` it uses), before [Gestures](gestures.md).

Split out of [Controls](controls.md) on 2026-08-03, when that file crossed THE
STRUCTURE LAW's 1,000 lines. The boundary is a responsibility one, not a size
one: `controls.js` drives the PC directly (keys, clicks, upload, quality),
everything here composes and frames WINDOWS on it.

## Connections

### Uses
- [State](state.md) — `send`, `layouts`, `layoutActive`, `layoutRegion`,
  `layoutArm`, `streamMode`, `baseBitmap`
- [Render](render.md) — the `<video>` element / `baseBitmap` as the frame
  source the settle watcher samples
- [Controls](controls.md) — `keepFocus`, `svg`, `showToast`, `IN_APP`

### Used by
- [Connection](connection.md) — `layout_state` → `settleLayLoading()`,
  `updateLayoutBar()`, `applyOrientationLock()`; `layout_offer` →
  `handleLayoutOffer()`; `layout_progress` → `cubeNext()`
- [Gestures](gestures.md) — the armed pick tap reads `layoutArm`
- [Window Manager](../../server/__about/window_manager.md) /
  [Web Layer](../../server/__about/web.md) — the other end of
  `layout_list` / `layout_create` / `layout_focus` / `layout_aspect` /
  `layout_remove`

## Key Functions & Data

- **Loading animation** — `showLayLoading(text)` / `settleLayLoading()` /
  `hideLayLoading()`, `cubeFrame`, `cubeNext`, `CUBE_VIEWS`. The overlay is
  opaque and covers the ENTIRE time a layout is created, loaded or switched;
  `layout_state` only arms the settle watcher (`settleStill` samples a 64×36
  thumbnail of the live frame), and the animation drops when the picture
  actually stops moving. Every showing opens on the next cube face.
- **Layout bar** — `updateLayoutBar`, `layoutStep(dir)`, `focusLayout(index)`
  (index −1 = full desktop), `applyOrientationLock` (drives the shell's
  `Android.lockOrientation`: layout focus = locked, desktop = free).
- **Layout list** — `openLayoutPicker`, `layRow`, `ratioLabel`: every layout
  at once (Desktop first), a row taps to focus, its trailing button opens the
  aspect panel.
- **Aspect panel** — `openAspectPanel`, `renderAspectPanel`,
  `updateAspectPreview`, `aspFrac`, `clampAspect`, `dragAspect`, `ratioPair`,
  `devicePair`: W : H fields over a dashed phone-screen preview with the region
  inside it. The state is one continuous number (`a` = W/H); the fields render
  it and either one may be typed. Nothing moves on the PC until Apply, which
  sends `layout_aspect {index, w, h}` on a 1000-scale (`0/0` = Screen).
- **Creation** — `openSourceChooser`, `armNextTap`, `handleLayoutOffer`,
  `renderCreationPanel`, `cancelCreation`, `slotFromOffer`/`slotFromEntry`,
  `GRID_CELLS`.

## Design Decisions

- **The overlay is the FRONT; the work happens behind it** (owner rule, said
  four times). It may fade out only when the layout window is in place and
  alone on screen — or, for Desktop, when every layout member is really
  minimized. Two ends must agree: the server now finishes AND VERIFIES before
  it answers (DWM transitions frozen + `wait_landed` position checks +
  `wait_minimized`, 2026-08-04 — see
  [Window Manager](../../server/__about/window_manager.md)), and this side
  waits `SETTLE_CATCHUP_MS` after the answer before it judges the picture at
  all. **That delay is the bug the owner saw twice:** sampling used to start
  the instant `layout_state` arrived, while the phone was still displaying the
  OLD frame (the encoder and the link run a few hundred ms behind the PC) — two
  identical samples of a STALE picture read as "settled", the cube left, and
  the frames showing the window rising arrived right after it.
- **The animation lasts until the SCREEN is right, not until the server
  answers** (owner, repeatedly, finally 2026-08-03). The server's
  `layout_state` arrives while Windows is still restoring windows from the
  taskbar and sliding them into their cells — the phone used to hide the
  overlay right then and the user watched the whole scramble. Now the overlay
  stays and a 64×36 thumbnail of the live frame is sampled every
  `SETTLE_SAMPLE_MS`; it drops after `SETTLE_STABLE_HITS` near-identical
  samples, `LOADING_MIN_MS` at the earliest, `SETTLE_MAX_MS` after the answer
  at the latest (unrelated motion on the PC — a playing video — must not hold
  it forever) and `LOADING_MAX_MS` if the server never answers at all.
  Sampling the frame source and NOT the canvas is deliberate: the canvas
  carries the layout view transform, which itself changes on focus.
- **A different cube angle every time** (owner 2026-08-03). `CUBE_VIEWS`
  holds one corner view per face in the owner's order (top → left → back →
  right → front → bottom, looping); each showing advances one step. Every
  entry is its face dead-on plus a ~30° tilt on both axes, so the cube still
  reads as a cube instead of a flat coloured square — the same reason the
  projection is orthographic (no `perspective`).
- **Enter and exit cross-fade** (owner 2026-08-03, "like the theme switch in
  Prompt Painter"): visibility is the `open` class with a CSS opacity
  transition, never the `hidden` attribute, and the cube keeps spinning
  through the fade-out — a frozen cube during the fade is exactly the stutter
  the smooth exit removes.
- **Arrows outside, name in a frame** (owner 2026-08-03): the old `‹ ›`
  glyphs sat inside the label and were too small to hit; they are now large
  SVG buttons on either side, and the framed name is its own button that
  opens the full list — stepping through a dozen layouts one by one to reach
  one was the reported pain.
- **The aspect ratio can only make the region SMALLER than the phone's own
  shape** (owner decision 2026-08-03): portrait keeps the phone's full width
  and only loses height, landscape keeps its height and only loses width. That
  is the ONE rule — `clampAspect` enforces it (and a `ASP_MIN_FRAC` floor so
  the region can never collapse to a slit), and the server clamps the same way
  — see [Window Manager](../../server/__about/window_manager.md).
- **The ratio is continuous, not stepped in units of the device pair** (owner
  2026-08-04, the reported bug). The panel used to hold `[W, H]` as whole
  units of the phone's approximated pair, so on a tablet reducing to 7:5 one
  step was ~14% of the width and **8:5 was simply unreachable**. State is now
  the plain number W/H: a drag moves it pixel by pixel and typing any pair
  (8 : 5) sets it exactly. `ratioPair` is demoted to a *rendering* of that
  number (denominator ≤ 40 — 412×892 → 6:13), used for the fields and the row
  label; Apply sends the exact value as `round(a × 1000) : 1000`.
- **The whole preview is the drag surface**, not the two 18px dots — on a
  tablet those were nearly unhittable, which is what read as "barely
  responsive". Pointer capture on the screen box, `touch-action: none` so a
  drag never becomes a page scroll, and the region itself is
  `pointer-events: none`.
- **"Screen" resets the override entirely** (`w = h = 0` on the wire — also
  sent when a drag lands back on the full screen), so an approximation error
  can never accumulate into a shrinking region.
