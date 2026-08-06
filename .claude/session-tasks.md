# Session Tasks — 2026-08-05 (owner-defined, enforced by the root Stop hook)

ISPORUKA (round 6): kod = the TOPMOST leak killed at its two proven roots
(lock is never an excursion — the reason comes from the Android shell, not a
90 s JS timer; and no window stays topmost on ANY exit path, with a
next-start repair for crash/kill) + a desktop TRAFFIC MONITOR window that
makes the owner's suspicion measurable (bytes to/from the phone over time, so
a locked screen must read as a flat line) · dokument = updated __about docs
of every changed module + the CLAUDE.md protocol entry · build + GIT RELEASE
closes the round.

ISPORUKA (round 7, the Controls round — parallel session, keep the line
above): kod = the 97-icon set the owner approved (client/icons.js), the
Region grab (client/region.js), the Claude app set with TYPED command
buttons (`paste_text` protocol + clipboard.copy_text), renameable built-in
buttons, the per-app-set Sets picker, Image dropped from Attach, and the
style.css/layouts.css split · dokument = __about/__flow of every module
touched, ACTIONS.md, CLAUDE.md's protocol, and the answer on sound
notification when the agent finishes.

ISPORUKA (round 9, the Controls FIX round — his prompt.txt list + the mid-turn
message): kod = the Claude set matches the CONVERSATION only (word test, list
of spellings, a document never matches) · app sets charge the wheel's cap of 8
by the largest group that can appear together (VSCode+Claude = 2, so six left)
· the Controls set list in three sections (Standard / App-aware / Custom) ·
vscode/chrome/explorer icons instead of the generic window · Arrangement
rebuilt (caption "Arrangement", lists "D-pad (landscape)" / "Stack (portrait)",
the lone reset renamed "Default" and moved under the lists) · dokument =
ACTIONS.md, CLAUDE.md protocol, controls/panels/icons/controls_editor
__about+__flow, ___tests.md · guard = tests/test_app_set_wheel.py (node-backed,
in run_guards.py). SHIPPED as v0.0.082:
https://github.com/UVuruna/Remote-User/releases/tag/v0.0.082
The two corruption bugs he shouted about (VSCode gone, Win in Mouse) were
diagnosed here and fixed by the parallel session in 0.0.210 — both are in this
release, and the guard proves them.

Round-9 task list (owner's prompt.txt of 2026-08-06 + his mid-turn message,
checkbox form per the new Final Report gate):
- [x] find why VSCode vanished when Claude arrived, and bring it back
- [x] Claude set only on the Claude conversation tab, never on a document
- [x] both app sets ticked = 6 free wheel slots, not 7 (app sets charge the cap)
- [x] set list split into sections: standard / app-aware / custom
- [x] real icons for VSCode, Chrome, Explorer instead of the generic window
- [x] Arrangement: short title, D-pad + Stack names, Default button below the lists
- [x] check ALL groups after the Win-in-Mouse corruption (slika 3)
- [x] root rule with teeth: a delivering session ends with the per-task final report (machine-wide)

WAITING_ON_OWNER: no

ROUND 4 IMPLEMENTED (owner approved "moze sve i bipovi kao checkbox"):
(a) shipped-pools merge now ALSO runs once at server start
(web._merge_shipped_actions, FROZEN-only) — default-set updates reach the
phone without opening the editor; (b) LOCK stops everything — shell onPause
cancels the round + refuses new ones, page hides → inputOff(); (c) "Mute
listening beeps" checkbox in the card, DEFAULT ON (AudioManager mute during
listening, restored on cancel/background); (d) "More languages (N)…"
collapsed section — downloadable models + online-service list; (e) pulse
animation removed, dashed border stays. Verified: load test, guards (venv),
INPUT GATE, layout audit re-run with the extended card. SHIPPED as
v0.0.078: https://github.com/UVuruna/Remote-User/releases/tag/v0.0.078
(the parallel session's v0.0.077 went out without round 4, so 0.0.078
carries it; tree was clean at build time). Task 1 closes when the owner's
device round confirms: lock silences everything, no beeps, Language in
Settings without opening the editor.

Round-3 owner report (2026-08-05): RECOGNITION
WORKS (Serbian Latin chosen, text lands) — remaining: (a) Settings still
shows Anywhere — ROOT CAUSE FOUND: the desktop Controls editor snapshots
actions.json into the USER copy which wins forever, bundled default updates
never propagate (needs a defaults-version merge that keeps user tweaks);
(b) listening beeps every round — add a mute option in the dictation card
(AudioManager mute during rounds); (c) beeps continue with the phone LOCKED
— lock must stop EVERYTHING (shell onPause cancels voice + suppresses
restarts; page micStop/inputOff on visibilitychange hidden); (d) language
list should also offer downloadable/online languages, not just the phone's;
(e) drop the pulse animation, dashed border alone (owner). Plan presented,
waiting on the owner's approval; three agents on the repo — rebase before
touching layouts/controls files.

