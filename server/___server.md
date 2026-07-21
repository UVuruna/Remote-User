# server/

The PC side of Remote User: captures the screen, streams JPEG frames over WebSocket, and injects mouse input received from the tablet client. Entry point: `main.py`.

## Files

### `main.py` — Entry Point
Declares per-monitor DPI awareness (before anything touches the screen), configures rotating-file logging, wires capture → hub → web app → injector, shows the pairing QR, and runs uvicorn. See [Main](main.md).

### `config.py` — Settings
Single source for every tunable value (port, fps, JPEG quality, stream downscale width, paths). No other file hardcodes these. See [Config](config.md).

### `capture.py` — Screen Streamer
Capture thread: dxcam (DXGI Desktop Duplication) → optional downscale → JPEG encode → callback. See [Screen Streamer](capture.md).

### `input_injector.py` — Input Injector
Win32 `SendInput` via ctypes. Maps 0–1 monitor-normalized coordinates to virtual-desktop absolutes. See [Input Injector](input_injector.md).

### `web.py` — Web Layer
FastAPI app: serves the client page, authenticates the WebSocket, fans frames out (dropping stale ones), dispatches input messages to the injector. See [Web Layer](web.md).

### `pairing.py` — Pairing
Token generation, LAN IP discovery, QR code (console ASCII + PNG). See [Pairing](pairing.md).

## Connections

### Uses
- [Client (folder)](../client/___client.md) — static files served to the tablet

### Used by
- Run directly: `python server/main.py` (venv: `.venv`)

## Design Decisions

- **Frames and input share one WebSocket**; a per-client queue of size 1 drops stale frames when the tablet lags instead of building latency.
- **No input before auth** — the socket closes (4401) unless the first message is a valid `auth` within 5 s.
- **Downscale before encode** — a 4K monitor at native resolution is ~216 Mbps of JPEG; capped at `max_stream_width` (1600 px → ~48 Mbps).
- **DPI awareness is declared in `main.py` before capture/injection imports run** — a root architecture constraint (see project [CLAUDE.md](../CLAUDE.md)).
