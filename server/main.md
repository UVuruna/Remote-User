# Main

**Script:** [Main (script)](main.py)

## Purpose
Entry point: wires all server components in the correct order and runs the event loop.

Order matters and is the whole point of this file:
1. `declare_dpi_awareness()` — pointer-sized context handle (`c_void_p`) with a CHECKED return, before any screen/GPU access. A bare-int ctypes call fails silently on 64-bit and the process stays DPI-unaware — found when monitor enumeration returned scaled sizes; the server refuses to start if the declaration fails.
2. Logging (rotating file in `logs/` + console)
3. `ScreenStreamer` → `FrameHub.push_threadsafe`
4. `InputInjector` with the captured monitor's pixel rect
5. Token + QR display, then uvicorn serves the FastAPI app

## Connections

### Uses
- [Config](config.md) — all settings
- [Screen Streamer](capture.md), [Input Injector](input_injector.md), [Web Layer](web.md), [Pairing](pairing.md)

### Used by
- Launched by the user: `python server/main.py`

## Functions
- `setup_logging()`: rotating file handler + console, per root logging policy
- `main()`: async wiring described above; stops the capture thread on shutdown
