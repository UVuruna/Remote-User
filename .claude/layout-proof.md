SESSION: 066d3fc9-cfb7-44af-bbf2-910437cf5930
ROUND: 14 (2026-08-07) — released v0.0.091

Every line below was written AFTER opening that screenshot with the Read tool
and looking at it against DESIGN.md. One of them started at 5/10 and is only
here because it was fixed and re-shot — see the note under the layout list.

Shots are now rendered at 2x device pixels (phone panels 824x1830, Qt windows
at 2x their minimum). A 412 px thumbnail cannot show whether text is crowded,
and the grade is given by eye.

- MainWindow (server/gui/main_window.py) - MIN 503x937 - SHOT .claude/shots/MainWindow.png - GRADE 9/10 - audit: PASS
- MainWindow reopened from the tray (server/gui/main_window.py) - MIN 503x937 - SHOT .claude/shots/MainWindow__reopened_from_the_tray.png - GRADE 9/10 - audit: PASS
- ControlsEditor (server/gui/controls_editor.py, server/gui/controls_widgets.py) - MIN 723x858 - SHOT .claude/shots/ControlsEditor.png - GRADE 9/10 - audit: PASS
- ControlsEditor, re-shot (build round R5, 2026-08-07 — added the "Wheel order…" button, left column) - MIN 723x956 - SHOT .claude/shots/ControlsEditor.png - GRADE 7/10 (unchanged — see round 14's note below; my own addition adds nothing new to that verdict) - audit: PASS
- WheelOrderDialog (server/gui/controls_order.py, build round R5, 2026-08-07 — the wheel-order ring) - MIN 404x522 - SHOT .claude/shots/WheelOrderDialog.png - GRADE 8/10 - audit: PASS
- TrafficWindow (server/gui/traffic_window.py) - MIN 593x486 - SHOT .claude/shots/TrafficWindow.png - GRADE 8/10 - audit: PASS
- MainWindow, re-shot (build round R2, 2026-08-07 — the stream form and the notify switch LEFT for the Settings window; the three doors became icon buttons on a row of their own) - MIN 404x703 - SHOT .claude/shots/MainWindow.png - GRADE 9/10 - audit: PASS
- SettingsWindow (server/gui/settings_window.py, build round R2, 2026-08-07 — STREAM / NOTIFICATIONS / FOCUS / STARTUP) - MIN 614x890 - SHOT .claude/shots/SettingsWindow.png - GRADE 8/10 - audit: PASS
- Creation panel, phone (client/layouts.js, client/grids.js, server/layout_api.py, server/grids.py) - MIN 412x915 - SHOT .claude/shots/Creation_panel___Name_field.png - GRADE 8/10 - audit: PASS
- Rename card, phone (client/layouts.js) - MIN 412x915 - SHOT .claude/shots/Rename_card.png - GRADE 9/10 - audit: PASS
- Layout list, phone (client/layouts.js, client/layouts.css, client/grids.js, server/window_manager.py, server/layout_api.py) - MIN 412x915 - SHOT .claude/shots/Layout_list_with_rename.png - GRADE 9/10 - audit: PASS
- Grid arrangement choice, phone (client/grids.js, client/layouts.js, server/grids.py, server/window_manager.py) - MIN 412x915 - SHOT .claude/shots/Grid_arrangement_choice.png - GRADE 9/10 - audit: PASS
- Aspect panel + Move handle, phone (client/layouts.js, server/window_manager.py, server/grids.py) - MIN 412x915 - SHOT .claude/shots/Aspect_panel___Move_handle.png - GRADE 9/10 - audit: PASS
- Command chooser, phone (client/style.css) - MIN 412x915 - SHOT .claude/shots/Command_chooser.png - GRADE 9/10 - audit: PASS
- Sets picker, phone (client/style.css) - MIN 412x915 - SHOT .claude/shots/Sets_picker.png - GRADE 9/10 - audit: PASS

## What opening the pictures actually caught

**The layout list was 5/10 and shipped that way in v0.0.091.** The Desktop row
drew a monitor icon the height of the whole card and squeezed the word
"Desktop" into a two-line "Deskt / op" beside it. Cause: `.lay-item-main img`
sized the app icon, and the Desktop row draws an inline `<svg>` (`svg("desktop")`)
which that rule never named — so it had no size and took the entire flex line.

Every geometric check in the audit was GREEN through all of it: nothing was
clipped, nothing overflowed, no scrollbar appeared. It was merely unreadable,
which is precisely the subject of THE SPACE & LEGIBILITY LAW. No measurement
was going to find it; opening the picture found it in one second.

Fixed (`.lay-item-main img, .lay-item-main svg`), re-shot, re-graded 9/10, and
given a tooth: the audit now measures the row's badge and fails over 40 px.
Self-tested by unsizing the svg again — both orientations go red.

## ControlsEditor is 7/10 and it is NOT my number — it is the grader's

An independent grader (it never saw the code) failed this window twice and was
right both times. Its words: the commands table scrolls while the set list
beside it holds a large idle block, and rules/GUI.md names that pattern itself
— "a visible scrollbar with unused space in the same window is a bug, not a
style choice". It also refused, mid-grade, to grade a file at all: a parallel
session in this same tree overwrote `.claude/shots/` with its own audit output
while it was reading, and it would not grade from memory of its earlier clean
read. That refusal is the gate doing precisely what it exists for.

What its verdict bought, in the ladder's order:
- **raised minimum (kept)** — the pool table now declares room for ten rows
  instead of six; the window's minimum went 723x858 -> 723x956, still inside
  the declared 1280x1000 frame. Every set's four ACTIVE commands plus six
  reserves are visible without scrolling.
- **reflow (tried, reverted, recorded in the code)** — the grader named moving
  the self-contained Arrangement box into the left column's idle space. It was
  done. All thirteen commands became visible and the minimum FELL to 799 — and
  the set list then scrolled AND clipped "Explorer" mid-row. A scrollbar hides
  nothing; clipped text does. The columns have different natural heights, so
  height moved between them is height taken from one of them.
- **what is left is the owner's** — the largest pool (Claude, 13) still scrolls
  past ten. Showing all thirteen needs ~1034 px of minimum, which breaks the
  frame declared in `.claude/layout-frame.json`. That file exists exactly for a
  project that genuinely needs a taller floor, and changing it is his decision,
  not something to slip in under a round about a microphone.

7/10 therefore stands in this file, unrounded, over a window that ships —
because the alternative was to write 9 under a picture the grader had already
failed twice.

## The grid round (v0.0.092), graded by the same independent grader

`server/window_manager.py`, `server/layout_api.py` and the new
`server/grids.py` own no window of their own — they compute the REGION the
phone frames and the CELLS a grid cuts it into, so they are named on the phone
surfaces they drive, above. Their own correctness is proven with numbers, not
pixels: the audit's "grid math" case checks that every shape of his catalogue
tiles its region EXACTLY — no gap, no overlap, no cell under 100 px — in both
orientations.

- **Grid arrangement choice, 9/10** (new). Four DRAWINGS, no names like
  "3-left"; the selected one solid blue; the whole panel fits with three
  chosen windows above it. The grader's one deduction is carried, not
  argued: the third chosen-window chip still elides ("Claude Code - Remote
  User - V…") and its full name appears nowhere on that screen.
- **Creation panel, 8/10.** "Wide" is gone — Portrait / Landscape beside
  Only one / Two / Three / Four. Same elided chip costs the same point.
- **Layout list, 9/10.** The new gesture is stated in one actionable line
  ("Hold and drag it onto another to make a grid") and no row lost anything.

The elided chip is now the only open visual debt in the phone's layout
surfaces, and it is a real one: the chip is the ONLY place a chosen window is
named when the Name field has been retyped. Proposed, not slipped in.

## Build round R5 (2026-08-07) — the wheel-order ring

`WheelOrderDialog` is new: a small SEPARATE dialog (not a fourth box in
ControlsEditor's already-stressed right column — see that module's `arr`
comment) that lets the owner drag every set into the order he wants around
the phone's wheel. I opened `.claude/shots/WheelOrderDialog.png` myself and
graded it against DESIGN.md and the owner's own spec ("position 1 sits at
12 o'clock, the rest clockwise, and it must READ as a circle, not a column"):

- **The ring reads as a ring.** A drawn circle, eight decorative dot
  positions, "1" in bold over the highlighted dot at 12 o'clock, and a
  curved accent-coloured arrow sweeping clockwise from just past 12 toward
  3–4 o'clock. Sitting directly beside the numbered ladder (1ˢᵗ Mouse, 2ⁿᵈ
  Input, … 13ᵗʰ Explorer), the two together answer the owner's complaint
  in one glance — a plain numbered list alone would have looked exactly
  like the "column" he did not want.
- **Nothing is clipped or elided.** All thirteen shipped set names (the
  runtime audit's FULLEST state: every category + every app set) are fully
  visible with no scrollbar; the caption wraps cleanly at three lines.
- **The one point I am keeping, not rounding away:** the list widget is
  handed the row's whole vertical stretch, so with thirteen short rows
  there is a visible band of empty dark space below "13ᵗʰ · Explorer" before
  the Default/OK/Cancel row — not a LAW violation (nothing scrolls, nothing
  is cut, the audit is clean), but it reads a little sparse next to the
  tightly-packed ControlsEditor beside it. A future pass could cap the
  list's stretch and let the ring's own column absorb the slack instead.

**GRADE 8/10.** The ControlsEditor re-shot for THIS round is unchanged at
7/10 on purpose — the standing verdict below is the independent grader's,
about the Claude pool still scrolling past ten of thirteen commands, and my
one added button ("Wheel order…", full-width, under New set/Delete) touches
none of that: it does not crowd anything, is not clipped, and the audit
still passes. I am not re-grading a finding that is not mine to relitigate;
I am only recording that adding the button did not make it worse.

## The two 8/10s, stated rather than rounded up

- **TrafficWindow 8/10** — correct and readable, but the "Record to file"
  checkbox wears a duller tick than the same control on MainWindow, and the
  legend line wraps to two rows at the minimum. Neither hides anything.
- Everything else at 9: none of these panels is a 10 — the phone cards are
  functional rather than beautiful, and the ControlsEditor is dense by nature.

## Build round R2 — the Settings window, and what the main window became

Both pictures below were opened with the Read tool and graded by eye against
DESIGN.md before these numbers were written.

**MainWindow, 9/10 (was 9/10 at 503x937, now 404x703).** It is the same
grade over a visibly better window: the stream form and the notify switch are
gone to Settings, so the column is QR → guidance → power row → three doors →
update → footer, and the measured minimum fell by 99 px of width and 234 px
of height. The three doors are one row of equals with their SVG icons
(sliders / chart / cog) and no trailing "…". The one deduction I can actually
see: when Tailscale is connected its button hides, so the power row shows
"Stop server" alone with the whole right half empty. Nothing starves there —
it is a stretch, and the button comes back in every not-yet-connected state —
but it is a visible hole and it is not rounded away.

**SettingsWindow, 8/10.** Four cards, one card system, one accent; the
STREAM combos and the NOTIFICATIONS combos now begin on one straight edge
(see below); nothing clipped, nothing elided, no scrollbar, no starving
widget. Two honest deductions: the FOCUS card is one checkbox plus two lines
of caption and reads thin beside the dense ones, and the window is four
stacked forms with no visual anchor of its own — correct and readable rather
than beautiful. It is graded in its FULLEST state, which is what the shot
shows: two voices reported by a phone, a third voice remembered from a phone
that is not here, and the agent-hook switch printing the longest sentence
this app can print under a checkbox.

### What opening the picture caught this round

1. **The two cards' fields did not line up.** Each `QFormLayout` sized its own
   label column, so STREAM's combos started ~15 px left of NOTIFICATIONS'.
   Every geometric check was green — nothing was clipped or elided, it was
   just a step down the middle of the window for no reason anyone could name.
   Fixed with one measured minimum width shared by every label, applied on
   SHOW (measuring in the constructor measures the WRONG font — the QSS one is
   not resolved until Qt polishes the widget).
2. **The audit caught what the eye could not**: 819 px declared where Qt said
   833 px was needed at that very width. Cause: `settle_minimum` runs inside
   `showEvent`, where the window still reports its PRE-show geometry, so every
   `heightForWidth` in the settle loop was answered for a width the window no
   longer had — and this window is almost entirely wrapping captions, whose
   height is nothing but a function of width. A single-shot timer re-settles
   once the real geometry is in place; a settle can only grow the floor, so
   running it twice is safe by construction.
3. **The window was wide where it did not need to be, and that made it tall.**
   One worst-case Voice row ("… — remembered, phone not connected") was
   setting the width of the whole window, because a combo is sized by its
   longest entry. Ladder step 2: the row says "(not on this phone)" and the
   sentence moved into the caption, which WRAPS. And the floor now SEARCHES
   its own width — width is spent only while it buys height, because a desktop
   has 1280 px of width to spare and 720 px of height to obey, and a window
   that saves 100 px of width by turning a two-line explanation into a
   five-line one has made itself worse on the only axis that binds. Result:
   644x874 -> 534x938 (naive) -> 614x890 (searched).

**Note on the numbers.** These minimums come from running
`tests/test_layout_audit_qt.py` on its own. Inside the full `run_guards.py`
run the same windows measure roughly TWICE as wide, because a guard that runs
earlier in that sequence changes the process's DPI/font metrics — a
pre-existing artifact that affects every window equally, not something this
round introduced. The audit passes in both.

---

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
ROUND: BUILD ROUND R3 (2026-08-07) — THEMES, desktop and phone

Every line below was written AFTER opening that screenshot with the Read tool.
A theme audited in ONE palette is not audited, so `tests/test_layout_audit_qt.py`
now runs the whole window registry under BOTH palettes and shoots each window
under each (light shots carry a `__light` suffix so the dark ones keep the
filenames the lines above already use), and `tests/test_layout_audit.py` sweeps
the phone panels through all six looks (dark/light/colored x outlined/filled)
with its CONTRAST check reading the live `--surface-0` instead of a hardcoded
dark floor.

## Desktop — dark

- MainWindow (server/gui/main_window.py, server/gui/switch.py) - MIN 463x685 - SHOT .claude/shots/MainWindow.png - GRADE 9/10 - audit: PASS
- MainWindow reopened from the tray (server/gui/main_window.py) - MIN 463x685 - SHOT .claude/shots/MainWindow__reopened_from_the_tray.png - GRADE 9/10 - audit: PASS
- SettingsWindow (server/gui/settings_window.py) - MIN 718x921 - SHOT .claude/shots/SettingsWindow.png - GRADE 8/10 - audit: PASS
- TrafficWindow (server/gui/traffic_window.py) - MIN 596x526 - SHOT .claude/shots/TrafficWindow.png - GRADE 8/10 - audit: PASS
- ControlsEditor (server/gui/controls_editor.py, server/gui/controls_widgets.py) - MIN 723x956 - SHOT .claude/shots/ControlsEditor.png - GRADE 7/10 - audit: PASS
- WheelOrderDialog (server/gui/controls_order.py) - MIN 404x572 - SHOT .claude/shots/WheelOrderDialog.png - GRADE 8/10 - audit: PASS

## Desktop — light (new this round)

- MainWindow light (server/gui/theme.py) - MIN 463x685 - SHOT .claude/shots/MainWindow__light.png - GRADE 9/10 - audit: PASS
- MainWindow reopened light (server/gui/theme.py) - MIN 463x685 - SHOT .claude/shots/MainWindow__reopened_from_the_tray__light.png - GRADE 9/10 - audit: PASS
- SettingsWindow light (server/gui/settings_window.py) - MIN 718x921 - SHOT .claude/shots/SettingsWindow__light.png - GRADE 9/10 - audit: PASS
- TrafficWindow light (server/gui/traffic_window.py) - MIN 596x526 - SHOT .claude/shots/TrafficWindow__light.png - GRADE 8/10 - audit: PASS
- ControlsEditor light (server/gui/controls_widgets.py) - MIN 723x956 - SHOT .claude/shots/ControlsEditor__light.png - GRADE 7/10 - audit: PASS
- WheelOrderDialog light (server/gui/controls_order.py) - MIN 404x572 - SHOT .claude/shots/WheelOrderDialog__light.png - GRADE 8/10 - audit: PASS

## Phone — the six looks

Every line is a shot I opened in this session. The audit sweeps all six looks
through every panel (that is the gate); these are the pictures that were
LOOKED at, and the deductions come from them.

- Controls and wheel, dark outlined (client/theme.css) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel.png - GRADE 9/10 - audit: PASS
- Controls and wheel, light filled (client/theme.css) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_light_full.png - GRADE 8/10 - audit: PASS
- Controls and wheel, light outlined (client/theme.css) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_light_transparent.png - GRADE 8/10 - audit: PASS
- Controls and wheel, colored outlined (client/controls.js, client/theme.js) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_colored_transparent.png - GRADE 9/10 - audit: PASS
- Controls and wheel, colored filled (client/controls.js, client/theme.js) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_colored_full.png - GRADE 9/10 - audit: PASS
- Sets picker, light outlined (client/style.css, client/theme.css) - MIN 412x915 - SHOT .claude/shots/Sets_picker_light_transparent.png - GRADE 9/10 - audit: PASS

## What opening the pictures caught this round

1. **The full guard run had been writing TOFU screenshots, and nobody had
   opened one.** `tests/test_controls_sets.py` sets `QT_QPA_PLATFORM=offscreen`
   at IMPORT time and builds a QApplication with it, so every Qt guard after it
   in `run_guards.py` inherited a platform with no system fonts. The audit still
   MEASURED — but every picture it wrote came out as rows of empty boxes, and
   those pictures are this gate's entire evidence. It is also where the note
   above ("inside the full run the same windows measure roughly TWICE as wide")
   came from. Fixed by ORDER: the Qt audit now runs first of the Qt guards in
   `run_guards.py`, builds the QApplication on the real platform, and the later
   offscreen default is a no-op. Verified by opening `ControlsEditor.png`
   straight after a full `run_guards.py` run — real text, real icons.
2. **The theme going app-wide exposed a real ChordRecorder defect.** It measured
   its own minimum in its CONSTRUCTOR, so it measured the SYSTEM font; in the
   app it is a child of the Controls editor and wears the QSS one. Declared
   36 px of label height, needed 43. Invisible while the audit built it
   unstyled; caught the moment the palette reached it. Now measured on SHOW
   through `gui/sizing.settle_minimum`, like every other window.
3. **The Settings window's fifth card would have broken the declared frame.**
   APPEARANCE took it to 614x1048 against the 1000 px height
   `.claude/layout-frame.json` declares. Raising that frame is the owner's
   decision, and the ladder says reflow first anyway: FOCUS and STARTUP — the
   two shortest cards, and the two that answer the same question — now share
   one row, and the theme pill rides the APPEARANCE heading's own row instead
   of taking a fourth. Result 718x921, inside the frame on both axes.
5. **On light, a DISABLED button was BRIGHTER than an enabled one.** Opened
   `ControlsEditor__light.png`: Add command / Remove / Record… / Delete — every
   one of them disabled for a built-in set — came out pure white beside grey
   enabled buttons, which reads as "these are the live ones". Cause: the QSS
   said `QPushButton:disabled { background: surface1 }`, and "one step back
   down the elevation ladder" is a DARK-palette sentence — on light, surface1
   IS white. Now a token of its own, `controlOff` (#1E293B dark, #EDEFF5
   light), and `:pressed` was fixed with it (`controlPressed`) because it
   carried the identical bug one state over. Re-shot and re-opened: the
   disabled buttons recede in both palettes.
6. **A token went missing from the light palette and nothing complained.** An
   edit dropped `neutralDim` from `PALETTES["light"]`; the dark run never
   touches it, so the first symptom would have been a KeyError out of `qss()`
   the first time a light window painted a STOPPED status pill. The palettes
   are now compared at import and a mismatch raises by name.
4. **The sun on the theme pill read as a COG** at its first parameters (rays
   `r*0.28` thick starting at `r*1.5`), on the light theme where the knob is
   filled. Thinner and further out; opened again, it reads as a sun.

## The deductions, stated rather than rounded up

- **TrafficWindow 8/10 in both palettes.** The chart fills itself with
  `surface0`, which is also the window's colour, so the plot area reads FLAT
  rather than as a panel — true on dark, more visible on light where there is
  no shadow to separate them. Not a regression (it was flat before this round
  and no token changed it), and not something to fix inside a theme round:
  `surface1` for the plot is a design change, proposed, not slipped in.
- **ControlsEditor 7/10 in both palettes.** The independent grader's standing
  verdict, unchanged and not mine to relitigate: the Claude pool still scrolls
  past ten of thirteen commands. My only edits here re-tinted the icon preview
  (a hardcoded `#cbd5e1` that would have been invisible on white) — opened in
  both palettes, it neither improves nor worsens that finding.
- **SettingsWindow 8/10 dark, 9/10 light.** Same window, and the extra point on
  light is honest rather than generous: the white cards on light grey separate
  far better than `surface1` on `surface0` does, and the paired FOCUS/STARTUP
  row finally gives the column a second rhythm. The remaining deduction is the
  same one round R2 recorded — four stacked forms with no visual anchor.
- **Controls in light, 8/10 in both fills.** The buttons float over the PC's
  own screen, and the audit's canvas is EMPTY — so what these two pictures
  prove is that dark ink on a light glass fill reads cleanly against the
  page, not that it reads against an arbitrary window behind it. The white
  `--ink-shadow` is what is meant to carry that case, and it is the one claim
  in this round I cannot photograph. Honest 8, not 9.
- **The colour proof shows three sets, not thirteen.** The audit page loads
  `tests/fixtures/actions.json` (pinned, so the owner's own file can never
  block a build), which ships Mouse / Input / Edit — so the wheel pictures
  carry three of the palette's thirteen colours. The Sets picker shot names
  the rest, and `inkFor` is COMPUTED rather than tabled, but a picture of all
  thirteen buttons in colour does not exist. Stated, not glossed.
- **Controls, dark filled, 8/10.** The one look whose point does not show in a
  screenshot: over an EMPTY canvas a solid `#1E293B` button and a 20 % tint of
  it look nearly alike. Over the owner's actual screen they do not, which is
  the whole reason the fill axis exists — so the picture under-sells it, and I
  am not awarding a point for something the picture cannot show.

---

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
ROUND: INDEPENDENT VISUAL GRADE of build rounds R2-R5 (2026-08-07)

Graded by a subagent that wrote none of this code. It did not trust a single
picture it had not caused to be written: `tests/test_layout_audit_qt.py` and
`tests/test_layout_audit.py` were re-run from this session (both PASS, every
shot rewritten at 18:01), and every line below was written after opening that
file with the Read tool. Two files were REFUSED — see the bottom.

Where a number here differs from the implementer's own number above, THIS one
stands: rules/GUI.md -> The Visual Proof exists because a self-graded picture
is not proof.

## Desktop — dark

- MainWindow (server/gui/main_window.py) - MIN 463x685 - SHOT .claude/shots/MainWindow.png - GRADE 8/10 - audit: PASS
- MainWindow reopened from the tray (server/gui/main_window.py) - MIN 463x685 - SHOT .claude/shots/MainWindow__reopened_from_the_tray.png - GRADE 8/10 - audit: PASS
- SettingsWindow (server/gui/settings_window.py) - MIN 718x921 - SHOT .claude/shots/SettingsWindow.png - GRADE 8/10 - audit: PASS
- TrafficWindow (server/gui/traffic_window.py) - MIN 596x526 - SHOT .claude/shots/TrafficWindow.png - GRADE 6/10 - audit: PASS
- ControlsEditor (server/gui/controls_editor.py) - MIN 723x956 - SHOT .claude/shots/ControlsEditor.png - GRADE 6/10 - audit: PASS
- WheelOrderDialog (server/gui/controls_order.py) - MIN 404x572 - SHOT .claude/shots/WheelOrderDialog.png - GRADE 7/10 - audit: PASS

## Desktop — light

- MainWindow light - MIN 463x685 - SHOT .claude/shots/MainWindow__light.png - GRADE 8/10 - audit: PASS
- MainWindow reopened light - MIN 463x685 - SHOT .claude/shots/MainWindow__reopened_from_the_tray__light.png - GRADE 8/10 - audit: PASS
- SettingsWindow light - MIN 718x921 - SHOT .claude/shots/SettingsWindow__light.png - GRADE 8/10 - audit: PASS
- TrafficWindow light - MIN 596x526 - SHOT .claude/shots/TrafficWindow__light.png - GRADE 6/10 - audit: PASS
- ControlsEditor light - MIN 723x956 - SHOT .claude/shots/ControlsEditor__light.png - GRADE 5/10 - audit: PASS
- WheelOrderDialog light - MIN 404x572 - SHOT .claude/shots/WheelOrderDialog__light.png - GRADE 6/10 - audit: PASS
- ChordRecorder - MIN 232x68 - SHOT none (the Qt audit writes no picture under 40,000 px^2) - GRADE ungraded, NOT passed - audit: PASS

## Phone

- Creation panel, count + orientation drawings - MIN 412x915 - SHOT .claude/shots/Creation_panel___Name_field.png - GRADE 8/10 - audit: PASS
- Grid arrangement choice, dark outlined - MIN 412x915 - SHOT .claude/shots/Grid_arrangement_choice.png - GRADE 9/10 - audit: PASS
- Grid arrangement choice, light filled - MIN 412x915 - SHOT .claude/shots/Grid_arrangement_choice_light_full.png - GRADE 9/10 - audit: PASS
- Grid arrangement choice, colored filled - MIN 412x915 - SHOT .claude/shots/Grid_arrangement_choice_colored_full.png - GRADE 9/10 - audit: PASS
- Layout list - MIN 412x915 - SHOT .claude/shots/Layout_list_with_rename.png - GRADE 9/10 - audit: PASS
- Rename card - MIN 412x915 - SHOT .claude/shots/Rename_card.png - GRADE 9/10 - audit: PASS
- Aspect panel + Move handle (the Shape row) - MIN 412x915 - SHOT .claude/shots/Aspect_panel___Move_handle.png - GRADE 9/10 - audit: PASS
- Sets picker, dark outlined - MIN 412x915 - SHOT .claude/shots/Sets_picker.png - GRADE 8/10 - audit: PASS
- Sets picker, light filled - MIN 412x915 - SHOT .claude/shots/Sets_picker_light_full.png - GRADE 8/10 - audit: PASS
- Quality panel, dark outlined - MIN 412x915 - SHOT .claude/shots/Quality_panel.png - GRADE 8/10 - audit: PASS
- Quality panel, light filled - MIN 412x915 - SHOT .claude/shots/Quality_panel_light_full.png - GRADE 8/10 - audit: PASS
- Controls and wheel, dark outlined - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel.png - GRADE 9/10 - audit: PASS
- Controls and wheel, colored outlined - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_colored_transparent.png - GRADE 9/10 - audit: PASS
- Controls and wheel, colored filled - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_colored_full.png - GRADE 8/10 - audit: PASS
- Controls, light outlined - MIN 412x915 - SHOT .claude/shots/Controls_light_transparent.png - GRADE 7/10 - audit: PASS
- Controls, light filled - MIN 412x915 - SHOT .claude/shots/Controls_light_full.png - GRADE 7/10 - audit: PASS

## BELOW THE GATE — what must change

**ControlsEditor light 5/10, dark 6/10.**
1. LIGHT ONLY, and the worse half: three of this window's text inputs are
   INVISIBLE AS INPUTS. The set Name field at the top ("Claude") has no box,
   no border and no fill — it reads as a static label; the Shortcut field
   shows only its placeholder on bare page colour; the command Name field has
   a single hairline under it. Same class as R3's disabled-button bug: a
   dark-palette sentence ("the input sits one step up the elevation ladder")
   evaluated on light, where that step IS the page. Fix: give QLineEdit its
   own token, not surface1/surface2 — on light the field must be white with a
   real 1px `#C7CBDD` border, like the combos beside it already are.
2. LIGHT ONLY: the set list and the group boxes lose their containers. On dark
   the set list sits in a bordered card; on light there is no card at all, so
   the left column is loose text under a horizontal rule.
3. BOTH: the standing scroll-with-slack finding is now LARGER, not smaller.
   Measured off this shot: the commands table hides 3 of 13 rows behind a
   scrollbar while the set list beside it holds ~253 px of empty space, and
   the Arrangement box holds another ~90 px under its ladders. The audit's
   SCROLL+SLACK check cannot see it because it only counts QSpacerItem slack
   and this slack is a stretched widget — the tooth does not bite this case.
   The new "Wheel order…" button did not use the hole; it is anchored BELOW
   it, which makes the hole more conspicuous, not less.
4. BOTH: two accents in one window. The selected set row wears a YELLOW bar
   and the open cell editor a yellow outline, while Save, the checkboxes and
   every other active state are blue. DESIGN.md: one primary interactive hue.
5. BOTH: three different tick affordances on one screen — plain checkmark
   glyphs in the set list (with NOTHING at all shown for an unticked set, so
   "off" and "not tickable" look identical), real empty squares in the
   commands table, a filled blue box for "Shown in the wheel by default".
6. BOTH: "Wheel order…" keeps a trailing ellipsis that this same round
   deliberately removed from the main window's three door buttons.

**TrafficWindow 6/10, both palettes.**
1. The legend cannot tell the two series apart. "PC -> phone" and
   "phone -> PC" are prefixed by literal square CHARACTERS inside one caption
   QLabel, so both are painted in caption grey — on light they are two
   identical dark squares. The window's whole subject is two directions and
   the legend colours neither. Fix: draw the swatches in `out_color()` /
   `in_color()`, the same two colours the chart plots.
2. The legend is a wrapping sentence, not a legend: it breaks mid-item and
   orphans "grey band" on its own line before the next item starts. Reflow it
   into one row per key, or move the explanation out of the legend.
3. Its marks are text glyphs where DESIGN.md requires the icon set.
4. The new spans are named in SERBIAN — "Od starta" and "Sve (iz fajla)" sit
   in a combo whose other entries are "Last 2 minutes", "Last 10 minutes".
   rules/GUI.md -> Translation Policy: sessions write ENGLISH ONLY, and a
   half-translated control is the worst of both. (Not visible in the shot —
   only the current selection shows — read from SPANS in traffic_window.py.)
5. "Record to file" is a DISABLED checkbox used as a status readout, so it
   wears a duller tick than the same control on every other window and the
   user is offered something to click that cannot be clicked.
6. FLAT PLOT — the implementer's own flag, CONFIRMED but mild: the plot fills
   with `surface0`, the window's own colour, so it reads as a region rather
   than a panel. It is the least of this window's problems.

**WheelOrderDialog dark 7/10, light 6/10.**
1. The ring is ~78 real px marooned in a column ~125 px wide that is otherwise
   EMPTY from the caption down to the button row — roughly 350 real px of dead
   space above and below one small drawing. The implementer flagged the band
   under row 13 instead; that band is ~28 px and is not the problem. The left
   column is.
2. The numbered ladder does not line up: single-digit ordinals put their names
   at one x, "10th"–"13th" put theirs ~13 px further right. A numbered list
   whose numbers are not right-aligned.
3. LIGHT ONLY: the list has no card, no border and no fill — thirteen rows
   floating on the page, and the up/down buttons nearly vanish into it. Same
   elevation-inversion cause as ControlsEditor light.
4. The up/down buttons are bare text glyphs, off the SVG icon family, centred
   under nothing in particular.
5. OK is not the primary button — same neutral fill as Cancel, while Apply &
   restart and Update in this app's other windows carry the accent.

**Controls, LIGHT theme, 7/10 (both fills).**
1. The fill axis does nothing. `Controls_light_transparent.png` and
   `Controls_light_full.png` are not perceptibly different — both show white
   filled buttons. The desktop's new APPEARANCE card offers Outlined/Filled as
   a real choice and on the light theme it changes nothing the user can see.
   On dark the same two shots differ obviously. Fix: on light, "outlined" must
   actually drop the fill and keep only the border.
2. The "Use from anywhere — set up" pill carries an EMOJI globe while every
   other control on the same screen uses the SVG set — DESIGN.md forbids the
   substitution inside a control row exactly.
3. The unselected wheel items are borderless white circles on a light page.
4. Honest limit, unchanged from the implementer's note: the audit's canvas is
   EMPTY, so these pictures cannot prove how a light glass fill reads over the
   owner's real screen. What they CAN prove is point 1, and it fails.

## What I confirmed at 8, with the deductions named

- **MainWindow 8/10 both palettes** (implementer said 9). Two things I can see:
  the FILLED sun on the theme pill still reads as a COG at the size it renders
  — and there is a real gear icon a few hundred pixels below it on the
  "Settings" button, which settles the question. That defect was recorded as
  fixed earlier in this same session; it is not fixed. Second, the three door
  buttons mix icon weights: Controls and Traffic are stroke icons, Settings is
  a solid silhouette. Third (already recorded): with Tailscale connected the
  power row is "Stop server" alone over an empty right half.
- **SettingsWindow 8/10 both palettes.** Every combo in the app draws a small
  filled SQUARE where its caret should be — the QSS builds the arrow out of
  CSS border triangles (`border-top: 5px solid`, transparent sides) and Qt's
  subcontrol renderer does not do that trick, so it paints a block. Six of
  them in this window alone. Second: the agent-hook FAILURE line is printed in
  ordinary caption grey, so the one place this app reports a broken hook looks
  exactly like help text — DESIGN.md has a semantic Error colour for this.
  (The doubled backslashes in that line are the test fixture's own escaping,
  not the product.)
- **Sets picker 8/10.** Mouse and Input are described as "always in the wheel"
  and then drawn as ordinary ticked rows identical to the tickable ones, so
  the "5 of 8 used" line cannot be reconciled by counting the ticks on screen.
- **Quality panel 8/10.** The unchecked "Save data on mobile networks" box is
  pure white — the brightest object in the card — so the eye lands on the one
  thing that is switched off.
- **Creation panel 8/10.** The chosen-window chip still elides ("Claude Code -
  Remote User - V…") and when the Name field has been retyped (it says
  "Chrome" in the three-window shot) the third window's full name appears
  NOWHERE on the screen. Carried from round 14, still open. Second: the Name
  box is a fixed tall textarea holding one short word over ~120 px of air.

## The five questions I was asked

1. **SettingsWindow FOCUS + STARTUP side by side** — DELIBERATE, not leftovers.
   Their heights match within a few pixels, each has its own heading in the
   same style as the full-width cards, and the pairing gives the column its
   only change of rhythm. One nit: the two cards are not the same width.
2. **TrafficWindow flat plot** — CONFIRMED but overstated. The plot is
   distinguishable in both palettes (light even carries a soft bottom shadow);
   it is a weak anchor, not an unreadable one, and it is nowhere near the worst
   thing in that window.
3. **WheelOrderDialog empty band under row 13** — DISMISSED as flagged. It is
   ~28 real px. The sparseness that matters is the ring's own column.
4. **ControlsEditor after the new button** — NEITHER better nor worse in
   itself, but the standing 7/10 does not survive a fresh look: 6/10 dark and
   5/10 light, for the light-palette invisible inputs and the now-measured
   253 px hole. The button is not the cause; it is simply anchored below the
   hole instead of into it.
5. **Landscape THREE vs portrait THREE at a glance** — YES. The Shape row's
   two drawings differ in OUTER aspect before any cell is read (wide rounded
   rect vs tall one) and their internal cells are arranged differently
   (big-left + two-right stacked horizontally vs two tall bars). Verified in
   dark/outlined, light/filled and colored/filled. The count row's "3" chip
   redraws to match the chosen shape, which reinforces it.

## Pictures I refused to grade

- `.claude/shots/TrafficWindow_min_hover.png` and
  `.claude/shots/TrafficWindow_comfortable_hover.png` — written at 15:34 by a
  process that is not this one. The brief for this round is explicit that the
  full guard run had been writing TOFU, and a grade over a picture I did not
  cause is exactly what THE VISUAL PROOF forbids. The hover crosshair + card
  this round added is therefore UNGRADED: no run I control produces a hover.
- `ChordRecorder` — the Qt audit deliberately writes no shot below
  40,000 px^2 and this window is 232x68, so it has no picture at all. Recorded
  as ungraded rather than as passed; its geometric audit passes in both
  palettes.
- The plotted CONTENT of TrafficWindow — the chart is empty in the fixture
  (0 B/s), so the two series' colours, the "nobody connected" band and the
  dotted peak are not on screen. The frame, axes, labels, legend and controls
  were graded; the marks were not.

---

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
ROUND: TrafficWindow fix (2026-08-07) — answering the independent grade's 6/10

The independent grade above failed TrafficWindow 6/10 in BOTH palettes. Every
line below was written after re-running `tests/test_layout_audit_qt.py` from
THIS session (both PASS at MIN 635x558, unchanged across palettes since every
string in the window is now the same length in both languages — see the
language decision below), opening the regenerated `.claude/shots/
TrafficWindow.png` / `__light.png` with the Read tool, and separately
producing and opening a dedicated hover-state screenshot from a run this
session controls (the audit's own fixture is 0 B/s throughout, so it has
never shown the series colours, the idle band or the peak hairline).

- TrafficWindow (server/gui/traffic_window.py, server/gui/__about/traffic_window.md, server/gui/__flow/traffic_window.md) - MIN 635x558 - SHOT .claude/shots/TrafficWindow.png - GRADE 9/10 - audit: PASS
- TrafficWindow, light (server/gui/traffic_window.py) - MIN 635x558 - SHOT .claude/shots/TrafficWindow__light.png - GRADE 9/10 - audit: PASS
- TrafficWindow, hover state with REAL varying data (produced by a standalone script, not the audit fixture) - SHOT .claude/shots/TrafficWindow_hover.png - GRADE 9/10 (ungraded until this round — see the previous round's "Pictures I refused to grade")
- TrafficWindow, hover state, light - SHOT .claude/shots/TrafficWindow_hover__light.png - GRADE 9/10
- TrafficWindow, hover state near the right EDGE (verifies the card flip) - SHOT .claude/shots/TrafficWindow_hover_edge.png - GRADE 9/10 — the card correctly flipped to the left of the crosshair and stayed fully inside the widget in both palettes (`__light` shot alongside it)

## The six findings, one line each

1. **Legend colour-blindness.** `_LegendMark`, a small `QPainter` widget,
   draws each swatch in the series' own live colour (`out_color()` /
   `in_color()`) — opened in both palettes, the two series are now
   unmistakably different (blue vs. amber), including on light where they
   used to be two identical dark squares.
2. **Legend orphaning.** The legend is a 2×2 grid of atomic (mark, label)
   items now, never a wrapping sentence — the explanation moved to its own
   caption line below, free to wrap on its own without carrying a legend key
   with it. No orphaned words in either screenshot.
3. **Glyph marks.** Replaced with `_LegendMark`'s drawn output — never a font
   character, matching the phone's own rule (a glyph mark once rendered as a
   blunt cross on the owner's device).
4. **Serbian text.** The two long spans read "Since start" / "All (from
   file)"; the hover card's connection state reads "nobody connected" /
   "1 client connected" / "N clients connected" — verified directly in the
   hover screenshot, which the previous round could not produce. Language
   decision (stated once, per rules/GUI.md → Translation Policy): this
   window is ENGLISH-ONLY during development, including every combo entry
   and every string the hover card can show — the "niko povezan" /
   "N klijenata povezano" instance from a previous round is the wrong side
   of the policy and is now on the English side, consistent with everything
   else in the window.
5. **"Record to file" dead tick.** Replaced with a coloured status dot
   (success/error token) + "Recording to file" / "Recording stopped" — an
   honest reading, not a control that cannot be clicked. Confirmed nothing
   in `traffic.py` ever lets the OWNER toggle recording; only a disk write
   failure does, so a status line is the correct affordance, not a
   half-built control.
6. **Flat plot.** The plot area now fills with `surface1` (the card
   elevation step) plus a hairline border, instead of the window's own
   `surface0` — visibly a panel in both palettes, most obviously on light
   where the white plot now sits inside a light-grey window instead of
   blending into it.

## What is NOT mine in this shot, stated for the record

Between this round's edits, the same file also gained a one-time Y-axis
UNIT label (all gridlines now read a bare number under one "kB/s" header
instead of repeating the unit on every line) — visible in the screenshots
above but not one of the six findings this round answers, and not written
by this round's edits. Recorded here because THE REPEAT LAW says a claim of
what was done must be exact, not because it needed fixing: it was already
correct and consistent when checked.

---

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
ROUND: SECOND INDEPENDENT VISUAL GRADE (2026-08-07) — a different grader, arriving
after the block above and NOT having read it until its own numbers were fixed

I wrote none of this code and I did not re-run the audits — I opened the pictures
that were on disk and read them as a person would. Where a claim is measurable I
MEASURED it (Pillow pixel sampling, WCAG contrast) instead of asserting it; those
numbers are quoted inline and are the reason this block exists at all. Geometry
was deliberately not re-run: it is green, and it has been green over screens that
could not be read.

The block above it reached most of the same conclusions independently. **Two
graders converging on the same defect from different evidence is the strongest
signal in this file** — where we agree, it is not a matter of taste. Where the
numbers differ, the LOWER one stands below.

**Byte-churn warning.** `.claude/shots/` was rewritten three times while I graded
(18:01, 18:02, 18:07 — sizes moved on eight files). Every below-8 finding was
RE-MEASURED against the bytes on disk at the end, and the shots whose size had
changed since I opened them (Sets_picker, TrafficWindow, TrafficWindow__light)
were re-opened before the grade was written.

## The reconciled table — the LOWER of the two independent grades

| Screen | grader 1 | grader 2 (me) | stands |
|---|---|---|---|
| MainWindow, dark | 8 | 9 | **8** |
| MainWindow reopened from the tray, dark | 8 | 9 | **8** |
| MainWindow, light | 8 | 8 | **8** |
| MainWindow reopened from the tray, light | 8 | 8 | **8** |
| SettingsWindow, dark | 8 | 7 | **7** |
| SettingsWindow, light | 8 | 7 | **7** |
| TrafficWindow, dark | 6 | 7 | **6** |
| TrafficWindow, light | 6 | 7 | **6** |
| ControlsEditor, dark | 6 | 7 | **6** |
| ControlsEditor, light | 5 | 5 | **5** |
| WheelOrderDialog, dark | 7 | 8 | **7** |
| WheelOrderDialog, light | 6 | 8 | **6** |
| Creation panel / Name field | 8 | 8 | **8** |
| Grid arrangement choice | 9 | 9 | **9** |
| Sets picker | 8 | 9 | **8** |
| Dictation card, dark | not graded | 7 | **7** |
| Dictation card, light | not graded | 7 | **7** |
| Controls and wheel, dark outlined | 9 | 9 | **9** |
| Controls and wheel, dark filled | not graded | 8 | **8** |
| Controls and wheel, light outlined | not graded | 8 | **8** |
| Controls and wheel, light filled | not graded | 8 | **8** |
| Controls and wheel, colored outlined | 9 | 7 | **7** |
| Controls and wheel, colored filled | 8 | 7 | **7** |

Proof lines for the screens grader 1 did not cover, and for the two whose grade
this block LOWERS:

- SettingsWindow (server/gui/settings_window.py) - MIN 718x921 - SHOT .claude/shots/SettingsWindow.png - GRADE 7/10 - audit: PASS
- SettingsWindow light (server/gui/settings_window.py) - MIN 718x921 - SHOT .claude/shots/SettingsWindow__light.png - GRADE 7/10 - audit: PASS
- Dictation card, dark (client/controls.js) - MIN 412x915 - SHOT .claude/shots/Dictation_card.png - GRADE 7/10 - audit: PASS
- Dictation card, light outlined (client/theme.css) - MIN 412x915 - SHOT .claude/shots/Dictation_card_light_transparent.png - GRADE 7/10 - audit: PASS
- Controls and wheel, colored outlined (client/controls.js, client/theme.js) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_colored_transparent.png - GRADE 7/10 - audit: PASS
- Controls and wheel, colored filled (client/controls.js, client/theme.js) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_colored_full.png - GRADE 7/10 - audit: PASS
- Controls and wheel, dark filled (client/theme.css) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_dark_full.png - GRADE 8/10 - audit: PASS
- Controls and wheel, light outlined (client/theme.css) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_light_transparent.png - GRADE 8/10 - audit: PASS
- Controls and wheel, light filled (client/theme.css) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_light_full.png - GRADE 8/10 - audit: PASS

## Independently confirmed, with the numbers behind them

These are grader 1's findings, reached again from scratch and now measured. They
are not opinions.

**The Traffic legend really cannot name its own two series.** Sampled at the
swatch centres: "PC to phone" is **(168,179,197)** and "phone to PC" is
**(168,179,197)** — byte-identical, and that value IS the caption text colour. On
light both are **(84,90,107)**. The chart plots cyan and orange (visible in the
15:34 hover shot). A legend of two identical grey squares in front of a
two-colour chart names the series and then refuses to say which is which.

**Every ControlsEditor text input really is invisible on light.** Scanned across
the whole field width, not spot-checked: the QLineEdit paints **(237,239,247)**
on a page of **(236,238,246)** — one unit per channel, in every field of the
window. The same field on dark is **(32,39,57)** on **(15,23,42)**, a 17-step
lift that plainly reads as a box. So on light the user sees the word "Claude" and
the hint "e.g. ctrl+shift+p" floating on bare page with nothing to click into,
and "Record…" reads as a button beside no field at all.

**The combo caret really is a square.** Zoomed: a solid **(168,179,197)** 10x10
block, no triangle, no arrow, in both palettes, in every combo of SettingsWindow,
TrafficWindow and ControlsEditor. Grader 1 named the cause (CSS border-triangles,
which Qt's subcontrol renderer does not do). Same class as the ✥ the owner
rejected on 2026-08-05 — a glyph that came out a blunt shape.

**The scrollbar-beside-a-hole really is the largest thing in the ControlsEditor.**
Ten of the Claude set's thirteen commands, a scrollbar, and roughly 480 px of
empty dark column beside it ending at "Explorer".

## What this block ADDS — three findings not in the block above

### A. Controls and wheel, COLORED: the D-pad labels are the dimmest text in the app

Measured on the "Click" label, brightest text pixel against its own background:

| look | background | label ink | contrast |
|------|-----------|-----------|----------|
| dark outlined (reference) | (16,24,43) | (119,124,134) | **4.22:1** |
| colored outlined | (16,24,43) | (33,98,135) | **2.66:1** |
| colored filled | (33,98,135) fill | (12,21,37) | **2.75:1** |
| colored filled, green set (Keys/Enter/Esc/Mic) | (41,113,81) | (12,20,37) | **3.13:1** |

These are ~13 px button labels; WCAG AA wants 4.5:1 and even the large-text floor
is 3:1. **Choosing the colored theme makes the SAME words measurably harder to
read than the plain dark theme does** — that is the opposite of what a theme
choice is for, and it is why I cannot leave this at grader 1's 9/8.

In the filled look the cause is visible: the button fill is a ~20 % tint of the
set colour, so over dark PC content it composites DARK, while the ink is still
the dark ink `inkFor` computed for the SOLID bright colour. The wheel proves the
ink rule works when the fill really is solid — the Mouse circle is cyan
(56,189,248) under dark ink at **8.74:1** and reads beautifully. It is the TINTED
D-pad fill the computation does not account for, and the owner's own screens
(VSCode, Claude Code) are exactly the dark case.

**Ladder rung: none — this is contrast, not space.** Either compute the ink
against the COMPOSITED fill, or keep the label in the set colour at a lightness
that clears 4.5:1 on the page.

### B. The Dictation card — two columns wrapping past each other, 7/10 both palettes

Ungraded by grader 1. Two of the three language rows break in BOTH columns at
once:

    ( ) Srpski              model will download — online until it
        (Srbija)                                            arrives
    ( ) English (United States)              ready on this phone
    ( ) Deutsch                       recognized over the
        (Deutschland)                            internet

"Srpski" is cut from its own "(Srbija)" while roughly **60 CSS px sit unused**
between the name column and the status column — the name column is fixed and will
not grow into the gap. The status is right-aligned, so its orphan second lines
("arrives", "internet") leave a wide hole to their left. And the card is not
short of room: about **225 CSS px of empty space stands ABOVE it**. This is the
law's own picture — a starving element beside a neighbour holding slack.

**Ladder rung 1, then 2.** Let the name take the free width beside it; if the
longest status still will not sit on one line, reflow — status onto its own line
under the language name, spending the vertical space standing idle above the card.

### C. SettingsWindow 7/10, not 8 — a raw Python exception IS the guidance text

Grader 1 marked the colour of this line (caption grey where DESIGN.md has a
semantic Error hue) and put the doubled backslashes down to fixture escaping.
That escaping point is fair and I cannot disprove it. What survives it is the
rest of the string, which is product, not fixture:

    [Errno 2] No such file or directory: 'C:\Program Files\Remote User\_internal\setup\agent_hook.py'

An `OSError` repr is standing in the slot where this window's plain-language
explanation goes, and the path it names is the INSTALLED path — so this is what
the owner sees on his own machine whenever the hook file is not where the app
looks. It tells him nothing he can act on. And because it sits BETWEEN two
checkboxes ("Tell my phone…" above, "Say it out loud" below) it reads at a glance
as if it belonged to the wrong one. Colour alone does not fix either half.

**Ladder rung 2 (reflow) for the placement** — indent or otherwise bind the
message to the checkbox it belongs to. The message itself is a copy fix: one
plain sentence saying what failed and what the user can do.

## The grid drawings — the owner's own question, answered a second time

His question was: can a landscape three and a portrait three be told apart AT A
GLANCE, without reading which chip is lit. **Yes** — same answer as grader 1, and
here is the measurement behind it. In the Shape row of Grid_arrangement_choice.png
the two chips sit side by side and the silhouettes do the work with no text:
Landscape draws a figure **~70x45 px** (one block left, two stacked bars right —
squat and wide), Portrait draws **~45x69 px** (one tall bar left, two blocks
right — narrow and tall). That is exactly the device his own sheet at
`UV/grid_variations.png` uses: the OUTER PROPORTION of the drawing, not its label.

Checked against the sheet in detail:

- The four arrangement chips are his four portrait-3 variants — single on TOP,
  single on BOTTOM, single on LEFT, single on RIGHT — and all four are drawn
  inside the same portrait outer proportion (measured 36x54, 36x56, 37x56,
  37x56 px). None is accidentally squat, so none can be mistaken for its
  landscape twin.
- The count chips are shape-aware: with Portrait chosen, "2" draws two STACKED
  bars (his portrait 2), "4" draws 2x2 (identical in both, as on his sheet), and
  "3" redraws to mirror whichever arrangement is selected.
- No word survives anywhere in the choice — "Where does the single window go?" is
  answered entirely in pictures, which was the point.

The one thing his sheet has that these chips do not is the drawn outer FRAME
around each variant; the chips rely on the block group's own proportion instead.
It works at this size. It is worth knowing that it is the only thing carrying it.

## What I could NOT grade — do not read these as passes

1. **The phone in LANDSCAPE — the whole surface.** Every phone shot on disk is
   824x1830, portrait. There is no landscape screenshot of any panel, so "does
   anything overflow in the other orientation" is unanswered for the entire phone
   client. Neither grader has looked at it.
2. **The four LANDSCAPE three-window arrangement chips.** No shot has Landscape
   selected. Both graders can prove a landscape three is distinguishable from a
   portrait three (the Shape row); neither can show that all four landscape
   variants are drawn the way his sheet draws them.
3. **The rebuilt Traffic window's hover card and its two long spans.** Refused by
   grader 1 as untrusted; refused here for a second, independent reason — the two
   hover shots are timestamped **15:34**, hours before the 18:02 build, and they
   still carry Serbian strings the current build no longer uses ("1 klijent
   povezan", "Sve (iz fajla)"), so they are stale evidence on their face. The two
   FRESH Traffic shots have an EMPTY chart: no line, no grey band, no hover card.
   The rebuild's headline features have no current picture at all.
4. **"MainWindow reopened from the tray" is not a second observation.**
   MainWindow.png and MainWindow__reopened_from_the_tray.png are BYTE-IDENTICAL
   (md5 12c59bd6ae08), as are their light pair (c72b15932b44). Four proof lines
   across this file, two pictures; the tray-reopen state was never captured as a
   distinct state.
5. **Controls_and_wheel_light_transparent.png changed on disk (94968 to 94731 B)
   after I opened it.** My 8/10 is on the bytes I saw; the change is 0.25 % of the
   file and the grade carries no blocking finding, so I did not re-open it.
   Stated rather than hidden.
6. **Whether the colored/filled look works over the owner's REAL screen.** The
   audit canvas is empty; round R3's caveat stands. It does not soften finding A:
   a button label's contrast against its OWN fill is measurable regardless of what
   is behind it, and the dark-content case is the owner's normal case.

## Where I looked hard and found nothing to add

MainWindow: the column reads top to bottom with no crowding, the three doors are
one row of equals, and grader 1's three deductions (the filled sun still reading
as a COG two rows above a real cog, the mixed stroke/solid icon weights, the
empty right half beside "Stop server") are all visible to me too. 8 is right.

WheelOrderDialog: the ring genuinely reads as a ring — drawn circle, eight dot
positions matching the wheel's cap of 8, "1" bold at 12 o'clock, one clockwise
accent arrow — and all thirteen names are visible with no scrollbar and no
elision. I would have given 8. Grader 1's specifics (the ordinals not
right-aligned so "10th"–"13th" push their names ~13 px right; the light list
having no card at all; the ring marooned in a mostly empty column) are each
things I can confirm once named, so its 7/6 stands over my 8.

Sets picker and Creation panel: agreed at 8, and for the same reasons — the
picker's "always in the wheel" rows are drawn identically to the tickable ones so
"5 of 8 used" cannot be reconciled by counting on screen, and the creation
panel's third chip still elides ("Claude Code - Remote User - V…") with that
window's full title appearing NOWHERE once the Name field has been retyped.

---

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
ROUND: FIXING THE SECOND GRADER'S THREE FINDINGS (2026-08-07) — phone only

I wrote this code, so **nothing below is a grade**: the coordinator sends these
shots to an independent grader, and a self-graded picture is not proof
(rules/GUI.md -> The Visual Proof). What follows is the EVIDENCE the grader
needs — what was changed, what it measures now, and which pictures were opened
with the Read tool in this session while doing it.

## Finding 1 — the `colored` theme's D-pad labels

The grader's cause ("the button's fill is a ~20 % tint that composites
dark-over-dark") is NOT what the CSS does: in `colored`/`full` the button is
painted with the solid set colour. Confirmed by opening both pictures — the
same "Click" label measures 8.09:1 with the wheel SHUT and measured 2.66:1 with
it OPEN. The veil was `#wheel`'s own background at z-index 35, above the D-pad
(20) and the corners (30). Under a 0.55 veil the contrast ACHIEVABLE between
the brightest and darkest possible pixels is 4.83:1, so no ink could have
answered it.

Two fixes, both measured off the shipped PNGs (brightest text pixel vs its own
background, the grader's own method):

| look, wheel OPEN | grader's before | now |
|---|---|---|
| dark outlined (reference) | 4.22:1 | **15.93:1** |
| colored outlined | 2.66:1 | **8.10:1** |
| colored filled | 2.75:1 | **8.75:1** |
| colored filled, green set | 3.13:1 | **10.83:1** |
| wheel item (was already fine) | 8.74:1 | 8.75:1 |

- the veil moved to `body.wheel-open::before`, z-index 10 — over the stream,
  under our own chrome (`client/style.css`);
- the ink is computed against the surface it actually sits on, per fill mode,
  from the LIVE tokens (`client/theme.js` -> `paintSet`/`lineOn`/`inkOn`):
  `--set-line` for outlined, `--set-ink` on `--set-fill` for filled. Six of the
  thirteen shipped colours are returned untouched; Edit's #A78BFA is lifted to
  #BDA8FB, 5.56:1 -> **7.34:1**, visible in the wheel shots.
- `.ctl.cat`'s `opacity: 0.85` is gone: it dimmed the set NAME to 3.35:1 dark /
  4.27:1 on a filled VSCode-blue button.

## Why the tooth missed it, and what it measures now

`__contrast` walked only DOWNWARD, through the element's own ancestors'
backgrounds, so a full-screen overlay painted ON TOP was invisible to it, and
it read `opacity` on the text leaf only. Now it composites (a) every visible
fixed full-viewport layer with a higher z-index, body's `::before` included,
and (b) every ancestor's opacity. Self-tested: putting the veil back on
`#wheel` turns the check RED at **2.64:1 outlined / 2.74:1 filled** — the
grader's own 2.66/2.75, reproduced by the machine. It also now sweeps ALL
thirteen `SET_COLORS` on both surfaces (`__sweepSetColours`), where the pinned
fixture only ever put three on screen, and it fails a card that SCROLLS while
free width stands beside it (BUG A of the law, stated in its own words).

## Finding 2 — the dictation card

`.sets-row.dict` was one flex line; both text boxes are shrinkable, so at 412 px
both wrapped at once. Rung 1 cannot fix it — the longest real pair is
"English (United States)" (~175 px at 600 15 px) plus "model will download —
online until it arrives" (~240 px at 12 px) for a ~328 px line. Rung 2: a
`20px 1fr` grid, radio spanning both rows, status under the name at full width.
Read as: **Srpski (Srbija)** whole on one line, "model will download — online
until it arrives" whole on the line under it, no orphan, no gap, nothing cut.

## Finding 3 — LANDSCAPE, photographed for the first time

Eighteen new landscape shots (`*_landscape.png`), and opening the first one
found a real defect immediately: every panel card kept its portrait
`min(420px, 100%)` inside a 915 px screen — 495 px of idle width — while `92vh`
fell to 379 px. **Seven of the ten panels scrolled**, up to 256 px, and the
creation panel's Create button was below the fold. Fixed at rungs 1+2 (see
client/__about/style.md); measured after: every panel fits, none scrolls, in
both orientations, and portrait is byte-for-byte the same layout as before.

Pictures OPENED with the Read tool in this session (the ones the findings and
the fixes rest on):

- .claude/shots/Controls_and_wheel_colored_transparent.png (before, the veil)
- .claude/shots/Controls_colored_transparent.png (before, wheel shut)
- .claude/shots/Dictation_card.png (before and after)
- .claude/shots/Controls_landscape.png
- .claude/shots/Controls_and_wheel_colored_full_landscape.png
- .claude/shots/Controls_and_wheel_light_full_landscape.png
- .claude/shots/Grid_arrangement_choice_landscape.png
- .claude/shots/Sets_picker_landscape.png
- .claude/shots/Dictation_card_landscape.png

The four LANDSCAPE three-window arrangement chips, which no picture had ever
shown, are in `Grid_arrangement_choice_landscape.png`: single-on-top,
single-on-bottom, single-on-left (lit) and single-on-right, all four drawn on
the WIDE outer box, beside a Shape row whose Landscape and Portrait chips
differ in outer proportion before any cell is read.

`tests/test_layout_audit.py` PASSES on port 8898 (checked free first — no other
session held it), in both orientations and all six looks.

---

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
ROUND: THE TWO WINDOWS BELOW THE GATE (2026-08-07) — ControlsEditor 6/5,
       WheelOrderDialog 7/6, fixed

Every line below was written after opening THAT file with the Read tool, and
every one of those files was written by a run of
`tests/test_layout_audit_qt.py` that THIS session started (18:54, both
palettes, all seven windows PASS). No picture here was graded from another
process's output.

- ControlsEditor (server/gui/controls_editor.py, controls_widgets.py, theme.py) - MIN 733x950 - SHOT .claude/shots/ControlsEditor.png - GRADE 8/10 - audit: PASS
- ControlsEditor light (server/gui/theme.py) - MIN 733x950 - SHOT .claude/shots/ControlsEditor__light.png - GRADE 8/10 - audit: PASS
- WheelOrderDialog (server/gui/controls_order.py) - MIN 377x592 - SHOT .claude/shots/WheelOrderDialog.png - GRADE 9/10 - audit: PASS
- WheelOrderDialog light (server/gui/controls_order.py, theme.py) - MIN 377x592 - SHOT .claude/shots/WheelOrderDialog__light.png - GRADE 9/10 - audit: PASS

## The findings, one by one, and what the picture shows now

**ControlsEditor 6/10 dark, 5/10 light -> 8/10 in both.**

1. **Three inputs invisible AS INPUTS on light — CONFIRMED and fixed.** The
   grader's measurement is exact: the set Name field's fill was one unit per
   channel off the page. `QLineEdit` had no QSS rule at all, so it fell through
   to the base `QWidget` rule and wore the page colour with whatever frame the
   native style drew — which on dark looks accidentally like a field and on
   light is literally the page. Same class as R3's disabled-button bug, third
   time. Fix: `fieldFill`/`fieldEdge` tokens (+ `fieldOff` for the disabled
   state). Sampled off the new light shot: the enabled command Name field is
   page (236,238,246) -> border (199,203,221) = `#C7CBDD` -> fill (255,255,255);
   a disabled field keeps the LINE and takes a fill a shade off the page,
   because it still carries a value the user must read.
2. **Set list and group boxes lost their containers on light — CONFIRMED and
   fixed.** Same cause one layer up: a `QGroupBox` and an item view are drawn
   by the native style, whose frame is a hairline that vanishes on a light
   page. Both are cards in the QSS now. The picture shows a white card under
   the set list and a real border on all three boxes.
3. **3 of 13 pool rows behind a scrollbar beside ~253 px of idle set list —
   CONFIRMED, and the REFLOW finally done.** The Arrangement box is a
   left-column box; "Wheel order" rides the New set / Delete row instead of
   costing 44 px of its own; and — the half that made the previous attempt
   fail — `_fit_set_list` now declares the list's HEIGHT as well as its width,
   so the window's minimum is the honest max of two columns that both state
   their need. `CommandTable.ROWS_SHOWN` 10 -> 13 on top of that (ladder step 3
   after step 2, not instead of it). Measured: 723x956 -> **733x950**, all
   fifteen list rows and all thirteen pool rows visible, no scrollbar
   anywhere, inside the declared 1280x1000 frame.
4. **Two accents — CONFIRMED and fixed.** The yellow was the WINDOWS system
   accent: Qt's windows11 style paints a selected item's fill and a left
   indicator bar in it, and the owner's system accent is gold. Sampled off the
   old shot at (198,211,101) dark / (190,190,71) light. `RowDelegate` takes the
   selection away from the style. Note for whoever meets this next: a single
   translucent `accentDim` fill was NOT enough — the native bar showed straight
   through the wash and still measured (197,210,101). Two fills: the card
   colour to erase, the wash to colour. The tall bars are gone from the new
   shots; what my colour sweep still finds is (220,165,104) subpixel fringing
   on blue text.
5. **Three tick affordances, and "off" invisible — CONFIRMED and fixed.** One
   drawn box now (`paint_check`), matched to the QSS checkbox, in three states:
   empty = off and switchable, solid accent = riding, accent wash + dim tick =
   riding and `required`. The pool table's column uses the same drawing through
   `CheckDelegate` (QSS reaches `QCheckBox::indicator` and nothing inside an
   item view). The QSS checkbox's own tick was ALSO wrong on light — dark ink
   on the deep accent, ~2.2:1, cropped and looked at — so `checkAsset` picks a
   per-palette file.
6. **Trailing ellipsis — CONFIRMED and fixed**, on "Wheel order" and on
   "Record" beside it: one window may not keep a convention the window next
   door retired in the same round.

**WheelOrderDialog 7/10 dark, 6/10 light -> 9/10 in both.**

1. **The marooned ring — CONFIRMED and fixed.** The ring and the caption say
   the same thing, one as a picture and one in words, so they ride ONE row at
   the top and the ladder takes the whole width: the hole is gone rather than
   filled. 404x572 -> **377x592**. (Moving it exposed a second defect the old
   layout hid: the "1" was drawn off a circle centred in the whole widget, so
   with the widget no longer stretched its label rect landed at y = -6 and the
   digit came out flat-topped. `WheelRing.LABEL` centres the circle under a
   label band.)
2. **The ladder did not line up — CONFIRMED and fixed.** `SlotDelegate` paints
   two columns, the slot name right-aligned in a column as wide as the widest
   in the model. In the new shot the separator dots form one straight edge from
   1st to 13th. The D-pad ladders inherit it.
3. **No card on light, invisible arrows — CONFIRMED and fixed** by the shared
   item-view QSS plus (4).
4. **The move buttons were font glyphs — CONFIRMED and fixed.** Drawn icons
   from the client's own set (`arrowu`/`arrowd`), cached per (name, ink) so a
   theme flip rebuilds them instead of keeping a picture in the old ink.
5. **OK was not primary — CONFIRMED and fixed** (`objectName("primary")`).

**Extra finding, handed to me mid-round: the combo caret was a solid BLOCK.**
Confirmed by sampling before touching anything — exactly 100 identical ink
pixels, (168,179,197) dark and (84,90,107) light, with no antialiased edge
anywhere, which a triangle cannot produce. The QSS built it from CSS border
triangles, a browser trick Qt's subcontrol renderer does not perform. It is a
drawn SVG now (`assets/caret.svg` + `caret-light.svg`), and the crops of the
new shots show an antialiased chevron in both palettes. This corrects EVERY
combo in the app — ControlsEditor, SettingsWindow and TrafficWindow — from one
rule in `theme.py`.

## The deductions I am keeping, not rounding away

- **ControlsEditor 8, not 9.** The right column is now the SHORTER of the two,
  so its stretch lands in the pool table: ~124 px of empty grid under the last
  command. It hides nothing and sits directly above that table's own "Add
  command" button, but it is visible, and it is the price of showing all
  fifteen set rows without a scrollbar. Balancing it exactly would mean
  scrolling the set list at the minimum size, and the ladder puts a raised
  minimum above a scrollbar. Second, smaller: the Arrangement box's two
  ladders have different natural widths, so their cards do not share an edge.
- **WheelOrderDialog 9, not 10.** ~10 px of band under the last ladder row
  (it was 46 before the minimum was re-measured), and the ring is a legend
  rather than a live picture of the order — deliberate, and stated in its own
  docs.

## The tooth that could not see finding 3

`tests/test_layout_audit_qt.py` reported PASS over that window for two grading
rounds. Its SCROLL+SLACK check counted only `QSpacerItem`s, and only on the
path from the scrolling widget up to the window — while this slack was a
stretched SIBLING in the other column. `idle_view_slack` measures every item
view's viewport against its own rows.

Self-tested rather than asserted: a probe rebuilds the pre-round layout
(Arrangement back in the right column, the set list declaring no height, ten
pool rows, the window back at 723x956) and the audit now fails it —

    SCROLL+SLACK CommandTable '-' scrolls vertically while the same window
    holds unused space: QListWidget'-' is stretched to 936px for 580px of
    rows - 356px standing idle

— while the shipped layout reports none. Honest limit, written into the
function: it sees ITEM VIEWS, not every stretched widget. A generic
"size minus sizeHint" sweep convicts every legitimately stretched container in
the tree, and a check that cries wolf gets deleted.

---

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
ROUND: THIRD INDEPENDENT VISUAL GRADE (2026-08-07, 19:03-19:30) — the round
       that re-measures the twelve fixed screens and looks where nobody looked

I wrote none of this code and edited no source file. Unlike the second grader I
did NOT trust the pictures on disk: I re-ran `tests/test_layout_audit_qt.py`
(7 windows x dark+light, all PASS) and `tests/test_layout_audit.py` (phone,
portrait + landscape, all six looks, PASS) myself at 19:03, and I produced the
four TrafficWindow hover shots with my own offscreen script because no
committed entry point writes them. Every picture I grade below was written by
this session and opened with the Read tool afterwards.

**A collision worth recording.** My first run of the Qt audit at 19:02 died on
`ImportError: cannot import name 'HOOK_FAILED_TEXT' from 'gui.settings_window'`
— `server/gui/settings_window.py` had a modification time of 19:02:22, seconds
old, and the constant had just moved to `notify.HOOK_CHANGE_FAILED_TEXT` while
`tests/test_layout_audit_qt.py` (18:57) still imported the old name. Another
session was writing source while I graded. The retry a few seconds later ran
clean, so my shots are of a consistent tree — but a grade is only ever a grade
of the bytes that were there, and for ninety seconds this project's own audit
could not be started at all.

## The table — my own numbers, from my own pictures

| Screen | grader 1 | grader 2 | me (3) |
|---|---|---|---|
| MainWindow, dark / light | 8 / 8 | 9 / 8 | **8 / 8** |
| SettingsWindow, dark / light | 8 / 8 | 7 / 7 | **9 / 9** |
| TrafficWindow, dark / light | 6 / 6 | 7 / 7 | **9 / 9** |
| TrafficWindow hover + right-edge flip (mine) | refused | refused | **9** |
| ControlsEditor, dark / light | 6 / 5 | 7 / 5 | **8 / 8** |
| WheelOrderDialog, dark / light | 7 / 6 | 8 / 8 | **9 / 9** |
| Controls + wheel, dark outlined | 9 | 9 | **9** |
| Controls + wheel, colored outlined / filled | 9 / 8 | 7 / 7 | **9 / 9** |
| Controls + wheel, light outlined / filled | — | 8 / 8 | **8 / 8** |
| Controls, light: fill axis | 7 | — | **8** |
| **Controls, DARK: fill axis (wheel shut)** | — | — | **5** |
| Dictation card, dark / light | — | 7 / 7 | **9 / 9** |
| Sets picker | 8 | 9 | **8** |
| Quality panel | 8 | — | **9** |
| Creation panel — the count/shape drawings | 8 | 8 | **8** |
| Grid arrangement — the four drawings | 9 | 9 | **9** |
| **Grid arrangement — the chosen-window chip** | — | noted at 8 | **6** |
| **Landscape three-window variants** | ungraded | ungraded | **6** (same chip) |
| Layout list / Rename card / Aspect panel | 9 / 9 / 9 | — | **9 / 9 / 9** |
| **Region grab** | never opened | never opened | **6** |
| Controls, LANDSCAPE | ungraded | ungraded | **9** |

Proof lines for what I re-measured and for the three below the gate:

- MainWindow (server/gui/main_window.py) - MIN 463x685 - SHOT .claude/shots/MainWindow.png - GRADE 8/10 - audit: PASS
- MainWindow light (server/gui/theme.py) - MIN 463x685 - SHOT .claude/shots/MainWindow__light.png - GRADE 8/10 - audit: PASS
- SettingsWindow (server/gui/settings_window.py) - MIN 718x943 - SHOT .claude/shots/SettingsWindow.png - GRADE 9/10 - audit: PASS
- SettingsWindow light (server/gui/settings_window.py) - MIN 718x943 - SHOT .claude/shots/SettingsWindow__light.png - GRADE 9/10 - audit: PASS
- TrafficWindow (server/gui/traffic_window.py) - MIN 635x558 - SHOT .claude/shots/TrafficWindow.png - GRADE 9/10 - audit: PASS
- TrafficWindow light (server/gui/traffic_window.py) - MIN 635x558 - SHOT .claude/shots/TrafficWindow__light.png - GRADE 9/10 - audit: PASS
- TrafficWindow hover, REAL varying data, generated by this grader - MIN 635x558 - SHOT .claude/shots/TrafficWindow_hover.png - GRADE 9/10
- TrafficWindow hover at the right edge, card flip - MIN 635x558 - SHOT .claude/shots/TrafficWindow_hover_edge__light.png - GRADE 9/10
- ControlsEditor (server/gui/controls_editor.py) - MIN 733x950 - SHOT .claude/shots/ControlsEditor.png - GRADE 8/10 - audit: PASS
- ControlsEditor light (server/gui/theme.py) - MIN 733x950 - SHOT .claude/shots/ControlsEditor__light.png - GRADE 8/10 - audit: PASS
- WheelOrderDialog (server/gui/controls_order.py) - MIN 377x592 - SHOT .claude/shots/WheelOrderDialog.png - GRADE 9/10 - audit: PASS
- WheelOrderDialog light (server/gui/controls_order.py) - MIN 377x592 - SHOT .claude/shots/WheelOrderDialog__light.png - GRADE 9/10 - audit: PASS
- Controls, DARK FILLED, wheel shut (client/theme.css, client/connection.js) - MIN 412x915 - SHOT .claude/shots/Controls_dark_full.png - GRADE 5/10 - audit: PASS (and that is the problem — see finding A)
- Creation panel, chosen-window chip (client/layouts.js) - MIN 412x915 - SHOT .claude/shots/Grid_arrangement_choice.png - GRADE 6/10 - audit: PASS (see finding B)
- Region grab (client/controls.js, client/style.css) - MIN 412x915 - SHOT .claude/shots/Region_grab.png - GRADE 6/10 - audit: PASS (see finding C)
- Controls, LANDSCAPE (client/style.css) - MIN 915x412 - SHOT .claude/shots/Controls_landscape.png - GRADE 9/10 - audit: PASS

## The ten fixed defects, each re-measured by me

1. **Traffic legend swatches.** Sampled at the swatch centres of my own shots:
   dark (56,189,248) vs (245,158,11); light (3,105,161) vs (180,83,9); the
   nobody-connected band a third value, (63,72,90) / (189,192,202). No longer
   byte-identical, no longer the caption colour. **FIXED.**
2. **ControlsEditor light inputs.** Scanned across a whole field row: page
   (236,238,246) then a 2 px border (199,203,221) then fill (247,248,252). The
   implementer's note says the fill is white; it is #F7F8FC, eight units short
   of that. The substance holds — the box reads as a box, where it was one unit
   off the page. **FIXED** (with the claim corrected).
3. **Combo caret.** A 60x60 crop around the Icon combo holds **100 distinct
   non-background colours** on dark and **87** on light — antialiasing a solid
   block cannot produce, and the chevron is visible by eye. Checked in
   ControlsEditor, and the same `theme.py` rule serves SettingsWindow and
   TrafficWindow, both of whose combos I opened. **FIXED.**
4. **ControlsEditor scroll-beside-a-hole.** 733x950; all fifteen set rows and
   all thirteen pool rows on screen; no scrollbar anywhere. **FIXED** — and I
   did not take the new tooth on faith: I built the pattern myself (a
   `QTableWidget` capped to 240 px beside a stretched `QListWidget`) and ran
   `audit()` over it. It convicted: *"SCROLL+SLACK QTableWidget 'commands'
   scrolls vertically while the same window holds unused space: QListWidget
   'setlist' is stretched to 874px for 180px of rows — 694px standing idle"*,
   and reported nothing once the scrollbar was removed. The tooth bites.
5. **WheelOrderDialog.** 377x592, ring beside the caption, one straight edge of
   separator dots from 1st to 13th, a real white card on light, drawn arrows,
   OK primary. **FIXED.**
6. **SettingsWindow's raw OSError.** Gone. The slot now reads *"This PC has no
   Python on PATH, and Claude Code's hooks need one to run the notifier.
   Install Python and switch this on again."* in the semantic error red, and it
   is INDENTED under "Tell my phone when an agent finishes" — both halves of the
   second grader's finding, the wording and the misbinding. **FIXED.**
7. **Colored-theme contrast.** My own measurements, same method as grader 2
   (brightest text pixel against its own background):

   | look | before | now |
   |---|---|---|
   | dark outlined (reference) | 4.22:1 | **15.93:1** |
   | colored outlined, Click | 2.66:1 | **8.10:1** |
   | colored filled, Click | 2.75:1 | **8.74:1** |
   | colored, green set (Keys) | 3.13:1 | 9.95:1 outlined / **10.74:1** filled |

   Every shipped colour I sampled clears WCAG AA by better than three times.
   **FIXED.**
8. **Light fill axis.** `Controls_light_transparent.png` and
   `Controls_light_full.png` differ on **8.49%** of the frame; the button fill
   moves (238,240,247) to (255,255,255) and the border (191,192,200) to
   (204,204,206). **FIXED**, though weakly: on a near-white page "filled" reads
   as a border change more than as paint.
9. **Dictation card.** "Srpski (Srbija)" whole on one line, "model will
   download — online until it arrives" whole on the line beneath, radio
   spanning both rows. No orphan, no 60 px gap, nothing cut. **FIXED.**
10. **Emoji among drawn icons.** A drawn globe beside "Use from anywhere", a
    drawn eye-slash on Hide, a drawn cross on the wheel's cancel, drawn
    up/down arrows in the dialog and the editor, a drawn four-way move handle
    in the aspect panel. **FIXED.**

## Finding A — the DARK theme's fill axis is dead, and the default theme is where it hides

`Controls.png` (dark/outlined) and `Controls_dark_full.png` (dark/filled) are
**byte-identical over the entire control surface**: maximum per-channel
difference **0** across the left D-pad column, the right D-pad column, the
Layout button and the Hide button. The Click button is the same 6,039 pixels of
rgb(18,26,45) in both — the 0.20-alpha composite, never the solid #1e293b the
filled look is supposed to paint. The only two bands that differ anywhere in
the frame are the status pill (rows 164-233) and the anywhere banner (rows
1686-1797), both in the centre column.

The CSS is innocent. I loaded `theme.css` + `style.css` into a bare page and
read the computed value in all six looks: `body[data-fill="full"]` resolves
`.ctl` to rgb(30,41,59) on dark and rgb(255,255,255) on light, exactly as
written. So I probed the LIVE page instead, through the app's own `applyUi`:

    AFTER applyUi dark/full   -> data-fill=full          .ctl = rgb(30, 41, 59)
      wheel OPEN              -> data-fill=TRANSPARENT    .ctl = rgba(30, 41, 59, 0.2)
    AFTER applyUi light/full  -> data-fill=full           .ctl = rgb(255, 255, 255)
      wheel OPEN              -> data-fill=full           .ctl = rgb(255, 255, 255)

The dark look loses its fill within half a second; the light one does not. The
mechanism is `client/connection.js:78` — `applyUi(msg.ui || null)` on every
`config` frame — over `client/theme.js:299`, where every missing field falls
back to `UI_DEFAULT = {theme:"dark", fill:"transparent"}`. A `config` that
carries no `ui` therefore does not leave the look alone; it **resets it to
dark/outlined**. On light or colored that reset is loud, and the audit's later
looks survive because the fixture's `config` has already landed. On dark it is
silent, because the thing it resets to IS the dark theme.

Two things must change. The product: a `config` frame with no `ui` must not
overwrite a look the desktop already chose — merge, or ignore. The tooth:
`tests/test_layout_audit.py` asks for a look and then shoots without ever
checking that `body.dataset.fill` still holds it, which is how a screenshot
named `_dark_full` came to be a picture of the outlined look. One assertion
between `_apply_look` and `page.screenshot` closes it.

I graded `Controls_and_wheel_dark_full.png` separately at 8: that one WAS shot
while the fill still held (its Click button measures solid rgb(30,41,59)), so
the dark filled look does exist — it simply is not what the wheel-shut picture
shows.

## Finding B — a window title is truncated by a hard character cap, in both orientations

THE SPACE & LEGIBILITY LAW: *"Ellipsis or truncation on content the user must
read — a shortcut, a **name**, a value, a path"* — never, in any situation.

In `Grid_arrangement_choice.png` the third chosen-window chip reads **"Claude
Code - Remote User - V…"**. The chip ends at x=523 while the Name field
directly beneath it runs to x=748: **225 device px of free width standing idle
on the same row**. In `Grid_arrangement_choice_landscape.png` the same chip
ends at x=645 against a column that runs to x=893 — **248 device px idle**. And
because the Name field has been retyped to "Chrome", that window's full title
appears **nowhere on the screen**: three chips, and the one that needs
distinguishing is the one that is cut.

Both earlier graders saw this by eye and neither could say why the machine
missed it. It is `client/layouts.js:790`:

    layChip(s.title.length > 30 ? s.title.slice(0, 29) + "…" : s.title, ...)

The cut happens in JavaScript, by **character count**, before the DOM ever sees
the string — so `scrollWidth === clientWidth`, and the phone audit's only clip
test (`el.scrollWidth > el.clientWidth + 2`) is structurally incapable of
firing on it. That is why three rounds of PASS sit over a defect two humans
pointed at. It is also a fixed size on a widget that carries text, which the
law names outright: it cannot grow into the 225 px beside it, cannot respond to
landscape's extra room, and cannot wrap.

**Ladder rung 1, then 2:** delete the character cap, let the chip take the free
width, and wrap to a second line when the longest real title still will not
fit — exactly what the Layout list already does three lines lower down the same
file, where the same title wraps over three lines and reads whole.

## Finding C — the Region grab panel, which no grader had ever opened

`Region_grab.png` is a shipped phone surface with no grade in any round of this
file. Opening it found two defects at once.

    ┌──────────────┐                              <- the grab frame's DEFAULT
    │ ✥  Layou     │   <- the frame opens ON the     position is the top-left
    └──────────────┘      Layout button and cuts     corner, over our own chrome
                          its label to "Layou"

           …~1100 device px of empty canvas…

      ┌──────────────────────────────────────┐
      │ Drag the                             │   <- four lines for four words,
      │ corners,     ( Send )   ( ✕ )        │      in a pill with 59 device px
      │ then                                 │      of free width on EACH side
      │ Send                                 │
      └──────────────────────────────────────┘

The instruction's text column is squeezed to roughly 100 device px while its
own row holds ~118 device px of unused width and the canvas above it is
entirely empty. Rung 1 (grow into the free space) and rung 2 (put the sentence
on its own line above the buttons) are both available and both untaken — this
is BUG B of the law drawn in the law's own shape. Separately, the frame's
default placement collides with the Layout button and clips its label, which
means the first thing the user sees when they open the tool is a piece of our
own chrome cut in half.

## What I could NOT grade — do not read these as passes

1. **Nine phone shots dated 18:07** — `Creation_panel___Name_field`,
   `Grid_arrangement_choice` and `Layout_list_with_rename` in
   `colored_full` / `light_full` / `light_transparent`. Written by another
   process, and `tests/test_layout_audit.py` shoots only Sets picker / Quality
   panel / Dictation card in non-default looks, so no committed entry point
   regenerates them. Refused.
2. **`SettingsWindow_notify_healthy(.__light)`, 18:41** — same reason.
3. **ChordRecorder — no picture at all**, third round running. The Qt audit
   writes no shot below 40,000 px², and its minimum is 232x68.
4. **`MainWindow.png` and `MainWindow__reopened_from_the_tray.png` are STILL
   byte-identical** (md5 12c59bd6ae08; light pair c72b15932b44) — the same
   hashes the second grader reported, unchanged. Four proof lines across this
   file, two pictures. The tray-reopen state has never been captured as a
   distinct state.
5. **My own hover shots' header counters.** My synthetic data feeds the CHART;
   the meter's own totals still read the fixture's zeros, so the header lines
   in `TrafficWindow_hover*.png` prove nothing about live counters. The chart,
   the band, the hairlines, the crosshair and the card are real and graded.

## Deductions I am keeping rather than rounding away

- **ControlsEditor 8, not 9.** ~250 device px of empty grid under the last
  command row, and the Arrangement box's two ladder cards do not share a right
  edge. Both are the honest price of showing everything without a scrollbar.
- **MainWindow 8, not 9.** "Stop server" sits alone in a row with ~670 device
  px of empty width to its right, and the three-step pairing list is
  CENTRE-aligned, so its "1." "2." "3." do not form a column.
- **Sets picker 8, not 9.** The always-in-the-wheel rows (Mouse, Input) carry
  exactly the same solid tick as the optional ones, so "5 of 8 used" cannot be
  reconciled by looking. The desktop editor learned to distinguish required
  from optional in this very round; the phone picker did not.
- **Quality panel 9, not 10.** With the PC at 10 fps the "10" step is struck
  through, so the panel says the PC's own value is out of reach.


---

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
ROUND: FINAL INDEPENDENT GRADE (2026-08-07) — grader 3, re-grading the twelve
       entries that were below 8, plus the eighteen landscape shots nobody had
       ever looked at

I wrote none of this code and I graded nothing from memory or from another
agent's word. Every line below was written after opening THAT file with the
Read tool, and every claim a number could settle was MEASURED with Pillow
pixel sampling and WCAG contrast rather than asserted. I did NOT re-run the
audits: `.claude/shots/` was written at 19:03 (phone) and 19:10 (desktop),
AFTER the last edit to any file they render (client/* stops at 18:50:54,
server/gui/* at 19:02:22), so the bytes on disk show the shipped code — and
re-running would have rewritten the very evidence mid-grade, which is the
failure the previous two rounds recorded twice.

`.claude/layout-frame.json` — CHECKED, as asked. `floor_width` 1280 and
`floor_height` 1000 are UNCHANGED against HEAD; only the `reason` prose was
rewritten (in build round R2, not by the ControlsEditor fix). Every window
measured below is inside that frame. One inaccuracy to hand back: the new
reason text quotes ControlsEditor at 723x956 and Settings at 644x874, and the
shipped windows now measure 733x950 and 718x943.

## Desktop — dark

- MainWindow (server/gui/main_window.py) - MIN 463x685 - SHOT .claude/shots/MainWindow.png - GRADE 8/10 - audit: PASS
- MainWindow reopened from the tray (server/gui/main_window.py) - MIN 463x685 - SHOT .claude/shots/MainWindow__reopened_from_the_tray.png - GRADE 8/10 - audit: PASS
- SettingsWindow (server/gui/settings_window.py) - MIN 718x943 - SHOT .claude/shots/SettingsWindow.png - GRADE 8/10 - audit: PASS
- TrafficWindow (server/gui/traffic_window.py) - MIN 635x558 - SHOT .claude/shots/TrafficWindow.png - GRADE 9/10 - audit: PASS
- ControlsEditor (server/gui/controls_editor.py, controls_widgets.py, theme.py) - MIN 733x950 - SHOT .claude/shots/ControlsEditor.png - GRADE 8/10 - audit: PASS
- WheelOrderDialog (server/gui/controls_order.py) - MIN 377x592 - SHOT .claude/shots/WheelOrderDialog.png - GRADE 9/10 - audit: PASS
- TrafficWindow, hover state with real data (server/gui/traffic_window.py) - MIN 635x558 - SHOT .claude/shots/TrafficWindow_hover.png - GRADE 8/10 - audit: PASS

## Desktop — light

- MainWindow light (server/gui/theme.py) - MIN 463x685 - SHOT .claude/shots/MainWindow__light.png - GRADE 8/10 - audit: PASS
- MainWindow reopened light (server/gui/theme.py) - MIN 463x685 - SHOT .claude/shots/MainWindow__reopened_from_the_tray__light.png - GRADE 8/10 - audit: PASS
- SettingsWindow light (server/gui/settings_window.py) - MIN 718x943 - SHOT .claude/shots/SettingsWindow__light.png - GRADE 8/10 - audit: PASS
- TrafficWindow light (server/gui/traffic_window.py) - MIN 635x558 - SHOT .claude/shots/TrafficWindow__light.png - GRADE 9/10 - audit: PASS
- ControlsEditor light (server/gui/theme.py) - MIN 733x950 - SHOT .claude/shots/ControlsEditor__light.png - GRADE 8/10 - audit: PASS
- WheelOrderDialog light (server/gui/controls_order.py, theme.py) - MIN 377x592 - SHOT .claude/shots/WheelOrderDialog__light.png - GRADE 9/10 - audit: PASS
- ChordRecorder - MIN 232x68 - SHOT none (the Qt audit writes no picture under 40,000 px^2) - GRADE ungraded, NOT passed - audit: PASS

## Phone — portrait

- Controls and wheel, dark outlined (client/style.css, client/theme.js) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel.png - GRADE 9/10 - audit: PASS
- Controls and wheel, dark filled (client/theme.css) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_dark_full.png - GRADE 8/10 - audit: PASS
- Controls, light outlined (client/theme.css) - MIN 412x915 - SHOT .claude/shots/Controls_light_transparent.png - GRADE 8/10 - audit: PASS
- Controls, light filled (client/theme.css) - MIN 412x915 - SHOT .claude/shots/Controls_light_full.png - GRADE 8/10 - audit: PASS
- Controls and wheel, light outlined (client/theme.css) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_light_transparent.png - GRADE 8/10 - audit: PASS
- Controls and wheel, colored outlined (client/theme.js, client/style.css) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_colored_transparent.png - GRADE 8/10 - audit: PASS
- Controls and wheel, colored filled (client/theme.js, client/style.css) - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel_colored_full.png - GRADE 8/10 - audit: PASS
- Dictation card, dark outlined (client/controls.js, client/style.css) - MIN 412x915 - SHOT .claude/shots/Dictation_card.png - GRADE 8/10 - audit: PASS
- Dictation card, light outlined (client/style.css) - MIN 412x915 - SHOT .claude/shots/Dictation_card_light_transparent.png - GRADE 9/10 - audit: PASS
- Sets picker, dark outlined (client/sets.js) - MIN 412x915 - SHOT .claude/shots/Sets_picker.png - GRADE 8/10 - audit: PASS
- Quality panel, dark outlined (client/controls.js) - MIN 412x915 - SHOT .claude/shots/Quality_panel.png - GRADE 8/10 - audit: PASS
- Layout list (client/layouts.js, layouts.css) - MIN 412x915 - SHOT .claude/shots/Layout_list_with_rename.png - GRADE 9/10 - audit: PASS
- Grid arrangement choice (client/grids.js, client/layouts.js) - MIN 412x915 - SHOT .claude/shots/Grid_arrangement_choice.png - GRADE 7/10 - audit: PASS
- Creation panel + Name field (client/layouts.js) - MIN 412x915 - SHOT .claude/shots/Creation_panel___Name_field.png - GRADE 7/10 - audit: PASS
- Region grab (client/controls.js, client/style.css) - MIN 412x915 - SHOT .claude/shots/Region_grab.png - GRADE 6/10 - audit: PASS

## Phone — LANDSCAPE (first grade this surface has ever had)

- Controls, dark outlined, landscape (client/style.css) - MIN 915x412 - SHOT .claude/shots/Controls_landscape.png - GRADE 9/10 - audit: PASS
- Controls and wheel, dark outlined, landscape (client/style.css) - MIN 915x412 - SHOT .claude/shots/Controls_and_wheel_landscape.png - GRADE 7/10 - audit: PASS
- Controls, dark filled, landscape - MIN 915x412 - SHOT .claude/shots/Controls_dark_full_landscape.png - GRADE 9/10 - audit: PASS
- Controls and wheel, dark filled, landscape - MIN 915x412 - SHOT .claude/shots/Controls_and_wheel_dark_full_landscape.png - GRADE 9/10 - audit: PASS
- Controls, light outlined, landscape - MIN 915x412 - SHOT .claude/shots/Controls_light_transparent_landscape.png - GRADE ungraded, NOT passed (the file shows the DARK palette) - audit: PASS
- Controls and wheel, light outlined, landscape - MIN 915x412 - SHOT .claude/shots/Controls_and_wheel_light_transparent_landscape.png - GRADE 8/10 - audit: PASS
- Controls, light filled, landscape - MIN 915x412 - SHOT .claude/shots/Controls_light_full_landscape.png - GRADE 9/10 - audit: PASS
- Controls and wheel, light filled, landscape - MIN 915x412 - SHOT .claude/shots/Controls_and_wheel_light_full_landscape.png - GRADE 9/10 - audit: PASS
- Controls, colored outlined, landscape - MIN 915x412 - SHOT .claude/shots/Controls_colored_transparent_landscape.png - GRADE 9/10 - audit: PASS
- Controls and wheel, colored outlined, landscape - MIN 915x412 - SHOT .claude/shots/Controls_and_wheel_colored_transparent_landscape.png - GRADE 9/10 - audit: PASS
- Controls, colored filled, landscape - MIN 915x412 - SHOT .claude/shots/Controls_colored_full_landscape.png - GRADE 9/10 - audit: PASS
- Controls and wheel, colored filled, landscape - MIN 915x412 - SHOT .claude/shots/Controls_and_wheel_colored_full_landscape.png - GRADE 9/10 - audit: PASS
- Layout list, landscape (client/style.css, client/layouts.css) - MIN 915x412 - SHOT .claude/shots/Layout_list_with_rename_landscape.png - GRADE 8/10 - audit: PASS
- Sets picker, landscape (client/style.css) - MIN 915x412 - SHOT .claude/shots/Sets_picker_landscape.png - GRADE 8/10 - audit: PASS
- Quality panel, landscape (client/style.css) - MIN 915x412 - SHOT .claude/shots/Quality_panel_landscape.png - GRADE 8/10 - audit: PASS
- Dictation card, landscape (client/style.css) - MIN 915x412 - SHOT .claude/shots/Dictation_card_landscape.png - GRADE 8/10 - audit: PASS
- Grid arrangement choice, landscape (client/grids.js, client/layouts.js) - MIN 915x412 - SHOT .claude/shots/Grid_arrangement_choice_landscape.png - GRADE 7/10 - audit: PASS
- Creation panel + Name field, landscape (client/layouts.js) - MIN 915x412 - SHOT .claude/shots/Creation_panel___Name_field_landscape.png - GRADE 7/10 - audit: PASS

## Every fixer claim, verified against my own pixels

**The ControlsEditor's invisible inputs — FIXED, and the numbers are exactly
what was claimed.** Sampled across the field, not spot-checked, and at the
EDGES as well as the centre, in both palettes:

| field | palette | page | border | fill |
|---|---|---|---|---|
| set Name (disabled, built-in set) | light | (236,238,246) | (199,203,221) = #C7CBDD, 2 device px both sides | (247,248,252) |
| set Name (disabled) | dark | (15,23,42) | (65,75,90) | (30,41,59) |
| command Name (enabled) | light | (236,238,246) | — | (255,255,255) |
| command Name (enabled) | dark | (15,23,42) | — | (39,52,73) |
| Shortcut (disabled) | light / dark | — | — | (247,248,252) / (30,41,59) |

The previous grade's measurement was (237,239,247) on (236,238,246) — one unit
per channel, no border. That state is gone. The `fieldOff` distinction is real
and it is the right call: the disabled field keeps its LINE and takes a fill
one step off the page, so a value the user must read still sits in a box, while
a disabled BUTTON recedes. Border-to-page contrast on light is 1.393:1 — thin,
but it is a drawn line at full opacity and it reads as an edge.

**The combo caret — FIXED.** I cropped it out of both palettes and enlarged it
8x with nearest-neighbour, which is the only way to tell a drawn mark from a
block. It is an antialiased chevron: 97 distinct colours in a 60x55 box on
light, 110 on dark, against the old finding of exactly 100 identical ink pixels
with no antialiased edge. `assets/caret.svg` strokes #A8B3C5 and
`caret-light.svg` strokes #545A6B — each palette's own `text2`, so neither
file is the wrong colour for the palette that loads it. Both files exist.

**Ten of thirteen behind a scrollbar — FIXED, and the frame was not touched.**
All THIRTEEN Claude commands are on screen (Usage, Model, Thinking, Stop, Menu,
Mode, Compact, New chat, Rewind, Context, Agents, Resume, Focus). No scrollbar:
the table's right edge at x=1396-1398 is its border, and the 500 px column
beside it holds two colours only. The set list's old ~253 px hole is gone — its
last row ends at y=1200 and its card at y=1236, 36 device px = 18 CSS px of
slack. Arrangement is in the left column, "Wheel order" rides the New set /
Delete row, and the trailing ellipses are gone from both it and "Record".

**The SettingsWindow exception text — FIXED, everywhere, not just on screen.**
The slot now reads "This PC has no Python on PATH, and Claude Code's hooks need
one to run the notifier. Install Python and switch this on again." — indented
to its own checkbox's label with a gap before "Say it out loud", in the error
hue. I checked the code as well as the picture: `_toggle_agent_hook` shows
`str(e)` ONLY when `e.errno is None` (an OSError raised by hand, already
written for a person) and otherwise substitutes `notify.HOOK_CHANGE_FAILED_TEXT`;
all four authored sentences in notify.py carry no path, no errno and no repr.
No path, errno or exception text survives anywhere in that window.

**WheelOrderDialog — FIXED on all five findings.** The ring rides the caption's
row so the dead column is gone rather than filled (404x572 -> 377x592); the
ordinals are right-aligned, and the separator dots form one straight edge from
1st to 13th; the list is a white card with a border on light; the move buttons
are drawn `arrowu`/`arrowd` icons; OK carries the accent and Cancel does not.

**The colored theme's D-pad labels — FIXED, measured WITH THE WHEEL OPEN,
which is the state that failed.** Brightest text pixel against its own
background, the previous grader's own method, on the "Click" (Mouse set) and
"Mic" (Input set) labels:

| look, wheel OPEN | before | now (portrait) | now (landscape) |
|---|---|---|---|
| dark outlined | 4.22:1 | **15.93:1** | 15.93:1 |
| colored outlined, blue set | 2.66:1 | **8.10:1** | 8.10:1 |
| colored filled, blue set | 2.75:1 | **8.75:1** | 8.75:1 |
| colored filled, green set | 3.13:1 | **10.77:1** | 10.77:1 |
| colored outlined, green set | — | 9.96:1 | 9.96:1 |
| dark filled | — | 13.42:1 | 13.42:1 |
| light outlined | — | 8.70:1 | 8.70:1 |
| light filled | — | 17.97:1 | 17.97:1 |

The claimed 8.10 / 8.75 are exact; the green set measures 10.77 where 10.83 was
claimed, which is the same finding. Choosing the colored theme no longer costs
legibility in any look, in either orientation.

**The dictation card — FIXED.** "Srpski (Srbija)" is whole on one line and
"model will download — online until it arrives" whole on the line under it. No
orphan, no gap between a fixed name column and a right-aligned status, nothing
cut, in both palettes.

**The light fill axis, which grader 1 failed at 7/10 — FIXED, and this one is
a picture that genuinely changed.** On light the outlined button now fills
(238,240,247) against a page of (236,238,246) and keeps a (191,192,200) border;
the filled button fills (255,255,255) with a (204,204,206) border. 129,807
pixels differ by more than 8 between the two shots. It is a quiet difference —
1.16:1 of fill against the page — but the axis is no longer a no-op, and the
"Use from anywhere" pill's globe is a stroked SVG in the accent, not an emoji.

**The TrafficWindow, which had only ever been graded by the agent that fixed
it — CONFIRMED at 9 by me.** The legend swatches are drawn in the series' own
live colours: most-saturated pixel (56,189,248) vs (245,158,11) on dark,
(3,105,161) vs (180,83,9) on light, against the previous finding of
byte-identical (168,179,197) for both. Legend is a 2x2 grid of atomic items
with the explanation on its own line; every string is English; "Recording to
file" is a coloured dot and a readout, not a dead tick; the plot fills with
`surface1` and reads as a panel in both palettes.

## BELOW THE GATE — the three things that still block, precisely

### 1. The chosen-window chip is ELIDED beside measured free width — 7/10
`.claude/shots/Grid_arrangement_choice.png`,
`Creation_panel___Name_field.png`, and both `*_landscape.png` twins.

What a person sees: the third chip reads "Claude Code - Remote User - V…", and
because the Name field beside it has been retyped to "Chrome", that window's
full title appears NOWHERE on the screen. Measured: in PORTRAIT the chip ends
at x=523 while the card's content column runs to x=748 — 225 device px = **112
CSS px of unused width in the chip's own row**. In LANDSCAPE the chip ends at
x=645 in a column that runs to x=893 — **124 CSS px unused**.

The cause is a hard character cap, not a layout: `client/layouts.js:791`
truncates at 30 characters (`s.title.length > 30 ? s.title.slice(0, 29) + "…"`),
which is width-blind and orientation-blind. `layouts.js:857` does the same at
34 for list entries.

Ladder: **rung 1 (take the free space), then rung 2 (reflow — wrap the chip to
a second line; the card has vertical room in both orientations)**. This is on
the law's own "Never, in any situation" list twice over — "ellipsis or
truncation on content the user must read — a shortcut, a NAME, a value" and "a
neighbour holding slack next to a starving element" — and `layouts.css:202`
already states the principle it breaks: the top-bar chip may clamp *because one
tap opens the list*. During creation there is no list to open.

**I am the third grader to see this and the first to fail it.** The picture has
NOT changed; the disagreement is mine and it is deliberate. Round 14 and both
independent grades named it ("the only open visual debt", "carried, not
argued") and then wrote 8 and 9 over it. A defect that is named in three
consecutive proofs and fixed in none is not debt, it is a grade being rounded
up by habit, and the law's text on truncation has no exception for a chip.

### 2. The Region grab pill — 6/10
`.claude/shots/Region_grab.png`. **Never graded by anyone**, in any round.

What a person sees: the instruction reads

    Drag the
    corners,          [ Send ]  (x)
    then
    Send

— four lines, two of them a single word — inside a pill that spans x=209..614
of an 824 px (device) screen. **419 device px = ~210 CSS px, more than half the
screen's width, stands empty on either side of it** while a four-word sentence
is broken four ways. Ladder **rung 1**: the pill takes the free width and the
sentence sits on one line. Second: the caption says "then Send" and the button
beside it says "Send" — the same word twice in one control. Third: the default
region frame and its move handle are drawn ON the "Layout" button, clipping its
label to "Layou" (this may be the fixture's staged position rather than the
product's default — it needs one look from someone who can run it).

### 3. The status pill paints over the wheel — landscape only — 7/10
`.claude/shots/Controls_and_wheel_landscape.png`.

What a person sees: with the category wheel open, the wheel's 12-o'clock item
is at the top centre of the screen and the status pill is drawn on top of it —
the "Mouse" circle's ring and icon show above and around the pill, and the
item's LABEL is completely covered. Portrait does not have this: the wheel sits
lower (the item's centre is at y=680 of 1830) and clears the pill entirely.

This is not only the connect-time "Connected" message. `toast {text}` is
specified to appear on the status pill, so every user-facing notice while the
wheel is open in landscape hides that set's name. Ladder **rung 1/2**: in
landscape either the ring's radius/origin or the pill's position must move —
there are ~700 device px of empty width on both sides of the pill.

## What I could NOT grade — do not read these as passes

1. **Controls, LIGHT outlined, LANDSCAPE.** The file
   `Controls_light_transparent_landscape.png` renders the DARK palette: its
   page samples (15,23,42) where every other `light` shot in the set, portrait
   and landscape, both fills, samples (236,238,246). Its wheel-OPEN sibling
   `Controls_and_wheel_light_transparent_landscape.png` IS light, so the look
   was applied and then lost between the two `page.screenshot` calls that
   straddle `closeWheel()` in tests/test_layout_audit.py:566-573. Either the
   audit has a race there or `closeWheel()` re-renders in the stored theme —
   the second would be a product bug on the phone, and neither can be settled
   from a still. That state has no picture and is recorded ungraded.
   I did not re-render it: the phone audit rewrites all 90 shots, which would
   have destroyed the evidence for every grade above, and two previous rounds
   already lost work to exactly that.
2. **ChordRecorder** — 232x68, below the Qt audit's 40,000 px^2 floor, so it
   has no picture at all. Ungraded, not passed. Third round running.
3. **"MainWindow reopened from the tray" is still not a second observation.**
   MainWindow.png and MainWindow__reopened_from_the_tray.png are BYTE-IDENTICAL
   (md5 12c59bd6ae08, unchanged since the second grader recorded it), as are
   their light pair (c72b15932b44). Two proof lines, one picture.
4. **The two 15:34 `TrafficWindow_*_hover.png` files** — refused by grader 1,
   refused by grader 2, refused here: written by a process none of us
   controlled, hours before the build they claim to show.
5. **The settled contrast of the status pill.** In both shots that contain it
   the pill was caught mid-fade, so what I can measure (2.2:1 - 2.7:1) is a
   composited animation frame, not the shipped state. Stated so that nobody
   reads it as a finding either way.

## Where I differ from the earlier graders, and why

Lowered: Grid arrangement 9 -> 7, Creation panel 8 -> 7 (portrait). The picture
is UNCHANGED; the judgement is mine, argued in full above.

Raised, because the picture genuinely changed and I measured the change:
ControlsEditor 6/5 -> 8/8, WheelOrderDialog 7/6 -> 9/9, SettingsWindow 7/7 ->
8/8, TrafficWindow 6/6 -> 9/9, colored controls 7/7 -> 8/8, light controls
7/7 -> 8/8, Dictation card 7/7 -> 8/9.

Held where I found nothing new: MainWindow 8 in both palettes — the theme
pill's filled "sun" still reads as a COG (I cropped and enlarged it: a blue
donut with white slots cut into the ring and a hollow centre, two rows above a
real gear on the Settings button; on DARK, where the sun is unfilled, it reads
as a sun immediately), and the three door icons still mix stroke with solid.
Sets picker 8 and Quality panel 8 for the reasons already in this file.

## The deductions behind the 8s and 9s I did give

- **ControlsEditor 8, not 9, in both palettes.** Measured: 248 device px = 124
  CSS px of empty grid under "Focus" inside the pool table (last gridline at
  y=976, viewport ends at y=1226). It hides nothing and it is the honest price
  of showing fifteen set rows and thirteen pool rows without a scrollbar — the
  ladder puts a raised minimum above a scrollbar — but it is visible. The two
  Arrangement ladders still do not share an edge.
- **SettingsWindow 8, not 9.** The error sentence is right, placed right and
  bound to the right checkbox, but on DARK it measures **3.89:1** ((239,68,68)
  on (30,41,59)) at ~14 px — under the 4.5:1 AA floor, in the one line this app
  uses to report a broken hook. Light is fine at 4.83:1. Second: the sun/cog.
- **TrafficWindow hover 8, not 9.** With real data the Y gridlines read "0,
  0.5, 1, 1.4, 1.9" — the axis divides its own max into four instead of picking
  round numbers, so the labels round into a scale that looks irregular. Also,
  the window's last line is a bare absolute path (U:\...\logs\traffic.csv),
  unlabelled, hard against the bottom edge.
- **Dictation card 8 dark / 9 light.** On dark the two UNSELECTED radios are
  solid white discs — the brightest objects on the card — so "off" shouts
  louder than the accent-ringed "on". Light draws them as outlines and does not
  have the problem. Both palettes keep a literal three-dot "More languages
  (2)..." after the same round retired trailing ellipses next door.
- **The landscape panels at 8.** The reflow is `column-count: 2` on the whole
  card, so it splits groups that should stay whole: the dictation card puts
  Deutsch alone at the top of the right column, ABOVE the Srpski and English it
  belongs with; the quality panel puts FPS in one column and Resolution and
  Bitrate in the other, three sibling rows on two different baselines; the
  layout list puts Desktop in one column and the only layout in the other.
  Nothing is cut and nothing scrolls — this is composition, not the law — but
  a reader meets a one-choice list out of order.
- **The landscape work is otherwise very good and should be said so.** Ten
  panels, none scrolling, in a 915x412 box where seven of ten were scrolling up
  to 256 px before; the creation panel's Create button is on screen; every
  D-pad label clears 8:1 in all six looks; the four LANDSCAPE three-window
  arrangement chips are finally photographed and are all drawn on the wide
  outer box, distinguishable from their portrait twins before any label is read.

---

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
ROUND: THIRD INDEPENDENT VISUAL GRADE — ADDENDUM, written after HEAD moved
       under me (69a64e6 -> c55dff3) and after a second wrong picture turned up

Two things happened after my block above was written, and both belong in the
record rather than in a quiet edit.

**1. HEAD moved while I graded.** My shots were taken at 19:03 against
69a64e6; the round was committed as c55dff3 at 19:1x. `.claude/visual-proof.json`
now carries c55dff3, and that is honest only because I checked it: the only
source files touched between my run and the commit are `server/grids.py`
(19:10), `server/window_manager.py` and `server/layout_api.py` (19:06) and
`tests/test_layout_protocol.py` (19:05) — server-side geometry and window
plumbing, none of them a rendering file. Everything under `server/gui/` stops
at 19:02:22 and everything under `client/` at 18:51, both before my run. So the
pictures still depict what c55dff3 renders. If any GUI file moves after this
line, the proof is stale and must be re-shot.

**2. A SECOND mislabelled screenshot, which settles Finding A.** After writing
Finding A I swept the page colour of all twelve `Controls*` look shots, dark
and landscape included. One more is wrong:

    Controls_light_transparent.png            page (236,238,246)  LIGHT   ok
    Controls_light_transparent_landscape.png  page ( 15, 23, 42)  DARK    WRONG
    Controls_light_full_landscape.png         page (236,238,246)  LIGHT   ok

The landscape light-outlined shot renders the DARK theme. Its portrait twin
does not, and the light-FILLED landscape shot does not. Combined with
`Controls_dark_full.png` losing its fill, that is two of twelve look-named
pictures showing a look other than the one in their filename — and both carried
`audit: PASS`.

This upgrades Finding A from "the dark fill axis is dead" to something wider
and worse: **`applyUi` can be silently overwritten between the moment the audit
asks for a look and the moment it presses the shutter, and nothing anywhere
notices.** The cause is the same one line — `client/connection.js:78`,
`applyUi(msg.ui || null)`, over `UI_DEFAULT` in `client/theme.js:299` — and the
audit's own omission is the same one assertion: nothing compares
`body.dataset.theme` / `body.dataset.fill` against the look that was requested
before `page.screenshot` runs.

Until that assertion exists, **a look-named screenshot in this project is not
evidence of that look**, and no grader — first, second or third — can tell a
correct picture from a mislabelled one without measuring the page colour by
hand. That is the whole reason this round found it and the previous two did
not, and it is the single cheapest thing this project could add to stop paying
for grading rounds that grade the wrong picture.

- Controls, light outlined, LANDSCAPE (client/connection.js, tests/test_layout_audit.py) - MIN 915x412 - SHOT .claude/shots/Controls_light_transparent_landscape.png - GRADE 5/10 - audit: PASS (and that is the defect)


## ADDENDUM — reconciliation with the grader who was working in parallel

While I graded, a second independent grader appended the block above mine
(`THIRD INDEPENDENT VISUAL GRADE, 19:03-19:30`). Neither of us saw the other's
numbers before writing our own, and it was that grader's audit runs that wrote
the 19:03 / 19:10 pictures I graded — so the provenance of my evidence is a
grader-caused run, not a fixer's. Reconciled per this file's own rule, **the
LOWER of two independent grades stands**:

| screen | that grader | me | STANDS |
|---|---|---|---|
| Controls, dark FILLED, wheel shut | **5** | not tested | **5** |
| Grid arrangement / Creation panel (portrait) | **6** | 7 | **6** |
| Landscape three-window variants | **6** | 7 | **6** |
| Region grab | 6 | 6 | **6** |
| Controls and wheel, LANDSCAPE, dark outlined | not graded | **7** | **7** |
| SettingsWindow, dark + light | 9 | **8** | **8** |
| ControlsEditor dark + light | 8 | 8 | **8** |
| WheelOrderDialog dark + light | 9 | 9 | **9** |
| TrafficWindow dark + light | 9 | 9 | **9** |
| MainWindow dark + light | 8 | 8 | **8** |

**Two graders converged on the same two blocking defects from different
evidence** — the hard 30-character chip cap and the Region grab panel — which
is the strongest signal this file records. On the chip we even measured the
same pixels independently (chip ends x=523, column runs to x=748 in portrait).

**And that grader's Finding A explains the one file I could not grade.** It
proved that `client/connection.js:78` calls `applyUi(msg.ui || null)` on every
`config` frame and that `client/theme.js:299` falls back to
`UI_DEFAULT = {theme:"dark", fill:"transparent"}` — so a `config` carrying no
`ui` RESETS the phone's look to dark/outlined. That is exactly what
`Controls_light_transparent_landscape.png` shows: a file asked for in
light/outlined that renders the DARK palette, page (15,23,42) where every other
`light` shot samples (236,238,246). Two independent observations, one root
cause. I confirmed the decisive half of Finding A on my own bytes: over the
RIGHT D-pad column `Controls.png` and `Controls_dark_full.png` differ by a
maximum of **0** per channel, and the Click button fills (18,26,45) in both —
the 20 % tint, never the solid (30,41,59) that `data-fill="full"` is supposed
to paint.

**The release therefore blocks on four items, not three:**

1. **Controls, dark filled — 5/10.** A `config` with no `ui` silently resets
   the look, so the Filled choice the desktop's Appearance card offers does
   nothing on the DEFAULT theme. Product fix: merge or ignore, never overwrite.
   Tooth: assert `body.dataset.fill` still holds between `_apply_look` and
   `page.screenshot` in tests/test_layout_audit.py.
2. **The chosen-window chip — 6/10**, portrait and landscape
   (client/layouts.js:791, hard 30-character cap; 112 / 124 CSS px idle beside
   it; the full title appears nowhere else once Name is retyped).
3. **Region grab — 6/10** (a four-word sentence broken four ways inside a pill
   that leaves ~210 CSS px of the screen empty; "Send" printed twice; the
   default frame drawn over the Layout button).
4. **Controls and wheel, landscape — 7/10** (the status pill paints over the
   wheel's 12-o'clock item and hides its label; every `toast` does this, not
   only the connect message).

Everything else on both graders' tables is at 8 or above.

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
Round 15's COORDINATOR grading the two screens it edited itself (client/region.js
and the landscape rule in client/style.css). Everything else this round was
graded by three independent graders whose blocks stand above; these two are mine
because I wrote them, and the law wants the author's own honest eyes on them.

- Region grab (client/region.js) - MIN 824x1830 - SHOT .claude/shots/Region_grab.png - GRADE 9/10 - audit: PASS
  OPENED and looked. "Drag the corners to frame it" now reads on ONE line, and
  "Send" is printed once — on the button, where it belongs. The frame is born
  clear of our own chrome: the Layout button is whole, no longer clipped to
  "Layou". Deduction: the bar's ends sit close to the Middle and Esc columns,
  so the pill is comfortable rather than roomy.
- Controls and wheel, LANDSCAPE (client/style.css) - MIN 915x412 - SHOT .claude/shots/Controls_and_wheel_landscape.png - GRADE 9/10 - audit: PASS
  OPENED and looked. The wheel's 12-o'clock item shows its label WHOLE — the
  status pill no longer paints over it. Both D-pads, Layout and Hide are clear
  of the ring. Honest limit, stated rather than hidden: this shot carries no
  toast, so it proves there is no overlap in the resting state; the pill's own
  new position under `body.wheel-open` is reasoned from the geometry (the free
  column is ~300 CSS px wide) and is not photographed here.

---

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
ROUND: FOURTH INDEPENDENT GRADE (2026-08-07, 19:55-20:10) — the CLOSING grade
       on the nine entries that were below 8, re-measured after the fixes

I wrote none of this code and I edited no source file in this round. I did not
take any earlier grader's word for anything: every ruling below was decided on
a picture I opened with the Read tool after checking its mtime against the
source it renders, and every claim a number could settle was MEASURED (Pillow
per-pixel sampling, WCAG 2.1 contrast, live DOM rectangles from a headless
Playwright page).

**Freshness, checked before grading anything.** `client/*` stops at 19:55:11
(style.css), `server/gui/*` at 19:02:22 (settings_window.py). The phone shots
are dated 19:55:25-19:55:31 and the desktop shots 19:55:32-19:55:34 — every
picture is newer than the last edit to any file it renders. I then RE-RAN
`tests/test_layout_audit.py` myself (20:03-20:04, headless Chromium, nothing on
the owner's screen, exit 0). The re-run reproduced the same bytes — same file
sizes, same measurements — so the pictures I graded are what the committed code
draws, twice over, not a lucky run.

**The audit's new tooth is armed and green.** `_shoot()` now reads
`document.body.dataset.theme/fill` at the shutter and FAILS the run when they
differ from the look it asked for. Both orientations printed
`PASS  the shot shows the look it is named for: ...` for all twelve looks. That
assertion is the reason finding A and the light-landscape picture cannot come
back silently — and I verified it fires from the source, not from the summary
line: `tests/test_layout_audit.py`, `_shoot`, `results[...] = ok`.

## The nine, re-measured

### 1. Controls, dark FILLED — 5/10 -> 9/10. THE AXIS IS REAL.

`Controls.png` (dark/outlined) vs `Controls_dark_full.png` (dark/filled), the
two files that were byte-identical over the whole control surface last round:

| measurement | outlined | filled |
|---|---|---|
| max per-channel difference between the two files | — | **16** (was **0**) |
| share of the frame that differs | — | **8.97 %** (was 0.00 %) |
| Click button interior (mode of a 30x15 px sample) | rgb(18,26,45) | **rgb(30,41,59)** |
| button border (top edge scan at x=90) | rgb(64,71,87) | **rgb(75,83,98)** |
| button fill vs page rgb(15,23,42) | 1.03:1 | **1.22:1** |
| border vs page | 1.92:1 | **2.31:1** |
| white label on the button | — | 14.63:1 |

The filled buttons now read as raised slate tiles against the near-black page
where they used to be invisible; the Filled choice on the desktop Appearance
card does what the card says it does. Nothing is cut, every label is legible,
targets are comfortable. Graded 9, the same as its already-passing landscape
twin `Controls_dark_full_landscape.png`.

### 2. Controls, light OUTLINED, LANDSCAPE — 5/10 -> 8/10. RIGHT PALETTE NOW.

I swept the page colour of all 14 `Controls*` shots again. Every light-named
file, portrait and landscape, both fills, now samples **rgb(236,238,246)**;
every dark-named file samples rgb(15,23,42). The mislabelled picture is gone.
Graded on what it now is: the D-pad really is a cross in landscape, every label
whole, Click label **15.78:1** on its button. Deduction, identical to its
portrait twin which already sat at 8: the outlined button fill is
rgb(238,240,247) against a rgb(236,238,246) page — **1.017:1** — so on light the
outlined look leans entirely on its hairline border.

### 3-6. The chosen-window chip — 6/10 -> 9/10 (three shots) and 8/10 (one).

The hard cap is gone from `client/layouts.js` (I grepped for it; `titleChip`
now only adds a class) and `.lay-chip.lay-title` in `client/layouts.css` carries
`max-width:100%; white-space:normal; overflow-wrap:anywhere`.

I did not take the source's word for it. The fixture title is the exact string
the owner complained about — `Claude Code - Remote User - Visual Studio Code
[Administrator]`, **62 characters**, previously cut to 29 + an ellipsis. In all
four pictures I read it character by character and it ends in `[Administrator]`:
**nothing is lost, in either orientation.**

| shot | chip x-span | chip width | Name field's right edge | idle width left in the row |
|---|---|---|---|---|
| `Creation_panel___Name_field.png` | 74 -> 749 | 676 device px | 749 | **0** (was 225) |
| `Grid_arrangement_choice.png` | 74 -> 749 | 676 device px | 749 | **0** (was 225) |
| `Creation_panel___Name_field_landscape.png` | 198 -> 891 | 694 device px | 891 | **0** (was 248) |
| `Grid_arrangement_choice_landscape.png` | 198 -> 891 | 694 device px | 891 | **0** (was 248) |

Ladder rung 1 is fully taken — the chip's right edge is now the same pixel as
the Name field's — and rung 2 does the rest: the title wraps to a second line
inside the chip. Arbitrarily longer titles are handled structurally by the same
two properties, and the card only scrolls past `max-height:92vh`, which is
rung 4 used legally.

And the half the owner actually reported is answered: in
`Grid_arrangement_choice.png` the Name field has been retyped to `Chrome` and
the window's full title is still on the screen, in the chip above it.

Grades: `Creation_panel___Name_field.png` 9, `Grid_arrangement_choice.png` 9
(both rulings on that file), `Grid_arrangement_choice_landscape.png` 9,
`Creation_panel___Name_field_landscape.png` **8** — one deduction of my own,
not carried from anyone: its right column runs out of content after the Shape
row and holds a visible hole above Cancel/Create while the left column's Name
box is three lines tall. Nothing starves, so it is cosmetic, not a law breach.

### 7. Region grab — 6/10 -> 9/10.

Every one of the three defects is answered, measured on my own picture
(`Region_grab.png`, 824x1830):

- The hint is **one line**: `Drag the corners to frame it`. Four lines, two of
  them a single word, is gone.
- `Send` is printed **once**, as the filled primary button, with a drawn cross
  beside it. `client/region.js:185` names why in the code.
- The newborn frame's bounding box is **x 134->689, y 198->1135**. The Layout
  button occupies the top-left corner up to y~147. **The frame clears it by
  51 px** and the label reads `Layout`, whole — no `Layou`.
- The bar spans x~165->660 between D-pad columns that end at x=148 and begin at
  x=678; it overlaps neither.

The audit grew a tooth for this in the same round and it is green in both
orientations: `PASS  the Region frame opens clear of every control`.

### 8. Controls and wheel, LANDSCAPE — 7/10 -> 8/10. PHOTOGRAPHED WITH THE PILL.

`Controls_and_wheel_landscape.png` shows no pill at all, so it could not prove
the fix. **A fix nobody photographed is not proof**, so I rendered the missing
state myself — headless Playwright, the audit's own harness and `_apply_look`,
the real page, `openWheel('left')` then a real `showToast(...)`, written to
`.claude/shots/Controls_and_wheel_landscape_toast.png` (1830x824, 154 KB).
Nothing reached the owner's screen and no committed picture was touched.

Live DOM rectangles, landscape 915x412 CSS:

- status pill `x=16, y=82, w=272.5, h=54` — it has moved into the empty LEFT
  column (`body.wheel-open #status`, `client/style.css:568`), where it used to
  be centred at the wheel's 12 o'clock.
- intersection with the wheel's 12-o'clock `Mouse` item: **0 px** (x-overlap 0,
  y-overlap 43 — no intersection); with `Input` and `Edit`: 0.
- gap from the pill's right edge to the ring's leftmost item: **29.8 CSS px**.
- clipping: `scrollWidth - clientWidth = 0`, `scrollHeight - clientHeight = 0`,
  and still 0 for a deliberately doubled 96-character toast, which simply grows
  the pill to h=73 and three lines.
- the wheel's `Mouse` label, previously hidden, measures **8.35:1** and is
  fully readable in the picture.

Held at 8 rather than 9 for a defect I found while shooting it and am not
burying: the toast's own ink, rgb(231,231,233) on the pill's amber
rgb(221,135,10), measures **2.25:1** at 14 px — below the 4.5:1 AA floor. It is
the `connecting` state's colour reused for every `toast {text}`, it is present
in portrait as well, and it is outside every ruling in `visual-proof.json`, so
it is recorded here as a new finding for the next round rather than used to
block this one.

### 9. SettingsWindow, dark — stays 8/10. THE CONTRAST IS UNCHANGED.

Re-measured from the 19:55 picture, not from the previous grader's note. The
error line is still **rgb(239,68,68) on rgb(30,41,59) = 3.89:1** at ~14 px —
2,730 pixels of it in the sampled band, no antialiasing artefact. The light
twin is rgb(220,38,38) on white = **4.83:1** and passes. Source confirms it:
`server/gui/theme.py:80`, `"error": "#EF4444"`.

I am ruling it 8, not below, and stating exactly why so nobody has to guess:
the ruling this entry is graded against asks for "a plain-language sentence in
the **semantic error colour**", and `#EF4444` IS the semantic error token
`DESIGN.md` itself publishes. The window meets its ruling; what misses is
`DESIGN.md`'s own stated target ("Semantic — target WCAG AA, 4.5:1 on
surface") on this project's dark card. The remedy is one token: `#F87171`
measures **5.29:1** on rgb(30,41,59) and keeps the hue.

Half of the old reason for this 8 is now void and I am withdrawing it: I
cropped the theme pill and enlarged it 6x with nearest-neighbour, and the sun
is unmistakably a sun — a plain disc with eight separated rays, beside a
crescent moon on the active knob. It does not read as a cog.

## Phone — portrait

- Controls, dark filled (client/theme.js, client/connection.js) - MIN 412x915 - SHOT .claude/shots/Controls_dark_full.png - GRADE 9/10 - audit: PASS
- Creation panel + Name field (client/layouts.js, layouts.css) - MIN 412x915 - SHOT .claude/shots/Creation_panel___Name_field.png - GRADE 9/10 - audit: PASS
- Grid arrangement choice (client/grids.js, client/layouts.js) - MIN 412x915 - SHOT .claude/shots/Grid_arrangement_choice.png - GRADE 9/10 - audit: PASS
- Region grab (client/region.js, client/style.css) - MIN 412x915 - SHOT .claude/shots/Region_grab.png - GRADE 9/10 - audit: PASS

## Phone — landscape

- Controls, light outlined (client/theme.js, client/connection.js) - MIN 915x412 - SHOT .claude/shots/Controls_light_transparent_landscape.png - GRADE 8/10 - audit: PASS
- Creation panel + Name field (client/layouts.js, layouts.css) - MIN 915x412 - SHOT .claude/shots/Creation_panel___Name_field_landscape.png - GRADE 8/10 - audit: PASS
- Grid arrangement choice (client/grids.js, client/layouts.js) - MIN 915x412 - SHOT .claude/shots/Grid_arrangement_choice_landscape.png - GRADE 9/10 - audit: PASS
- Controls and wheel (client/style.css) - MIN 915x412 - SHOT .claude/shots/Controls_and_wheel_landscape.png - GRADE 8/10 - audit: PASS
- Controls and wheel with a live toast, GENERATED BY THIS GRADER (client/style.css) - MIN 915x412 - SHOT .claude/shots/Controls_and_wheel_landscape_toast.png - GRADE 8/10 - audit: PASS

## Desktop — dark

- SettingsWindow (server/gui/settings_window.py, theme.py) - MIN 718x943 - SHOT .claude/shots/SettingsWindow.png - GRADE 8/10 - audit: PASS

## What I am handing back, in priority order

Nothing in `visual-proof.json` is below 8 after this round. Two measured
defects remain, neither of them a gate on any ruling in that file, both worth a
line in the next round's task list:

1. **Toast ink 2.25:1.** rgb(231,231,233) on rgb(221,135,10), every toast, both
   orientations. `showToast` reuses the `connecting` pill style. Either give
   the toast its own state with darker ink, or darken the amber.
2. **Dark error text 3.89:1.** `#EF4444` on `#1E293B`, the one line that tells
   the owner his agent hook is broken. `#F87171` -> 5.29:1.

## What I could NOT grade, and it is not a pass

- **ChordRecorder** — still no picture at all. Its minimum is 232x68 and the Qt
  audit writes nothing under 40,000 px squared. Fourth round running. It is not
  in `visual-proof.json`, so it does not block this gate, but it has never been
  looked at by anyone.
- **MainWindow reopened from the tray** — `MainWindow__reopened_from_the_tray.png`
  is byte-identical to `MainWindow.png` (same 93,765 bytes) and its light pair
  likewise (93,544). Two proof lines, one picture; the tray-reopen state has
  still never been captured as a distinct state. Both entries sit at 8 on the
  strength of the picture they actually share, and the JSON says so.
- The nine shots in non-default looks dated 18:07 and the two
  `SettingsWindow_notify_healthy` shots dated 18:41 were written by another
  process and no committed entry point regenerates them. They are not in
  `visual-proof.json` and I did not grade them.

## Addendum — HEAD moved under me, so I re-shot everything again

Written after the grade above, so the record is exact rather than tidy. While I
was writing my verdict the round's coordinator committed twice more (b9bda3f,
then 9ae2d55 at 20:12:08, which swept in this very file and my toast shot).
That left every picture in `.claude/visual-proof.json` OLDER than the commit it
claims to prove — a thing THE VISUAL PROOF refuses outright, and rightly: a
picture taken before the commit is not evidence of the commit.

So I re-rendered all of it a second time, after 20:12:08 and with no source
changed in between: `tests/test_layout_audit.py` (exit 0),
`tests/test_layout_audit_qt.py` (exit 0), the hover script, and my own toast
shot. Then I set `commit` to `9ae2d55`. Every measurement in the block above
was re-taken on those final bytes and every one of them reproduced exactly —
the dark fill axis still 16 / 8.97 %, the light landscape page still
rgb(236,238,246), the chips still x74->749 and x198->891, the Region frame
still x134->689 / y198->1135, the Settings error line still rgb(239,68,68) on
rgb(30,41,59). Determinism, checked three times rather than assumed once.

I then ran the gate's own validator against the file
(`rules/hooks/visual_proof_guard.py::validate_proof`): **0 problems** —
`commit` matches HEAD, `grader` differs from `implementer`, every image exists,
is a real screenshot, is newer than the commit, and no grade is below 8.

The standing trap, stated so the next round does not fall into it: committing
the proof file moves HEAD past the shots, so the pictures must be re-rendered
AFTER the commit that carries them, or the guard blocks on its own bookkeeping.

One entry was REMOVED rather than graded: `MainWindow reopened from the tray
(light)`. Commit b9bda3f deliberately stopped photographing that case
(`NO_SHOT` in `tests/test_layout_audit_qt.py`) after measuring both factories
byte-identical, so no run regenerates the picture and the entry would have
blocked the gate on an image the project decided not to take. Its own ruling
already read "NOT AN INDEPENDENT OBSERVATION". The case is still AUDITED —
both palettes PASS — and `MainWindow__light.png` carries the pixels. What it
proves is a number, and the audit is where a number belongs.

---

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
ROUND: FOURTH INDEPENDENT VISUAL GRADE (2026-08-07, 19:58-20:20) — the round
       sent to check the last two fixes, and the one that found what the
       previous four rounds were not looking at

I wrote none of this code and edited no source file. I did not grade a single
picture another process wrote: I ran `tests/test_layout_audit_qt.py` (7 windows
x dark+light, all PASS) and `tests/test_layout_audit.py` (phone, portrait +
landscape, all six looks, PASS) myself at 19:58, and then **ran both again at
20:13** after HEAD moved under me (`b9bda3f` -> `9ae2d55`, a `.claude`-only
commit that swept the shots and the proofs into git) — because a picture older
than the commit it claims to prove is not evidence, whatever else is true about
it. Every measurement below was reproduced on BOTH runs, byte for byte.

## The table — my own numbers, from my own pictures

| Screen | g1 | g2 | g3 | me (4) |
|---|---|---|---|---|
| **Controls, dark: fill axis (wheel shut)** | — | — | **5** | **9 — FIXED** |
| **Controls, light outlined, LANDSCAPE** | — | — | **5 (wrong palette)** | **8 — FIXED** |
| **The chosen-window chip** (4 shots) | 8/9 | 8 | **6** | **9 — FIXED** |
| **Region grab** (portrait) | never opened | never opened | **6** | **9 — FIXED** |
| Region grab, LANDSCAPE (new picture) | — | — | — | **8** |
| Controls + wheel, LANDSCAPE (pill/label) | — | — | **7** | **8 — met, evidence hand-made** |
| Controls, light fill axis | 7 | — | 8 | **8 / 8** |
| Controls, colored filled | 9 | 7 | 9 | **9** |
| Controls + wheel, dark outlined / filled | 9 | 9 | 9 / 8 | **9 / 9** |
| Controls, LANDSCAPE | ungraded | ungraded | 9 | **9** |
| MainWindow, dark / light | 8 / 8 | 9 / 8 | 8 / 8 | **8 / 8** |
| SettingsWindow, dark / light | 8 / 8 | 7 / 7 | 9 / 8 | **8 / 8** |
| TrafficWindow, dark / light | 6 / 6 | 7 / 7 | 9 / 9 | **8 / 8** |
| **ControlsEditor, dark / light** | 6 / 5 | 7 / 5 | 8 / 8 | **7 / 7 — NEW** |
| WheelOrderDialog, dark / light | 7 / 6 | 8 / 8 | 9 / 9 | **9 / 9** |
| Sets picker / Quality panel / Dictation card | 8 / 8 / — | 9 / — / 7 | 8 / 8 / 8 | **8 / 8 / 8** |
| Quality / Dictation, LANDSCAPE | — | — | 8 / 8 | **8 / 8** |
| Layout list / Rename card / Aspect panel | 9 / 9 / 9 | — | 9 / 9 / 9 | **9 / 9 / 8** |
| Command chooser | never opened | never opened | never opened | **9** |
| **The status pill / every `toast`** | — | — | — | **5 — NEW, computed** |
| ChordRecorder | no picture | no picture | no picture | **no picture — 4th round** |

Proof lines:

- MainWindow (server/gui/main_window.py) - MIN 463x685 - SHOT .claude/shots/MainWindow.png - GRADE 8/10 - audit: PASS
- MainWindow light (server/gui/theme.py) - MIN 463x685 - SHOT .claude/shots/MainWindow__light.png - GRADE 8/10 - audit: PASS
- SettingsWindow (server/gui/settings_window.py) - MIN 718x943 - SHOT .claude/shots/SettingsWindow.png - GRADE 8/10 - audit: PASS
- SettingsWindow light (server/gui/settings_window.py) - MIN 718x943 - SHOT .claude/shots/SettingsWindow__light.png - GRADE 8/10 - audit: PASS
- TrafficWindow (server/gui/traffic_window.py) - MIN 635x558 - SHOT .claude/shots/TrafficWindow.png - GRADE 8/10 - audit: PASS
- TrafficWindow light (server/gui/traffic_window.py) - MIN 635x558 - SHOT .claude/shots/TrafficWindow__light.png - GRADE 8/10 - audit: PASS
- ControlsEditor (server/gui/controls_widgets.py) - MIN 733x950 - SHOT .claude/shots/ControlsEditor.png - GRADE 7/10 - audit: PASS (and that is the problem — see finding 1)
- ControlsEditor light (server/gui/controls_widgets.py) - MIN 733x950 - SHOT .claude/shots/ControlsEditor__light.png - GRADE 7/10 - audit: PASS
- WheelOrderDialog (server/gui/controls_order.py) - MIN 377x592 - SHOT .claude/shots/WheelOrderDialog.png - GRADE 9/10 - audit: PASS
- WheelOrderDialog light (server/gui/controls_order.py) - MIN 377x592 - SHOT .claude/shots/WheelOrderDialog__light.png - GRADE 9/10 - audit: PASS
- ChordRecorder - MIN 232x68 - SHOT none (below the Qt audit's 40,000 px^2 shot floor) - GRADE ungraded, NOT passed - audit: PASS
- Controls, dark FILLED, wheel shut (client/theme.js, client/connection.js) - MIN 412x915 - SHOT .claude/shots/Controls_dark_full.png - GRADE 9/10 - audit: PASS
- Controls, dark outlined (client/style.css) - MIN 412x915 - SHOT .claude/shots/Controls.png - GRADE 9/10 - audit: PASS
- Controls, light outlined / filled (client/theme.css) - MIN 412x915 - SHOT .claude/shots/Controls_light_transparent.png, Controls_light_full.png - GRADE 8/10 - audit: PASS
- Controls, colored filled (client/theme.js) - MIN 412x915 - SHOT .claude/shots/Controls_colored_full.png - GRADE 9/10 - audit: PASS
- Controls, light outlined, LANDSCAPE (client/theme.js) - MIN 915x412 - SHOT .claude/shots/Controls_light_transparent_landscape.png - GRADE 8/10 - audit: PASS
- Grid arrangement choice (client/layouts.js, client/layouts.css) - MIN 412x915 - SHOT .claude/shots/Grid_arrangement_choice.png - GRADE 9/10 - audit: PASS
- Grid arrangement choice, LANDSCAPE - MIN 915x412 - SHOT .claude/shots/Grid_arrangement_choice_landscape.png - GRADE 9/10 - audit: PASS
- Creation panel + Name field (client/layouts.js) - MIN 412x915 - SHOT .claude/shots/Creation_panel___Name_field.png - GRADE 9/10 - audit: PASS
- Creation panel + Name field, LANDSCAPE - MIN 915x412 - SHOT .claude/shots/Creation_panel___Name_field_landscape.png - GRADE 9/10 - audit: PASS
- Region grab (client/region.js, client/style.css) - MIN 412x915 - SHOT .claude/shots/Region_grab.png - GRADE 9/10 - audit: PASS
- Region grab, LANDSCAPE (client/region.js) - MIN 915x412 - SHOT .claude/shots/Region_grab_landscape.png - GRADE 8/10 - audit: PASS
- Controls and wheel, dark outlined / filled - MIN 412x915 - SHOT .claude/shots/Controls_and_wheel.png, Controls_and_wheel_dark_full.png - GRADE 9/10 - audit: PASS
- Controls and wheel, LANDSCAPE (client/style.css:568) - MIN 915x412 - SHOT .claude/shots/Controls_and_wheel_landscape.png - GRADE 8/10 - audit: PASS
- Controls, LANDSCAPE - MIN 915x412 - SHOT .claude/shots/Controls_landscape.png - GRADE 9/10 - audit: PASS
- Sets picker (client/sets.js) - MIN 412x915 - SHOT .claude/shots/Sets_picker.png - GRADE 8/10 - audit: PASS
- Sets picker, colored filled - MIN 412x915 - SHOT .claude/shots/Sets_picker_colored_full.png - GRADE 8/10 - audit: PASS
- Quality panel (client/quality.js) - MIN 412x915 - SHOT .claude/shots/Quality_panel.png - GRADE 8/10 - audit: PASS
- Quality panel, LANDSCAPE - MIN 915x412 - SHOT .claude/shots/Quality_panel_landscape.png - GRADE 8/10 - audit: PASS
- Dictation card (client/panels.js) - MIN 412x915 - SHOT .claude/shots/Dictation_card.png - GRADE 8/10 - audit: PASS
- Dictation card, LANDSCAPE - MIN 915x412 - SHOT .claude/shots/Dictation_card_landscape.png - GRADE 8/10 - audit: PASS
- Command chooser (client/panels.js) - MIN 412x915 - SHOT .claude/shots/Command_chooser.png - GRADE 9/10 - audit: PASS
- Layout list (client/layouts.js) - MIN 412x915 - SHOT .claude/shots/Layout_list_with_rename.png - GRADE 9/10 - audit: PASS
- Rename card (client/layouts.js) - MIN 412x915 - SHOT .claude/shots/Rename_card.png - GRADE 9/10 - audit: PASS
- Aspect panel + Move handle (client/layouts.js) - MIN 412x915 - SHOT .claude/shots/Aspect_panel___Move_handle.png - GRADE 8/10 - audit: PASS
- The status pill / every `toast` (client/style.css:42-58, client/theme.css:49-62,104-117) - GRADE 5/10 - audit: PASS (the contrast tooth is never run over `#status`)

## The two fixes I was sent to check — measured, both real

**1. The look reset.** `Controls.png` and `Controls_dark_full.png` were
byte-identical over the whole control surface last round (max per-channel
difference **0**). On my own bytes they now differ on **8.98 %** of the frame,
and the Click button is the decisive patch:

| look | Click button body | page |
|---|---|---|
| dark outlined | rgb(18, 26, 45) | (15, 23, 42) |
| dark **filled** | **rgb(30, 41, 59)** | (15, 23, 42) |
| light outlined / filled | (238,240,247) -> **(255,255,255)** | (236,238,246) |
| colored outlined / filled | (18,26,45) -> **(56,189,248)** | (15, 23, 42) |

rgb(30,41,59) is exactly `#1e293b` — the solid the filled look promises, where
the outlined look composites the same hex at 0.20. The axis is alive on all
three themes. `applyUi` now returns early on an absent `ui` and merges a partial
one (client/theme.js:336), which is the product half; the audit's half is the
new assertion, and it printed **14 `the shot shows the look it is named for`
PASS lines** in my run.

I then swept the page colour of every look-named `Controls*` shot — all
twenty-six of them, portrait and landscape:

    light (portrait + landscape, both fills)   (236, 238, 246)   correct
    dark and colored (both fills)              ( 15,  23,  42)   correct
    light under the wheel's veil               (167, 168, 177)   correct

`Controls_light_transparent_landscape.png`, which rendered the DARK palette
under a `light` filename last round, is now genuinely light — and it is the
only picture of that state, so a state that had NO evidence now has some.

**2a. The chip.** "Claude Code - Remote User - Visual Studio Code
[Administrator]" reads **whole**, wrapped over two lines, in all four shots
(creation panel and grid arrangement, portrait and landscape). The 30-character
guillotine is gone from `client/layouts.js`, and the new `__truncated` tooth
looks for the tell a JS cut leaves behind — an ellipsis IN the text — which is
the one thing `scrollWidth > clientWidth` can never see. That is the right
tooth for the right hole.

**2b. The Region grab.** Hint on ONE line ("Drag the corners to frame it"),
"Send" printed once, and the frame born clear of our chrome: the Layout button
reads "Layout" whole in portrait and in landscape.

## Who was right about the Region default frame: the FIXER, and I can show it

The old audit staged the frame itself:

    ("Region grab",
     "openRegionPanel();"
     "rgBox.x = 4; rgBox.y = 4; rgBox.w = 60; rgBox.h = 60; rgApply()",   <- removed in c6b338f
     ...)

A 60x60 box at (4, 4) is the top-left corner by construction — that is what
every grader was handed, and it is not a state the product opens in. The
product's old default was `x = 18 %`, `y = 22 %` of the screen, which in
PORTRAIT puts the frame's top at **y = 201 CSS px**, far below a Layout button
that ends at ~75. **The previous grader's finding that the default frame lands
on the Layout button was FALSE**, and it was false because the fixture lied to
them — the same class of failure as a screenshot named for a look it does not
show. The fixer's further claim that the old percentages DID collide in
LANDSCAPE is arithmetically sound (0.22 x 412 = 90.6, minus the 22 px handle
overhang = 68.6, against corner buttons running to ~75), but I could not run the
old code, so I record it as their claim and not my measurement.

The new birthplace is measured from the real elements (`rgFreeBand`), and it
costs one thing, which I grade rather than hide: in landscape the band between
the corner buttons and the D-pad rows is thin, so the newborn frame is a
**915 x 66 CSS letterbox**. It overlaps nothing; it is simply a sliver the user
must open out.

## Finding 1 — BELOW THE GATE: the ControlsEditor calls a typed command a chord

Ten of the thirteen commands in the Claude set are TYPED text in the shipped
`actions.json` — the `paste_text` mechanism the owner asked for on 2026-08-05,
because a slash command must be one atomic insert and not a race with the
autocomplete menu:

    {"label": "Usage", "icon": "usage", "text": "/usage", "enter": true}

The editor prints every one of them as **`chord`** with an **empty Shortcut
cell**, and its detail form shows **"Shortcut (chord)"** over a blank field with
a Record button beside it. The cause is one missing branch, in two places:

    server/gui/controls_widgets.py:530  (CommandTable.fill)
        if action:      does = "built-in"
        elif key:       does = "key"
        else:           does, shortcut = "chord", btn.get("chord", "")   <- a `text` command lands here
    server/gui/controls_widgets.py:412  (CommandDetail.show_button)      <- and here

Nothing is lost — `dump()` returns `dict(self._btn)` for a non-editable set, so
a Save does not rewrite the typed commands — but the window is telling the owner
something false about ten of the thirteen rows of its fullest set, and there is
no way to CREATE a typed command in a custom set at all, because the kind combo
offers only "Shortcut (chord)", "Special key" and the built-ins.

The app contradicts itself in writing, in the same round, in two pictures I
opened one after the other: the phone's command chooser
(`.claude/shots/Command_chooser.png`) says *"Pick one — the PC types it and runs
it"* about the very command the desktop calls a chord.

**MUST CHANGE:** a third branch — `does = "types"`, and the text itself in the
Shortcut column (`/usage`) — plus the kind in the combo so the pool can grow a
typed command. It is a display fix, not an architecture change.

## Finding 2 — BELOW THE GATE: every `toast` the app shows fails WCAG AA

`#status` is the pill that carries **every** user-facing notice — `toast {text}`
is specified to use it. It pins `color: var(--text-primary)` while its
background is a saturated semantic gradient, and `--text-primary` inverts with
the theme while the gradient does not:

| theme | state | ink on the gradient | contrast |
|---|---|---|---|
| dark | connecting (warning) | #f5f5f5 on #f59e0b -> #d97706 | **1.97 -> 2.92** |
| dark | disconnected (error) | #f5f5f5 on #ef4444 -> #b91c1c | **3.45** -> 5.93 |
| light | connecting (warning) | #16161f on #b45309 -> #92400e | **3.58 -> 2.53** |
| light | disconnected (error) | #16161f on #b91c1c -> #7f1d1d | **2.78 -> 1.79** |

Six of eight are under the 4.5:1 floor DESIGN.md itself sets for semantic
colour. I also measured it on a real rendering of the amber pill —
**2.68:1** — but that picture is one I refused (below), so the finding stands
on the shipped tokens, which need no photograph.

**Why four rounds of teeth missed it:** `window.__contrast` is real, careful and
now even composites overlays — and it is run over exactly four roots,
`#group-left`, `#group-right`, `#wheel` and each panel card. `#status` is passed
to none of them. The one element whose entire purpose is to be read at a glance
is outside the reach of the contrast tooth, and the Qt audit has no contrast
check at all.

**MUST CHANGE:** give the pill its own ink per state instead of the theme's body
ink — dark ink on the warning fill (#16161f on #f59e0b = **8.37:1**, on #d97706
= **5.64:1**), white on the light theme's deep amber (**5.02 / 7.09**), white on
error in both themes with the dark theme's first stop moved to #dc2626
(**4.83:1**). And pass `#status` to `__contrast`.

## What else I found that four rounds had not

- **The light theme pill's "sun" is a COG.** Enlarged 6x: a filled blue disc
  with a white hole and eight white slots cut through its ring, two rows above
  a real gear on the Settings button. On dark, where the same icon is unfilled,
  it reads as a sun immediately — so the cause is that the fill swallows the ray
  roots. Third round named, still unfixed. Draw the rays outside the disc, or
  grow the hole.
- **The dictation card's radios are inverted, measured.** The two UNSELECTED
  radios are a solid disc of pure **(255,255,255)** on a (30,41,59) card —
  **18.4:1**, the brightest object on the card — while the SELECTED radio is a
  (56,189,248) ring at 8.6:1. "Off" shouts twice as loud as "on".
- **The Quality panel's sentence is wrong by one word.** It says greyed-out
  steps are "already **above** what it allows", while `client/quality.js:40` is
  deliberately `fps >= base.fps` ("a step at or above the PC's own rate is
  identical to Max"). With the PC at 10 fps the picture shows the "10" step
  struck through under a sentence that says it should not be. Fix the sentence.
- **The SettingsWindow error line still measures 3.89:1 on dark** ((239,68,68)
  on (30,41,59)) — DESIGN.md ships `#EF4444` as Error and asks for 4.5:1 on the
  surface, and this surface is a card, not the page. `#F87171` measures 5.29:1
  there. Named twice before; the reason it survives is that
  `tests/test_layout_audit_qt.py` runs **no contrast check whatsoever**.
- **The wheel has never been photographed with more than THREE items.** Every
  wheel picture in this file — four rounds, six looks, both orientations —
  shows three, because `tests/fixtures/actions.json` defines exactly three
  categories, while the wheel's own cap is EIGHT and the picker in the very same
  screenshot says "up to 8 in total". I computed the missing state rather than
  leave it hanging: `WHEEL_RADIUS = 118`, item diameter 74, so at n = 8 adjacent
  centres are 2 x 118 x sin(22.5 deg) = **90.3 CSS px** apart — a 16 px gap, no
  collision — and the 6 o'clock item's bottom edge lands at **612.5 CSS px**,
  clear of the anywhere banner at 855. The geometry holds. The picture still
  does not exist, and a fixture with three categories cannot prove an
  eight-category rule.

## What I refused to grade — do not read these as passes

1. **`Controls_and_wheel_landscape_toast.png` (20:05:28)** — the only picture
   anywhere of the status pill beside an OPEN wheel, which is precisely the
   state the previous round failed at 7/10. **No committed entry point writes
   it**: `grep -ri toast tests/*.py` finds nothing in either audit. It was made
   by hand by another process while I graded, so I refuse it as proof exactly as
   the three graders before me refused pictures they did not produce — and I
   settle the ruling by construction instead: `body.wheel-open #status`
   (client/style.css:568) takes `left: var(--space-m)` and
   `max-width: calc(50% - 185px)` = 272.5 CSS px, while the wheel's 12 o'clock
   item spans 420.5..494.5 CSS px — **132 px of clearance** — and my own
   `Controls_and_wheel_landscape.png` shows the "Mouse" label whole at 7.08:1.
   The fix is real; its evidence is hand-made, which is the pattern THE VISUAL
   PROOF exists to stop. **The audit should stage a toast.**
2. **Every `TrafficWindow_*hover*` file** (19:22 and earlier) — older than the
   commit, and no committed entry point writes them. The hover card, the
   crosshair, the grey band and the right-edge flip are therefore **unproven
   this round**, not passed.
3. **The nine 18:07 phone shots in non-default looks** and the two 18:41
   `SettingsWindow_notify_healthy` shots — same reason, third round running.
4. **ChordRecorder — no picture at all**, fourth round. 232x68 is below the Qt
   audit's 40,000 px^2 shot floor. Ungraded, not passed.

## The tray subtraction: I agree, and I checked it rather than took it

`MainWindow (reopened from the tray)` is now audited WITHOUT a screenshot. That
is right. My freshly written `MainWindow.png` hashes to **md5 12c59bd6ae08** —
the identical hash the tray shot carried in the two previous rounds — and the
light pair to **c72b15932b44**. Two factories, one set of pixels; what the case
proves is a number (a window measured on its way back from the tray does not
report a smaller minimum), and a number is not a photograph. One housekeeping
item: the stale `MainWindow__reopened_from_the_tray(.__light).png` files are
still on disk and older than the commit — delete them, so no future round
mistakes them for evidence.

## `.claude/layout-frame.json`, checked

`floor_width` 1280 and `floor_height` 1000 UNCHANGED against HEAD. Every window
above is inside it. The `reason` prose still quotes ControlsEditor at 723x956
and Settings at 644x874 while the shipped windows measure **733x950** and
**718x943** — the same inaccuracy the previous grader handed back, still
uncorrected.

## The deductions behind the 8s, stated rather than rounded away

- **MainWindow 8.** "Stop server" alone in a row with ~670 device px of empty
  width to its right; the three-step pairing list CENTRE-aligned, so its
  "1." "2." "3." do not form a column; the cog-sun on light.
- **TrafficWindow 8 / 8.** The window's last line is a bare unlabelled absolute
  path hard against the bottom edge, and at the fixture's zeros the window draws
  a full 0-1.5 kB/s axis over an empty frame instead of saying there is nothing
  yet.
- **Aspect panel 8.** The preview draws four identical round handles on all four
  edges while the card's own caption says "portrait: full width, free height" —
  two of the four cannot move anything and are drawn exactly like the two that
  can.
- **Sets picker 8.** The always-in-the-wheel rows still carry the same solid
  tick as the optional ones — while the DESKTOP editor now draws them lighter,
  so the two ends of the same feature disagree.
- **The landscape panels 8.** `column-count: 2` still splits groups that should
  stay whole: Deutsch alone at the top of the right column ABOVE the Srpski and
  English it belongs with; FPS in one column with Resolution and Bitrate in the
  other. Nothing is cut and nothing scrolls — this is composition, not the law.
- **Region grab landscape 8.** The 915x66 CSS letterbox the free band leaves.
- **Controls and wheel landscape 8.** Met, but its only photograph is hand-made.

---

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38
ROUND: TYPED COMMAND FIX (2026-08-07) — answering Finding 1

Finding 1 above (the ControlsEditor calling a typed command a chord) is fixed.
Every line below was written AFTER re-running `tests/test_layout_audit_qt.py`
from THIS session (both palettes PASS, ControlsEditor unchanged at
MIN 733x950 — the reflow round's own footprint survives untouched) and opening
the freshly regenerated `.claude/shots/ControlsEditor.png` /
`ControlsEditor__light.png` with the Read tool.

- ControlsEditor (server/gui/controls_widgets.py, server/gui/controls_editor.py) - MIN 733x950 - SHOT .claude/shots/ControlsEditor.png - GRADE 9/10 - audit: PASS
- ControlsEditor light (server/gui/controls_widgets.py, server/gui/controls_editor.py) - MIN 733x950 - SHOT .claude/shots/ControlsEditor__light.png - GRADE 8/10 - audit: PASS

## What changed

`CommandTable.fill` already read a typed command correctly ("types ·
/usage"); `CommandDetail.show_button` had no branch for `{"text": …}` at all
and fell into the chord `else`, so the SAME selected row (Claude's Usage, the
first button in its pool — the row the audit's fullest-pool selection lands
on automatically) showed **"Shortcut (chord)"** over an empty field with a
live Record button. Fixed with a third kind, `KIND_TEXT`: the `Does` combo
gains "Types (paste text)" (the table's own word), and selecting it shows a
**Text** row (the real string, e.g. `/usage`) and a **"Press Enter
afterwards"** checkbox (`enter`, previously nowhere in this UI) instead of
the chord row — the two rows are mutually exclusive, drawn with `setVisible`,
never both on screen at once. Opening the shot: for the selected "Usage" row,
"The selected command" now reads exactly —

    Does      [Types (paste text)  v]
    Text      [/usage.........................]
              [x] Press Enter afterwards
    Name      [Usage.........................]
    Icon      [usage  v]

— matching the pool table's own "types · /usage" cell for the same row. No
shortcut field, no Record button, no contradiction.

A typed command is also now CREATABLE in a custom set: "Add command" seeds a
blank chord command as before, and switching its "Does" combo to "Types
(paste text)" reveals the Text field and Enter checkbox, which `dump()` turns
into `{"label", "text", "enter", "icon"?}` — the exact `paste_text` shape
`server/web.py`'s handler and the client's command chooser expect (proven by
`tests/test_controls_sets.py::test_a_custom_typed_command_round_trips`).

## The real bug the runtime audit caught along the way

The first version of this fix put the new "Press Enter afterwards" checkbox
in the SAME narrow column the Record button uses. That checkbox's text is
much wider than "Record", and because the fullest-pool audit selection lands
on a TYPED command by default (Claude's Usage), the checkbox — not the
Record button — was the thing actually occupying that column when the window
was first measured. `tests/test_layout_audit_qt.py` failed immediately:
`CLIPPED QComboBox '-': has 162x34, needs at least 218x34` — the `Does` combo
itself, starved by its own narrow-column neighbour. THE SPACE & LEGIBILITY
LAW's own ladder gave the answer: reflow, not a wider window. The checkbox
now rides its own row, spanning the field and button columns instead of
sharing the narrow one, and the clip is gone in both palettes with the
window's minimum UNCHANGED at 733x950 (in fact 70 px narrower than the
first, un-reflowed attempt at 803x950 — the checkbox's width no longer
inflates the floor at all).

## The deduction, stated rather than rounded away

- **ControlsEditor 9 dark / 8 light.** The standing, pre-existing idle space
  under the pool table's last row (~124 device px, documented in earlier
  rounds — all thirteen Claude commands fit with no scrollbar, so nothing is
  hidden by it) is untouched by this round and still the honest reason this
  is not a 10. Light loses one further point for the same generic reason
  earlier rounds gave SettingsWindow's light pass: correct and readable
  rather than beautiful, no new defect of its own.

SESSION: 5eac3ddf-7019-4f1c-914a-95246d063c38

The COORDINATOR's own eyes, at the end of round 15. Four independent graders ran
before this block and their findings drove eight fix rounds; what follows is not
a summary of theirs. I opened each image below myself, after the audits
regenerated them against HEAD e5a6b8e, and graded what I saw. Where I saw
something below the bar I sent it back rather than write a higher number: the
Controls editor was 7/10 in my own reading an hour ago — the command table said
"types . /usage" while the panel below it offered "Shortcut (chord)" with a
Record button for the same selected row — and it is 8/10 here because that was
FIXED (0.0.323), not because I revised the number.

- MainWindow (server/gui/main_window.py) - MIN 463x685 - SHOT .claude/shots/MainWindow.png - GRADE 8/10 - audit: PASS
- SettingsWindow (server/gui/settings_window.py) - MIN 718x943 - SHOT .claude/shots/SettingsWindow.png - GRADE 8/10 - audit: PASS
- TrafficWindow (server/gui/traffic_window.py) - MIN 635x558 - SHOT .claude/shots/TrafficWindow.png - GRADE 8/10 - audit: PASS
- ControlsEditor light (server/gui/controls_widgets.py) - MIN 733x950 - SHOT .claude/shots/ControlsEditor__light.png - GRADE 8/10 - audit: PASS
- WheelOrderDialog light (server/gui/controls_order.py) - MIN 377x592 - SHOT .claude/shots/WheelOrderDialog__light.png - GRADE 9/10 - audit: PASS
- Controls light outlined (client/style.css) - MIN 412x915 - SHOT .claude/shots/Controls_light_transparent.png - GRADE 8/10 - audit: PASS
- Controls light filled (client/style.css) - MIN 412x915 - SHOT .claude/shots/Controls_light_full.png - GRADE 8/10 - audit: PASS

What I actually saw, and the deduction behind each number:

MainWindow 8 - QR card, guidance, Stop server, three ICON buttons with no "..."
and the sun/moon pill after RUNNING. "Stop server" sits alone with the right
half of its row empty; the full-width update bar shouts louder than the RUNNING
pill does.

SettingsWindow 8 - five cards, one accent, label columns on one edge, and the
notification failure now reads as a SENTENCE in the semantic error red, not an
OSError repr with an installed path in it. The two Appearance combos are unequal
widths, and Focus/Startup - paired to keep the minimum inside the frame - are
not equal width either.

TrafficWindow 8 - the legend finally names its own two directions IN THEIR OWN
COLOURS (blue out, amber in, a grey band, a dashed peak); the axis carries its
unit, the gridlines round values, the X axis real times, and "Recording to file"
is an honest status dot instead of a checkbox nobody may click. The plot reads
as a panel now. It is empty because the audit fixture is 0 B/s - a fixture
limit, not a product one, and it is why the hover card is proven by hand-made
shots rather than by the audit.

ControlsEditor light 8 - every text input is a real white box with a real
border (it was one unit per channel off the page), the set list has a card, all
13 of the Claude set's commands are visible with NO scrollbar beside a column
that used to hold ~480px of nothing, the caret is a drawn chevron instead of a
solid square, and the detail panel now says "Types (paste text)" with the text
and a "Press Enter afterwards" box - a field that has been in actions.json since
2026-08-05 and had never had any UI at all. Deduction: ~124px of idle grid under
the pool table, and the right column now ends higher than the left.

WheelOrderDialog 9 - the ring sits beside its caption (it was marooned in ~350px
of dead space), the ordinals are right-aligned so the separators form one edge,
all 13 rows show, the list has a card on light, the arrows are drawn, OK is
primary. Deduction: the ring illustrates the rule rather than showing HIS actual
order.

Controls light outlined / filled 8 and 8 - these two were BYTE-IDENTICAL before
this round; the fill axis the desktop offers did nothing on one of three themes.
Now outlined lets the page through a thin border and filled is a solid white
card raised off it. Real, but subtler on light than on dark - white on a very
light page - which is inherent to the theme rather than a defect I would send
back. The "Use from anywhere" pill carries a DRAWN globe; the emoji is gone.
