# Web Layer

**Script:** [Web Layer (script)](../web.py) ·
**Flow:** [diagram](../__flow/web.md)

## Purpose
The FastAPI application: serves the client page and static files, authenticates the WebSocket, runs the per-client stream loop (H.264 sessions or the JPEG hub fan-out), streams the cursor position, and dispatches input messages to the injector. This is THE protocol file — [CLAUDE.md](../../CLAUDE.md) is the authoritative record of every message type; this doc and its flow diagram describe how this module implements that contract. API docs endpoints are disabled (`docs_url`/`redoc_url`/`openapi_url=None`) — nothing is exposed beyond the routes below.

HTTP routes: `GET /` — the client page ONLY for the APK's WebView (User-Agent carries the `VibeCoderApp` marker); every other browser, on every device, gets `install.html`, the full-screen install funnel (owner rule, hardened 2026-08-02: NO browser ever shows the client — Chrome on Android tablets presents a desktop-Linux User-Agent with no `Android` token, so detect-Android routing served a tablet the live client). Sole exception: no APK built (dev checkout) — the funnel would have nothing to offer, so the client is served. `GET /favicon.ico` (the SVG logo — otherwise every fresh load logs a 404). `GET /ping` (auth-free 204 — the phone's reachability probe for the Tailscale wizard AND the Android shell's start-up address resolver; reveals nothing but "server exists"). `GET /app.apk` (the APK for the funnel's Install button, 404 JSON when unbuilt). `GET /static/*` (client assets, mounted from `SETTINGS.client_dir`). `POST /upload?token=…` (phone → PC image: decodes the upload — Pillow first, with the HEIF opener registered for phone-camera HEIC, EXIF-orientation-corrected; OpenCV is the fallback decoder — puts it in the Windows clipboard, and injects Ctrl+V so the image lands in the focused box by itself). A `no_cache` middleware forces `Cache-Control: no-store` on every response — client files are served straight from disk and a cached `index.html` paired with a fresh `app.js` would crash the page before it ever connects.

**Security rule:** the WebSocket's first message must be a valid `auth` within 5 seconds, or the socket closes with code 4401. Nothing is processed before it (root CLAUDE architecture constraint 3).

**One device at a time** (owner 2026-08-02): the newest authenticated socket wins; the previous one is closed with code **4409** and its client stops auto-reconnecting until a deliberate tap (otherwise two devices would steal the session from each other in a loop). The `auth` message may carry `screen {w, h}` — the device's aspect drives layout window sizing.

That eviction goes through [`presence.hand_over`](presence.md) since 2026-08-07, and never inline: "the previous device" is nearly always **the same phone on a route that just died**, whose socket is a black hole where `close()` does not fail but waits — and it sat ahead of everything the returning client is sent (`actions`, held notices, `layout_state`, the resumed layout, `config`, the stream, and every per-connection task). The phone's page saw `onopen`, said "Connected", and — since `ensureConnected` never retries an OPEN socket — waited there until the app was killed. That is the owner's report of 2026-08-07; the gate is `tests/test_link_recovery.py`.

