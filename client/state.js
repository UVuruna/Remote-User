// Vibe Coder client — H.264 (MSE) or JPEG stream rendering, virtual cursor,
// pinch zoom, two configurable D-pad groups, and a single toggle "touch mode"
// that decides what one finger on the screen does.
//
// Split into 6 classic (non-module) scripts loaded in this exact order by
// index.html — they share ONE global scope, same as one concatenated file:
//   state.js (this file) -> render.js -> input-geometry.js -> controls.js
//   -> gestures.js -> connection.js
// Order matters: later files use consts/functions defined in earlier ones.
// See client/__about/state.md for the split rationale.

"use strict";

// --- Tunables -------------------------------------------------------------
const ZOOM_MAX = 6;
const SCROLL_PX_PER_TICK = 40;
const SCROLL_FLING_MIN = 0.35;
const SCROLL_FLING_DECAY = 0.004;
const VIEWPORT_MARGIN = 0.15;
const VIEWPORT_THROTTLE_MS = 150;
// --- The zoom's own crop (T76) --------------------------------------------
// In H.264 every region change rebuilds this client's ffmpeg and the picture
// blinks once. He has accepted ONE blink per finished gesture and no more, so
// the rect is sent only once the gesture has STOPPED — which is an
// observation, not an estimate of anyone's timing: the fingers are ours to
// watch (no pointer down, and the view transform identical across two
// samples). ~280 ms of stillness at 60 ms sampling is the "settled" threshold
// — long enough that the pause between a pinch and its follow-up pan does not
// count as an end, short enough that the sharp picture arrives while his hand
// is still on the way down.
const ZOOM_SAMPLE_MS = 60;
const ZOOM_SETTLE_MS = 280;
// How far the rect must have moved before it is worth a blink at all — the
// same rule the server enforces (layout_api.ZOOM_MIN_DELTA), here so a
// one-pixel drift does not even reach the wire.
const ZOOM_MIN_DELTA = 0.02;
const RECONNECT_MS = 2000;
// --- Losing the route (owner report 2026-08-07) ----------------------------
// *"kada nismo na wi-fi mreži ... dešava nam se prekid veze, i ovo 'Try again'
// dugme retko kad pomogne ... nekad čak i da zatvorimo celu aplikaciju."*
//
// A WebSocket only ever tells us it CLOSED. It never tells us it is alive, and
// on a phone that changes networks those are two very different silences:
//
//   - CONNECTING forever. `new WebSocket()` to an address with no route sits
//     in CONNECTING until Android's own TCP timeout — up to two minutes — and
//     `ensureConnected` skips a socket that is CONNECTING. So the page that
//     looks like it is "retrying every 2 s" is in fact retrying nothing.
//   - OPEN but never served. The handshake completes and then nothing arrives:
//     no `config`, no stream, no cursor. `ensureConnected` skips an OPEN
//     socket too, so this one never retries either — the pill says "Connected"
//     over a frozen frame for as long as it lasts.
//
// Both are dead ends with no exit, which is exactly why killing the app was
// the only cure: a fresh process re-probes both addresses from scratch. So the
// page now watches its own connection and, when it has failed this way often
// enough, says so to the shell — which owns the addresses and can move us.
const CONNECT_TIMEOUT_MS = 6000;   // CONNECTING longer than this is no route
const SERVED_TIMEOUT_MS = 8000;    // OPEN but no `config` is a server we cannot hear
const LINK_LOST_TRIES = 3;         // failures in a row before the shell re-probes
// Presence (owner 2026-08-05): the server holds layout windows always-on-top
// while we are watching, so it must learn the instant we stop. A locked phone
// often cannot even close the socket (its Wi-Fi sleeps), so PRESENCE IS THE
// SIGNAL — this beat, and its silence when the page is frozen or gone. The
// server's patience is 12 s (three missed beats).
const HEARTBEAT_MS = 4000;
// An excursion — image picker, camera, voice, a permission dialog — hides the
// page while the owner is very much still working with us, so the PC holds the
// layout instead of packing it away underneath a gallery pick.
//
// THIS TIMER IS THE FALLBACK, NOT THE ANSWER (owner failure 2026-08-05, the
// second time his windows stayed on top). It used to be 90 s and it was the
// ONLY signal: tapping Mic armed it, and LOCKING the tablet six seconds later
// was therefore announced to the PC as "back in a moment", which held his
// Chrome and VSCode above everything for five minutes while he sat at his
// desk. Inside the app the reason now comes from the shell, which can read
// the screen and keyguard state and knows whether it launched the picker
// itself (`Android.hideReason()`); this grace only covers a dev browser,
// where nothing can be asked — and it is short enough to be harmless there.
const EXCURSION_GRACE_MS = 12000;
// How long the screen is held awake after the last touch. The shell used to
// set FLAG_KEEP_SCREEN_ON once and never clear it, so the tablet NEVER slept
// by itself: the presence signal the whole design rests on could only ever
// fire if the owner locked it by hand, and the screen burned battery all the
// while (audit 2026-08-05).
const KEEP_AWAKE_MS = 180000;
const LIVE_MAX_BEHIND_S = 0.5;   // jump to the live edge when this far behind
// WHERE A CATCH-UP LANDS (task 122/151). Was 0.1 s — SIX FRAMES at 60 fps,
// and his log of 2026-08-09 showed what that cost: the drift rode 0.47-0.49 s
// for a minute, crossed the threshold, and the very next sample was already
// NEGATIVE. A landing with no headroom turned one late chunk into a starved
// player.
const LIVE_TARGET_BEHIND_S = 0.45;
// Below this, the player's own clock has run PAST the data it has and the
// picture is frozen (task 122's freeze sat at -11 s). Not zero: a hair of
// negative drift is ordinary jitter, and re-seeking on that would stutter
// forever. See client/live-clock.js `liveAction` — the decision this feeds.
const LIVE_STARVED_S = -0.2;
// The starve check also runs on a slow tick (render.js `unfreezeIfStarved`),
// because `updateend` only fires when a chunk ARRIVES — and the whole
// failure is chunks not arriving.
const LIVE_UNFREEZE_TICK_MS = 1000;
// How often the live-drift measurement reaches the server log (task 83). Long
// enough that a session's log stays readable, short enough that one minute of
// him moving the mouse produces several lines to compare across fps settings.
const LIVE_REPORT_S = 15;
const BUFFER_KEEP_S = 8;         // decoded history kept in MSE before trimming
// How long the keyboard's height must stand still before it is worth one line
// in the PC's log (render.js `reportKeyboard`). Android ANIMATES the IME in and
// fires the inset listener on every frame of it, so an un-settled report would
// bury the one number that matters under twenty half-open keyboards — and it
// would print a rise computed against a keyboard that was still moving.
const KB_REPORT_SETTLE_MS = 400;

