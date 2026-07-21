# Monitors

**Script:** [Monitors (script)](monitors.py)

## Purpose
Enumerates physical monitors with their rects in virtual-desktop coordinates (`EnumDisplayMonitors` + `GetMonitorInfoW`). The injector needs the captured monitor's *position*, which dxcam does not expose — monitors are matched to dxcam outputs by resolution, falling back to enumeration order.

**DPI note:** returns native pixel rects ONLY in a per-monitor-DPI-aware process — [Main](main.md) declares (and verifies) awareness before this module is imported. In an unaware process Windows silently returns scaled sizes (e.g. 3072×1728 for a 4K monitor at 125 %), which is exactly the bug class that forced the checked declaration.

## Connections

### Uses
- Nothing project-internal (leaf module over user32)

### Used by
- [Main](main.md) — initial injector rect
- [Web Layer](web.md) — rect swap on monitor switch

## Functions
- `enumerate_monitors()`: list of `{left, top, width, height, primary}` for active monitors
- `rect_for_size(width, height, fallback_index)`: rect of the monitor matching a dxcam output's resolution; ambiguity falls back to enumeration order, a miss falls back to primary (both logged)
