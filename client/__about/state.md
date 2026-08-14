# State

**Script:** [State (script)](../state.js)

## Purpose

Tunables (zoom limits, scroll fling constants, timing constants), the shared
mutable state every other client script reads and writes (canvas/context
refs, connection/view/gesture state), and the three primitives everything
else is built on: `setStatus`
(status pill), `toCanvasPx` (pointer event → canvas-px point) and `send`
(JSON WebSocket send with the "dead socket → visible reconnect" fallback).

Loads FIRST of the six client scripts (see [Client (folder)](../___client.md))
— every other script assumes these globals already exist.

## Connections

### Uses
- Nothing (no dependencies — this is the base of the load order)

### Used by
- [Render](render.md), [Input Geometry](input-geometry.md), [Controls](controls.md),
  [Gestures](gestures.md), [Connection](connection.md) — all read/write this
  file's `let`/`const` bindings as shared global state (classic `<script>`
  tags in one page share one lexical scope — this is not a module with
  exports; there is no import/export anywhere in the client)

## Key State & Functions

- **Tunables** — `ZOOM_MAX`, scroll fling constants, `VIEWPORT_MARGIN`,
  `RECONNECT_MS`, MSE live-edge constants: `LIVE_MAX_BEHIND_S` (jump forward
  past this), `LIVE_TARGET_BEHIND_S` (where a catch-up lands — 0.45s since
  task 151, was 0.1s/six frames at 60fps until his log showed that landing
  turning one late chunk into a starved player), `LIVE_STARVED_S` (below
  this the clock has run PAST the data — his freeze), `LIVE_UNFREEZE_TICK_MS`
  (the `waiting`/`stalled` backstop tick interval). Consumed by
  [Live Clock](live-clock.md)'s `liveAction`, fed in by
  [Render](render.md)'s `applyLiveDecision` — the regulator's OWN numbers
  (slow rate, degrade hold, min flush gap) live in live-clock.js itself,
  nothing outside it reads them.
- **Losing the route** (owner 2026-08-07) — `CONNECT_TIMEOUT_MS` = 6 s (a
  socket still CONNECTING has no route), `SERVED_TIMEOUT_MS` = 8 s (OPEN but
  never sent a `config` is a server we cannot hear), `LINK_LOST_TRIES` = 3
  (connections in a row that were never served, after which the shell is
  asked to re-probe both addresses). A WebSocket only ever reports that it
  CLOSED — these three are how the page tells a dead route from a quiet PC.
  The mechanism itself lives in [Connection](connection.md).
- **DOM/connection refs** — `canvas`, `ctx`, `statusEl`, `token` (from the URL
  query string, delivered by the QR/pairing link).
