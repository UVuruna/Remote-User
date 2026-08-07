# Desktop Entry Point

**Script:** [Desktop Entry Point (script)](../gui_main.py)

## Purpose
The desktop app's entry point — what the installed EXE runs. Follows the same import order as `main.py` (bootstrap before any screen-touching import), then adds Qt: `QApplication` → `MainWindow` wrapped around a `ServerController`. `--minimized` starts the window hidden in the tray (the installer's autostart task uses it); the server itself always starts on launch regardless of the flag. Closing the window hides it to the tray (`setQuitOnLastWindowClosed(False)`) — Quit lives in the tray menu instead.

A `--selfcheck` flag short-circuits `main()`: it imports the whole app graph (bootstrap, Qt, `gui.main_window`, `server_core`) and exits 0 or 1 without ever showing a window. The build's smoke test runs the FROZEN exe with this flag so a PyInstaller packaging gap (a module that silently failed to bundle, e.g. `qrcode`) fails the BUILD instead of surfacing on the owner's first launch — exceptions are caught so the windowed exe's crash dialog can never block the automated check.

## Connections

### Uses
- [Bootstrap](bootstrap.md) — `init_process()`, the first call in both `main()` and `_selfcheck()`
- [Server Core](server_core.md) — `ServerController`
- [GUI (subfolder)](../gui/___gui.md) — `MainWindow`

### Used by
- The installed EXE (`RemoteUser.exe`) — PyInstaller entry point, see [Setup (folder)](../../setup/___setup.md)
- Dev: `python server/gui_main.py`

## Functions
- `_selfcheck()`: imports the full app graph and exits 0 (`"selfcheck OK"`) or 1 — the build's frozen-exe smoke test
- `main()`: bootstrap → `QApplication` → `MainWindow(ServerController(console_pairing=False))` → `controller.start()` → `app.exec()`; jumps straight to `_selfcheck()` when `--selfcheck` is in `sys.argv`

## Nothing outlives the process in the topmost band (owner decree 2026-08-05)

`main()` wires two of the three nets that keep the owner's desk clear —
`app.aboutToQuit` (the ordinary Qt exit: tray Quit, the self-update relaunch,
Windows logging the session off) and `atexit` (anything that ends the
interpreter without Qt, an unhandled exception included), both onto
`ServerController.release_windows()`. The third net is the on-disk ledger,
repaired at the next start, for the paths that run no code at all — Task
Manager, the installer's `taskkill`, a power cut. See
[Window Manager](window_manager.md) — the topmost ledger. `release_windows()`
is idempotent, so all three firing is the design, not a bug.

Windows' FOREGROUND LOCK (round R2) rides the same two in-process nets —
`foreground_lock.release` is connected to `aboutToQuit` and registered with
`atexit` SEPARATELY from `release_windows`, because that one also runs on
every server stop (Apply & restart) and the lock belongs to the process, not
to a server run. Its third net is the same on-disk ledger idea, and it has a
fourth the topmost band does not: the value never reaches the registry, so a
reboot already restores it. See [Foreground Lock](foreground_lock.md).
