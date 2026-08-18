# Layouts

**Script:** [Layouts (script)](../layouts.js) ·
**Flow:** [diagram](../__flow/layouts.md)

## Purpose

LIVING with the layouts that exist: the loading animation, the top-center
layout bar, the layout LIST and its drag, the ✕ chooser and the member chooser
— which layouts exist, which one is shown, and which windows are in them.
Loads after [Controls](controls.md) (whose `keepFocus`, `svg`, `showToast` and
`IN_APP` it uses), before [Gestures](gestures.md).

Two siblings carry the rest of the feature, split off under THE STRUCTURE LAW:
[Layout Create](layout-create.md) MAKES a layout (2026-08-08), and
[Layout Settings](layout-settings.md) CHANGES one — the per-layout ⚙ sheet,
the rename card, the aspect-ratio panel and the orientation/arrangement
choosers (2026-08-09, owner task 175). Both borrow this file's panel
vocabulary and its `.lay-item` row markup; nothing is copied.

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
- [Row tap](row-tap.md) — since 2026-08-15 every row of every list here, and every control inside the scrolling card, uses `keepRowTap` instead of `keepFocus`, so a finger landing on one can still scroll

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
- **Layout list** — `openLayoutPicker`, `layRow`: every layout at once
  (Desktop first), a row taps to focus. Since task 175 (owner 2026-08-09) the
  row is `[icon][⭐][name][shape][⚙]` — the two facts it can carry at a GLANCE
  (which app, what shape) and ONE door to everything else. The rename pencil
  and the aspect chip that used to trail it are gone into that door
  ([Layout Settings](layout-settings.md)); his instruction was to put every act
  under one common settings icon rather than give each its own, and the
  portrait list had been graded 6/10 for exactly that crowding. `layRow`'s
  badge argument takes three kinds — an app-icon URL, `{draw: markup}` for a
  drawing we made, or `null` for the Desktop row's monitor — because the member
  chooser's badge is a third thing and a builder that could only draw two of
  them would have been copied instead of reused.
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
  the DOOR to the member chooser; a SOLO layout renders the same picture as a
  `<span>` instead. The aspect chip's 96 px label floor that used to sit beside
  it is GONE with the chip (task 175): both remaining controls are icon-only
  and drawn at a fixed size, so they agree by construction and there is nothing
  left for a floor to hold together.
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
- **Naming** — `nameField(value, placeholder)` lives here (both siblings use
  it); `openRenamePanel(index)` moved to
  [Layout Settings](layout-settings.md) with the rest of the ⚙ sheet
  (2026-08-09). A layout's auto name is the target window's title; the
  creation panel offers it prefilled in an editable Name field (`creating.name`
  — `null` follows the title, `""` sent means "keep it"), and the list's
  pencil renames an existing one via `layout_rename {index, name}` without
  moving anything on the PC. The field is a WRAPPING textarea, not a one-line
  input: window titles are long enough that a single line hid most of one
  behind its own horizontal scroll (caught by `tests/test_layout_audit.py`,
  THE SPACE & LEGIBILITY LAW); newlines are stripped as they are typed.
- **Aspect panel** — moved to [Layout Settings](layout-settings.md) on
  2026-08-09 (`openAspectPanel`, `renderAspectPanel`, `updateAspectPreview`,
  `aspFrac`, `clampAspect`, `dragAspect`, `ratioPair`, `devicePair`): W : H
  fields over a dashed phone-screen preview with the region inside it. Its
  rules are unchanged and its Design Decisions stay below, where they were
  argued. The state is one continuous number (`a` = W/H); the fields render
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
  *"čip sa izabranim prozorom skraćuje naziv na 'Claude Code - Vibe Coder - V…', a pun naziv se na tom ekranu ne vidi nigde kada polje Name već prepišeš"* — lang-ok: owner quote.
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

