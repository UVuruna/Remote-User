SESSION: 066d3fc9-cfb7-44af-bbf2-910437cf5930
RELEASE: https://github.com/UVuruna/Remote-User/releases/tag/v0.0.091

- [~] 73. THE APP MUST NOTICE A RELEASE WHILE IT RUNS — SHIPPED, unconfirmed — `main_window._check_updates` said it in its own docstring: "one GitHub check per start". His installed exe is 0.0.089, running since 2026-08-06 19:49:58; v0.0.090 was published at 20:06 — seventeen minutes later, into an app that had already asked. Now a 15-minute QTimer that never disturbs an update already in flight. HIS EVIDENCE proves the DEFECT (installed binary + today's traceback from a line fixed yesterday); the FIX is unseen until he installs v0.0.091 — the last install he has to start by hand. Commit 0.0.295.
- [x] 74. THE LAW he ordered — DONE — root CLAUDE.md law 6 (THE REPEAT LAW), rules/PLAN.md → The Session Task List, teeth in rules/hooks/session_tasks_guard.py: a `REPEAT OF` block with no `PROCESS CAUSE:` is blocked; a `[x]` REPEAT with neither `OWNER CONFIRMED` nor `HIS EVIDENCE:` is blocked; `[~]` (shipped, he has not seen it) passes. SELF-TESTED on all four paths, and it caught this very round twice — once legitimately, once on the law's own name, which is why it matches `REPEAT OF` and not the bare word. Root-repo commit 0.0.030.
- [~] 75. THE DICTATION SPAM — SHIPPED, unconfirmed — REPEAT OF task 61's rescue copy. PROCESS CAUSE: that round added the rescue and tested that a dying round types what it heard; it never asked what happens when rounds die four times a second, and the answer was in the same log it was reading. "The phone types something" was proven; "the phone types it once" was never stated. HIS EVIDENCE: server.log 11:30:05 → 11:30:12, forty × `Voice error 5 (online)` = ERROR_CLIENT, plus both of his messages to us this morning, shredded. Root cause: `startListening` on a still-running recognizer is refused with ERROR_CLIENT, the page retries after 250 ms, and every refusal ran `deliver(null)` — with cumulative partials that re-types the whole sentence so far. Fixed at both ends: cancel before start, and `lastOut` trims a rescue to what has not been typed. Commit 0.0.293, APK 0.0.091.
- [~] 76. THE CLAUDE SET — SHIPPED, unconfirmed — REPEAT OF tasks 25, 41, 55, 58: four numbers, four `[x]`, one bug. PROCESS CAUSE: round 11c built the detection he demanded (`server/agents.py`) and closed it, but never removed what detection replaced. `sets.js` kept `if (Array.isArray(lay.app_sets)) return lay.app_sets.includes(s.name)` — "answered from it ALONE" — and the creation panel kept writing that list at creation time, so a live `agents: ["claude"]` on every state frame was discarded by a copy of an older answer. Its guard case was named "the layout's own ticks win over the title guess": a test that PINNED the defect as intended behaviour and therefore could never go red. Ticks removed end to end (creation panel, rename panel, `layout_apps`, `Layout.app_sets`, `layout_state`); the guard now asserts the opposite and fails on the old line. Commit 0.0.294.
- [~] 77. THE SLOW LOAD — SHIPPED, unconfirmed — `agents.agents_for()` was called bare from the async handlers (layout_api.py:70/103/112), once per window and once per tab: a 1.85 s PowerShell probe MEASURED on his PC, with the whole event loop stopped — no stream, no heartbeats — every time the 2 s cache lapsed, which a slow `uia.list_tabs` between two windows guaranteed. One snapshot per request, in a thread. Gate counts the probes and fails at two. Measured end-to-end after the fix: 1.63 s, 22 entries, one probe. Commit 0.0.294.
- [x] 78. Round close — DONE — APK 0.0.091 (Kotlin changed) + full desktop build (payload gate, INPUT/PRESENCE/NOTIFY/FOCUS/LAYOUT gates, PyInstaller smoke test, signed exe and installer, VERIFY FileVersion 0.0.091) and GIT RELEASE published: https://github.com/UVuruna/Remote-User/releases/tag/v0.0.091 — guards 4/4 full, phone layout audit 26/26, app-set wheel 8/8, layout protocol 6/6, controls sets green.
- [~] 79. THE MOVE HANDLE DOES NOT MOVE — SHIPPED, unconfirmed — REPEAT OF round 3's task 2, closed as DONE 0.0.169 on "guards + load test + INPUT GATE pass". PROCESS CAUSE: everything that round built was correct — protocol, server placement, `dragMove`'s arithmetic — and its tests proved exactly that. None of them ever delivered a TOUCH, so both defects, which live in the gesture layer, were invisible to all of them. Two real causes, each reproduced in the audit before being fixed: (a) the re-centre fired on `pointerdown` for any contact within 350 ms, so tap-then-drag was read as a double tap — region back to the MIDDLE and no pointer capture, so the drag died too; his sentence contains both halves; (b) `moveTapAt` started at 0, a real `performance.now()` reading meaning "a tap at page load", so any tap in the first 350 ms re-centred — landscape failed on this while portrait passed at 623 ms. A THEORY THAT DID NOT HOLD is recorded in the code and the commit: `touch-action` on `.asp-move` was the first diagnosis and is WRONG (`body` declares `touch-action: none` and the restriction is cumulative), so that check could not fail and was thrown away rather than kept green. Commit 0.0.296.
- [~] 80. THE KEYBOARD MUST NOT LIFT THE VIEW — SHIPPED, unconfirmed — `kbShift` is 0 and the canvas transform is gone. The canvas still keeps its FULL height, so the picture is never SQUEEZED — that half of his 2026-08-03 request stands; only the lift, which carried the line he was typing off the top of the screen, is withdrawn. Commit 0.0.295.
- [ ] 81. DRAG A LAYOUT ROW INTO ANOTHER TO MAKE A GRID — NOT STARTED, four questions with him. He said explicitly to ask rather than invent, and the questions are not cosmetic: what the two source layouts become, which grid template a drop chooses, whether a drop onto an existing grid extends it, and whether the same drag also reorders the list.

# Final Report — round 14 (2026-08-07): why "done" kept not being done

NOT DONE: **task 81** (drag a layout row onto another to build a grid) — his
new feature, not started, because he said to ask rather than invent and the
four questions genuinely change what gets built. Everything else he raised
today is built, gated and released as **v0.0.091**, and marked `[~]`: shipped,
and he has not seen it work yet. That state did not exist this morning.

## The finding that explains the circle

He asked for the process cause before the code, and the process cause is not a
matter of judgement — it is two lines from his own machine:

    installed exe: 0.0.089     running since 2026-08-06 19:49:58
    v0.0.090 published                       2026-08-06 20:06

    his server.log, TODAY 11:35:07:
      File "layout_api.py", line 86, in layout_list
      UnboundLocalError: cannot access local variable 'mon_rect'

Line 86 is the bug fixed in 0.0.290 and released as v0.0.090; the repo's line
93 has read `rect = mon_rect(stream)` since yesterday evening. So "create from
a list still does not work" was TRUE on his device and the fix was real — he
has never run it. `_check_updates` is documented "one GitHub check per start",
his app had been running for seventeen minutes when v0.0.090 appeared, and it
never asked again.

That is the mechanical half of "I give ten tasks, the agent says all ten are
done, half are unchanged". We ship; the release is real; the app in front of
him is from before it; the next round re-diagnoses a fixed bug and the week is
gone. Fixed in code (task 73) — but the code fix only takes effect once he
installs v0.0.091 by hand, which is the last time that will be true.

## The other half, and it is ours

Three tasks in this round were REPEATS, and the record shows one mechanism
behind all of them: **"done" had come to mean "my own test is green"**, and a
test written from the same belief that produced the bug cannot go red.

- The Claude set carried FOUR task numbers and four `[x]` (25, 41, 55, 58).
  Round 11c built the detection he demanded and left the tick list that
  overruled it — with a guard case named "the layout's own ticks win over the
  title guess". The test pinned the defect AS THE RULE.
- The Move handle was closed on "guards + load test + INPUT GATE pass". Every
  piece was correct; nothing had ever delivered a touch, and both real defects
  live in the gesture layer.
- The dictation rescue copy was tested for the round it was written for. Four
  collisions a second was never asked, and the answer was in the log that
  round was already reading.

THE REPEAT LAW (root CLAUDE.md law 6) is the answer he ordered: when he
reports something a previous round closed, the FIRST deliverable is why that
claim was false; the code is second. A task may be `[x]` only on his word or
evidence from HIS machine; otherwise `[~]`, carried forward until he closes
it. Teeth in `rules/hooks/session_tasks_guard.py`, self-tested on four paths —
and it blocked this very round twice, once correctly and once on the law's own
name, which is why it matches `REPEAT OF` rather than the bare word.

`[~]` is not a demand that he verify the whole app. It applies to what he
reported and we claim to have fixed. A round still ships, still closes, still
releases — it simply stops calling a thing proven when the only witness is its
own author.

## What is in v0.0.091

| His report | Cause | Where |
|---|---|---|
| mic spams the sentence until switched off | `startListening` on a live recognizer → ERROR_CLIENT storm × cumulative partials × deliver-on-every-error | APK, 0.0.293 |
| wheel offers only VS Code inside Claude | the tick list written at creation outranked live detection | 0.0.294 |
| "create from a list" dead | fixed in v0.0.090; he runs 0.0.089 | 0.0.295 delivers it |
| layout setup takes very long | 1.85 s process probe per entry, on the event loop | 0.0.294 |
| Move handle stays centred | tap-then-press read as double tap; timer origin at 0 | 0.0.296 |
| keyboard pushes the typed text out of sight | the canvas was lifted by the keyboard's height | 0.0.295 |
