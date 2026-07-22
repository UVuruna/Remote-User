# Server Core

**Script:** [Server Core (script)](server_core.py)

## Purpose
The whole server stack as one start/stoppable component, shared by both entry points — the CLI ([Main](main.md), blocking) and the desktop GUI ([GUI (subfolder)](gui/___gui.md), background thread with buttons). Owns what `main.py` used to wire inline: the stream-mode decision (H.264 when a verified encoder exists, else JPEG), the injector, pairing info, the uvicorn lifecycle, and teardown.

**Precondition:** the process is already DPI-aware ([Bootstrap](bootstrap.md) ran) before this module is imported.

## How start/stop works

```
start():  spawn a daemon thread → asyncio.run(serve)
    serve: detect encoder → build stream backend + injector + app
           publish ServerInfo (mode, encoder, URLs, token, stats)
           state = "running"; uvicorn serves until should_exit
stop():   set uvicorn.should_exit → thread unwinds → capture/session teardown
Failure anywhere → state = "failed", .error set — the GUI shows it, never silent
```

## Classes

### ServerInfo
Snapshot the GUI shows: mode, encoder, monitor size, port, token, `qr_url` (Tailscale-preferred), `lan_url`, `tailscale_ip`, live `ServerStats` (client count).

### ServerController
- `start()` — non-blocking, idempotent while alive; `stop(timeout)` — signals uvicorn and joins
- `run_blocking()` — CLI mode on the calling thread
- `state`: `stopped → starting → running → stopped`, or `failed` + `error`
- `console_pairing=True` prints the QR to the console (CLI); the GUI renders it in-window instead

## Connections

### Uses
- [Config](config.md), [Encoders](encoders.md), [Screen Capture](capture.md), [H.264 Streamer](h264_streamer.md), [Input Injector](input_injector.md), [Web Layer](web.md), [Pairing](pairing.md), [Monitors](monitors.md)

### Used by
- [Main](main.md) — CLI entry
- [Main Window](gui/main_window.md) — Start/Stop buttons + status polling
