SESSION: b8d8ce25-5cc2-4f32-9fc5-60a910985a1f (round 12 — the focus guard: typed input lands where the owner is looking)
- MainWindow (server/gui/main_window.py, server/gui/sizing.py, server/gui/theme.py) - MIN 503x937 - SHOT .claude/shots/MainWindow.png - GRADE 9/10 - audit: PASS
- MainWindow reopened from the tray (server/gui/main_window.py) - MIN 503x937 - SHOT .claude/shots/MainWindow__reopened_from_the_tray.png - GRADE 9/10 - audit: PASS
- ControlsEditor (server/gui/controls_editor.py) - MIN 723x858 - SHOT .claude/shots/ControlsEditor.png - GRADE 8/10 - audit: PASS
- TrafficWindow (server/gui/traffic_window.py) - MIN 593x486 - SHOT .claude/shots/TrafficWindow.png - GRADE 8/10 - audit: PASS
- Command chooser, phone (client/style.css) - MIN 412x915 - SHOT .claude/shots/Command_chooser.png - GRADE 9/10 - audit: PASS
- Sets picker, phone (client/style.css) - MIN 412x915 - SHOT .claude/shots/Sets_picker.png - GRADE 9/10 - audit: PASS

What this round actually touched, stated plainly: NO Qt window and NO client
CSS. The change is `server/focus_guard.py` (new), the guard call in the
dispatcher (`server/web.py`), and `Layout.last_member` + the raise order in
`server/window_manager.py` — the last of which this gate counts as a GUI file
because it places windows on screen. It changes WHICH member window is left in
the foreground after a re-focus; it moves no widget and no pixel inside any of
our own windows.

The six windows above were re-audited and re-shot in this session all the same
(`tests/test_layout_audit_qt.py`, five windows PASS at minimum and +50%), and
every shot was OPENED and graded on what is actually in the picture:

- MainWindow / the tray copy 9/10 — the QR card, the four settings rows and
  the button row all breathe; labels and fields align on one column edge; the
  wide primary button anchors the bottom; nothing is cut and no strip of the
  window is starved.
- ControlsEditor 8/10, not 9 — everything is legible and aligned (set list |
  command table | command form | arrangement), nothing clipped and no text
  elided, so it passes; but at the DECLARED minimum the arrangement box carries
  visible empty space under its two lists while the table above it is the part
  that scrolls. That imbalance is the one thing keeping it off a 9, and it is
  not this round's work to move.
- TrafficWindow 8/10 — axis, legend row and the four bottom controls sit clean
  and unclipped; the plot itself is an empty grid because an offscreen audit
  has no traffic to draw, which is honest but bare.
- Command chooser 9/10 — six dark rows with borders and white text, evenly
  spaced, Cancel centered under them.
- Sets picker 9/10 — the cap line ("5 of 8 used — 2 held for app shortcuts")
  reads at a glance, the app-set group is separated by a rule, and the two
  "ON THE WHEEL NOW" badges are dark ink on the accent.

SESSION: 0eb7cbe2-d779-4c9d-9ec7-0a3d35d0897a (round 11b - the overlap the first fix did NOT fix, and the two teeth that were missing)
- MainWindow (server/gui/main_window.py, server/gui/sizing.py, server/gui/theme.py) - MIN 503x937 - SHOT .claude/shots/MainWindow.png - GRADE 9/10 - audit: PASS
- MainWindow reopened from the tray (server/gui/main_window.py) - MIN 503x937 - SHOT .claude/shots/MainWindow__reopened_from_the_tray.png - GRADE 9/10 - audit: PASS
- ControlsEditor (server/gui/controls_editor.py) - MIN 723x858 - SHOT .claude/shots/ControlsEditor.png - GRADE 9/10 - audit: PASS
- TrafficWindow (server/gui/traffic_window.py) - MIN 593x486 - SHOT .claude/shots/TrafficWindow.png - GRADE 8/10 - audit: PASS
- Command chooser, phone (client/style.css) - MIN 412x915 - SHOT .claude/shots/Command_chooser.png - GRADE 9/10 - audit: PASS
- Sets picker, phone (client/style.css) - MIN 412x915 - SHOT .claude/shots/Sets_picker.png - GRADE 9/10 - audit: PASS

