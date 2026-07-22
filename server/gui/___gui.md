# gui/

The desktop face of Remote User: a PySide6 window + tray icon around the
[Server Core](../server_core.md). This is what the installed EXE runs
(entry point: `server/gui_main.py`); the CLI (`server/main.py`) stays for dev.

Design follows root DESIGN.md (dark-first, soft depth, one accent) with the
same slate/cyan palette as the web client — one product, one look.

## Files

### `../gui_main.py` — Desktop Entry Point
Bootstrap (DPI → logging → settings) BEFORE Qt and server imports, then
QApplication + window + controller. `--minimized` starts hidden in the tray
(the installer's autostart entry uses it); the server always starts on launch.
Quit lives in the tray menu — closing the window only hides it.

### `main_window.py` — Main Window + Tray
Status pill, pairing QR card, settings card, Start/Stop, Tailscale helper,
tray icon. See [Main Window](main_window.md).

### `theme.py` — Design Tokens + QSS
All colors/radii/typography in one place (root Rule #4). See [Theme](theme.md).

## Connections

### Uses
- [Server Core](../server_core.md) — start/stop/state/info
- [Pairing](../pairing.md) — QR PNG bytes
- [Config](../config.md) — current values + `save_user_settings()`

### Used by
- The installed EXE (`RemoteUser.exe` → `gui_main.py`); dev: `python server/gui_main.py`

## Design Decisions

- **The GUI never blocks**: start/stop/restart run on worker threads; a 1 s
  QTimer polls controller state. A `_busy` flag gates the buttons meanwhile.
- **Close = hide to tray** (server keeps running); a one-time balloon explains
  it. Quit is explicit, in the tray menu.
- **Settings apply = save + restart**: values persist to the user settings
  file (see [Config](../config.md)) and the server restarts to pick them up —
  no half-applied state.
- **Tailscale wizard-lite**: the installer chain-installs Tailscale; in-app,
  the "Set up Tailscale" button runs `tailscale login` (or opens the download
  page in dev) and hides itself once a Tailscale address is detected.
