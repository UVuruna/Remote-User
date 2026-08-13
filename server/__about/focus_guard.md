# Focus Guard

**Script:** [Focus Guard (script)](../focus_guard.py)

## Purpose
Decide **where the phone's typed input lands** — before a single key is
injected, instead of letting Windows decide it afterwards.

`SendInput` has no target. Every character the phone dictates or types goes to
whatever window Windows calls the FOREGROUND at that instant, so anything on
the PC that takes focus while the owner speaks takes the rest of his sentence
with it — silently, with the stream still showing the PC and no error anywhere.

Split out of [Web Layer](web.md) on 2026-08-06 (THE STRUCTURE LAW): one
responsibility, its own rules, its own failure history and its own gate
(`tests/test_focus_guard.py`).

## The failure this module exists to prevent
Owner report, 2026-08-06 — three trips back to the phone in one evening, and
the fourth report was the bug itself: a sentence he dictated **for another
project** arrived in *this* project's session. Mid-dictation the PC's focus
moved, and the words simply followed it:

```
he taps Mic  →  speaks  →  key_text "…" → foreground = his text box   ✔
             →  something on the PC takes focus (app start, dialog, agent)
             →  speaks  →  key_text "…" → foreground = SOMEONE ELSE'S window ✘
```

Nothing in the app could notice: the injector had no idea which window it was
aiming at, and the phone had no way to be told.

## The rules
1. **In a layout, the fence is the layout.** The phone is looking at that
   layout's member windows and at nothing else, so its keyboard may reach
   nothing else. A foreground outside the members is refused: focus goes back
   to the member the phone was last typing into, and only then do the keys go
   out.
2. **At the full desktop the guard builds a fence.** The window that held
   focus when the typing burst began IS the target, and it is re-armed only by
   things the owner did on purpose — an injected click (`pointer_down`,
   `click`, `press`), `next_input`, a layout switch, a monitor switch
   (`RETARGET_KINDS` in [Web Layer](web.md)). A thief arms nothing: it sends
   no message.
3. **A dialog of the target is the target.** Save As… is a window of its own
   and would fail both tests above, so ownership is walked up (`GW_OWNER`).
   Process identity is deliberately NOT used — every VSCode window shares one
   process, and one of those windows is exactly the thief.
3b. **But a window the LAYOUT'S WORK opened is not a thief either** (owner
   eruption 2026-08-11, task 202). Refusing it was only half the failure: it
   opens OUTSIDE the layout's region, under the members' topmost band, where
   the phone can see it and not touch it — and Desktop, the only way to it,
   minimizes his place of work. The layout branch therefore asks
   [Layout Popup](layout_popup.md) first, which either brings the window into
   the picture (inside the region, or full screen when it cannot fit) or
   answers "" — and "" is this rule's refusal, unchanged. `watch` takes that
   module's baseline once per connection.
4. **The thief is NAMED in the log** (exe + title + hwnd), every time. Being
   the last to find out is what made this bug cost three reports; a restored
   keystroke that logged nothing would only hide the next cause.

## Inside one sentence (build round R1, owner-approved 2026-08-07)
The fence above stands between MESSAGES. The hole that left: `SendInput`
injects one UTF-16 code unit at a time, and that is far slower than anyone
assumed. **Measured on the owner's PC** (`SendInput` with one keyboard event:
921 µs; `GetForegroundWindow`: 194 ns), so:

| | |
|---|---|
| one typed character (down + up) | ~1.84 ms |
| a 600-character dictated sentence | **~1.1 s** of injection |
| the foreground check that protects it | 194 ns — **0.01%** of one character |

A whole second in which a window that took focus received the remainder, with
nothing to replay it and no error from Windows.

So the check runs **before every character** (`TYPE_CHUNK_CHARS = 1`, and that
number is measured, never reasoned — re-measure before changing it). The first
attempt used 40 characters from an assumed 0.03–0.1 ms per character; that was
~20× optimistic, and it also meant "a steal loses zero characters" was only
true when the steal landed exactly ON a chunk boundary (35/20/39/25 characters
reached the thief at other offsets). At one character per check the answer is
zero, everywhere.

- The check is **bare on the happy path**: `typist()` compares
  `GetForegroundWindow` with the armed target — no lock, no owner walk,
  nothing that can block. Only a foreground that is NOT the target pays for
  the full `checkpoint()`.