// The PC cursor sits exactly under the finger (owner decision 2026-08-02,
// reversing the 2026-07-26 offset system after living with it: the pointer
// is where the tap registers, no diagonal offset, no reserved edge margins —
// the image touches all four screen edges).

// --- State ----------------------------------------------------------------
const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");

const token = new URLSearchParams(location.search).get("token");

let monitor = { w: 0, h: 0 };
// EVERY monitor the PC can stream, and which one it is streaming now (owner
// 2026-08-09, task 155): the layout list's single "Desktop" row became one row
// PER MONITOR, each naming its resolution. Both arrive on the EXISTING `config`
// frame as OPTIONAL fields, so a server too old to send them leaves this list
// empty and the list draws the one Desktop row it always did — nothing on the
// wire had to become required for a feature the phone can live without.
let monitorList = [];      // [{index, width, height, primary}]
let monitorIndex = 0;      // which of them the stream is showing
// The monitor-normalized rect the H.264 stream COVERS (owner order
// 2026-08-12: the per-client encoder crops to the focused layout, so the
// phone never decodes pixels it does not show). From `config.stream_region`;
// null = the stream is the full monitor, exactly the old world. render.js
// maps the video onto this rect; quality.js sizes the decode ceiling by it.
let streamRegion = null;
let baseRect = { x: 0, y: 0, w: 1, h: 1 };
let view = { scale: 1, tx: 0, ty: 0 };

let baseBitmap = null;
let detailBitmap = null;
let detailRegion = { x: 0, y: 0, w: 1, h: 1 };
let ws = null;

// Stream mode comes from the server's `config`: "h264" (fMP4 via MSE, drawn
// from the offscreen <video>) or "jpeg" (bitmaps, region streaming).
let streamMode = "jpeg";
let cursorPos = null; // PC cursor, monitor-normalized — capture never includes it

// One finger's meaning is set by a single toggle mode. Only one is ever active.
//   move (default — the finger only steers the PC cursor, never clicks)
//   · drag · scroll · pan
// NOTHING on the canvas is a tap (owner decision 2026-07-26): the flow is
// always steer-then-press-a-button. Left AND right clicks are explicit
// buttons (`click` at the current cursor; press twice fast = double click).
// pan moves the local view; two fingers always pinch.
let touchMode = "move";

