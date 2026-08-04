# Connection

**Script:** [Connection (script)](../connection.js) ·
**Flow:** [diagram](../__flow/connection.md)

## Purpose

The WebSocket connection lifecycle: connect/reconnect, the four inbound
message types (`config`/`cursor`/`actions`/`toast`), and the
visibility-gated session (owner security decision: control only while the
page is actually visible). Last of the six client scripts to load — its
final statement (`connect();`) is what actually starts the page running, so
every other script must already be loaded by this point (and is, since
`<script>` tags run synchronously in document order).

## Connections

### Uses
- [State](state.md) — `ws`, `token`, `setStatus`, `RECONNECT_MS`
- [Render](render.md) — `initMse`/`teardownMse`, view/bitmap reset
- [Controls](controls.md) — `updateAnywhereBanner`, `refreshUpdateBanner`,
  `renderGroup`, `showToast`
- The APK's `window.Android` JS bridge (`setTailscaleUrl`, `rescan`) — see
  [Android (folder)](../../android/___android.md)

### Used by
- Nothing downstream — this is the entry point; the page's only other
  trigger is direct user gestures handled in [Gestures](gestures.md)

## Key Functions

- `connect()` — opens `ws://{host}/ws`, sends `auth` on open, and installs
  `onmessage`/`onclose`. Every handler guards on `sock === ws` so a stale,
  still-closing socket's late callbacks never touch a newer connection's
  state.
- `onmessage` (text) — dispatches by `type`:
  - `config` — full view reset: monitor size, `hand`, stream mode/codec,
    `tailscale_url` (fed to the Android bridge), `app_version` (drives the
    update banner); re-inits or tears down MSE; sent after auth and after
    every stream restart.
  - `cursor` — updates `cursorPos` (server-authoritative correction of the
    client's optimistic draw).
  - `actions` — replaces `categories`/`appSets`/`groups` and re-renders both
    D-pad groups via `refreshCategories()`; `layout_state` calls it too —
    app-aware sets appear/vanish with layout focus (owner 2026-08-04).
  - `toast` — shows a status-pill notice.
- `onmessage` (binary) — H.264: pushed into `mseQueue` + `pumpMse()`; JPEG:
  handed to `onFrame()`.
- `onclose` — code `4401` (bad/expired token) stops retrying and, inside the
  APK, wires a tap-to-rescan handler via `window.Android.rescan()`; any
  other code shows "Disconnected — retrying…" (or "Paused" while hidden).
- `ensureConnected()` — reconnects unless the page is hidden or the token was
  rejected; called on `visibilitychange`(→visible), `pageshow`, and a
  `RECONNECT_MS` watchdog.

## Design Decisions

- **Session lives only while watched** (owner security decision) — the
  socket closes the instant the page hides (tab switch, screen lock) and
  reconnects immediately on return, not on the watchdog interval — waiting
  out the interval swallowed the first taps after every app switch.
- **`sock === ws` guards everywhere** — an instant reconnect can create a new
  socket while the old one is still `CLOSING`; without the guard its late
  `onclose` would tear down the new connection's MSE pipeline.
- **4401 is terminal, not retried** — hammering the server with the same
  rejected token helps nobody; the phone needs a fresh QR/pairing link.
## Layouts (Phase F+ step 1)
`auth` now carries `screen {w, h}` — the device's aspect drives layout window
sizing on the server (tablet vs phone). New handlers: `layout_state` (mirror
the list, update the bar, lock/unlock rotation, apply or reset the locked
view) and `layout_offer` (opens the creation panel). Close code **4409** =
another device took over (one device at a time): no auto-reconnect — a
deliberate tap on the status pill takes the session back.

## Layout focus survives excursions (owner 2026-08-04)
Server-side focus is per-connection, so every excursion that hides the page
(gallery pick, a permission dialog) closed the socket and dumped the owner
back on the desktop. The `layout_state` handler now consumes `layoutRestore`
([State](state.md)): a state that says desktop while the client remembers a
focused layout (same index AND name — a pruned/renamed list skips the
restore) means "reconnect reset us", and the client re-sends
`layout_focus {index}` once; a user's deliberate desktop/remove choice clears
the memory in `send()` and is never overridden.

## Creation flow rework (owner feedback 2026-08-02, same day)
`layout_offer` is delegated to `handleLayoutOffer` (list arrival or one tap's
slot — same creation session); `layout_state` ARMS the loading overlay's settle watcher (`settleLayLoading`) instead of hiding it — the server being done is not the screen being still (owner 2026-08-03; see [Layouts](layouts.md)).
