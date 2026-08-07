# Config

**Script:** [Config (script)](../config.py) ·
**Flow:** [diagram](../__flow/config.md)

## Purpose
Single source of truth for every tunable value in the server (root Rule #4 — no hardcoded values elsewhere): network binding, streaming/H.264 parameters, injection self-check thresholds, pairing, remote access, logging, and update-check settings.

**Two layers, one instance.** Code defaults (the `Settings` dataclass) plus a user settings JSON (`settings.json`, written only by the desktop GUI) validated against a `USER_ADJUSTABLE` allowlist — unknown keys or bad values are logged and skipped, never fatal. The module-level `SETTINGS` is the ONLY instance; runtime changes go through `apply()` (controlled mutation of the shared frozen dataclass via `object.__setattr__`), so every module that imported `SETTINGS` sees updates without rebinding.

**Paths follow the run mode.** Dev checkout: everything stays inside the project (`logs/`, `PAIRING_QR.png` at the root, `actions.json`, ffmpeg from PATH). Installed EXE (`sys.frozen`): user data (settings, token, logs, QR, an owner-edited `actions.json` copy) lives in `%LOCALAPPDATA%\RemoteUser` (Program Files is not writable); bundled read-only data (`client/`, the default `actions.json`) comes from the PyInstaller bundle dir (`sys._MEIPASS`), and the installer places `ffmpeg/` next to the exe.

`app_version()` reads the running version from the bundled `setup/app_info.json` — `"dev"` in an unversioned checkout. It is the single source the GUI footer, the update check, and the `config` WebSocket message all read from.

**Round R2 (owner 2026-08-07) added five user-adjustable keys**, all of them owned by the new [Settings window](../gui/__about/settings_window.md): `notify_speak` / `notify_voice` / `notify_rate` (how the phone SAYS a notice — they ride in every `notify` frame), `foreground_lock` (Windows' own foreground rule, re-applied at every start), and `update_check`, which had lived here as a default with no UI at all. Two non-adjustable companions came with them: `foreground_lock_timeout_ms` + `foreground_lock_ledger_path` (see [Foreground Lock](foreground_lock.md)) and `autostart_task`, the Task Scheduler task name shared with the installer (see [Autostart](autostart.md)).

See the [flow doc](../__flow/config.md) for the full section/key tree.

## Connections

### Uses
- Nothing (leaf module)

### Used by
- Every other file in this folder — [Bootstrap](bootstrap.md), [Server Core](server_core.md), [Screen Capture](capture.md), [H.264 Streamer](h264_streamer.md), [Encoders](encoders.md), [Input Injector](input_injector.md), [Web Layer](web.md), [Pairing](pairing.md), [Updates](updates.md), [Autostart](autostart.md), [Foreground Lock](foreground_lock.md) — plus `gui/main_window.py` and `gui/settings_window.py` (see [GUI (subfolder)](../gui/___gui.md))

## Classes

### Settings
Frozen dataclass — the module-level `SETTINGS` instance is the only one. See the section tree in the flow doc.

## Functions
- `app_version()`: running version from `setup/app_info.json`, `"dev"` when absent/unreadable
- `apply(**changes)`: controlled mutation of the shared `SETTINGS` (bypasses the frozen dataclass via `object.__setattr__`) — components that shape themselves from a value (port, monitor, encoder settings) need a restart to pick up a change
- `load_user_settings()`: applies `settings.json` overrides onto `SETTINGS` once at startup (after logging is configured); missing file = defaults, unreadable file logs and keeps defaults
- `save_user_settings(changes)`: the GUI's only write path — merges `changes` over the existing file (rejects keys outside `USER_ADJUSTABLE` with `ValueError`), writes it, and applies them to the running `SETTINGS`
- `_coerced(key, value)`: validates one override against the dataclass field's declared type (bool checked before int — bool is an int subclass); returns `None` (logged) for an unusable value
- `bitrate_bps(text)`: `"12M"` / `"1200k"` / `"900000"` → bits per second; unparsable text logs and falls back to 12 Mbps rather than killing a stream
- `bitrate_for_level(level)`: the phone's bitrate step resolved against the DESKTOP choice — `"high"` is `h264_bitrate` itself, `"mid"`/`"low"` are `h264_bitrate_mid_pct` / `_low_pct` percent of it. Percentages replaced the absolute `"5M"`/`"1200k"` on 2026-08-05: fixed numbers meant the desktop Bitrate combo applied only while the phone sat on "High", so the PC's choice was silently discarded the moment the phone picked Mid

## Settings trim (owner 2026-08-02); `hand` removed for good (owner 2026-08-07)
"Phone hand" left the Settings form on 2026-08-02 (the cursor-offset system it
fed was removed — the pointer sits under the finger). The `hand` field itself
is now GONE too: the owner ordered every remaining offset-era remnant
deleted, not kept as a compatibility shim ("sve ono što smo računali offset —
uopšte, to se neće koristiti više"), so `Settings.hand` no longer exists and
`config` no longer sends it. Frame rate gained a "10 fps — light" choice. An
old settings.json that still carries `"hand"` is unaffected — it was never in
`USER_ADJUSTABLE`, so `load_user_settings()` logs a warning and skips the
key, exactly like any other unrecognized key.

## apk_version (owner bug 2026-08-02)
`apk_version()` reads the `RemoteUser.apk.version` sidecar (written by
`build_apk.py`, bundled by `build.py`) — the version of the APK this server
serves at /app.apk. The phone's update banner compares against THIS, not
`app_version()`: the APK does not change with desktop-only releases, and the
old comparison offered a phantom update forever.

## Build round R3 (2026-08-07) — themes

### APPEARANCE (build round R3, owner-approved 2026-08-07)

Three settings and one table, all in `USER_ADJUSTABLE` or their own section:

| Key | Values | What it is |
|---|---|---|
| `ui_theme` | `dark` / `light` | THIS PC's palette (`server/gui/theme.py`) |
| `phone_theme` | `dark` / `light` / `colored` | the PHONE's |
| `phone_fill` | `transparent` / `full` | outlined buttons, or filled |

`SET_COLORS` is the per-set colour palette the owner adopted (this round's
answer P5): Mouse `#38BDF8`, Input `#4ADE80`, Settings `#94A3B8`, Edit
`#A78BFA`, Attach `#F59E0B`, Navigate `#2DD4BF`, Media `#F87171`, Windows
`#818CF8`, VSCode `#3B82F6`, Chrome `#FACC15`, Explorer `#FB923C`, Claude
`#D97757`, Cursor `#F472B6`. Custom sets are deliberately NOT listed — the
owner names his own sets, so the phone hands each unnamed one the next colour
of this same palette that nothing already wears (`client/theme.js`). One table
to tune, no second list to keep in step.

`ui_config()` is the whole APPEARANCE half of a `config` frame,
`{theme, fill, colors}`. It lives here rather than in `web.py` on purpose: the
desktop owns this decision, this file owns the desktop's settings, and the web
layer's job is only to put it on the wire.
