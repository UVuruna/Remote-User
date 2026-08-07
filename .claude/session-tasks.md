# Session Tasks — 2026-08-05 (owner-defined, enforced by the root Stop hook)

WAITING_ON_OWNER: no   (round 15 — he gave the one word the board was waiting
for: R1–R7 all run, this session COORDINATES them, and he answered the three
questions that changed the work. Building.)

## Round 15 (owner 2026-08-07 — "ti si agent koji vodi ovaj posao: da angažuje
## druge agente, da ih proverava, i na kraju da me obavesti kada se sve završi")

His order, in his words: this session does not build R1–R7 by hand — it HOLDS
them. It dispatches agents, verifies what they bring back, and reports once, at
the end. Plus one new request of his own: the GRID choice on the phone must be
made by LOOKING at a drawing, never by reading a word (UV/grid_variations.png —
his own sheet: landscape | portrait columns, 2 · 3 · 4 rows).

HIS THREE ANSWERS this turn (the questions the plan page left open):
  P1  stream quality (Monitor/Resolution/Bitrate/FPS) MOVES into Settings
  P4  the phone's theme is chosen on the DESKTOP only — one source of truth
  release  ONE release, at the very end of all seven rounds — not one per round
P2 (gamepad mappings), P3 (both Traffic spans) and P5 (the set palette) go by
the recommendation, as he said they should where he does not object.

The build order is his R1–R7 with ONE change, and the reason is in the record so
no later round reads it as drift: R3 (themes) runs AFTER R4 and R5, because a
theme is applied application-wide and must find Settings, Traffic and the
Controls editor in their final shape — otherwise the same windows are painted
twice and the second painting is the one that is graded.

- [ ] 85. R1 — focus C + A (agent, running). C = chunked type_text with a
      foreground re-check between chunks, so a steal mid-sentence costs zero
      characters; A = SetWinEventHook(EVENT_SYSTEM_FOREGROUND) on its own
      thread, ms reaction, the 0.25 s poll staying as the backstop. Gate:
      tests/test_focus_guard.py, defect-planted.
- [ ] 86. THE GRID IS A PICTURE (his new request, agent, running) — the
      creation panel's count ("Only one / Two / Three / Four") and the
      orientation ("Portrait / Landscape") were WORDS; they become drawings from
      his sheet, and the sketch's outer box now differs by orientation (wide vs
      tall) so a landscape three and a portrait three are told apart at a
      glance, not by which chip is lit.
- [ ] 87. R2 — the desktop SETTINGS window (agent, running): Stream (moved, P1)
      · Notifications (the phone-notice switch moved off the main window, speak
      on/off, voice from the phone's own TTS list via a new `tts_info` message,
      tempo) · Focus (the B switch, default OFF, no SPIF_UPDATEINIFILE, ledger +
      next-start repair, in its own module) · Startup (update check — it existed
      in code with no UI — and a real Task-Scheduler autostart switch). Main
      window: icon buttons, no "…". Gate: 4th window in the Qt layout audit.
- [ ] 88. R4 — TRAFFIC (agent, running): "Od starta" + "Sve (iz fajla)" spans
      downsampled to a point per pixel keeping average AND max, Y gridlines on
      the 1/2/5×10ⁿ ladder with labels, X time labels, hover crosshair with the
      time to the second and both rates. QPainter only.
- [ ] 89. R5 — WHEEL ORDER (agent, running): the ladder in the Controls editor,
      top = 12 o'clock then clockwise, stored as `wheel_order` in actions.json,
      preserved across updates by merge_shipped_pools, non-riding sets leave no
      hole, unknown sets go last, the cap of 8 unweakened.
- [ ] 90. R3 — THEMES (next wave): desktop dark/light applied app-wide with the
      sun/moon switch; Android dark/light/colored × transparent/full + per-set
      colours, all chosen on the desktop (P4) and carried in `config.ui`.
- [ ] 91. R6 + R7 — GAMEPAD (last wave): the shell's KeyEvent/MotionEvent
      bridge, D-pad = left group, △◻○✕ = right group, L2/R2 = Layout (+)/Hide,
      sticks = cursor/scroll; then L1/R1 hold-and-point wheel selection, short
      L1/R1 = layout ‹ ›, Start/Select, on-screen feedback.
