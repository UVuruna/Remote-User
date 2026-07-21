# Main

**Script:** [Main (script)](main.py)

## Purpose
Entry point: wires all server components in the correct order and runs the event loop.

Order matters and is the whole point of this file:
1. `declare_dpi_awareness()` — pointer-sized context handle (`c_void_p`) with a CHECKED return, before any screen/GPU access. A bare-int ctypes call fails silently on 64-bit and the process stays DPI-unaware — found when monitor enumeration returned scaled sizes; the server refuses to start if the declaration fails.
2. Logging (rotating file in `logs/` + console)
3. Stream-mode decision, once: `detect_encoder()` → **H.264** (`H264Manager`, capture runs on demand per client) or the **JPEG** fallback (`JpegStreamer` → `FrameHub.push_threadsafe`, capture always on). The fallback is a warning in the log, never silent.
4. `InputInjector` with the captured monitor's pixel rect
5. Token + QR display, then uvicorn serves the FastAPI app

## Connections

### Uses
- [Config](config.md) — all settings
- [Encoders](encoders.md), [Screen Capture](capture.md), [H.264 Streamer](h264_streamer.md), [Input Injector](input_injector.md), [Web Layer](web.md), [Pairing](pairing.md)

### Used by
- Launched by the user: `python server/main.py`

## Functions
- `setup_logging()`: rotating file handler + console, per root logging policy
- `main()`: async wiring described above; on shutdown stops the JPEG capture thread or shuts the H.264 manager down (sessions + capture)