Round 2 (owner approved 2026-08-05): dictation setup CARD (first Mic tap) +
language CHANGE entry in the Settings set REPLACING the Anywhere button
(anywhere stays available in the actions pool — future preset combining, put
it in ROADMAP); while a model downloads, the Mic button wears an alternate
look and online recognition on the CHOSEN language serves; silent auto-switch
to on-device when the model lands; diagnostics go to the server log, never
the screen.

Rules: a task is checked ONLY when FIXED = VERIFIED (root cause named + fix +
evidence). WAITING_ON_OWNER may be `yes` ONLY when the turn genuinely ends
with questions/presentation the owner must answer; back to `no` the moment
work resumes. Enforced machine-wide by rules/hooks/session_tasks_guard.py.

- [x] 1. Mic (Input set) non-English recognition — REAL debugging, not
      micro-tweaks. LANGUAGE-AGNOSTIC (owner, angrily): the app works with
      the PHONE'S languages, never hardcodes any language — remove the
      hardcoded "sr-RS" in voiceLanguages(). Instrument: status pill shows
      engine (on-device/cloud), languages, onError codes. Use
      checkRecognitionSupport() to KNOW what the device offers; fallback =
      cloud pinned to the phone's locale; offer on-device model download /
      guide the user to add their language when the API says it exists.
      Owner approves several debug rounds; a settings/guided step in the app
      for the user's language choice is welcome if immediate keyboard-grade
      recognition is impossible.
      ROUND 1 EVIDENCE (owner device, 2026-08-05): Serbian speech transcribed
      as English garbage ("Be a Valley key In football lalinesis") → the
      engine ran ENGLISH; primary-locale pinning is wrong when the phone's
      first language is English. The __voiceInfo toast UX was WRONG (owner,
      angrily): a transient multi-line cryptic panel that vanishes in a
      second — the requirement is a GUIDED, persistent, plain-language card
      that lets the user CHOOSE the dictation language and fix what's
      missing (Tailscale-error-card pattern). Diagnostics must go SILENTLY
      to the server log, never flashed at the user. Design presented,
      waiting on the owner's yes.
      ROUND 2 SHIPPED (v0.0.075, still in v0.0.076): the dictation setup card
      (language chosen by the USER, never guessed), the Settings → Language
      entry, the alternate Mic look while a model downloads, and silent
      `client_log` diagnostics into the server log. BLOCKED HERE, not
      abandoned: the next step is EVIDENCE only obtainable on the owner's
      phone — install v0.0.076, pick the language on the card, dictate a
      sentence, and send back (a) what got typed on the PC and (b) the
      server-log lines around it. Which fix follows is decided by that log:
      an engine/model gap, a wrong language pin, or a recognizer error code
      each lead somewhere different, and guessing between them is exactly
      what the first two rounds proved wasteful.
      STATE AFTER ROUND 10 (2026-08-06): this is the ONLY open task, and
      nothing on this PC can close it. The owner's own round-3 report says
      RECOGNITION WORKS (Serbian Latin chosen, the text lands), and the
      five follow-ups he raised (a–e) all shipped in v0.0.078: the
      shipped-pools merge at server start, LOCK stopping every listening
      round, the mute-beeps checkbox default ON, More languages…, and the
      pulse animation dropped. What is missing is a CONFIRMATION only his
      device can give — three checks, on v0.0.085 or any build since
      0.0.078: (1) locking the phone mid-dictation silences everything at
      once, (2) no listening beeps between rounds, (3) Settings shows
      Language, not Anywhere, WITHOUT opening the desktop Controls editor.
      If all three hold the task is FIXED = VERIFIED and closes; if any
      fails, that failure is the next round's evidence and the server log
      around it (client_log lines) says which of the three causes it is.
      CLOSED 2026-08-06 by the owner himself, and his word IS the evidence
      this task was waiting for: "nije otvoreno, to je odavno zavrseno i radi
      kako treba sve vezano za MIC i setup". The three checks above are
      confirmed on his device. Root cause of the original failure, for the
      record: the engine was pinned to the phone's FIRST system locale, which
      on his phone is English, so Serbian speech came back as English garbage
      ("Be a Valley key In football lalinesis"). Fix: the language is a USER
      CHOICE made in the dictation setup card, never guessed — shipped in
      v0.0.075, with the five follow-ups (shipped-pools merge at server start,
      LOCK stopping every listening round, mute-beeps default ON, More
      languages…, pulse animation dropped) in v0.0.078.
- [x] 2. Layout resize panel: center Move handle (✥) — drag repositions the
      shrunken region along the free axis; applied on Apply; double-tap
      re-centers. DONE 0.0.169: layout_aspect {pos} + Layout.pos/_fit_rect
      placement + preview drag (layouts.js dragMove). Evidence: guards +
      load test + INPUT GATE pass.
- [x] 3. Sets picker rotating state — DONE 0.0.169, two root causes:
      per-ORIGIN localStorage split across LAN/Tailscale addresses →
      Android.prefGet/prefSet SharedPreferences bridge; opening-tap ghost
      click → capture-phase armor. Evidence: guards + load test pass;
      device confirmation rides the owner's release round.
