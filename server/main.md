# Main

**Script:** [Main (script)](main.py)

## Purpose
Entry point: wires all server components in the correct order and runs the event loop.

Order matters and is the whole point of this file:
1. `SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)` — before any screen/GPU access
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