**Layouts** (Phase F+ step 1): `layout_pick {x, y}` (armed tap) → `layout_offer {target, windows, grids}`; `layout_create {target, mode, grid, fill, orient}`; `layout_focus {index}` (−1 = full desktop) re-reads the FRESH region each time; `layout_remove {index, close?}` (owner 2026-08-08 — `close:true` also asks every member window to close; absent/false is the plain removal it always was, read as `is True` so nothing truthy can reach his windows by accident, and survivors come back as a toast); `layout_aspect {index, w, h}` (owner 2026-08-03 — store a layout's own W:H, `0/0` = the phone's own shape, then focus it so the windows are re-placed); `layout_member_remove {index, member, grid?}` (owner request 2026-08-09, task 165 — throw ONE window out of a grid: a four becomes a three, a three a two, a two a single. `member` is the ORDINAL of the cell tapped, never a handle; `grid` is the arrangement a four landing on a three should take, and a three is the only size in the catalogue with a real choice. It is **not** a close — the window leaves the layout, leaves the topmost band and goes on standing where it stands; removing the LAST member removes the layout through the existing `remove()` path. Handled in [Layout API](layout_api.md), not here: this dispatcher stands at the 1,000-line wall); `layout_reorder {source, before}` (a row dropped BETWEEN two others — the list's own order, nothing on the PC moves. It moved to [Layout API](layout_api.md) on 2026-08-09 with a fix: **the focus rides on an INDEX, and a reorder moves indices.** `conn["active"]` is a plain position in the registry's list, so re-ordering while a layout was focused left the server calling a DIFFERENT layout active — the phone framed one layout while the bar's ✕ would have offered to close another one's windows. `layout_merge` corrects its own shift arithmetically at the call site; this one corrects it by **identity** — `reorder` never drops a layout, so the object that must stay focused is right there to be found again, and an index recomputed a second way is a second thing to keep in step. Gate: `tests/test_layout_drag.py`, which asserts the survivor by identity and never by number, because "active is still 1" was true all through the bug). The creation list leaves out every window that already belongs to a layout (`LayoutRegistry.member_hwnds`), and asks for tabs only from tab-capable apps (`uia.has_tabs`). The server answers every change with `layout_state {layouts, active, region, orient}` (also sent right after auth — the registry survives phone disconnects). All blocking Win32 work is delegated to [Window Manager](window_manager.md) via `to_thread`. Streaming is untouched: the client locks its own view onto `region` (full-frame H.264 is cheap — ROADMAP measurement); both paths narrow via the existing `viewport` mechanism — the JPEG streamer
crops to it directly, and since T76 (2026-08-14) the H.264 branch hands it to
`layout_api.zoom_region`, which folds the phone's SETTLED visible rect into the
same region path the focused layout feeds (the layout's region is a floor the
crop may never widen past). The message used to be discarded outright in H.264
mode, which is why a zoom magnified already-downscaled pixels.

The `stream` argument threaded through every handler is either an `H264Manager` or a `JpegStreamer` — one duck interface: `mode`, `width`, `height`, `monitor_index`, `output_count()`, `switch_to()`, `take_screenshot()`; the JPEG side additionally has `set_viewport()`, the H.264 side has `new_owner()`/`open_session()`/`close_session()`. The connection handler branches once on `stream.mode`.

## Connections

