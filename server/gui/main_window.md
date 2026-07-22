# Main Window

**Script:** [Main Window (script)](main_window.py)

## Purpose
The one desktop window plus the tray icon. A single column of soft-shadowed cards:

- **Header** — logo, title, live status pill (`running / starting / stopped / failed`, colored via a QSS dynamic property)
- **QR card** — the pairing QR rendered in-window (from [Pairing](../pairing.md) `qr_png`), the URL (selectable), Copy link / Open in browser, and a reachability hint (Tailscale = anywhere, otherwise LAN-only + setup nudge)
- **Settings card** — monitor, resolution cap, bitrate, frame rate; **Apply & restart** persists via `save_user_settings()` and restarts the server
- **Bottom row** — Start/Stop (primary/danger), "Set up Tailscale" (hidden once connected)
- **Update button** — hidden until the startup [Updates](../updates.md) check (background thread) finds a newer GitHub release; one click downloads the installer to `%TEMP%`, launches it and quits the app (files must not be in use). Workers only set state attributes; the 1 s refresh timer does every Qt touch (`found → downloading → ready → launched`, `failed` re-arms the button as a retry)
- **Tray** — Open / Start-Stop / Quit; tooltip shows mode, encoder and client count; closing the window hides here

## Flow

```
button → worker thread (controller.start/stop/restart)   — UI never blocks
1 s QTimer → _refresh(): pill, QR, URL, hints, tray tooltip, button states
controller.state == "failed" → error text shown in the card (never silent)
```

## Connections

### Uses
- [Server Core](../server_core.md) — the controller it drives
- [Theme](theme.md) — QSS + card shadows
- [Pairing](../pairing.md) — QR bytes
- [Config](../config.md) — current settings + persistence + `app_version()`
- [Updates](../updates.md) — the startup release check behind the Update button
- [Screen Capture](../capture.md) — monitor count for the combo

### Used by
- `gui_main.py` (see [GUI (subfolder)](___gui.md))
