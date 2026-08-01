# Bootstrap

**Script:** [Bootstrap (script)](../bootstrap.py)

## Purpose
Process initialization shared by both entry points, in the one order that matters: **DPI awareness → logging → user settings**. Kept in its own module with no heavy imports (ctypes + stdlib only) because DPI awareness MUST be declared before any module that touches the screen, GPU or injection is imported — `main.py` and [Desktop Entry Point](gui_main.md) both call `init_process()` before importing `server_core`.

## Connections

### Uses
- [Config](config.md) — `SETTINGS` (log paths) and `load_user_settings()`

### Used by
- `main.py` (script) — CLI entry point
- [Desktop Entry Point](gui_main.md) — GUI entry point

## Functions
- `declare_dpi_awareness()`: `SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)` via a checked, pointer-sized (`c_void_p`) ctypes call — a bare-int call truncates on 64-bit and fails SILENTLY (found by a monitor-enumeration test returning DPI-scaled sizes); raises `RuntimeError` on failure rather than run with wrong coordinates
- `setup_logging()`: rotating file handler (`SETTINGS.log_dir`/`log_file`, size/backup caps) + a console handler only when `sys.stderr` exists (a windowed no-console EXE has none — file logging only)
- `init_process()`: the three steps above, in order — call first, before importing `server_core` / `capture` / `gui` modules
