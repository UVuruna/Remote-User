// Canvas rendering, view transform, and dual-mode (H.264 MSE / JPEG) frame
// decode. Part of the app.js split — loads after state.js. See
// client/__about/render.md.
"use strict";

// --- View transform -------------------------------------------------------

// The image is aspect-fitted into the FULL canvas, centered — no reserved
// margins (owner 2026-08-02: the pointer sits under the finger, so the old
// offset margins are gone and the image touches the screen edges).
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

// The rect the view may ever show, in unscaled base-canvas px: the whole
// monitor on the desktop, the layout's own region in layout focus. Panning
// never brings anything outside it into sight.
function viewBounds() {
  if (!viewLocked()) return baseRect;
  const r = layoutRegion;
  return {
    x: baseRect.x + r.x * baseRect.w,
    y: baseRect.y + r.y * baseRect.h,
    w: r.w * baseRect.w,
    h: r.h * baseRect.h,
  };
}

// The HOME transform = maximum zoom-out. On the desktop that is the plain
// aspect-fitted monitor (scale 1); in layout focus it is the region fitted
// into the FULL canvas — a matching-aspect region touches all four screen
// edges (owner 2026-08-02). Pinch zoom works in BOTH modes and can never go
// below home (owner 2026-08-04 — layout focus is no longer a hard lock, it
// just starts and bottoms out at its own framing).
let viewHome = { scale: 1, tx: 0, ty: 0 };

function computeViewHome() {
  if (!viewLocked() || !monitor.w) {
    viewHome = { scale: 1, tx: 0, ty: 0 };
    return;
  }
  const R = viewBounds();
  const s = Math.min(canvas.width / R.w, canvas.height / R.h);
  viewHome = {
    scale: s,
    tx: (canvas.width - R.w * s) / 2 - R.x * s,
    ty: (canvas.height - R.h * s) / 2 - R.y * s,
  };
}

// Snap all the way back out (layout switch, monitor switch, stream reset).
function resetViewHome() {
  computeViewHome();
  view = { ...viewHome };
  redraw();
}

function clampView() {
  const f = viewHome;
  if (view.scale <= f.scale) {
    view = { ...f };
    return;
  }
  view.scale = Math.min(view.scale, f.scale * ZOOM_MAX);
  const s = view.scale;
  const R = viewBounds();
  // Where the bounds rect sits when fully zoomed out — the zoomed view must
  // always cover it, so no letterbox/desktop ever creeps in at an edge.
  const hx = R.x * f.scale + f.tx;
  const hy = R.y * f.scale + f.ty;
  view.tx = Math.min(Math.max(view.tx, hx + R.w * f.scale - (R.x + R.w) * s), hx - R.x * s);
  view.ty = Math.min(Math.max(view.ty, hy + R.h * f.scale - (R.y + R.h) * s), hy - R.y * s);
}

function redraw() {
  ctx.fillStyle = "#0f172a";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const D = drawnRect();
  ctx.save();
  if (viewLocked()) {
    // In layout focus the phone shows ONLY the framed region. Once a layout
    // carries its own aspect ratio the region no longer fills the screen, and
    // what is left over must stay the app's own background — NEVER the
    // desktop behind it (owner 2026-08-03). The PC cursor is clamped to the
    // very same rect (input-geometry.js `toRemoteClamped`), so nothing out
    // there is reachable either: the layout stays one window, whole.
    ctx.beginPath();
    ctx.rect(D.x + layoutRegion.x * D.w, D.y + layoutRegion.y * D.h,
             layoutRegion.w * D.w, layoutRegion.h * D.h);
    ctx.clip();
  }
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
  ctx.restore();
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

// The full viewport for the CURRENT orientation, remembered across keyboard
// openings. The soft keyboard shrinks the viewport (the WebView is resized, or
// visualViewport reports less — depending on the device), and re-fitting the
// picture into that shorter box squeezed the whole layout (owner report
// 2026-08-03). The width is the tell: it never changes when the keyboard
// appears, only on rotation — so a width change resets the remembered height,
// and otherwise the tallest height ever seen for this width IS the full one.
let fullView = { w: 0, h: 0 };

function updateViewport() {
  const vv = window.visualViewport;
  const w = vv ? vv.width : window.innerWidth;
  const visibleH = vv ? vv.height : window.innerHeight;
  const kb = vv ? Math.max(0, window.innerHeight - vv.height - vv.offsetTop) : 0;
  if (Math.abs(w - fullView.w) > 1) fullView = { w, h: visibleH }; // rotation
  else fullView.h = Math.max(fullView.h, visibleH);
  // What the canvas keeps (full height) vs what is actually visible: the
  // difference is how far the canvas is lifted so its BOTTOM edge — the row
  // the user is typing into — sits right above the keyboard.
  const h = fullView.h;
  kbShift = Math.max(0, h - visibleH);
  canvas.style.transform = kbShift ? `translateY(${-kbShift}px)` : "";
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
  computeViewHome(); // rotation / keyboard resize re-fits the layout's region
  clampView();       // ...and keeps whatever zoom the user pinched into
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
