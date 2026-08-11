# Autostart

**Script:** [Autostart (script)](../autostart.py)

## Purpose
"Start with Windows", as a switch over WINDOWS rather than a preference of our own (Settings window, round R2, owner 2026-08-07). `installed()` asks the Task Scheduler whether the logon task exists; `set_autostart(on)` creates or deletes the same task the installer creates.

## Why a Task Scheduler task and not HKCU Run
The app runs ELEVATED — Windows' UIPI silently eats injected input from a non-elevated process whenever an elevated window has focus (the 2026-07-29 dead-mouse failure, see [Input Injector](input_injector.md)) — and **HKCU Run silently refuses to start elevated apps**. So autostart is a logon task with `/RL HIGHEST`, exactly as `setup/installer.nsi` → `SecAutostart` creates it (see [Setup (folder)](../../setup/___setup.md)), and there is no second, easier place to keep this state.

Which is why the switch had to read the real thing. A tick that merely remembered an intention would show "on" over a machine with no task (a user who unticked autostart during a repair install) or "off" over one the installer had just created — and a setting that only pretends is the failure mode this project keeps paying for (THE REPEAT LAW).

## Connections

### Uses
- [Config](config.md) — `autostart_task` (the task name, `"VibeCoder"`, the same `${APP_NAME}` the installer uses), `FROZEN`, `PROJECT_ROOT`

### Used by
- `gui/settings_window.py` (see [GUI (subfolder)](../gui/___gui.md)) — the STARTUP card's "Start with Windows" switch: `installed()` on every open, `set_autostart()` on every toggle

## Functions
- `installed()` → bool: `schtasks /Query /TN <task>`, return code 0. Asked every time the window opens — never cached, never inferred.
- `set_autostart(on)` → `(ok, message)`: `schtasks /Create /F /TN … /SC ONLOGON /RL HIGHEST /TR "<target>"` or `/Delete /F`. `message` is empty on success and is the last line of what Windows said on failure, shown by the window instead of leaving a switch that lies. When the `subprocess`/`OSError` call itself fails (schtasks missing, the call timing out) the message is a fixed plain sentence — never `f"...{e}"` — and the exception's own text goes to the log only (round R2's second independent grader, 2026-08-07: a Python exception repr is not a sentence the owner can act on, the same finding that hit `notify.set_agent_hook` in the same round).
- `_target()`: what the task runs — `"<exe>" --minimized` when frozen, `"<python>" "<…/server/gui_main.py>" --minimized` in a dev checkout, so the switch is honest about what it created either way.
- `_run(args)`: one `subprocess.run` with `CREATE_NO_WINDOW` (a windowed PyInstaller app has no console, and every call would otherwise flash a black window across the owner's screen) and a 15 s timeout.

## Honest limits
- `/RL HIGHEST` needs an ELEVATED caller. The packaged app always is (`--uac-admin`); a dev run from a plain shell is not, and Windows refuses — the message says to run as administrator rather than silently failing.
- The uninstaller deletes the task too (`installer.nsi` → Uninstall), so nothing survives a removal.
