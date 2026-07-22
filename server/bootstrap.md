# Bootstrap

**Script:** [Bootstrap (script)](bootstrap.py)

## Purpose
Process initialization shared by both entry points, in the one correct order: **DPI awareness → logging → user settings**. Lives in its own module with no heavy imports (ctypes + stdlib only) because DPI awareness MUST be declared before any module that touches the screen/GPU is imported — the reason `main.py`/`gui_main.py` import `server_core` only after `init_process()` ran.

## Functions
- `declare_dpi_awareness()`: `PER_MONITOR_AWARE_V2` via a pointer-sized (`c_void_p`) checked call — a bare-int ctypes call fails SILENTLY on 64-bit and clicks land at wrong coordinates; refuses to run on failure
- `setup_logging()`: rotating file handler (user log dir) + console, per root logging policy
- `init_process()`: the three steps above, in order

## Connections

### Uses
- [Config](config.md) — log paths + `load_user_settings()`

### Used by
- [Main](main.md), [GUI (subfolder)](gui/___gui.md) — first call in both entry points
