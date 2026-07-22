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
- **Tailscale guidance is three explicit states** (owner principle, 2026-07-22:
  non-technical users must never puzzle over a third-party screen — our window
  says exactly what happens next): **not installed** → "Install Tailscale";
  **installed but signed out** → "Sign in to Tailscale" with plain-language
  text (a browser opens, pick account, come back — and Tailscale's one-time
  questions can be answered with anything); **connected** → button hidden.
  Install ≠ signed in — the missing-login state is the confusing one, found
  live. The default install path is checked too (a fresh install is not on
  this process's cached PATH).
- **The QR follows the login live**: while running without a Tailscale
  address, the pairing URLs are re-checked every few seconds — the moment the
  sign-in completes, the QR/URL/hints switch to the works-anywhere address
  with NO restart (the server already listens on all interfaces). The user
  never has to know why it changed.
