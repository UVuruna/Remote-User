// Remote User client — H.264 (MSE) or JPEG stream rendering, virtual cursor,
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
const RECONNECT_MS = 2000;
const LIVE_MAX_BEHIND_S = 0.5;   // jump to the live edge when this far behind
const LIVE_TARGET_BEHIND_S = 0.1;
const BUFFER_KEEP_S = 8;         // decoded history kept in MSE before trimming

// Cursor offset — the finger must never sit on top of the pointer it steers.
// The PC cursor is placed at finger + offset in a FIXED direction (owner
// decision 2026-07-26, replacing the radial-angle system: the pointer must
// always be diagonally ABOVE the finger, never under or beside it):
//   right-handed → 315° (up-left of the finger)
//   left-handed  →  45° (up-right of the finger)
// The handedness comes from the desktop app's Settings via `config.hand`.
// The distance is constant per session, calibrated once from the touch
// contact size. The screen keeps a margin on the far side(s) — see
// computeBaseRect — so the finger can travel PAST the image edge and the
// pointer still reaches every corner of the PC screen.
const CURSOR_OFFSET_MARGIN = 20;   // CSS px added beyond the measured finger radius
const CURSOR_OFFSET_MIN = 36;      // CSS px floor
const CURSOR_OFFSET_MAX = 96;      // CSS px ceiling
const CURSOR_OFFSET_FALLBACK = 52; // CSS px until measured / for non-touch (mouse, pen)
const CURSOR_CALIB_SAMPLES = 12;   // touch samples → MAX radius → locked for the session

// --- State ----------------------------------------------------------------
const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");

const token = new URLSearchParams(location.search).get("token");

let monitor = { w: 0, h: 0 };
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
let hand = "right";   // "right" | "left" — from config; decides the offset diagonal

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
// mirrors it via `layout_state`. While a layout is focused the view is LOCKED
// onto its monitor-normalized region: pinch/pan are disabled and the PC
// cursor is clamped inside it — the phone sees and drives ONLY that window.
let layouts = [];
let layoutActive = null; // index into layouts, null = full desktop
let layoutRegion = null; // {x,y,w,h} monitor-normalized, null on desktop
let layoutArm = false;   // one-shot: the next canvas tap picks a window

function viewLocked() {
  return layoutRegion !== null;
}

// Cursor-offset calibration: take the LARGEST touch contact radius over the
// first CURSOR_CALIB_SAMPLES touch samples (max, not median — a light press
// under-reports contact size and would hide the pointer), then lock it for the
// session. Settings → Calibrate re-arms it.
let fingerRadiusPx = null;           // CSS px, null until locked
let fingerMaxPx = 0;                 // running max contact radius while sampling
let fingerSampleCount = 0;           // samples collected
let calibrating = false;             // explicit (Settings) calibration in progress

// Region-streaming state — declared before the first updateViewport() call.
let lastSentViewport = { x: 0, y: 0, w: 1, h: 1 };
let viewportTimer = null;

function setStatus(cls, text) {
  statusEl.className = cls;
  statusEl.textContent = text;
}

window.addEventListener("error", (e) => setStatus("disconnected", `Page error: ${e.message}`));
window.addEventListener("unhandledrejection", (e) =>
  setStatus("disconnected", `Page error: ${e.reason}`));

function toCanvasPx(e) {
  return { x: e.clientX * devicePixelRatio, y: e.clientY * devicePixelRatio };
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(msg));
    return;
  }
  // The 4401 pill carries the ONLY re-pair instruction ("tap here to scan
  // the new QR") — never stomp it with a reconnect notice that can't succeed.
  // 4409 (another device took over) likewise: only a deliberate tap on the
  // pill reconnects, or two devices would steal the session in a loop.
  if (authRejected || takenOver) return;
  // A dropped command must be VISIBLE (a dead socket behind a frozen frame
  // read as "buttons randomly stopped working" — owner report 2026-07-26).
  setStatus("connecting", "Reconnecting…");
  ensureConnected();
}
