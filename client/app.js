// Remote User client — stream rendering, pinch zoom + region streaming,
// modifier-button input (tap = left click; hold RIGHT/DRAG/SCROLL + finger).

"use strict";

// --- Tunables -------------------------------------------------------------
const ZOOM_MAX = 6;
const TAP_MAX_MOVE = 12;        // CSS px of finger travel before a tap stops being a tap
const SCROLL_PX_PER_TICK = 40;  // CSS px of finger travel per wheel tick
const VIEWPORT_MARGIN = 0.15;   // extra region requested around the visible area
const VIEWPORT_THROTTLE_MS = 150;
const RECONNECT_MS = 2000;

// --- State ----------------------------------------------------------------
const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");

const token = new URLSearchParams(location.search).get("token");

let monitor = { w: 0, h: 0 };                // real monitor size (server `config` message)
let baseRect = { x: 0, y: 0, w: 1, h: 1 };   // where the full monitor sits at zoom 1
let view = { scale: 1, tx: 0, ty: 0 };       // zoom/pan on top of baseRect
let lastBitmap = null;
let lastRegion = { x: 0, y: 0, w: 1, h: 1 }; // monitor region the last frame covers
let ws = null;

// Gesture state
const pointers = new Map(); // pointerId -> {x, y} in canvas px (tap/pinch flow only)
let tap = null;             // {startX, startY, moved}
let pinch = null;           // {startDist, startScale, qx, qy}
let gestureHadPinch = false;
let dragState = null;       // {id, pos} while the DRAG modifier drives a mouse drag
let scrollState = null;     // {id, lastY, acc, pos} while the SCROLL modifier is held
const modifiers = { right: false, drag: false, scroll: false };

function setStatus(cls, text) {
  statusEl.className = cls;
  statusEl.textContent = text;
}

// The user must never stare at a silent "Connecting…" — any failure surfaces
// its actual reason on the status pill.
window.addEventListener("error", (e) => setStatus("disconnected", `Page error: ${e.message}`));
window.addEventListener("unhandledrejection", (e) =>
  setStatus("disconnected", `Page error: ${e.reason}`));

function toCanvasPx(e) {
  return { x: e.clientX * devicePixelRatio, y: e.clientY * devicePixelRatio };
}

// --- View transform -------------------------------------------------------

function computeBaseRect() {
  if (!monitor.w) return;
  const aspect = monitor.w / monitor.h;
  const w = Math.min(canvas.width, canvas.height * aspect);
  const h = w / aspect;
  baseRect = { x: (canvas.width - w) / 2, y: (canvas.height - h) / 2, w, h };
}

function drawnRect() {
  return {
    x: baseRect.x * view.scale + view.tx,
    y: baseRect.y * view.scale + view.ty,
    w: baseRect.w * view.scale,
    h: baseRect.h * view.scale,
  };
}

function clampView() {
  if (view.scale <= 1) {
    view = { scale: 1, tx: 0, ty: 0 };
    return;
  }
  view.scale = Math.min(view.scale, ZOOM_MAX);
  // The zoomed frame must always cover its zoom-1 area — no drifting off-screen.
  const s = view.scale;
  view.tx = Math.min(Math.max(view.tx, (baseRect.x + baseRect.w) * (1 - s)), baseRect.x * (1 - s));
  view.ty = Math.min(Math.max(view.ty, (baseRect.y + baseRect.h) * (1 - s)), baseRect.y * (1 - s));
}

function redraw() {
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (!lastBitmap) return;
  const D = drawnRect();
  ctx.drawImage(
    lastBitmap,
    D.x + lastRegion.x * D.w,
    D.y + lastRegion.y * D.h,
    lastRegion.w * D.w,
    lastRegion.h * D.h
  );
}