The ChordRecorder is NOT listed: it was not touched this round, and its shot is
a 378-byte strip because the window genuinely is one - 219x66 of "Press the key
combination now...". A line claiming to grade that as a designed window would be
the kind of paperwork this gate exists to stop.

The two phone lines are new here, and they are the point of this round's second
half: a colour verdict can only be given on a PICTURE, which is why the owner
had to report it by eye. The phone audit now writes its own screenshots at
portrait size, so every panel it measures can also be looked at. Command chooser
9/10 - the six rows the owner photographed as white-on-white now read as dark
rows with a border and white text, aligned, evenly spaced. Sets picker 9/10 -
"ON THE WHEEL NOW" is dark ink on the accent instead of near-white at 1.96:1.

WHAT THE FIRST FIX GOT WRONG, and how it was found: the owner installed v0.0.086
and the link was STILL drawn across the QR. Reproduced here at his real 125%
scaling with the real Segoe UI - qr_label y=17..233, url_label y=195, Copy link
y=221 - all inside the QR. Root cause: `minimumSizeHint()` quotes a WRAPPING
label at ONE line, so the column's minimum came out 48 px short (hint 835, truth
883), and Qt spends a shortfall by OVERLAPPING, not clipping. Every widget still
reported its full size, which is why the guard was green over a broken window.
The measurement is now `layout.heightForWidth(width)` in one shared module
(server/gui/sizing.py) used by all three windows, and the pairing URL label -
60 characters of token nobody reads, the element that landed on the QR - is
gone; the QR carries it and Copy link copies it.

TWO TEETH ADDED, both self-tested by replanting the defect:
- OVERLAP (tests/test_layout_audit_qt.py): no two cells of one layout may
  intersect. Nothing here had ever checked POSITION, only size. Self-test: with
  the fix stubbed the audit reports the main window CLIPPED 820x837 needs
  618x880; it also caught a real one nobody had reported - TrafficWindow drew
  its chart 4 px over the caption beneath it.
