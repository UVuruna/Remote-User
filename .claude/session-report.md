# FINAL REPORT — Round 15 (2026-08-07)

**Released: v0.0.093** — https://github.com/UVuruna/Remote-User/releases/tag/v0.0.093
Installer signed, APK bundled. 17 commits (0.0.305–0.0.321). Sixteen agents,
three independent visual graders, four grading passes.

His order this round: *"ti si agent koji će da vodi ovaj posao ... da angažuje
druge agente, da ih proverava, i na kraju da me obavesti kada se sve završi."*

---

## Per task

| # | Task | State | Evidence |
|---|---|---|---|
| 85 | R1 focus C+A | `[~]` | Per-CHARACTER guard (SendInput 921 µs/key vs GetForegroundWindow 194 ns = 0.11% cost); loss on a mid-sentence steal went from "up to 39 chars" to ZERO; the phone is toasted what never arrived. 25 gate checks across two files, defect-planted. An independent verifier found 5 defects in the first version and all were fixed. |
| 86 | The grid is a picture | `[~]` | Count and orientation are drawings; the sketch's outer box is wide for landscape, tall for portrait. Graded 9/10 twice, independently. |
| 87 | R2 Settings window | `[~]` | Four cards; Stream moved in (his P1); notification speak/voice/pace; the B focus-lock with ledger + next-start repair; a real Task-Scheduler autostart switch. No exception text ever reaches the user. |
| 88 | R4 Traffic | `[~]` | "Od starta" + "Sve" read 1.33M rows in 3.3 s off the UI thread (2,789 event-loop pumps during the read); one unit per axis; legend swatches read from the same functions that paint the lines. 9/10 both palettes. |
| 89 | R5 wheel order | `[~]` | Drawn ring + ladder; `wheel_order` preserved across updates. It also needed one line in `_load_actions` — without it the feature was a no-op for every user, fresh installs included. |
| 90 | R3 themes | `[~]` | Two palettes compared at import; app-wide QSS; phone dark/light/coloured × transparent/full via `config.ui`. The coloured theme's labels went 2.66:1 → 8.10:1 once the wheel's veil stopped painting over our buttons. |
| 91 | R6+R7 gamepad | `[~]` | A pad press runs through `buttonPress()` — the same activator a finger's pointerup runs — so CLICK/HOLD cannot drift. 30 gate checks, defect-planted 7 ways. Horizontal scroll closed (`hticks`). |
| 93 | The ghost client | `[~]` | Four hours of 4K encoding for a phone that was not there; 12,924 s of ffmpeg CPU. `await asyncio.to_thread(open_session)` cannot be cancelled. Fixed with a claim made before the encoder exists + a second, independent rule in `push`. |
| 94 | Claude never detected | `[~]` | The switch never reached HIS actions.json; every guard built its "user file" as a copy of ours. The migration rule is inverted and forward-compatible; detection reads `~/.claude/sessions/<pid>.json`. Verified live on his machine: `{'claude': ['remote user','uvuruna']}`. |
| 95 | Notices while the phone is in his pocket | `[~]` | His decision, quoted: the small service, minimal channel. One idle `GET /notices`, one byte a minute, ~150 KB/day. A waiting channel is structurally never a present phone. |
| — | Move handle (`pos`) | `[~]` | Third report. `arranged_pos` was a note of what was COMMANDED; once a member left its rect every later Apply placed nothing. Arrangement is MEASURED now. |
| 92 | Visual proof | `[x]` | 55 entries, none below 8. Four passes; where two graders disagreed the LOWER stood. |
| 96 | Caret-aware keyboard | NOT BUILT | His decision recorded with his refinement (only the PICTURE moves, never the navy filler; only if the caret would really be covered). Scheduled next, deliberately, so today's work reaches him first. |

`[~]` = shipped, and HIS machine has not confirmed it. Only his screen closes these.

## Found by LOOKING, not by any test
Every text input invisible in light (Δ1 per channel) · the dropdown caret a solid
square · Filled vs Outlined byte-identical on the default theme · the window title
cut at 30 chars beside 112 px of empty space (named in three previous rounds and
rounded up in all three) · "Send" printed twice · the status pill covering the
wheel's 12-o'clock label · seven of ten phone panels scrolling in landscape beside
495 px of idle width · the editor calling a TYPED command a "chord".

## Not in v0.0.093
The editor's "types" label (0.0.321) landed after the installer was built.

## Open, named rather than rounded away
Toast ink 2.25:1 · dark error line 3.89:1 (DESIGN.md's own token) · the detail
panel still says "Shortcut (chord)" for a typed command · `_paste_text`'s Enter is
unguarded for 120 ms · ChordRecorder has never been photographed.

## My own failures this round
1. I told him PID 28016 was our leftover server and gave him a kill command. It
   was not ours — `server/main.py` parses no arguments. An agent caught it, not me.
2. I asked him to choose the notification mechanism. He had chosen it that same
   day at 12:20. The task list said "waiting on him" and I trusted the note over
   his words.
3. I dispatched overlapping briefs twice; two agents stood down rather than
   corrupt the tree. Their judgement was better than my dispatching.
4. An agent of mine benchmarked real `SendInput` — ~200,000 mouse events into his
   live session. That was his frozen mouse. The rule now: fake the Win32 layer; a
   real measurement needs his window of time, agreed first.
