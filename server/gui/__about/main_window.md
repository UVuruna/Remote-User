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

**The minimum is re-declared whenever the content changes** (owner screenshots
2026-08-06 — the QR's link drawn over the QR, and the guidance text over the
settings card below it). Measuring once, at construction, was the bug: two
things arrive later — the update button (hidden until the GitHub check answers)
and the notify switch's caption (three lines when it reports a failure instead
of one) — and an explicit `setMinimumSize()` makes Qt stop enforcing its
layout's own minimum, so the extra rows had nowhere to go and were painted on
top of what was already there. `_settle_minimum()` is now callable at any time:
it re-measures from the computed floor, declares the result, and grows the
window without ever shrinking below the size the owner gave it (a maximized
window is left alone). `_content_signature()` is what decides WHEN — the six
strings/visibilities that can change length — so the 1 s refresh tick does not
re-lay-out the window every second. `showEvent()` settles again on every show:
a widget measured while hidden can under-report by whole rows (43 px of update
button, here).

**The tray is part of that** — closing this app hides it, it does not close it,
so an update offer can arrive while nobody is looking. Two rules keep that from
undoing the fix: `_resettle` does nothing while the window is hidden (Qt gives
no real metrics there, and the smaller floor it would produce is exactly the
bug), and the signature asks `isHidden()` rather than `isVisible()` — a child
of a hidden window is not visible either, so a visibility-based signature would
"change" the moment the owner closes to the tray and trigger that bad
measurement. `showEvent` is what settles whatever arrived while the window was
away.

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
- `_settle_minimum()` / `_content_signature()` / `_resettle()` — the law's
  ladder step 3 kept LIVE (see Sizing above): measure, declare, grow — on every
  change to content that can arrive after the window was built
- `showEvent()` — one more settle the first time the window is realized, where
  Qt finally gives every widget its real metrics
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

## "Tell my phone when an agent finishes" (ROADMAP H2, owner 2026-08-06)

A checkbox in the Settings card, below Apply. It installs or removes the Claude
Code `Stop` hook, and it takes effect **at once** — nothing restarts, which is
why it sits below the Apply row rather than in the form above it.

It reads the real hook state on every open (`agent_hook_installed()`), so it
can never claim an installation that is not there. When the switch cannot be
armed — a packaged app on a PC with no Python for the hook host to run — the
checkbox springs back and the caption says why. This whole control exists
because the feature shipped working in v0.0.081 and stayed silent for a day
on the owner's own PC: nobody had run the install command, and an end user
must never type one.

The logic lives in [notify](../../__about/notify.md); this window owns the
checkbox and its caption.

**Why it could not be switched on in v0.0.085** (owner screenshot 2026-08-06):
`setup/agent_hook.py` was never added to the PyInstaller bundle, so the
installed app answered the tick with a raw `[Errno 2] No such file or
directory: …\_internal\setup\agent_hook.py` and sprang back. Three fixes, one
per layer: the file is bundled (`setup/build.py`), the build now REFUSES to
package without it (the payload gate), and the message the user can see is
plain language about the app, not a path (`notify._hook_module`).
