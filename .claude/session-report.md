SESSION: b8d8ce25-5cc2-4f32-9fc5-60a910985a1f
RELEASE: https://github.com/UVuruna/Remote-User/releases/tag/v0.0.090 (supersedes v0.0.089 — same round, one regression fixed on top)

- [x] 64. "layout, kreiraj iz liste, nista se ne desava" — the loading cube spun — DONE — root cause read from his own server log (three tracebacks, 19:56:24 / 19:56:31 / 19:56:39): UnboundLocalError at layout_api.py:86, `mon_rect = mon_rect(stream)` shadowed the module's own function so the right-hand call raised before anything was sent; the socket died and the phone reconnected into a spinner. Introduced in 0.0.266, shipped in v0.0.088 and v0.0.089. Fix: `rect = mon_rect(stream)`. Gate: tests/test_layout_protocol.py (5 checks, every layout message through the real web._receive_input + real LayoutRegistry), fail-closed as build.py step 0f, SELF-TESTED by replanting the defect — check 1 fails with that exact UnboundLocalError. Commit 0.0.290, released v0.0.090.
- [x] 61. FOCUS NEVER LEAVES THE BOX HE IS DICTATING INTO — server/focus_guard.py. — DONE — root cause: SendInput has no target, so every dictated character went to whatever window Windows called the foreground; half of it was ours (focus() raised layout members in list order, so a re-focus after an excursion handed the keyboard to the last window of the grid — his log: excursions 18:38:56, 18:41:50). Fix: focus_guard decides the target before every typing message (layout = fence, desktop = pin, GW_OWNER dialog = target, thief named in the log), Layout.last_member raised last, and focus_guard.watch defends a focused layout every 0.25 s; phone half: VoiceInput keeps a rescue copy (EXTRA_PARTIAL_RESULTS) so a dying round types what it heard instead of deleting it. Evidence: tests/test_focus_guard.py 15/15 incl. the whole path through the real web._receive_input dispatcher, fail-closed as build.py step 0e; commits 0.0.280, 0.0.282, 0.0.283.
- [x] 63. The tray toast — the "already told" flag lived only in the window — DONE — the flag lived only in the MainWindow object, so every start of the app produced the toast again; now SETTINGS.tray_notice_path (a marker file beside the user data) makes once mean once, and the window footer carries the same sentence permanently. His screenshot's sender was "Python" = a dev instance, which is stated to him, not hidden. Evidence: commit 0.0.281, guards 4/4 and the Qt layout audit 5/5 re-run after the change.
- [x] 62. Round close — APK 0.0.089 (Kotlin changed) + full desktop build (payload — DONE — APK 0.0.089 built (2.9 MB, Kotlin changed), then the full desktop build with every gate green (payload gate, INPUT, PRESENCE, NOTIFY 15/15, FOCUS 15/15, smoke test, signed exe + installer, VERIFY FileVersion 0.0.089) and the GIT RELEASE published: https://github.com/UVuruna/Remote-User/releases/tag/v0.0.089

# Final Report — round 12 (2026-08-06): the dictation that went somewhere else

The report that opened this session was itself the evidence: the first
paragraph of his message is a sentence he dictated for ANOTHER project, and it
arrived here.

NOT DONE / BLOCKED: **nothing is left undone — every task he gave is finished
and shipped**. (Say this the right way round: an earlier version of this line
read "none of what he asked", which in Serbian reads as "I did nothing you
asked" — the exact opposite. A status line that can be read as its own
opposite is a broken status line.) One thing is stated, not hidden: I could not name the specific program that stole his focus tonight,
because nothing in the app was watching. From this version the server log
names it (exe + title) every time it tries — and it no longer succeeds inside
a layout.

## Root cause, in one line
`SendInput` has no target. Every dictated character went to whatever window
Windows called the FOREGROUND at that instant, so anything on the PC that took
focus mid-sentence took the rest of the sentence with it — silently, with no
error, while the stream still showed the PC.

Half of it was OURS, and his own server log dates it: a picker or permission
dialog closes the socket (excursions at 18:38:56 and 18:41:50), the page
re-focuses the layout on the new connection, and `focus()` raised members in
LIST order — so the keyboard went to whichever window sat last in the grid,
which for him is the other agent's session.

## Per task

### 61 — the focus guard (see the line above for status + evidence)
  `server/focus_guard.py`: the target is decided BEFORE every message that
  types. In a layout the fence is the layout (a foreign foreground is refused
  and focus handed back to the member he was typing in); at the desktop the
  target is the window the typing burst started in, re-armed only by what he
  does on purpose; a dialog of the target counts as the target (GW_OWNER
  chain, never process identity — every VSCode window shares one process and
  one of them is the thief); the thief is NAMED in the log.
  After his second message, shouted: the layout is **defended**, not merely
  checked — `focus_guard.watch` polls every 0.25 s, because the recognizer
  delivers a whole utterance only at the END of a round, so a guard that waits
  for a keystroke arrives after the damage. It sleeps while the phone is away.
  `Layout.last_member` fixes the other half: the keyboard member is raised
  LAST on every re-focus.
  Phone half: `VoiceInput` keeps a rescue copy of what it has already heard
  (`EXTRA_PARTIAL_RESULTS`), so a round that dies — the `ERROR_CLIENT` lines
  that fill his log — types those words instead of deleting them; `deliver()`
  is the only exit, so nothing is typed twice.
  Evidence: `tests/test_focus_guard.py` 15/15, including the whole path
  through the real `web._receive_input` dispatcher, fail-closed as step 0e of
  `build.py`. Commits 0.0.280, 0.0.283.

### 63 — the tray toast (status + evidence above)
  The "already
  told" flag lived only in the window object, so every start of the app
  produced it again. A marker file (`SETTINGS.tray_notice_path`) makes once
  mean once. Noted for him: his screenshot showed the sender as **Python**, so
  that one came from a dev instance, not the installed app. Commit 0.0.281.

### 62 — round close (status + evidence above)
  APK 0.0.089 (Kotlin changed) + full desktop
  build and GIT RELEASE v0.0.089.

## Gates on the released tree

guards 4/4 · INPUT GATE · PRESENCE GATE · NOTIFY GATE 15/15 · **FOCUS GATE
15/15 (new, step 0e)** · Qt layout audit 5/5 · phone layout audit · client
load test · PyInstaller smoke test · payload gate · signed exe + installer ·
VERIFY FileVersion 0.0.089.

## What he should watch for
If anything still pulls focus while he dictates, the server log now says who:
`Focus left the layout the phone is showing — <exe> "<title>" (0x…)`. That
line is the next fix's starting point, and it did not exist before tonight.

SESSION: 0eb7cbe2-d779-4c9d-9ec7-0a3d35d0897a
RELEASE: https://github.com/UVuruna/Remote-User/releases/tag/v0.0.088

# Final Report — rounds 11 / 11b / 11c (2026-08-06)

One session, three rounds, because twice what I reported as fixed was not.

NOT DONE / BLOCKED: **none**. One limit remains open by design and was stated
to him, not hidden: with the phone app FULLY CLOSED a notice cannot arrive at
the moment it happens — it arrives on his return — unless he asks for an
Android foreground service, which costs a permanent tray entry and battery.

WHAT I GOT WRONG, twice, plainly: I reported v0.0.086 as fixing his overlap on
the strength of a guard that measured SIZES and an audit run with substitute
FONTS. Both were green; his screen was not. And the round before this one told
him that detecting a Claude conversation was impossible after probing exactly
one source. Neither was a coding error — both were stopping too early and
reporting the stop as an answer.

## Gates on the released tree

guards 4/4 · APP-SET WHEEL 8/8 (two new) · CONTROL SETS · INPUT · PRESENCE ·
NOTIFY 15/15 (three new) · Qt layout audit 5/5 on the REAL platform fonts,
now with an OVERLAP check · phone layout audit with a CONTRAST check · client
load test · PyInstaller smoke test · payload gate · signed exe + installer.
Every new check self-tested by replanting the defect and watching it fail.

## Per task

- [x] find why VSCode vanished when Claude arrived, and bring it back — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] Claude set only on the Claude conversation tab, never on a document — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] both app sets ticked = 6 free wheel slots, not 7 (app sets charge the cap) — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] set list split into sections: standard / app-aware / custom — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] real icons for VSCode, Chrome, Explorer instead of the generic window — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] Arrangement: short title, D-pad + Stack names, Default button below the lists — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] check ALL groups after the Win-in-Mouse corruption (slika 3) — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] root rule with teeth: a delivering session ends with the per-task final report (machine-wide) — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 1. Mic (Input set) non-English recognition — REAL debugging, not — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 2. Layout resize panel: center Move handle (✥) — drag repositions the — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 3. Sets picker rotating state — DONE 0.0.169, two root causes: — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 4. Quality panel — DONE 0.0.169: FPS Max/10/15/30/60, res full/⅔/½, — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 5. Font-zoom staircase (layout focus only) — DONE 0.0.169: — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 6. Session close — DONE: APK 0.0.074 built (Kotlin compiled), full — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 7. Layout custom NAME — DONE 0.0.175 — the auto name (target window title) stays the — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 8. Z-ORDER — owner decided 2026-08-05 to KEEP the topmost band and — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 9. DONE 0.0.174 (root cause: no liveness signal at all — the server — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 10. DONE 0.0.175. Aspect panel Move handle icon — the ✥ glyph renders as a fat cross — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 11. Session close — DONE: APK 0.0.076 built, full desktop build passed — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 12. DONE — Controls editor obeys THE SPACE & LEGIBILITY LAW. Causes found: — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 13. DONE — Teeth: tests/test_layout_law.py (static, in --fast) + — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 14. DONE — Presets carry more than 4 commands: `buttons` is the pool, — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 15. DONE — Reserve commands per set (ACTIONS.md table), incl. the — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 16. DONE — Built-in rows tell the truth: load_client_builtins() parses — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 17. DONE — Session close: docs of every changed module updated — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 18. FOLLOW-UP RELEASE v0.0.079 — the Stop gate flagged theme.py as — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 19. Arrangement ladder (owner 1A) — raising a command must move the — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 20. Portrait ordinals (owner 1B) — a column has no left/right: the — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 21. Mouse side buttons (owner 2) — Btn 4 / Btn 5 (XBUTTON1/2) as — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 22. Settings pool (owner 4) — Next box and Snap removed; the five that — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 23. Icons for the commands that have none (owner 5) — proposal page — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 24. Region (owner 3) — free-size/free-position rectangle on the phone, — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 25. Claude app set (owner 6) — feasible; answer delivered. Needs (a) a — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 27. Quality hierarchy (owner report: "desktop settings do nothing") — — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 26. Round close for 23–25 — the code shipped as 0.0.198 + 0.0.199; the — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 28. DONE 0.0.200 — a LOCK is never an excursion. ROOT CAUSE from the — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 29. DONE 0.0.201 — the topmost ledger. clear_topmost() existed and was — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 30. DONE 0.0.203 — the Traffic window. MeteredSocket wraps the socket — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 31. DONE 0.0.202 — the audit's remaining leaks, none of them reachable — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 32. DONE — SHIPPED as v0.0.081: — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 23. ICONS — the whole proposal page accepted by the owner. 40 new faces — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 24. REGION — free-size/free-position frame, captured and pasted at once — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 25. CLAUDE app set — `title` match beside `process` (Layout keeps the — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 26. RENAME any button of any shipped set (owner's new requirement — the — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 27. Image dropped from the Attach pool. DONE 0.0.198. — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 33. "The PC calls you" (owner go + refinement 2026-08-05: several — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 33b. Thinking button (owner correction with the screenshot): `/effort` — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 34. DONE — the round close both rounds were waiting for. One release — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 35. PROBLEM: "zašto je WIN u MOUSE i nema RIGHT CLICK" — FIXED 0.0.210, — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 36. "Zašto je nestao VSCode kad si ubacio Claude" (editor half) — FIXED — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 37. Thinking = a CHOICE, not a command (owner idea: "u centar da — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 38. Sets picker grouping + group NAMES (his item 2) — DONE 0.0.214 — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 39. Arrangement section (his item 3) — already done by the parallel — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 40. Round close — DONE: full desktop build (INPUT/PRESENCE/NOTIFY — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 41. WHY THE CLAUDE SET NEVER SHOWED — root cause PROVEN by probing his — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 42. WHY NINE COULD BE TICKED (his item 2, cap of 8 confirmed as LAW) — — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 43. THE LIVE BADGE (his item 3) — the app rows now carry "ON THE WHEEL — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 44. NOTIFICATIONS DON'T WORK EITHER (his follow-up question) — correct, — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 45. STRUCTURE LAW — controls.js hit 1000 lines mid-round; the — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 46. Round close — APK 0.0.085 + full desktop build (INPUT + PRESENCE + — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 47. OVERLAP WITH THE UPDATE BUTTON (screenshot 1) and OVERLAP AT THE QR — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 48. NOTIFICATIONS CANNOT BE SWITCHED ON in the installed app - the root — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 49. THE CHECKBOX IS VISUALLY UNACCEPTABLE - correct: a QCheckBox had no — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 50. THE TICK BESIDE THE SELECTED SETS - delivered. Every set row carries — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 51. Round close - full desktop build (INPUT + PRESENCE + NOTIFY gates, — DONE — closed and evidenced in an earlier round of this same task list (.claude/session-tasks.md carries its root cause, fix and proof); this session did not re-verify it.
- [x] 52. THE OVERLAP IS STILL THERE ON v0.0.086 — REAL cause found and fixed: — DONE — v0.0.086's fix was real but not HIS bug. Cause: minimumSizeHint() quotes a WRAPPING label at ONE line, so the column was 48 px short and Qt spends a shortfall by OVERLAPPING, not clipping — every widget reported full size, which is why the guard was green. Reproduced at his 125% scaling before (qr 17..233, url at 195) and clean after. heightForWidth in one shared module (server/gui/sizing.py); the URL label deleted. Commit 0.0.258, shipped v0.0.087.
- [x] 53. COLOURS — cause: .sets-row sets no background, harmless on a <label> — DONE — .sets-row sets no background, harmless on a <label>, fatal on a <button>: the WebView paints its light default under near-white ink. Fixed; contrast tooth added (WCAG against the COMPOSITED backdrop). Self-test: all six chooser rows report 1.05:1 with the defect replanted. Found two more nobody reported. Commit 0.0.259.
- [x] 54. NOTIFICATIONS — answered from HIS log, not from belief: the hook — DONE — answered from his own server.log: 17:30:51 and 17:33:02, both 200, phone connected since 17:30:03. The PC half worked; the broken link was Android POST_NOTIFICATIONS. He confirmed the same evening. Fixed properly in task 59.
- [x] 55. CLAUDE — the earlier 'impossible' was WRONG, and proven wrong on his — DONE — the investigation reversed an earlier 'impossible'; he gave the go the same evening and it is BUILT in task 58.
- [x] 56. Round close — full desktop build (payload gate, INPUT/PRESENCE/NOTIFY — DONE — v0.0.087 released with the overlap fix, the colour fixes and the three new guards.
- [x] 57. THE TICKS — done exactly as specified: own strip on the LEFT with the — DONE — ticks in their own strip on the LEFT, icon and name indented past them; GREY where the set is `required`, WHITE where it is his to switch; App-aware rows ticked and their checkbox made live (the phone already read the same `enabled` flag, so a blank row hid a working switch). Evidence: the list rendered to PNG and inspected. Commit 0.0.265.
- [x] 58. CLAUDE DETECTED — server/agents.py reads the process table: a live — DONE — server/agents.py: a live claude.exe carries --resume=<session-id>, the id names a transcript whose `cwd` names the project, the VS Code title ends in that folder. Sent as `agents` per layout and per creation entry; the Claude set claims it with "agent": "claude"; his own ticks still win. Verified on HIS machine (three live projects matched his three titles; a Notepad title matched nothing) and pinned by two guard cases, self-tested. Commit 0.0.266.
- [x] 59. NOTIFICATIONS — three fixes. (a) POST_NOTIFICATIONS asked once at app — DONE, with one limit stated — permission asked at START (and a notice arriving before the answer is held, not dropped), an absent phone's notice WAITS 30 min and arrives oldest-first with '8 min ago', and the hook says 'needs you' because a Stop hook fires at every turn end. Three guard cases. What remains, by design and told to him: with the app fully closed nothing arrives at that moment, only on his return, unless he wants a foreground service. Commits 0.0.267, 0.0.269.
- [x] 60. Round close — APK 0.0.088 (Kotlin changed) + full desktop build — DONE — APK 0.0.088 (Kotlin changed) + full desktop build with every gate, signed, VERIFY FileVersion 0.0.088, and the GIT RELEASE published: https://github.com/UVuruna/Remote-User/releases/tag/v0.0.088
