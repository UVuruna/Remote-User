# Main Window

**Script:** [Main Window (script)](../main_window.py) ·
**Flow:** [diagram](../__flow/main_window.md)

## Purpose

The one desktop window plus the system tray icon: status, in-window pairing
QR, Start/Stop, Tailscale helper, the three doors (Controls, Traffic,
Settings) and the self-update button. A single column of soft-shadowed cards
(DESIGN.md bento style). The window never blocks — server start/stop/restart
run on worker threads, and a 1 s `QTimer` pulls state from the
`ServerController` and repaints. Closing the window hides it to the tray; the
server keeps running until Quit.

**What this window is NOT, since round R2** (owner 2026-08-07). It had become
two things at once: the thing you open to PAIR a phone, and the thing you open
to CONFIGURE a PC — so the settings form sat under the QR forever and every
new switch made the pairing window taller. The stream form and the notify
switch moved to the [Settings window](settings_window.md); what is left is one
job, plus one row of doors to the three windows that do the rest. The measured
minimum fell from **503 × 937** to **404 × 703**.

Those three doors are **icon buttons** now, on a row of their own, sharing it
equally, without the trailing "…" (a dialog is what a button does, not
something its label has to apologise for). Five heterogeneous buttons in one
line was what made the old row — and therefore the whole window — wide. The
icons are drawn SVG assets tinted by `theme.icon()`, **never a font glyph**:
see [GUI (subfolder)](../___gui.md) → Design Decisions for why that rule holds
on the desktop too.

**Sizing** (THE SPACE & LEGIBILITY LAW, 2026-08-05): the window is resizable
with a COMPUTED minimum — `_computed_minimum()` measures the widest real row
(the two button rows at their longest captions, the update button's full
sentence, the QR) and the height its longest guidance
text needs wrapped at that width, then a settle loop takes the larger of that
and Qt's own layout minimum. The old hard `setFixedWidth(400)` is gone — it was
exactly the "element can no longer take the free space" the law forbids. The
QR label keeps its fixed 216 px square (an image at scan size, exempted on the
line with its reason). The three guided reachability texts live in one place,
`REACH_TEXT`, because the refresh loop shows them and the minimum size
measures them.

**The settle itself lives in [Sizing](sizing.md)** (2026-08-06, second pass):
the loop this window used to own asked `minimumSizeHint()`, which quotes a
WRAPPING label at ONE line — 48 px short here — and Qt spends a shortfall by
OVERLAPPING, which is why v0.0.086 still drew the pairing link across the QR on
the owner's screen while every widget reported its full size. The honest
question is `heightForWidth`, and it is asked in one place for all three
windows now.

