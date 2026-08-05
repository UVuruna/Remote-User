# Session Tasks — 2026-08-05 (owner-defined, enforced by the root Stop hook)

ISPORUKA (round 5): kod = arrangement-ladder fix, portrait ordinals, mouse
side buttons, Settings pool cleanup · dokument = icon proposal page + answers
on Image/Gallery, Region and a Claude app set · build + GIT RELEASE rides the
END of round 5 (a parallel session holds uncommitted work in this same tree —
client/quality.js, web.py, style.css — so a build now would package their
half-finished state).

WAITING_ON_OWNER: yes

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

- [ ] 1. Mic (Input set) non-English recognition — REAL debugging, not
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
- [ ] 23. Icons for the commands that have none (owner 5) — proposal page
      published (35 icons + Btn 4/5 + Region + a Claude set preview), each
      drawn as the real 58 px button next to its text-only alternative.
      WAITING on the owner's rejections; the accepted ones go into
      `ICONS` + `actions.json` in one pass.
- [ ] 24. Region (owner 3) — free-size/free-position rectangle on the phone,
      that crop pasted on the PC (Snipping-Tool equivalent). Server side is
      already there (`screenshot {x,y,w,h,paste:true}` crops any rect), so it
      is a client-side selection overlay reusing the aspect panel's drag
      mechanics. WAITING on the owner's yes.
- [ ] 25. Claude app set (owner 6) — feasible; answer delivered. Needs (a) a
      title/tab matcher next to `process` in `app_sets` so the set appears for
      a Claude window inside VSCode, (b) a new button kind `text` (type a
      slash command + Enter — the commands he named are not chords), (c) the
      Sets picker listing app sets one by one instead of one master toggle.
      Two app sets showing together already works (`visibleAppSets` filters,
      it does not pick one). WAITING on the owner's yes.
- [ ] 26. Round close — build + GIT RELEASE once 23–25 land (single release
      for the whole round; the parallel session's tree state is the reason
      this turn did not build).
