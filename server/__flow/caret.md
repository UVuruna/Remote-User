# Caret — Flow

**About:** [description](../__about/caret.md)

## One poll, end to end

```
                       every POLL_S (0.15 s), on a worker thread
                                    │
                 conn["away"] / ["left"]?  ──yes──▶  say nothing, sleep
                                    │ no             (nobody is looking)
                                    ▼
   WHICH window is being typed into  ──▶  focus_guard.current_target()
                                              READ ONLY: raises nothing,
                                              arms nothing, takes no lock
                                    │
                                    ▼
   ┌────────────────────────────────────────────────────────────────┐
   │ 1. GetGUIThreadInfo(thread of that window).rcCaret             │  µs
   │    client coords of hwndCaret  →  ClientToScreen               │
   │    empty rect (height 0) counts as NO caret                    │
   └────────────────────────────────────────────────────────────────┘
                     │ none — every app on his desk
                     ▼
   ┌────────────────────────────────────────────────────────────────┐
   │ 2. uia.caret_rect(hwnd)   next read ≥ 10× what this one costs  │ 6–516 ms
   │      GetFocusedControl()                                       │
   │      element → … → the window that owns it                     │
   │         names ANOTHER window  ──▶  not ours, refuse            │
   │         names none (0)        ──▶  ACCEPT — VSCode's whole     │
   │                                    chain answers 0             │
   │      TextPattern.GetSelection()[0]                             │
   │        rects?  ──yes──▶  the caret's LINE      (VSCode)        │
   │        none    ──▶  Clone().ExpandToEnclosingUnit(Character)   │
   │                          ──▶  a character box  (Claude chat)   │
   └────────────────────────────────────────────────────────────────┘
                     │ still none
                     ▼
        last MEASURED rect younger than HOLD_S?   ──yes──▶  hold it
                     │ no                                   (the VSCode
                     ▼                                       suggestion list
              unknown("no-caret")                            has focus)
```

## From a screen rect to what the phone is told

```
   screen px (2500, 1100, 2, 25)        monitor being shown (1920, 0, 3840, 2160)
              │                                        │
              └────────────────┬───────────────────────┘
                               ▼
              centre inside the monitor?
                 no  ──▶  {"type":"caret","known":false,"why":"off-monitor"}
                 yes ──▶  {"type":"caret","known":true,
                           "x":0.1510,"y":0.5093,"w":0.0005,"h":0.0116}
                               │
                               ▼
                   same as last time?  ──yes──▶  send NOTHING
                               │ no
                               ▼
                       ws.send_text(...)
```

The unknown form carries **no x/y/w/h at all**. That is deliberate: a client
that forgets to test `known` then reads `undefined` and breaks visibly,
instead of quietly lifting its picture to the corner of the screen — which is
what a `(0, 0)` "unknown" would mean to it.

## What was measured, and on what
Three read-only sampling runs over the owner's real desktop, 2026-08-08 —
nothing opened, nothing injected, nothing moved:

```
GetGUIThreadInfo   ██                                          0 hits / ~3 min
                   (VSCode, Chrome, Explorer, Paint, Spotify, Snipping Tool)

UIA selection      ████████████████████████                    VSCode: the ROW
   VSCode editor   (300,1248,995,25) → (300,1272,…) → (300,1296,…) as he typed
   Chrome document (1236,196,1,1)                              a 1×1 caret box

UIA + expand       ████████                                    the rescue
   Claude chat box selection=[]  →  expanded=(1203,936,21,21)
```

Cost of one UIA read on that machine: `GetFocusedControl` + window walk,
median 5.3 ms (39.7 ms on the first, COM-warming call); the text read itself
0.6 ms. **Not uniform** — the Claude Code chat box took 516 / 532 / 516 ms
where the editor beside it took 6 ms, which is why the throttle is a duty
cycle rather than a fixed interval.

## And the same module, run read-only against his real desktop

```
BEFORE the window-check fix    150 s, VSCode foreground, he was typing
                               → 1 message: {"known": false, "why": "no-caret"}

AFTER                          45 s, same desk
   15:15:08  known  x 0.2969  y 0.7704  w 0.0055   Claude chat (expanded box)
   15:15:12  known  x 0.0781  y 0.8301  w 0.2294   prompt.txt  (the ROW)
   15:15:16  known  x 0.0781  y 0.7440  w 0.2294
   15:15:16  known  x 0.0781  y 0.7106  w 0.2294
   15:15:18  known  x 0.0781  y 0.5931  w 0.2294
   15:15:22  known  x 0.0781  y 0.6042  w 0.2294
                               → 11 messages in 45 s, one per change
```

