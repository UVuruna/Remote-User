# Web Layer

**Script:** [Web Layer (script)](../web.py) ·
**Flow:** [diagram](../__flow/web.md)

## Purpose
The FastAPI application: serves the client page and static files, authenticates the WebSocket, runs the per-client stream loop (H.264 sessions or the JPEG hub fan-out), streams the cursor position, and dispatches input messages to the injector. This is THE protocol file — [CLAUDE.md](../../CLAUDE.md) is the authoritative record of every message type; this doc and its flow diagram describe how this module implements that contract. API docs endpoints are disabled (`docs_url`/`redoc_url`/`openapi_url=None`) — nothing is exposed beyond the routes below.

HTTP routes: `GET /` — the client page ONLY for the APK's WebView (User-Agent carries the `RemoteUserApp` marker); every other browser, on every device, gets `install.html`, the full-screen install funnel (owner rule, hardened 2026-08-02: NO browser ever shows the client — Chrome on Android tablets presents a desktop-Linux User-Agent with no `Android` token, so detect-Android routing served a tablet the live client). Sole exception: no APK built (dev checkout) — the funnel would have nothing to offer, so the client is served. `GET /favicon.ico` (the SVG logo — otherwise every fresh load logs a 404). `GET /ping` (auth-free 204 — the phone's reachability probe for the Tailscale wizard AND the Android shell's start-up address resolver; reveals nothing but "server exists"). `GET /app.apk` (the APK for the funnel's Install button, 404 JSON when unbuilt). `GET /static/*` (client assets, mounted from `SETTINGS.client_dir`). `POST /upload?token=…` (phone → PC image: decodes the upload — Pillow first, with the HEIF opener registered for phone-camera HEIC, EXIF-orientation-corrected; OpenCV is the fallback decoder — puts it in the Windows clipboard, and injects Ctrl+V so the image lands in the focused box by itself). A `no_cache` middleware forces `Cache-Control: no-store` on every response — client files are served straight from disk and a cached `index.html` paired with a fresh `app.js` would crash the page before it ever connects.

**Security rule:** the WebSocket's first message must be a valid `auth` within 5 seconds, or the socket closes with code 4401. Nothing is processed before it (root CLAUDE architecture constraint 3).

**One device at a time** (owner 2026-08-02): the newest authenticated socket wins; the previous one is closed with code **4409** and its client stops auto-reconnecting until a deliberate tap (otherwise two devices would steal the session from each other in a loop). The `auth` message may carry `screen {w, h}` — the device's aspect drives layout window sizing.

