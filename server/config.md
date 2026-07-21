# Config

**Script:** [Config (script)](config.py)

## Purpose
Single source of truth for every tunable value (Rule #4 — no hardcoded values elsewhere): network binding, streaming parameters, pairing behavior, logging paths.

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
