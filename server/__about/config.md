# Config

**Script:** [Config (script)](../config.py) ·
**Flow:** [diagram](../__flow/config.md)

## Purpose
Single source of truth for every tunable value in the server (root Rule #4 — no hardcoded values elsewhere): network binding, streaming/H.264 parameters, injection self-check thresholds, pairing, remote access, logging, and update-check settings.

**Two layers, one instance.** Code defaults (the `Settings` dataclass) plus a user settings JSON (`settings.json`, written only by the desktop GUI) validated against a `USER_ADJUSTABLE` allowlist — unknown keys or bad values are logged and skipped, never fatal. The module-level `SETTINGS` is the ONLY instance; runtime changes go through `apply()` (controlled mutation of the shared frozen dataclass via `object.__setattr__`), so every module that imported `SETTINGS` sees updates without rebinding.

**Paths follow the run mode.** Dev checkout: everything stays inside the project (`logs/`, `PAIRING_QR.png` at the root, `actions.json`, ffmpeg from PATH). Installed EXE (`sys.frozen`): user data (settings, token, logs, QR, an owner-edited `actions.json` copy) lives in `%LOCALAPPDATA%\RemoteUser` (Program Files is not writable); bundled read-only data (`client/`, the default `actions.json`) comes from the PyInstaller bundle dir (`sys._MEIPASS`), and the installer places `ffmpeg/` next to the exe.

`app_version()` reads the running version from the bundled `setup/app_info.json` — `"dev"` in an unversioned checkout. It is the single source the GUI footer, the update check, and the `config` WebSocket message all read from.

See the [flow doc](../__flow/config.md) for the full section/key tree.

## Connections

### Uses
- Nothing (leaf module)

### Used by
- Every other file in this folder — [Bootstrap](bootstrap.md), [Server Core](server_core.md), [Screen Capture](capture.md), [H.264 Streamer](h264_streamer.md), [Encoders](encoders.md), [Input Injector](input_injector.md), [Web Layer](web.md), [Pairing](pairing.md), [Updates](updates.md) — plus `gui/main_window.py` (see [GUI (subfolder)](../gui/___gui.md))

## Classes

### Settings
Frozen dataclass — the module-level `SETTINGS` instance is the only one. See the section tree in the flow doc.

## Functions
- `app_version()`: running version from `setup/app_info.json`, `"dev"` when absent/unreadable
- `apply(**changes)`: controlled mutation of the shared `SETTINGS` (bypasses the frozen dataclass via `object.__setattr__`) — components that shape themselves from a value (port, monitor, encoder settings) need a restart to pick up a change
- `load_user_settings()`: applies `settings.json` overrides onto `SETTINGS` once at startup (after logging is configured); missing file = defaults, unreadable file logs and keeps defaults
- `save_user_settings(changes)`: the GUI's only write path — merges `changes` over the existing file (rejects keys outside `USER_ADJUSTABLE` with `ValueError`), writes it, and applies them to the running `SETTINGS`
- `_coerced(key, value)`: validates one override against the dataclass field's declared type (bool checked before int — bool is an int subclass); returns `None` (logged) for an unusable value

## Settings trim (owner 2026-08-02)
"Phone hand" is gone from the Settings form (the cursor-offset system it fed
was removed — the pointer sits under the finger); `config.hand` stays a
legacy field the server still sends and nobody reads. Frame rate gained a
"10 fps — light" choice. An old settings.json carrying "hand" is ignored on
load with a warning (documented non-fatal path).

## apk_version (owner bug 2026-08-02)
`apk_version()` reads the `RemoteUser.apk.version` sidecar (written by
`build_apk.py`, bundled by `build.py`) — the version of the APK this server
serves at /app.apk. The phone's update banner compares against THIS, not
`app_version()`: the APK does not change with desktop-only releases, and the
old comparison offered a phantom update forever.