**The pairing URL is no longer printed under the QR** (owner: *"ja ne znam
zašto stoji taj link tu"*). Sixty characters of random token that nobody reads
and nobody can type: the QR carries it and "Copy link" copies it. It was also
the one element that landed on the QR when the column ran short. A stopped or
failed server puts its reason in `reach_label`, so the card has ONE place that
speaks instead of two.

**The minimum is re-declared whenever the content changes** (owner screenshots
2026-08-06 — the QR's link drawn over the QR, and the guidance text over the
settings card below it). Measuring once, at construction, was the bug: things
arrive later — above all the update button, hidden until the GitHub check
answers — and an explicit `setMinimumSize()` makes Qt stop enforcing its
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
- [Theme](theme.md) — `QSS` (window stylesheet), `card()` (the shared card
  factory), `icon()` (the SVG assets on the three door buttons), `repolish()`
- [Pairing](../../__about/pairing.md) — `tailscale_exe()`, `pairing_urls()`,
  `qr_png()` for the in-window QR
- [Config](../../__about/config.md) — `BUNDLE_DIR`, `FROZEN`, `PROJECT_ROOT`,
  `SETTINGS`, `app_version()`
- [Settings Window](settings_window.md) — built on first open and handed
  `restart_server`, so a stream Apply restarts the server on THIS window's
  worker thread
- [Updates](../../__about/updates.md) — `check()`, the GitHub-release lookup
  behind the Update button (at start and every 15 min)
- [Update Handover](../../__about/update_handover.md) — `begin()`, everything
  from "the installer is on disk" to "the phone is talking to the new version"
- [Traffic Window](traffic_window.md) — built on first open, modeless

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
- `_update` / `_update_state` / `_update_path` / `_update_error` — self-update
  state machine (`None → found → downloading → ready → launched`, or `failed`);
  background workers only SET these attributes, the UI-thread refresh timer is
  the only code that touches Qt with them. `_update_error` carries the SPECIFIC
  reason a `failed` state shows: the 1 s tick redraws the caption, so a
  `setText` alone would be replaced a second later by "Update download failed",
  which is a lie when the download finished and it was the FILE that was wrong

#### Key methods
- `_build_header/_build_qr_card/_build_power_row/_build_window_row/
  _build_update_button/_build_footer/_build_tray` — one builder per zone,
  called once from `__init__` in layout order (see
  [flow](../__flow/main_window.md))
- `restart_server()` — the Settings window's Apply & restart, run the way
  every other server action here runs (worker thread, buttons gated). A no-op
  while a worker is in flight or while the server is stopped: the new values
  are read by the next start
- `_show_settings()` / `_show_traffic()` / `_show_child()` — the modeless
  children, built once and never destroyed on close (they hold live state: a
  chart's history, the phone's reported voices)
- `_toggle_server()` / `_run_worker()` / `_guarded()` — start/stop dispatch
  onto a daemon thread; `_busy` is cleared in a `finally` so a crashing worker
  can never wedge the buttons permanently
- `_refresh()` — the 1 s tick: pill text/color, QR re-render on change,
  reachability hint text (three Tailscale states), tray tooltip, button
  enable/disable
- `_refresh_pairing()` — re-checks LAN/Tailscale addresses while running, so
  signing in to Tailscale mid-session flips the QR to the works-anywhere URL
  with no restart
- `_check_updates()` / `_recheck_updates()` / `_install_update()` /
  `_download_update()` / `_refresh_update_button()` — the self-update flow;
  download runs chunked with a socket timeout (`urlretrieve` has none) so a
  stalled CDN can't leave the button stuck on "Downloading…" forever
- `_begin_handover()` — what "ready" does, and this window's whole share of the
  2026-08-07 fix. It calls
  [`update_handover.begin()`](../../__about/update_handover.md), which verifies
  the download, tells the phone, and arms the detached script that installs
  silently and starts an app again; the window then quits. **The person tapping
  this button is usually a hundred kilometres away, looking at this window
  through the app that is about to be replaced** — so from the tap on there is
  nothing left for anyone to click. `("manual", …)` keeps the old visible-
  installer path for a dev checkout with no elevation; `("stop", text)` puts
  the reason on the button and leaves the app running
- `_settle_minimum()` / `_content_signature()` / `_resettle()` — the law's
  ladder step 3 kept LIVE (see Sizing above): measure, declare, grow — on every
  change to content that can arrive after the window was built
- `showEvent()` — one more settle the first time the window is realized, where
  Qt finally gives every widget its real metrics
- `closeEvent()` — overridden to `event.ignore()` + `hide()` instead of
  closing; shows a one-time tray balloon explaining the app is still running

## Settings trim (owner 2026-08-02); `hand` removed for good (owner 2026-08-07)
"Phone hand" left this window on 2026-08-02 (the cursor-offset system it fed
was removed — the pointer sits under the finger). `config.hand` and
`Settings.hand` are gone from the server entirely as of 2026-08-07 — no UI,
no field, no wire message. An old settings.json carrying `"hand"` is
unaffected: it was never in `USER_ADJUSTABLE`, so it is logged and skipped
like any other unrecognized key. The stream form itself now lives in the
[Settings window](settings_window.md).

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

It lived here until round R2 and now lives in the
[Settings window](settings_window.md)'s NOTIFICATIONS card. The history below
is kept because it is the reason the switch exists at all. It installs or
removes the Claude Code `Stop` hook, and it takes effect **at once** —
nothing restarts.

It reads the real hook state on every open (`agent_hook_installed()`), so it
can never claim an installation that is not there. When the switch cannot be
armed — a packaged app on a PC with no Python for the hook host to run — the
checkbox springs back and the caption says why. This whole control exists
because the feature shipped working in v0.0.081 and stayed silent for a day
on the owner's own PC: nobody had run the install command, and an end user
must never type one.

The logic lives in [notify](../../__about/notify.md); the
[Settings window](settings_window.md) owns the checkbox and its caption.

**Why it could not be switched on in v0.0.085** (owner screenshot 2026-08-06):
`setup/agent_hook.py` was never added to the PyInstaller bundle, so the
installed app answered the tick with a raw `[Errno 2] No such file or
directory: …\_internal\setup\agent_hook.py` and sprang back. Three fixes, one
per layer: the file is bundled (`setup/build.py`), the build now REFUSES to
package without it (the payload gate), and the message the user can see is
plain language about the app, not a path (`notify._hook_module`).

## Build round R3 (2026-08-07) — themes

Two changes, both small on the surface and both load-bearing:

- **The theme is applied to the APPLICATION here.** `__init__` no longer calls
  `self.setStyleSheet(QSS)` — it calls `theme.apply_theme(SETTINGS.ui_theme)`.
  A per-widget stylesheet wins over its parent's, so the old call would have
  stranded Controls, Traffic, Settings and the wheel-order dialog in whatever
  palette they were born with.
- **The top bar carries the sun/moon pill**, after the RUNNING pill
  ([Switch](switch.md)). It owns no state: it is told the current theme and
  its `picked` signal goes straight to `switch.choose_theme`, which persists
  the choice, flips under the cover transition, and moves the twin pill in
  Settings.

The three door buttons now carry a dynamic property `iconName`. That is what
lets `theme.apply_theme` rebuild their icons on a flip: Qt's SVG renderer does
not resolve `currentColor`, so `theme.icon()` bakes the ink into the source
and an icon built once is a picture in the OLD ink afterwards.

`_computed_minimum` grew a `header_row` term for the same reason every other
row is measured: the header sits OUTSIDE the card, so it competes with the
card's width, and the pill added roughly 64 px to the widest state (logo +
subtitle + "STARTING..." + switch). `THEME_SWITCH_W` is imported from the
widget that DRAWS the pill so the measurement can never drift from the row.
