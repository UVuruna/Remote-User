# Server Core

**Script:** [Server Core (script)](../server_core.py) ·
**Flow:** [diagram](../__flow/server_core.md)

## Purpose
The whole server stack as one start/stoppable component, shared by both entry points — `main.py` (CLI, blocking on the calling thread) and the desktop GUI ([GUI (subfolder)](../gui/___gui.md), background thread, buttons). Owns everything `main.py` used to wire inline: the stream-mode decision (H.264 when a verified encoder exists, else JPEG), the input injector, pairing info, the uvicorn lifecycle, and teardown.

**Precondition:** the process is already per-monitor DPI aware ([Bootstrap](bootstrap.md) ran) before this module is imported.

## Connections

### Uses
- [Config](config.md) — every tunable read during `_serve()`
- [Encoders](encoders.md) — `detect_encoder()` decides the stream mode
- [Screen Capture](capture.md) — `JpegStreamer` (lazy import, JPEG branch only)
- [H.264 Streamer](h264_streamer.md) — `H264Manager` (lazy import, H.264 branch only)
- [Input Injector](input_injector.md) — built with the captured monitor's pixel rect
- [Web Layer](web.md) — `FrameHub`, `ServerStats`, `create_app()`
- [Pairing](pairing.md) — `generate_token()`, `pairing_urls()`, `show_pairing()`
- [Monitors](monitors.md) — `rect_for_size()` for the injector's initial rect

### Used by
- `main.py` (script) — CLI entry, `run_blocking()`
- [Desktop Entry Point](gui_main.md) / `gui/main_window.py` (see [GUI (subfolder)](../gui/___gui.md)) — `start()`/`stop()` from Qt buttons, `state`/`info` polled by a timer

## Classes

### ServerInfo
Snapshot the GUI reads: `mode`, `encoder`, `monitor_width`/`height`, `port`, `token`, `qr_url` (Tailscale-preferred), `lan_url`, `tailscale_ip`, live `ServerStats` (client count).

### ServerController
One instance per process; states `"stopped" → "starting" → "running" → "stopped"`, or `"failed"` with `.error` set — the GUI polls this, never silent.

- `start()` — non-blocking, spawns a daemon thread running `asyncio.run(_serve())`; no-op while already alive
- `stop(timeout=10.0)` — force-exits uvicorn (`force_exit` + `should_exit`, NOT graceful shutdown — see the flow doc for why) and joins the thread; waits briefly for the uvicorn instance to exist first when stopping mid-startup, so the exit flags always have something to land on
- `run_blocking()` — CLI mode: runs `_serve()` on the calling thread until Ctrl+C/exit
- `console_pairing=True` prints the QR to the console (CLI); the GUI renders it in-window from `pairing.qr_png()` instead