- The **restore is verified, never assumed**: `SetForegroundWindow` succeeding
  is a request to the window manager, not a fact, so the foreground is re-read
  until it really is the target or `REFOCUS_SETTLE_S` (50 ms) runs out. That
  50 ms is only the confirmation tail — the `guard()` call before it can
  itself take seconds when a window has to be raised.
- **Focus that cannot be brought back stops the typing**, and the phone is
  TOLD: `type_text` returns what never reached the PC and
  [Web Layer](web.md) turns it into a toast naming the size of the loss and
  the start of what is missing. A remainder destroyed in silence is the
  original failure wearing a different coat. The log carries both halves too —
  the guard names the window holding the keyboard, the injector names the
  damage.
- **Half a character never goes out.** An unpaired surrogate (the page reads
  printable characters by diffing UTF-16 strings and can hand us half an
  emoji) cannot be encoded at all; discovering that per chunk threw
  `UnicodeEncodeError` out of the middle of a sentence and killed the socket,
  since the dispatcher catches only `WebSocketDisconnect`. The whole text is
  checked once, before a single key goes out.
- The checkpoint is handed to the injector as a plain callable
  (`typist(layouts, conn)`). [Input Injector](input_injector.md) is the layer
  BELOW and must know nothing about layouts, connections or fences —
  inverting that import to give it a guard would be the layering defect this
  project splits modules to avoid. `type_text` with no guard is exactly the
  old behaviour, which is what every caller with nothing to fence wants.
- Residual, stated honestly: a character is typed whole, so a steal landing
  BETWEEN the two code units of one surrogate pair lets the low half follow
  the high one out. At most one code unit — never a whole character.

## The layout is DEFENDED, not merely checked (owner decree 2026-08-06)
His second message the same evening, shouting: *"kada uhvatimo fokus lejauta ne
može nikakav program da izbaci fokus"* — and the reason a guard that only runs
on a keystroke is not enough is dictation. Android's recognizer hands over a
whole utterance **at the end** of a listening round, so a program that grabs
focus while he speaks does not misplace one character: it takes the window his
half hour of speech was meant for, and the round often dies with it (the phone
now keeps a rescue copy of what it heard — [VoiceInput](../../android/__about/VoiceInput.md)).

`watch(layouts, conn)` is therefore one task per connection: while the phone is
showing a layout, a foreground outside its members is put back at once, by the
cheapest route that works (`_refocus` — plain `SetForegroundWindow`, then the
`AttachThreadInput` unlock, and only a minimized window pays for the full
`raise_window`). The thief is logged once per `STEAL_LOG_QUIET_S`, so an app
that fights back cannot write the log by itself.

**Two sources, one decision** (build round R1, 2026-08-07). Windows announces
every foreground change through [Focus Hook](focus_hook.md), which puts the
restore at **2–5 ms** instead of up to 250 ms; the `WATCH_POLL_S` (0.25 s) poll
**stays** as the backstop, because a hook can be refused at install time or
dropped later by Windows. Both sources wake the SAME loop, so the decision is
taken in one place, on a worker thread, whichever spoke — and `guard` is
serialized by a lock, because two threads deciding the target at once would
race over the pin and could raise two different windows.

**The hook's callback may only SIGNAL** (`loop.call_soon_threadsafe`), and this
is not a style preference: a WinEventProc runs inside Windows' own event
dispatch, so calling `guard` from it was measured stalling a second caller for
**2.99 s** — the guard waits on that lock, which is held across a window raise
that waits for a frame to settle. Everything the desktop does with the
foreground queues behind that, and the owner feels it as a juddering mouse.
Worse, Windows silently DETACHES a hook that is slow to return, after which we
would believe we had millisecond reaction while running on the poll alone. So
the callback signals, the loop works, `focus_hook` logs any callback that
overruns its budget, and `_log_silent_hook` reports (once) a hook that Windows
still claims to hold but that announced nothing about a change the poll then
had to undo.

`watch` registers one listener, warns in the log if Windows refused it, and
releases it when the connection ends — **synchronously**, because the web layer
cancels this task without awaiting it, and a release needing one more turn of
the event loop would simply never run.

Two deliberate limits: the watcher **sleeps while the phone is away** (an
excursion or a leave hands those windows back to the desk — pulling focus to
them there is the sin two earlier rounds were spent fixing), and it **does not
defend the desktop pin**, because outside a layout there is no fence, only a
memory of where typing began; fighting the whole desktop for it would be us
stealing focus.

