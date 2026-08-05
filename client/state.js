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
// Font-zoom staircase steps already applied per layout index (owner
// 2026-08-05 — gestures.js sends Ctrl+-/= past the fitted view). Kept here
// with the rest of the layout state; removal shifts the indices in send().
const fontZoomByLayout = new Map();

function viewLocked() {
  return layoutRegion !== null;
}

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

// The canvas keeps its FULL height when the soft keyboard opens and is simply
// shifted up by `kbShift` CSS px (owner 2026-08-03 — the picture must never be
// squeezed; the bottom stays visible above the keyboard and the top runs off
// screen). Touch coordinates are reported against the visible viewport, so the
// same shift is added back here to land in canvas space.
let kbShift = 0;

function toCanvasPx(e) {
  return {
    x: e.clientX * devicePixelRatio,
    y: (e.clientY + kbShift) * devicePixelRatio,
  };
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
  // A dropped command must be VISIBLE (a dead socket behind a frozen frame
  // read as "buttons randomly stopped working" — owner report 2026-07-26).
  setStatus("connecting", "Reconnecting…");
  ensureConnected();
}
