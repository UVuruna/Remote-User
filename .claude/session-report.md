SESSION: 0eb7cbe2-d779-4c9d-9ec7-0a3d35d0897a
RELEASE: https://github.com/UVuruna/Remote-User/releases/tag/v0.0.086

# Final Report — round 11 (2026-08-06)

Owner's opening: two screenshots of the desktop window — *"slika 1 pokazuje
preklapanje elemenata kada ima update, slika 2 pokazuje preklapanje kod QR
koda, BUG da ne mogu da ukljucim NOTIFIKACIJE (prethodni agent je rekao da je
uradio) i CHECKBOX vizuelno neprihvatljiv"* — plus, mid-turn: *"jedan agent je
IMAO ZADATAK da stavi ŠTIKLIRANO pored onih koju su SELEKTOVANI I NIJE GA
IZVRŠIO"*.

NOT DONE / BLOCKED: **none**.

Two of the four were reported as done by an earlier session and were not. Both
are now proven by something other than my word: the overlap by a guard that
fails without the fix, the notifier by the file's presence in the built bundle.

## Gates on the released tree

guards 4/4 (structure, config sections, docs coverage, doc links) · APP-SET
WHEEL · CONTROL SETS · INPUT GATE · PRESENCE GATE · NOTIFY GATE · Qt layout
audit 5/5 at minimum and +50% (a fifth window registered this round) · phone
layout audit · client load test · PyInstaller smoke test · PAYLOAD GATE (new)
· signed exe + installer. Both new mechanisms self-tested by restoring the old
behaviour and watching the guard fail.

## Per task

- [x] 47. The two overlaps (both screenshots) — **FIXED**. Root cause: ONE
  bug, not two. The window's minimum was measured once, at construction, and
  an explicit `setMinimumSize` makes Qt stop enforcing its layout's own
  minimum. The update button is hidden until the GitHub check answers, and the
  notify caption grows from one line to three when it reports a failure — so
  the rows those two need had nowhere to go and were painted over the QR and
  its link. Fix: `_settle_minimum()` is callable at any time (re-measure from
  the computed floor, declare, grow, never shrink under the owner's own size),
  `_content_signature()` decides when so the 1 s tick does not re-lay-out the
  window every second, `showEvent()` settles on every show, and `_resettle()`
  refuses to measure while the window sits in the tray. That last part is a
  second hole found while reviewing the first: a child of a hidden window
  reports invisible, so closing to the tray looked like a content change and
  the re-measure handed back a minimum with no update button in it.
  Regression test: the audit factory now builds the window the way the owner
  meets it (shown first, late content after) and a second factory walks the
  tray path. Evidence: without the fix the audit reports `CLIPPED MainWindow:
  has 820x837, needs at least 618x880` — 43 px, the update button's own row —
  and `has 869x837, needs 618x880` on the tray path; with it, PASS at 869x880
  and +50%. Commits 0.0.250, 0.0.254.

- [x] 48. Notifications could not be switched on — **FIXED**. Root cause was
  not the switch's code, which was correct: `setup/agent_hook.py` was never
  added to PyInstaller's `--add-data`, so the frozen app resolved it under
  `_internal\setup\` and failed. Three layers, each of which failed on its
  own: the file is bundled; a new PAYLOAD GATE fails the build when any path
  the frozen code resolves under `BUNDLE_DIR` is missing — the smoke test
  could never have caught this, because it imports the module graph, not the
  data; and `notify._hook_module()` no longer hands a user a raw path, because
  a missing script means the APP is broken, which is what the sentence now
  says (the path stays in the log). Evidence:
  `dist/RemoteUser/_internal/setup/agent_hook.py` is present in this round's
  build. Commit 0.0.251.

- [x] 49. The checkbox's background — **FIXED**. Root cause: a `QCheckBox` had
  no QSS rule at all, so it fell to the base `QWidget` rule and carried the
  WINDOW's `surface0` into the `surface1` card it sits in — exactly the
  "background color različit od elementa u kojem se nalazi" — next to Windows'
  own gray tick box. The label is transparent now and the indicator is the
  same control surface as a combo (surface2, 1 px border, 5 px radius),
  accent-filled when on, wearing a DRAWN tick from `assets/check.svg` (never a
  font glyph — this project has already paid for one that came out a blunt
  cross on his device). Evidence: the window rendered offscreen to PNG and
  inspected as an image, because no audit can see a colour; and `check.svg` is
  in the built bundle beside `logo.svg`. Commit 0.0.252.

- [x] 50. The tick beside the selected sets — **DONE**, and this time visible.
  Each set row carries its own answer at the right edge: `CHECK_ROLE` holds
  it, `SectionDelegate._paint_tick` draws it in the accent, `MARK` reserves a
  22 px column so a long set name can never be drawn underneath it, and the
  caption over the list says what it means once. App sets wear no tick,
  because they do not ride on their own — they come and go with the focused
  layout. `_mark_current()` keeps the row and the form's checkbox saying the
  same thing the instant either changes. Evidence: the list rendered to PNG
  and inspected — six Standard sets ticked, three not (Cursor/Media/Windows,
  off by default since the cap fix), App-aware clean; and the editor's
  declared minimum grew by exactly the reserved 22 px, which is the audit
  confirming the column is really asked for. Commit 0.0.253.

- [x] 51. Round close — **DONE**. Full desktop build and GIT RELEASE v0.0.086.
  The APK was not rebuilt: nothing under `client/` or `android/` changed this
  round, and the phone's update banner compares against `config.apk_version`
  (the APK the PC actually serves, 0.0.085), so a desktop-only bump raises no
  false banner.

## What the owner should see on his PC

Install v0.0.086 from the release. In the Remote User window: nothing overlaps
while the update button is on screen, and "Tell my phone when an agent
finishes" can now be ticked — it will report only a real problem (a PC with no
Python on PATH), not a missing file. The checkbox itself is an accent box with
a tick. In Controls…, the set list shows a tick beside every set that is on
the phone's wheel.
