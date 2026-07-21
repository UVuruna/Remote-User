// Remote User client — stream rendering, tap = click, pinch zoom + two-finger pan.

"use strict";

const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");

const token = new URLSearchParams(location.search).get("token");

const ZOOM_MAX = 6;
const TAP_MAX_MOVE = 12; // CSS px of finger travel before a tap stops being a tap

// baseRect: where the frame sits at zoom 1 (letterboxed). view: zoom/pan on top of it.
let baseRect = { x: 0, y: 0, w: 1, h: 1 };
let view = { scale: 1, tx: 0, ty: 0 };
let lastBitmap = null;
let ws = null;

// Gesture state
const pointers = new Map(); // pointerId -> {x, y} in canvas px
let tap = null;             // {startX, startY, moved} for the single-finger click
let pinch = null;           // {startDist, startScale, qx, qy} anchor in frame-normalized coords
let gestureHadPinch = false;

function setStatus(cls, text) {
  statusEl.className = cls;
  statusEl.textContent = text;
}

function toCanvasPx(e) {
  return { x: e.clientX * devicePixelRatio, y: e.clientY * devicePixelRatio };
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
  const r = drawnRect();
  ctx.drawImage(lastBitmap, r.x, r.y, r.w, r.h);
}

function computeBaseRect() {
  if (!lastBitmap) return;
  const scale = Math.min(canvas.width / lastBitmap.width, canvas.height / lastBitmap.height);
  const w = lastBitmap.width * scale;
  const h = lastBitmap.height * scale;
  baseRect = { x: (canvas.width - w) / 2, y: (canvas.height - h) / 2, w, h };
}

function resizeCanvas() {
  canvas.width = window.innerWidth * devicePixelRatio;
  canvas.height = window.innerHeight * devicePixelRatio;
  computeBaseRect();
  clampView();
  redraw();
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

async function drawFrame(blob) {
  const bitmap = await createImageBitmap(blob);
  if (lastBitmap) lastBitmap.close();
  lastBitmap = bitmap;
  computeBaseRect();
  redraw();
}

// Maps a canvas-px point to 0-1 coordinates within the remote monitor,
// or null on the letterbox padding.
function toRemote(px, py) {
  const r = drawnRect();
  const x = (px - r.x) / r.w;
  const y = (py - r.y) / r.h;
  if (x < 0 || x > 1 || y < 0 || y > 1) return null;
  return { x, y };
}

function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}

// --- Gestures -------------------------------------------------------------
// One finger, no travel  -> click on release (down + up at that point)
// Two fingers            -> pinch zoom around the midpoint + pan (no clicks sent)

function firstTwoPointers() {
  const it = pointers.values();
  return [it.next().value, it.next().value];
}

canvas.addEventListener("pointerdown", (e) => {
  canvas.setPointerCapture(e.pointerId);
  const p = toCanvasPx(e);
  pointers.set(e.pointerId, p);

  if (pointers.size === 1) {
    tap = { startX: p.x, startY: p.y, moved: false };
    gestureHadPinch = false;
  } else if (pointers.size === 2) {
    tap = null;
    gestureHadPinch = true;
    const [p1, p2] = firstTwoPointers();
    const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
    const r = drawnRect();
    pinch = {
      startDist: Math.hypot(p1.x - p2.x, p1.y - p2.y),
      startScale: view.scale,
      qx: (mid.x - r.x) / r.w, // frame point under the midpoint stays anchored
      qy: (mid.y - r.y) / r.h,
    };
  }
});

canvas.addEventListener("pointermove", (e) => {
  if (!pointers.has(e.pointerId)) return;
  const p = toCanvasPx(e);
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
  } else if (tap && pointers.size === 1) {
    const travel = Math.hypot(p.x - tap.startX, p.y - tap.startY);
    if (travel > TAP_MAX_MOVE * devicePixelRatio) tap.moved = true;
  }
});

function endPointer(e) {
  pointers.delete(e.pointerId);
  if (pinch && pointers.size < 2) pinch = null;
  if (pointers.size > 0) return;

  if (tap && !tap.moved && !gestureHadPinch && e.type === "pointerup") {
    const p = toCanvasPx(e);
    const pos = toRemote(p.x, p.y);
    if (pos) {
      send({ type: "pointer_down", x: pos.x, y: pos.y, button: "left" });
      send({ type: "pointer_up", x: pos.x, y: pos.y, button: "left" });
    }
  }
  tap = null;
  gestureHadPinch = false;
}

canvas.addEventListener("pointerup", endPointer);
canvas.addEventListener("pointercancel", endPointer);

// --- Connection -----------------------------------------------------------

function connect() {
  setStatus("connecting", "Connecting…");
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.binaryType = "blob";

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "auth", token }));
    setStatus("connected", "Connected");
  };

  ws.onmessage = (e) => {
    if (e.data instanceof Blob) drawFrame(e.data);
  };

  ws.onclose = () => {
    setStatus("disconnected", "Disconnected — retrying…");
    setTimeout(connect, 2000);
  };
}

connect();
