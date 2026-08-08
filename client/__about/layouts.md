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
  `layout_remove {index, close?}`

## Key Functions & Data

- **Loading animation** — `showLayLoading(text)` / `settleLayLoading()` /
  `hideLayLoading()`, `cubeFrame`, `cubeNext`, `CUBE_VIEWS`. The overlay is
  opaque and covers the ENTIRE time a layout is created, loaded or switched;
  `layout_state` only arms the settle watcher (`settleStill` samples a 64×36
  thumbnail of the live frame), and the animation drops when the picture
  actually stops moving. Every showing opens on the next cube face.
- **The ✕ chooser** — `openCloseChooser(index)`, `chooserBtn(icon, label,
  sub, onTap)`. The bar's ✕ used to send `layout_remove` outright, which is
  one of the two things the owner means by it (2026-08-08): *"brisanje layouta
  ga samo obrise iz nase liste ali ostavlja prozor na desktopu. Nekad hocemo
  to, a nekad hocemo bas da zatvorimo sve tu."* It now opens the same
  side-by-side card the creation flow uses — **Remove the layout** (what it
  always did) and **Close the window(s)** (`close: true`; the PC posts
  `WM_CLOSE`). Each chip carries a second line naming its consequence and the
  real member COUNT, so the irreversible one is never picked by elimination.
- **Layout bar** — `updateLayoutBar`, `layoutStep(dir)`, `focusLayout(index)`
  (index −1 = full desktop), `applyOrientationLock` (drives the shell's
  `Android.lockOrientation`: layout focus = locked, desktop = free).
- **Layout list** — `openLayoutPicker`, `layRow`, `ratioLabel`: every layout
  at once (Desktop first), a row taps to focus, its trailing buttons open the
  RENAME card (pencil) and the aspect panel.
- **Naming** — `nameField(value, placeholder)`, `openRenamePanel(index)`
  (owner 2026-08-05). A layout's auto name is the target window's title; the
  creation panel offers it prefilled in an editable Name field (`creating.name`
  — `null` follows the title, `""` sent means "keep it"), and the list's
  pencil renames an existing one via `layout_rename {index, name}` without
  moving anything on the PC. The field is a WRAPPING textarea, not a one-line
  input: window titles are long enough that a single line hid most of one
  behind its own horizontal scroll (caught by `tests/test_layout_audit.py`,
  THE SPACE & LEGIBILITY LAW); newlines are stripped as they are typed.
- **Aspect panel** — `openAspectPanel`, `renderAspectPanel`,
  `updateAspectPreview`, `aspFrac`, `clampAspect`, `dragAspect`, `ratioPair`,
  `devicePair`: W : H fields over a dashed phone-screen preview with the region
  inside it. The state is one continuous number (`a` = W/H); the fields render
  it and either one may be typed. Nothing moves on the PC until Apply, which
  sends `layout_aspect {index, w, h}` on a 1000-scale (`0/0` = Screen).
- **Creation** — `openSourceChooser`, `armNextTap`, `handleLayoutOffer`,
  `renderCreationPanel`, `cancelCreation`, `slotFromOffer`/`slotFromEntry`,
  `titleChip`, `GRID_CELLS`.
- **A window title is never cut** (owner 2026-08-06, fixed 2026-08-07). The
  chosen-slot chips and the creation list both used to shorten a title in JS
  — `s.title.slice(0, 29) + "…"` — which is a truncation the DOM cannot see:
  the element fits perfectly, `scrollWidth === clientWidth`, and every clip
  check in the layout audit reported PASS while 225 device px stood idle on
  that row. His words: *"čip sa izabranim prozorom skraćuje naziv na 'Claude
  Code - Remote User - V…', a pun naziv se na tom ekranu ne vidi nigde kada
  polje Name već prepišeš"*. `titleChip` now adds `.lay-title`, which lets a
  chip take the free width and then WRAP — the same treatment
  `.lay-item-main span` gives the same titles in the layout list, not a second
  one. **And that chip is the answer to the second half of his complaint:**
  the Name field may be retyped to anything, the chip above it still carries
  the window's own full title. The audit gained the tooth this class needed —
  `__truncated`, an ellipsis in the text itself beside free width on its row
  (see [tests](../../tests/___tests.md)).

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
- **The Move handle** (owner 2026-08-05): a round button in the region's
  center, drawn as `ICONS.move` — a four-way arrow with real arrowheads.
  (It was the "✥" character until the owner saw what his phone's font made of
  it: a blunt cross. A control's shape must not depend on the device's fonts.)
  Dragging it slides the shrunken region along the free axis (portrait:
  up/down, landscape: left/right) — the region no longer has to sit centered;
  a double-tap re-centers it. `dragMove` owns the gesture (pointer capture on
  the handle, `stopPropagation` so the surrounding resize drag stays out);
  state is `aspecting.pos` (0–1 fraction of the free-axis slack, 0.5 =
  centered, initialized from the server's `layout_state` `pos`). Everything
  OUTSIDE the handle still resizes as before. Apply sends `pos` (0–1000) in
  `layout_aspect`; the server places the region with the same fraction — see
  [Window Manager](../../server/__about/window_manager.md).

  **A DOUBLE TAP IS TWO TAPS, NOT TWO TOUCHES** (owner 2026-08-07: he shrank a
  layout, dragged it down, "ali on je i dalje na sredini"). Every piece above
  was correct and every test of it passed; the two defects lived in the gesture
  and nothing had ever delivered a touch to it.
  1. The re-centre fired from `pointerdown` on ANY contact within 350 ms of the
     previous one, so the very common tap-then-drag was read as a double tap:
     it put the region back in the MIDDLE *and* returned without capturing the
     pointer, so the drag died too. Both halves of his sentence, from one line.
     A tap is now judged at its END — short, and without travel past
     `MOVE_TAP_SLOP`; a press is always a press, and `pointercancel` counts as
     an end (the rule the control buttons already live by).
  2. `moveTapAt` started at **0**, which is a real `performance.now()` reading
     meaning "a tap at page load" — so any tap in the page's first 350 ms
     re-centred. It is `-Infinity` now. The audit found this in landscape while
     portrait passed at 623 ms, which is exactly how a timing bug survives a
     green suite.

- **Nothing here asks which app shortcuts a layout carries** (owner 2026-08-07).
  The creation panel and the rename panel both held a row of ticks between
  2026-08-06 and 2026-08-07; they are gone, with `autoAppSets`, the `apps` field
  of a creation session, and the `layout_apps` message. `appSetMatches` reads
  the server's live `agents` instead — see
  [Window Manager](../../server/__about/window_manager.md) for what the stored
  copy cost.

## App shortcuts are chosen here (owner 2026-08-06)

The creation panel and the rename card both carry the row **"App shortcuts on
the wheel for this layout"** — the ticks that decide which app-aware sets ride
while this layout is focused. `autoAppSets()` pre-ticks every set whose
`process` matches the first slot and that demands no title, which is correct
for Chrome, Explorer and plain VSCode; Claude is the single tap the owner adds
himself, because nothing on the PC can identify a Claude Code conversation
(the probe is in [sets](sets.md)).

They sit in the rename card rather than as a third button in each list row:
the row already carries rename and ratio, and a fourth control is what THE
SPACE & LEGIBILITY LAW keeps catching. Both panels are audited at their
fullest — long title AND four chips — in `tests/test_layout_audit.py`.

`layout_create` carries the list; `layout_apps {index, sets}` changes it
later, and nothing on the PC moves when it does.
