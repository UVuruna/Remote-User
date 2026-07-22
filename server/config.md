# Config

**Script:** [Config (script)](config.py)

## Purpose
Single source of truth for every tunable value (Rule #4 — no hardcoded values elsewhere): network binding, streaming parameters, pairing behavior, logging paths.

**Two layers + one instance.** Code defaults (the dataclass) + a user settings JSON (`settings.json`, written only by the desktop GUI, validated against a `USER_ADJUSTABLE` allowlist — bad values log and fall back, never crash). The module-level `SETTINGS` is the ONLY instance; runtime changes go through `apply()` (controlled mutation of the shared frozen dataclass), so every module sees updates without rebinding.

**Paths follow the run mode.** Dev checkout: everything stays in the project (`logs/`, root `PAIRING_QR.png`, `actions.json`, ffmpeg from PATH). Installed EXE (`sys.frozen`): user data lives in `%LOCALAPPDATA%\RemoteUser` (Program Files is not writable), bundled read-only data comes from the PyInstaller bundle dir, and ffmpeg is the copy the installer placed next to the exe.

**Version + updates.** `app_version()` reads the running version from the bundled `setup/app_info.json` ("dev" in an unversioned checkout) — the single source used by the GUI footer, the update check and the `config` message. `update_repo` / `update_check` drive the desktop's GitHub-release check (see [Updates](updates.md)).

Key values:
- `monitor_index` — which monitor is captured at startup (runtime switching cycles from there)
- `max_stream_width` — frames wider than this are downscaled before encoding; bandwidth guard for 4K monitors
- `use_h264` / `ffmpeg_path` / `h264_encoder_order` — the H.264 path and its startup auto-detection order (NVENC → QuickSync → AMF → libx264)
- `h264_max_width` — H.264 resolution cap, default 3840 (native 4K — sharp zoom; the JPEG-era 1600 cap applies only to the JPEG path)
- `h264_bitrate` / `h264_gop` / `h264_fragment_us` — stream shape: bitrate cap, keyframe interval, one fMP4 fragment per frame
- `h264_head_timeout` / `h264_queue_chunks` — session guards: init-segment wait, per-client outbound cap (a full queue resets the session instead of building latency)
- `cursor_hz` — virtual-cursor position polls per second (sent only on change)
- `jpeg_quality` / `target_fps` — the bandwidth/smoothness trade-off (JPEG fallback)

## Connections

### Uses
- Nothing (leaf module)

### Used by
- Every other server module

## Classes

### Settings
Frozen dataclass; the module-level `SETTINGS` instance is the only one.
