# server/

The PC side of Remote User: captures the screen, streams it over WebSocket as H.264 (JPEG fallback), streams the cursor position, and injects mouse/keyboard input received from the tablet client. Two entry points around one core: `gui_main.py` (the desktop app — what the installed EXE runs) and `main.py` (headless CLI for dev).

## Files

### `bootstrap.py` — Process Init (shared)
DPI awareness → logging → user settings, in that order, before any screen-touching import. See [Bootstrap](bootstrap.md).

### `main.py` — CLI Entry Point
Thin: bootstrap + `ServerController.run_blocking()` with console pairing (ASCII QR + viewer). See [Main](main.md).

### `gui_main.py` / `gui/` — Desktop App
PySide6 window (status, in-window QR, settings) + tray around the server core; `--minimized` starts in the tray. See [GUI (subfolder)](gui/___gui.md).

### `server_core.py` — Server Component
The whole stack as one start/stoppable unit shared by both entry points: stream-mode decision, injector, pairing info, uvicorn lifecycle. See [Server Core](server_core.md).

### `config.py` — Settings
Single source for every tunable value (port, fps, H.264 bitrate/GOP/fragmenting, JPEG quality, stream caps, cursor rate, paths). Two layers: code defaults + a user settings JSON written by the GUI; frozen (installed) runs keep user data in `%LOCALAPPDATA%\RemoteUser` and read bundled data from the install dir. See [Config](config.md).

### `capture.py` — Screen Capture
dxcam ownership: `BaseCapture` (camera lifecycle, screenshots, monitor switch) + `JpegStreamer` (the JPEG fallback path with region-of-interest streaming) + `RawFrameSource`/`FrameSink` (raw-frame fan-out feeding the H.264 encoder sessions). See [Screen Capture](capture.md).

### `h264_streamer.py` — H.264 Streamer (primary)
One shared capture, one ffmpeg process per client: fragmented-MP4 H.264 the browser decodes via MSE, codec string parsed from the live init segment. Measured ~1.5 Mbps vs ~37 Mbps JPEG on the same static screen. See [H.264 Streamer](h264_streamer.md).

### `encoders.py` — Encoder Detection
Picks a working H.264 encoder for this machine (NVENC/QuickSync/AMF/software) by test-encoding. See [Encoders](encoders.md).

### `input_injector.py` — Input Injector
Win32 `SendInput` via ctypes. Maps 0–1 monitor-normalized coordinates to virtual-desktop absolutes; `cursor_norm()` reads the position back for the virtual cursor. See [Input Injector](input_injector.md).

### `web.py` — Web Layer
FastAPI app: serves the client page, authenticates the WebSocket, runs the per-client stream loop (H.264 sessions or JPEG hub fan-out), streams cursor positions, dispatches input messages to the injector. See [Web Layer](web.md).

### `pairing.py` — Pairing
Token generation (persisted across restarts), LAN IP discovery, QR code (console ASCII + PNG in the project root). See [Pairing](pairing.md).

### `monitors.py` — Monitors
Physical monitor rects in virtual-desktop coordinates; matches dxcam outputs to positions. See [Monitors](monitors.md).

### `clipboard.py` — Clipboard
Screenshot frames into the Windows clipboard as CF_DIB. See [Clipboard](clipboard.md).

### `updates.py` — Updates
Desktop update discovery via the project's GitHub Releases; the phone updates from the PC instead (`config.app_version` + `/app.apk`). See [Updates](updates.md).

Action sets for the radial wheels are defined in [actions.json](../ACTIONS.md) at the project root (hand-edited by the owner) and served by [web.py](web.md).

## Connections

### Uses
- [Client (folder)](../client/___client.md) — static files served to the tablet

### Used by
- Desktop app: `python server/gui_main.py` (what the packaged EXE runs — see [Setup (folder)](../setup/___setup.md))
- Headless dev CLI: `python server/main.py` (venv: `.venv`)

## Design Decisions

- **Frames and input share one WebSocket.** JPEG mode: a per-client queue of size 1 drops stale frames when the tablet lags. H.264 mode: bytes are a continuous stream and can never be dropped individually — a client that falls a whole queue behind gets its session reset (fresh init segment + keyframe) instead of accumulating latency.
- **One ffmpeg per client, capture shared** — each client's stream starts with its own init segment and keyframe (no mid-stream joining), and capture+encode run only while at least one client is connected.
- **No input before auth** — the socket closes (4401) unless the first message is a valid `auth` within 5 s.
- **Downscale before encode** — a 4K monitor at native resolution is ~216 Mbps of JPEG; capped at `max_stream_width` (1600 px). With H.264 the same screen is ~1.5 Mbps.
- **The client draws the cursor** — DXGI frames never contain the pointer, so the server streams `GetCursorPos` (normalized, on change) and the client renders a virtual cursor.
- **DPI awareness is declared in `main.py` before capture/injection imports run** — a root architecture constraint (see project [CLAUDE.md](../CLAUDE.md)).
