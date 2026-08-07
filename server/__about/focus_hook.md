# Focus Hook

**Script:** [Focus Hook (script)](../focus_hook.py)

## Purpose
Let **Windows say** the instant the foreground window changes, instead of the
server asking four times a second.

[Focus Guard](focus_guard.md) defends the layout the phone is showing by
polling `GetForegroundWindow` every `WATCH_POLL_S` (0.25 s). That poll is
honest but late, and dictation is the case where late equals never: Android's
recognizer hands over a whole utterance at the END of a listening round, so a
program that holds the keyboard for a quarter of a second while the owner
speaks can still end up with the entire sentence. `SetWinEventHook` with
`EVENT_SYSTEM_FOREGROUND` puts the reaction at **2–5 ms**.

Its own module (THE STRUCTURE LAW, build round R1 — owner-approved
2026-08-07): the guard owns the POLICY (what may hold the keyboard), this owns
the PLUMBING (how we hear about a change). An out-of-context WinEvent hook is
delivered to the thread that installed it, through that thread's own message
queue — so it needs a real thread running a real `GetMessage` loop, which is
not four lines inside a policy module.

## A listener may only SIGNAL
Learned the hard way, and the owner felt it: a callback runs INSIDE Windows'
own event dispatch, inside `GetMessage`, on this one thread — everything the
desktop does with the foreground queues behind it. The first version called
`focus_guard.guard` straight from here, and `guard` waits on a lock held
across a window raise that itself waits for a frame to settle
(`SETTLE_TIMEOUT_S`, 1.5 s, twice on the fallback path). **Measured stall for
a second caller: 2.99 s.**

So a callback hands the work on and returns — `focus_guard.watch` signals its
own loop with `loop.call_soon_threadsafe` — and this module MEASURES that it
did: a callback past `CALLBACK_BUDGET_S` (10 ms) is an ERROR in the log. That
matters beyond politeness, because Windows silently DETACHES a hook that is
slow to return, and we would go on believing we had millisecond reaction while
running on the poll alone. `event_count()` exists for the other half of that:
a counter that does not move while the foreground demonstrably did is the only
evidence a detached hook ever leaves, and
[Focus Guard](focus_guard.md)'s `_log_silent_hook` reports it once.

## The poll stays — belt AND braces
A hook is not a guarantee. `SetWinEventHook` can be refused outright, and
Windows silently detaches a hook whose thread stops pumping messages in time.
So `listen()` **reports whether Windows really took it**, the guard logs a
warning when it did not, and the 0.25 s poll runs either way. The two never
disagree: both call the same `focus_guard.guard`, which serializes them.

## Nothing of ours outlives us
The same discipline as the topmost ledger ([Window Manager](window_manager.md),
owner decree 2026-08-05): a thread and a hook handle left behind are exactly
the kind of leftover this project has been burned by.

- `stop()` is **THE exit call** — idempotent, posts `WM_QUIT` to the listener
  thread, joins it, and logs if it does not go. It is wired into
  [`ServerController.release_windows()`](server_core.md), which every
  documented way out already funnels through: server stop, Apply & restart,
  tray Quit, Ctrl+C, a console close/logoff, Qt's `aboutToQuit`, `atexit`.
- **A join that times out does NOT forget the thread.** Clearing the identity
  there was a real leak (found by an independent probe, 2026-08-07): the hook
  stayed installed, the thread stayed alive with a tid nobody could reach
  again, `_installed` stayed True, and the next `listen()` cheerfully started
  a SECOND thread over the first. It is the topmost leak in another costume —
  something of ours surviving at process granularity, which is exactly what
  the decree rejects. The thread keeps its place in the book, is named at
  ERROR level, nothing is installed over it, and the next `stop()` tries
  again.
- `STOP_TIMEOUT_S` is **0.25 s**, not seconds: `stop()` runs on the Qt UI
  thread at tray Quit and inside the console CTRL handler, whose whole budget
  Windows measures in seconds. Since a listener only signals, the thread is
  always sitting in `GetMessage` ready to take `WM_QUIT`, so the join is
  microseconds in practice — and a miss is an orphan we log and retry, never a
  hang the owner waits through.
- The module registers `stop` with `atexit` itself, and the thread is a
  **daemon** — a stop we somehow never reach may cost us the hook handle at
  process death, but it may never hold the owner's Quit open.
- `release(callback)` drops one listener and stops the thread with the last of
  them, so the listener also dies with the phone's connection.

## Connections

### Uses
- Win32 only (`user32`/`kernel32` via its **own** `ctypes.WinDLL` handles —
  the argtypes pinned here must not reach into the shared `ctypes.windll`
  object every other module uses; a hook handle is a pointer, and the default
  int return truncates it on 64-bit, which would make `UnhookWinEvent` fail on
  the way out)

### Used by
- [Focus Guard](focus_guard.md) — `watch()` registers one listener per
  connection and releases it when the connection ends
- [Server Core](server_core.md) — `release_windows()` calls `stop()`

## API
- `listen(callback) -> bool` — call `callback()` (no arguments) on every
  foreground change; starts the thread on the first caller. **False** means
  Windows refused the hook and the caller is on its backstop alone. The
  callback **may only signal** (see above). Blocking (thread start + a bounded
  wait) — call it through `asyncio.to_thread`.
- `release(callback)` — drop one listener; the thread ends with the last one.
- `stop()` — the exit call: no hook, no thread, nothing left behind.
  Idempotent, and reached from several paths on the way out by design.
- `installed()` — does Windows currently hold a hook of ours? Distinguishes
  "no hook" from "a hook that has gone quiet".
- `event_count()` — how many foreground changes have been announced.

## Notes that cost something to learn
- The event is an **announcement, not data**: the hwnd Windows names may be
  stale by the time a listener acts, so listeners re-read the foreground
  themselves.
- `_dispatch` filters on `OBJID_WINDOW` — the same event id also arrives for
  child parts of a window.
- `GetMessageW` returns **-1** on error, so its `restype` is signed; read
  unsigned, the loop would spin forever on a broken queue.
- A listener that raises is logged and swallowed **at that call only** — one
  bad listener must not take the hook down for the next foreground change.

## Gate
`tests/test_focus_hook.py` (FOCUS HOOK GATE, step 0e of
[build.py](../../setup/build.py), also a full-run check in
`tests/run_guards.py`). It installs **no real hook and touches no real
window** — the owner works on this machine, and a hook a FAILING test forgot
to release is his mouse juddering. The thread, the joins and the identity book
are real; Windows is faked (`tests/_focus_fakes.py`).
