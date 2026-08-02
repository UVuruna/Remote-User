// Canvas rendering, view transform, and dual-mode (H.264 MSE / JPEG) frame
// decode. Part of the app.js split — loads after state.js. See
// client/__about/render.md.
"use strict";

// --- View transform -------------------------------------------------------

// The image is fitted into the canvas MINUS a margin on the sides the offset
// points away from (right-handed: right + bottom; left-handed: left + bottom).
// The margin equals one offset component, so the finger can travel past the
// image edge and the pointer still reaches the far corners of the PC screen —
// without it the offset makes those edges physically unreachable.
function computeBaseRect() {
  if (!monitor.w) return;
  const m = offsetDistancePx() * devicePixelRatio * Math.SQRT1_2;
  const left = hand === "left" ? m : 0;
  const boxW = canvas.width - m;  // one horizontal margin, on the offset's far side
  const boxH = canvas.height - m;
  const aspect = monitor.w / monitor.h;
  const w = Math.min(boxW, boxH * aspect);
  const h = w / aspect;
  baseRect = { x: left + (boxW - w) / 2, y: (boxH - h) / 2, w, h };
}

function drawnRect() {
  return {
    x: baseRect.x * view.scale + view.tx,
    y: baseRect.y * view.scale + view.ty,
    w: baseRect.w * view.scale,
    h: baseRect.h * view.scale,
  };
}

// Layout focus: zoom/translate the view so the layout's region fills the
// canvas (minus the same cursor-offset margin computeBaseRect reserves, so
// the offset pointer can still reach the region's far edges). While locked
// this transform is authoritative — clampView backs off, gestures are off.
function applyLayoutView() {
  if (!viewLocked() || !monitor.w) return;
  const m = offsetDistancePx() * devicePixelRatio * Math.SQRT1_2;
  const left = hand === "left" ? m : 0;
  const boxW = canvas.width - m;
  const boxH = canvas.height - m;
  const r = layoutRegion;
  const rw = r.w * baseRect.w;
  const rh = r.h * baseRect.h;
  const s = Math.min(boxW / rw, boxH / rh);
  view.scale = s;
  view.tx = left + (boxW - rw * s) / 2 - (baseRect.x + r.x * baseRect.w) * s;
  view.ty = (boxH - rh * s) / 2 - (baseRect.y + r.y * baseRect.h) * s;
  redraw();
}

function clampView() {
  if (viewLocked()) return; // the layout transform owns the view
  if (view.scale <= 1) {
    view = { scale: 1, tx: 0, ty: 0 };
    return;
  }
  view.scale = Math.min(view.scale, ZOOM_MAX);
  const s = view.scale;
  view.tx = Math.min(Math.max(view.tx, (baseRect.x + baseRect.w) * (1 - s)), baseRect.x * (1 - s));
  view.ty = Math.min(Math.max(view.ty, (baseRect.y + baseRect.h) * (1 - s)), baseRect.y * (1 - s));
}

function redraw() {
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const D = drawnRect();
  if (streamMode === "h264") {
    if (video.readyState >= 2) ctx.drawImage(video, D.x, D.y, D.w, D.h);
  } else {
    if (baseBitmap) ctx.drawImage(baseBitmap, D.x, D.y, D.w, D.h);
    if (view.scale > 1 && detailBitmap) {
      ctx.drawImage(
        detailBitmap,
        D.x + detailRegion.x * D.w,
        D.y + detailRegion.y * D.h,
        detailRegion.w * D.w,
        detailRegion.h * D.h
      );
    }
  }
  drawCursor(D);
}

// The PC pointer, drawn client-side (screen capture never contains it).
// Classic arrow outline; screen-fixed size, independent of zoom.
const CURSOR_PATH = [
  [0, 0], [0, 16.5], [3.6, 13.3], [6, 19], [8.7, 17.9], [6.3, 12.4], [11.2, 11.9],
];

function drawCursor(D) {
  if (!cursorPos) return;
  if (cursorPos.x < 0 || cursorPos.x > 1 || cursorPos.y < 0 || cursorPos.y > 1) return;
  ctx.save();
  ctx.translate(D.x + cursorPos.x * D.w, D.y + cursorPos.y * D.h);
  ctx.scale(devicePixelRatio, devicePixelRatio);
  ctx.beginPath();
  CURSOR_PATH.forEach(([px, py], i) => (i ? ctx.lineTo(px, py) : ctx.moveTo(px, py)));
  ctx.closePath();
  ctx.shadowColor = "rgba(0, 0, 0, 0.55)";
  ctx.shadowBlur = 3;
  ctx.fillStyle = "#fff";
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.strokeStyle = "#000";
  ctx.lineWidth = 1.25;
  ctx.stroke();
  ctx.restore();
}

