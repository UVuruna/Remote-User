# Foreground Lock

**Script:** [Foreground Lock (script)](../foreground_lock.py) · **Flow:** [flow](../__flow/foreground_lock.md)

## Purpose
The desktop half of the focus work (Settings window, round R2, owner 2026-08-07 — *"ne daj aplikacijama da otimaju fokus"*). Where [Focus Guard](focus_guard.md) fences ONE window so a dictated sentence cannot end up in another agent's editor, this module fences the whole PC: Windows already refuses to let a process push itself in front of the user for N milliseconds after the user's last input, and the default N is small enough to be no rule at all. `SPI_SETFOREGROUNDLOCKTIMEOUT` raises N.

It is a MACHINE-WIDE setting, which is the entire reason this file is shaped the way it is — see below.

## Connections

### Uses
- [Config](config.md) — `foreground_lock` (the owner's switch), `foreground_lock_timeout_ms` (what we raise it to), `foreground_lock_ledger_path`

### Used by
- [Server Core](server_core.md) — `repair_stranded()` then `apply(True)` in `ServerController.__init__`, before anything of ours can raise a window
- `gui/settings_window.py` (see [GUI (subfolder)](../gui/___gui.md)) — the FOCUS card's switch calls `apply(on)` and reports a refusal
- `server/gui_main.py` and `server/main.py` — `release()` on every process-exit path

## The safety, in three pieces
The always-on-top band twice left the owner's Chrome and VSCode nailed above everything ([Window Manager](window_manager.md) → the topmost ledger, owner decree 2026-08-05). A machine-wide setting is the same danger with a longer reach, so it is guarded the same way — plus one net the topmost ledger does not have:

1. **The flag word is ZERO.** No `SPIF_UPDATEINIFILE`, so the value never reaches the registry: it lives in this Windows session's memory only, and a reboot or logoff already restores it. `SPIF_NOTHING` in the source is a named constant precisely so nobody adds a flag to it by accident.
2. **We get to run code** — tray Quit, Ctrl+C, a console close, Qt's `aboutToQuit`, `atexit`, an unhandled crash: `release()` writes back the value we found. Idempotent; being called three times on the way out is the design. Deliberately NOT part of `ServerController.release_windows()`, which also runs on every server stop (Apply & restart) — this lock belongs to the process, not to a server run.
3. **We do NOT** — Task Manager, the installer's `taskkill`, a power cut: the ledger is mirrored to `foreground_lock_ledger_path` on every change and `repair_stranded()` reads it at the next start.

## The identity check
`repair_stranded()` writes the old value back ONLY while the current timeout is still the one the killed run left behind (`raised`). Anything else — the owner, another tool, a Windows restart that already reset it — means someone has moved it since, and their value outranks our note. This is the same rule that keeps a recycled window handle out of the topmost repair.

## Functions
- `apply(on)` → bool: raise (remembering the previous value) or `release()`. Idempotent in both directions; `False` means Windows refused and the switch says so.
- `release()` → bool: THE exit call. A no-op when we never raised, so a stranded ledger from a killed run is left for `repair_stranded()` instead of being deleted by an exit that owes nothing.
- `repair_stranded()`: at start, before we raise anything of our own.
- `is_raised()` → bool: whether THIS process currently holds it raised (what the switch falls back to when a change is refused).
- `_read()` / `_write(ms)`: the two `SystemParametersInfoW` calls. `_read` returns `None` when Windows refuses; `_write` returns `False`. Neither raises — nothing on an exit path may.

## Honest limits
- The lock does not stop a window that the USER's own click brought forward, and it does not stop an app that already has the foreground. It stops the uninvited jump, which is the reported failure.
- Our own `window_manager.raise_window` bypasses it (it attaches thread input first), so raising a layout for the phone still works with the switch on.
