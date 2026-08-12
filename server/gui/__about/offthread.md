# Off-thread

**Script:** [Off-thread (script)](../offthread.py)

## Purpose

The desktop window's blocking work, moved off the window's own thread.

[Main Window](main_window.md)'s header has always promised "the window never
blocks". On 2026-08-12 that promise was measured and it was false in two
places, both of them in the state a **first-time user** sits in:

- `pairing.pairing_urls()` — a UDP socket with a 1 s timeout plus the Tailscale
  CLI with a 3 s one, called straight from the 1 s refresh timer every fifth
  tick for as long as Tailscale is not signed in. Up to ~4 s of frozen window,
  recurring, while he waits for that very window to tell him his phone can
  reach the PC.
- `ServerController.stop()` — joins the server thread for up to 10 s, and the
  tray's Quit called it inline. Ten seconds of a dead, un-redrawing window
  after he had already chosen to leave.

Both are the same shape of job the update flow already solved: a daemon thread
does the slow thing and writes a plain attribute; the refresh timer, on the UI
thread, reads it and touches Qt. This module is that pattern given a home —
which is also what THE STRUCTURE LAW required, since `main_window.py` stands at
the 1,000-line wall and cannot grow.

**Nothing in this file may touch Qt.** Every function here runs on a worker
thread; widgets belong to the thread that created them, and the window's own
1 s timer is what redraws.

## Contents

- `QUIT_WAIT_S` — how long a quit waits for the server before going anyway. The
  stop is already bounded; this is the window's patience on top of it, so a
  wedged worker can never leave the app on screen with no way out
- `run(fn, *args, on_done=None)` — the one background-job definition: daemon
  thread, exceptions logged (never raised into a thread nobody joins), and an
  `on_done` that always runs, which is how a caller clears its busy flag. Every
  worker the window starts goes through it
- `refresh_pairing(info)` — the blocking address re-check, writing the new QR /
  LAN / Tailscale values into the controller's `info`. Signing in to Tailscale
  mid-run switches the QR to the works-anywhere URL with no restart, and the
  refresh tick notices the changed URL by itself
- `stop_server(controller)` — begins the shutdown and returns a `finished()`
  predicate (done, or past `QUIT_WAIT_S`). The caller POLLS it from a Qt timer
  instead of waiting on it, so the event loop keeps painting. The desk's
  windows are released BEFORE this is called — the owner's decree of
  2026-08-05, unchanged: nothing may be left nailed above his desk because a
  quit was slow

## Guarded by

`tests/test_gui_nonblocking.py` — the pairing re-check and the quit each
measured against a call that deliberately sleeps, with the GUI thread's own
elapsed time as the evidence.
