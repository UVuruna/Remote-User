# Web Layer

**Script:** [Web Layer (script)](web.py)

## Purpose
The FastAPI application: serves the client page and static files, authenticates the WebSocket, streams video out (H.264 or JPEG), streams the cursor position, and routes input messages to the injector. API docs endpoints are disabled — nothing is exposed beyond `/`, `/static`, `/ws`, `/upload`.

HTTP: `GET /` (client page), `GET /favicon.ico` (the logo — otherwise every fresh load logs a 404), `GET /ping` (auth-free 204 — reachability probe for the phone's in-page Tailscale wizard; reveals nothing but "server exists"), `GET /static/*` (client assets), `POST /upload?token=…` (phone → PC image: decodes the upload and puts it in the Windows clipboard via [Clipboard](clipboard.md), token-gated). Upload decoding is Pillow-first with the HEIF opener registered — phone cameras default to **HEIC**, which OpenCV cannot read, and Pillow also applies the **EXIF orientation** (cv2.imdecode ignores it and portrait photos would paste rotated); OpenCV stays as the fallback decoder, and an undecodable upload logs its magic bytes.

Protocol (project [CLAUDE.md](../CLAUDE.md) is the authority):
- client → server (JSON text): `auth`, `pointer_down`, `pointer_up`, `pointer_move`, `scroll`, `viewport` (JPEG mode only), `key_text`, `key_special`, `chord`, `monitor_switch`, `screenshot`
- server → client (JSON text): `config` (after auth and after every stream (re)start — monitor size + `stream` mode + MSE `codec` in H.264 mode), `actions` (the owner's control categories from [actions.json](../ACTIONS.md)), `toast` (user-facing notices), `cursor` (PC pointer position for the client-drawn virtual cursor — capture frames never contain it)
- server → client (binary): H.264 mode — the raw fMP4 byte stream; JPEG mode — 16-byte region header (4 × float32 LE) + JPEG

**Security rule:** the first message must be a valid `auth` within 5 seconds, otherwise the socket closes with code 4401. Nothing is processed before it.

The `stream` dependency is either an `H264Manager` or a `JpegStreamer` — one duck interface (`mode`, `width`, `height`, `monitor_index`, `output_count()`, `switch_to()`, `take_screenshot()`; JPEG adds `set_viewport()`, H.264 adds the session calls). The connection handler branches once on `mode`.

## Classes

### FrameHub
JPEG mode only: fan-out from the capture thread to per-client asyncio queues of size 1 — when a client lags, its stale frame is replaced, not queued. H.264 bytes are NOT individually droppable (the stream would corrupt) and use per-session ordered queues instead.

### ServerStats
Live counters for the desktop GUI (connected client count), mutated only on the event loop; [Server Core](server_core.md) exposes it via `ServerInfo`.

## Functions
- `create_app(stream, hub, injector, token)`: builds the FastAPI app with routes closed over dependencies (`hub` is None in H.264 mode)
- `_authenticate(ws, token)`: the 5-second auth gate
- `_stream_h264(ws, manager)`: the H.264 per-client loop — open a session (fresh init segment + keyframe), send `config` with the parsed codec, forward chunks until the session ends (monitor switch, slow-client reset, encoder death), close it, open the next. A full outbound queue means the client cannot keep up: the whole session is dropped and reopened (a logged, self-healing reset — never a corrupted stream, never unbounded latency).
- `_send_frames(ws, queue)`: the JPEG per-client sender
- `_send_cursor(ws, injector)`: polls `cursor_norm()` at `cursor_hz`, sends only changes (quantized to 4 decimals)
- `_receive_input(ws, injector, stream)`: dispatches input; `viewport` applies only in JPEG mode
- `_switch_monitor(...)`: `switch_to` on the stream backend + injector rect update; JPEG resends `config` directly, H.264 clients get it from their fresh session

## Connections

### Uses
- [Config](config.md) — client dir, queue caps, cursor rate
- [Input Injector](input_injector.md) — pointer dispatch + cursor position
- [H.264 Streamer](h264_streamer.md) / [Screen Capture](capture.md) — the stream backend
- [Monitors](monitors.md) — injector rect on monitor switch
- [Clipboard](clipboard.md) — screenshot + upload

### Used by
- [Main](main.md) — `create_app(...)` into uvicorn