- **View/stream state** — `monitor`, `baseRect`, `view` (pan/zoom transform),
  `baseBitmap`/`detailBitmap`/`detailRegion` (JPEG mode), `ws`, `streamMode`
  (`"h264"` default-overridden-to `"jpeg"` at declaration, actually set from
  the server's `config` message), `cursorPos`.
- **Gesture state** — `touchMode` (single active mode: move/drag/scroll/pan),
  `pointers` (Map of active PointerEvents), `pinch`, `primary` (the steering
  finger).
- **Region-streaming state** — `lastSentViewport`, `viewportTimer`, and (T76)
  the H.264 zoom-crop settle: `lastSentZoom`, `zoomSample`, `zoomChangedAt`,
  `zoomSettleTimer`, with `ZOOM_SAMPLE_MS` / `ZOOM_SETTLE_MS` /
  `ZOOM_MIN_DELTA` beside the other tunables. See [Zoom Crop](zoom-crop.md).
- `setStatus(cls, text)` — sets the status pill's class + text.
- Global `error`/`unhandledrejection` listeners route uncaught page errors
  into the status pill (visible, never a silent dead page).
- `toCanvasPx(e)` — PointerEvent → canvas-px point (`clientX/Y * devicePixelRatio`).
- `send(msg)` — JSON-encodes and sends on `ws` if open; otherwise (unless the
  4401 "link expired" state is active) queues the message when it is one of
  the four TYPING kinds ([Type Queue](type-queue.md) — `typeQueueKind` /
  `typeQueuePush`), flips the status pill to "Reconnecting…" and calls
  `ensureConnected()` (defined in [Connection](connection.md), loaded later —
  safe because `send` only *references* it inside a function body, and it is
  always defined by the time `send` is actually invoked at runtime, well
  after all six scripts have finished loading).
- `flushTypeQueue()` — called by [Connection](connection.md)'s `sock.onopen`,
  after `auth` is sent: drains the queue in order, or gives up on the whole
  of it at once (`typeQueueFlush`'s staleness rule) and toasts
  `noteTypeQueueLoss()` — the 2026-08-13 fix for a typing message that used
  to vanish silently in a short reconnect (see [Type Queue](type-queue.md)).

## Design Decisions

- **One shared global scope, on purpose.** The client has "no framework, no
  build step" (project CLAUDE.md). Converting this into ES modules would
  require explicit `export`/`import` for ~40 cross-referenced bindings — a
  much larger, riskier rewrite for a project that intentionally has no build
  step. Classic `<script>` tags loaded in order are semantically identical to
  one concatenated file (same shared lexical scope), which is what this split
  preserves. See [Client (folder)](../___client.md) Design Decisions for the
  full god-file-split rationale.
## Layouts (Phase F+ step 1)
`layouts` / `layoutActive` / `layoutRegion` mirror the server's `layout_state`
(the server owns the list — it survives phone disconnects); `layoutArm` is the
one-shot "next canvas tap picks a window" flag set by the Layout (+) button;
`viewLocked()` selects the view's bounds rect (see [Render](render.md)) and
the cursor clamp — it no longer disables gestures: since owner 2026-08-04
pinch zoom/pan works in layout focus too, bottoming out at the layout's own
framing. `layoutAnchorPos()` (owner decree 2026-08-09) reads the focused
layout's `pos` — the Move handle's free-axis anchor for the letterboxed
picture, 0.5 when no layout is focused or an old server sent none; render.js
feeds it to [View Anchor](view-anchor.md)'s fit, so the picture sits where
the handle put it ON THIS SCREEN (the server always centres the PC windows).
`send()` also refuses to auto-reconnect after a 4409 takeover (one device at a
time — a background reconnect would steal the session back in a loop).
`markExcursion()` / `inExcursion()` (owner 2026-08-05) mark the moments we
leave the app on purpose — image picker, camera, voice — so the hide that
follows within `EXCURSION_GRACE_MS` is announced to the server as an
excursion instead of the end of work ([Connection](connection.md) sends it,
and the PC keeps the layout standing while the owner picks). `HEARTBEAT_MS`
is the other half: presence is a positive signal, and its silence is what
tells the PC to hand the desk's windows back.

`layoutRestore` (owner 2026-08-04) remembers the focused layout across the
socket churn every excursion causes (gallery pick, permission dialog — the
page hides, the socket closes by rule, the fresh connection's server-side
focus starts at desktop): armed by each focused `layout_state`, cleared in
`send()` by a DELIBERATE `layout_focus`/`layout_remove`, consumed by
[Connection](connection.md)'s handler which re-sends `layout_focus` so the
app comes back into the layout it was working in.

`fontZoomByLayout` (owner 2026-08-05) — Ctrl+-/= steps the font-zoom
staircase ([Gestures](gestures.md)) has applied, per layout index; `send()`
shifts the indices down when a `layout_remove` goes out.

## `kbShift` (owner 2026-08-03 / 2026-08-07)
The canvas keeps its full height when the soft keyboard opens — it is never
SQUEEZED ([Render](render.md)) — and it is never lifted by the **keyboard's
height** (owner 2026-08-07, withdrawing his own 2026-08-03 request: the row he
types into is almost never at the bottom of the PC screen, so a keyboard-sized
lift carried the text he was watching off the top).

It IS lifted by the caret's **shortfall** — the few pixels, if any, by which
the row he is typing in would otherwise sit under the keys ([Caret](caret.md)).
`kbShift` is where that answer lands in CSS px (`caretRise / devicePixelRatio`)
and `toCanvasPx` adds it, so a finger touching a risen picture still lands on
the PC pixel under it.

**This section said "`kbShift` is therefore 0" until 2026-08-09**, months after
`caretRise` started feeding it. It was harmless while every rise really was 0
for other reasons — and it is exactly the kind of confident, false note that
costs the next round an hour, so it is recorded here rather than quietly
replaced.

## When the PC cannot see the caret (2026-08-09)
Nothing moves. There was a `caretUnknownMode` here — his idea of 2026-08-07, a
Settings switch letting a window he knows sits at the bottom take the old
whole-keyboard lift. It was declared, **assigned nowhere**, and `config.ui`
never grew the field, so the branch it fed in `caret.js` could not run: a
documented switch that did nothing. Both were deleted (owner decree 2026-08-07
— legacy things are removed, not kept). It comes back the day the desktop
Settings window grows the control that would feed it, and not before.

## `imeHeight` (2026-08-09)
What the SHELL measured the soft keyboard to be, in CSS px — 0 when it is
closed, and 0 forever in a dev browser that never tells us. The page cannot
measure this for itself under edge-to-edge; see
[Render](render.md) → the keyboard-height pipe, and
[Insets](../../android/__about/Insets.md) for why only the shell can answer.

## The hide reason comes from the shell (owner failure 2026-08-05)

`inExcursion()` used to be the ONLY answer to "why is the page hiding", and its
grace was 90 s armed by the last Mic/picker tap. Locking the tablet six seconds
after dictating was therefore announced to the PC as an excursion, and the
owner's Chrome and VSCode hovered over his desk for five minutes. The server
log measured it twice, to the second.

- **`hideReason()`** asks `Android.hideReason()` first — the shell reads the
  screen and keyguard state and knows whether IT launched a picker / camera /
  voice / permission dialog. Its answers are `"lock"`, `"excursion"` and `""`,
  and an EMPTY answer is an answer: it means "switched away", i.e. a leave.
- `EXCURSION_GRACE_MS` is down to 12 s and is now only the **dev-browser
  fallback**, where there is nothing to ask.
- **`phoneNet()`** returns Android's own TrafficStats counters (this app's UID
  and the whole device) for the PC's Traffic window.
- **`KEEP_AWAKE_MS`** (3 min) is how long the screen is held awake after the
  last touch. The shell used to set `FLAG_KEEP_SCREEN_ON` once and never clear
  it, so the tablet never slept by itself — the presence signal the whole
  layout design rests on could only fire if the owner locked it by hand.
