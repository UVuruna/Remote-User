# tests/

End-to-end regression gates PLUS the four project guard tests (rules/CODE.md
→ Enforcement). Per rules/DOCS.md's tier table, every file in this folder is
**tests tier — this folder doc is the only doc any of them get**, individual
files are not otherwise documented below except by name and one line.

## Files

### `test_input_pipeline.py` — Input Pipeline Gate
The REAL client page and the REAL server app, driven by a REAL headless
Chromium with touch emulation; only injection is faked (a recorder replaces
`SendInput`). Every scenario walks the full chain:

```
touch on the page → Pointer Events → WebSocket protocol → FastAPI handler → injector call
```

Scenarios: cursor steering (and the no-tap decree — a canvas touch never
clicks), the Click button (left), the Right button (right click), a chord
button, **the stolen-tap rescue** (Android ends edge-zone touches with
`pointercancel` — a no-travel cancel must still fire or buttons die
on-device, the 2026-07-26 live failure) and its inverse (**a system swipe
crossing a button — real travel, then cancel — must NOT fire**), edge
reachability with no reserved margin (the pointer sits exactly under the
finger — the offset system is gone), keyboard capture (typed
text + the Shift+Enter new-row rule), **the mic-survives-the-tap rule**
(owner 2026-08-09, amending the 2026-08-04 both-off rule: he steers the
cursor WHILE dictating, so a canvas tap closes only the KEYBOARD and a
listening mic keeps listening — while Esc (`inputOff()`) and the keyboard
going ON still switch the mic off), **the /ping contract** — the
endpoint must answer EXACTLY 204: the Android shell's reachability probe
counts only 204 as "the PC answered", because captive portals on foreign
Wi-Fi answer any request with a 2xx/redirect login page (live failure
2026-07-27); a drift to 200 would strand every phone — and **the injection
tripwire** (`InjectionMonitor` decision logic): Windows silently discards
all injected input from a non-elevated process while an elevated window
has focus (UIPI, live failure 2026-07-29 — SendInput "succeeds", the phone
looks healthy, the mouse is dead); the monitor must alarm on exactly the
configured miss streak, ignore small jumps, and re-arm after a success —
plus the WIRING: the real `InputInjector.move()` (with `SendInput` stubbed
out, so the build machine's cursor is never touched) must raise the alarm
that the web layer forwards to the phone, and clear it once read.

**The gamepad** (build rounds G1/G2, 2026-08-07) is gated in the same file
and by the same standard: synthetic pad events are driven through the page's
REAL mapping (`__padButton` / `__padAxis` — the two names the Android shell
calls) and the exact protocol that must come out is asserted. A D-pad arrow
presses the LEFT group's button in that direction and HOLDS the PC button
while the key is held; a face button presses the RIGHT group's, on the
RELEASE; L2/R2 are Layout (+) / Hide; the left stick steers on the tuned
curve at three deflections including the deadzone; the right stick scrolls
(and up is up); L1 held + a stick + release picks a wheel category and fires
NO button; a short shoulder tap steps the layout bar instead. Because the pad
is only ever let in through `buttonPress()` — the same activator a finger's
`pointerup` runs — this block also pins that there is no second button path
left to drift away from the pointercancel rescue (CLAUDE.md constraint 9).

The **stick curve is pinned by SHAPE, not by number**: the gate reads
`PAD_DEADZONE` / `PAD_CURVE` / `PAD_CURSOR_SPEED` out of the page and
recomputes the expected coordinate independently. The owner's answer to the
open question was "start from this table and tune it on the real controller",
so retuning the feel may never turn a build red — changing the FORMULA must.

The control layout comes from `tests/fixtures/actions.json` — pinned on
purpose: the repo `actions.json` is the owner's hand-edited file, and a
layout edit there must never block a build.

Run directly:

```
.venv\Scripts\python tests/test_input_pipeline.py
```

Requires `pip install playwright` + `playwright install chromium` (dev/build
machine only — nothing of this ships in the app).

### `test_layout_audit.py` — Layout Audit (THE SPACE & LEGIBILITY LAW)
The real page in a real headless Chromium at phone sizes (portrait 412×915,
landscape 915×412): every overlay panel is opened and measured — the card
fully inside the viewport, no horizontal page overflow, nothing clipped
inside it.

**CONTRAST** (owner 2026-08-06: *"je l' moguće da prođe situacija sa dizajnom
elemenata i bojama"* — six white buttons carrying near-white labels, and every
geometric check green). Text nobody can read is not a style opinion; it is
unreadable content, which is this law's whole subject. Every leaf text node is
measured against its **composited** backdrop — each translucent layer painted
over the one below, down to the page — and anything under a 3.0:1 WCAG ratio
fails, naming the element and the ratio. Compositing is not a detail: the first
version of this check ignored alpha and called this project's own translucent
selected states 1.00:1, and a guard that cries wolf gets switched off. It found
two real defects on its first honest run — the Sets picker's live badge at
1.96:1 (`var(--bg)` is not a token here, so the declaration was invalid and the
badge inherited near-white ink) and the command chooser's rows at 1.05:1 (a
`<button>` with no background of its own takes the WebView's light default). Covers the Quality panel, the Sets picker, the Dictation card,
the Aspect panel (incl. the Move handle's hit size), the layout list with
its rename button, the Rename card and the creation panel's Name field.
Also checks `grids._fit_rect` purely: the placed region never
leaves its box and sits centred, at any aspect (`pos` left the server's
geometry on 2026-08-09 — the phone anchors the letterboxed picture,
`tests/test_view_anchor.py`). Proof source for
`.claude/layout-proof.md`. The Name fields are WRAPPING textareas because
this audit caught the one-line version hiding most of a window title behind
its own horizontal scroll (2026-08-05). Also checks the D-PAD BUTTONS: a set's
pool may hold reserve commands whose names are longer than the shipped four
("Copy path", "Go to file"), the law forbids eliding them, so the label wraps —
and the wrapped label must still sit fully inside its 58 px button.

**TEXT CUT BEFORE THE DOM EVER SEES IT** (`__truncated`, independent grader
2026-08-07 — the hole that let the owner's own complaint pass three rounds
green). Every other clip check in this file measures the DOM: `scrollWidth >
clientWidth`, a card wider than its viewport, a label outside its button. A
string JavaScript shortened BEFORE the node existed defeats all of them by
construction — `client/layouts.js` did `s.title.slice(0, 29) + "…"`, so the
element fitted perfectly and the audit could only report PASS while 225 device
px stood idle on the same row and the owner was writing *"a pun naziv se na tom
ekranu ne vidi nigde"*. The tell such a cut leaves is the ellipsis IN THE TEXT,
so that is what is measured: a text node ending in "…" (or "...") with more
than 24 CSS px still free to its right on its own row, failing with the string,
the element and the number. CSS elision leaves no ellipsis in the text — that
case belongs to the `scrollWidth` check, and the two together cover both ways a
string can be shortened. The one deliberate ellipsis this app draws ("More
languages (2)…") declares itself with `data-opens-more` in `client/panels.js`,
in the product rather than in an allow-list nobody editing the product would
see. Self-tested by planting the cap again: 14 checks fail, naming *"Claude
Code - Remote User - V…" … was cut with 129 CSS px still free on its row*.

**THE REGION FRAME OPENS CLEAR OF EVERY CONTROL** (same grader). `#region-panel`
draws at z-index 55, above every control, so a newborn grab frame lying on one
paints its dashed edge and its 44 px handles across that control's label — his
picture read "Layou" where the corner button says "Layout". The default rect is
now placed in the band the chrome leaves free, and this check measures the
frame, its four handles and its hint bar against every `.corner`,
`#layout-bar` and `.group` rect, in both orientations. The panel's own entry in
`PANELS` was also changed to open at that default (`rgBox = null`): it used to
be staged into the top-left corner, which proved nothing about the bottom-centre
bar it claimed to test and handed every grader a picture of a state the product
never opens in.

**EIGHT LOOKS, not one** (build round R3, 2026-08-07). The desktop now
chooses one of four phone themes (dark / light / colored / colored-light —
the fourth arrived the same day with the owner's colour correction) and one of
two fills (outlined / filled), so there are eight real renderings of every
surface and a theme audited in one combination is not audited. The two
coloured themes are not variations of each other for this file's purposes:
they are different pages under DIFFERENT palettes (`server/config.py` ships
two), which is the whole reason the colour sweep exists — a colour that reads
on one surface can be invisible on the other. `_apply_look` therefore fetches
the palette through `config.ui_config()` instead of carrying a table of its
own, so the audit can never measure the light page with the dark colours. The full panel sweep runs in
every combination at PORTRAIT (narrowest cards, where a row starves first);
landscape keeps the default look, because what landscape tests is GEOMETRY and
geometry does not change with a colour. Three things changed with it:

- the contrast check's page FLOOR is read from the live `--surface-0` instead
  of the dark theme's literal `[15, 23, 42]` — otherwise every light panel
  would have been scored against a dark page that is not there;
- the check moved into one installed `window.__contrast(root)` so the panels,
  the D-pad and the wheel are judged by the same function, not three copies;
- **the D-pad groups and the category wheel are measured too.** That is where
  a set's colour actually lands in the coloured themes, and no panel check had ever
  looked at them. Self-tested by forcing `theme.js`'s `inkOn()` to return white
  whatever the surface, so
  every ink comes out white: thirteen labels go red at 1.74–2.72:1 in
  `colored/full`, in both orientations, and green again when it is put back.

**A LOOK-NAMED SHOT MUST BE THAT LOOK** (`_shoot`, 2026-08-07 — the tooth this
file was missing, and the reason three rounds of independent graders were
handed pictures of the wrong look while every check printed PASS). Twelve
`Controls*` pictures carry a theme and a fill in their filenames, and nothing
here had ever compared those two words with `body.dataset.theme` /
`body.dataset.fill` at the instant the shutter fired. Two of the twelve
therefore showed a different look: `Controls_dark_full.png` was byte-identical
to `Controls.png` (max per-channel diff 0 over all 1,507,920 pixels; both
87,024 px of the 20 % tint `rgb(18,26,45)`, never the solid `rgb(30,41,59)`),
and `Controls_light_transparent_landscape.png` rendered the dark page
`(15,23,42)` where its portrait twin renders `(236,238,246)`. Both were
labelled `audit: PASS`. Two things close it:

- `_shoot(page, label, look, results)` is now the ONLY way a look-named shot is
  written. It reads the two dataset attributes, records a per-shot result, and
  **FAILS the audit** — not warns — when they disagree, printing `asked for
  X/Y, the page was showing A/B at the shutter`. The picture is still written:
  a grader has to be able to see what was measured.
- The drift itself is gone at both ends. `_apply_look` also calls
  `config.apply(phone_theme=…, phone_fill=…)` — the audit runs the real server
  in THIS process, so the look it asks for is the look every later `config`
  frame carries, instead of the audit fighting its own server (in-memory only;
  `save_user_settings` is the sole writer of the owner's file). And the page's
  readiness gate now waits for `monitor.w > 0`, the socket's first `config`:
  `#group-left button` goes green about **1.4 s** earlier — the D-pad renders
  from the page's own defaults — and everything done in that window used to be
  silently overwritten when the frame finally landed. Exactly one look per
  browser context was being stomped, which is why the wrong picture moved from
  run to run.

Self-tested by planting the reset back: `_apply_look` was made to close the
socket and wait 2.5 s, delivering a `config` between the request and the
shutter exactly as it used to happen by accident. **35 look-named shots go
red** in one run (`the shot shows the look it is named for: Controls dark
full → FAIL`), `Controls.png` and `Controls_dark_full.png` return to a
per-channel difference of **0**, and every `light` shot returns to the dark
page. Restored, the audit is green and the same pair differs by R13 G16 B15
across 134,804 pixels (8.94 %), with the filled shot carrying 87,023 px of the
solid `rgb(30,41,59)`.

**THE DICTATION CARD'S THREE ROW STATES, AND WHOSE LANGUAGES THEY ARE** (owner
2026-08-09, task 127). The card now names the DEVICE it describes and offers a
listen button per language, so the sweep alone is not enough: it measures fit
and contrast, but it cannot say whether the states that carry the honest limit
are on the card at all. `tests/_audit_panels.py` → `DICT_STAGE_JS` therefore
stages four rows on purpose — sr-RS and en-US (a voice AND a sample → the
button), de-DE (no voice on this device) and is-IS (a voice, no sample
sentence written) — and a dedicated check asserts all three states are
present, that every listen button is a ≥40 px finger target inside the card
and clear of its own row's name, and that the device line contains the model
THIS browser context's User-Agent carries (`UA_MODEL`) rather than the
"this device" fallback, which renders perfectly while the real path is broken.
Self-tested by planting both defects: dropping `speakAs` from the stub turns
the whole card into the no-preview case (**4 findings** — no listen button, no
honest-limit row, and each of the two notes named), and asserting a model this
context never sends reports the line's real text back. A row state nobody
stages is where this project's bugs keep arriving.

**THE LAYOUT LIST'S THREE MARKS** (owner, 2026-08-09, tasks 164 / 165 / 169).
The staged list (`LAYOUT_LIST_STAGE_JS`) is three layouts of three DIFFERENT
shapes now — a two, a solo and a four — because a staging that cannot tell the
new drawing from a constant proves nothing about it; the first row is
`parent: true`, so the ⭐ lands on the hardest row there is (the 63-character
VS Code title, its elision, and all three trailing buttons at once). Two
instruments in `tests/_audit_js.py` measure what the sweep cannot:

- `__kinRows` now compares the trailing buttons **column by column**. It used
  to take one chip per row with `querySelector` — whichever comes FIRST in the
  DOM — so putting a third button in front of it would have silently changed
  what the tooth watched and left the old kin group unmeasured. Every column
  is its own kin group: shape against shape, pencil against pencil, aspect
  against aspect.
- `__layoutStars(layouts)` asserts the star from the STAGED LIST rather than
  from a row number: Desktop is never starred, a `parent` layout always is, a
  non-parent never is, the star renders at a real size, sits before the first
  letter on the name's own line, and the long name still elides beside it.
  Its own instrument because both ways it can fail are invisible to everything
  else here — landing on the wrong row is a fact about which LAYOUT, and a
  colour emoji's own metrics lifting its row above its siblings is task 163's
  kin defect arriving through a new door (which is why the kin measurement
  runs on the same staging, with the star on it).
  Both this and `__kinRows` END by demanding that the >40-character name really
  overflowed — an elision rule nothing exercises is a rule nobody is checking —
  and both said so out loud when task 172 gave the layout list its landscape
  row back (718px, one column): 62 characters now FIT. The fixture grew instead
  of the tooth shrinking. `_LONG_TITLE` in `_audit_panels.py` is 111 characters
  — what Claude Code's VS Code window is really called, the conversation's name
  in front of the project — which elides in the widest row this list can draw
  as well as in the narrowest. The member titles stay at 62: their rows are the
  two-column ones, where 62 already overflows.
- `__nameRoom(card)` (2026-08-09, task 172) fails any row that gives its NAME
  less width than the widest button beside it. Everything above judges the row
  as geometry, and the shipped row passed all of it while being useless: equal
  heights, nothing wrapped, nothing off the card, and 48 px of name beside a
  96 px chip that said "Screen" — legal, aligned and unreadable, which is
  exactly the gap THE SPACE & LEGIBILITY LAW exists to close. A pixel floor
  would have closed it too, but a floor of "at least 90 px" is an opinion with
  no argument behind it and the first row needing 92 would be a negotiation
  instead of a defect; a RELATION in the row's own terms has nothing to tune
  and drifts with no font. Proven by planting the shipped row back into the
  live page (the glyph re-inserted, the floor back at 96 px): red at all four
  viewports — 48 < 96 at 412 px, 57 < 96 in both landscapes, 88 < 96 on the
  tablet — while `__kinRows` stayed green on the same staging, which is the
  whole reason it needed an instrument of its own.

- `__settingsSheet(members)` (2026-08-09, task 175) — the ⚙ sheet IS its list
  of acts, so what has to be true of it is not a geometry: a SOLO layout has no
  window to throw out and no arrangement to choose, and offering either would
  be a control that cannot act. Nothing else here can see that — a row that
  does nothing is legible, unclipped, the right height and inside the card. It
  asks both shapes (a THREE, the fullest the sheet gets, and a solo) and the
  arrangement chips are demanded for a three and for nothing else, which is the
  asymmetry of the owner's own sheet. Proven by planting `members > 0` for the
  member row → *"a SOLO layout offers to take a window out of nothing"* at all
  four viewports.
- `__closeWarning(dependents)` (2026-08-09, task 171) — WHICH option of the ✕
  chooser carries the "Also destroys …" line is a fact about MEANING, not about
  pixels: a warning printed under the harmless act, or under both, is worse
  than none. It demands exactly one warned option, that it is the one whose
  label says *close*, that every staged dependent is NAMED in it, and that the
  line is neither clipped nor outside the card — plus the negative case, that a
  layout with no dependents is warned about nothing. Proven by planting the
  removal of `dependentWarning(lay)` → *"0 of the two options carry the warning
  — only the CLOSE one may"*, all four viewports.
- `__scrollInColumns(card)` (2026-08-09, found by photographing the creation
  panel at 915×412) — a scroll container inside a `column-count` card. Every
  other instrument here measures a rendered box and each of them was GREEN on
  that panel: nothing overflowed the card, no text was cut before the DOM saw
  it, the contrast was fine, the rows were the same height. The defect is a
  COMPOSITION of two layout modes that are each correct alone, so what is
  checked is the composition — no number to tune, and it generalises to any
  future panel. Proven by planting the card back to `card-columns` → *"lc-rows
  lc-scroll scrolls (276 in 157) inside a 2-column card — a fragmentainer does
  not clip it, so its rows paint over whatever the next column holds"*.

**AND THE ROWS CARRY REAL APP ICONS** (task 172). `LAYOUT_LIST_STAGE_JS` staged
`icon: null` on every layout, so `layRow` fell back to the Desktop row's monitor
and the picture showed FOUR IDENTICAL leading badges. The server sends a real
per-app icon per layout (`layout_registry` → `wm.icon_data_uri`), so the grader
who opened that picture read a variable as a constant and proposed deleting it
to make room for the name. A fixture that renders a variable as a constant does
not merely fail to test the feature — it argues, in a picture, for removing it.
Three data-URI stand-ins now ride the fixture, because the real icons come off
EXEs on the owner's machine and this audit runs anywhere.

The member chooser (task 165) is staged on the FOUR — four member rows, each
with its own cell of the grid lit, plus the arrangement row only a 4→3 shows —
and measured by `__kinRows` plus `__memberCells`, which reads the LAST path of
every row's drawing and fails when two rows light the same square. The whole
panel rests on "he picks the window by its position", and four VS Code windows
have four nearly identical titles. The layout list also joined `COLOUR_SHOTS`:
the ⭐ is the one mark whose ink the palette does not own, so it is
photographed on a light card as well as a dark one.

**THE CREATION LIST, PHOTOGRAPHED AT LAST** (2026-08-09, tasks 166 / 167 /
168). The round that rewrote every row of it shipped without one picture of it:
the only creation panel ever staged had `creating.slots` and no list at all, so
the indent, the tab rows, the minimized note and the cap had never been drawn
anywhere. Two entries close that. `CREATION_LIST_STAGE_JS` stages six rows — a
62-character VS Code window with THREE tabs indented under it (worth 3 members,
not 4 rows, which is the cap's own arithmetic), a minimized Chrome that must
SAY why it offers no tabs, and a plain Explorer window; "Creation panel capped
at two" stages the other half of task 166, the only state that puts the missing
3 and 4 chips, the line explaining their absence and a dimmed not-ready Create
on one screen.

`__kinRows` runs on those rows too, and it had to learn the owner's own ruling
first: **a child is not in its parent's kin group** (task 168 — which is what
makes the indent legal at all). Rows are grouped by their live left inset
(`margin-left` + `padding-left`, so `.lc-kid`'s 30 px splits the groups) and
every relation — height, trailing-button columns, main-button width — is
measured INSIDE a group. The key is the inset and never the row's absolute left
edge: a short-landscape card is a two-column multicol, and the layout list's
rows really do land in both columns while remaining one kin group. Proven by
planting: one tab row made taller than its two tab siblings goes red, one tab
row wrapped to two lines goes red, one window row taller than its window
siblings goes red — and ALL tab rows taller than ALL window rows stays green,
which is the ruling itself.

**The panel catalogue moved out** on 2026-08-09 (THE STRUCTURE LAW — the
listen control pushed this file past 1,000 lines): `tests/_audit_panels.py`
now holds WHICH overlay is opened and in WHAT state, the boundary this file's
own docstring already drew, while `tests/_audit_js.py` keeps HOW a truth about
pixels is measured. The same wall was met again the same day, by the star and
member checks: both went into `_audit_js.py` as instruments rather than as
inline JS strings, which is the boundary that file was cut on — and a third
time by the creation-list entry, which took the audit to 998 of its 1,000
lines, so `COLOUR_SHOTS`, `LANDSCAPE_SHOTS` and `SHOT_SUBJECTS` joined the
catalogue as well: which picture a panel is worth, and which subject folder it
lands in, is the same row of the same catalogue read one step further on.

**TASK 151 (2026-08-10) — the never-blank canvas and the truth-table wiring,
restored.** This file was already at EXACTLY 1,000 lines when the mechanism
landed — zero headroom, unlike either earlier split — so
`LIVE_CLOCK_BLANK_JS` (paints the canvas a known colour before and after a
starved decoder, proving a gap leaves the last picture alone) and
`LIVE_CLOCK_DRIFT_JS` (the same six-case truth table `tests/test_live_clock.py`
proves in isolation, driven here through the live page's own globals) joined
`tests/_audit_js.py` rather than landing inline. A third, one-time check —
`render.js` must actually call `liveAction`/`liveRegulate`/`liveSeekTarget` —
sits beside `_fit_rect_audit`/`_grid_audit` in the results dict this file
builds before opening a page, because it too is independent of screen size.
Proven by planting: removing the never-blank guard from `redraw()` turns the
blank check red at every SIZE; making `render.js`'s `applyLiveDecision`
call neither function under an `if (false)` guard turns the wiring check red.

Run: `.venv\Scripts\python tests/test_layout_audit.py`

### `test_layout_audit_qt.py` — Layout Audit, Qt windows (THE SPACE & LEGIBILITY LAW)
The runtime half of the law for the DESKTOP app (MIGRATE-LAYOUT.md step 2,
owner go 2026-08-05). Every Qt window the project has — `MainWindow`,
`ControlsEditor`, `ChordRecorder` — is built offscreen in its FULLEST
realistic state (a running server with a Tailscale URL and the longest guided
text; the set with the longest command pool), shown at its DECLARED minimum
and at +50%, and its whole widget tree measured for: CLIPPED (a widget with
less room than it minimally needs), ELIDED (text wider than its element),
ITEM CUT (a list/table row wider than its column — Qt's item views truncate
silently, and an item is not a QWidget, so the widget checks cannot see it),
SCROLL+SLACK (something scrolling while a spacer in the same window holds
unused space), plus the law's precondition: a declared, computed minimum size.

Three measurement notes, each about measuring the RIGHT thing rather than
loosening a tolerance: a `QHeaderView`'s `minimumSizeHint` is an
orientation-blind square (68×68 whatever its sections hold), so only the
header's own axis is compared, against Qt's size hint and the font; a `QLabel`
is charged no control padding, because it paints straight into its
contentsRect; and a container of WRAPPING children has no single minimum
height (`minimumSizeHint` quotes it at the narrowest width), so only its width
is checked there — the vertical truth is measured element by element by the
wrapped-text branch.

**"Fullest state" includes what arrives LATE** (owner screenshots 2026-08-06).
`MainWindow`'s factory used to build the window and stop there — but two things
reach it only after it is on screen: the update button (hidden until GitHub
answers) and the notify switch's caption (one line normally, three when it has
to report a failure, and a failure names a path). The factory now `show()`s the
window first and lets both arrive afterwards, exactly as the owner's evening
does. Self-tested: with the fix disabled the audit reports
`CLIPPED MainWindow: has 820x837, needs at least 618x880` — 43 px, the update
button's own row, which was being drawn over the QR's link.

**MainWindow (reopened from the tray)** is the same window reached the way the
owner actually reaches it: closing this app hides it to the tray, so the update
offer lands on a window nobody is looking at, and Qt gives a hidden window no
real metrics. The case shows the window, hides it, lets the late content
arrive, and hands it back for the audit to show again — proving the minimum is
re-measured on the way BACK. Self-tested the same way (signature on
`isVisible()` + a settle-once `showEvent` restored): `CLIPPED … has 869x837,
needs at least 618x880`.

**It is a measurement case and NOT a second picture** (`NO_SHOT`, 2026-08-07 —
independent graders reported it three times: `MainWindow.png` and
`MainWindow__reopened_from_the_tray.png` were byte-identical, md5
`12c59bd6ae08`, as were their light pair `c72b15932b44` — four proof lines
standing over two pictures). Measured before deciding: both windows built,
each resized to its own declared minimum and rendered at 2x, in both palettes.
All four report **minimum 463x685, sizeHint 463x657**, and the two pixel
buffers hash the same in each palette (`7ce0566f4066` dark, `3bcd7da153a3`
light). They cannot differ, and not by accident — the tray factory reaches the
identical widget state by a longer road. What the case proves is that the
hidden round trip leaves no WRONG FLOOR behind, a claim about numbers, and a
photograph says nothing about it. So the case stays in `WINDOWS` and its name
goes into `NO_SHOT`: `audit_window` skips the screenshot only, never the
checks. A picture that is a copy of another picture is not evidence — it is a
second proof line that costs a grader a second look and returns the first
look's answer.

**E. OVERLAP, and REAL FONTS** (owner 2026-08-06, after this guard reported
PASS over the window he had photographed twice). Two holes, both closed:

- Every check here asked whether an element got its own SIZE; none asked where
  it was PUT. Qt does not clip a layout that is short of space — it OVERLAPS
  it, so every widget reports its full size while the pairing link is painted
  across the QR. `check_overlap` compares the cells of each layout (not
  arbitrary siblings: a scrollbar over a viewport is legitimate) and fails on
  any intersection. It immediately caught one nobody had reported — the
  Traffic window's chart drawn 4 px over the caption beneath it.
- The platform WAS the measurement error: `offscreen` has none of the
  machine's fonts and substitutes metrics, reporting the main window at
  869x880 where the owner's real Segoe UI at 125% scaling needs 503x937 — the
  defect lived in the difference. The native platform is used whenever there
  is a desktop, with `WA_DontShowOnScreen` so the full layout machinery runs
  with real fonts and DPI while nothing appears on screen; offscreen remains
  the fallback. That switch alone surfaced two more genuine defects: the
  Controls editor 59 px short, and a Traffic combo cut to "Last 10 minut" by
  the theme's own 92 px combo floor.
- The container-height blind spot is gone with them. This file used to zero
  out the height of any container with wrapping children and check only its
  width; that is how the QR card could be handed 332 px against a minimum of
  348 in silence. It is now asked `heightForWidth` at the width it actually
  has.
- Each window's screenshot at its DECLARED minimum is written to
  `.claude/shots/` by the audit itself, so the picture the layout gate grades
  can never be of a different build than the one just measured.

- **BOTH PALETTES** (build round R3, 2026-08-07). The whole registry is built
  and audited under dark and then under light, and each window is shot in
  each — the light shots carry a `__light` suffix so the dark ones keep the
  filenames the existing proof lines already point at. A light theme is not a
  repaint of a dark one: a translucent white border vanishes on white, a
  16 %-alpha wash reads as nothing on a card, and an icon whose ink was baked
  in at build time turns invisible. `use_palette()` sets `SETTINGS.ui_theme`
  as well as calling `apply_theme`, because `MainWindow` applies that setting
  in its own constructor and would otherwise flip the app back.

Run: `.venv\Scripts\python tests/test_layout_audit_qt.py` — also a full-run
guard in `run_guards.py`.

### `test_presence.py` — Presence Gate
Proves that the phone leaving work mode frees the owner's desk: layout
members are always-on-top while the phone shows them, and before 2026-08-05
only a CLEAN socket close ever ended that — which a locked phone rarely
manages (Wi-Fi sleeps, the connection just goes quiet), so the windows kept
hovering over everything at the desk. Checks the heartbeat holding a
session, the watchdog ending a silent one (members minimized, socket closed
4408), an announced excursion (image picker, camera, voice) NOT counting as
a leave, an announced leave acting at once, `_leave_session` being
idempotent, and the resume pointer (`LayoutRegistry.last_focus`) surviving
rename/remove and forgetting on a deliberate Desktop choice. No browser and
no real windows — the window calls are stubbed.

Run: `.venv\Scripts\python tests/test_presence.py` — also a fail-closed step
in `build.py` (0c/6).

### `test_notice_channel.py` — Notice Channel Gate
Proves that a notice reaches the phone while the owner is **not looking at
it**. His report on 2026-08-07: *"notifikacije mi stižu tek kada podignem
aplikaciju iako je sve vreme otvorena u pozadini"*. The cause was structural —
every notice rode the streaming socket, and that socket is closed on purpose
the moment the page hides (project CLAUDE.md constraint 8), so at the exact
moment a notice mattered there was no channel and the server queued it until
he opened the app himself.

Eight checks against a REAL server (`web.create_app` with a fake stream,
registry and injector) and a real HTTP client standing in for the phone's
foreground service: `/notices` refusing a bad token; a notice arriving whole
down the waiting channel with the page closed; **a waiting phone never
counting as a present phone** (the one-device slot empty, `stats.clients` 0,
the capture not started, the layout registry untouched, neither
`presence.watchdog` nor `focus_guard.watch` armed — a notice connection that
looked present would nail his own windows always-on-top over his desk); the
idle channel carrying one beat byte and nothing else; an open page taking a
notice ALONE, never twice; a page dying mid-notice falling through to the
channel instead of into the queue; and the queue being the last resort, drained
oldest-first the moment the phone starts waiting again.

Every check was shown red on a planted defect before being trusted — including
one plant that revealed a real weakness in the gate itself (the isolation check
ran after another check's `reset()` and would have scrubbed a live defect out
from under itself; it runs first now).

The Kotlin half — `NoticeService`, `NoticeLink`, `Bridge` — cannot be exercised
here: there is no Android runtime on the build machine. What this gate pins is
the PC's half of the contract and the exact bytes the shell must read.

Run: `.venv\Scripts\python tests/test_notice_channel.py`

### `test_link_recovery.py` — Link Recovery Gate
Proves that a phone which loses its **route** comes back by itself. His report
on 2026-08-07: *"kada nismo na wi-fi mreži … dešava nam se prekid veze, i ovo
'Try again' dugme retko kad pomogne, već moramo više puta, nekad čak i da
zatvorimo celu aplikaciju."*

A REPEAT. Three mechanisms were already written as the answer to this exact
complaint — two stored addresses probed at start, a self-re-probing error card,
a `/ping` contract only an exact 204 satisfies — and all three hold. All three
only run in states he is not in. The state he **is** in is a page that loaded
perfectly and is now retrying an address that no longer reaches the PC, and
there: the shell re-probed only behind its error card, the page cannot move
itself (its socket goes to `location.host` and nowhere else), a socket stuck
CONNECTING or opened onto silence is skipped by `ensureConnected` so the page
retries nothing at all, and on the PC a socket the watchdog had already
declared dead still held the one-device slot — so the returning phone arrived
as a *second device against its own corpse* and its first act was
`await prev.close(4409)` on a socket with nowhere to send.

Eleven checks in three parts. **The PC** (fakes, no Windows): a watchdogged
session vacating the one-device slot; `presence.hand_over` bounded against a
socket whose `close()` never returns; and the real `ws_endpoint` still
delivering `actions`, `layout_state` and `config` to a new client while a
corpse sits in the slot. **The page** — the REAL `client/state.js` +
`client/connection.js` run in node inside a sandbox with a virtual clock, a
scripted WebSocket and a fake `window.Android` (no browser, no server, no
waiting): a socket that never opens abandoned and retried, a socket that opens
and is never served abandoned and retried, a run of unserved connections
(silent **or** flapping) asking the shell exactly once, a served connection
never asking, and 4401/4409 never being read as a lost route. **The shell**
(source contract — no Android runtime here): the network-change re-probe not
gated on the error card, `Android.linkLost()` existing and reaching the
resolver, and session health judged by ADDRESS rather than by a whole URL
string (with the callback now firing on a live page, a string mismatch would
reload a working session on every blip).

Every check was shown red on a planted defect before being trusted — ten
plants, ten reds, tree restored green.

Needs `node` on PATH for the page half; a missing node fails the gate rather
than skipping it.

Run: `.venv\Scripts\python tests/test_link_recovery.py` — also a fail-closed
step in `build.py` (0j/6).

### `test_focus_guard.py` — Focus Gate
Proves that what the phone types lands where the owner is LOOKING. `SendInput`
has no target, so before 2026-08-06 every dictated character went to whatever
window Windows called the foreground at that instant — and when something on
the PC took focus mid-sentence (an app starting, a dialog, another agent's
editor window), the rest of the sentence went there, silently, with the stream
still showing the PC. The owner reported it three times in one evening, and
the fourth report WAS the bug: a sentence dictated for another project arrived
in this project's session.

Twenty-three checks, no browser and (for the policy half) no real windows —
every user32 call is answered by a fake: the layout fence refusing a foreign
foreground and handing focus back to the member being typed into; the fence
holding on a fresh connection with no pin yet; a move the owner made INSIDE
the layout being followed, not fought; a dialog of a member (Save As…)
counting as that member; the desktop pin arming on the burst's first key and
restoring `topmost=False`; a click / `next_input` / layout switch re-arming it
while a thief arms nothing; the thief being NAMED in the log;
`LayoutRegistry.focus()` raising the keyboard member LAST (one excursion used
to move dictation into the other pane); `prune` moving the target off a window
closed at the desk; and the whole path through the real `web._receive_input`
dispatcher.

**Build round R1 (owner-approved 2026-08-07) closed the hole INSIDE one
message.** `SendInput` types one code unit at a time, and it was MEASURED on
the owner's PC at ~1.84 ms per character — a 600-character dictated sentence
is over a SECOND during which a thief used to get the remainder. The gate
proves that a steal at EIGHT different offsets costs zero characters and the
rest still lands in the right window; that a steal inside an emoji costs at
most that character's tail, never a whole character; that typing which cannot
be re-aimed STOPS and names both the thief and what was never sent; that the
**phone is told** what never reached the PC; that half a character never goes
out and never raises into the dispatcher; that a caller passing no guard
behaves exactly as before; and that the real dispatcher hands the injector the
checkpoint.

Run: `.venv\Scripts\python tests/test_focus_guard.py` — also a fail-closed
step in `build.py` (0e/6) and a full-run check in `run_guards.py`.

### `test_focus_hook.py` — Focus Hook Gate
The other half of the focus work, split out on 2026-08-07 when the two
subjects together crossed THE STRUCTURE LAW's 1,000 lines: `test_focus_guard`
proves the POLICY, this proves the MACHINERY that carries it.

Nine checks: the hook announcement defending the layout measurably before a
poll tick could have; **the callback only SIGNALLING** — a WinEventProc runs
inside Windows' own event dispatch, and the first version called the guard
from there, measured stalling a second caller for 2.99 s (the owner felt it as
a juddering mouse); the log line when a listener overruns that contract;
a hook that Windows still claims to hold but that has gone quiet being reported
once; the 0.25 s poll still defending when Windows refuses the hook; the
thread's start / stop / unhook / restart; a timed-out `stop()` keeping the
thread's identity instead of orphaning it with the hook still installed and
letting a second one be built over it; every documented exit path really
calling `ServerController.release_windows` — **parsed with `ast` inside the
function that handles that exit**, because a file-wide grep stays green when
tray Quit stops calling it while another line still names it; and two threads
never deciding the target at once.

**It installs no real hook and touches no real window.** The owner works on
this machine: a hook or a thread a FAILING test forgot to release is his mouse
juddering, not a red line in a terminal. The thread, the joins and the identity
book are real; Windows is faked.

Run: `.venv\Scripts\python tests/test_focus_hook.py` — also a fail-closed step
in `build.py` (0e/6) and a full-run check in `run_guards.py`.

### `_focus_fakes.py` — the fake Windows both focus gates share
`FakeWin32` (the user32 calls the guard makes), `Raises` (records what would
have been raised, raises nothing), `FakeHookWin32` (the four calls
`focus_hook` makes into Windows, incl. a `deaf` mode that swallows `WM_QUIT`
so a timed-out stop can be tested on purpose), `TypeSpy` (the REAL injector
with only `SendInput` replaced, recording every UTF-16 unit and the window
that would have received it), the fake socket/injector, and the shared runner.

### `test_layout_protocol.py` — Layout Gate
Proves that EVERY layout message the phone can send answers it. Born from the
2026-08-06 live failure — *"layout, kreiraj iz liste, ništa se ne dešava"*: the
loading cube spun and no list ever came, because one line in
`layout_api.layout_list` read `mon_rect = mon_rect(stream)`. That name is the
module's own function, so the assignment made it a LOCAL for the whole function
and the call on the right-hand side raised `UnboundLocalError` before anything
was sent. The owner's server log carried the traceback three times; the build
carried nothing, because **no test walked this path** — four guards, an input
gate, a presence gate, a notify gate and a focus gate, and the phone's entire
layout protocol had none.

Six checks driving the REAL `web._receive_input` dispatcher over the REAL
`layout_api` and `LayoutRegistry`, with only Windows faked (user32, the window
list, UIA, the process table): create from a LIST (windows plus the tabs of
tab-capable apps), create by TAPPING a window, create → focus → desktop,
rename / app-sets / aspect / remove each answering with a fresh `layout_state`,
and a 2×1 grid built from the list. A handler that raises, or that answers the
phone with nothing, fails here. Self-tested by replanting the defect: the
first check reports the exact `UnboundLocalError` and fails.

**And three checks on the Move handle's SERVER half** (owner decree
2026-08-09, the FOURTH round of the same feature). Round two taught this file
to follow the handle to the WINDOWS with `install_fakes(track_placement=True)`
— a model of the desk where every commanded rect becomes the window's real
frame — and that was still the wrong screen: the server crops the region and
streams the SAME picture wherever the windows sit, so three green rounds
moved nothing the owner could see. The phone half (where the letterboxed
picture actually lands) is `tests/test_view_anchor.py`; what this file owns
now is the server's side of that contract, still asserted on the RECT:
- *placement is CENTRED whatever the pos* — solo **and** grid, portrait
  **and** landscape: fresh applies at 0 / 500 / 1000 land on identical,
  centred rects, and each answer's `layout_state` carries the pos the phone
  anchors by.
- *a pos change moves the phone's picture, never the windows* — the SAME
  ratio re-applied at a new pos places NOTHING (the untangled trigger:
  `place_pending` + `arranged_ratio` + `_standing`, with pos deliberately
  absent) while the reply still carries the new pos to the phone.
- *a wandered window is put back — centred* — the desk is still re-read on
  every Apply (round three's lesson, kept): a member that drifted off its
  rect is re-placed, to the centre.

Proven by planting the old behaviour back: sliding the region by `lay.pos` in
`layout_registry.focus` turns the first two red — *"placement FOLLOWED pos"*
with the union rects at y=0/290/581, and *"a pos-only change re-placed
windows"*.

**And four checks on the CREATION LIST and the shape it can honestly build**
(owner reports 2026-08-09, tasks 166 + 167). The first of them replaced a
check that **REQUIRED THE DEFECT**, which is the finding worth more than the
fix: the fixture faked ONE VS Code window holding exactly ONE tab and asserted
`len(entries) == 3` — window, its lone tab, and a plain window — so enforcing
his rule (*"a tab can be extracted into its own window only when the window
has more than one tab"*) turned it red. A gate written around a fixture that
cannot tell two behaviours apart proves whichever one it was written against,
so the fixture is the fix: `fake_windows()` now offers a window with THREE
tabs, a window with ONE, and a plain window, and both answers are asserted in
the same run.
- *a window's lone tab is NOT offered beside it* — the three-tab window offers
  its three, the one-tab window offers none, and the emission order stays
  window-then-its-tabs, which is what the phone's indented list is drawn from
  (task 168).
- *a minimized window SAYS why it shows no tabs* — measured on his PC: a
  minimized window reports height 0 to UIA and enumerates zero tabs whatever
  it holds, so the same window silently appeared with and without its tabs
  depending on its state. It now carries `tabs_hidden`, and restoring it
  brings the tabs back (a flag nobody clears would be a second way to be
  wrong).
- *a grid is built from the windows that ARRIVED, and a downgrade is said* — a
  four asked for with three windows becomes a THREE and the phone is told; a
  grid that FITS is left alone and toasts nothing.
- *the framed region is FULLY covered by its members* — the geometry he
  judges, not the number stored. Three windows in a 2×2 left the union rect,
  the member list and `placed` all looking correct while a quarter of the
  picture on his phone was bare desktop.

Each proven by planting its own defect: restoring the old `list_tabs` loop
reports *"the ONE-tab window's lone tab was offered"*; removing the minimized
branch reports *"the minimized window did not say WHY"*; and passing the
phone's grid straight through reports *"4 from 3 windows was downgraded in
SILENCE"* and *"covers 75% of the region it frames"*.

Run: `.venv\Scripts\python tests/test_layout_protocol.py` — also a
fail-closed step in `build.py` (0f/6).

### `test_layout_member.py` — Layout Member Gate

ONE WINDOW OUT OF A GRID (owner request 2026-08-09, task 165): each row of the
layout list has a rename button and an aspect button, *"but there must be a
button by which I can throw ONE member out of the grid — to enter the grid
state and remove any member, i.e. change it to a single or to a 2-grid."*
Until that round a grid could only be BUILT (`layout_merge`) or removed WHOLE,
so losing one window of four meant deleting the layout and making it again.

Ten checks driving `layout_member_remove` through the REAL dispatcher. Nothing
is copied: the Windows model, the fake socket and the runner come from
`test_layout_protocol.py`, the multi-window fixture (`build_layouts`,
`names_of`, WIN_C/WIN_D) from `test_layout_drag.py`, in a chain that only ever
points one way — member → drag → protocol. Its own file because adding it to
the layout gate put that file at 1,154 lines (THE STRUCTURE LAW), and because
a layout SHRINKING is a responsibility of its own — the same seam
`test_layout_drag.py` was cut on the same day:

- *a grid shrinks one window at a time* — 4→3, 3→2, 2→single, with the SHAPE
  following the size (three windows still standing in a 2×2 is not a three).
- *the leftovers are RE-PLACED into the new shape* — asserted on the RECTS,
  against cells read out of `grids.py` rather than restated, so the check
  cannot agree with a wrong answer. A shape change that moves no window is the
  Move handle's bug again: the phone's panel changes and the PC does not.
- *the window that leaves is NEVER closed* — the safety property, written
  against the real `close_windows` desk model. Only the ✕ chooser closes
  windows, and only when he asked (2026-08-08, task 116).
- *the window that leaves drops out of the topmost band* — CLAUDE.md
  constraint 10. It is exactly the window no member list can still name a
  moment later, so the drop has to happen on the way OUT.
- *removing the LAST member removes the layout* — through the existing
  `remove()` path, with the connection's focus bookkeeping.
- *a member that is not there is refused IN WORDS* — the panel was open while
  the desk changed; a silent no-op reads as the button being broken.
- *a four lands on the three the phone named* — the one place in his catalogue
  with a real choice; an unnamed or wrongly-sized one takes the sheet's first
  drawing rather than a shape with an empty cell.
- *the keyboard follows when its own window leaves*, and
  ***`drop_member` leaves the orders it promises*** — the second exists
  because planting the defects proved the first could not see it: `focus`
  begins with `prune` (which re-homes a stray `last_member`) and re-places
  whenever `_standing` fails (which after a shape change it always does), so
  both lines could be deleted with every end-to-end check still green. It
  asserts at the METHOD's own boundary, and it is deliberately the smallest
  such check beside four that measure rects.
- *`layout_state` NAMES every member* — `member_titles`, in CELL order, since
  the phone cannot ask for a window it was never told about.
- ***the leaving window takes its SOURCE record with it*** (2026-08-09, tasks
  171 + 173). A member EXTRACTED from another window carries a record of where
  it came from, and that record is what makes the other layout wear the ⭐ and
  what the ✕ chooser's warning is built out of. When the extracted window
  leaves, the record must leave with it — or the trunk goes on being marked as
  the parent of a branch that no longer holds its content, and the phone warns
  him about destroying something a close cannot touch. Asserted end-to-end AND
  at the method's own boundary, because planting proved the end-to-end case
  cannot see it: `focus` begins with `prune`, and `prune` drops every record
  whose member has left — the same masking two checks above.

Proven by planting each defect in turn (ten of them: the template not
re-derived, no re-place ordered, the leaving window closed, the leaving window
left topmost, the last member not removing the layout, a bad ordinal accepted
in silence, `_template_for` ignoring the named shape, the keyboard pointer
left behind, `member_titles` dropped, the source record kept after the member
left → *"drop_member left {48: 16} behind — only the prune that happens to
follow it cleans up"*). Each turns its own check red and the suite is green
again on restore.

Run: `.venv\Scripts\python tests/test_layout_member.py` — also a fail-closed
step in `build.py` (0t/6).

### `test_grid_icons.py` — Grid Icon Gate

THE LIST SAYS WHICH SHAPE EACH LAYOUT IS (owner request 2026-08-09, task 164).
A row carried a name and nothing about its shape, so a solo window, a
two-split and a four-grid read identically until he opened one. The catalogue
is not derived anywhere: it is his own sheet, `UV/grid_variations.png`
(2026-08-07) — LANDSCAPE and PORTRAIT columns, rows of 2 / 3 / 4, with FOUR
arrangements in the 3 row and one each in the 2 and 4 rows. **Six grid shapes
plus solo is 7; with the orientations, 14.**

Fifteen checks. The geometry is pure (`client/grid-icons.js`, the
view-anchor.js / cursor-shapes.js pattern) and is run WHOLE in node:

- *every variant draws its OWN silhouette* — the whole feature. Two shapes
  drawing one picture tells him nothing and fails silently.
- *portrait and landscape never draw one picture* — only `"2"` changes its
  PARTITION with orientation; the other six lean their BOX, which is why the
  box is part of the signature. A fixed square was the real bug once.
- *the cells ARE `server/grids.py`'s partition, in member order* — compared
  number for number against the arithmetic that actually places his windows.
  `client/grids.js` had carried "if one changes, the other must" since it was
  split off, and nothing had ever checked it.
- *only a THREE may change its arrangement* — his sheet's asymmetry, held in
  one pure function so no panel can offer a choice that does not exist.
- *an unknown key falls back to a safe generic, never throws* — a name from a
  NEWER server, a missing field, a nonsense count: one exception while
  building the list would kill the whole panel.
- *fewer live members than cells draws only what is there* — a window closed
  at the desk is pruned and the template left alone, so a four holding three
  really does show three quadrants and a gap.
- plus the catalogue's shape, per-cell lighting, box/overlap sanity, the load
  order, `grids.js` keeping no second copy, the module staying pure, the
  server still sending `grid`/`members`/`orient`, and the banned second name
  for "landscape" staying out.

Proven twice by planting a defect: drawing `"3-bottom"` as `"3-top"` turns
*every variant draws its OWN silhouette* red (*"3-bottom x3 landscape draws
exactly what 3-top x3 landscape draws"*) and takes the server-partition check
with it; making an unknown grid throw turns the fallback check red.

**One check is RED until the layout list is wired** — *the layout LIST draws
the shape of every row*, which requires `client/layouts.js` to call
`gridIconSvg(lay.members, lay.grid, lay.orient)`. That is deliberate: a pure
function nobody calls is a feature that does not exist (the actions.json
lesson, 2026-08-07), so the tooth is the thing that makes the wiring
mandatory, and its failure message states the exact lines to add.

Run: `.venv\Scripts\python tests/test_grid_icons.py` (needs node) — also a
fail-closed step in `build.py` (0s/6).

### `test_layout_drag.py` — Layout Drag Gate

A ROW DRAGGED ONTO ANOTHER IS A GRID — the server half of the list's own two
gestures. **The finding is the absence, not the feature.** `layout_merge` and
`layout_reorder` shipped whole on 2026-08-07 — client drag block, protocol,
`LayoutRegistry.merge`/`.reorder` — and until 2026-08-09 not one test file in
this project mentioned either name; the layout gate above, the fail-closed one
for the whole protocol, had no merge, no reorder, no drag and no hold in it. So
when the owner reported the gesture dead on his phone (task 162), nothing on
this side could say whether the server half had ever worked at all. Its own
file rather than another section of that gate because that file sits at THE
STRUCTURE LAW's ceiling, and because the boundary is real: this one owns what a
finger does to the ORDER and MEMBERSHIP of layouts that already exist. The
fixtures are the layout gate's own (`install_fakes`, `drive`, the fake desk),
imported rather than copied. Eight checks, each driven through the REAL
dispatcher: every grid size a drop can make (1+1 → 2, 1+2 → 3, 1+3 → 4, with
the source layout disappearing), the three taking the shape the phone named
(and a sane one when it named none or named the wrong size), a FULL layout
refusing in words, a row dropped on ITSELF, the index shift after a merge in
both directions, and reorder's pop/insert correction over six real gaps — with
`PLACED` empty, because "nothing moves on the PC" means rects.

Two more since 2026-08-09, both about a claim the LIST makes rather than a
window it moves:

- **A reorder keeps the focus on the SAME layout, not on the same number.**
  `conn["active"]` is a plain position, so re-ordering while a layout was
  focused left the server calling a DIFFERENT layout active — the phone framed
  one layout while the bar's ✕ would have offered to close another one's
  windows. The bug shipped with `layout_reorder` itself on 2026-08-07 and was
  found while wiring the phone's member chooser. Asserted by IDENTITY (the
  same `Layout` object, and the same NAME at the index the phone is told in
  that very frame), never by number — *"active is still 1"* was true all
  through the bug. Five real drops: the focused row carried over its
  neighbours and under them, a stranger's row jumped across it in both
  directions, and a drop that changes nothing.
- **The ⭐ marks the trunk and nothing else** (owner decision 2026-08-09, task
  169). Built, never asserted about: a layout is made from a WINDOW and a
  second one from a TAB torn out of it, through the real `resolve_slot`, so
  `Layout.source` is written by the product and not by the check. All three
  states in one build — the parent is starred, the branch that came out of it
  is not, an unrelated layout is not — plus the self-contained case: after the
  two are merged into one layout, nobody is starred, because the mark is about
  OTHER layouts losing their content.
- **A tab extracted into a LATER cell is recorded too** (task 173,
  2026-08-09) — the ⭐'s own honest limit, closed. `create` stored ONE source,
  taken from the first slot, so a tab extracted into cell 2, 3 or 4 of a grid
  left no record and both readers under-reported on exactly the grids the mark
  exists for. BOTH shapes are built in one run, because a fixture that can only
  build the shape which already worked is a fixture that proves the old
  behaviour.
- **The phone is told WHICH layouts a close would destroy** (task 171,
  2026-08-09) — `layout_state.dependents`, the NAMES and not a count: "1 other
  layout" is a number, and what he needs before an irreversible tap is which.
  Two branches out of one trunk are two names; a branch that is REMOVED stops
  being named, or the warning would list a layout that no longer exists.
  Asserted by RELATION — which layout NAME is destroyed by which — never by a
  handle (the phone is never told one) or an index (a reorder moves them).

Each check proven by planting its own defect at RUNTIME (the registry method
replaced in memory — never on disk, because another agent was editing
`layout_registry.py` in the same tree): never popping the source →
*"1+1: 2 layouts left"*; ignoring the phone's grid → *"asked for '3-left' and
got '3-top'"*; the four-window ceiling removed → *"the merge went through
anyway"*; self-merge allowed; the handler's index correction lost →
*"focused 0 and told the phone 0, expected 1"*; the pop/insert correction
removed → *"reorder(0, 2) -> ['B', 'C', 'A'], expected ['B', 'A', 'C']"*.
The two 2026-08-09 checks likewise: the pre-fix `layout_reorder` branch put
back in `web.py` → *"focus 0, reorder(0, 3): the server now calls 'B' active —
the phone is showing 'A'"* (four of the five cases red); `"parent": True` for
every layout → *"the stars are {'Trunk': True, 'Plain': True, 'Branch': True}"*.
And the two of task 171/173: `layout_api` recording only `resolved[:1]`'s
source — the pre-task-173 line, exactly — turns both red at once, *"a tab in
cell 1: the stars are {'Trunk': False, …}"* and *"the dependents are
{'Trunk': [], …}, expected {'Trunk': ['Branch'], …}"*, while the cell-0 shape
that always worked stays green: the fixture can tell the two behaviours apart.

Run: `.venv\Scripts\python tests/test_layout_drag.py` — also a fail-closed
step in `build.py` (0f/6) and a full-run guard.

### `test_layout_shape.py` — Layout Shape Gate

A LAYOUT CAN BE TURNED AND RE-ARRANGED AFTER IT EXISTS (owner 2026-08-09, task
175). Every act on an existing layout moved under one common ⚙, and one of them
could not be done AT ALL before: a layout built portrait had to be DELETED and
made again to become landscape.

**The finding is the absence.** The message it rides — `layout_grid {index,
grid, orient}` — has existed since 2026-08-07 for a THREE's arrangement, and no
test in this project ever mentioned `layout_grid` or `set_grid`. So "the server
already has it" was a claim about a NAME, not about a behaviour, and this round
was about to build a phone panel on top of it. Same absence
`test_layout_drag.py` was written for on the same day, and the same answer —
except this one exists BEFORE the panel's first screenshot rather than after
his first report.

What it asserts is the RECTS. A shape change the phone shows and the PC ignores
is the Move handle's bug arriving in a new place (owner 2026-08-07, *"uvek
ostavi centrirano"* — lang-ok: owner quote), and a check on a stored value the
user cannot see proves nothing about a feature he judges by geometry.

- a THREE re-arranged (which edge its single window takes), a grid TURNED, and
  a SOLO layout turned — the phone sends an empty grid for that one, so the
  path is driven as it really arrives;
- the survivors land on the cells of the NEW shape, read out of `grids.py`
  rather than restated, so the check cannot agree with a wrong answer;
- a shape of the WRONG SIZE is refused, not obeyed into a cell nobody is in —
  and the refusal still TURNS the layout, because the orientation is a separate
  question from the arrangement;
- and the re-place ORDER at the method's own boundary.

That last one exists because planting proved the others could not see it:
`focus` re-places whenever `_standing` says the members are off their targets,
which after a shape change they always are, so `place_pending` could be deleted
with every end-to-end case still green. Two plants, both red on restore-check:
`set_grid` ordering no re-place → *"set_grid ordered no re-place — a shape
change every member happens to satisfy would leave the windows as they were"*;
`set_grid` ignoring the orientation → *"2 -> '2'/portrait: became
'2'/'landscape'"* on three cases at once.

Its own file because `test_layout_protocol.py` stands at THE STRUCTURE LAW's
ceiling (these checks put it at 1,018 lines) and the boundary is real anyway —
the same seam `test_layout_drag.py` and `test_layout_member.py` were cut on: a
layout CHANGING SHAPE without changing its membership. Nothing is copied; the
Windows model and the real-dispatcher runner are imported.

Run: `.venv\Scripts\python tests/test_layout_shape.py` — also a fail-closed
step in `build.py` (0u/6).

### `test_hold_gesture.py` — Hold Gesture Gate

A HOLD IS A CONTACT THAT STAYED PUT (owner report 2026-08-09, task 162). He
held a layout row without moving it, meaning to pick it up, and the layout
simply OPENED. Three things defeated a gesture that had shipped whole: the
row's `pointermove` cleared the 380 ms timer on ANY movement (a resting finger
on a capacitive digitizer wanders — the reported point is the centroid of a
contact patch that breathes); `keepFocus` fires its tap on `pointerup` with no
duration test and rescues any `pointercancel` under 18 px, while Chrome hands
out that cancel at ~8 dp when it decides the touch is a scroll; and
`.lay-item` declared no `touch-action`, so the browser owned the vertical
gesture. **It stayed broken because the arming logic was not extractable and
therefore never tested** — no test mentioned `holdTimer`, `dragEnd` or
`mergeLayouts`. The rule is a pure module now (`client/hold-gesture.js`) and
this gate runs it WHOLE in node against a modelled resting finger sampled at
~60 Hz for 400 ms, plus a real 20 px pull: a rule about jitter cannot be
proven by one call. Wiring checks pin the rest — the row must ASK the rule,
its tap must refuse a press that lasted (`keepFocus` untouched: it is the
activator the gamepad shares), the pointer must be captured BEFORE `drag` is
armed, the row must refuse the browser's pan AND the drag must still be able
to reach a target below the fold, `MOVE_TAP_SLOP` must be derived from
`HOLD_DRAG_SLOP` (one digitizer, one number), and the module must stay pure.

Thirteen checks, each proven by planting its own defect: zero tolerance back
→ *"a resting finger at 16 ms (+1.0, +0.0 px) was read as 'drag'"*; the slop
made infinite → the drag check red; a per-axis slop → *"a 12.7 px diagonal was
read as 'tap'"*; the verdict call removed → *"the row no longer asks
pressVerdict()"*; the duration guard deleted → *"the row's tap does not refuse
a press that lasted"*; the capture moved after the arm → *"`drag` is armed
BEFORE the pointer is captured"*; `touch-action` removed; the auto-scroll
removed; `MOVE_TAP_SLOP` re-typed as `12`; the `<script>` tag removed; a
`document` reference added. **A hole this exercise found and closed:** two
wiring checks could NOT go red at first, because the comment explaining the
fix names `setPointerCapture` and `touch-action: none` and a grep over the raw
text answered from the prose instead of the code — `_code()` strips comments
before any of them indexes anything.

Run: `.venv\Scripts\python tests/test_hold_gesture.py` (needs node) — also a
fail-closed step in `build.py` (0s/6) and a full-run guard.

### `test_view_anchor.py` — View Anchor Gate

THE POSITION LIVES ON THE PHONE (owner decree 2026-08-09, the Move handle's
FOURTH round). Three rounds shipped green through gates that measured window
rects on the PC monitor — a screen the owner never sees — while the geometry
he grades the feature by, where the letterboxed picture sits on his tablet,
was computed by no check. The fit-and-anchor math therefore lives in a PURE
module (`client/view-anchor.js`, the caret.js/voice.js pattern) and this gate
runs it WHOLE in node: pos 0 flush to the near edge of the slack axis
(his gesture — the app at the TOP, empty space below), 1 flush far, 0.5
centred, both orientations, matching aspects immune to pos, a missing pos
read as centred (old servers), out-of-range clamped, and a region off the
origin still landing on its anchor. Wiring checks pin both ends — render.js's
`computeViewHome` must run `fitAnchorView` with `layoutAnchorPos()`, the page
must load the module before render.js, the module must stay pure, and the
server must keep centring windows while `layout_state` still echoes `pos` —
because a pure function nobody calls is a feature that does not exist
(the actions.json lesson). Proven by planting the old always-centred rule in
`fitAnchorView`: pos 0 then draws at y=866.25 — the owner's centred picture,
to the pixel — and the gate goes red.

Run: `.venv\Scripts\python tests/test_view_anchor.py` (needs node) — also a
fail-closed step in `build.py` (0o/6).

### `test_cursor_shape.py` — Cursor Shape Gate

THE CURSOR SHOWS WHAT THE PIXEL UNDER IT DOES (owner request 2026-08-09,
task 142). The phone draws the PC pointer itself — capture never contains it
— and drew ONE fixed arrow, so from the tablet a draggable window edge, a
text box, a link and plain background were the same picture. Three ends have
to hold together and each can break silently, so this gate covers all three:

- *the PC names the right cursor* — the REAL `server/cursor_shape.py`
  resolver, driven with FAKED HANDLES through its injected loader rather than
  stubbed: every `IDC_*` to its name, an unknown handle to `custom` (never a
  near-miss — a wrong shape promises a grabbable edge that is not there), the
  system table loaded ONCE across 200 lookups (this runs at 30 Hz), and a
  cursor-SCHEME change healing itself after `RELOAD_SECONDS` instead of
  reporting every cursor on the machine as `custom` forever.
- *the name reaches the phone the way the protocol says* — the real
  `web._send_cursor` loop over a fake socket: an OPTIONAL field on the
  EXISTING `cursor` message (never a new type), a shape change ALONE sent
  even though the pointer has not moved (hovering onto an edge is exactly
  that), nothing unchanged ever resent, and an unreadable cursor leaving the
  field off the wire.
- *the page draws a distinct, correctly ANCHORED shape* — `cursorPolys` run
  WHOLE in node (`client/cursor-shapes.js` is pure, the
  caret.js/view-anchor.js pattern): every name its own silhouette, the
  hotspot landing on the commanded point under each shape's own rule (tip for
  the arrow family, bounding-box centre for resize/move/wait/I-beam), the
  point only ever translating the shape, every shape inside a readable size
  band, and an unknown/missing/`custom` name drawing the EXACT arrow this
  page always drew — pinned as a literal, because "unchanged" is a claim
  about yesterday's pixels and only a literal can hold it. Wiring checks pin
  both ends (drawCursor calls `cursorPolys` with `cursorShapeName` and keeps
  the fill/outline/shadow legibility treatment, connection.js carries
  `msg.shape` over, index.html loads the module before render.js, the module
  stays pure) and the two name tables must be the SAME SET — a drawn name the
  PC can never send is dead code that looks alive, a sent name with no shape
  is a silent fallback nobody notices.

Proven twice by planting a defect: `cursorPolys` always returning the arrow
turns *every name draws its own shape* red (`'ibeam' draws exactly what
'arrow' draws`) and takes the hotspot check with it; the resolver answering
`ARROW` instead of `CUSTOM` for an unmatched handle turns *an unknown handle
is 'custom', never a guess* and the scheme-change check red.

Honest limit, stated because the gate cannot state it: the handle→name match
is proven against FAKED handles only. That a real Windows session hands
`GetCursorInfo` the same handle `LoadCursorW` returns for that cursor is the
documented behaviour, not something this suite observes — it needs a live
desk with a real window edge under the pointer.

Run: `.venv\Scripts\python tests/test_cursor_shape.py` (needs node) — also a
fail-closed step in `build.py` (0p/6).

### `test_caret_lift.py` — Caret Lift Gate

THE KEYBOARD LIFTS THE PICTURE ONLY IF NEEDED, ONLY BY THE SHORTFALL (owner
2026-08-07, after asking for the opposite thing twice and being right both
times: a box at the bottom is covered unless the picture rises, a box at the
top leaves the screen if it does). Runs `client/caret.js` WHOLE in node — it
is pure by design, the `voice.js` / `view-anchor.js` pattern.

**Rewritten 2026-08-09, because this file is half of why five rounds shipped
green while the rise was pinned at exactly 0 on his tablet.** The old fixture
handed the rule a view transform with `VIEW = {"scale": float(CANVAS_H)}` —
1800 — under a confident paragraph explaining why that was right. `view.scale`
is a ZOOM FACTOR and is 1 at home; it can never hold 1800 in production. So the
fixture made `caret.y * scale` mean "canvas pixels", the rule agreed with it,
and on the real device the same expression put a caret at y=0.95 at 0.95
PIXELS from the top of the screen. Same lesson as the Move handle two sections
up: **a gate that invents its own value for a production variable proves the
fixture to itself.**

The rule now takes the rect the picture is DRAWN into (`drawnRect()`), which is
what the owner actually looks at, and this gate feeds it rects a real phone
produces:
- *the production case really produces pixels* — the check the old fixture
  could not make. Caret at y=0.95, a 700 px keyboard on an 1800 px canvas, and
  the answer asserted EXACTLY: **660 px** on a full-canvas picture and
  **519 px** on a LETTERBOXED one (`picture = {y: 150, h: 1500}` — layout
  focus, where he does most of his typing, and a shape the old fixture had no
  way to express). They must differ: the old arithmetic dropped the letterbox
  offset entirely, so a check that cannot tell those two apart never looked at
  the picture at all.
- *only if needed / only by the shortfall / never off the top* — a caret at the
  top moves nothing, a 20 px overlap lifts 34 px and not 700, and a keyboard
  leaving a 50 px strip lifts only what the strip can take.
- *an unknown caret never moves the picture* — and a caller still passing the
  retired `unknownMode` argument changes nothing, so the deleted branch cannot
  come back by accident.
- *the plumbing, not just the arithmetic* — `window.__imeHeight` must exist in
  `render.js`, be folded in as `Math.max(kbSelf, imeHeight)`, and sit BETWEEN
  `updateViewport` and `initMse`. That last one is not pedantry: the receiver
  was deleted as collateral by a revert of the streaming block it happened to
  sit next to, and nothing noticed because nothing in the repo calls a
  `window.*` global. `Insets.kt` must still push the inset and must carry
  `forgetImeInset`.

Proven by planting the pre-2026-08-09 `caret.y * view.scale + view.ty` back:
five checks go red, every one of them reporting a rise of **0** — the exact
symptom he reported six times.

Run: `.venv\Scripts\python tests/test_caret_lift.py` (needs node) — also a
fail-closed step in `build.py` (0m/6).

### `test_stream_lifecycle.py` — Stream Lifecycle Gate
Proves that a client which is GONE takes its encoder with it. Born from the
2026-08-07 live failure, found in the owner's own running app while his mouse
juddered: **one leaked H.264 session ran for four hours at native 4K with no
phone connected at all** — 12,924 s of `ffmpeg.exe` CPU, `_sessions` never
empty again (so capture could never stop), and 1,890 `Client stream backlog —
resetting the H.264 session` warnings, one every ~7 s, for a client that had
disconnected at 12:05.

Root cause, dated to the millisecond by his server log: `await
asyncio.to_thread(manager.open_session, …)` **cannot be cancelled.** The socket
died 910 ms after auth; the awaiting coroutine raised `CancelledError` at once;
the worker thread ran on and finished the encoder 219 ms later, registering a
session whose only reference had just been thrown away. `close_session` was
never called for it, and its `push` callback kept overflowing a queue nobody
would ever drain again.

Seven checks driving the REAL `web._stream_h264` loop over the REAL
`H264Session` / `H264Manager`, with only the process and the frame source faked
(a stand-in on ffmpeg's exact pipe contract, emitting a minimal but genuine
`ftyp`+`moov(avcC)` init segment — no dxcam, no ffmpeg, no 4K, because the
owner's CPU was already saturated by the very bug under repair): **cancelled
mid-open** (the live bug — the fake encoder's `head_delay` is that 219 ms
window, widened), a clean close, a 4409 takeover / silent network death
mid-stream, an exception in the send path, server stop mid-spawn, **no reset
ever fires for a client with no live socket**, and — the check that keeps the
gate honest — **a live but SLOW client still is reset**, so the suite can never
pass by having the backlog feature deleted.

Every check ends on one verdict: the active count is zero, capture is stopped,
every encoder is terminated, and (unless the check asked for one) not one reset
was logged.

Self-tested by planting each defect separately, which is how the two defences
were shown to be genuinely independent:

| Planted | What goes red |
|---------|---------------|
| `open_session` ignores `owner.take()`'s answer (the live code) | only *cancelled mid-open* — the other six stay green, and the dead-client check proves the queue guard alone still silences the log |
| `owner.release()` removed from `_stream_h264`'s cancellation path | only *cancelled mid-open* |
| the `if not o.alive` guard removed from `push` | only *a client with no live socket is NEVER reset* |

The dead-client check disables the first defence ON PURPOSE (`DeafOwner`, a
claim that accepts every session and remembers none — exactly the pre-fix
world) so the second defence is tested on its own, and it asserts that the leak
it planted was real (`leaked == 1`) so it can never quietly decay into testing
nothing.

Run: `.venv\Scripts\python tests/test_stream_lifecycle.py` — also a
fail-closed step in `build.py` (0g/6).

### `test_quality_reset.py` — Quality Reset Gate
Proves that **changing the bitrate cannot kill the app**. The owner's #1 report
of 2026-08-10, in his words: *"pada cele aplikacije to jest strima prenosa
podataka ukoliko se u settingsu promeni kvalitet bit rate-a"* (lang-ok: owner
quote) — the whole application, that is the data stream, falls over when the
bitrate quality is changed in settings.

Root cause, two defects in one chain. A bitrate lives inside a running ffmpeg's
flags, so the phone's quality panel can only be applied by closing that
client's encoder and opening a new one. **(1)** With one client — the normal
case, "one device at a time" is a hard rule — closing it emptied
`H264Manager._sessions`, so `_stop_source_if_idle` tore dxcam DOWN and
`open_session` built it again for a change that never touched capture. The new
encoder therefore had no frames, and ffmpeg cannot write an init segment before
it has encoded one; past `h264_head_timeout` the open raised. **(2)**
`_stream_h264` answered a failed RE-open exactly as it answers a failed FIRST
open — `ws.close(1011)` — and that socket carries input, layouts, dictation and
presence as well as pictures.

His own `%LOCALAPPDATA%\RemoteUser\server.log`, 2026-08-10:

```
20:29:33,516 INFO  h264_streamer: H.264 session opened — 1 active, codec avc1.4D4032
20:30:21,267 INFO  h264_streamer: H.264 session closed — 0 active
20:30:21,267 INFO  dxcam.dxcam:   Frame buffer build(start): 3840x2160 c=3 n=8.
20:30:42,895 ERROR web: H.264 session failed to open: ffmpeg produced no init segment in time
20:30:43,160 INFO  uvicorn.error: 192.168.0.30:54526 - "WebSocket /ws" [accepted]
```

Zero `stream backlog` warnings and zero ffmpeg errors in that whole file, so
the 20:30:21 close was neither a slow client nor a dying encoder — and the
`Frame buffer build(start)` on the same millisecond is capture being REBUILT,
which is what a reset does and a pause does not. The same close-and-reopen
rides every connection, because the page restates its saved quality right after
auth: `19:29:30,138 opened avc1.4D4034` → `19:29:30,274 closed` →
`19:29:31,514 opened avc1.4D4032`, a different H.264 LEVEL because a different
bitrate.

Seven checks over the REAL `H264Manager`, `H264Session`, `web._stream_h264`
loop and `web._receive_input` handler, reusing the fakes of
`test_stream_lifecycle.py` plus a `ScriptedFfmpeg` that stalls a NAMED spawn (a
reset is two encoders in a row; one class-wide delay cannot say "the second one
is late"): a bitrate change reaches the encoder as a new `-b:v`; it does NOT
recycle capture (dxcam is started ONCE per connection); a slow re-open does not
close the socket and the stream comes back by itself; a re-open that never
recovers still gives up (so this can never become the 2026-07-29 error loop —
171 open failures in 90 s); a FIRST open failure is still fatal at once with no
retries; an away phone still stops capture, so the hold cannot defeat "nothing
runs while nobody is watching"; and the change is SAID in the server log, end
to end from a real `quality` message — his crash could not be dated in his own
log because this branch was the one cause of a close-and-reopen that wrote
nothing.

Self-tested by planting each defect separately in the shipped source:

| Planted | What goes red |
|---------|---------------|
| `manager.hold_source(hold)` removed from the session `finally` (the pre-fix world) | *does NOT recycle capture* |
| a failed re-open closes the socket (`if True:` — the pre-fix world) | *a slow re-open does not kill the socket*, *a re-open that never recovers still gives up* |
| the retry is unbounded (`if False:`) | *never recovers still gives up*, *a FIRST open failure is still fatal* |
| the `first` term dropped, so a first failure retries | *a FIRST open failure is still fatal at once* |
| `release_source` removed from the pause branch | *an away phone still stops capture* |
| the log line removed | *the change is logged, end to end* |
| `bitrate_for_level(None)` — the override never reaches ffmpeg | *reaches the encoder*, *slow re-open*, *logged end to end* |
| `_stop_source_if_idle` ignores `_holds` | *does NOT recycle capture* |

Run: `.venv\Scripts\python tests/test_quality_reset.py` — also a fail-closed
step in `build.py`.

### `test_server_generation.py` — Server Generation Gate
Proves that a SUPERSEDED SERVER RUN OWNS NOTHING. Read out of the owner's own
`server.log` on 2026-08-09, under a screenshot of the GUI saying **STOPPED**
while his phone was streaming: a stop at `19:15:04` gave up after 10 s
(`Server thread did not stop within 10s`), run B started at `19:15:14` and
served fine, and run A finally unwound at `19:15:52` — writing `state =
"stopped"` over the live server, releasing the live layout's topmost windows
and shutting the live encoder down.

Five checks drive the REAL `ServerController` (`start`/`stop`/`_run`/`_serve`)
over fakes for uvicorn, the stream and Win32: a run that outlives its stop
changes nothing; a `stop()` that gives up on a thread gives up its uvicorn with
it (else the abandoned object is the next stop()'s target — the same pill one
press later); a run superseded while still SETTING UP never reaches the socket;
a superseded run's crash is not `FAILED`; and the CURRENT run still tears
itself down completely — the last one is what stops the gate from passing with
the whole teardown deleted. Each defence was proven by planting its own defect.

The middle two came from an adversarial review of the first fix and were both
real — that version guarded only the TEARDOWN, leaving every setup-phase write
(`info`, `loop`, `_uvicorn`, `state = "running"`) last-writer-wins.
`run_blocking()` carries the same guard for symmetry and is deliberately not
checked: it needs the CLI entry point mixed with `start()`/`stop()` on one
controller, which nothing does.

Run: `.venv\Scripts\python tests/test_server_generation.py` — also a
fail-closed step in `build.py` (0x/6).

### `test_actions_migration.py` — Actions Migration Gate
Proves that a NEW VERSION'S FIELDS actually reach the owner's own
`%LOCALAPPDATA%\RemoteUser\actions.json`. His copy is seeded once, at his first
install, and never replaced — `merge_shipped_pools` is the only path a later
version has into it, and until 2026-08-07 it copied a **hardcoded list of field
names** (`name, icon, required, process, title`). Anything invented after that
list was written silently never arrived. The bill: the shipped Claude app set
gained `"agent": "claude"` on 2026-08-06, his copy never did, so the set could
only match by TITLE — and Claude Code names its VS Code tab after the
CONVERSATION, making the condition unsatisfiable forever. **He reported the
Claude set missing across four or five releases.** The same engine had already
kept "Anywhere" in his Settings set after the update that replaced it, and
`wheel_order` (build round R5) was one release from joining them.

Why every guard stayed green through all of it, which is the part worth
remembering: `tests/test_controls_sets.py` builds its "user file" with
`user = copy(shipped)`. **A user file made out of the shipped file already has
every new field**, so the guards proved the repo's actions.json to itself and
could not fail. This gate therefore starts from an OLDER shape — the owner's
real file, held as literal text, not derived from the shipped one — and it does
NOT test for the field named `agent`: it plants a field name nobody has
invented, because a gate written around today's field would ship broken on
tomorrow's.

Seven checks: his real file receives the agent switch · a field nobody has
invented yet arrives · a new top-level key arrives (`wheel_order`, plus an
invented one) · everything he owns survives (`active`, `order_land`,
`order_port`, `enabled`, `wheel_order`, `custom_sets`, `left`/`right`, and his
button renames) · a field we retired stops lying · **the nine-option Model
panel becomes the official five** (tasks 190/191, 2026-08-10 — the same
`buttons`-is-entirely-OURS rule proven on the Claude set's old nine-option
Model list and bare-`/effort` Thinking button: after the merge, Model must
carry exactly the official five `{label, value}` pairs in the official order
and Thinking must gain the same committing `options` panel Model has, five
levels instead of a bare command that only raises Claude's own menu) · a set
he has never had arrives whole.

Self-tested by planting the defect: restoring the old hardcoded field list and
removing the top-level migration turns **four of the six red**, while all four
merge checks in `test_controls_sets.py` stay **green** — the exact shape of the
failure this gate exists to end.

Run: `.venv\Scripts\python tests/test_actions_migration.py` — also in
`run_guards.py` and a fail-closed step in `build.py` (0h/6).

### `test_update_handover.py` — Update Handover Gate
Proves that an update never costs him the session he is installing FROM. His
report on 2026-08-07: *"dešava se da ja ne mogu da instaliram novu verziju ako
nisam kući, zato što čim uđem u instalaciju on će meni ugasiti Remote User i
više neću moći da komandujem odavde."* Every fix this project ships reaches him
only through an install, so an install that kills the remote session is a bug
that eats the project.

Nine checks against `server/update_handover.py` and, for six of them, the
SHIPPED handover script itself — written out of `update_handover.SCRIPT` and
really executed, so the batch this project ships is the batch this gate proves:
nothing unverified is ever run (truncated / too small / not-a-program /
missing) · a damaged download stops EVERYTHING before anything irreversible
(no notice, no record, no script, no spawn) · the phone is told BEFORE the app
can exit · the script waits for the old app's own pid to be gone before the
installer starts (proven by the fake installer looking that pid up and writing
down what it found) · **THE ROLLBACK** — a non-zero installer exit still starts
an app again from the same path · it proves the app came back, and tries once
more when it did not · "nothing to run" is SAID, never shrugged off · and the
next start tells him how it went, good or bad.

**Nothing real is touched.** The installer and the app are fakes; the pid it
waits on and the image name it probes are the gate's own (`RU_GATE_FAKE_APP.exe`),
and `refuse_to_touch_the_real_app()` asserts that before every run — a gate that
could take his live session down while proving his live session is safe would be
its own worst bug. It kills what it starts and prints a check proving nothing of
its own is left running.

It earned its keep on the first run: the `DETACHED_PROCESS` spawn flag left the
script with no console at all, where `tasklist` silently returns nothing — so
"is the old app gone?" answered yes instantly and wrongly. And a bare `find`
in the script resolves to **GNU find** on any PC with Git for Windows, which
reads its argument as a file name and fails the same way. Both are real
shipping defects that no amount of reading would have found; every system tool
is called by full path now.

Self-tested by planting three defects: making the restart conditional on the
installer's exit code turns the rollback check red; moving `tell_phone` after
the spawn turns the ordering check red; disabling the declared-size comparison
turns the verify check red. Each returns exit 1 and is green again on revert.

The NSIS half — `/S`, the silent-mode section choices — is compile-verified
only (`makensis` against a throwaway payload). Running a real silent install on
the dev machine would taskkill the owner's live app, rewrite his autostart task
and his firewall rule; that half is proven on his PC or not at all.

Run: `.venv\Scripts\python tests/test_update_handover.py` — also a fail-closed
step in `build.py` (0i/6).

### Guard tests (THE LAWS — rules/CODE.md → Enforcement, rules/DOCS.md → Enforcement)
Five standard-named guard tests, a fast runner, and a small shared helper —
four installed 2026-08-01 alongside the MD-First 2.0 docs migration, the fifth
(the layout law) on 2026-08-05:

- `_guards_common.py` — `iter_source_files()` / `iter_doc_files()`, pruning
  `.venv`/`build`/`dist`/etc. during the walk (not after) so the guards stay
  fast.
- `test_structure_law.py` — THE STRUCTURE LAW: no source file (`.py`/`.js`/
  `.ts`/`.kt`/`.html`/`.css`) over ~1,000 lines outside the `RATCHET`
  allowlist (currently empty).
- `test_config_sections.py` — THE CONFIG SECTION LAW: every top-level
  definition in a `CONFIG_FILES` entry sits under a `# ══...══` section
  banner; no post-definition table patching; no duplicate dict keys.
  `CONFIG_FILES` = `server/config.py`, `server/gui/theme.py`.
- `test_docs_coverage.py` — every source file has the `__about`/`__flow`
  docs its tier requires; the tier lists here are the project's single
  source of truth (update this file in the same commit as any tier change).
- `test_doc_links.py` — every relative link in every `.md` resolves to a
  real file, and every `.md` is reachable from `README.md`.
- `test_layout_law.py` — THE SPACE & LEGIBILITY LAW, static half: no banned
  API in a GUI source (`server/gui`, `client`) — elision, forced scrollbars,
  disabled wrapping, hard pixel sizes on text-bearing widgets, CSS
  `text-overflow: ellipsis` and `-webkit-line-clamp`. One line may opt out
  with `layout-law: exempt - <reason>` ON that line; `RATCHET` is empty.
- `test_controls_sets.py` — the owner's `actions.json` is never silently
  rewritten: two sets of one process both survive a pool merge, renames are
  carried across it, a pool corrupted by an older build repairs itself, and
  switching sets in the editor never writes into another set's pool (both
  failures of 2026-08-05). Builds the real Controls dialog offscreen, so it
  is a full-run guard.
- `test_app_set_wheel.py` — the app-aware sets appear for the RIGHT window
  and pay for their seat (owner's two rules of 2026-08-06): only the Claude
  conversation wears the Claude set — never an open `CLAUDE.md`, a transcript
  or any other document carrying the word — and an app set charges a wheel
  slot, the charge being the largest group that can appear together (VSCode +
  Claude = 2, Chrome + Explorer + VSCode = 1). Two more rules from the same
  day: **the owner's per-layout ticks beat the guess** — the guard pins his
  real title, `Ispravka UI dizajna meni…`, on which the automatic test can
  only ever find VSCode (Claude Code names its tab after the conversation, and
  nothing else on the window identifies it) — and **the cap of 8 is a law over
  the STORED state**: the SHIPPED `actions.json` may not tick past it, and a
  state that already does is brought back by dropping the app set first.
  It runs `client/sets.js` **whole** in node behind stubs for the prefs bridge
  and the focused layout, rather than lifting a block out of it: the cap is
  enforced across storage, so stubbing the storage away would prove the
  arithmetic and miss the law. Skipped, not failed, when node is absent.
  Self-tested by re-enabling `Cursor` in the shipped file — "the shipped
  actions.json ticks 9 sets by default".
- `run_guards.py` — runs all guards plus the focus gate (or, with `--fast`,
  structure + config-sections + the static layout law — a grep costs nothing, so it
  belongs in the PostToolUse hook's budget; the Qt audit is full-run only,
  it builds a QApplication); exits 2 on any failure. Wired into
  `.claude/settings.json` (PostToolUse `--fast`, Stop full). Run directly:
  `python tests/run_guards.py`.

These are plain `assert`-based functions (pytest-discoverable, but
`run_guards.py` calls them directly — no pytest dependency, since neither
this project's venv nor `requirements.txt` install pytest).

## Connections

### Uses
- [Client (folder)](../client/___client.md) — the page under test, served from disk
- [Web Layer](../server/__about/web.md) — the real FastAPI app + protocol handler

### Used by
- [Setup (folder)](../setup/___setup.md) — `build.py` runs this as the
  fail-closed INPUT GATE before packaging; a broken click path cannot ship

### `test_pad_shape.py` — Pad Shape Gate

THE ARRANGEMENT IS NOT WELDED TO THE ORIENTATION (owner request 2026-08-09,
task 177). Landscape always drew the D-pad cross because a CSS media query
said so, while his sideways phone leaves a finger-wide letterbox band down
each side that holds the sets upright perfectly. Three things have to hold and
this gate covers all three: the DECISION (`padShapeFor`/`padShapeSeed` driven
PURE, by argument — `auto` still draws yesterday's picture in both
orientations, an explicit choice outranks it both ways, the two orientations
are independent, the choice is written through the shell's prefs bridge and
never bare localStorage); task 121's SAVED CHOICE (`padCross` read as the
upright seed — proven by a browser that ARRIVES carrying the old key at page
load, and by the old key NOT answering for the other orientation); and the
MIRROR IMAGE (a column really laying itself out 1×5 sideways and a cross 3×3
upright, on phone and tablet sizes, nothing off screen, no group climbing into
the corner buttons, no horizontal scroll, the two sides never meeting — with
the one honest exception stated in the gate: two crosses cannot fit on a
412 px phone, which is exactly why the column is the upright default). Each
check was proven by planting its own defect: the media query restored, the
preference ignored, the seed dropped, one key answering for both orientations,
the write sent to bare localStorage, and a gap wide enough to push the column
off the band. Writes the two pictures nobody could see before this round into
`.claude/shots/round32-pad-shape/`.

Run: `.venv\Scripts\python tests/test_pad_shape.py` (needs playwright +
chromium; binds its own port 8896).

### `test_on_state.py` — ON State Gate

ON IS A LUMINANCE EVENT (owner report 2026-08-09, task 179 — round TWO of the
same complaint, with his screenshot of the Mic switched on in the coloured
look). Round one answered with an accent ring, an accent wash and a scale, and
its gate asked three questions about COMPUTED STYLE in ONE of the eight looks
— all three true there, while in the coloured looks the per-set rules
outranked `.ctl.active` entirely and the `background:` shorthand erased the
wash. This gate therefore measures what a CAMERA sees: it photographs the real
page and compares the ON button against its own OFF SIBLING as a contrast
ratio, over the face and over the ring, in ALL EIGHT looks, with a 3:1 floor
(WCAG's bar for a graphic object). It also holds `.ctl.held` apart from the
latched state, and asserts each shot really wears the look it is named for.
The planted defect was the SHIPPED rule itself: 1.05–1.58:1 in all eight,
fifteen checks red; after the redesign, 3.24–8.98:1. Two instrument failures
found while writing it are fixed in it — the controls AUTO-HIDE during a
long sweep (the last looks were being scored on a bare page, a perfect 1.00:1
measurement of nothing), and a second connection to the same server earns the
real takeover notice across the picture. Writes all eight ON pictures plus
their held counterparts into `.claude/shots/round32-on-state/`.

Run: `.venv\Scripts\python tests/test_on_state.py` (needs playwright +
chromium + Pillow; binds its own port 8897).

### `test_live_clock.py` — Live Clock Gate

THE PICTURE NEVER GOES BLANK, AND WHEN IT STOPS IT STARTS AGAIN BY ITSELF
(task 151, 2026-08-10, the owner's own promise for this build). Two earlier
fixes for his freeze at 60fps/20Mbps (task 122) each went back out the SAME
night they shipped (0.0.375's revert, commit 581244b): a9db36b's
starve-recovery seek was real but flushed the decoder on every recovery, and
on a link that cannot keep up that turned a freeze into a blank screen; the
rate-limited fix for THAT (3b7b477) landed beside two other streaming changes
in one window and the owner could not attribute any of it (*"da radiš
ispravke jednu po jednu da me obaveštavaš šta se dešava"* — lang-ok: owner
quote). This build returns all of it as ONE mechanism, in the pure module
`client/live-clock.js` (the caret.js/voice.js pattern): a starved player is
SLOWED (`playbackRate` to 0.97) before it is ever flushed, and even the flush
that does become necessary fires no more than once per 4000ms
(`LIVE_UNFREEZE_MIN_GAP_MS`). This gate drives the WHOLE mechanism in node
against a REALISTIC DRIFT RAMP taken from his own server log (+0.34 → -0.01
→ -0.14 → -0.96 → -4.92 → -9.09 → -13.62 → -21.03 → -24.90, over ~6 minutes,
interpolated to a 250ms tick), asserting the starve is caught, no two
backward seeks fire under 4000ms apart across the whole ramp, and the rate is
already slowed on the tick before the first seek fires — proving the
regulator engaged BEFORE the flush, not on the same call as a side door
around the hold. Also covers the truth table's six named cases, the seek
target's buffer-start clamp, the hysteresis band and rate recovery, and the
wiring: `render.js`'s `applyLiveDecision` must call all three exports from
BOTH call sites (`onMseUpdateEnd`, `unfreezeIfStarved`), `index.html` must
load the module before `render.js`, `state.js` must still carry the
thresholds the module is fed, and the module must stay pure. Proven by
planting two defects against scratch copies of the module (the shipped file
itself was never touched): a copy with no `"starved"` branch — matching
today's pre-151 shipped rule — never classifies any sample of the ramp as
starved and never seeks at all, going red on "the realistic ramp ... starved,
caught, rate-limited"; a copy with the `gapOk`/`lastFixAt` rate-limit removed
fires 580 seeks in 60 real seconds at a 100ms cadence (min gap 100ms, not
4000ms), going red on "a backward seek never fires more than once per 4s".

EXTENDED 2026-08-11 — THE BLUE FLASH WHILE HE DICTATES (his first night on
v0.0.105; his log 00:37–00:39 reads `jumps=41 starves=3 in 15s` against
`jumps=0` in every other session): the regulator's own catch-up seeks pass
through a state where the element's `seeking` flag is already up (raised
synchronously by the `currentTime` assignment) while `readyState` still
reads HAVE_CURRENT_DATA with no paintable frame — the readyState-only
never-blank guard let `redraw()` clear the canvas and `drawImage()` then
silently painted nothing: one background-coloured frame per unlucky seek.
The guard's decision now lives in the module as `liveHoldFrame({mode,
readyState, seeking, everDrew})`, and two checks pin it: the hold-frame
truth table (holds mid-seek at readyState 4, holds on a starved decoder,
never holds a healthy frame / a session's first frame / JPEG mode) and the
rewritten wiring check (redraw() must call `liveHoldFrame` and feed it all
four fields — an inlined copy of the condition is how the two drift apart).
Proven by planting both defects on 2026-08-11: dropping `seeking` from the
table went red on the truth-table check alone; re-inlining the old
readyState-only condition in `redraw()` went red on the wiring check alone.

Run: `.venv\Scripts\python tests/test_live_clock.py` (needs node) — also a
fail-closed step in `build.py` (0y/6).

### `test_layout_rename_live.py` — Layout Rename Live Gate

A RENAME MUST SHOW ITS OWN WORK, NOT THE NEXT UNRELATED FRAME'S (owner report,
task 199, 2026-08-10: after renaming a layout from the ⚙ sheet, the new name
did not show anywhere on the phone until he opened Rename a SECOND time).
Root cause: `client/layout-settings.js`'s Rename Save handler sent
`layout_rename` and closed the panel, touching neither `lay.name` nor
`updateLayoutBar()` — every surface that shows a layout's name (the bar, the
list row, the ⚙ sheet's own header) reads the SAME shared `layouts` array,
which was only ever overwritten wholesale by whichever `layout_state`
happened to arrive next. Renaming moves nothing on the PC, unlike the
aspect/grid Applies right above it in the same file, which raise a real
loading cube while the windows visibly move — so a rename had no local tell
at all, and the round trip's own latency read as "did nothing" the instant
Save was tapped; reopening Rename only "fixed" it because it reads
`layouts[index]` fresh, by which point an unrelated later frame had usually
already landed.

The fix makes Save OPTIMISTIC: it mutates `lay.name` — the object every
surface reads — and calls `updateLayoutBar()` synchronously, both before
`send()`. This gate is the REAL client page + REAL server app (reuses
`test_input_pipeline.py`'s fixture, like `test_layout_drag.py` reuses
`test_layout_protocol.py`'s), driven by a real headless Chromium: it stages
the layout list fixture, taps ⚙ → Rename, retypes the name and taps Save —
with `send()` stubbed to a black hole for the WHOLE drive. That stub is the
point: a gate that let the real reply do the work would only prove the
rename is fast on localhost, never that it is optimistic, and the owner's
phone is not always on a hard-wired LAN. Asserts the bar, a freshly reopened
list row and a freshly reopened sheet header all show the new name — with no
second rename and no server reply ever arriving — plus that `layout_rename`
was still sent exactly once (the local update must be IN ADDITION to
telling the server, never a replacement for it). Proven red against the
original handler (4 of 8 checks fail: the bar, the state, the reopened row
and the reopened sheet header all still read the old name) and green after.

Run: `.venv\Scripts\python tests/test_layout_rename_live.py` (needs
playwright + chromium; reuses `test_input_pipeline.py`'s port 8898).

## Design Decisions

- **Real browser, fake injector.** Unit-testing the JS or the protocol alone
  kept missing the class of bug that actually shipped (handlers correct,
  events never delivered). Touch emulation in real Chromium exercises the
  same Pointer Events pipeline the WebView uses, headless and screen-safe.
- **Fail-closed in the build.** A missing playwright/Chromium fails the build
  rather than skipping the gate — a silently skipped gate is the same as no
  gate ([Code Rules](../../../rules/CODE.md) → No Error Masking).
- **Guards prune, not filter.** `_guards_common.py` excludes `.venv` et al.
  by pruning `os.walk`'s `dirnames` in place, never descending into them —
  filtering AFTER an unpruned walk was measured at 2.3s+ against this
  project's `.venv` (tens of thousands of files), over the guard runner's
  ~2s budget; pruning brought the full run to ~0.3s.