const pointers = new Map();
let pinch = null;
let primary = null; // the first finger: {id, type, startX, startY, offset, ...}

// --- Layouts (Phase F+ step 1) --------------------------------------------
// The SERVER owns the layout list (it survives phone disconnects); the client
// mirrors it via `layout_state`. While a layout is focused the view is BOUND
// to its monitor-normalized region: the region fitted to the screen is the
// maximum zoom-out, two fingers pinch in and pan exactly as on the desktop
// (owner 2026-08-04 — no reason for zoom to be missing here), and both the
// view and the PC cursor stay inside the region — the phone sees and drives
// ONLY that window.
let layouts = [];
let layoutActive = null; // index into layouts, null = full desktop
let layoutRegion = null; // {x,y,w,h} monitor-normalized, null on desktop
let layoutArm = false;   // one-shot: the next canvas tap picks a window
// The layout to RE-FOCUS after a reconnect that reset to desktop (owner
// 2026-08-04: any excursion — gallery pick, a permission dialog — hides the
// page, the socket closes by rule, and the fresh connection's server-side
// focus starts at desktop; the app must come back into the layout it was
// in). Armed by every layout_state that carries a focus; cleared by a
// DELIBERATE focus change/removal the user sends (see send() below).
let layoutRestore = null; // {index, name} or null
// TASK 204: true from the moment a layoutRestore attempt is SENT until its
// own reply lands (success or failed verify) — see applyOrientationLock in
// layouts.js. The server's interim "desktop" layout_state during that
// window is not a real desktop choice; unlocking rotation on it let the
// tablet spin sideways with blue letterbox bars for the seconds the restore
// takes (owner report, task 204). Distinct from layoutRestore itself, which
// is cleared BEFORE the restore's layout_focus is even sent.
let orientationRestoring = false;
// Font-zoom staircase steps already applied per layout index (owner
// 2026-08-05 — gestures.js sends Ctrl+-/= past the fitted view). Kept here
// with the rest of the layout state; removal shifts the indices in send().
const fontZoomByLayout = new Map();

function viewLocked() {
  return layoutRegion !== null;
}

// WHERE THE PICTURE SITS ALONG THE FREE AXIS (owner decree 2026-08-09, the
// Move handle's fourth round): the focused layout's `pos` — 0 = top/left,
// 0.5 = centred, 1 = bottom/right — anchors the letterboxed picture on THIS
// screen. The server stores and echoes it in `layout_state` but no longer
// moves any PC window by it: moving windows inside the monitor never changed
// the cropped picture he sees. Centre when no layout is focused or an old
// server sent no pos.
function layoutAnchorPos() {
  const lay = layoutActive !== null ? layouts[layoutActive] : null;
  return lay && typeof lay.pos === "number" ? lay.pos : 0.5;
}

// Region-streaming state — declared before the first updateViewport() call.
let lastSentViewport = { x: 0, y: 0, w: 1, h: 1 };
let viewportTimer = null;
// The H.264 zoom-crop settle (T76): the last rect really sent, the last
// sample taken, when that sample last CHANGED, and the sampler itself.
let lastSentZoom = null;
let zoomSample = null;
let zoomChangedAt = 0;
let zoomSettleTimer = null;

function setStatus(cls, text) {
  statusEl.className = cls;
  statusEl.textContent = text;
}

window.addEventListener("error", (e) => setStatus("disconnected", `Page error: ${e.message}`));
window.addEventListener("unhandledrejection", (e) =>
  setStatus("disconnected", `Page error: ${e.reason}`));

// HOW FAR THE PICTURE HAS BEEN RAISED, in CSS px, and the one place every
// finger passes through on its way to a PC coordinate.
//
// THE RULE, in the shape he settled it (owner decree 2026-08-07): the canvas
// keeps its FULL height when the soft keyboard opens — the picture is never
// SQUEEZED — and it is NEVER lifted by the KEYBOARD's height. That second half
// is his own 2026-08-03 request withdrawn after living with it: the row he is
// typing into is almost never at the very bottom of the PC screen, so a
// keyboard-sized lift carried the text he was watching off the top.
//
// It IS lifted by the caret's SHORTFALL — the few pixels, if any, by which the
// row he is typing in would otherwise sit under the keys. That is the rule in
// client/caret.js, it is answered with 0 most of the time, and `kbShift` is
// where its answer lands in CSS px (`caretRise / devicePixelRatio`).
//
// So this is NOT 0 and no longer "stays 0" — it said so here until 2026-08-09,
// months after `caretRise` started feeding it, and a comment that flatly
// contradicts the line under it is how the next round loses an hour.
// `toCanvasPx` must keep adding it: a finger that touches a risen picture has
// to land on the PC pixel under it, not on the one that used to be there.
let kbShift = 0;