**Layouts** (Phase F+ step 1): `layout_pick {x, y}` (armed tap) → `layout_offer {target, windows, grids}`; `layout_create {target, mode, grid, fill, orient}`; `layout_focus {index}` (−1 = full desktop) re-reads the FRESH region each time; `layout_remove {index}`; `layout_aspect {index, w, h}` (owner 2026-08-03 — store a layout's own W:H, `0/0` = the phone's own shape, then focus it so the windows are re-placed). The creation list leaves out every window that already belongs to a layout (`LayoutRegistry.member_hwnds`), and asks for tabs only from tab-capable apps (`uia.has_tabs`). The server answers every change with `layout_state {layouts, active, region, orient}` (also sent right after auth — the registry survives phone disconnects). All blocking Win32 work is delegated to [Window Manager](window_manager.md) via `to_thread`. Streaming is untouched: the client locks its own view onto `region` (full-frame H.264 is cheap — ROADMAP measurement); the JPEG path narrows via the existing `viewport` mechanism.

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
- `_load_actions()`: reads `actions.json` fresh on every connect (owner edits apply without a restart); missing/invalid file logs and yields empty categories, never a crash. Also passes through `app_sets` (owner 2026-08-04) — the client shows those ONLY in layout focus, when the focused layout's process matches
- `_send_config(ws, stream, token, codec=None)`: builds and sends the `config` payload (monitor size, `stream` mode, `hand`, `tailscale_url`, `app_version`, `base`, and `codec` when given)
- `_stream_base(stream)`: the desktop Settings card as the phone needs to read it — `{fps, width, height, bitrate, bitrate_mid, bitrate_low}`. The phone's quality panel may only go BELOW this, so it has to be able to state what "Max / Full / High" currently mean and grey out steps that can never take effect (owner 2026-08-05: picking 30 fps under a 10 fps PC changed nothing and said nothing, which read as "the desktop settings do nothing")
- `_switch_monitor(...)`: `stream.switch_to()` + injector rect update; JPEG resends `config` directly, H.264 clients get it from their fresh session instead
- `_paste_text(injector, text, enter)`: a TYPED command button (owner 2026-08-05 — the Claude set's `/usage`, `/model`, `/effort`, which are slash commands written into an app's prompt, not shortcuts). The text goes through the CLIPBOARD and one Ctrl+V rather than key-by-key: a slash command types into an autocomplete menu that re-filters on every character, and one atomic insert cannot be raced by it. `PASTE_ENTER_DELAY` separates the paste from the Enter — the target app is still reacting to the paste — and `enter:false` leaves the line standing (the Menu button, which types `/` so the list can be picked with the cursor). Falls back to `type_text` when the clipboard is held by another app, so the button is never silently dead
- `_screenshot(ws, stream, injector, msg)`: native-resolution frame → optional crop to the region the phone views (the Attach set's Shot sends it — owner 2026-08-04: never the whole desktop) → clipboard; `paste:true` additionally injects Ctrl+V ("Screenshot pasted on the PC")
- `_receive_input(ws, injector, stream, token)`: the main dispatch loop — see the flow doc. New message `press {button, down}` (CLICK/HOLD mouse buttons) → `injector.press`. Every message in `TYPING_KINDS` passes the [Focus Guard](focus_guard.md) FIRST (owner 2026-08-06 — `SendInput` has no target, so a window that steals focus mid-dictation steals the sentence); every message in `RETARGET_KINDS` is the owner choosing a window on purpose and re-arms the guard's target
- `POST /upload_files?token=…`: the multi-file / any-type phone upload — saves to a temp drop folder (previous upload's files cleared here, not after their paste), `clipboard.copy_files` (CF_HDROP) + injected Ctrl+V

`config` additionally carries `apk_version` (the served APK's real version —
the phone's update-banner comparison; `app_version` stays for display).

## Presence — the phone leaving work mode (owner 2026-08-05)
Layout members sit in the always-on-top band while the phone is showing them
([Window Manager](window_manager.md)), which is only correct while somebody
is actually looking. The server used to learn otherwise ONLY from a clean
socket close — and a locked phone rarely manages one: its Wi-Fi sleeps and
the connection just goes quiet. The live symptom was the owner sitting down
at his own PC with every layout window hovering over everything else.

Presence is therefore a POSITIVE signal:

- `hb` — the client beats every 4 s while the page is visible. Any message
  refreshes `conn["seen"]`; silence is what means something.
- `_presence_watchdog(ws, layouts, conn)` — polls every `WATCHDOG_POLL_S`;
  `HEARTBEAT_TIMEOUT_S` (12 s, three missed beats) of silence ends the
  session and closes the socket with 4408.
- `away {excursion}` — the client's parting word when the page is hidden.
  An EXCURSION (image picker, camera, voice, a permission dialog) is the
  owner still working with us: the layout stands, guarded only by
  `EXCURSION_MAX_S` (5 min) — as a live socket via the watchdog, or after
  the socket closes via `_excursion_backstop`. Anything else (lock, app
  closed) is a leave and acts immediately.
- `_leave_session(layouts, conn)` — idempotent (watchdog and socket teardown
  both call it): every layout member leaves the topmost band and is
  minimized, exactly like choosing Desktop. WHICH layout was in use stays
  remembered in the registry, and the next authenticated connection resumes
  there (`layouts.resume_index()` right after the first `layout_state`).

`layout_rename {index, name}` renames a layout; `layout_create` accepts an
optional `name` (the phone's creation panel prefills the window title, the
owner may type anything). A deliberate `layout_focus -1` also calls
`forget_focus()` — the desktop is then the state to resume into.

Proven by `tests/test_presence.py` — a fail-closed step in `build.py`.

## Round 6 (owner report 2026-08-05, the second TOPMOST failure)

Two responsibilities left this module under THE STRUCTURE LAW and now have
their own docs: **[Presence](presence.md)** (heartbeat, the `away` reason, the
excursion hold, the desk rule) and **[Layout API](layout_api.md)** (every
`layout_*` handler). `web.py` keeps the routes, the stream dispatch, the input
dispatch and the connection lifecycle. `toast` is imported from
[Layout API](layout_api.md) — one definition, no copy.

What changed inside the lifecycle itself:

- **Everything that can raise a window is inside the `try`.** The resume-focus
  puts members into the always-on-top band, and it used to run BEFORE the
  block whose `finally` releases them — one exception during setup left them
  stranded.
- **Excursion holds are owned.** The backstop task handle is kept in `holds`
  (a bare `create_task` is only referenced while it runs and can be collected
  mid-sleep) and every new authenticated socket **cancels** the armed ones —
  its only test was "no client connected", which is equally true in every
  ordinary reconnect gap.
- **`away` pauses the stream, whichever kind it is.** `conn["paused"]` stops
  `_stream_h264` from opening the next session; any real message clears it.
  The page normally closes the socket right behind its `away`, but when the
  phone's Wi-Fi falls asleep first the socket lingers — and the encoder was
  filling it for as long as the hold lasted.
- **`conn["away"]` is cleared by a non-excursion `away`**, so an announced
  leave is judged by the 12-second heartbeat budget, never the excursion one.
- **A monitor switch leaves the layout.** Its members stand on the monitor the
  phone stopped watching, still always-on-top over a desk it can no longer
  see, so the switch minimizes them and clears the focus.
- **JPEG capture is on demand.** `FrameHub.subscribers` starts it with the
  first watcher and stops it with the last; it used to start with the SERVER,
  so the fallback mode encoded 30 fps at an empty room all night.
- **Every byte is counted.** `traffic.MeteredSocket` wraps the socket once at
  accept, and the upload endpoints count their own bodies — see
  [Traffic Meter](traffic.md).
- **`hb` and `away` may carry `net`** — the phone's own Android TrafficStats
  counters, forwarded to the meter.
