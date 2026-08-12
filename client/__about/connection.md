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
  - `config` — full view reset: monitor size, stream mode/codec,
    `tailscale_url` (fed to the Android bridge), `app_version` (drives the
    update banner); re-inits or tears down MSE; sent after auth and after
    every stream restart.
  - `cursor` — updates `cursorPos` (server-authoritative correction of the
    client's optimistic draw) and `cursorShapeName` from the OPTIONAL `shape`
    field (owner request 2026-08-09, task 142 — the name of the system cursor
    the PC is really showing, so a window edge draws a resize arrow). An older
    server simply sends no `shape`, and `undefined` is what
    [Cursor Shapes](cursor-shapes.md) reads as "draw the arrow". It is kept
    beside `cursorPos`, not on it — the finger rebuilds that object on every
    optimistic move and the shape must not flick back to an arrow while he is
    reaching for the edge.
  - `actions` — replaces `categories`/`appSets`/`groups` and re-renders both
    D-pad groups via `refreshCategories()`; `layout_state` calls it too —
    app-aware sets appear/vanish with layout focus (owner 2026-08-04). Also
    sets `wheelOrder` from `msg.wheel_order` (build round R5, 2026-08-07 —
    the desktop Controls editor's "Wheel order…" list; `sets.js`'s
    `allCats()` sorts by it — see [sets](sets.md)).
  - `toast` — shows a status-pill notice.
- `onmessage` (binary) — H.264: pushed into `mseQueue` + `pumpMse()`; JPEG:
  handed to `onFrame()`.
- `onclose` — code `4401` (bad/expired token) stops retrying and, inside the
  APK, wires a tap-to-rescan handler via `window.Android.rescan()`; any
  other code shows "Disconnected — retrying…" (or "Paused" while hidden).
- `ensureConnected()` — reconnects unless the page is hidden or the token was
  rejected; called on `visibilitychange`(→visible), `pageshow`, and a
  `RECONNECT_MS` watchdog.
- `abandon(sock, why)` / `noteDeadConnection()` — the proof-of-life machinery
  below.

## Proof of life: losing the route (owner report 2026-08-07)

*"kada nismo na wi-fi mreži … dešava nam se prekid veze, i ovo 'Try again'
dugme retko kad pomogne, već moramo više puta, nekad čak i da zatvorimo celu
aplikaciju."*

A WebSocket only ever reports that it CLOSED. It never reports that it is
alive, and on a phone that changes networks those are two very different
silences — both of which used to be dead ends with no exit:

| Silence | What `ensureConnected` did |
|---------|----------------------------|
| CONNECTING forever (no route) | skipped it — a socket that is CONNECTING counts as "already trying". Android's own TCP timeout is up to **two minutes**, so a page that looked like it retried every 2 s retried nothing at all. |
| OPEN but never served | skipped it too. The pill said "Connected" over a frozen frame for as long as the server took to reach us — and if the server was stuck handing the session over to this phone's own corpse (see `server/__about/presence.md`), that was until the app died. |

So `connect()` now arms two deadlines — `CONNECT_TIMEOUT_MS` and
`SERVED_TIMEOUT_MS` (`state.js`) — and `abandon()` closes the socket, clears
`ws` so `ensureConnected` will act, **says what is wrong on the pill**, and
retries at once.

The proof of life is the server's **first message of any kind** — not `config`
specifically. Anything arriving proves this address reaches a PC that is
serving us, which is the only question being asked; waiting for `config` would
be wrong twice, since in H.264 mode it comes only after ffmpeg has started
(measured 1.3 s on the owner's machine, slower on a cold DERP relay) while the
failure being defended against sends nothing at all, `actions` included. It
clears the served deadline and forgets every failure before it.

A connection that ends without one — including a flapping link that
opens and drops in under a second, never reaching either deadline — counts
against `LINK_LOST_TRIES`, and a full run calls `window.Android.linkLost()`.

That call is the point of the whole mechanism. **The page owns one address**:
`location.host`, the one the document was loaded from. It can never move
itself, which is why a restart was the only cure. The shell owns both stored
addresses, so the shell is asked, and the shell's resolver decides — a current
address that still answers leaves this document exactly where it is.

Never counted as a lost route: 4401, 4409, and any close while
`document.hidden`. The first two are answers from a server we can hear
perfectly; the third is us closing the socket on purpose.

Gated by `tests/test_link_recovery.py`, which runs this file for real.

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
On open, right after `auth`, `sendTtsInfo()` reports this phone's own
text-to-speech voices (round R2 — see [Notify (client)](notify.md)); the PC
cannot enumerate them and the desktop Settings window's Voice dropdown has
no other source.

`auth` now carries `screen {w, h}` — the device's aspect drives layout window
sizing on the server (tablet vs phone). It also carries **`panel {w, h}`** —
this device's REAL pixels (CSS px x `devicePixelRatio`), the CEILING on what
the PC's encoder may send (owner order 2026-08-12: "what is the point of the
PC sending 4K if the Android device cannot receive it"). A NEW field, never a
new meaning for `screen`: those stay CSS px and an older PC reads them as an
aspect. A PC that does not know `panel` ignores it and streams exactly as
before. See [Decode Caps](decode-caps.md) -> `devicePanel()` and
`server/__about/h264_streamer.md` -> The panel cap. New handlers: `layout_state` (mirror
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

## Presence: the beat and the parting word (owner 2026-08-05)
The PC holds layout windows always-on-top while we are showing them, so it
must know the moment we stop — and a locked phone cannot even close its
socket (Wi-Fi sleeps, the connection goes quiet). The live symptom was the
owner sitting down at his PC with every layout window hovering above
everything. Two signals fix it, both from here:

- **`hb` every `HEARTBEAT_MS` (4 s)** while the page is visible. A paused or
  dead page stops beating all by itself, which is exactly the point — the
  server ends the session after 12 s of silence (its close code is 4408,
  retried like any other drop).
- **`away {excursion}` right before the hide-close.** `inExcursion()`
  ([State](state.md)) answers whether we are leaving for an image picker /
  camera / voice / permission dialog — the owner still working with us, so
  the PC keeps the layout standing — or for good (lock, app closed), which
  frees the desk at once instead of waiting out the heartbeat.

## Creation flow rework (owner feedback 2026-08-02, same day)
`layout_offer` is delegated to `handleLayoutOffer` (list arrival or one tap's
slot — same creation session); `layout_state` ARMS the loading overlay's settle watcher (`settleLayLoading`) instead of hiding it — the server being done is not the screen being still (owner 2026-08-03; see [Layouts](layouts.md)).

## Round 6 (owner report 2026-08-05, the second TOPMOST failure)

- **The parting word carries a REASON.** `away {reason, excursion, net}` —
  `reason` from [State](state.md)'s `hideReason()`, which asks the shell rather
  than guessing; `excursion` stays for an older server; `net` is the phone's
  own traffic counters.
- **The heartbeat carries `net` too**, so the PC can subtract a reading taken
  before an absence from one taken after it.
- **The page connects through `ensureConnected()`, not a bare `connect()`.**
  Every other entry point checked `document.hidden` and this one did not — and
  the shell can load the page while the activity is paused, so an unguarded
  connect opened a full 4K stream to a pocketed phone AND re-raised the
  owner's layout windows on top of his desk.
- **`layoutRestore` is cleared on 4409 and 4401.** A page that was taken over
  or whose link expired is no longer the authority on what the session should
  show, and it must not silently re-raise "its" layout on some later reconnect.
- **The screen is held awake only while the owner is working** — every
  pointer/key event re-arms `KEEP_AWAKE_MS`, and the idle sweep calls
  `Android.keepAwake(false)` so the phone's own timeout takes over.

## Build round R3 (2026-08-07) — themes

The `config` handler gained one line: `applyUi(msg.ui)` — how this phone
should LOOK, decided on the desktop (build round R3, owner answer P4). It sits
with `setStreamBase`, beside the other "what the PC is set to" fields.

**`msg.ui` is handed over exactly as it arrived, absence included.** The line
was written `applyUi(msg.ui || null)` and `applyUi` then defaulted every
missing field to `UI_DEFAULT`, so a `config` frame that said nothing about
appearance — or named only the theme — put the owner's chosen look back to
dark/outlined within half a second of him choosing it, on every connect and
every stream restart. An independent grader found it by measuring pixels
(2026-08-07): the dark theme's whole fill axis was dead on disk.

The `||` is gone. What silence MEANS is decided in `theme.js`, beside the look
and the per-device cache that remembers it — no `ui` changes nothing at all, a
partial `ui` merges onto the look in force. This file's job is only to deliver
the server's word, not to invent one. See [theme.css + theme.js](theme.md).

## The return stopwatch (task 203)

"Coming back from the gallery takes about a minute" cannot be fixed by guessing
which hop is slow, and only one of the hops is visible in the server's log — it
cannot see the seconds before the socket exists, nor the ones after the last
byte, which is exactly where the loading overlay lives.

So the page times its own return and reports it ONCE, as a `client_log` line
into the server log beside everything else — never a panel on the phone (the
2026-08-05 rule: diagnostics go to the log). The marks, each in milliseconds
since the return itself:

| mark | meaning |
|------|---------|
| `open` | the socket opened |
| `served` | the PC answered anything at all |
| `config` | the encoder exists — the first-picture moment (`config` carries the codec parsed from the live init segment) |
| `cube` | the loading overlay left, with the reason it left |

Only a return **into a layout** is timed: that is the seam he reported, and the
only one with an overlay to end the measurement. Coming back to the plain
desktop leaves `RETURN.sent` true, which makes every mark a no-op.

## `auth` carries the quality (task 203)

The `auth` message now includes `quality: effectiveQuality()`. The restatement
below it still goes — an older PC understands only that one — but a PC that
reads the field opens its **first** encoder already correct. Sent only in the
later message, it arrived after the whole connection setup had finished, so
every return from an excursion built one ffmpeg at default quality, tore it
down and built a second: his log, 2026-08-11, `10:08:08,773 → 08,864 →
10,086` — 1.31 s of nothing, on top of everything else. Server side:
`config.quality_override`, one parser for both messages. Gate:
[`tests/test_return_timing.py`](../../tests/___tests.md).
