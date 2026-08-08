# gui/

The desktop face of Remote User: a PySide6 window + tray icon around the
[Server Core](../__about/server_core.md). This is what the installed EXE runs (entry
point: `server/gui_main.py`, documented under [Server (folder)](../___server.md));
the CLI (`server/main.py`) stays for dev. Design follows root DESIGN.md
(dark-first, soft depth, one accent) with a palette shared with the web
client (see [Theme](__about/theme.md) for the verified overlap).

## Files

| File | Tier | One line |
|------|------|----------|
| `main_window.py` | Algorithmic | window shell, tray, layout, wiring — [about](__about/main_window.md) · [flow](__flow/main_window.md) |
| `theme.py` | Algorithmic | TWO palettes (dark + light), the QSS generated from the active one, effect helpers, and `apply_theme` — which styles the APPLICATION, so one call re-themes every window — [about](__about/theme.md) · [flow](__flow/theme.md) |
| `switch.py` | Algorithmic | the sun/moon theme pill (smoothstep knob, ~600 ms) and the snapshot COVER the palette changes under, so the repaint cascade is never seen — [about](__about/switch.md) · [flow](__flow/switch.md) |
| `sizing.py` | Algorithmic | how a window declares the minimum it TRULY needs — `heightForWidth`, not `minimumSizeHint`, because a short layout overlaps instead of clipping — [about](__about/sizing.md) · [flow](__flow/sizing.md) |
| `controls_editor.py` | Algorithmic | the Controls WINDOW: assembles/saves `actions.json` from the three modules below — [about](__about/controls_editor.md) · [flow](__flow/controls_editor.md) |
| `controls_data.py` | Algorithmic | actions.json plumbing, no Qt: paths, client-table parsing, the shipped-pool merge, wheel-order helpers — [about](__about/controls_data.md) · [flow](__flow/controls_data.md) |
| `controls_widgets.py` | Algorithmic | command-editing widgets: chord recorder, pool table, command form — [about](__about/controls_widgets.md) · [flow](__flow/controls_widgets.md) |
| `controls_order.py` | Algorithmic | arrangement/order-editing widgets: the per-set ladder, the wheel-order ring — [about](__about/controls_order.md) · [flow](__flow/controls_order.md) |
| `traffic_window.py` | Algorithmic | the Traffic window: bytes to and from the phone over time, with a grey band wherever nobody was connected — [about](__about/traffic_window.md) · [flow](__flow/traffic_window.md) |
| `settings_window.py` | Algorithmic | the Settings window: APPEARANCE (this PC's theme + the PHONE's), STREAM, NOTIFICATIONS, and FOCUS beside STARTUP on one row — [about](__about/settings_window.md) · [flow](__flow/settings_window.md) |
| `__init__.py` | Trivial | package marker; one-line docstring naming `gui_main.py` as the entry point |

## Connections

### Uses
- [Server Core](../__about/server_core.md) — `ServerController`: start/stop/state/info
- [Pairing](../__about/pairing.md) — QR PNG bytes, Tailscale executable/URL lookup
- [Config](../__about/config.md) — current settings, `save_user_settings()`, `app_version()`
- [Autostart](../__about/autostart.md) — the real Task Scheduler logon task behind "Start with Windows"
- [Foreground Lock](../__about/foreground_lock.md) — Windows' own foreground rule behind "Don't let applications steal focus"
- [Notify](../__about/notify.md) — the agent-hook switch, and the phone-reported TTS voices the Voice dropdown shows
- [Updates](../__about/updates.md) — startup GitHub-release check for the Update button
- [Screen Capture](../__about/capture.md) — monitor count for the settings combo
- [Client (folder)](../../client/___client.md) — `theme.py`'s palette is
  deliberately the same slate/cyan family as `client/style.css` (verified
  token-by-token in [Theme](__about/theme.md))

### Used by
- The installed EXE (`RemoteUser.exe` → `gui_main.py`); dev:
  `python server/gui_main.py`. `gui_main.py` itself lives one level up and is
  documented in [Server (folder)](../___server.md) — it has no dedicated
  `__about`/`__flow` pair of its own.

## Design Decisions

- **The GUI never blocks**: start/stop/restart run on worker threads; a 1 s
  `QTimer` polls controller state. A `_busy` flag gates the buttons meanwhile.
- **Close = hide to tray** (server keeps running); a one-time balloon explains
  it. Quit is explicit, in the tray menu.
- **Settings apply = save + restart**: values persist to the user settings
  file (see [Config](../__about/config.md)) and the server restarts to pick them up —
  no half-applied state.
