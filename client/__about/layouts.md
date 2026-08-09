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
- [Grid Icons](grid-icons.md) — `gridIconSvg` for each row's shape and each
  member row's lit cell, `gridIconChoices` for the one arrangement a 4→3 asks
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
  at once (Desktop first), a row taps to focus, its trailing buttons are the
  layout's own SHAPE (task 164, below), the RENAME card (pencil) and the
  aspect panel. `layRow`'s badge argument takes three kinds now — an app-icon
  URL, `{draw: markup}` for a drawing we made, or `null` for the Desktop row's
  monitor — because the member chooser's badge is a third thing and a builder
  that could only draw two of them would have been copied instead of reused.
- **The row says what shape the layout is** (owner request 2026-08-09, task
  164). A solo window, a two-split and a four-grid read identically while a
  row carried only a name, so the only way to tell them apart was to OPEN one.
  Each row now draws its real arrangement with
  [Grid Icons](grid-icons.md)'s `gridIconSvg(lay.members, lay.grid,
  lay.orient)` — three fields `layout_state` has carried since 2026-08-07, so
  the wire did not change. The drawing sits in a `.lay-ratio.lay-shape`
  button, which is also the DOOR to the member chooser; a SOLO layout renders
  the same picture as a `<span>` instead, because it has nothing to throw out
  and a button that does nothing is a promise the panel cannot keep. It is
  deliberately outside the aspect chip's label floor (that floor makes two
  different LABELS agree — a drawing has no label to disagree about, and three
  floored chips would leave a phone-width row nothing for the name).
- **The name outranks the buttons beside it** (independent grader, 2026-08-09,
  task 172: *"the starred row spends its width on two leading badges plus three
  trailing buttons and leaves the name 'Claude Cod…' — nine characters, one
  word, which cannot tell two Claude layouts apart"*). The aspect chip carried
  `svg("aspect")` in FRONT of a label already reading "3:5" or "Screen", and
  that pair is what set the chip's 96 px floor — so on a 338 px row the widest
  trailing control spent 26 px restating its own text while the name had 48.
  The glyph is gone and the floor is re-derived from the widest label the chip
  can hold ("Screen": 62 px of box plus the ~4 px of headroom the old floor
  carried), which hands the name 30 px on every row: 5 characters to 9 at
  412 px, 10 to 15 on the tablet. `aria-label` names the button, since the
  remaining text names only the value. **The leading badge was NOT the thing to
  cut** — it looked like a constant because the audit staged `icon: null` on
  every row, and the server really sends a per-app icon per layout, which is
  the fastest answer to "which app" on a row whose name is cut; the fixture was
  fixed instead (`tests/_audit_panels.py`). The floor is now the row's own law
  rather than a number: `__nameRoom` (tests/_audit_js.py) fails any row that
  gives its name less width than the widest button standing beside it.
- **Taking one window out of a grid** — `openMemberPanel(index)` (owner
  request 2026-08-09, task 165): *"there must be a button by which I can throw
  ONE member out of the grid — to enter the grid state and remove any member,
  i.e. change it to a single or to a 2-grid."* Until this round a grid could
  only be BUILT (drag one row onto another) or removed WHOLE, so losing one
  window of four meant deleting the layout and building it again.
  **He picks the window by its POSITION, not by its name:** every row's badge
  is this layout's own drawing with THAT cell lit and the rest faint (`{cell:
  k}` — cell *k* is member *k*, the order the server places into), because
  four VS Code windows have four nearly identical titles and only one of them
  is the top-left square. Titles come from `layout_state.member_titles` and
  obey task 163's one-line rule; a server too old to send them still gives a
  usable panel, since the CELL is the picture and the title only the word.
  A 4→3 is the one size with a shape to choose, asked of the RESULT via
  `gridIconChoices(members - 1, null)` — a three shrinking to a two has
  nothing to decide, and the asymmetry stays in the pure module so no panel
  can offer a choice that does not exist. Sends `layout_member_remove {index,
  member, grid?}`; the survivors are re-placed, so the loading cube covers it.
  **It is not a close** — the window leaves the layout, leaves the topmost band
  and goes on standing where it stands.
- **⭐ marks the trunk** (owner decision 2026-08-09, task 169): one emoji
  before the first letter of a layout whose window another layout's content was
  torn out of — closing it would take that other layout's tab with it. The
  server answers it (`layout_state.parent`, read off `Layout.source`); nothing
  here guesses from a title, and only the layout SELECTOR is marked (the
  creation list shows parenthood by indentation instead — his task 168, not
  this one). It is its own element, not part of the name: task 163's ellipsis
  can then never eat it, and its `line-height` is pinned to the badge's 20 px
  so a colour emoji's own metrics cannot make a starred row taller than its
  siblings. **An emoji although this project draws its icons** — the ✥ move
  handle came out a blunt cross on his phone in 2026-08-05 and everything has
  been drawn geometry since — because he asked for this one by name, and a
  colour emoji from Android's own emoji font is exactly what that dingbat was
  not. Gated on both ends: `tests/test_layout_drag.py` proves the server marks
  the trunk and nothing else, `tests/test_layout_audit.py` (`__layoutStars`)
  proves the right ROW wears it, in every look and on all four screens, without
  changing the measured row height.
- **Dragging a row** — the hold, `dragMoveTo`, `dragEnd`, the edge auto-scroll
  (owner 2026-08-07, the Explorer gesture; repaired 2026-08-09, task 162).
  Hold a row and it is picked up; dropping it ON another sends
  `layout_merge {source, target}` (`mergeLayouts` in [Grids](grids.md) asks
  which of the four shapes when the result is a THREE), dropping it in the gap
  above or below one sends `layout_reorder {source, before}`. A layout that
  already holds four greys out the moment the drag starts, so the refusal is
  visible before the finger arrives instead of arriving as a toast after it.
  The arming rule itself is [Hold Gesture](hold-gesture.md) — a pure module,
  because inline it was untestable and therefore untested for two days while
  the feature was dead on the phone. See **A hold is a contact that STAYED
  PUT** and **One row is one line** below.
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
  `GRID_CELLS`. They live in [layout-create.js](layout-create.md); this file
  lends them its panel vocabulary and its `.lay-item` row markup.
- **A window title is never cut IN JS** (owner 2026-08-06, fixed 2026-08-07).
  The chosen-slot chips and the creation list both used to shorten a title in
  JS — `s.title.slice(0, 29) + "…"` — which is a truncation the DOM cannot
  see: the element fits perfectly, `scrollWidth === clientWidth`, and every
  clip check in the layout audit reported PASS while 225 device px stood idle
  on that row. His words:
  *"čip sa izabranim prozorom skraćuje naziv na 'Claude Code - Remote User - V…', a pun naziv se na tom ekranu ne vidi nigde kada polje Name već prepišeš"* — lang-ok: owner quote.
  That half stands and must never come back. What changed on 2026-08-09 is
  the treatment AFTER it: task 163 made a kin group's rows one line each, cut
  by CSS (`.lay-item-main span`), and task 168 turned the creation panel's two
  lists into those same rows — so the wrapping title pill that answered him in
  2026-08-07 (`titleChip` / `.lay-chip.lay-title`) lost its last caller and was
  deleted the same day. **The second half of his complaint is answered one
  step further on:** the Name field under the chosen rows is a WRAPPING
  textarea prefilled with the window's own title, and the rename card is the
  same for a layout that already exists — the full name is always exactly one
  tap away from the row that elides it. The audit gained the tooth this class
  needed — `__truncated`, an ellipsis in the text itself beside free width on
  its row (see [tests](../../tests/___tests.md)).
- **A hold is a contact that STAYED PUT, not one that never moved a pixel**
  (owner report 2026-08-09, task 162). He held a row without moving it and the
  layout OPENED. Three separate things defeated the gesture, and all three are
  now fixed here: the `pointermove` handler cleared the 380 ms timer on ANY
  movement (a resting finger on a capacitive digitizer wanders — it now asks
  `pressVerdict` and only a travel past `HOLD_DRAG_SLOP` counts); `keepFocus`
  fires its tap on `pointerup` with no duration test and rescues any
  `pointercancel` under 18 px, while Chrome hands out that cancel at ~8 dp as
  soon as it decides the touch is a scroll (the ROW now refuses a tap whose
  press lasted `HOLD_DRAG_MS` — `keepFocus` is untouched: it is the activator
  the gamepad shares); and `.lay-item` declared no `touch-action`, so the
  browser owned the vertical gesture and ended the carry with a cancel. The
  fourth fix is a latent one in the same block: `setPointerCapture` throws for
  a pointer that is already gone, and it used to run AFTER `drag` was
  assigned — leaving `drag` non-null with no gesture in flight, which made
  every row in the list dead until the panel was reopened. Capture first, arm
  only if it took.
- **Taking the browser's pan away is PAID for, not ignored** — with
  `touch-action: none` on a row, a long list can no longer be scrolled by
  dragging one (the header, the gaps and the actions row still scroll it), so
  a drag in flight scrolls the card itself when the finger nears its top or
  bottom edge: `dragMoveTo` starts a frame loop (a finger held still at the
  edge sends no pointer events, and that is exactly when it must keep
  scrolling) and `dragEnd` kills it. Without that half, a drop target below
  the fold would simply be unreachable — one broken gesture traded for
  another.
- **One row is one line, like a button** (owner 2026-08-09, task 163, with his
  screenshot: one row wrapped to FOUR lines beside a two-line sibling). His
  rule: elements of one kin group are always the same size, and a long name is
  CUT — "the first two words, as many as fit — and three dots" — never
  wrapped. `.lay-item-main span` elides in CSS (never in JS: a string cut
  before the DOM is invisible to every clip check, the 2026-08-07 finding
  above), and the trailing chips carry the same nowrap rule, because a chip
  that wrapped would make one row taller through the other half of the same
  kin group. The full name stays one tap further on, in the rename card, whose
  field is a wrapping textarea for exactly this reason. The audit stages this
  panel with THREE layouts now — a list of one has no sibling to differ from
  and no row to drag onto, which is how both bugs shipped.
- **The row was CUT SHORTER SIDEWAYS than upright** (owner width question
  2026-08-09, task 172). The landscape two-column reflow in `panels.css` had
  just been widened from short screens to all landscape — right for the panels
  it was built for, ruinous here: this list's rows carry a name AND four
  trailing controls, so halving the row left the name 87px of 347 and 12
  characters of a 62-character window title, fewer than the same tablet showed
  in PORTRAIT (378px row, 16 characters). `openLayoutPicker` therefore does not
  put `.card-columns` on its card — deliberate, commented, and the class is the
  declaration so the next panel cannot inherit the wrong policy silently. Off
  the reflow the row is 718px with a 458px name: the whole title, at every
  audited viewport, and the card still fits (363px of content in the 377px a
  915x412 phone allows). The price is paid rather than hidden, and counted:
  the list scrolls from the FOURTH layout sideways and the TENTH on a tablet,
  which makes this card a stated exception to BUG A. `openMemberPanel`
  and the creation panel answer the opposite way for measured reasons of their
  own; see [style.md](style.md). Portrait is untouched: whether the 420px card
  should widen for a name is the owner's own open question.

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
  `layout_aspect`; the server stores and echoes it, and the PHONE anchors the
  letterboxed picture with it (owner decree 2026-08-09, the handle's FOURTH
  round — three rounds slid WINDOWS along the PC monitor, a screen he never
  sees, and his tablet stayed centred; the server always centres the windows
  now and the anchor acts in [View Anchor](view-anchor.md), via
  [Render](render.md)'s `computeViewHome`).

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