- **The eject button draws `ejectwin`, not `newwin`** (grader flag a, task
  233): the member chooser's eject act now has its own arrow-leaving-a-frame
  icon, distinct from `addwin`/`splitwin` in
  [Layout Settings](layout-settings.md) — see [Icons](icons.md).
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

## The row's two facts, and one door (owner 2026-08-09, task 175)

A row of the layout list shows what it can say at a GLANCE — the app's icon,
the ⭐ if other layouts' content lives in its windows, the NAME, and the drawn
SHAPE — plus a ⚙. Everything a layout can be ASKED lives behind that one icon:
rename, aspect ratio, orientation, arrangement, and taking one window out. See
[Layout Settings](layout-settings.md) for the sheet and for why orientation is
an act rather than a door.

The section that stood here until 2026-08-09 described a row of app-shortcut
TICKS in the rename card. Those were removed on 2026-08-07 — the PC recognises
what runs in a window by itself (`agents` in every state frame) — and the page
already said so two bullets above; the section outlived the feature it
described, which is the drift the Living Docs Rule exists to stop.

## The bar is part of the top row, and it can stand at the bottom (task 160)

Owner 2026-08-09, in translation: this central layout-and-arrows switcher must
have the SAME style as the other buttons — as Layout and Hide — that height,
that radius, the whole top row's treatment, not something different of its own.
And: in the settings there should be two options, one that it appears and
stands at the top, another that it appears and stands at the bottom.

- Every piece of the bar takes `--corner` for its height and 16 px for its
  radius — the numbers `.ctl` itself uses, read from the same tokens rather
  than copied, so a later retune of the corner buttons carries the bar with it
  instead of leaving it behind again. The arrows became BUTTONS of that row
  (fill, border, radius) instead of glyphs standing on the bare stream.
- `layBarPos()` / `setLayBarPos()` hold "top" (the default, and what has always
  shipped) or "bottom", per device through the shell's prefs bridge. One class
  says the DECISION — `body.laybar-bottom` — with top as the base rule.
- **At the bottom it sits ABOVE the D-pad, never on it.** The two groups own the
  bottom corners and, on a 412 px phone in the cross shape, they meet in the
  middle. `--group-h` (declared in `client/style.css` beside the grid that
  decides it) is what the bar clears, plus the same `--kb` and safe-area insets
  every other bottom-anchored element respects.
- **And down there it spends the WHOLE band** (independent grader,
  2026-08-11). The top position reserves the width of a corner button on each
  side because at the top that is literally what stands beside it — Layout (+)
  and Hide. At the bottom nothing does: the D-pad groups are BELOW, which is
  exactly what the `--group-h` above clears. Those two reservations were
  therefore 164 px of idle band held for buttons in another row, while the bar
  stayed 248 px wide and gave a 111-character layout name 36 px to live in —
  eight readable characters, wrapped to two lines and THEN ellipsed. Rung 1 of
  the resolution ladder: `body.laybar-bottom` drops the reservations
  (`left`/`right` become plain `--space-m`), `#lay-frame` grows into the band
  (`flex: 1 1 auto` — at the top it must NOT, or the name would push the arrows
  out, owner 2026-08-03), and the name takes **one** line plus an ellipsis
  instead of two clamped ones, so the bar stays exactly one row tall against
  the D-pad it has to clear. Measured after the fix: 380 px of a 412 px screen
  with 193 px for the name, 883 px of 915 with 696 px for the name.
- The Top / Bottom chips **left this card on 2026-08-11** (task 218a). The note
  that used to stand here said it plainly: they sat on the layout list because
  the Sets picker next door was the wrong room too, task 161 was the open
  request to gather the small switches properly, and "guessing at that
  gathering here would be a second home for the same switch the day it lands".
  Task 161 landed. They live on the Phone card
  ([phone-panel.md](phone-panel.md)), and they did not stay here as well — a
  switch with two doors is two states to keep in step. `layBarPos()` /
  `setLayBarPos()` are unchanged and still live in this file.

