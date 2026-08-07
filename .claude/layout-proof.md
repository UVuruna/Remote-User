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
- TrafficWindow (server/gui/traffic_window.py) - MIN 593x486 - SHOT .claude/shots/TrafficWindow.png - GRADE 8/10 - audit: PASS
- Creation panel, phone (client/layouts.js, client/layouts.css) - MIN 412x915 - SHOT .claude/shots/Creation_panel___Name_field.png - GRADE 9/10 - audit: PASS
- Rename card, phone (client/layouts.js) - MIN 412x915 - SHOT .claude/shots/Rename_card.png - GRADE 9/10 - audit: PASS
- Layout list, phone (client/layouts.js, client/layouts.css) - MIN 412x915 - SHOT .claude/shots/Layout_list_with_rename.png - GRADE 9/10 - audit: PASS
- Aspect panel + Move handle, phone (client/layouts.js) - MIN 412x915 - SHOT .claude/shots/Aspect_panel___Move_handle.png - GRADE 9/10 - audit: PASS
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

## The two 8/10s, stated rather than rounded up

- **TrafficWindow 8/10** — correct and readable, but the "Record to file"
  checkbox wears a duller tick than the same control on MainWindow, and the
  legend line wraps to two rows at the minimum. Neither hides anything.
- Everything else at 9: none of these panels is a 10 — the phone cards are
  functional rather than beautiful, and the ControlsEditor is dense by nature.