- REAL FONTS: the Qt audit no longer forces the offscreen platform (whose
  substitute fonts measured 869x880 where the owner's machine needs 503x937).
  Native platform + WA_DontShowOnScreen: full layout, real DPI, nothing on
  screen. That switch alone surfaced two more genuine defects - the Controls
  editor 59 px short, and a Traffic combo cut to "Last 10 minut" by the theme's
  own 92 px floor.
- CONTRAST (tests/test_layout_audit.py, phone): WCAG ratio of every leaf text
  against its composited backdrop, < 3.0 fails. This is the owner's "kako
  dizajn los prolazi" - six white buttons with near-white labels passed every
  geometric check. Self-test: replanting the missing background reports all six
  rows at 1.05:1. It found two MORE that nobody had reported: the Sets picker's
  live badge at 1.96:1 (`var(--bg)` is not a token in this project, so the
  declaration was invalid and the badge inherited near-white ink), and it
  proved its own first version wrong - translucent selected states read as
  1.00:1 until the check composited alpha, so it now paints every layer.

FLOOR: .claude/layout-frame.json raises the height floor to 1000 with its
reason. The width, 503, is well under 1280; the height is content-driven (QR at
scan size + guided pairing text + settings + the notify caption's worst case).

SESSION: 0eb7cbe2-d779-4c9d-9ec7-0a3d35d0897a (round 11 — the two overlap screenshots, the notify switch that could not be armed, the checkbox's own colour, the tick in the set list)
- Main window (server/gui/main_window.py — the declared minimum is no longer measured ONCE: `_settle_minimum` re-runs on every content change and once more on the first `showEvent`) - Qt window at its DECLARED minimum 869x880 and at +50% 1303x1320 - audit: PASS - .venv\Scripts\python tests/test_layout_audit_qt.py, this session's own run. This is the state the owner photographed and the audit had never measured: the update button VISIBLE (it is hidden until the GitHub check answers) and the notify caption reporting a failure (three lines where it normally speaks one). 880 is 43 px taller than round 10's 837 — the update button's own row, the strip that was being painted over the QR's link — and 869 wide because the failure sentence names a path with no space in it, which cannot be wrapped and must therefore be given its width (the law: never elide content the user must read).
- GUARD SELF-TEST (on the mechanism this round actually added, not a neighbour): with `_resettle` and `showEvent` stubbed out, the same audit FAILS — "CLIPPED MainWindow: has 820x837, needs at least 618x880" — and passes with them restored. The 43 px in that message is the bug, measured. The audit factory itself was corrected in the same commit: it now `show()`s the window FIRST and lets the update button and the long caption arrive afterwards, which is the owner's actual sequence; built the old way, a window that is still hidden reports the button as costing nothing.
- Controls editor (server/gui/controls_editor.py — every set row now carries a TICK when it rides in the phone's wheel, drawn by `SectionDelegate`) - Qt window at its DECLARED minimum 1385x715 and at +50% 2077x1072 - audit: PASS - same run. The minimum grew by exactly 22 px in width, which is `SectionDelegate.MARK`: the tick gets a RESERVED column added to every non-heading row's `sizeHint`, so the list asks for it and no set name can ever be drawn underneath the mark (ladder step 1, then 3 — the list is not a stretched widget, so it must ask). Height unchanged: the tick is painted inside the row it belongs to.
- Visual check on the actual pixels (an audit cannot see a PAINTED mark, the same limit this file recorded for the section rule): both windows rendered offscreen to PNG and INSPECTED as images. The set list shows the tick in the accent, right-aligned in its own column, on the six enabled Standard sets and on none of the App-aware rows (they ride with a focused layout, not by themselves). The main window shows the notify checkbox as an accent-filled box wearing the drawn tick from assets/check.svg — the owner's "background color različit od elementa u kojem se nalazi" is gone, because the label is transparent now instead of carrying the window's surface0 into the card.
- Chord recorder (406x58) and Traffic window (1017x441) — untouched this round, re-audited because three sibling GUI modules changed - audit: PASS - same run.

SESSION: bed684c5-10c5-4b8f-9f53-cd011ed9074c (round 10 — the Claude tick, the cap of 8, the live badge, the notify switch)
- Main window (server/gui/main_window.py — the Settings card gained the "Tell my phone when an agent finishes" checkbox and its caption line) - Qt window at its DECLARED minimum 820x837 and at +50% - audit: PASS - .venv\Scripts\python tests/test_layout_audit_qt.py, this session's own run. The minimum GREW from 787 to 837 in height and is the new content's own number: it is computed in `showEvent` after Qt resolves the QSS font (the v0.0.079 lesson), so both new strings are measured, not estimated. At both sizes nothing is clipped, no text elided, and no scrollbar appears while the same axis still holds slack.
- Controls editor (server/gui/controls_editor.py — `_save()` now counts the app-set reserve, and its Wheel-limit message is longer than the one it replaced) - Qt window at its DECLARED minimum 1363x715 and at +50% - audit: PASS - same run. The message is a QMessageBox, which sizes to its own text; the dialog's own minimum is unchanged because no widget string moved.
- Chord recorder (406x58) and Traffic window (1017x441) — untouched this round, re-audited because two sibling GUI modules changed - audit: PASS - same run.
- Sets picker (client/panels.js + client/style.css — the new `.sets-live` badge, and the counter line given its own class so it can be updated in place) - phone 412x915 portrait + 915x412 landscape - audit: PASS - .venv\Scripts\python tests/test_layout_audit.py. Measured in its FULLEST state, which this session installed in the audit itself: all four app sets listed with the REAL names out of actions.json, a focused Claude layout, and TWO rows wearing the badge at once — the widest a row in this card can be (checkbox + icon + name + "ON THE WHEEL NOW"). The badge keeps its box when off (transparent, not removed), so no row changes height as focus moves.
- Rename card (client/layouts.js) - phone 412x915 + 915x412 - audit: PASS - same run. Now carries the four app-shortcut chips BESIDE the 70-char window title, and the audit case was extended to open it in exactly that state.
- Creation panel + Name field (client/layouts.js) - phone 412x915 + 915x412 - audit: PASS - same run, same long title + the same four chips.
- Quality panel, Dictation card, Region grab, Command chooser, Aspect panel + Move handle, Layout list with rename, D-pad labels - phone 412x915 + 915x412 - audit: PASS - same run (19/19), re-audited because panels.js/layouts.js/style.css changed.
- Layout region placement (server/window_manager.py + server/layout_api.py, no window of their own — this round added `Layout.app_sets` and the `layout_apps` message) - audit: PASS - tests/test_layout_audit.py `_fit_rect_audit`: four aspects × five positions, the placed rect never leaves its box and never degenerates. Neither change touches placement; this is the regression check that proves it.
- GUARD SELF-TEST (on the element this round actually added): planted `.sets-live { padding: 3px 210px }` in client/style.css -> audit FAILED "Sets picker @ portrait 412x915" AND "@ landscape 915x412", both with noClip: False, and the DETAIL lines name the Sets card itself. Plant removed -> full audit PASS 19/19. The badge is genuinely measured, not merely rendered.

SESSION: 2b03bd57-7cf3-4c57-85db-a463a2bf4c0f (the set list's section titles)
- Controls editor (server/gui/controls_editor.py — `SectionDelegate` paints each section heading centered, 1.25x, with a dividing rule above every heading but the first; the Custom section is not built at all while it is empty) - Qt window at its DECLARED minimum 1363x715 and at +50% 2044x1072 - audit: PASS - .venv\Scripts\python tests/run_guards.py (full) and a re-run of tests/test_layout_audit_qt.py printing each audited size, so the numbers above are this session's own run, not last round's. At both sizes: nothing clipped, no elision, no cut item row, no scrollbar while an axis still has slack. The declared minimum is UNCHANGED at 1363x715: the taller headings cost the SET LIST height, which is a stretched widget inside a window whose minimum is driven by the command table and the arrangement box, and the heading strings ("Standard", "App-aware", "Custom") are far shorter than the longest row ("Claude   (code · “claude code”)") even at 1.25x, so `sizeHintForColumn(0)` did not move.
- Visual check on the actual pixels (the failure this round was fixed FOR): the set list rendered offscreen to a PNG and INSPECTED as an image, twice — first render showed the rule invisible (`palette.mid()` sits a hair off this dialog's dark background), so the colour was changed to the palette's text colour at alpha 110 and the render repeated; the second render shows the rule clearly, the headings centered and larger, and no Custom section. An audit alone would have passed both, which is exactly why the image was looked at.
- Main window (820x787 + 1230x1180), Chord recorder (406x58 + 609x87), Traffic window (1017x441 + 1525x661) — untouched this round, re-audited because controls_editor.py changed - audit: PASS - same run.

SESSION: 2152f192-e6bb-4b94-b363-e35bd39777cd (round 9 — the Controls FIX)
- Controls editor (server/gui/controls_editor.py — the set list gained three section headings, and the Arrangement box gained a row: the lone reset button, renamed "Default", moved out of the third column and under the two lists) - Qt window at its DECLARED minimum 1363x715 and at +50% - audit: PASS - .venv\Scripts\python tests/test_layout_audit_qt.py. The minimum was RE-MEASURED in the same commit as the layout change (`_computed_minimum` now costs the arrangement seven text rows instead of five, because the ↑↓ pair and the Default row are both real), so 1363x715 is the new content's own number, not the old 1311x665 inherited. The audit's factory had to be fixed to keep telling the truth: it selects the set with the longest pool by ENTRY index, and with headings in the list that index is no longer the row — it now goes through `_row_of`, verified by the audited dialog reporting "Claude" (the 13-command pool) as selected. At both sizes: nothing clipped, no elision, no cut item row, and no scrollbar while an axis still has slack (the command table is the only stretched widget, so the free height lands there).
- Sets picker card (client/panels.js — a usage line "N of 8 used — M held for app shortcuts" and a longer app-group heading "App shortcuts while a layout is focused — they take wheel slots too") - phone 412x915 portrait + 915x412 landscape - audit: PASS - .venv\Scripts\python tests/test_layout_audit.py (card fully in viewport, no page horizontal overflow, no element clipped). The two new strings are exactly what could overflow; both wrap inside the card at portrait width.
- Main window + Chord recorder + Traffic window (untouched, re-audited because controls_editor.py changed) - audit: PASS - tests/test_layout_audit_qt.py
- GUARD SELF-TEST (on the card this round actually touched): planted `.sets-sub { min-width: 620px; white-space: nowrap }` in client/style.css -> audit FAILED "Sets picker @ portrait 412x915" AND "@ landscape 915x412", both with noClip: False (the DETAIL lines name the card, so the failure is the Sets card's own, not a neighbour's); plant removed via `git checkout -- client/style.css` (tree clean) -> full audit PASS, 25/25 checks.

SESSION: 2e75c457-babe-4f3d-be5b-586550ddc5c4 (round 8 — the command chooser)
- Command chooser (client/panels.js + client/style.css `.sets-row.choice`) - phone 412x915 portrait + 915x412 landscape - audit: PASS - .venv python tests/test_layout_audit.py, new case opened in its longest real state (the Claude Thinking button's six levels): card in viewport, no page overflow, no row clipped. It reuses the audited `.sets-card`/`.sets-list` shell, so the shape was already under the law; the new part is the row, which is a button rather than a checkbox line.

SESSION: 2e75c457-babe-4f3d-be5b-586550ddc5c4 (round 7 — Controls: icons, Region, Claude set)
- Region grab (client/region.js + client/style.css) - phone 412x915 portrait + 915x412 landscape - audit: PASS - .venv python tests/test_layout_audit.py, new case "Region grab" opened with the frame pushed into the top-left corner (where an overlap with the action bar would show first): card in viewport, no page horizontal overflow, nothing clipped inside the bar.
- GUARD SELF-TEST (on the panel this round actually added): planted `.rg-send { min-width: 620px; white-space: nowrap }` -> audit FAILED "Region grab @ portrait 412x915" with noClip: False; plant removed -> full audit PASS. The landscape case stayed green under the plant, which is the honest reading: 915 px of width really does swallow a 620 px button, and the portrait phone is the case that matters.
- Controls editor (server/gui/controls_editor.py + controls_widgets.py — the Name field became editable on built-in rows) - Qt window at its DECLARED minimum 1311x665 and at +50% - audit: PASS - tests/test_layout_audit_qt.py. The change adds no string: the field was already there and already measured, only its enabled state changed.
- Main window + Chord recorder (untouched, re-audited because the editor module changed) - 676x787 / 406x58 - audit: PASS - tests/test_layout_audit_qt.py
- D-pad buttons with the new icons and renamed labels (client/icons.js + client/controls.js) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py ("D-pad labels inside their buttons": the reserve-name case still wraps inside its 58 px button; the 97-icon set adds no text).

SESSION: 91d137d1-4678-4744-a74c-63de3d9df31b
- Quality panel (client/quality.js — split out of client/panels.js this session — + client/style.css) - phone 412x915 portrait + 915x412 landscape - audit: PASS - .venv python tests/test_layout_audit.py (real page, headless Chromium: card fully in viewport, no page horizontal overflow, no element clipped). Measured in the FULLEST state, which this session had to install in the audit itself: the case now calls setStreamBase({fps:10, width:3840, height:2160, bitrate:'6M', ...}) before opening, because an unset base renders the SHORT header ("Waiting for the PC's own settings…") and the old case was therefore measuring the empty panel. With the base set, the header is the longest it can be ("This PC is set to 10 fps · 3840×2160 · 6 Mbps — change that in the Remote User window on the PC"), a second explanatory paragraph sits under it, four of the five FPS steps carry the struck-through .out style, and the bitrate steps carry real Mbps labels instead of High/Mid/Low. The card's max-height: 92vh + overflow-y: auto is unchanged and does not engage at either size — no scrollbar beside slack.
- Sets picker (client/panels.js — the quality panel moved OUT of this file, nothing else changed) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py (same three checks)
- Dictation card (client/panels.js, same reason — re-audited because the file changed) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py
- GUARD SELF-TEST (on the panel this session actually touched): planted `.q-seg button { min-width: 200px; white-space: nowrap; }` in client/style.css -> audit FAILED both sizes with noClip: False ("Quality panel @ portrait 412x915" and "@ landscape 915x412"); plant removed (git diff --stat clean) -> full audit PASS, 21/21 checks. The check has teeth on this card, not merely on its neighbours.

SESSION: 2e75c457-babe-4f3d-be5b-586550ddc5c4
- Controls editor widgets (server/gui/controls_widgets.py — the arrangement lists, chord recorder, pool table and command form now live here after the STRUCTURE LAW split; they have no window of their own and are audited inside the two windows below) - audit: PASS - .venv python tests/test_layout_audit_qt.py. The rich-text SlotDelegate reports the RENDERED width (QTextDocument.idealWidth), so the item-view check measures what is drawn, not the `<sup>` markup — verified by the ITEM CUT check staying silent while the portrait rows really do fit.
- Controls editor (server/gui/controls_editor.py) - Qt window, offscreen at its DECLARED minimum 1311x665 and at +50% - audit: PASS - .venv python tests/test_layout_audit_qt.py (fullest state: the set with the longest command pool selected; nothing clipped, no elision, no cut item row, no scroll beside slack). The minimum is UNCHANGED by this session's work: the portrait ladder ("1ˢᵗ") is narrower than the names it replaced ("Bottom"), so the measured minimum stayed 1311x665. Also inspected with real fonts (QT_QPA_PLATFORM=windows, grab of the Arrangement group after a move): both ladders readable, superscript renders as superscript, no row cut.
- Chord recorder (server/gui/controls_widgets.py — moved here from controls_editor.py, unchanged) - Qt window, minimum 406x58 computed from its own two lines - audit: PASS - tests/test_layout_audit_qt.py (its factory import now points at the new module)
- Main window (server/gui/main_window.py — untouched this session, re-audited because the split changed what it imports) - Qt window at its DECLARED minimum 676x787 and at +50% - audit: PASS - tests/test_layout_audit_qt.py
- GUARD SELF-TEST (both halves, on the NEW file): planted `setFixedHeight(38)` on the arrangement list in controls_widgets.py -> static guard FAILED naming controls_widgets.py:249 ("Qt hard size - the element can no longer take the free space"), runtime audit FAILED with "CLIPPED SlotList: has 297x38, needs at least 70x96" plus the scrollbar container; plant removed -> static PASS (6 GUI files clean) and runtime PASS 3/3. The new module is inside the guard's reach, not beside it.

SESSION: 7583f4e9-4bcd-4842-b7ce-9d71cbc34872
- Theme (server/gui/theme.py, no window of its own — it styles all three) - the QSS combo `min-width` 140 -> 92 px, because two combos in a row held 280 px while the shortcut field beside them was squeezed to "ift+tab" - audit: PASS - tests/test_layout_audit_qt.py, which now applies the THEME to the Controls dialog the way the app does (a bare instance was being measured without it, i.e. without the very rule that caused the bug). That change immediately failed the audit — "ELIDED QCheckBox 'Shown in the wheel by default…': text needs 780px, element offers 758" and the set list cut again — root cause: the minimum was measured in `__init__`, where Qt has not yet resolved the QSS font, so every string was measured ~8% too narrow. Measurement moved to `showEvent`; re-run PASS. Declared minimum is now 1311x665.
- Controls editor (server/gui/controls_editor.py) - Qt window, offscreen at its DECLARED minimum 1311x665 and at +50% - audit: PASS - .venv python tests/test_layout_audit_qt.py (fullest state: the set with the longest command pool selected; no clipping, no elision, no cut item row, no scroll beside slack). FIRST RUN FAILED and named the owner's two screenshots: the arrangement lists scrolled at a hard height while a trailing stretch held the free space (BUG A), and the set list cut "Explorer   (app · explorer)" (BUG B class). Fixed by the ladder: stretch removed and the command table given the free height, SlotList sizing to its rows, the list asking for sizeHintForColumn(0), fields moved to full-width rows, minimum COMPUTED from the longest real strings.
- Main window (server/gui/main_window.py) - Qt window, offscreen at its DECLARED minimum 676x787 and at +50% - audit: PASS - tests/test_layout_audit_qt.py (running server, Tailscale URL, longest guided text). FIRST RUN FAILED: setFixedWidth(400) plus a footer wider than the window -> hard width replaced by a computed, settled minimum; footer wraps; QR label's fixed square exempted on the line with its reason.
- Chord recorder (server/gui/controls_editor.py) - Qt window, minimum 406x58 computed from its own two lines - audit: PASS - tests/test_layout_audit_qt.py
- D-pad buttons with reserve labels (client/controls.js + client/style.css) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py (".ctl .lbl" now wraps instead of eliding; the wrapped label stays inside its 58px button. Check SEEN failing on a deliberately over-long label, then passing.)
- Layout list row name (client/style.css) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py (the row name wraps instead of eliding; the top-bar chip keeps its 2-row clamp, exempted with the reason that the full name is one tap away in this list)
- GUARD SELF-TEST (both halves, mandatory): planted `setFixedHeight(40)` on the arrangement list -> static guard FAILED naming controls_editor.py:310, runtime audit FAILED naming "CLIPPED SlotList: has 285x40, needs at least 70x52" plus the scrollbar container; plant removed -> both PASS (5 GUI files clean, 3/3 windows).

SESSION: 010646e6-701d-482d-ac47-275166fd9746
- Quality panel (client/panels.js + client/style.css) - phone 412x915 portrait + 915x412 landscape - audit: PASS - .venv python tests/test_layout_audit.py re-run on the MERGED tree 2026-08-05 (real page, headless Chromium: card fully in viewport, no page horizontal overflow, no element clipped)
- Sets picker (client/panels.js + client/style.css) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py (same three checks)
- Dictation setup card (client/panels.js + client/style.css) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py re-run after round 4 (card in viewport, no overflow, no clipped rows; 5-language stub incl. long names + the collapsed extra section + the mute-beeps row)
- Aspect panel + Move handle (client/layouts.js + client/style.css) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py (card in viewport, no clipping, handle fully inside the card, zero page errors)
- Layout region placement (server/window_manager.py, no window of its own) - audit: PASS - tests/test_layout_audit.py `_fit_rect_audit`: the region stays inside its box and keeps positive size for every pos 0..1 and aspect 0.4..3.2

SESSION: c06e67a0-3082-48c1-a699-1053f9d49fe3
- Quality panel (client/panels.js + client/style.css) - phone 412x915 portrait + 915x412 landscape - audit: PASS - .venv python tests/test_layout_audit.py (real page, headless Chromium: card fully in viewport, no page horizontal overflow, no element clipped)
- Sets picker (client/panels.js + client/style.css) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py (same three checks)
- Dictation setup card (client/panels.js + client/style.css) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py (card in viewport, no overflow, no clipped rows; 3-language stub incl. long names)
- Aspect panel + Move handle (client/layouts.js + client/style.css) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py (card in viewport, no clipping, handle >= 40px and fully inside the card, zero page errors; the handle is now the drawn ICONS.move arrow, not a font glyph)
- Layout list with rename button (client/layouts.js + client/style.css) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py (a 70-char window title row keeps its pencil + ratio buttons on the card, nothing clipped)
- Rename card (client/layouts.js + client/style.css) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py (FIRST RUN FAILED: the one-line <input> hid most of a long window title behind its own horizontal scroll -> fixed with a wrapping 3-row textarea, box-sizing: border-box; re-run PASS)
- Creation panel + Name field (client/layouts.js + client/style.css) - phone 412x915 + 915x412 - audit: PASS - tests/test_layout_audit.py (same failure and same fix as the rename card; the prefilled long title is fully readable)
- Layout region placement (server/window_manager.py, no window of its own) - audit: PASS - tests/test_layout_audit.py `_fit_rect_audit`: the region stays inside its box and keeps positive size for every pos 0..1 and aspect 0.4..3.2
