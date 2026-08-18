# Main Window — Server Control

**Script:** [Main Window Server (script)](../main_window_server.py)

## Purpose

The desktop window's power over the server it wraps: start, stop, restart and
QUIT. Split out of [Main Window](main_window.md) on 2026-08-18 (THE STRUCTURE
LAW, VC-R3) on that file's own `# -- server control --` banner.

## Why a MIXIN and not a helper object

Every method here reaches the window's own widgets (`start_btn`, the status
pill, the tray) and its `controller`. A helper object would have to be handed
that `self` anyway, and passing a window into an object that then drives its
widgets is the same coupling written down twice — once in the constructor and
once at every call. `MainWindow(ServerControl, UpdateFlow, QMainWindow)` says
the truth: this is the window, split by subject.

## The rule that outranks everything here

**Nothing we force on a window may outlive us** (project `CLAUDE.md`). `_quit`
is one of the documented exit paths that funnel through
`ServerController.release_windows`, and `tests/test_focus_hook.py` asserts
that this exact function calls it — the check names this file since the split.

## The worker rule

Start and stop block. They run through `_run_worker` on
[Off-thread](offthread.md) with `_busy` gating the buttons, and the worker
never touches a widget: the refresh timer redraws on the UI thread. A window
that froze while its server started would be indistinguishable from a crashed
one.

## Connections

### Uses
- [Off-thread](offthread.md) — every blocking call
- `server_core.ServerController` — the thing being controlled

### Used by
- [Main Window](main_window.md) — as a base class

## Classes

### ServerControl
- `restart_server()` — the Settings window's "Apply & restart"
- `_run_worker(target)` / `_restart_worker()` — the off-thread half
- `_toggle_server()` — the Start/Stop button
- `_show_window()` — the tray double-click
- `_quit()` — the tray Quit, and the release funnel it must call