- [x] 4. Quality panel — DONE 0.0.169: FPS Max/10/15/30/60, res full/⅔/½,
      bitrate high/mid/low + auto-on-mobile-data; protocol
      quality {fps,res,bitrate}; per-client ffmpeg overrides; desktop
      Settings combos remain the defaults every level maps against.
- [x] 5. Font-zoom staircase (layout focus only) — DONE 0.0.169:
      pinch-out past fitted view → chord ctrl+minus per step; pinch-in
      restores with ctrl+plus before visual zoom; per-layout step counter;
      minus/plus OEM VKs added to the injector.
- [x] 6. Session close — DONE: APK 0.0.074 built (Kotlin compiled), full
      desktop build passed (INPUT GATE + PyInstaller + signed installer,
      "BUILD COMPLETE ... OK: exe + installer signed"), GIT RELEASE
      published: https://github.com/UVuruna/Remote-User/releases/tag/v0.0.074
      Docs updated (CLAUDE.md protocol, module __about docs, panels.md).
      Task 1 (mic) stays open pending the owner's on-device debug round with
      this release — the diagnostics in it exist exactly for that round.

## Round 3 (owner brief 2026-08-05, evening — LAYOUT fix)

- [x] 7. Layout custom NAME — DONE 0.0.175 — the auto name (target window title) stays the
      default, but the owner may type his own. Creation panel gets a Name
      field (prefilled from slot 1); existing layouts get a rename entry in
      the layout list. Server `create()` already takes `name`; new protocol
      `layout_rename {index, name}` for the rename.
- [x] 8. Z-ORDER — owner decided 2026-08-05 to KEEP the topmost band and
      instead take the right away the moment the phone stops working (see 9).
      Original — stop forcing permanent TOPMOST on layout members: the
      owner AT THE DESK cannot see any other window above them. Proposal
      presented: transient topmost pop (TOPMOST → NOTOPMOST +
      SetForegroundWindow) = guaranteed to come forward, then a normal
      window. Waiting on the owner's yes (consequence: a foreign
      always-on-top window may cover a member).
- [x] 9. DONE 0.0.174 (root cause: no liveness signal at all — the server
      only reacted to a clean socket close, which a locked phone rarely
      sends; heartbeat + away + watchdog + server-side resume pointer;
      evidence tests/test_presence.py 7/7, now a build gate). Phone leaves
      work mode (lock / app closed) → PC minimizes every
      layout member; phone comes back → the LAST used layout is restored,
      not the desktop. Server-side memory (survives the socket) + grace
      timer so an excursion (gallery/permission dialog) does not minimize.
- [x] 10. DONE 0.0.175. Aspect panel Move handle icon — the ✥ glyph renders as a fat cross
      on the owner's device; replace it with an inline SVG four-way arrow
      (real arrowheads, font-independent).
- [x] 11. Session close — DONE: APK 0.0.076 built, full desktop build passed
      (INPUT GATE + PRESENCE GATE + signed installer), layout audit 19/19,
      GIT RELEASE published. Session close — docs of every changed module, APK + desktop build,
      GIT RELEASE.

## Round 4 (owner brief 2026-08-05, night — desktop Controls editor)

Presented to the owner (rendered page, 2026-08-05): field-by-field explanation,
the two law violations with their exact causes, the new dialog layout, the
buttons-pool data model, the per-set reserve commands. OWNER ANSWERED: all
three Qt windows in the audit registry; built-in presets get the pool CHOICE
only (their commands stay ours, custom sets stay fully editable).

- [x] 12. DONE — Controls editor obeys THE SPACE & LEGIBILITY LAW. Causes found:
      OrderList setFixedHeight(96) (controls_editor.py:240) + right.addStretch()
      (:343) = BUG A (list scrolls, ~300 px empty); theme.py
      `QComboBox {min-width:140px}` + a QGridLayout with no column stretch =
      BUG B ("shift+tab" → "ift+tab"). Fixed by the ladder: stretch removed and
      the table given the free height, SlotList sizes to its rows, fields moved
      to full-width rows, combo min-width 140→92, set list asks for
      sizeHintForColumn(0), minimum COMPUTED (1224x646) and documented.
      MainWindow lost setFixedWidth(400) for a computed+settled 676x787;
      ChordRecorder 406x58. Evidence: audit 3/3 PASS at minimum and +50%.
- [x] 13. DONE — Teeth: tests/test_layout_law.py (static, in --fast) +
      tests/test_layout_audit_qt.py (runtime registry of all three Qt windows,
      full run) wired into run_guards.py. SELF-TEST SHOWN: planted
      setFixedHeight(40) → static failed at controls_editor.py:310, runtime
      failed with "CLIPPED SlotList: has 285x40, needs at least 70x52"; plant
      removed → both PASS. The phone audit gained a D-pad label check, also
      shown failing on an over-long label. .claude/layout-proof.md written.