function updateViewport() {
  const vv = window.visualViewport;
  const w = vv ? vv.width : window.innerWidth;
  const h = vv ? vv.height : window.innerHeight;
  const kb = vv ? Math.max(0, window.innerHeight - vv.height - vv.offsetTop) : 0;
  // NOTE: do NOT blur the keyboard field on a keyboard-height drop. Switching
  // to the IME's voice/mic input transiently shrinks the keyboard, and a blur
  // there tore down the field mid-dictation (had to re-tap Keys to get back —
  // owner report 2026-07-22). Focus is only released by the Keys toggle now.
  const root = document.documentElement.style;
  root.setProperty("--kb", `${kb}px`);
  root.setProperty("--vtop", `${vv ? vv.offsetTop : 0}px`);
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  canvas.width = Math.round(w * devicePixelRatio);
  canvas.height = Math.round(h * devicePixelRatio);
  computeBaseRect();
  clampView();
  applyLayoutView(); // rotation / keyboard resize must re-fit the locked region
  redraw();
  scheduleViewport();
}
window.addEventListener("resize", updateViewport);
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", updateViewport);
  window.visualViewport.addEventListener("scroll", updateViewport);
}
updateViewport();

// --- Region streaming -----------------------------------------------------

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
  if (streamMode !== "jpeg") return; // region streaming is a JPEG-path concept
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
  const r = new Float32Array(buffer, 0, 4);
  const bitmap = await createImageBitmap(new Blob([new Uint8Array(buffer, 16)]));
  const isFull = r[0] <= 0.001 && r[1] <= 0.001 && r[2] >= 0.999 && r[3] >= 0.999;
  if (isFull) {
    if (baseBitmap) baseBitmap.close();
    baseBitmap = bitmap;
  } else {
    if (detailBitmap) detailBitmap.close();
    detailBitmap = bitmap;
    detailRegion = { x: r[0], y: r[1], w: r[2], h: r[3] };
  }
  redraw();
}

// --- H.264 decode (MSE) ---------------------------------------------------
// The server sends one continuous fragmented-MP4 byte stream; chunks are
// appended in arrival order. currentTime chases the buffered end to stay
// live, and played-out history is trimmed so memory stays flat.

const video = document.getElementById("vid");
let mediaSource = null;
let sourceBuffer = null;
let mseQueue = [];
let rafId = null;

function initMse(codec) {
  teardownMse();
  const ms = new MediaSource();
  mediaSource = ms;
  video.src = URL.createObjectURL(ms);
  ms.addEventListener("sourceopen", () => {
    if (ms !== mediaSource) return; // torn down before it opened (fast reconnect)
    URL.revokeObjectURL(video.src);
    sourceBuffer = ms.addSourceBuffer(`video/mp4; codecs="${codec}"`);
    sourceBuffer.addEventListener("updateend", onMseUpdateEnd);
    pumpMse();
  }, { once: true });
  video.play().catch(() => {}); // muted+playsinline is allowed; retried on touch
  renderLoop();
}

function teardownMse() {
  mseQueue = [];
  if (rafId) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
  if (sourceBuffer) {
    sourceBuffer.removeEventListener("updateend", onMseUpdateEnd);
    sourceBuffer = null;
  }
  mediaSource = null;
  video.removeAttribute("src");
  video.load();
}

function pumpMse() {
  if (!sourceBuffer || sourceBuffer.updating || !mseQueue.length) return;
  try {
    sourceBuffer.appendBuffer(mseQueue.shift());
  } catch (err) {
    // Decoder/buffer wedged (e.g. quota, codec hiccup) — never freeze
    // silently: drop the connection, auto-reconnect brings a fresh stream.
    console.error("MSE append failed:", err);
    setStatus("disconnected", `Stream error: ${err.name} — reconnecting…`);
    if (ws) ws.close();
  }
}

function onMseUpdateEnd() {
  const b = video.buffered;
  if (b.length) {
    const end = b.end(b.length - 1);
    if (end - video.currentTime > LIVE_MAX_BEHIND_S) {
      video.currentTime = end - LIVE_TARGET_BEHIND_S; // fell behind (jank, slow link) — jump
    }
    if (end - b.start(0) > BUFFER_KEEP_S * 2 && sourceBuffer && !sourceBuffer.updating) {
      sourceBuffer.remove(0, end - BUFFER_KEEP_S);
    }
    if (video.paused) video.play().catch(() => {});
  }
  pumpMse();
}

function renderLoop() {
  if (rafId) return;
  const step = () => {
    rafId = requestAnimationFrame(step);
    redraw();
  };
  rafId = requestAnimationFrame(step);
}
