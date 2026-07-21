# Config

**Script:** [Config (script)](config.py)

## Purpose
Single source of truth for every tunable value (Rule #4 — no hardcoded values elsewhere): network binding, streaming parameters, pairing behavior, logging paths.

Key values:
- `monitor_index` — which monitor is captured (Phase 1: primary; Phase 2 adds runtime switching)
- `max_stream_width` — frames wider than this are downscaled before JPEG encoding; bandwidth guard for 4K monitors
- `jpeg_quality` / `target_fps` — the bandwidth/smoothness trade-off

## Connections

### Uses
- Nothing (leaf module)

### Used by
- Every other server module

## Classes

### Settings
Frozen dataclass; the module-level `SETTINGS` instance is the only one.
