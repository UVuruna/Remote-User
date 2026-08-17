# Layout Acts API — the wire for what a layout's own application can do

Source: [`server/layout_acts_api.py`](../layout_acts_api.py) ·
Catalogue and injections: [Layout Acts](layout_acts.md) ·
Phone half: [`client/layout-new.js`](../../client/layout-new.js) ·
Gate: [`tests/test_new_source.py`](../../tests/test_new_source.py)

## Why it is its own module

Split out of [Layout API](layout_api.md) on 2026-08-17, when that file crossed
THE STRUCTURE LAW's wall — and **by responsibility rather than by line count**,
which is the split this project has made every time it reached that wall.
`layout_api.py` answers what layouts EXIST and what may be done TO them:
create, focus, grow, shrink, re-place, remove. These two handlers ask a
different question — what the program a layout is MADE OF can be asked to do —
and their answer touches no layout and creates no member.

The catalogue and the injections themselves live one door further in
([Layout Acts](layout_acts.md)), deliberately free of websockets and JSON so
its gate can run it whole. This module is the wire between the two: it reads
which layout is focused, hands the act off, and answers the phone.

## The two messages

| Message | Answer | Note |
|---------|--------|------|
| `layout_acts {}` | `layout_acts {in_layout, app, name, entries}` | answered even at the DESKTOP, with `in_layout: false` and an empty list — the phone draws one group or two off this frame, and an absent answer is a panel that never renders |
| `layout_act {id}` | a `toast` only when it refused, then `layout_act_done {}` | the act runs as its own task; the `done` frame is the ONE end of the phone's loading overlay |

`focused()` is [Layout API](layout_api.md)'s own reader, imported rather than
copied: "which layout is he watching" having two answers is precisely what that
function exists to prevent, and that does not stop being true across a file
boundary.

## The one rule this module carries alone

**An act runs OFF the receive loop, and the phone is answered when the work is
really finished.** Both halves come from one owner report (2026-08-17) and his
own server log is what dated it.

`layout_act` used to `await` its work inside `web.py`'s receive loop.
`asyncio.to_thread` frees the event loop, but it does not free THIS
connection's receive loop — web.py awaits the handler before it reads the next
message — and one act blocks for as long as its work takes: up to
`layout_acts.LAUNCH_WATCH_S` (25 s) for the act that waits for a window to
appear. For those 25 seconds not one `hb` was read, so presence did exactly
what it is built to do:

```
09:37:35 presence: No signal from the phone for 12s (heartbeat) — session ends
09:37:35 presence: Phone left work mode — layout members minimized
09:37:48 RuntimeError: WebSocket is not connected
```

That is the "blockade and a slight disconnect" he reported, and his layout
windows minimizing under him mid-act: **our own handler starving our own
watchdog.** The act is its own task now, so the loop keeps reading heartbeats.

**The answer is a fact, never a timer** (constraint 15 — we never estimate how
long another program needs). `layout_act_done` is sent on every ending an act
can have: done, refused, crashed, or refused before it began. One message for
all of them, because an overlay whose end is one of several different frames
is an overlay that will one day be left standing over his screen. The phone
adds the one ending this message cannot have — a socket that died owing it —
in `connection.js`'s close path.

**Nothing is serialized, on purpose.** Two acts are two independent
injections, each behind its own fence check ([Layout Acts](layout_acts.md),
rule 2). A queue would only make the second one act on a desk that has moved
since he tapped it.

## What the gate holds

In [`tests/test_new_source.py`](../../tests/test_new_source.py), each proven by
planting its own defect:

* a slow act **never blocks the receive loop** — the staged act blocks until
  the dispatcher has returned and released it, so a handler that awaits inline
  cannot finish at all;
* a slow act **still answers when it is really done** — moving work off the
  loop must not lose the overlay's end;
* an act at the DESKTOP is refused, injects nothing, and is still answered.

The two checks that predate this round could not see any of it: they drive acts
that return at once, so *"does the handler return"* and *"does the handler
return PROMPTLY"* looked like one question. They are not, and only the second
one is the feature.