## The bar's MINIMUM width, and the bottom position rebuilt (task 237, verdict ~21:4x)

His full spec, BALLOT-approved with one correction to the drawings: TOP is
unchanged from the 2026-08-11 fix above — the name takes almost the whole row,
the arrows are slim glyphs (~2 px gap) tight against the frame. BOTTOM is
IDENTICAL to the top drawing, only at the bottom: WHEN THERE IS ROOM the bar
sits **IN** the bottom controls row, between the left and right D-pad columns,
at the SAME width/height/style as the top row, with the same edge gap from the
bottom the top row has from the top. It is **never** on its own strip above
the pads while there is room in the row — that shape (the one this file
described above, "above the D-pad, never on it") is now the approved OVERFLOW
fallback only ("slika 2 ok"), not the default any more. And there is a MINIMUM
width: below it the bar takes its own full row instead of being squeezed —
at TOP the Layout/Hide corners drop to the row below the bar; at BOTTOM the
bar falls back to its own strip above the pads (the pre-237 shape). LANDSCAPE
honors the Top/Bottom setting (bug fixed — it used to always sit at the top,
full width regardless) and is centered under a ~560 px cap.

- **`layBarFit()`** (client/layouts.js) is the new measurement: it reads the
  REAL gap between whatever would share the row with the bar — the two corner
  buttons at the top, the two `.group` elements at the bottom — and toggles
  `body.laybar-overflow` when that gap is under `LAY_BAR_MIN_GAP` (356 CSS
  px). It runs after `updateLayoutBar()`, `setLayBarPos()`, `refreshCategories()`
  (a set swap rebuilds the groups) and `setPadShape()` (cross vs. column
  changes a group's width), plus on `resize` and `visualViewport` resize — a
  D-pad rebuild or a rotation is exactly when the measurement can change.
  Landscape is skipped entirely (it removes `laybar-overflow` and returns):
  landscape has no in-row/overflow CHOICE at all, only the centered/capped
  shape below, so measuring the portrait gap there would be meaningless.
- **The number: 340 CSS px of bar content** (356 measured as the gap between
  neighbours, which folds in the bar's own 2×8px margin to them), chosen from
  his two real devices (owner spec ~21:5x) — a phone (412-class CSS width)
  must OVERFLOW at both positions; a tablet (a 1280x800 tablet rotated
  upright, ~800-class CSS width) must FIT at both. The reservation on each
  side is `space-m + X + space-s` where `X` is `--corner` at the top and the
  new **`--group-w`** at the bottom (client/style.css, declared beside
  `--group-h` the same way — a group's real rendered width, `3*corner+16px`
  in the cross shape and plain `--corner` in the column shape, which is what
  portrait uses by default, so top and bottom reserve the SAME width there).
  Measured: phone-top gap 264px, phone-bottom gap 0-264px depending on pad
  shape, tablet-top gap 652px, tablet-bottom gap 388px — 340 sits with slack
  on every side of that 320-360 window so a later font or corner retune
  cannot flip the verdict by a few pixels.
- **The bottom in-row rule** (`body.laybar-bottom:not(.laybar-overflow)
  #layout-bar`) puts the bar's own bottom edge exactly where a `.group`'s is
  (`space-m + --kb + safe-area`) and caps its width at `--laybar-max` inside
  the room the two columns leave (`--group-w` mirroring the top row's own
  `space-m + X + space-s` formula). No frame override is needed — the base
  `#lay-frame { flex: 1 1 auto }` rule already applies. **It is not scoped to
  an orientation** — see the 2026-08-12 section below, which rewrote both
  halves of this rule.
- **The overflow fallback** at the bottom (`body.laybar-bottom.laybar-overflow
  #layout-bar`) is the exact pre-237 rule this file described above: its own
  strip, above the D-pad, spending the whole edge, one-line name. At the top
  (`body.laybar-overflow:not(.laybar-bottom)`) the bar takes `left`/`right:
  var(--space-m)` (its own full row) and `.corner` drops to
  `top + --corner + --space-s` — below the bar's row. `--topbar` (the line
  every floating notice starts below) grows by one more `--corner` in this
  state, so a toast never covers the dropped corner row.
- **Landscape used to be its own geometry**, in `@media (orientation:
  landscape)`: centered, capped at 560 px, and at the bottom clearing the
  D-pad's whole height because a 560 px bar on a 915 px phone already reached
  into the two groups' own band. Both halves were folded into the shared rules
  on 2026-08-12 (below) once the cap came down to 420 px and the band became
  wide enough to sandwich the bar in every size this project ships to.
- **Why the portrait rules are wrapped in `@media (orientation: portrait)`
  instead of standing bare**: a media query changes WHEN a rule is eligible,
  never its SPECIFICITY. The bottom-position class selectors
  (`body.laybar-bottom … #layout-bar`, specificity 1,2,1) outrank the plain
  `#layout-bar` landscape rules (1,0,0) regardless of which orientation is
  actually live, so an unscoped class rule still won the cascade in landscape
  too — found live while building this round (the bar tried to center inside
  a `left`/`right` box the portrait rule had already pinned, landing 280 px
  off-screen). Scoping both sides to their own orientation lets the simpler
  selector govern in landscape without a specificity fight.
- Gate: `tests/test_phone_chrome.py` → `_bar_geometry_checks`, planted-defect-
  proven claims, one set per size in `SIZES` (portrait phone, landscape, and
  the tablet-portrait 800x1280 entry) — his phone overflows both positions,
  his tablet fits in-row at the bottom, and landscape honors Bottom. Their
  exact numbers were re-decided on 2026-08-12; see below.
  `tests/test_layout_audit.py` and `tests/run_guards.py` stay green; visual
  proof in that round's layout report (ROUND 44) — the file itself was
  retired on 2026-08-18; screenshots now land in `.claude/evidence/` via
  `uv shot`.

## One maximum, one bottom row, and no bar means no row (owner 2026-08-12)

Three reports of his landed on this same strip of screen, and the fix for each
is one rule:

- **"The maximum width is too large."** There were two answers before — 560 px
  in landscape, and no cap at all in portrait, where the bar simply stretched
  between whatever stood beside it. There is ONE now: `--laybar-max`, **420
  px**, declared at the top of `client/layouts.css` and spent by EVERY in-row
  placement (top and bottom, portrait and landscape). The base `#layout-bar`
  rule is what centers and caps — `left: 50%; transform: translateX(-50%);
  width: min(--laybar-max, 100% − 2·(space-m + --corner + space-s))` — so the
  bar is never stretched edge to edge between its neighbours again. What the
  old bounded-both-sides rule protected (a long name pushing the › arrow or
  the ✕ off the screen, owner 2026-08-03) is now the `width` calc's job, and
  the name still wraps to a second line rather than growing the box.
  The OVERFLOW shapes are the exception and undo the cap explicitly
  (`width: auto; transform: none` with both edges pinned): there the whole
  point is the full row.
- **"With the bar at the bottom it draws above or among the button groups,
  never down in the bottom row where it belongs"** (his tablet, BOTH
  orientations). The in-row rule used to centre the bar on the groups' HEIGHT
  BAND, `(--group-h − --corner)/2` — and that band is 190 px in the cross
  shape but **306 px** in the column shape, so the bar climbed a third of the
  way up a tablet and past half of a phone. A bar that rides IN the row shares
  the row's BASELINE: `bottom: space-m + --kb + safe-area`, byte for byte the
  `.group` rule's own bottom, whatever shape the pads wear. The rule also left
  its `@media (orientation: portrait)` wrapper, because his report named
  landscape too — with the 420 px cap there IS room between the columns at
  every size shipped (915 px landscape phone: 487 px of band; 1280 px tablet:
  852 px), so landscape's separate "clear the whole D-pad" rule was deleted
  rather than restated. Clearing the groups' full height is now the OVERFLOW
  shape alone, where it is unavoidable: a full-width strip crosses both
  columns and cannot share their row. **In that shape the ROW moves instead of
  the bar** — the pads are lifted by exactly one bar (`--corner + --space-s`)
  so the strip has the edge to itself.