## Which member holds the keyboard
The target survives the connection, because the connection does not survive an
excursion: a picker or a permission dialog closes the socket by rule
([Presence](presence.md)), and the page re-focuses the layout on the new one.
So `Layout.last_member` lives in the registry ([Window
Manager](window_manager.md)), is updated whenever the guard sees a legitimate
member in front, follows a `prune` when that window is closed at the desk, and
is what `LayoutRegistry.focus()` raises **last** — the second half of the same
bug. Raising members in plain list order handed the keyboard to whichever
window sat last in the grid, so one excursion was enough to move his dictation
into the other pane.

## A fence whose target no longer exists fails OPEN (owner report 2026-08-13)
"Our application blocked me and my agents" — he had two solo layouts of the
same project; layout 2's only member was a VS Code tab TORN OFF layout 1's
window (our own extraction flow). He then, BY HAND on the PC, dragged that
tab back into its origin window — Windows DESTROYS the torn-off window on
such a merge, through **none** of our own removal paths
(`drop_member`/`eject_member`/`merge`/`remove` in
[Layout Registry](layout_registry.md) never ran). `Layout.members` is a note
of who was ADDED, not who is still ALIVE: only `LayoutRegistry.prune()` ever
removes a closed member from it, and it runs only when the phone next acts
(`focus`/`layout_state`/…) — never on its own, and never from `watch()`'s own
loop. Between the merge and the phone's next action, `_active_layout` treated
a member list that still named the dead hwnd as a live fence, `_layout_target`
handed that dead hwnd back as THE target (`lay.members[0]` /
`lay.last_member`, both dead), and every guard call — the per-message fence
AND the 0.25 s poll of `watch()` — kept trying to `_refocus`/`raise_window` it,
fighting whatever window was really in front instead of ever giving the
keyboard back. Because the poll runs continuously while a layout is shown
(`_defending`), this was not a one-off refusal: it repeated four times a
second for as long as the dead layout stayed focused.

Fixed at the boundary a member list that can hold a dead window is the
defect, not each caller that reads one: `_active_layout` now checks
`window_manager.user32.IsWindow` across `lay.members` and answers "no active
layout" (fail OPEN, never closed) the moment none of them are alive anymore —
which naturally falls through to the ordinary desktop-pin rule below it, the
exact behaviour a layout with no fence should have. `_layout_target` filters
to the alive members before consulting `pin`/`last_member`, so a pin that
independently names the exact member that just died is never handed back
either. A layout that still has ONE live member among several dead ones keeps
fencing correctly — only an ALL-dead layout releases the fence. The release is
logged once per connection per layout index (`_log_dead_fence`, the
`_log_silent_hook` pattern) so the cause is visible without becoming a diary
entry every poll cycle.

Gate: `tests/test_focus_dead_member.py`, fail-closed in `setup/gates.py`
(0b8/6), five checks each proven by planting the pre-fix code back and
watching exactly the checks that exercise it go red.

## Looking without acting (2026-08-08)
`current_target(layouts, conn)` answers the same question as `guard()` — where
the phone's keys would land right now — and does **none** of its actions: it
raises nothing, arms nothing, writes nothing into `conn` and takes no lock.

It exists because [Caret](caret.md) has to ask that question several times a
second (so the phone knows which row on the PC its keyboard must not cover),
and a passive watcher that could raise a window would be a second focus policy
running beside the real one — on a machine whose owner has twice paid for
windows that were left where he did not put them.

The two answers cannot drift apart, because the rules they share are single
functions: `_layout_target()` (which member the keyboard belongs to when the
foreground is not one) and `_armed_pin()` (whether the desktop pin is live).
`guard()` then acts on that answer; `current_target()` only reports it.

## Connections

### Uses
- [Focus Hook](focus_hook.md) — the instant announcement that the foreground
  moved (the poll is the backstop, never the only defence)
- [Window Manager](window_manager.md) — the user32 readers, `raise_window`,
  and `Layout.last_member`

### Used by
- [Web Layer](web.md) — `guard()` before every message in `TYPING_KINDS`,
  `retarget()` on every one in `RETARGET_KINDS`, `typist()` handed to
  `type_text` / `_paste_text`, and `watch()` as one task per connection
- [Input Injector](input_injector.md) — indirectly: it calls the `typist`
  callable it is given, and imports nothing from here
- [Caret](caret.md) — `current_target()`, to read the caret of the window the
  phone is actually typing into rather than whatever holds the foreground

## Cost
One `GetForegroundWindow` (plus at most eight `GetWindow` owner hops) per
typing message and per 40 typed characters, on a worker thread — microseconds
each. A raise happens only when focus was actually stolen; the normal path
touches no window at all.