// WHERE THE PC SAYS THE TYPING CARET IS, and how far the picture rose for it
// (owner 2026-08-07; server half server/caret.py, the rule client/caret.js).
// `pcCaret` is the last `caret` frame — `null` while the PC cannot see one,
// which is a real answer and not a zero: some apps expose nothing, and the
// page must be able to tell "the row is here" from "I could not find the row".
//
// `caretRise` is what caret.js decided, in CANVAS pixels, and it is almost
// always 0. It moves the PICTURE only: render.js subtracts it from the drawn
// rect, so the canvas and the colour behind it do not move and the navy
// letterbox stays where it is — his screenshot of the 2026-08-03 attempt was
// exactly that filler travelling with the image.
//
// It rides `kbShift` for the INVERSE mapping because that is what kbShift was
// left in place for: the one point every gesture passes through. A finger that
// touches a risen picture must still land on the PC pixel under it.
//
// WHEN THE PC CANNOT SEE THE CARET, NOTHING MOVES. There was a
// `caretUnknownMode` here — his idea of 2026-08-07, a Settings switch letting
// a window he knows sits at the bottom take the old whole-keyboard lift. It
// was declared, never assigned, and `config.ui` never grew the field, so the
// branch it fed in caret.js could not run: a documented switch that did
// nothing. Both went on 2026-08-09 (owner decree 2026-08-07 — legacy things
// are removed, not kept). It comes back the day the desktop Settings window
// grows the control, and not before.
let claudeSaved = {};
// What the SHELL measured the keyboard to be, in CSS px (0 = closed, or a
// dev browser that never told us). The page cannot measure this for itself
// under edge-to-edge — see render.js `updateViewport` and `window.__imeHeight`.
let imeHeight = 0;
let pcCaret = null;
let caretRise = 0;

function toCanvasPx(e) {
  return {
    x: e.clientX * devicePixelRatio,
    y: (e.clientY + kbShift) * devicePixelRatio,
  };
}

// Set by everything that deliberately leaves the app for a moment (image
// picker, camera, voice, a permission dialog): the hide that follows is an
// EXCURSION, not the end of work — the PC keeps the layout standing.
let excursionUntil = 0;

function markExcursion() {
  excursionUntil = performance.now() + EXCURSION_GRACE_MS;
}

function inExcursion() {
  return performance.now() < excursionUntil;
}

// WHY the page is being hidden, in the words of whoever actually knows.
// Inside the app that is the shell: it reads the screen and keyguard state,
// and it knows whether IT put a picker / camera / voice / permission dialog in
// front of us. The page's own timer is only consulted when nobody can be
// asked — a dev browser, or an older shell without the bridge.
//
// The vocabulary is small and the server treats everything it does not
// recognise as a LEAVE, because the safe default is the owner's own desk:
//   "lock"      — screen off or device locked. ALWAYS the end of the session.
//   "excursion" — we are still working; the PC holds the layout.
//   ""          — app switched away, closed: the end of the session.
function hideReason() {
  if (IN_APP && window.Android.hideReason) {
    try {
      const reason = window.Android.hideReason();
      if (reason) return reason;
      // The shell answered "not a lock, not my picker" — believe it over any
      // timer of ours. An empty answer IS an answer.
      return "";
    } catch (e) {
      // fall through to the page's own guess
    }
  }
  return inExcursion() ? "excursion" : "";
}

// What the phone itself has spent (Android TrafficStats — our app's UID and
// the whole device, both cumulative since the phone booted). The PC's Traffic
// window turns two of these readings into the only honest answer to "does it
// keep running while the screen is off" (owner 2026-08-05). Null outside the
// app, where there is nothing to ask.
function phoneNet() {
  if (!IN_APP || !window.Android.netStats) return null;
  try {
    const raw = JSON.parse(window.Android.netStats() || "null");
    return raw && typeof raw.app_rx === "number" ? raw : null;
  } catch (e) {
    return null;
  }
}