- [ ] 93. THE GHOST CLIENT — a LIVE failure on his machine, found mid-round from
      his own log while he was reporting a juddering mouse (agent, running).
      HIS EVIDENCE, %LOCALAPPDATA%/RemoteUser/server.log:
        14:22:50 Client authenticated · 14:22:52 "H.264 session opened — 2
        active" (ONE phone) · 14:45:46 "Phone left (lock)" → "closed — 1 active"
        · 14:45:47 … 16:07 "Client stream backlog — resetting the H.264 session"
        every ~7 s, 1890 times since 12:16, with NO "Client authenticated" line
        anywhere after 14:45:46.
      So the PC has been encoding 4K H.264 in a restart loop for an hour and a
      half for a client that does not exist: RemoteUser.exe 21,336 s CPU,
      ffmpeg 12,043 s. Two questions, possibly two causes: why ONE phone counts
      as TWO active sessions (the 4409 one-device rule and the "encode only
      while ≥1 client" rule both read that count), and why the backlog-reset
      path loops forever on a socket that is gone. Fix at the root + a
      fail-closed regression test that ends a connection every way it can end
      and proves the count returns to zero. Feeds task 83 (queue latency).
      PROCESS NOTE, mine, per THE REPEAT LAW: when he asked whether our agents
      were blocking his mouse I named PID 28016 (`main.py --no-browser --port
      8843`) as our leftover dev server and gave him a kill command. That was
      FALSE — `server/main.py` parses no arguments at all; the process was not
      ours. The R2 agent caught it, not me. I asserted from a plausible name
      instead of checking the one file that would have settled it, and the cost
      was a wrong instruction on his own machine. The rule that failed is the
      one already in the books — verify before claiming — and the cheap check
      is: a process is ours only if OUR entry point accepts those arguments.
      AND THE ANSWER CAME FROM THE AGENT, NOT FROM ME. The R1 agent volunteered
      it: to size `TYPE_CHUNK_CHARS` it benchmarked the REAL `SendInput` —
      ~200,000 mouse events and ~100,000 key events over ~2.5 minutes, into his
      live session, at the time he complained. THAT is the frozen, juddering
      mouse. The ghost client (task 93) is real and burns his CPU, but it is a
      second fault, not this symptom. The process hole: agent briefs forbade
      touching his desktop only AFTER he complained, and nothing forbade an
      ad-hoc measurement script — a gap the standing rule now closes (fake the
      Win32 layer; a real measurement needs HIS window of time first).
- [ ] 94. THE CLAUDE SET STILL DOES NOT APPEAR — his report, v0.0.092, with his
      screenshot: a layout made from a VS Code window running a Claude Code
      conversation shows the VSCode set on the wheel and no Claude set. A
      REPEAT across four or five releases ("zašto se stalno vrtimo u krug
      između program zna i program ne zna").
      THE PROCESS CAUSE FIRST, per THE REPEAT LAW, and it is not in the
      detection code at all — it is in WHICH FILE we proved it against:
        shipped actions.json (repo), Claude app set:
          {"process":"code","title":[…],"name":"Claude","icon":"claude","agent":"claude"}
        HIS live file, %LOCALAPPDATA%/RemoteUser/actions.json, mtime 2026-08-06 19:55:
          {"process":"code","title":[…],"name":"Claude","icon":"claude"}   ← no `agent`
      `agent: claude` is the switch that turns on process-table detection. His
      copy does not have it, so on his PC the set can only match by TITLE — and
      his title is "…grid skice - Remote User - Visual Studio Code
      [Administrator]", which cannot ever contain the word, because Claude Code
      names its tab after the CONVERSATION. An unsatisfiable condition.
      WHY EVERY ROUND SAID IT WORKED: the user copy is seeded ONCE at first
      install; `_merge_shipped_actions` / `merge_shipped_pools` refresh command
      POOLS, never NEW FIELDS on an existing set. Every test, every guard and
      every agent read the REPO's file, which has the field. Green here, dead
      there. This is the SAME engine already recorded in CLAUDE.md as the root
      of "Settings still shows Anywhere after an update" — so a KNOWN class was
      allowed to bite again, which is the process failure proper.
      IT WAS ABOUT TO BITE A SIXTH TIME: today's `wheel_order` (task 89) is a
      new TOP-LEVEL key; his file has none and the merge would not add it.
      THIRD, INDEPENDENT: `server/agents.py` keys on `claude.exe --resume=<id>`.
      Read off his machine today, extension anthropic.claude-code-2.1.223 runs
      `claude.exe --output-format stream-json …` and `--claude-in-chrome-mcp` —
      NO `--resume` anywhere, so even with the switch on, detection would limp
      on the 30-minute recent-transcript fallback.
      Fix in flight: a migration that carries new FIELDS and TOP-LEVEL KEYS by a
      stated ownership RULE (not a list of today's names), detection that does
      not depend on one flag, and a gate that runs the merge over a file shaped
      like HIS instead of over ours.
- [ ] 95. THE NOTIFICATION MUST ARRIVE WHILE THE PHONE IS IN HIS POCKET —
      task 82's build, and HIS DECISION WAS ALREADY GIVEN. Quoted, not
      paraphrased, from his transcript 2026-08-07T12:20:18Z (066d3fc9):
        "STAVKA 12 — notifikacija: zašto je apsurd i šta ga rešava
         A. Radimo taj mali servis — samo je važno da ta komunikacija koja mora
         da bude u pozadini bude minimalna … android strana čeka signal, ne
         prima ništa od kompjutera, ali ostane u stanju čekanja signala."
      So: the Android FOREGROUND SERVICE, not FCM — and with his own
      implementation constraint attached: the background channel is MINIMAL,
      the phone WAITS for a signal and receives nothing else. His battery
      concern is on the record too (2026-08-04T22:56 — "potrošio je dosta
      baterije"), which is why the waiting channel must be idle, not a stream.
      The rest of his spec, gathered from his own words: the notice names WHICH
      agent finished (2026-08-05T17:28 — several run at once, a bare beep says
      nothing; the agent's name is the session's); it is DOUBLE — spoken aloud
      AND a real entry in the notification tray (2026-08-06T16:19); voice and
      speaking pace are chosen in the desktop Settings (2026-08-06T18:59, built
      in R2, task 87).
      THE PROCESS CAUSE, per THE REPEAT LAW: task 82 still read "needs his
      choice … nothing built" although his choice had arrived THAT SAME DAY at
      12:20, in a transcript on this disk. The round that wrote the note had the
      answer in front of it and did not read it — and this session then trusted
      the note over his words and asked him a second time, which is what he
      exploded at ("svaku odluku moram da pričam 15 puta"). The rule this
      creates: an owner decision enters the record as a DATED QUOTE, never as a
      summary, and a task that claims to be waiting on him must name the message
      it is waiting for.
- [ ] 96. WHAT THE TWO INDEPENDENT GRADERS FOUND — and the reason the gate exists.
      Every implementer this round graded their own work and every one of them
      passed themselves. Two graders who wrote none of the code then failed
      TWELVE screens, and the second one MEASURED instead of asserting:
        · Traffic legend: both swatches sampled (168,179,197) — byte-identical,
          and that value IS the caption colour, in front of a two-colour chart.
          The window's whole subject is two directions and the legend refused to
          say which was which. FIXED (9/10 both palettes, hover shot produced
          with real data because the audit fixture is 0 B/s and the chart was
          EMPTY in every graded picture).
        · ControlsEditor on light: every QLineEdit paints (237,239,247) on a page
          of (236,238,246) — ONE unit per channel. The owner sees the word
          "Claude" floating on bare page with nothing to click into. Same root as
          R3's disabled-button bug: an elevation rule written for dark.
        · The combo caret is a solid 10×10 BLOCK, not a triangle, in every combo
          of three windows — the QSS uses the CSS border-triangle trick and Qt's
          subcontrol renderer silently does not draw it. Same class as the ✥ that
          came out a blunt cross on his phone.
        · ControlsEditor: ten of thirteen commands behind a scrollbar beside
          ~480 px of empty column. THE LAW'S OWN PICTURE — and the audit CANNOT
          see it, because its SCROLL+SLACK check counts only `QSpacerItem` while
          this slack is a stretched widget. The blind spot is being fixed with
          the window.
        · COLORED theme measured WORSE than plain dark on the same words: 2.66:1
          and 2.75:1 against dark's 4.22:1, where AA wants 4.5:1. The D-pad fill
          is a 20% TINT that composites dark over his dark screens, while the ink
          was computed for the SOLID colour. The wheel proves the rule is right
          when the fill really is solid (8.74:1).
        · The dictation card breaks BOTH columns at once while 60 px sit unused
          between them and 225 px stand empty above the card.
        · SettingsWindow prints a raw `OSError` repr where its plain-language
          sentence belongs — naming the INSTALLED path, so it is what HE sees,
          and it likely means the notification switch refuses to turn on.
      THE PROCESS FINDING: a self-graded picture is not proof, and this round is
      the evidence — eleven implementers, eleven passes, twelve failures found by
      two outsiders. Second: the graders refused to grade pictures they had not
      caused to be written, which is the only correct response to the tofu
      discovery (task 92) — a full guard run had been writing FONTLESS
      screenshots, so "I opened the picture" could mean opening empty boxes.
- [ ] 96. THE KEYBOARD MUST FOLLOW THE CARET, NOT A RULE (owner 2026-08-07,
      after living with both halves of his own earlier decisions). His problem,
      stated exactly: when he types into a box at the BOTTOM of the PC screen he
      wants the keyboard to lift the picture so that row stays visible; when the
      box is at the TOP, lifting carries the very text he is watching off the
      screen. "Dakle nijedna opcija nije idealna ni da tastatura gura naš layout
      ... niti da ga prekriva. Zato bi najoptimalnije rešenje bilo da naš program
      prepozna gde se nalazi koja je pozicija na ekranu kursora koji kuca."
      THE ANSWER IS AVAILABLE AND NOBODY LOOKED: the PC knows where the caret is
      — `GetGUIThreadInfo` gives the caret rect of the foreground thread, and UI
      Automation gives the selection/caret bounding rect; `server/uia.py` and the
      focus guard already know WHICH window is being typed into. So the server
      can send the caret's position and the phone lifts ONLY when the caret would
      actually be covered, and ONLY by the difference — never by the keyboard's
      full height, which is what made the 2026-08-03 attempt intolerable and got
      it withdrawn on 2026-08-07 (task 80, `kbShift = 0`).
      HIS REFINEMENT, mid-turn, with a screenshot — and it is the half a naive
      implementation gets wrong: the previous attempt moved EVERYTHING, "zaključno
      sa ovim delom koji nije deo naše aplikacije" — the navy filler above and
      below the region, which exists because a layout narrower or shorter than the
      phone letterboxes. Only the PICTURE may move; the filler stays. "Poenta je
      da tastatura kada pomera sa offsetom ne pomera taj prazan deo već pomera
      samo vidljivi ekran gde se nalazi aplikacija, i to samo ako ima potrebe."
      His fallback, to be built as well, for apps that expose no caret (some do
      not): a switch in Settings — lift the picture / cover the picture — which
      decides what happens when the PC CANNOT say where the caret is. So he is
      never left without a way out.
      Scheduled AFTER this release, deliberately: it is a new feature and the ten
      finished things must reach his hands first.
- [ ] 92. The independent VISUAL PROOF of every window and panel this round
      touches (rules/GUI.md — a grader that did not write the code, ≥ 8/10),
      then guards, ONE build and ONE GIT RELEASE, then the final report.

## Round 14 (owner 2026-08-07, furious — "uvek je prioritet rešiti ZAŠTO je
## došlo do toga u komunikaciji sa agentima, tek sekundarno bag aplikacije")

THE PROCESS FINDING, and it is the whole explanation of the circle he is in.
Not reasoned — read off his own machine this morning:

    installed exe: 0.0.089     built 2026-08-06 19:22:58
    running since  2026-08-06 19:49:58   (never restarted)
    latest release v0.0.090    published 2026-08-06 20:06 local

    his server.log, TODAY 11:35:07:
      File "layout_api.py", line 86, in layout_list
      UnboundLocalError: cannot access local variable 'mon_rect'

Line 86 is the bug that was FIXED in 0.0.290 and RELEASED as v0.0.090 — the
repo's line 93 reads `rect = mon_rect(stream)`. So "create from a list still
does not work" is TRUE on his device and the fix is real: he has never run it.
`main_window._check_updates` is documented "ONE GitHub check per start", his
app has been running since 17 minutes BEFORE v0.0.090 existed, so the update
button could not appear, and it never will until he restarts by hand.

That is the mechanical cause of "I give 10 tasks, the agent says all 10 are
done, half of them are unchanged": we ship, the release is real, and the app
in front of him is from before it. Every following round then re-diagnoses a
fixed bug and burns his week. The code half of the process fix is task 73; the
rule half is task 74.

- [~] 73. THE APP MUST NOTICE A RELEASE WHILE IT RUNS — done 0.0.295, shipped
      v0.0.091. `_check_updates` said it in its own docstring: "one GitHub
      check per start". Now every 15 minutes, never disturbing an update
      already in flight. HIS EVIDENCE for the DEFECT (installed 0.0.089 +
      today's traceback from a line fixed yesterday); the FIX is unseen by him
      until he installs v0.0.091 — which is the last install he has to do by
      hand.
- [x] 74. THE LAW he ordered — root CLAUDE.md law 6 (THE REPEAT LAW),
      rules/PLAN.md → The Session Task List, teeth in
      rules/hooks/session_tasks_guard.py. Self-tested on all four paths:
      REPEAT without PROCESS CAUSE blocked; `[x]` REPEAT without OWNER
      CONFIRMED / HIS EVIDENCE blocked; the same block as `[~]` passes; `[x]`
      with his evidence passes. Nothing here waits on his device.
- [~] 75. THE DICTATION SPAM — done 0.0.293, shipped in APK 0.0.091.
      REPEAT of task 61 (the rescue copy, "nothing spoken is thrown away").
      PROCESS CAUSE: that round added a rescue copy and tested that a dying
      round types what it heard. It never asked what happens when rounds die
      four times a second — and it had the answer in the same log it was
      reading. The gap is a class, not an oversight: a feature was tested for
      the case it was written for and for no other, and "the phone types
      something" was proven while "the phone types it once" was never stated.
      HIS EVIDENCE: server.log 11:30:05 → 11:30:12, forty × `Voice error 5
      (online)` = ERROR_CLIENT, and his own two messages to us this morning,
      shredded. Root cause: `startListening` on a still-running recognizer is
      refused with ERROR_CLIENT, the page retries after 250 ms, and every
      refusal ran `deliver(null)` — with cumulative partials, that re-types
      the whole sentence so far. Fixed at both ends (cancel before start;
      `lastOut` trims a rescue to what has not been typed).
- [~] 76. THE CLAUDE SET — done 0.0.294, shipped v0.0.091. He is IN Claude and
      the wheel offers only VS Code.
      REPEAT of tasks 25, 41, 55, 58 — four numbers, four `[x]`, one bug.
      PROCESS CAUSE: his instruction was implemented BACKWARDS and the record
      shows exactly where. Round 11c built the detection he asked for
      (agents.py, 0.0.266) and closed task 58 as "CLAUDE DETECTED". It never
      removed the thing detection replaced. sets.js:88 kept reading
      `if (Array.isArray(lay.app_sets)) return lay.app_sets.includes(s.name)`
      — "a layout that HAS the list is answered from it ALONE" — and the
      creation panel kept writing that list. So detection ran on every state
      frame, said "claude", and was discarded by a copy of an older answer.
      The task's evidence was a guard case named "the layout's own ticks win
      over the title guess": a test that PINNED the defect as the intended
      behaviour. That is the shape of the whole failure — the guard could not
      have gone red, because it was written from the same wrong belief.
- [~] 77. THE SLOW LOAD — done 0.0.294, shipped v0.0.091. `agents.agents_for()`
      was called from the async handlers with NO thread
      (layout_api.py:70/103/112): a 1.85 s PowerShell probe MEASURED on his PC,
      blocking the whole event loop (stream, heartbeats, everything) once per
      entry whose 2 s cache had lapsed — and a slow `uia.list_tabs` between two
      windows guaranteed the lapse. One snapshot per request, in a thread; the
      layout gate counts the probes and fails at two.
      NOT the cause of "create from a list does nothing" — that was
      v0.0.089 (see the header). Measured end-to-end here after the fix:
      1.63 s, 22 entries, one probe.
- [x] 78. Round close — APK 0.0.091 (Kotlin changed) + full desktop build
      (payload gate, INPUT/PRESENCE/NOTIFY/FOCUS/LAYOUT gates, smoke test,
      signed exe and installer, VERIFY FileVersion 0.0.091) and GIT RELEASE
      published: https://github.com/UVuruna/Remote-User/releases/tag/v0.0.091
      Guards 4/4 full, phone layout audit 26/26, app-set wheel 8/8, layout
      protocol 6/6, controls sets, INPUT/PRESENCE/NOTIFY/FOCUS gates green.

His UV/prompt.txt of 2026-08-07, three more (added mid-turn; NOTHING above is
dropped for them):
- [~] 79. THE MOVE HANDLE DOES NOT MOVE — done 0.0.296, shipped v0.0.091.
      REPEAT of task 2 of round 3 (`layout_aspect {pos}` + `Layout.pos` +
      preview drag), closed as DONE 0.0.169 on "guards + load test + INPUT
      GATE pass".
      PROCESS CAUSE: every piece that round built was correct — the protocol,
      the server placement, `dragMove`'s arithmetic — and its tests proved
      exactly that. Not one of them ever DELIVERED A TOUCH to the handler, so
      the two defects that live in the gesture layer were invisible to all of
      them. "The feature is implemented" was tested; "a finger can use it" was
      not, and only the second one is the task.
      TWO real causes, both now reproduced by the audit before being fixed:
      (a) the re-centre fired on `pointerdown` for ANY contact within 350 ms of
      the previous one, so tap-then-drag was read as a double tap — it put the
      region back in the MIDDLE and returned without capturing the pointer, so
      the drag died too; his sentence had both halves in it. (b) `moveTapAt`
      started at 0, a real `performance.now()` reading meaning "a tap at page
      load", so any tap in the page's first 350 ms re-centred. Landscape
      failed on (b) while portrait passed at 623 ms.
      A THEORY THAT DID NOT HOLD, recorded so nobody spends the hour again:
      the first diagnosis was `touch-action` on `.asp-move` (it does not
      inherit). WRONG — `body` declares `touch-action: none` and the
      restriction is cumulative down the tree, so the browser can never claim
      that drag as a scroll. The check written for it could not fail; it was
      thrown away, not kept green.
- [~] 79b. THE MOVE HANDLE STILL DOES NOT MOVE THE WINDOW — his 3rd report of
      the same feature (10:13 portrait, handle dragged to the TOP, preview
      shows it at the top, Apply, and the PC window comes out vertically
      centred: "uvek ostavi centrirano"; measured off his screenshot, the
      window spans 0.195–0.805 of the screen height — exactly centred).
      PROCESS CAUSE, first: round 14 fixed the GESTURE (the double-tap
      re-centre) and proved it with a headless-Chromium check that ends
      `return aspecting.pos === 0.9` — an in-memory VARIABLE. Nothing in it
      ever pressed Apply, so the hop from `aspecting.pos` to the wire was
      still unwalked, and the layout gate's own aspect check asserted
      `layouts[0].pos == 0.25` — a STORED NUMBER — while its `place_window`
      fake threw the rect away. Round 3 measured `_fit_rect`, round 14
      measured the finger, and between them sat the only thing that matters:
      the RECT a window is told to take. Two rounds, two green suites, and
      the feature was never once followed to a window. THE FIX is at that
      exact place: `LayoutRegistry.focus` guarded the rebuild on
      `Layout.arranged_ratio`/`arranged_pos`, a note of what was COMMANDED,
      written before `place_window` was even called and never compared with
      the desk — so once a member left its rect (an app re-laying itself out,
      a restore out of the taskbar, a snap, a placement that did not take),
      every later Apply of the SAME position matched the note and re-placed
      NOTHING: the phone's panel moved, the PC never did again, for good.
      `focus` now computes the targets fresh, asks `_standing()` where the
      windows REALLY are (`grids.at_rect`, ±8 px), and writes the note only
      when the placement LANDED — a refusal is logged, toasted and retried.
      GATE: two new checks in `tests/test_layout_protocol.py` (fail-closed,
      build.py 0f/6) that assert on the placement RECT — solo AND grid,
      portrait AND landscape, pos 0/500/1000, plus the same position applied
      again after the window drifted. Both proven by re-planting the defect.
- [~] 80. THE KEYBOARD MUST NOT LIFT THE VIEW — done 0.0.295, shipped
      v0.0.091. `kbShift` is 0 and the canvas transform is gone: the keyboard
      covers what it covers. The canvas still keeps its FULL height (it is
      never SQUEEZED — that half of his 2026-08-03 request stands).
- [ ] 83. WHY DOES 10 fps FEEL SMOOTHER THAN 30 OR 60? (owner 2026-08-07 — and
      he is asking the right question: "koja je svrha slati toliko velik
      bitrate i mnogo frejmova ako to dovodi do suprotnog efekta"). His mouse
      and his whole session feel SLOWER at the higher settings. Not a taste
      question — a measurement one. The hypothesis to test first is queue
      latency, not throughput: at native 4K the encoder and the Wi-Fi link
      produce more than the phone can drain, the MSE buffer grows, and every
      pointer move is drawn from a picture that is already old — the classic
      bufferbloat shape, where MORE data means a LATER picture. Lowering fps
      shortens the queue, so 10 fps feels immediate while 60 feels like syrup.
      What to measure (the Traffic window already records the bytes): end-to-
      end pointer→pixel latency at 10/30/60 and at full/⅔/½ resolution, the
      MSE buffered-ahead length on the phone, and the encoder's own queue
      depth. Then decide whether the defaults are simply wrong, whether the
      quality panel should present LATENCY rather than fps, and whether the
      client should drop frames to keep the buffer short.
- [ ] 84. R1–R7 — NOT STARTED, and he asked directly. The plan of 2026-08-06
      (focus C+A, Settings window, themes, Traffic spans, wheel order, gamepad
      G1+G2) is tasks 65–71 below. Nothing of it has been built by anyone. R1
      already carries his approval ("odradi kako si predložio, B ostavi kao
      prekidač u settingsu"); R2–R7 and questions P1–P5 do not. He asked
      whether agents should be launched onto them — that is his call and needs
      one word.
- [ ] 82. THE NOTIFICATION ONLY ARRIVES WHEN HE UNLOCKS THE PHONE — his words,
      and he is right that it is an absurdity: "notifikaciji posao je da
      obavesti korisnika kada NE radi to na telefonu, a mi čekamo da korisnik
      otvori aplikaciju i onda mu kao kažemo". DIAGNOSIS (read, not guessed):
      the whole notify path rides the WEBSOCKET — server/notify.py sends the
      `notify` frame to a connected client, and Notifier.kt raises the Android
      notification from inside the page's own process. But the session is
      designed to END when the phone locks (CLAUDE.md constraint 8 — the
      socket closes so nothing hovers over his desk). So at the exact moment a
      notification matters, there is no socket, and the notice is QUEUED (30
      min / 20 deep, task 59) until he opens the app himself. The queue was
      built for "he was away"; it is not a delivery mechanism. This was named
      as an open limitation in round 11c ("with the app fully closed nothing
      arrives AT THAT MOMENT — unless he wants a foreground service"), which
      is exactly what he is now answering: he wants it. Needs his choice
      between a foreground service and FCM push — presented in this round's
      report, nothing built.
- [~] 81. DRAG A LAYOUT ROW — BUILT and shipped v0.0.092, to his four answers
      and his drawing (UV/grid_variations.png). Hold a row, drop ON another =
      a grid of the two and the dragged layout disappears; drop BETWEEN rows =
      reorder. A full four greys out while the drag is in flight. 1+1 and 1+3
      ask nothing; 1+2 becomes a three and he picks one of the four
      arrangements. New: server/grids.py + client/grids.js (the catalogue,
      every shape a DRAWING), layout_grid / layout_merge / layout_reorder,
      the shape in the layout's settings panel, and "wide" renamed to
      "landscape" everywhere. Gate: the audit proves every shape tiles its
      region exactly — no gap, no overlap, no sliver.


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

WAITING_ON_OWNER: yes   (round 13 — the owner APPROVED C+A+B and dropped a
large new batch; per his explicit order the PLAN went first, as a rendered
HTML page. The plan is PUBLISHED:
https://claude.ai/code/artifact/da670d11-4913-454b-9763-66e4851f5b2f
with build order R1-R7 and questions P1-P5 (each with a recommendation);
building starts the moment he confirms — "sve po preporukama" also unlocks
the whole board. No code was touched this turn.)

Round-13 batch (owner 2026-08-06 mid-turn message; plan pending approval —
each round ends in its own build + GIT RELEASE):
- [ ] R1: focus C+A — chunked type_text with a foreground re-check between
      chunks + SetWinEventHook instant refocus (0.25 s poll stays as backstop).
      APPROVED already.
- [ ] R2: Settings window (Izgled / Notifikacije / Fokus / Pokretanje) + icon
      buttons without "…" on the main window + the focus-lock switch (B,
      default OFF, no SPIF_UPDATEINIFILE, ledger + next-start repair) +
      notification voice/tempo/sound-off (phone reports voices via tts_info;
      small APK change in Notifier.kt)
- [ ] R3: themes — desktop dark/light QSS + sun/moon switch (PromptPainter
      pattern) top-right after RUNNING and in Settings; Android
      dark/light/colored × transparent/full + per-set colors via config.ui
- [ ] R4: Traffic — "Od starta" + "Sve (iz fajla)" spans (csv downsampled),
      Y-axis gridlines at nice values, X time labels, hover crosshair with
      time + both rates
- [ ] R5: wheel order — Controls editor ladder, wheel_order in actions.json,
      top = position 1 then clockwise; app sets keep their slot when riding
- [ ] R6: gamepad G1 — shell KeyEvent/MotionEvent bridge (WebView has no
      Gamepad API), dpad→left group, face buttons→right group, L2=Layout,
      R2=Hide, left stick=cursor, right stick=scroll
- [ ] R7: gamepad G2 — L1/R1 hold opens that side's wheel + stick points +
      release picks, short L1/R1 = layout ‹ ›, on-screen button feedback

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

## Round 11b (owner: the fix did NOT fix it, + colours, + Claude, + notifications)

- [x] 52. THE OVERLAP IS STILL THERE ON v0.0.086 — REAL cause found and fixed:
      minimumSizeHint() quotes a WRAPPING label at one line, so the column was
      48 px short (hint 835, truth 883), and Qt spends a shortfall by
      OVERLAPPING, not clipping — every widget reported full size, which is why
      the guard was green. Reproduced at his 125% scaling before the fix
      (qr 17..233, url at 195) and clean after. heightForWidth in one shared
      module (gui/sizing.py); the URL label deleted. Teeth: OVERLAP check +
      REAL-FONT platform, self-tested by stubbing the fix. Commits 0.0.258.
- [x] 53. COLOURS — cause: .sets-row sets no background, harmless on a <label>
      and fatal on a <button> (the WebView paints its own light default under
      near-white ink). Fixed, and the tooth added: WCAG contrast against the
      COMPOSITED backdrop, < 3.0 fails. Self-test: replanted, all six rows
      report 1.05:1. Found two more nobody reported — the live badge at 1.96:1
      (var(--bg) is not a token here). Commit 0.0.259.
- [x] 54. NOTIFICATIONS — answered from HIS log, not from belief: the hook
      fired and the server forwarded (17:30:51 'Remote User · 0eb7cb finished',
      17:33:02 'UVuruna · ed8163 finished', both 200, phone connected from
      17:30:03). The broken link is Android's POST_NOTIFICATIONS: the shell
      asks for it only when the FIRST notice arrives and drops that one
      (MainActivity.kt:816 says so in a comment). He confirmed the same
      evening: it arrived as a toast, not in the notification tray. Two real
      gaps named for the next round: ask the permission up front, and queue a
      notice for a phone that is away.
- [x] 55. CLAUDE — the earlier 'impossible' was WRONG, and proven wrong on his
      own PC: round 10 probed only UIA and never looked at the process table.
      Ten claude.exe processes, each a child of a specific VSCode
      extension-host, each carrying --resume=<session-id>; the session id maps
      to ~/.claude/projects/<slug>, and the slug IS the project path, which the
      window title also carries ('… - Remote User - Visual Studio Code'). A
      deterministic bridge with no ticking. Also found: autoAppSets pre-ticks
      VSCode/Chrome/Explorer already (his 'we went backwards' does not hold),
      but only from slots[0] — a grid's second cell is never pre-ticked. Design
      presented to the owner and WAITING on his go before building.
- [x] 56. Round close — full desktop build (payload gate, INPUT/PRESENCE/NOTIFY
      gates, smoke test, signed exe + installer, VERIFY FileVersion 0.0.087)
      and GIT RELEASE published:
      https://github.com/UVuruna/Remote-User/releases/tag/v0.0.087
      No APK rebuild: the shell embeds no client assets (no android assets dir,
      no file:///android_asset), so the colour fixes are served from this PC.

## Round 11c (owner's go on detection + his tick spec + the notification demand)

- [x] 57. THE TICKS — done exactly as specified: own strip on the LEFT with the
      icon and name indented past it, GREY for `required` (Mouse/Input/Settings,
      not his to switch) and WHITE for the rest. App-aware rows are ticked too,
      and their checkbox is LIVE: the phone already read the same `enabled`
      flag for them (client/sets.js appSetOn), so a blank row hid a working
      switch and a dead box refused an edit the file accepted; a switched-off
      app set also stops charging a wheel slot. Evidence: the set list rendered
      to PNG and inspected — six grey/white ticks where they belong, four on
      App-aware. Commit 0.0.265.
- [x] 58. CLAUDE DETECTED — server/agents.py reads the process table: a live
      claude.exe carries `--resume=<session-id>`, the id names a transcript
      whose `cwd` names the project, and the VS Code title ends in that
      project's folder. Sent as `agents` in layout_state and per layout_offer
      entry; the Claude set claims it with `"agent": "claude"`. His own ticks
      still win. Verified on HIS machine: {remote user, uvuruna, domy watch}
      matched his three titles, "Some Folder - Notepad" matched nothing. Two
      guard cases, self-tested (the PC's "no" outranks a title saying "Claude
      Code"). Honest limit recorded everywhere: one Electron process for all
      windows, so the match is per project FOLDER. Commit 0.0.266.
- [x] 59. NOTIFICATIONS — three fixes. (a) POST_NOTIFICATIONS asked once at app
      START, not when the first notice arrives (which spent that notice on the
      dialog — the code said so itself: "this one is lost; the next lands"),
      and a notice that arrives before the answer is held and posted on grant.
      (b) A notice for an absent phone WAITS: 30 min, 20 deep, delivered
      oldest-first on the next connection, with "8 min ago" appended so it
      never pretends it just landed. (c) The hook says "needs you", not
      "finished" — a Stop hook fires at every TURN end, which is what made the
      owner ask why it said I was done while I was still working. Three guard
      cases, one replacing a name that had become a lie. Commits 0.0.267,
      0.0.269. OPEN, by design and stated to him: with the app fully closed
      nothing arrives AT THAT MOMENT — only on his return — unless he wants a
      foreground service.
- [x] 60. Round close — APK 0.0.088 (Kotlin changed) + full desktop build
      (payload gate, INPUT/PRESENCE/NOTIFY gates, smoke test, signed exe and
      installer, VERIFY FileVersion 0.0.088) and GIT RELEASE published:
      https://github.com/UVuruna/Remote-User/releases/tag/v0.0.088

Round 12 (owner's voice message of 2026-08-06 evening — the URGENT one; the
first paragraph of his message is the evidence itself: a sentence dictated for
another project that landed in THIS session):
- [x] 61. FOCUS NEVER LEAVES THE BOX HE IS DICTATING INTO — server/focus_guard.py.
      Root cause: SendInput has no target — every dictated character went to
      whatever window Windows called the foreground at that instant, so anything
      that took focus mid-sentence took the sentence. Half of it was OURS and is
      in his log (excursions 18:38:56, 18:41:50): a picker closes the socket, the
      page re-focuses the layout, and focus() raised members in LIST order, so the
      keyboard went to the last window of the grid. Fix: the target is decided
      before every typing message (layout = fence, desktop = pin, GW_OWNER dialog
      = the target, thief NAMED in the log), Layout.last_member rides last, and —
      after his second, shouted message — the layout is DEFENDED every 0.25 s by
      focus_guard.watch, because the recognizer delivers a whole utterance only at
      the END of a round. Phone half: VoiceInput keeps a rescue copy of what it
      heard, so a round that dies types it instead of deleting it. Evidence:
      tests/test_focus_guard.py 15/15 (incl. the whole path through the real
      dispatcher), fail-closed as step 0e of build.py. Commits 0.0.280, 0.0.283.
- [x] 63. The tray toast — the "already told" flag lived only in the window
      object, so every start of the app produced it again and a day of starting
      and stopping turned one-time guidance into a toast constantly opening and
      closing. Now a marker file (SETTINGS.tray_notice_path) makes once mean once;
      the footer says the same sentence permanently anyway. Commit 0.0.281.
- [x] 62. Round close — APK 0.0.089 (Kotlin changed) + full desktop build (payload
      gate, INPUT/PRESENCE/NOTIFY/FOCUS gates, smoke test, signed exe + installer,
      VERIFY FileVersion 0.0.089) and GIT RELEASE published:
      https://github.com/UVuruna/Remote-User/releases/tag/v0.0.089

## Round 13 (owner's three questions about the focus defence, 2026-08-06 —
## ANSWER ROUND, nothing built; his choice decides what gets built)

He asked three things about proposals A (SetWinEventHook) and B
(SPI_SETFOREGROUNDLOCKTIMEOUT), and the third one uncovered a real hole in
what shipped as v0.0.089. Answered in chat this session; NOTHING was written
to the codebase, on purpose — the build follows his decision.

WHAT THE ANSWERS WERE, so the next session does not re-derive them:
  Q1 (does B run only while Remote User is on): no — SPI_SETFOREGROUNDLOCKTIMEOUT
  is a per-USER Windows setting (HKCU\Control Panel\Desktop\ForegroundLockTimeout),
  in force for every app until reverted. Our only lever is HOW LONG we hold it
  (while the server runs / while the phone is present / only in layout focus).
  Called WITHOUT SPIF_UPDATEINIFILE it lives in the running session only, so a
  reboot restores his value even if a hard kill beats our ledger.
  Q2 (does it look like a virus): no new detection class from either. A uses
  WINEVENT_OUTOFCONTEXT — explicitly NO code in other processes, the same
  accessibility API screen readers use; B is one documented SystemParametersInfo
  call. What SmartScreen actually objects to is already true and unchanged:
  unsigned binary + elevation + heavy SendInput. Only a bought certificate
  fixes that, and it is out of scope by his no-payment rule.
  Q3 (does the 250 ms steal erase what he dictated): NO for the common case,
  and this was read out of the code, not assumed. The recognizer holds the
  whole utterance ON THE PHONE until the end of a round
  (VoiceInput.kt:372 deliver()), so a steal while he SPEAKS costs nothing, and
  when the text arrives web.py:773 runs focus_guard.guard BEFORE injecting.

- [ ] 64. THE HOLE Q3 FOUND — the guard runs before every typing MESSAGE but
      not INSIDE one. `InputInjector.type_text` (server/input_injector.py:378-385)
      is a per-code-unit SendInput loop with no re-read of the foreground, so a
      600-character dictated sentence is ~20-60 ms during which a thief that
      takes focus gets the REST of the sentence — and injected characters are
      not replayed by anything. Neither the 0.25 s watcher nor proposal A closes
      this; only chunking does. Proposed as option C (guard between chunks of
      ~40 chars; GetForegroundWindow costs microseconds). OWNER APPROVED C+A+B
      ("odradi kako si predložio, B ostavi kao prekidač u settingsu") — this
      task is the C half of build round R1.

OWNER'S BATCH of 2026-08-06 (his long message; his order: PLAN FIRST as HTML —
delivered this turn: https://claude.ai/code/artifact/8e162995-1e65-4eb8-961e-e4bbde6e91c4
Build order R1-R7 lives on that page; questions P1-P5 pending):
- [ ] 65. R1 — Focus C (chunked type_text with foreground re-check between
      chunks) + A (SetWinEventHook EVENT_SYSTEM_FOREGROUND thread, ms reaction,
      0.25 s poll stays as the belt) — server only; gate cases in
      tests/test_focus_guard.py; build + GIT RELEASE.
- [ ] 66. R2 — the desktop SETTINGS window (server/gui/settings_window.py, 4th
      window in the Qt layout audit) + icon buttons WITHOUT "…" on
      Controls/Traffic/Settings (SVG icons in assets/, never font glyphs) + B
      switch ("Ne daj aplikacijama da otimaju fokus", default OFF, no
      SPIF_UPDATEINIFILE, ledger + next-start repair) + Notifications section:
      speak on/off (notify frame `speak` — no APK), voice picker (phone reports
      voices via new Android.ttsVoices bridge + one message), tempo
      (setSpeechRate — APK). Answered his "šta još pripada tu": update_check
      (exists, no UI) + autostart Task-Scheduler switch (reads real state);
      `hand` stays buried (dead since 2026-08-02). Build + APK + GIT RELEASE.
- [ ] 67. R3 — THEMES. Desktop: dual palette in theme.py (light proposal on
      the plan page), applied app-wide so every window/submenu follows;
      Day/Night switcher top-right AFTER the RUNNING pill + a row in Settings;
      PromptPainter-pattern transition (snapshot cover fade ~300 ms + knob
      slide ~600 ms). Android: dark/light/colored × transparent/full via new
      `config.ui` field (server-side user settings; page applies CSS vars;
      prefs-cached against first-paint flash; NO APK); colored = per-set
      preset colors editable in Settings (palette proposed on the page, P5);
      ink by luminance; the phone audit's WCAG contrast tooth covers it.
      Splittable R3a desktop / R3b android. Build + GIT RELEASE.
- [ ] 68. R4 — TRAFFIC: spans "Od starta servera" + "Sve iz zapisa" (read
      traffic.csv, minute buckets; csv already appends every sample, rotates
      at 20 MB); Y gridlines at nice steps (1/2/5×10^n) with labels; hover =
      crosshair + tooltip (time to the second, both directions, "niko povezan"
      inside the grey band). QPainter only. Build + GIT RELEASE.
- [ ] 69. R5 — WHEEL ORDER: "Točak" ladder in the Controls editor (reuses
      OrderList) — top of list = 12 o'clock, then clockwise; stored as
      `wheel_order` in actions.json; merge_shipped_pools preserves it; client
      sets.js sorts; non-riding sets skipped, unknown new sets appended;
      default = today's order. Build + GIT RELEASE.
- [ ] 70. R6 — GAMEPAD G1: shell captures controller input (dispatchKeyEvent /
      dispatchGenericMotionEvent, SOURCE_GAMEPAD|JOYSTICK — WebView has no
      reliable Gamepad API) → bridge to page; D-pad = LEFT group's 4 buttons,
      face △◻○✕ = RIGHT group's (top/left/right/bottom), presses run through
      the SAME on-screen button code so CLICK/HOLD holds; L2 = Layout (+),
      R2 = Hide (his spec); left stick = cursor (deadzone+expo), right stick =
      scroll (P2 proposals). INPUT GATE cases with synthetic pad events; APK;
      build + GIT RELEASE.
- [ ] 71. R7 — GAMEPAD G2: L1/R1 hold opens that side's wheel, stick points
      (frame around the set), release picks (his spec); L1/R1 tap = layout
      ‹ › ; Start = Keys, Select = layout list; L3 = double click, R3 = middle
      (P2 proposals); on-screen buttons light when the pad presses them. APK;
      build + GIT RELEASE.
- [ ] 72. Questions P1-P5 on the plan page await his verdicts (each carries a
      recommendation): P1 stream combos move into Settings? · P2 gamepad
      proposal mappings · P3 both long Traffic spans? · P4 phone theme changed
      from desktop only? · P5 the set-color palette. "Sve po preporukama"
      resolves all five.

Round 12b (mid-turn, furious — a REGRESSION he hit while this round was closing):
- [x] 64. "layout, kreiraj iz liste, nista se ne desava" — the loading cube spun
      forever. ROOT CAUSE from his own server log, three times over:
      UnboundLocalError at layout_api.py:86, `mon_rect = mon_rect(stream)` — the
      module's own function name assigned to, so it became a LOCAL for the whole
      function and the call on the right raised before a byte was sent.
      Introduced in 0.0.266 (the app-sets/ticks round), shipped in v0.0.088 and
      v0.0.089. Fix: `rect = mon_rect(stream)`. The real finding: the phone's
      ENTIRE layout protocol had no test — tests/test_layout_protocol.py now
      drives every layout message through the real dispatcher (build step 0f),
      self-tested by replanting the defect. Commit 0.0.290, released v0.0.090.