- [x] 14. DONE — Presets carry more than 4 commands: `buttons` is the pool,
      `active` names the four BY ID (no `active` = first four, old files
      unchanged); client activeButtons() + editor pool table with the tick,
      per-command detail panel, app_sets editable for the first time, and
      merge_shipped_pools() refreshing built-in pools from the shipped file —
      which is also the root cause of "Settings still shows Anywhere".
      Evidence: functional round-trip (Navigate 11-command pool: tick swap →
      active ['esc','shift+tab','tab','alt+left'], fifth tick refused; custom
      set: 5 commands, first four on the D-pad, no redundant key).
- [x] 15. DONE — Reserve commands per set (ACTIONS.md table), incl. the
      owner's: VSCode Preview ctrl+shift+v + next/prev tab, Chrome prev tab,
      Explorer next/prev tab. Injector gained `/` (VK_OEM_2) and
      medianext/mediaprev/mediastop.
- [x] 16. DONE — Built-in rows tell the truth: load_client_builtins() parses
      the client's BUILTINS, so the row shows "Built-in: Esc (esc)", name
      "Esc", icon "esc" — greyed because inherited, never a placeholder.
      Also fixed while proving it: the detail form kept the PREVIOUS set's
      command when both selections sat on row 0 (setCurrentCell is silent when
      the index does not change).
- [x] 17. DONE — Session close: docs of every changed module updated
      (controls_editor __about + __flow, main_window __about + __flow, theme,
      client controls, input_injector, ACTIONS.md pools+reserves table,
      CLAUDE.md, tests/___tests.md, .claude/layout-proof.md). APK 0.0.077 +
      full desktop build (INPUT GATE + PRESENCE GATE + PyInstaller + signed
      installer, "OK: exe + installer signed"), GIT RELEASE published:
      https://github.com/UVuruna/Remote-User/releases/tag/v0.0.077
      Scope note: v0.0.077 carries THIS round only — the parallel session's
      dictation round 4 (0.0.182) landed after the tag and ships with theirs
      (verified in the built client: pools present, their card changes not).
- [x] 18. FOLLOW-UP RELEASE v0.0.079 — the Stop gate flagged theme.py as
      unproven, and chasing that found a REAL defect the guard had been blind
      to: the audit built ControlsEditor bare, while the app builds it as a
      child of MainWindow and it inherits the theme, so the guard measured a
      dialog without the very QSS rule behind "ift+tab". With the theme
      applied the audit failed at once (checkbox needing 780px in 758,
      set list cut again). Root cause: the minimum was computed in __init__,
      before Qt resolves the QSS font — every string measured ~8% too narrow.
      Measurement moved to showEvent + settle; minimum 1224x646 -> 1311x665;
      3/3 windows PASS. APK + desktop rebuilt, GIT RELEASE published:
      https://github.com/UVuruna/Remote-User/releases/tag/v0.0.079
      (includes v0.0.078's dictation round 4).

## Round 5 (owner brief 2026-08-05, night — Controls FIX)

- [x] 19. Arrangement ladder (owner 1A) — raising a command must move the
      COMMAND, not the slot name. Root cause: `OrderList.set_order` baked the
      slot name INTO the item's text, so `takeItem/insertItem` carried
      "Bottom" up with it and the left column read Top·Left·Bottom·Right.
      Fix: the item holds only the command (INDEX_ROLE + LABEL_ROLE) and
      `_relabel()` re-draws the ladder from the row numbers after every move.
      Evidence: shot of the group after a move — ladder fixed, `order()`
      = [0,1,3,2]; Qt layout audit 3/3 PASS.
- [x] 20. Portrait ordinals (owner 1B) — a column has no left/right: the
      portrait ladder is now 1st/2nd/3rd/4th with REAL superscript, drawn by
      a rich-text delegate out of the dialog's own font (never an exotic
      glyph — the ✥ lesson). Evidence: same shot.
      Forced by both: `controls_editor.py` sat at 996/1000 lines, so the
      widgets moved into `server/gui/controls_widgets.py` (STRUCTURE LAW) —
      editor 639, widgets 474, docs + tier classification written.
- [x] 21. Mouse side buttons (owner 2) — Btn 4 / Btn 5 (XBUTTON1/2) as
      CLICK/HOLD reserves in the Mouse pool. `BUTTON_FLAGS` grew a mouseData
      column (both side buttons share one flag pair), client BUILTINS x1/x2 +
      two icons. Evidence: INPUT GATE, new case "side buttons: x1/x2 ->
      XDOWN/XUP with the right mouseData" PASS.
- [x] 22. Settings pool (owner 4) — Next box and Snap removed; the five that
      stay are Monitor · Sets · Quality · Language · Anywhere. They reach the
      owner's own %LOCALAPPDATA% copy through `merge_shipped_pools`, which
      runs at server start.
- [x] 23. Icons for the commands that have none (owner 5) — proposal page
      published (35 icons + Btn 4/5 + Region + a Claude set preview), each
      drawn as the real 58 px button next to its text-only alternative.
      DONE in round 7 (0.0.198): the owner accepted the whole page, 40 new
      faces (set now 97), moved to client/icons.js — which the desktop
      editor now parses — and wired onto every command in actions.json.
