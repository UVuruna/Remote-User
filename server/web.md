# Web Layer

**Script:** [Web Layer (script)](web.py)

## Purpose
The FastAPI application: serves the client page and static files, authenticates the WebSocket, streams frames out, and routes input messages to the injector. API docs endpoints are disabled — nothing is exposed beyond `/`, `/static`, `/ws`.

Protocol (project [CLAUDE.md](../CLAUDE.md) is the authority):
- client → server (JSON text): `auth`, `pointer_down`, `pointer_up`, `pointer_move`, `scroll`, `viewport`, `monitor_switch`, `screenshot`
- server → client: `config` JSON text (after auth and after a monitor switch), `toast` JSON text (user-facing notices), and binary frames — 16-byte region header (4 × float32 LE) + JPEG

**Security rule:** the first message must be a valid `auth` within 5 seconds, otherwise the socket closes with code 4401. Nothing is processed before it.

## Connections

### Uses
- [Config](config.md) — client dir
- [Input Injector](input_injector.md) — pointer dispatch

### Used by
- [Main](main.md) — `create_app(...)` into uvicorn

## Classes

### FrameHub
Fan-out from the capture thread to per-client asyncio queues of size 1 — when a client lags, its stale frame is replaced, not queued. `push_threadsafe` is the only method safe to call from the capture thread.

## Functions
- `create_app(hub, injector, token)`: builds the FastAPI app with routes closed over dependencies
- `_authenticate(ws, token)`: the 5-second auth gate
- `_send_frames(ws, queue)` / `_receive_input(ws, injector)`: the two per-client loops
