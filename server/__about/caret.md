# Caret

**Script:** [Caret (script)](../caret.py)
**Flow:** [diagram](../__flow/caret.md)

## Purpose
Say **where the typing caret is on the PC screen**, in coordinates the phone
can use — or say honestly that the PC cannot see it.

The phone's soft keyboard covers the bottom of its own screen. Whether that
matters depends on something only the PC can know: which row of which window
the characters are actually appearing in.

## The failure this module exists to end
Owner report 2026-08-07, screenshots again 2026-08-08 — a REPEAT, so the
process half is written down beside the code half:

| shipped guess | what happened |
|---|---|
| lift the canvas by the keyboard's height (`kbShift`) | fine for a box at the BOTTOM of the PC screen; for a box at the TOP it carried the very row he was watching off the top. Withdrawn by the owner 2026-08-07. |
| leave the picture alone | the keyboard covers exactly the row he types into. |

Both guesses moved the picture by a CONSTANT. Neither ever asked where the
text was. His instruction is the specification:

> *"Najoptimalnije rešenje bilo bi da naš program prepozna gde se nalazi, koja
> je pozicija na ekranu, kursora koji kuca."*

And his refinement, which decides what the phone may do with the answer:

> *"Tastatura kada pomera sa offsetom ne pomera taj prazan deo već pomera samo
> vidljivi ekran gde se nalazi aplikacija, i to samo ako ima potrebe."*

Only the PICTURE may move, only when there is a need — and "is there a need"
is a question about a caret position, which is what this module supplies.

## What it reads, and what that is worth
MEASURED on the owner's own machine, 2026-08-08, in three read-only sampling
runs over his real desktop while he worked (no window opened, no input
injected):

| source | verdict |
|---|---|
| `GetGUIThreadInfo().rcCaret` — the classic Win32 caret | **Not one hit in ~3 minutes** across VSCode, Chrome, Explorer, Paint, Spotify, Snipping Tool. Kept, because it is exact and costs microseconds where it does exist (Notepad, classic dialogs) — but on his desktop it fires for nothing. |
| UIA `TextPattern.GetSelection()` | **VSCode answers with the caret's LINE** — e.g. `(300, 1248, 995, 25)`, and the `top` follows the row he types on (1130 → 1248 → 1272 → 1296). Chrome's page document answers with a 1×1 caret box. |
| the same range, `ExpandToEnclosingUnit(Character)` | **Load-bearing.** The Claude Code chat box inside VSCode returns an EMPTY rect list for its collapsed caret; only the expanded range gives `(1203, 936, 21, 21)`. |

So the honest answer to "do Electron apps expose anything": **VSCode does, and
it gives the ROW** — which is better for this purpose than a 1-px caret would
be, since the row is exactly what the keyboard must not cover. What VSCode
does not give is a real caret: its accessibility surface is a proxy element
named *"The editor is not accessible…"*.

Cost, measured the same day against his own VSCode: `GetFocusedControl` plus
the walk up to the owning window, **median 5.3 ms** (39.7 ms on the first,
COM-warming call); the text read itself **0.6 ms**. But cost is not uniform —
the **Claude Code chat box took 516, 532 and 516 ms** where the editor beside
it answered in 6 ms, which is why the throttle is a DUTY CYCLE
(`UIA_DUTY_FACTOR`) and not a fixed interval: each read waits ten times what
the last one cost, so this feature stays at ~10% of one background thread
whatever window he types into.

## The bug the measurement caught before he could
Run read-only against his real desktop, the first version of this module
answered `no-caret` for **150 seconds while he was typing in VSCode**. The
cause was a rule that reads as obviously correct — *use the caret only if the
focused element belongs to the window we are watching* — and that in practice
throws away every caret in his main app: the element chain under VSCode's
suggestion items carries **no window handle at all**, so "cannot tell" was
being treated as "someone else's window".

A window that cannot be NAMED is now accepted; only one that names a
DIFFERENT window is refused. The same run afterwards reported **11 caret
positions in 45 seconds**, from the editor (`w = 0.2294` — the row) and from
the Claude Code chat box (`w = 0.0055` — the expanded character box).

The lesson is the one this project keeps paying for: **a gate built only from
fakes stays green through this.** The fakes agreed with the code because both
were written from the same wrong assumption; only the real desktop disagreed.

## The rules
1. **Unknown is unknown.** The message carries either a measured rect or
   `known: false` — and the unknown form carries **no coordinates at all**, so
   a client that forgets to test `known` reads `undefined` and breaks visibly
   instead of lifting its picture to the top-left corner of the screen.
2. **Normalized to the monitor the phone is being shown**, exactly like
   `cursor`. A caret on ANOTHER monitor is not a number outside 0-1 for the
   page to puzzle over — it is unknown, with `why: "off-monitor"`.
3. **Which window is being typed into is not this module's question.** It is
   [Focus Guard](focus_guard.md)'s, and it is asked through
   `current_target()` — the READ-ONLY twin of `guard()`. Re-deriving it here
   is how two answers to one question start to disagree.
4. **Looking never acts.** `current_target()` raises nothing, arms nothing and
   takes no lock. A watcher that could raise a window would be a second focus
   policy running beside the real one, several times a second.
5. **Only on change.** This rides the same socket as the video.
6. **A rect is HELD, never invented.** While he types in VSCode the suggestion
   list takes UIA focus on nearly every keystroke and there is no caret to
   read; the last MEASURED rect stands for `HOLD_S` (4 s), so the phone is not
   told "unknown" mid-word. What is held is the row he is typing IN, and that
   row does not move while a suggestion popup is open.
7. **A read pays for the silence after it.** Cost is not uniform across
   windows (516 ms vs 6 ms, measured), so the next read waits
   `UIA_DUTY_FACTOR` times what the last one cost.

## The message
Server → client, on the existing WebSocket, only when the answer changes:

```json
{"type": "caret", "known": true, "x": 0.1510, "y": 0.5093, "w": 0.2591, "h": 0.0116}
{"type": "caret", "known": false, "why": "no-caret"}
```

`x, y, w, h` are 0-1 within the displayed monitor (the top-left corner of the
caret rect and its size). `why` is one of `no-caret`, `off-monitor`,
`no-window`, `no-monitor` — so the owner's log can say why the feature did
nothing for a given app.

## Connections
**Uses:**
- [Focus Guard](focus_guard.md) — `current_target()`: which window the phone's
  keys land in right now
- [UIA](uia.md) — `caret_rect()`: the UI Automation half of the read

**Used by:**
- [Web Layer](web.md) — starts and cancels `watch()` with the connection

## Gate
`tests/test_caret.py` — fail-closed, with every Win32 and UIA call faked
(nothing on the owner's desktop is read or touched). It pins the three ways
this feature can be worse than not existing: a rect normalized against the
wrong monitor, an unknown reported as a position, and a message per read.