- **The pads' lift is INSTANT, and it took T89 (2026-08-14) to see why it was
  not** (`tests/test_phone_chrome.py` had been failing at 412x915 — his own
  phone's CSS size — and nothing ran it: it was wired into neither
  `setup/gates.py` nor `setup/build.py`, so every release shipped over it).
  The lift used to raise the pads' own `bottom`, and `.group` carries
  `transition: bottom 0.1s ease-out` (client/style.css) for the SOFT KEYBOARD.
  A row RESERVATION is not a keyboard: the bar is painted in its new row the
  instant `laybar-overflow` lands, so animating the pads' half of one layout
  decision drew the full-width strip straight across BOTH D-pad columns for
  the whole 100 ms — every time the bar moved to Bottom, and every time the
  first layout was born with Bottom already chosen. The reservation now rides
  `margin-bottom`, which that transition does not name and which therefore
  applies on the same frame; for a fixed box with `bottom` set the margin is
  part of the offset, so the geometry is byte for byte what the old rule
  computed. The keyboard glide `bottom` owns is untouched.
- **"Pressing nothing at all, the top buttons sit one row down."** With NO
  layout created there is no bar — and `layBarFit()` measured the corner-to-
  corner gap anyway. On any phone-width screen that gap is under the minimum,
  so `laybar-overflow` was set at load, the corners dropped a whole row and
  the space they left was reserved for a bar that does not exist. It now
  clears the class and returns when `layoutBar.hidden`; `updateLayoutBar()`
  sets `hidden` before calling it, so the verdict is re-taken the moment the
  first layout is born and again when the last one goes.