### Uses
- [Window Manager](window_manager.md) — the `layout_*` message handlers (pick/create/focus/remove) and the `layout_state` payload; the registry lives per app instance (server lifetime)
- [Config](config.md) — client dir, favicon path, queue caps, cursor rate, `app_version()`
- [Input Injector](input_injector.md) — `InputInjector`, `BUTTON_FLAGS` for validating the client's `button` field
- [Cursor Shape](cursor_shape.md) — `current_cursor_name()`, the shape name the cursor stream carries
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
- `_stream_h264(ws, manager, token, conn)`: the thin wrapper that owns this connection's **capture hold** and gives it back on every exit from `_h264_loop` — a cancellation can land anywhere after a session ends, and a hold left behind would keep dxcam running with nobody watching (the 2026-08-07 orphan in another shape)
- `_h264_loop(ws, manager, token, conn, hold)`: opens an `H264Session`, sends `config` with the parsed codec, forwards chunks until the session ends, closes it, opens the next — see the flow doc for the full per-iteration loop and its backpressure handling. **A RE-open is not a FIRST open** (owner report 2026-08-10 — "changing the bitrate kills the whole app"): a bitrate lives inside a running ffmpeg's flags, so the phone's quality panel can only be applied by swapping encoders, and the gap between two of this client's sessions is a working state. Two rules follow. (a) The **hold** is taken in the session's own `finally`, before `owner.release()`: closing the last session is what used to empty `_sessions` and tear dxcam down, and the new encoder then had no frames — ffmpeg cannot write an init segment before it has encoded one, so past `h264_head_timeout` the open raised. (b) A failed **re-open** is retried (`h264_reopen_tries` / `h264_reopen_pause_s`) instead of `ws.close(1011)`, which is still the answer for a failed FIRST open: that socket carries input, layouts, dictation and presence as well as pictures, and one slow encoder restart used to end all of them. Bounded, so this can never become the 2026-07-29 error loop (171 open failures in 90 s). Gate: `tests/test_quality_reset.py`. Every iteration takes a **claim** (`manager.new_owner()`, see [H.264 Streamer](h264_streamer.md) → SessionOwner) BEFORE the encoder thread starts, and releases it on every exit — a clean close, a 4409 takeover, a cancellation, an exception in the send path. That release is what closes the session, because `asyncio.to_thread` cannot cancel the thread it started: on 2026-08-07 one cancelled-mid-open session ran four hours at native 4K with nobody watching. The `push` closure also refuses to touch a released claim's queue, so a "backlog reset" can never fire for a client with no live socket — the two defences are independent on purpose, and `tests/test_stream_lifecycle.py` proves each of them by planting the other's defect
- `_send_frames(ws, queue)`: the JPEG per-client sender — pulls from its `FrameHub` queue and forwards
- `_send_cursor(ws, injector)`: polls `cursor_norm()` at `cursor_hz`, sends only on change (quantized to 4 decimals); also the delivery path for `injector.take_input_alarm()`. Since 2026-08-09 (owner request, task 142) it also carries the SHAPE — [Cursor Shape](cursor_shape.md)'s name for the system cursor the PC is really showing — as the OPTIONAL `shape` field on that same message: never a new message type and never an image, so a page that predates the field ignores it and a name it has never heard of draws the arrow it always drew. The shape counts as "changed", because hovering onto a window edge moves nothing and is the entire feature; a name the PC cannot read (secure desktop) is left OFF the wire rather than guessed. The cadence is untouched — still this loop's, still on change only
- `_load_actions()`: reads `actions.json` fresh on every connect (owner edits apply without a restart); missing/invalid file logs and yields empty categories, never a crash. Also passes through `app_sets` (owner 2026-08-04) — the client shows those ONLY in layout focus, when the focused layout's process matches
- `_send_config` MOVED to [Config API](config_api.md) on 2026-08-12 (THE STRUCTURE LAW — this file stood at the 1,000-line wall again; the actions_api precedent). web.py imports it as `_send_config`, call sites unchanged; the frame gained `stream_region` the same day (the region-crop order)
- `config.stream_base(stream)` (MOVED to [Config](config.md) on 2026-08-10, THE STRUCTURE LAW — every number in it is a reading of SETTINGS): the desktop Settings card as the phone needs to read it — `{fps, width, height, bitrate, bitrate_mid, bitrate_low}`. The phone's quality panel may only go BELOW this, so it has to be able to state what "Max / Full / High" currently mean and grey out steps that can never take effect (owner 2026-08-05: picking 30 fps under a 10 fps PC changed nothing and said nothing, which read as "the desktop settings do nothing")
- `_switch_monitor(...)`: `stream.switch_to()` + injector rect update; JPEG resends `config` directly, H.264 clients get it from their fresh session instead
- `scroll {x, y, ticks, hticks?}` dispatch: `injector.wheel(x, y, ticks, msg.get("hticks", 0))` (owner spec 2026-08-07 — "scroll vertikalni i horizontalni", the gamepad round's right-stick horizontal axis). `hticks` is read with a default so a message that never carries it — every client before this round — reaches [Input Injector](input_injector.md) exactly as it always did
- `_paste_text(injector, text, enter)`: a TYPED command button (owner 2026-08-05 — the Claude set's `/usage`, `/model`, `/effort`, which are slash commands written into an app's prompt, not shortcuts). The text goes through the CLIPBOARD and one Ctrl+V rather than key-by-key: a slash command types into an autocomplete menu that re-filters on every character, and one atomic insert cannot be raced by it. `PASTE_ENTER_DELAY` separates the paste from the Enter — the target app is still reacting to the paste — and `enter:false` leaves the line standing (the Menu button, which types `/` so the list can be picked with the cursor). Falls back to `type_text` when the clipboard is held by another app, so the button is never silently dead
- `_screenshot(ws, stream, injector, msg)`: native-resolution frame → optional crop to the region the phone views (`content.crop_to_region`, moved out of here 2026-08-10 — the Attach set's Shot sends it, owner 2026-08-04: never the whole desktop) → clipboard; `paste:true` additionally injects Ctrl+V ("Screenshot pasted on the PC")
- Two CLAUDE messages live in [Claude API](claude_api.md), not here (2026-08-11 — this file stands at the 1,000-line wall): `paste_text {focus: "claude"}` puts the caret in the Claude prompt before the command is typed and a refusal `continue`s past the paste with nothing injected, and `claude_state {}` answers `{model, model_id, effort, mode, saved}` read from the focused layout's live transcript. The dispatch branches here are two lines each; everything they do is over there.
- `_receive_input(ws, injector, stream, token)`: the main dispatch loop — see the flow doc. New message `tts_info {voices}` (round R2) → `notify.set_voices()`: the phone lists the text-to-speech voices IT has, once per connection, because the PC cannot enumerate another device's TTS engine and the desktop Settings window's Voice dropdown has no other source. New message `press {button, down}` (CLICK/HOLD mouse buttons) → `injector.press`. Every message in `TYPING_KINDS` passes the [Focus Guard](focus_guard.md) FIRST (owner 2026-08-06 — `SendInput` has no target, so a window that steals focus mid-dictation steals the sentence); every message in `RETARGET_KINDS` is the owner choosing a window on purpose and re-arms the guard's target. `key_text` and `_paste_text`'s clipboard-busy fallback also carry the guard INTO the injection (`focus_guard.typist` → `type_text(text, guard)`, build round R1 2026-08-07): the message-level check only fences the instant before the first character, and a dictated sentence is ~1.1 s of `SendInput` (measured). Both then TOAST the phone with whatever never reached the PC (`TYPING_LOST_TOAST`, naming the size of the loss and the start of what is missing) — he is looking at his device while he speaks, and a remainder destroyed in silence is the original failure wearing a different coat. `_paste_text` additionally WITHHOLDS its Enter when the text was cut off: half a slash command must never be submitted. `key_special` (2026-08-13, HALF 2 of the measured typing-loss defect — HALF 1 is the phone's own `client/type-queue.js`) used to inject unconditionally with no loss check at all; the branch now runs `focus_guard.typist(layouts, conn)` once — a single key has no chunks to checkpoint between — and toasts `focus_guard.loss_notice(key, unit="key press")` on a lost fence, the same toast machinery its siblings use. See [Focus Guard](focus_guard.md) → "`key_special` gets the same loss report as its siblings"
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

`layout_state` carries **`dependents`** and **`parent`** per layout since
2026-08-09 (owner decision, task 169 — the ⭐ on the layout selector's rows;
owner request, task 171 — the ✕ chooser must NAME what closing these windows
would destroy). `dependents` is the NAMES of every other layout whose content
was torn out of a window this one holds, in list order; `parent` is simply
whether that list is empty, so the star and the warning are ONE computation and
can never disagree about which row is a trunk. Computed in
`LayoutRegistry.state` off `Layout.sources`, which `resolve_slot` records at
creation — no new probe, no guess from a title. A layout is never its own
parent: the source window may itself be a member of the SAME layout, and closing
that pair together surprises nobody.

**The honest limit of task 169 is CLOSED** (task 173, the same day): `create`
used to store a single `source`, taken from the FIRST slot, so a tab extracted
into cell 2, 3 or 4 of a grid left no record at all and BOTH readers
under-reported — on exactly the grids the mark exists for. Every slot is
recorded now (`Layout.sources`, keyed by the extracted member window), and the
record leaves with its member on `drop_member`, on `prune` and through `merge`.
Gates: `tests/test_layout_drag.py` (both cells, and the names by relation),
`tests/test_layout_member.py` (the record leaves with the window).

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

## Build round R3 (2026-08-07) — themes

### `ui` in every `config` frame (build round R3, 2026-08-07)

`_send_config` gained exactly one key, `"ui": ui_config()` — theme, fill and
the per-set colours, decided on the DESKTOP and nowhere else (owner answer
P4). The shape is built in `config.ui_config()`; this file only ships it, so
the feature costs this module one line and no new responsibility.

Because it rides `config`, a change made while the phone is connected reaches
it on the next connection — which the phone makes on every visibility change,
so in practice locking and unlocking is enough. The desktop's caption says so
rather than promising instant.

## A deliberate session end is not an error loop (2026-08-12)

`_h264_loop` sleeps a full second whenever a session dies younger than two
seconds. That is the correct answer to the 2026-07-29 storm (171 open failures
in 90 s) and the wrong answer to a quality change or a layout region change,
which are healthy sessions ending ON PURPOSE — and the owner paid that second
inside his loading overlay every time he switched layouts twice in a row. The
`reset_stream` hook now MARKS the close (`conn["planned_close"]`), because only
the code that ends a session knows it was intended, and the brake reads the
mark instead of guessing from the clock. Everything else — a backlog reset, an
ffmpeg death, an open failure — leaves the mark False and is paced exactly as
before.

Gate: `tests/test_return_speed.py`, whose storm check plants a session that
dies the instant it is born and proves the brake still holds the loop to about
one open per second.