- [x] 24. Region (owner 3) — free-size/free-position rectangle on the phone,
      that crop pasted on the PC (Snipping-Tool equivalent). Server side is
      already there (`screenshot {x,y,w,h,paste:true}` crops any rect), so it
      DONE in round 7 (0.0.198): client/region.js — free size AND position,
      pasted the moment you tap Send (owner: "odmah lepi"). Phone audit
      case added and self-tested.
- [x] 25. Claude app set (owner 6) — feasible; answer delivered. Needs (a) a
      title/tab matcher next to `process` in `app_sets` so the set appears for
      a Claude window inside VSCode, (b) a new button kind `text` (type a
      slash command + Enter — the commands he named are not chords), (c) the
      Sets picker listing app sets one by one instead of one master toggle.
      DONE in round 7 (0.0.198), all three: `title` match beside `process`
      (Layout keeps the window's own title, so a rename cannot break it),
      per-app-set ticks in the Sets picker, and the typed-command kind —
      `paste_text` = clipboard + Ctrl+V + Enter, pinned in the INPUT GATE.
- [x] 27. Quality hierarchy (owner report: "desktop settings do nothing") —
      diagnosed as a real but INVISIBLE hierarchy plus one genuine bypass.
      Owner chose option A (keep the hierarchy, put the truth in the UI).
      Server: bitrate Mid/Low became percentages of the desktop bitrate
      (`config.bitrate_for_level`, was absolute "5M"/"1200k" — that was the
      bypass), and `config` now carries `base`. Client: quality split into
      `client/quality.js`, panel states the PC's live values and strikes out
      unreachable fps steps. Evidence: guards full PASS, load test PASS,
      INPUT GATE + PRESENCE GATE PASS, bitrate derivation checked
      (20M→8000k/2000k, 12M→4800k/1200k, 6M→2400k/600k).
      Commits 0.0.193–0.0.195, app v0.0.080.
- [x] 26. Round close for 23–25 — the code shipped as 0.0.198 + 0.0.199; the
      BUILD + GIT RELEASE itself is task 34, which carries the blocker.

## Round 6 (owner brief 2026-08-05, night — TOPMOST leak + traffic proof)

Owner report, verbatim intent: he built a GRID from the tablet, locked it,
turned the screen off, came to the PC — Chrome and VSCode were STILL TOPMOST.
Second demand: nothing may stay topmost when the app CLOSES. Third: he is
convinced the app keeps talking with the screen locked (battery), and wants a
desktop window that RECORDS all transfer and graphs it over time, so a locked
phone must be a provable FLAT LINE. He explicitly refused another "solved"
that is not solved.

ROOT CAUSE, PROVEN FROM THE LIVE LOG (%LOCALAPPDATA%/RemoteUser/server.log)
— not a theory: the LOCK was reported to the server as an EXCURSION.
client/state.js EXCURSION_GRACE_MS = 90000, and markExcursion() fires on
every Mic tap and every picker tap; the owner had been dictating seconds
before locking. So `away {excursion:true}` went out and web.py held the
layout topmost for EXCURSION_MAX_S = 300 s. The log shows it twice, to the
second: excursion 18:41:56 -> "Phone left work mode" 18:46:56, and excursion
18:43:11 -> 18:48:11. Exactly 300 s each.
SECOND ROOT CAUSE: LayoutRegistry.clear_topmost() exists and is called
NOWHERE in the repo — no exit path drops the topmost band.

- [x] 28. DONE 0.0.200 — a LOCK is never an excursion. ROOT CAUSE from the
      live log, not reasoning: client/state.js EXCURSION_GRACE_MS=90000 armed
      by every Mic/picker tap, so locking six seconds after dictating was
      announced as an excursion and web.py held the layout for
      EXCURSION_MAX_S=300 (18:41:56 -> 18:46:56 and 18:43:11 -> 18:48:11,
      exactly 300 s each). The reason now comes from the shell
      (Android.hideReason() reads PowerManager/Keyguard + its own excursion
      counter; lock is tested FIRST); the hold is 45 s; and THE DESK WINS —
      local input at this PC ends it at once. Presence moved to presence.py.
      Evidence: PRESENCE GATE 14/14 incl. "a LOCK is never an excursion" and
      "the owner's own keyboard at this PC ends the hold".

- [x] 29. DONE 0.0.201 — the topmost ledger. clear_topmost() existed and was
      called NOWHERE. Every raised hwnd is written down; release_all() is
      wired into ServerController.release_windows() (first in stop(), first in
      _serve's finally), Qt aboutToQuit, atexit in both entry points and a
      SetConsoleCtrlHandler; the ledger is mirrored to
      %LOCALAPPDATA%/RemoteUser/topmost.json and repair_stranded() fixes a
      killed run at the next start, identity-checked against the process
      image. drop_topmost is verified and keeps refused windows on the books.
      Evidence: PRESENCE GATE ledger checks; guards 4/4.

- [x] 30. DONE 0.0.203 — the Traffic window. MeteredSocket wraps the socket
      ONCE at accept (complete by construction), uploads counted too; one
      second per sample, an hour in memory, every sample appended to
      traffic.csv; a GREY BAND wherever no client was connected, so a locked
      phone must be a flat line inside it; the phone's own TrafficStats ride
      the heartbeat and the away-gap line reports what the app spent while it
      was gone. QPainter, no new dependency. Evidence: Qt layout audit 4/4 at
      minimum and +50%, the window built in its fullest state.

- [x] 31. DONE 0.0.202 — the audit's remaining leaks, none of them reachable
      from any member list: uia raised the tab's SOURCE window and next_input's
      target TOPMOST (now topmost=False); prune() deleted layouts whose members
      were merely CLOAKED (a virtual-desktop switch) and abandoned them up
      there; focus()'s drop-others pass ran after its early returns; a monitor
      switch left the layout on top of the monitor the phone had left; the
      resume-focus ran outside ws_endpoint's try; pairing.get_lan_ip could
      abort the process from the GUI's 1 s refresh. Evidence: INPUT GATE 19/19
      (it caught the JPEG duck-interface change the moment it landed).

- [x] 32. DONE — SHIPPED as v0.0.081:
      https://github.com/UVuruna/Remote-User/releases/tag/v0.0.081
      APK 0.0.081 + full desktop build (INPUT GATE + PRESENCE GATE +
      PyInstaller smoke test + signed exe and installer, "OK: exe + installer
      signed"). Docs: presence/layout_api/traffic/traffic_window about+flow,
      folder indexes, dated sections on web/window_manager/uia/server_core/
      gui_main/main_window/state/connection/MainActivity, CLAUDE.md constraint
      10 + the rewritten Presence paragraph.
      TWO-SESSION NOTE: my commits staged three files round 7 was editing, and
      de-staging their hunks to keep HEAD compilable meant their 0.0.206 lost
      the notify wiring; 0.0.208 restored it. Nothing was lost. Next time,
      shared files are staged by whoever owns the change.
      OPEN ON THE OWNER'S DEVICE: install v0.0.081, make a grid, lock the
      tablet, walk to the PC — the windows must already be gone. Then open
      Traffic… and lock the phone again: the line must be flat inside the grey
      band. If it is not, that window is now the evidence.

## Round 7 (owner answers 2026-08-05, night — Controls FIX accepted)

- [x] 23. ICONS — the whole proposal page accepted by the owner. 40 new faces
      (set now 97), moved into `client/icons.js`; the desktop editor parses
      that file. Wired onto every command in actions.json. DONE 0.0.198.
- [x] 24. REGION — free-size/free-position frame, captured and pasted at once
      (owner: "odmah lepi"). `client/region.js` + `.rg-*`; server unchanged —
      `screenshot {x,y,w,h,paste:true}` already crops any rect. Phone audit
      case added + self-tested (planted 620px button -> portrait FAIL ->
      removed -> PASS). DONE 0.0.198.
- [x] 25. CLAUDE app set — `title` match beside `process` (Layout keeps the
      window's own title, renames cannot break it), per-app-set ticks in the
      Sets picker, and the TYPED command kind: `paste_text {text, enter}` ->
      clipboard.copy_text + Ctrl+V + Enter. Usage / Model / Thinking / Stop on
      the D-pad; Menu types "/" without Enter. Gate case pins the order.
      DONE 0.0.198.
- [x] 26. RENAME any button of any shipped set (owner's new requirement — the
      side buttons carry whatever the user's driver assigned). Name field live
      on built-in rows, empty = back to ours, merge_shipped_pools carries
      renames by command ID. Round-trip probe PASS. DONE 0.0.198.
- [x] 27. Image dropped from the Attach pool. DONE 0.0.198.
- [x] 33. "The PC calls you" (owner go + refinement 2026-08-05: several
      agents run at once, so the notice must NAME the one that finished —
      "ime agenta je ime sesije"). DONE 0.0.206, ROADMAP Phase H1:
      setup/agent_hook.py (Claude Code `Stop` hook, self-installing, names the
      agent and never fails the turn) -> POST /notify -> server/notify.py ->
      `notify` frame -> client/notify.js -> Android notification TAGGED with
      the agent + TextToSpeech + toast. Notifier.kt does the Android half.
      Evidence: NOTIFY GATE 11/11 (bad token refused, no-phone answered not
      queued, two agents = two banners with their own tags, spoken line names
      the agent, hook naming rule), wired into build.py fail-closed; APK
      built so the Kotlin is proven to compile.
      STILL OWED (H2): the desktop BUTTON that installs the hook — the end
      user must never type a command. It waited only because main_window.py
      was being rewritten by the parallel session.
- [x] 33b. Thinking button (owner correction with the screenshot): `/effort`
      takes a level, so the button now types it WITHOUT Enter and the level is
      picked from the chooser with the cursor. DONE 0.0.206.
- [x] 34. DONE — the round close both rounds were waiting for. One release
      carries them: v0.0.081,
      https://github.com/UVuruna/Remote-User/releases/tag/v0.0.081
      (APK 0.0.081 + signed exe and installer). Built from the tree that has
      BOTH rounds in it, with every gate green on the committed state: guards
      4/4, INPUT GATE 19/19, PRESENCE GATE 14/14, NOTIFY GATE 4/4, Qt layout
      audit 4/4, phone layout audit 19/19.
      Note for round 7: 0.0.206 went out missing its own call sites — the
      topmost round had staged those three shared files and de-staged the
      in-flight hunks to keep HEAD compilable. 0.0.208 put the wiring back and
      the release contains it. Nothing was lost.

## Round 8 (owner report + questions 2026-08-05, night)

- [x] 35. PROBLEM: "zašto je WIN u MOUSE i nema RIGHT CLICK" — FIXED 0.0.210,
      my regression. `_select` called setCurrentCell BEFORE invalidating the
      detail form, and that signal fires synchronously, so the handler wrote
      the PREVIOUS set's command into the NEW set's pool at the old row index
      (Windows' Win sat at row 1; Mouse's row 1 is right). Harmless until this
      session allowed renaming shipped sets. Fixed twice: invalidate before
      the signal, and the form now remembers WHICH set it belongs to.
      Evidence: tests/test_controls_sets.py, self-tested by re-planting the
      shipped code — "set switching rewrote these pools: Mouse".
- [x] 36. "Zašto je nestao VSCode kad si ubacio Claude" (editor half) — FIXED
      0.0.210: merge_shipped_pools keyed app sets by PROCESS and both VSCode
      and Claude are `code`, so Claude merged on top of VSCode. Keyed by NAME
      now; a corrupted user copy repairs itself (a stale `active` is dropped).
      The PHONE half (the wheel's cap of 8 with two app sets) is the parallel
      session's — they added the per-set cap check in panels.js.
- [x] 37. Thinking = a CHOICE, not a command (owner idea: "u centar da
      prikažemo opcije pa korisnik odabere") — DONE 0.0.211: a pool command
      may carry `options`; the phone shows them centred and one tap sends the
      finished `/effort xhigh` + Enter. Generic, not a Claude special case.
      Evidence: 2 new checks in the NOTIFY GATE + a layout-audit case.
- [x] 38. Sets picker grouping + group NAMES (his item 2) — DONE 0.0.214
      (the session the owner's slika 1 actually shows is the DESKTOP editor
      list): three sections Standard / App-aware / Custom with heading rows,
      row↔entry map so a heading can never be selected, real vscode/chrome/
      explorer icons; the phone's picker keeps its own named app-group heading
      and now counts app sets against the cap (0.0.213). Evidence: offscreen
      smoke rows map [None,0..8,None,9..12,None,None]; guards + layout audits
      green; shipped in v0.0.082.
- [x] 39. Arrangement section (his item 3) — already done by the parallel
      session (title shortened, "D-pad (landscape)" / "Stack (portrait)",
      Default button moved below). Not duplicated.
- [x] 40. Round close — DONE: full desktop build (INPUT/PRESENCE/NOTIFY
      gates green, signed exe + installer, APK bundled) and GIT RELEASE
      v0.0.082 published:
      https://github.com/UVuruna/Remote-User/releases/tag/v0.0.082

## Round 10 (owner report + questions 2026-08-06 — "zašto mi se ne pokazuje Claude controls")

- [x] 41. WHY THE CLAUDE SET NEVER SHOWED — root cause PROVEN by probing his
      own PC, not reasoned: Claude Code names its VSCode tab after the
      CONVERSATION ('Ispravka UI dizajna meni…'), the word "claude" appears
      nowhere, the UIA ClassName is identical to the 'prompt.txt' tab beside
      it, AutomationId/HelpText are empty, and a walk of the extracted
      window's whole tree (20 elements) finds no "claude"/"anthropic" —
      VSCode hides webview content from accessibility. The title test could
      NEVER have fired for a conversation; it only ever matched CLAUDE.md,
      the document case he banned. FIXED by the owner's own tick:
      Layout.app_sets, chosen in the creation panel (pre-ticked from the
      process, so only Claude needs a tap) and changeable from the layout
      list's pencil; layout_create.app_sets + layout_apps + layout_state.
      Evidence: test_app_set_wheel case "the layout's own ticks win over the
      title guess" pins his real title.
- [x] 42. WHY NINE COULD BE TICKED (his item 2, cap of 8 confirmed as LAW) —
      two sources found: (a) the cap was tested only at the moment of a tap,
      so prefs and defaults arriving another way sailed past it —
      enforceWheelCap() normalizes the stored state and the phone toasts what
      gave way; (b) the SHIPPED actions.json had seven categories enabled
      under a two-slot reserve = nine — Cursor is off by default now. The
      desktop Controls editor was claiming app sets are free (its own line
      from 08-05, reversed by him on 08-06) and now counts the same
      per-process reserve. Victim order is his rule: app set first, then the
      last optional basic. Evidence: two new guard cases, self-tested by
      re-enabling Cursor ("ticks 9 sets by default").
- [x] 43. THE LIVE BADGE (his item 3) — the app rows now carry "ON THE WHEEL
      NOW" for the sets matching the focused layout; tick = allowed, badge =
      riding. Updated in place (rebuilding the card would re-arm the
      ghost-click armor and swallow the next tick). Both tick paths made to
      write-then-measure — they disagreed before. Phone audit measures the
      picker at its fullest with two badges lit; self-tested with a 210px
      badge padding failing at both orientations.
- [x] 44. NOTIFICATIONS DON'T WORK EITHER (his follow-up question) — correct,
      and the cause was not the code: agent_hook.py was never registered in
      ~/.claude/settings.json. Installed for him this round, and ROADMAP H2
      closed — the Settings card carries "Tell my phone when an agent
      finishes", reading the REAL hook state, copying the script out of the
      bundle and naming a real python when frozen (and SAYING so when the PC
      has none).
- [x] 45. STRUCTURE LAW — controls.js hit 1000 lines mid-round; the
      composition rules became client/sets.js (about + flow + client index +
      load test order + docs coverage tier).
- [x] 46. Round close — APK 0.0.085 + full desktop build (INPUT + PRESENCE +
      NOTIFY gates, PyInstaller smoke test, signed exe and installer) and
      GIT RELEASE published:
      https://github.com/UVuruna/Remote-User/releases/tag/v0.0.085
      TWO-SESSION NOTE: the parallel session took 0.0.223 and shipped v0.0.084
      while this round was in flight, so my five commits were renumbered to
      0.0.230–0.0.235 before anything was pushed. Two files that were NOT
      mine (.claude/settings.json, e.txt) were swept into a `git add -A` and
      taken back out — staged files belong to whoever owns the change.
      OPEN ON THE OWNER'S DEVICE: install v0.0.085, make the Claude layout,
      tick Claude in the creation panel, and the Claude set must be on the
      wheel beside VSCode. Then open Settings → Sets: the counter must read
      8 of 8, never 9, and the two live sets must wear the badge.

## Round 11 (owner's two screenshots + his mid-turn message, 2026-08-06)

- [x] 47. OVERLAP WITH THE UPDATE BUTTON (screenshot 1) and OVERLAP AT THE QR
      (screenshot 2) - ONE bug: the declared minimum was measured once, at
      construction, and an explicit setMinimumSize makes Qt stop enforcing the
      layout's own minimum. The update button (hidden until GitHub answers) and
      the notify caption (three lines when it reports a failure) arrive later,
      so their rows had nowhere to go and were painted over the QR and its
      link. `_settle_minimum` is callable any time now, `_content_signature`
      decides when, `showEvent` settles on every show, and `_resettle` refuses
      to measure while the window is in the tray (a second hole: a hidden child
      reports invisible, so closing to the tray looked like a content change
      and re-measured a floor with no update button in it).
      EVIDENCE: the audit reproduces the bug at 43 px - "CLIPPED MainWindow:
      has 820x837, needs at least 618x880" - and passes at 869x880 with the
      fix; the tray path is its own registered case, self-tested the same way
      (869x837 against a needed 880). Commits 0.0.250, 0.0.254.
- [x] 48. NOTIFICATIONS CANNOT BE SWITCHED ON in the installed app - the root
      cause was NOT the switch's code: setup/agent_hook.py was never in
      PyInstaller's --add-data, so the frozen app resolved it under
      _internal\setup and failed with [Errno 2]. Bundled now; a PAYLOAD GATE
      fails the build when any BUNDLE_DIR path is missing (the smoke test
      could never catch this - it imports the module graph, not the data); and
      a missing script is reported as the APP being broken, in plain language,
      with the path left in the log.
      EVIDENCE: dist/RemoteUser/_internal/setup/agent_hook.py exists in this
      round's build. Commit 0.0.251.
- [x] 49. THE CHECKBOX IS VISUALLY UNACCEPTABLE - correct: a QCheckBox had no
      QSS rule at all, so it took the base QWidget rule and carried the
      WINDOW's surface0 into the surface1 card. Transparent label now, and an
      indicator that is the same control surface as a combo, accent-filled
      when on, wearing a DRAWN tick (assets/check.svg, bundled and verified in
      the build).
      EVIDENCE: the window rendered offscreen to PNG and inspected as an image
      - an audit cannot see a colour. Commit 0.0.252.
- [x] 50. THE TICK BESIDE THE SELECTED SETS - delivered. Every set row carries
      it at the right edge (CHECK_ROLE + SectionDelegate._paint_tick, drawn,
      never a font glyph), in a reserved 22 px column so no name can be
      painted under it; app sets wear none, because they ride with a focused
      layout and not on their own.
      EVIDENCE: the list rendered to PNG and inspected - six Standard sets
      ticked, three not, App-aware clean; the editor's declared minimum grew
      by exactly those 22 px. Commit 0.0.253.
- [x] 51. Round close - full desktop build (INPUT + PRESENCE + NOTIFY gates,
      payload gate, PyInstaller smoke test, signed exe and installer) and GIT
      RELEASE published:
      https://github.com/UVuruna/Remote-User/releases/tag/v0.0.086