Gates: `_bar_geometry_checks` in `tests/test_phone_chrome.py` — the tablet's
in-row bar is measured against the D-pad's own baseline and the 420 px cap,
landscape asserts the same two plus "between the columns", and a new check
drives BOTH bar positions with no layouts staged and fails if either the
overflow class or a dropped corner survives. Both new claims were proven red
by planting their own defect. T89 added a check at his own phone's size that
reads the pads' bottom edge TWICE — on the frame the bar takes the row and
again once anything moving has settled — and fails on either an overlap or a
difference between the two, because a settled-only test cannot tell an instant
lift from an animated one. **The whole file is now fail-closed in the build**
(`setup/gates.py` → `0b16/6`, beside the input gate it shares a browser
toolchain with).

## The desktop is a LIST OF MONITORS (owner 2026-08-09, task 155)

His instruction: Monitor leaves the Settings menu and becomes part of these
layout panels — where it now says "Desktop" it will say, if there is more than
one monitor, Monitor 1 and its resolution, Monitor 2, and so on.

- The rows are drawn from `monitorList` / `monitorIndex`, two OPTIONAL fields on
  the `config` frame the server already sends (`server/monitor_api.py`). A
  server too old to send them, and a PC with ONE screen, both draw the single
  "Desktop" row that has always shipped — the same, already-proven path.
- Tapping the monitor it is ALREADY on is a plain "back to the desktop"
  (`layout_focus -1`); any other sends `monitor_switch` carrying that index,
  which the server already answers by leaving the focused layout and showing
  the bare desktop there. `index` is optional on a message that has always
  existed, so an older PC still cycles.
- No loading cube for the switch: the cube is dropped by the `layout_state`
  that follows a placement, and a switch made from the desktop sends none.

It frees the Settings slot the Monitor cycler was spending — the action itself
stays in the client's BUILTINS, so a custom set can still carry it.
