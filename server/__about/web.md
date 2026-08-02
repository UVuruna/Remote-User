# Web Layer

**Script:** [Web Layer (script)](../web.py) ·
**Flow:** [diagram](../__flow/web.md)

## Purpose
The FastAPI application: serves the client page and static files, authenticates the WebSocket, runs the per-client stream loop (H.264 sessions or the JPEG hub fan-out), streams the cursor position, and dispatches input messages to the injector. This is THE protocol file — [CLAUDE.md](../../CLAUDE.md) is the authoritative record of every message type; this doc and its flow diagram describe how this module implements that contract. API docs endpoints are disabled (`docs_url`/`redoc_url`/`openapi_url=None`) — nothing is exposed beyond the routes below.

HTTP routes: `GET /` — the client page ONLY for the APK's WebView (User-Agent carries the `RemoteUserApp` marker); every other browser, on every device, gets `install.html`, the full-screen install funnel (owner rule, hardened 2026-08-02: NO browser ever shows the client — Chrome on Android tablets presents a desktop-Linux User-Agent with no `Android` token, so detect-Android routing served a tablet the live client). Sole exception: no APK built (dev checkout) — the funnel would have nothing to offer, so the client is served. `GET /favicon.ico` (the SVG logo — otherwise every fresh load logs a 404). `GET /ping` (auth-free 204 — the phone's reachability probe for the Tailscale wizard AND the Android shell's start-up address resolver; reveals nothing but "server exists"). `GET /app.apk` (the APK for the funnel's Install button, 404 JSON when unbuilt). `GET /static/*` (client assets, mounted from `SETTINGS.client_dir`). `POST /upload?token=…` (phone → PC image: decodes the upload — Pillow first, with the HEIF opener registered for phone-camera HEIC, EXIF-orientation-corrected; OpenCV is the fallback decoder — puts it in the Windows clipboard, and injects Ctrl+V so the image lands in the focused box by itself). A `no_cache` middleware forces `Cache-Control: no-store` on every response — client files are served straight from disk and a cached `index.html` paired with a fresh `app.js` would crash the page before it ever connects.

**Security rule:** the WebSocket's first message must be a valid `auth` within 5 seconds, or the socket closes with code 4401. Nothing is processed before it (root CLAUDE architecture constraint 3).

**One device at a time** (owner 2026-08-02): the newest authenticated socket wins; the previous one is closed with code **4409** and its client stops auto-reconnecting until a deliberate tap (otherwise two devices would steal the session from each other in a loop). The `auth` message may carry `screen {w, h}` — the device's aspect drives layout window sizing.

**Layouts** (Phase F+ step 1): `layout_pick {x, y}` (armed tap) → `layout_offer {target, windows, grids}`; `layout_create {target, mode, grid, fill, orient}`; `layout_focus {index}` (−1 = full desktop) re-reads the FRESH region each time; `layout_remove {index}`. The server answers every change with `layout_state {layouts, active, region, orient}` (also sent right after auth — the registry survives phone disconnects). All blocking Win32 work is delegated to [Window Manager](window_manager.md) via `to_thread`. Streaming is untouched: the client locks its own view onto `region` (full-frame H.264 is cheap — ROADMAP measurement); the JPEG path narrows via the existing `viewport` mechanism.

The `stream` argument threaded through every handler is either an `H264Manager` or a `JpegStreamer` — one duck interface: `mode`, `width`, `height`, `monitor_index`, `output_count()`, `switch_to()`, `take_screenshot()`; the JPEG side additionally has `set_viewport()`, the H.264 side has `open_session()`/`close_session()`. The connection handler branches once on `stream.mode`.

## Connections

### Uses
- [Window Manager](window_manager.md) — the `layout_*` message handlers (pick/create/focus/remove) and the `layout_state` payload; the registry lives per app instance (server lifetime)
- [Config](config.md) — client dir, favicon path, queue caps, cursor rate, `app_version()`
- [Input Injector](input_injector.md) — `InputInjector`, `BUTTON_FLAGS` for validating the client's `button` field
- [H.264 Streamer](h264_streamer.md) / [Screen Capture](capture.md) — whichever stream backend [Server Core](server_core.md) built
- [Pairing](pairing.md) — `get_tailscale_ip()` for the `tailscale_url` sent in every `config`
- [Monitors](monitors.md) — injector rect recomputed on monitor switch
- [Clipboard](clipboard.md) — screenshot and phone-upload paste

### Used by
- [Server Core](server_core.md) — `create_app(stream, hub, injector, token, stats)` mounted into uvicorn

## Classes

### FrameHub
JPEG mode only: fans frames from the capture thread out to per-client `asyncio.Queue(maxsize=1)` — a lagging client's stale frame is replaced, not queued. H.264 bytes are NOT individually droppable (the stream would corrupt) and use per-session ordered queues (`_stream_h264`) instead.

### ServerStats
`clients: int` — live connected-client count for the desktop GUI, mutated only on the event loop; [Server Core](server_core.md) exposes it through `ServerInfo`.

## Functions
- `create_app(stream, hub, injector, token, stats=None)`: builds the FastAPI app with routes closed over these dependencies (`hub` is `None` in H.264 mode)
- `decode_upload(data)`: Pillow-first (HEIC + EXIF orientation) with an OpenCV fallback → BGR ndarray or `None`
- `_authenticate(ws, token)`: the 5-second auth gate
- `_stream_h264(ws, manager, token)`: opens an `H264Session`, sends `config` with the parsed codec, forwards chunks until the session ends, closes it, opens the next — see the flow doc for the full per-iteration loop and its backpressure handling
- `_send_frames(ws, queue)`: the JPEG per-client sender — pulls from its `FrameHub` queue and forwards
- `_send_cursor(ws, injector)`: polls `cursor_norm()` at `cursor_hz`, sends only on change (quantized to 4 decimals); also the delivery path for `injector.take_input_alarm()`
- `_load_actions()`: reads `actions.json` fresh on every connect (owner edits apply without a restart); missing/invalid file logs and yields empty categories, never a crash
- `_send_config(ws, stream, token, codec=None)`: builds and sends the `config` payload (monitor size, `stream` mode, `hand`, `tailscale_url`, `app_version`, and `codec` when given)
- `_switch_monitor(...)`: `stream.switch_to()` + injector rect update; JPEG resends `config` directly, H.264 clients get it from their fresh session instead
- `_screenshot(ws, stream)`: native-resolution frame → clipboard, toast on the result
- `_receive_input(ws, injector, stream, token)`: the main dispatch loop — see the flow doc