function resizeCanvas() {
  canvas.width = window.innerWidth * devicePixelRatio;
  canvas.height = window.innerHeight * devicePixelRatio;
  computeBaseRect();
  clampView();
  redraw();
  scheduleViewport();
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

// --- Region streaming (sharp zoom) ---------------------------------------
// When zoomed, tell the server which monitor region is visible — it then
// streams only that region, so zoom gets native pixels at constant bandwidth.

let lastSentViewport = { x: 0, y: 0, w: 1, h: 1 };
let viewportTimer = null;

function currentViewport() {
  if (view.scale <= 1) return { x: 0, y: 0, w: 1, h: 1 };
  const D = drawnRect();
  let x1 = Math.max(0, -D.x / D.w);
  let y1 = Math.max(0, -D.y / D.h);
  let x2 = Math.min(1, (canvas.width - D.x) / D.w);
  let y2 = Math.min(1, (canvas.height - D.y) / D.h);
  const mx = (x2 - x1) * VIEWPORT_MARGIN;
  const my = (y2 - y1) * VIEWPORT_MARGIN;
  x1 = Math.max(0, x1 - mx);
  y1 = Math.max(0, y1 - my);
  x2 = Math.min(1, x2 + mx);
  y2 = Math.min(1, y2 + my);
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

function scheduleViewport() {
  if (viewportTimer) return;
  viewportTimer = setTimeout(() => {
    viewportTimer = null;
    const vp = currentViewport();
    const d = Math.max(
      Math.abs(vp.x - lastSentViewport.x), Math.abs(vp.y - lastSentViewport.y),
      Math.abs(vp.w - lastSentViewport.w), Math.abs(vp.h - lastSentViewport.h)
    );
    if (d > 0.01) {
      lastSentViewport = vp;
      send({ type: "viewport", ...vp });
    }
  }, VIEWPORT_THROTTLE_MS);
}

async function onFrame(buffer) {
  const region = new Float32Array(buffer, 0, 4);
  const bitmap = await createImageBitmap(new Blob([new Uint8Array(buffer, 16)]));
  if (lastBitmap) lastBitmap.close();
  lastBitmap = bitmap;
  lastRegion = { x: region[0], y: region[1], w: region[2], h: region[3] };
  redraw();
}

// --- Coordinate mapping ---------------------------------------------------

// Canvas point -> 0-1 within the remote monitor, null on the letterbox padding.
function toRemote(px, py) {
  const D = drawnRect();
  const x = (px - D.x) / D.w;
  const y = (py - D.y) / D.h;
  if (x < 0 || x > 1 || y < 0 || y > 1) return null;
  return { x, y };
}

// Same, but clamped — drags may travel over the padding without breaking.
function toRemoteClamped(px, py) {
  const D = drawnRect();
  return {
    x: Math.min(Math.max((px - D.x) / D.w, 0), 1),
    y: Math.min(Math.max((py - D.y) / D.h, 0), 1),
  };
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

// --- Modifier buttons -----------------------------------------------------

for (const name of ["right", "drag", "scroll"]) {
  const el = document.getElementById(`btn-${name}`);
  el.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    el.setPointerCapture(e.pointerId);
    modifiers[name] = true;
    el.classList.add("active");
  });
  const release = () => {
    modifiers[name] = false;
    el.classList.remove("active");
    if (name === "drag") finishDrag(); // releasing the button mid-drag ends the drag
  };
  el.addEventListener("pointerup", release);
  el.addEventListener("pointercancel", release);
}

function finishDrag() {
  if (!dragState) return;
  send({ type: "pointer_up", x: dragState.pos.x, y: dragState.pos.y, button: "left" });
  dragState = null;
}

// --- Keyboard -------------------------------------------------------------
// Toggle button focuses a hidden input, which summons the tablet's native
// keyboard. Printable characters are captured by DIFFING the field value
// (IME/autocorrect-proof — never trust keydown.key for printables, project
// CLAUDE.md rule); structural keys are captured via keydown.

const kbInput = document.getElementById("kb");
const kbBtn = document.getElementById("btn-kb");
let kbPrev = "";

const SPECIAL_KEYS = {
  Enter: "enter", Backspace: "backspace", Tab: "tab", Escape: "escape",
  Delete: "delete", Home: "home", End: "end",
  ArrowLeft: "left", ArrowUp: "up", ArrowRight: "right", ArrowDown: "down",
};

kbBtn.addEventListener("pointerdown", (e) => e.preventDefault()); // focus is handled manually
kbBtn.addEventListener("pointerup", (e) => {
  e.preventDefault();
  if (document.activeElement === kbInput) kbInput.blur();
  else kbInput.focus({ preventScroll: true });
});

kbInput.addEventListener("focus", () => kbBtn.classList.add("active"));
kbInput.addEventListener("blur", () => kbBtn.classList.remove("active"));

kbInput.addEventListener("keydown", (e) => {
  const special = SPECIAL_KEYS[e.key];
  if (!special) return; // printable characters flow through the input event
  e.preventDefault();   // keep the field unchanged — no double handling via the diff
  send({ type: "key_special", key: special });
});

kbInput.addEventListener("input", (e) => {
  const value = kbInput.value;
  // Diff previous vs current value: common prefix + suffix, the middle changed.
  const minLen = Math.min(kbPrev.length, value.length);
  let p = 0;
  while (p < minLen && kbPrev[p] === value[p]) p++;
  let s = 0;
  while (s < minLen - p && kbPrev[kbPrev.length - 1 - s] === value[value.length - 1 - s]) s++;
  const removed = kbPrev.length - p - s;
  const inserted = value.slice(p, value.length - s);
  for (let i = 0; i < removed; i++) send({ type: "key_special", key: "backspace" });
  if (inserted) send({ type: "key_text", text: inserted });
  kbPrev = value;
  // Trim the buffer once it grows, outside IME composition (programmatic reset is silent).
  if (!e.isComposing && value.length > 200) {
    kbInput.value = "";
    kbPrev = "";
  }
});

// --- Canvas gestures ------------------------------------------------------
// tap (no travel)            -> left click on release
// RIGHT held + tap           -> right click on release
// DRAG held + finger         -> mouse down / move / up (real drag)
// SCROLL held + finger       -> wheel ticks (content follows the finger)
// two fingers on the canvas  -> pinch zoom + pan (never sends clicks)

function firstTwoPointers() {
  const it = pointers.values();
  return [it.next().value, it.next().value];
}

canvas.addEventListener("pointerdown", (e) => {
  // While the keyboard is open, tapping the screen must NOT steal focus from
  // the hidden input — you click a field on the PC and keep typing.
  if (document.activeElement === kbInput) e.preventDefault();
  canvas.setPointerCapture(e.pointerId);
  const p = toCanvasPx(e);

  if (modifiers.drag && !dragState) {
    dragState = { id: e.pointerId, pos: toRemoteClamped(p.x, p.y) };
    send({ type: "pointer_down", x: dragState.pos.x, y: dragState.pos.y, button: "left" });
    return;
  }
  if (modifiers.scroll && !scrollState) {
    scrollState = { id: e.pointerId, lastY: p.y, acc: 0, pos: toRemoteClamped(p.x, p.y) };
    return;
  }

  pointers.set(e.pointerId, p);
  if (pointers.size === 1) {
    tap = { startX: p.x, startY: p.y, moved: false };
    gestureHadPinch = false;
  } else if (pointers.size === 2) {
    tap = null;
    gestureHadPinch = true;
    const [p1, p2] = firstTwoPointers();
    const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
    const D = drawnRect();
    pinch = {
      startDist: Math.hypot(p1.x - p2.x, p1.y - p2.y),
      startScale: view.scale,
      qx: (mid.x - D.x) / D.w, // frame point under the midpoint stays anchored
      qy: (mid.y - D.y) / D.h,
    };
  }
});

canvas.addEventListener("pointermove", (e) => {
  const p = toCanvasPx(e);

  if (dragState && dragState.id === e.pointerId) {
    dragState.pos = toRemoteClamped(p.x, p.y);
    send({ type: "pointer_move", x: dragState.pos.x, y: dragState.pos.y });
    return;
  }
  if (scrollState && scrollState.id === e.pointerId) {
    scrollState.acc += p.y - scrollState.lastY;
    scrollState.lastY = p.y;
    const tickPx = SCROLL_PX_PER_TICK * devicePixelRatio;
    const ticks = Math.trunc(scrollState.acc / tickPx);
    if (ticks) {
      scrollState.acc -= ticks * tickPx;
      send({ type: "scroll", x: scrollState.pos.x, y: scrollState.pos.y, ticks });
    }
    return;
  }
  if (!pointers.has(e.pointerId)) return;
  pointers.set(e.pointerId, p);

  if (pinch && pointers.size >= 2) {
    const [p1, p2] = firstTwoPointers();
    const dist = Math.hypot(p1.x - p2.x, p1.y - p2.y);
    const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
    const s = Math.min(Math.max(pinch.startScale * (dist / pinch.startDist), 1), ZOOM_MAX);
    view.scale = s;
    view.tx = mid.x - (baseRect.x + pinch.qx * baseRect.w) * s;
    view.ty = mid.y - (baseRect.y + pinch.qy * baseRect.h) * s;
    clampView();
    redraw();
    scheduleViewport();
  } else if (tap && pointers.size === 1) {
    const travel = Math.hypot(p.x - tap.startX, p.y - tap.startY);
    if (travel > TAP_MAX_MOVE * devicePixelRatio) tap.moved = true;
  }
});

function endPointer(e) {
  if (dragState && dragState.id === e.pointerId) {
    finishDrag();
    return;
  }
  if (scrollState && scrollState.id === e.pointerId) {
    scrollState = null;
    return;
  }

  pointers.delete(e.pointerId);
  if (pinch && pointers.size < 2) pinch = null;
  if (pointers.size > 0) return;

  if (tap && !tap.moved && !gestureHadPinch && e.type === "pointerup") {
    const p = toCanvasPx(e);
    const pos = toRemote(p.x, p.y);
    if (pos) {
      const button = modifiers.right ? "right" : "left";
      send({ type: "pointer_down", x: pos.x, y: pos.y, button });
      send({ type: "pointer_up", x: pos.x, y: pos.y, button });
    }
  }
  tap = null;
  gestureHadPinch = false;
  scheduleViewport();
}

canvas.addEventListener("pointerup", endPointer);
canvas.addEventListener("pointercancel", endPointer);
window.addEventListener("contextmenu", (e) => e.preventDefault());

// --- Connection -----------------------------------------------------------
// Security decision (owner): the session lives only while the owner is looking
// at this page. Backgrounding the tab or locking the tablet closes the socket;
// returning to the page reconnects automatically.

function connect() {
  setStatus("connecting", `Connecting to ${location.host}…`);
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "auth", token }));
    lastSentViewport = { x: 0, y: 0, w: 1, h: 1 };
    scheduleViewport(); // restore the zoomed region after a reconnect
    setStatus("connected", "Connected");
  };

  ws.onmessage = (e) => {
    if (typeof e.data === "string") {
      const msg = JSON.parse(e.data);
      if (msg.type === "config") {
        monitor = { w: msg.monitor_width, h: msg.monitor_height };
        computeBaseRect();
        clampView();
        redraw();
      }
    } else {
      onFrame(e.data);
    }
  };

  ws.onclose = (e) => {
    if (e.code === 4401) {
      setStatus("disconnected", "Invalid token — scan the fresh QR on the PC");
      return; // retrying with a dead token is pointless
    }
    setStatus(
      "disconnected",
      document.hidden ? "Paused — screen away" : `Disconnected (code ${e.code}) — retrying…`
    );
  };
}

// Pause while the page is hidden (owner security decision); the watchdog
// below reconnects when it is visible again.
document.addEventListener("visibilitychange", () => {
  if (document.hidden && ws) ws.close();
});

// Single reconnect authority: whenever the page is visible and the socket is
// not alive, try again. No state machine to get stuck in.
setInterval(() => {
  if (document.hidden) return;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  connect();
}, RECONNECT_MS);

connect();
