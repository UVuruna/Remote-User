# Main Window — Update Flow

**Script:** [Main Window Updates (script)](../main_window_updates.py)

## Purpose

The in-app update, from the periodic check to handing this PC over to the
installer. Split out of [Main Window](main_window.md) on 2026-08-18 (THE
STRUCTURE LAW, VC-R3) on that file's own `# -- updates --` banner.

## It is a STATE MACHINE, and that is why it is worth a file

`None -> found -> downloading -> ready -> launched`, with `failed` beside it.
The button's text, its enabled state and the progress bar are all functions of
that single `_update_state` field, and keeping them in one module is what
stops the day they disagree.

The three captions the button can wear moved here with it
(`UPDATE_FAILED_TEXT`, `UPDATE_HANDOVER_TEXT`) because this is what writes
them — [Main Window](main_window.md) imports them back for one reason only:
its computed minimum has to MEASURE every string this button can show (THE
SPACE & LEGIBILITY LAW).

## The check is PERIODIC, and that word cost a day

Until 2026-08-07 the check ran once per start. The owner's own machine:
installed 0.0.089 at 19:49:58, v0.0.090 published at 20:06 — seventeen minutes
later, and he spent the following day testing and reporting a build published
before the fix he was testing for. `UPDATE_CHECK_MS` is fifteen minutes, and
`_recheck_updates` refuses to disturb an update already in flight.

## Why a MIXIN

Same reason as its sibling, [Server Control](main_window_server.md): every
method reaches the window's own update button and progress bar. The state
fields are declared in `MainWindow.__init__` beside everything else it owns —
a mixin that quietly invented attributes on `self` would be the hardest kind
of coupling to read.

## Connections

### Uses
- [Updates](../../__about/updates.md) — the GitHub release check and the
  chunked, resuming download
- [Update Handover](../../__about/update_handover.md) — verify, tell the
  phone, arm the script, go
- [Off-thread](offthread.md) — the check and the download

### Used by
- [Main Window](main_window.md) — as a base class, and for the two captions
  its computed minimum measures

## Classes

### UpdateFlow
- `_check_updates()` / `_recheck_updates()` — the periodic ask
- `_install_update()` — his tap
- `_download_update(upd)` — the worker, and where a failure gets its REASON
- `_begin_handover()` — from here on there is nothing left for anyone to click
- `_show_progress(...)` / `_refresh_update_button()` — the state made visible
