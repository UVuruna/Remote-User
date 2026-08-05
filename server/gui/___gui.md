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
| `theme.py` | Algorithmic | design tokens + QSS + effect helpers — [about](__about/theme.md) · [flow](__flow/theme.md) |
| `controls_editor.py` | Algorithmic | the Controls dialog: load/assemble/save `actions.json` — [about](__about/controls_editor.md) · [flow](__flow/controls_editor.md) |
| `controls_widgets.py` | Algorithmic | its widgets: chord recorder, pool table, command form, arrangement ladders — [about](__about/controls_widgets.md) · [flow](__flow/controls_widgets.md) |
| `traffic_window.py` | Algorithmic | the Traffic window: bytes to and from the phone over time, with a grey band wherever nobody was connected — [about](__about/traffic_window.md) · [flow](__flow/traffic_window.md) |
| `__init__.py` | Trivial | package marker; one-line docstring naming `gui_main.py` as the entry point |

## Connections

### Uses
- [Server Core](../__about/server_core.md) — `ServerController`: start/stop/state/info
- [Pairing](../__about/pairing.md) — QR PNG bytes, Tailscale executable/URL lookup
- [Config](../__about/config.md) — current settings, `save_user_settings()`, `app_version()`
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
  a reset to the shipped default. End users never hand-edit files; the
  dialog's "Open the file" stays as the power-user escape hatch.
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
- **All colors/radii live in `theme.py` only** (root Rule #4) — no component
  code hardcodes a literal; see [Theme](__about/theme.md) for the token tree
  and its verified (and one honestly-noted un-verified) overlap with the web
  client's palette.