// What this phone's own battery says (T80d, owner 2026-08-14). The owner's
// requirement is that EVERY device answers for its own hardware, not just his
// — so the phone measures itself through `Android.batteryStats()` and the PC
// only reports what it was told. A simulated number was refused and must not
// come back: an emulator has no battery and reports a fixed fake value.
//
// Feature-detected on the method itself: the page is served by the PC while
// the shell is installed separately, so an older APK simply has no such
// method and this returns null — which travels as an ABSENT field, never as a
// zero. Same rule inside the reading: the shell leaves out a property its
// device will not answer, and this must not fill it in.
function phoneBattery() {
  if (!IN_APP || typeof window.Android.batteryStats !== "function") return null;
  try {
    const raw = JSON.parse(window.Android.batteryStats() || "null");
    if (!raw || typeof raw !== "object") return null;
    const out = {};
    if (typeof raw.level === "number") out.level = raw.level;
    if (typeof raw.current_ua === "number") out.current_ua = raw.current_ua;
    if (typeof raw.charging === "boolean") out.charging = raw.charging;
    // An empty object is a device that answered nothing — that is a "will not
    // say" and it must reach the PC as no field at all, so the desktop says so
    // in words instead of drawing a blank.
    return Object.keys(out).length ? out : null;
  } catch (e) {
    return null;
  }
}

// The bounded outbound queue for typing messages while the socket is down
// (client/type-queue.js — pure, gated whole; see its header for the count
// and staleness reasoning). `typeQueueLossNotified` dedupes the toast to ONE
// per outage — a rapid burst can drop several messages in a row and a toast
// per message would bury the one thing worth telling him under a stack of
// identical ones; it resets the moment the outage truly ends (a successful
// flush) so the NEXT outage can notify again.
let typeQueue = [];
let typeQueueLossNotified = false;

function noteTypeQueueLoss() {
  if (typeQueueLossNotified) return;
  typeQueueLossNotified = true;
  showToast("Some typing wasn't sent — the connection was down too long");
  // The invisible field's own model of the PC text (kb-sync.js's `kbPrev`,
  // controls.js) is now WRONG by an unknown amount — some of what it assumed
  // landed did not. There is no way to learn the PC's real text from here
  // (the field is a diff source, never a mirror read back), so the honest
  // move is the same one blur() already performs after every send: stop
  // assuming, and let the next edit start a fresh diff from whatever the
  // owner sees on the PC screen he is already watching.
  if (typeof kbInput !== "undefined" && document.activeElement === kbInput) {
    kbInput.blur();
  }
}

/** Called once the socket is OPEN again (connection.js `sock.onopen`) — sends
 *  everything the outage queued, in order, or gives up on the whole queue at
 *  once and says so. Must run AFTER `auth` is sent: nothing may reach the
 *  server before it (hard security rule), and `send()` below routes straight
 *  to `ws.send` once `ws.readyState` is OPEN, so calling this too early would
 *  jump the queue's own messages ahead of `auth`. */
function flushTypeQueue() {
  if (typeQueue.length === 0) return;
  const { messages, dropped } = typeQueueFlush(typeQueue, performance.now());
  typeQueue = [];
  if (dropped) {
    noteTypeQueueLoss();
    return;
  }
  typeQueueLossNotified = false; // the outage is over — the next one may notify again
  messages.forEach((m) => send(m));
}

function send(msg) {
  // A DELIBERATE focus change or removal voids the auto-refocus — only a
  // reconnect may restore a layout, never a user's explicit choice of the
  // desktop. (A focus of a real index re-arms via its layout_state reply.)
  if (msg.type === "layout_focus" || msg.type === "layout_remove") layoutRestore = null;
  if (msg.type === "layout_remove") {
    // The font-zoom steps ride on layout INDICES — removing one shifts every
    // higher index down by one.
    fontZoomByLayout.delete(msg.index);
    [...fontZoomByLayout.keys()].sort((a, b) => a - b).forEach((k) => {
      if (k > msg.index) {
        fontZoomByLayout.set(k - 1, fontZoomByLayout.get(k));
        fontZoomByLayout.delete(k);
      }
    });
  }
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
    return;
  }
  // The 4401 pill carries the ONLY re-pair instruction ("tap here to scan
  // the new QR") — never stomp it with a reconnect notice that can't succeed.
  // 4409 (another device took over) likewise: only a deliberate tap on the
  // pill reconnects, or two devices would steal the session in a loop.
  if (authRejected || takenOver) return;
  // A TYPING message survives a short outage (2026-08-13 MEASURED defect,
  // see client/type-queue.js) — every other kind keeps the old behaviour
  // below it: dropped, with only the status pill to show for it.
  if (typeQueueKind(msg)) {
    const result = typeQueuePush(typeQueue, msg, performance.now());
    typeQueue = result.queue;
    if (result.dropped) noteTypeQueueLoss();
  }
  // A dropped command must be VISIBLE (a dead socket behind a frozen frame
  // read as "buttons randomly stopped working" — owner report 2026-07-26).
  setStatus("connecting", "Reconnecting…");
  ensureConnected();
}
