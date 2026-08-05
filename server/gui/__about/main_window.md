# Main Window

**Script:** [Main Window (script)](../main_window.py) ·
**Flow:** [diagram](../__flow/main_window.md)

## Purpose

The one desktop window plus the system tray icon: status, in-window pairing
QR, stream settings, Start/Stop, Tailscale helper, and the self-update button.
A single column of soft-shadowed cards (DESIGN.md bento style). The window
never blocks — server start/stop/restart run on worker threads, and a 1 s
`QTimer` pulls state from the `ServerController` and repaints. Closing the
window hides it to the tray; the server keeps running until Quit.

**Sizing** (THE SPACE & LEGIBILITY LAW, 2026-08-05): the window is resizable
with a COMPUTED minimum — `_computed_minimum()` measures the widest real row
(the three bottom buttons at their longest captions, the update button's full
sentence, the widest settings row, the QR) and the height its longest guidance
text needs wrapped at that width, then a settle loop takes the larger of that
and Qt's own layout minimum. With the shipped strings: **676 × 787** (dev
machine, Segoe UI 13 px). The old hard `setFixedWidth(400)` is gone — it was
exactly the "element can no longer take the free space" the law forbids. The
QR label keeps its fixed 216 px square (an image at scan size, exempted on the
line with its reason). The three guided reachability texts live in one place,
`REACH_TEXT`, because the refresh loop shows them and the minimum size
measures them.

## Connections

### Uses
- [Server Core](../../__about/server_core.md) — `ServerController`: the `start` /
  `stop` / `state` / `info` / `error` surface this window drives and polls
- [Theme](theme.md) — `QSS` (window stylesheet), `card_shadow()`,
  `repolish()`
- [Pairing](../../__about/pairing.md) — `tailscale_exe()`, `pairing_urls()`,
  `qr_png()` for the in-window QR
- [Config](../../__about/config.md) — `BUNDLE_DIR`, `FROZEN`, `PROJECT_ROOT`,
  `SETTINGS`, `app_version()`, `save_user_settings()`
- [Updates](../../__about/updates.md) — `check()`, the startup GitHub-release lookup
  behind the Update button
- [Screen Capture](../../__about/capture.md) — `BaseCapture.output_count()`, imported
  locally inside `_populate_monitors()` to size the monitor combo

### Used by
- `gui_main.py` (documented under [Server (folder)](../../___server.md) —
  it has no dedicated doc of its own): builds `QApplication`, constructs
  `MainWindow(controller)`, shows it unless `--minimized`

## Classes

### `MainWindow(QMainWindow)`

#### Key attributes
- `controller` — the `ServerController` this window drives
- `_busy` — `True` while a start/stop/restart worker thread is in flight;
  gates the power/apply buttons
- `_shown_qr_url` — last QR URL actually rendered, so `_refresh()` skips
  re-encoding an unchanged QR every tick
- `_tick` — refresh-timer counter; throttles the Tailscale-address recheck to
  every `PAIRING_RECHECK_TICKS` ticks instead of every second
- `_update` / `_update_state` / `_update_path` — self-update state machine
  (`None → found → downloading → ready → launched`, or `failed`); background
  workers only SET these attributes, the UI-thread refresh timer is the only
  code that touches Qt with them

#### Key methods
- `_build_header/_build_qr_card/_build_settings_card/_build_bottom_row/
  _build_update_button/_build_footer/_build_tray` — one builder per zone,
  called once from `__init__` in layout order (see
  [flow](../__flow/main_window.md))
- `_toggle_server()` / `_run_worker()` / `_guarded()` — start/stop dispatch
  onto a daemon thread; `_busy` is cleared in a `finally` so a crashing worker
  can never wedge the buttons permanently
- `_refresh()` — the 1 s tick: pill text/color, QR re-render on change,
  reachability hint text (three Tailscale states), tray tooltip, button
  enable/disable
- `_refresh_pairing()` — re-checks LAN/Tailscale addresses while running, so
  signing in to Tailscale mid-session flips the QR to the works-anywhere URL
  with no restart
- `_check_updates()` / `_install_update()` / `_download_update()` /
  `_refresh_update_button()` — the self-update flow; download runs chunked
  with a socket timeout (`urlretrieve` has none) so a stalled CDN can't leave
  the button stuck on "Downloading…" forever
- `closeEvent()` — overridden to `event.ignore()` + `hide()` instead of
  closing; shows a one-time tray balloon explaining the app is still running

## Settings trim (owner 2026-08-02)
"Phone hand" is gone from the Settings form (the cursor-offset system it fed
was removed — the pointer sits under the finger); `config.hand` stays a
legacy field the server still sends and nobody reads. Frame rate gained a
"10 fps — light" choice. An old settings.json carrying "hand" is ignored on
load with a warning (documented non-fatal path).

## Round 6 (owner 2026-08-05)

- **Traffic…** joins the bottom row beside Controls…, opening
  [Traffic Window](traffic_window.md) — modeless, because the owner watches it
  WHILE he locks the phone in his other hand. The computed minimum grew by one
  button caption (THE SPACE & LEGIBILITY LAW: the floor is measured from the
  widest real row, and the row just got wider).
- **`_quit` releases the always-on-top band BEFORE stopping the controller.**
  `stop()` joins the server thread for up to 10 s and a 2x2 placement in
  flight can burn every one of them; the owner must not be left with windows
  nailed above his desk because a quit was slow.
- **`_refresh` is guarded as a whole** (the body moved to `_refresh_inner`).
  It runs every second and reaches the network (pairing re-checks); an
  `OSError` from a cosmetic refresh could abort the process — and take the
  daemon server thread, and every always-on-top window it was holding, with it.