- **One window, one job** (round R2, owner 2026-08-07). The main window had
  become the pairing window AND the configuration window, so every new switch
  made the QR page taller. The stream form and the notify switch moved into
  the [Settings window](__about/settings_window.md); the main window kept the
  QR, the status and the buttons, and its measured minimum fell from 503x937
  to 404x703. The three doors — Controls, Traffic, Settings — became ICON
  buttons in one even row, with drawn SVG assets (`assets/icon-*.svg`) and no
  trailing "…". **Never a font glyph**, on the desktop as on the phone: a
  glyph depends on whatever face the machine has, and this project has paid
  for that once already (the ✥ that came out a blunt cross on the owner's
  phone, 2026-08-05). `theme.icon()` substitutes the colour into the SVG
  source before Qt parses it, because Qt's SVG renderer does not resolve
  `currentColor` — which also keeps the palette out of the asset, so one icon
  file will serve a light theme too.
- **Everything but STREAM acts on the toggle**
  ([Settings window](__about/settings_window.md)): a window where some
  switches act and others wait for a button is a window nobody can trust. And
  every switch that can be REFUSED (the agent hook, the focus lock, the logon
  task) puts its tick back from the REAL state and says what happened — a
  setting that only pretends is the failure this project keeps paying for.
- **The Controls editor** ([about](__about/controls_editor.md) ·
  [flow](__flow/controls_editor.md), ROADMAP Phase G1 — owner
  spec 2026-08-05): the "Controls…" button opens a dialog that edits the USER
  copy of `actions.json` (`user_actions_path()` seeds the %LOCALAPPDATA% copy
  from the read-only bundled default on first use and repoints the running
  server via `config.apply`; the phone refreshes on its next connection).
  Custom sets: create/delete/rename, 4 buttons each (a built-in action or a
  RECORDED chord — `ChordRecorder` captures the combination from the PC
  keyboard, it is never typed), icon from the client's own icon set
  (`load_client_icons()` parses `const ICONS` out of client/controls.js — one
  source of truth), `enabled` = shown-in-wheel default (revised same day:
  Mouse/Input/Settings are `required` and locked ON; every other shipped or
  custom set toggles; over 8 shown-by-default, extras are switched off on
  save). Any set — shipped ones included — gets per-orientation arrangement
  (`order_land`/`order_port` via `OrderList`, identity order = no entry) with
  a reset to the shipped default. Build round R5 (2026-08-07) added a second
  ring the owner arranges the same way: the phone's WHEEL ORDER itself
  (`WheelOrderDialog`, [Controls Order](__about/controls_order.md)) — a
  separate small dialog, opened from "Wheel order…", storing `wheel_order`
  (a list of set names; position 1 = 12 o'clock, the rest clockwise) at the
  top level of actions.json. End users never hand-edit files; the dialog's
  "Open the file" stays as the power-user escape hatch.
- **Tailscale guidance is three explicit states** (owner principle, 2026-07-22:
  non-technical users must never puzzle over a third-party screen — our window
  says exactly what happens next): **not installed** → "Install Tailscale";
  **installed but signed out** → "Sign in to Tailscale" with plain-language
  text (a browser opens, pick account, come back — and Tailscale's one-time
  questions can be answered with anything); **connected** → button hidden.
  Install ≠ signed in — the missing-login state is the confusing one, found
  live. The default install path is checked too (a fresh install is not on
  this process's cached PATH).
- **The QR is always the HOME link** (first scan happens at home; the phone's
  page guides its own switch to the works-anywhere address). While running
  without a Tailscale address the state is re-checked every few seconds, so
  the hints flip to "connected" the moment the sign-in completes — no restart
  (the server already listens on all interfaces).
- **All colors/radii live in `theme.py` only** (No Hardcoded Values, rules/CODE.md) — no component
  code hardcodes a literal; see [Theme](__about/theme.md) for the token tree
  and its verified (and one honestly-noted un-verified) overlap with the web
  client's palette.
- **And they are read LATE, never at import** (build round R3, 2026-08-07).
  A module-level `QSS = f"...".format(**TOKENS)` or a
  `OUT_COLOR = QColor(TOKENS["accent"])` evaluates ONCE and can never be
  flipped, which is why `theme.qss()`, `traffic_window.out_color()` and
  `controls_widgets.icon_stroke()` are all functions. The palette itself is
  mutated IN PLACE, so every `TOKENS["…"]` inside a `paintEvent` keeps
  working with no call-site change.
- **The theme is applied to the QAPPLICATION, not to a window.** A per-widget
  stylesheet wins over its parent's, so styling the main window alone would
  leave Controls, Traffic, Settings and the wheel-order dialog in the old
  palette. `theme.apply_theme()` is the one call, and it also does the three
  things QSS cannot: re-colour card shadows, rebuild any icon carrying an
  `iconName` property (Qt bakes the tint into the SVG source), and repaint
  the custom-painted widgets.
- **Every window is audited and screenshotted in BOTH palettes**
  (`tests/test_layout_audit_qt.py`) — a light theme is not a repaint of a dark
  one, and a translucent white border that vanishes on white is invisible to
  any check that only ever ran on dark.
