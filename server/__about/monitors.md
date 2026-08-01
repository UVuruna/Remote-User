# Monitors

**Script:** [Monitors (script)](../monitors.py)

## Purpose
Enumerates physical monitors with their rects in virtual-desktop coordinates (`EnumDisplayMonitors` + `GetMonitorInfoW`). The injector needs the captured monitor's *position*, which dxcam does not expose — monitors are matched to a dxcam output by resolution, falling back to enumeration order (which matches DXGI output order on typical single-GPU machines), and finally to the primary monitor.

**DPI note:** returns native pixel rects ONLY in a per-monitor-DPI-aware process — [Bootstrap](bootstrap.md) declares (and verifies) awareness before this module is ever exercised. In an unaware process Windows silently returns scaled sizes (e.g. 3072×1728 for a 4K monitor at 125%) — exactly the bug class that forced the checked DPI declaration.

## Connections

### Uses
- Nothing project-internal (leaf module over `user32`)

### Used by
- [Server Core](server_core.md) — initial injector rect at startup
- [Web Layer](web.md) — rect swap on `monitor_switch`

## Functions
- `enumerate_monitors()`: list of `{left, top, width, height, primary}` for every active monitor
- `rect_for_size(width, height, fallback_index)`: rect of the monitor matching a dxcam output's resolution; an ambiguous size (two monitors, same resolution) falls back to enumeration order, a total miss falls back to the primary monitor — both cases logged as warnings
