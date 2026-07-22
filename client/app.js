// Remote User client — H.264 (MSE) or JPEG stream rendering, virtual cursor,
// pinch zoom, two configurable D-pad groups, and a single toggle "touch mode"
// that decides what one finger on the screen does.

"use strict";

// --- Tunables -------------------------------------------------------------
const ZOOM_MAX = 6;
const TAP_MAX_MOVE = 12;
const SCROLL_PX_PER_TICK = 40;
const SCROLL_FLING_MIN = 0.35;
const SCROLL_FLING_DECAY = 0.004;
const VIEWPORT_MARGIN = 0.15;
const VIEWPORT_THROTTLE_MS = 150;
const RECONNECT_MS = 2000;
const LIVE_MAX_BEHIND_S = 0.5;   // jump to the live edge when this far behind
const LIVE_TARGET_BEHIND_S = 0.1;
const BUFFER_KEEP_S = 8;         // decoded history kept in MSE before trimming

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
//   · right · drag · scroll · pan
// Clicks come from the explicit Click button (press again fast = double
// click). pan moves the local view; two fingers always pinch.
let touchMode = "move";

const pointers = new Map();
let pinch = null;
let primary = null; // the first finger: {id, type, startX, startY, moved, ...}

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
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  else ensureConnected(); // a tap on a dead socket revives the link right away
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
  const root = document.documentElement.style;
  root.setProperty("--kb", `${kb}px`);
  root.setProperty("--vtop", `${vv ? vv.offsetTop : 0}px`);
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  canvas.width = Math.round(w * devicePixelRatio);
  canvas.height = Math.round(h * devicePixelRatio);
  computeBaseRect();
  clampView();
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

// --- Coordinate mapping ---------------------------------------------------

function toRemote(px, py) {
  const D = drawnRect();
  const x = (px - D.x) / D.w;
  const y = (py - D.y) / D.h;
  if (x < 0 || x > 1 || y < 0 || y > 1) return null;
  return { x, y };
}

function toRemoteClamped(px, py) {
  const D = drawnRect();
  return {
    x: Math.min(Math.max((px - D.x) / D.w, 0), 1),
    y: Math.min(Math.max((py - D.y) / D.h, 0), 1),
  };
}

// --- Scroll momentum ------------------------------------------------------

let scrollInertia = null;

function startScrollInertia(vel, pos) {
  if (Math.abs(vel) < SCROLL_FLING_MIN) return;
  let v = vel;
  let carry = 0;
  let last = performance.now();
  const tickPx = SCROLL_PX_PER_TICK * devicePixelRatio;
  function step(now) {
    const dt = now - last;
    last = now;
    carry += v * dt;
    const ticks = Math.trunc(carry / tickPx);
    if (ticks) {
      carry -= ticks * tickPx;
      send({ type: "scroll", x: pos.x, y: pos.y, ticks });
    }
    v *= Math.exp(-SCROLL_FLING_DECAY * dt);
    scrollInertia = Math.abs(v) > 0.02 ? requestAnimationFrame(step) : null;
  }
  scrollInertia = requestAnimationFrame(step);
}

function cancelScrollInertia() {
  if (scrollInertia) {
    cancelAnimationFrame(scrollInertia);
    scrollInertia = null;
  }
}

// --- Icons ----------------------------------------------------------------

const ICONS = {
  mouse: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 7v4"/>',
  right: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 3v7"/><path d="M12 3h2a4 4 0 0 1 4 4v3h-6z" fill="currentColor" stroke="none"/>',
  drag: '<polyline points="5 9 2 12 5 15"/><polyline points="9 5 12 2 15 5"/><polyline points="15 19 12 22 9 19"/><polyline points="19 9 22 12 19 15"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/>',
  scroll: '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
  click: '<path d="M3 3l7.4 18 2.3-7.3L20 11.4z"/><path d="M14 6.5a7 7 0 0 0-8-2.4"/>',
  keyboard: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01M18 13h.01M9 13h6"/>',
  monitor: '<rect x="2" y="4" width="14" height="10" rx="2"/><path d="M9 18h7"/><path d="M9 14v4"/><path d="m17 9 4 3-4 3"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-4.5-4.5L5 21"/>',
  snap: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  x: '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
};

function svg(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
}

// --- Built-in group actions -----------------------------------------------

const BUILTINS = {
  // The finger itself only steers the cursor — Click is the explicit left
  // click at the CURRENT cursor position; press it twice for a double click.
  click:    { label: "Click",  icon: "click",    kind: "send", msg: { type: "click", button: "left" } },
  right:    { label: "Right",  icon: "right",    kind: "mode" },
  drag:     { label: "Drag",   icon: "drag",     kind: "mode" },
  scroll:   { label: "Scroll", icon: "scroll",   kind: "mode" },
  keyboard: { label: "Keys",   icon: "keyboard", kind: "kb" },
  monitor:  { label: "Monitor", icon: "monitor", kind: "send", msg: { type: "monitor_switch" } },
  snap:     { label: "Snap",   icon: "snap",     kind: "send", msg: { type: "screenshot" } },
  upload:   { label: "Image",  icon: "image",    kind: "upload" },
};

// --- Touch-mode toggles ---------------------------------------------------

function setMode(mode) {
  touchMode = touchMode === mode ? "move" : mode;
  refreshModeButtons();
}

function refreshModeButtons() {
  document.querySelectorAll("[data-mode]").forEach((el) =>
    el.classList.toggle("active", el.dataset.mode === touchMode));
}

// --- Keyboard capture (invisible textarea) --------------------------------
// The field never shows — what you type appears in the focused box on the PC
// screen itself (owner decision 2026-07-22: a mirror bar duplicated it). A
// textarea, so the phone IME offers ↵ (new row) instead of a Send/Go key:
// ↵ makes a new row on the PC (Shift+Enter — messengers keep typing instead
// of sending); the D-pad Enter button sends the real Enter.

const kbInput = document.getElementById("kb");
let kbPrev = "";

const SPECIAL_KEYS = {
  Backspace: "backspace", Tab: "tab", Escape: "escape",
  Delete: "delete", Home: "home", End: "end",
  ArrowLeft: "left", ArrowUp: "up", ArrowRight: "right", ArrowDown: "down",
};

function keyboardOpen() {
  return document.activeElement === kbInput;
}

function toggleKeyboard() {
  if (keyboardOpen()) kbInput.blur();
  else kbInput.focus({ preventScroll: true });
}

kbInput.addEventListener("focus", () => {
  document.querySelectorAll('[data-action="keyboard"]').forEach((el) => el.classList.add("active"));
});
kbInput.addEventListener("blur", () => {
  kbInput.value = "";
  kbPrev = "";
  document.querySelectorAll('[data-action="keyboard"]').forEach((el) => el.classList.remove("active"));
});

kbInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    send({ type: "chord", chord: "shift+enter" }); // new row, never "send"
    return;
  }
  const special = SPECIAL_KEYS[e.key];
  if (!special) return;
  e.preventDefault();
  send({ type: "key_special", key: special });
});

function sendTyped(text) {
  // Some IMEs commit "\n" without any keydown — those newlines become the
  // same Shift+Enter new row as the ↵ key.
  const parts = text.split("\n");
  parts.forEach((part, i) => {
    if (i) send({ type: "chord", chord: "shift+enter" });
    if (part) send({ type: "key_text", text: part });
  });
}

kbInput.addEventListener("input", (e) => {
  const value = kbInput.value;
  const minLen = Math.min(kbPrev.length, value.length);
  let p = 0;
  while (p < minLen && kbPrev[p] === value[p]) p++;
  let s = 0;
  while (s < minLen - p && kbPrev[kbPrev.length - 1 - s] === value[value.length - 1 - s]) s++;
  const removed = kbPrev.length - p - s;
  const inserted = value.slice(p, value.length - s);
  for (let i = 0; i < removed; i++) send({ type: "key_special", key: "backspace" });
  if (inserted) sendTyped(inserted);
  kbPrev = value;
  if (!e.isComposing && value.length > 200) {
    kbInput.value = "";
    kbPrev = "";
  }
});

// --- "Access from anywhere" wizard ----------------------------------------
// The server's config carries tailscale_url when the PC is on Tailscale.
// If this page runs on the home (LAN) address, a banner offers a guided
// one-time setup: install the Tailscale app (Play Store link), sign in,
// and the page DETECTS the moment the phone joins (probing /ping on the
// Tailscale address) — then hands over the works-anywhere link. The user
// only follows on-screen steps; nothing is explained outside the app.

let tailscaleUrl = null;
const anywhereBanner = document.getElementById("anywhere-banner");
const wizardEl = document.getElementById("wizard");
const wizStep3 = document.getElementById("wiz-step-3");
const wizStatus = document.getElementById("wiz-status");
const wizHint = document.getElementById("wiz-hint");
const wizOpen = document.getElementById("wiz-open");
let wizTimer = null;

function updateAnywhereBanner() {
  const onAnywhere = tailscaleUrl && new URL(tailscaleUrl).host === location.host;
  anywhereBanner.hidden =
    !tailscaleUrl || onAnywhere || sessionStorage.getItem("wizDismissed") === "1";
}

function openWizard() {
  wizardEl.hidden = false;
  wizProbe();
  if (!wizTimer) wizTimer = setInterval(wizProbe, 3000);
}

function closeWizard(dismiss) {
  wizardEl.hidden = true;
  if (wizTimer) {
    clearInterval(wizTimer);
    wizTimer = null;
  }
  if (dismiss) sessionStorage.setItem("wizDismissed", "1");
  updateAnywhereBanner();
}

async function wizProbe() {
  if (!tailscaleUrl) return;
  try {
    // no-cors: an opaque success still proves the address is reachable —
    // exactly the "phone joined the mesh" signal we need.
    await fetch(`${new URL(tailscaleUrl).origin}/ping`, { mode: "no-cors", cache: "no-store" });
  } catch {
    return; // not on the mesh yet — keep waiting
  }
  wizStep3.classList.add("done");
  wizStatus.textContent = "Connected — your phone is in!";
  wizHint.textContent = "Open your permanent link below and save it (Add to Home screen). It works at home AND anywhere.";
  wizOpen.hidden = false;
  wizOpen.href = tailscaleUrl;
  if (wizTimer) {
    clearInterval(wizTimer);
    wizTimer = null;
  }
}

anywhereBanner.addEventListener("click", openWizard);
document.getElementById("wiz-close").addEventListener("click", () => closeWizard(true));
wizardEl.addEventListener("pointerdown", (e) => {
  if (e.target === wizardEl) closeWizard(true); // backdrop tap = later
});

// window.Android is the APK shell's JS bridge — present = running in the app.
// (Android BROWSERS never reach this page at all: the server routes them to
// the install funnel by User-Agent.)
const IN_APP = typeof window.Android !== "undefined";

// --- Phone → PC image upload ----------------------------------------------

const filePick = document.getElementById("filepick");
filePick.addEventListener("change", async () => {
  const file = filePick.files && filePick.files[0];
  if (!file) return;
  showToast("Uploading image…");
  try {
    const body = new FormData();
    body.append("file", file);
    const res = await fetch(`/upload?token=${encodeURIComponent(token)}`, { method: "POST", body });
    const j = await res.json();
    // The server pastes it into the focused box by itself (Ctrl+V injected) —
    // picking the image was the whole gesture.
    showToast(j.ok ? "Image pasted on the PC" : "Upload failed");
  } catch (err) {
    showToast(`Upload failed: ${err.message}`);
  }
  filePick.value = "";
});

// --- D-pad groups ---------------------------------------------------------

const groupEls = {
  left: document.getElementById("group-left"),
  right: document.getElementById("group-right"),
};
const POSITIONS = ["up", "left", "right", "down"];

let categories = [];
const groups = { left: 0, right: 0 };

function keepFocus(el, onTap) {
  el.addEventListener("pointerdown", (e) => e.preventDefault());
  el.addEventListener("pointerup", (e) => {
    e.preventDefault();
    onTap(e);
  });
}

function makeButton(cls, iconName, label) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = cls;
  el.innerHTML = (iconName ? svg(iconName) : "") + `<span class="lbl">${label}</span>`;
  return el;
}

function makeActionButton(btn, pos) {
  let el;
  if (btn.action && BUILTINS[btn.action]) {
    const b = BUILTINS[btn.action];
    el = makeButton("ctl", b.icon, b.label);
    el.dataset.action = btn.action;
    if (b.kind === "mode") {
      el.dataset.mode = btn.action;
      keepFocus(el, () => setMode(btn.action));
    } else if (b.kind === "kb") {
      keepFocus(el, toggleKeyboard);
    } else if (b.kind === "send") {
      keepFocus(el, () => send(b.msg));
    } else if (b.kind === "upload") {
      keepFocus(el, () => filePick.click());
    }
  } else if (btn.chord) {
    el = makeButton("ctl text", null, btn.label || btn.chord);
    keepFocus(el, () => send({ type: "chord", chord: btn.chord }));
  } else if (btn.key) {
    el = makeButton("ctl text", null, btn.label || btn.key);
    keepFocus(el, () => send({ type: "key_special", key: btn.key }));
  } else {
    el = makeButton("ctl text", null, btn.label || "?");
  }
  el.style.gridArea = POSITIONS[pos];
  return el;
}

function renderGroup(side) {
  const host = groupEls[side];
  host.innerHTML = "";
  const cat = categories[groups[side]];
  if (!cat) return;

  const center = makeButton("ctl cat", cat.icon, cat.name);
  center.style.gridArea = "center";
  keepFocus(center, () => openWheel(side));
  host.appendChild(center);

  (cat.buttons || []).slice(0, 4).forEach((btn, i) => host.appendChild(makeActionButton(btn, i)));
  refreshModeButtons();
  if (keyboardOpen()) {
    host.querySelectorAll('[data-action="keyboard"]').forEach((el) => el.classList.add("active"));
  }
}

// --- Category wheel (tap to open, tap an item, X to cancel) ---------------

const wheelEl = document.getElementById("wheel");
const WHEEL_RADIUS = 118;

function openWheel(side) {
  wheelEl.innerHTML = "";
  const cx = window.innerWidth / 2;
  const cy = window.innerHeight / 2;
  const n = categories.length;
  categories.forEach((cat, i) => {
    const angle = -Math.PI / 2 + (i * 2 * Math.PI) / Math.max(1, n);
    const item = document.createElement("div");
    item.className = "wheel-item" + (i === groups[side] ? " current" : "");
    item.innerHTML = svg(cat.icon) + `<span>${cat.name}</span>`;
    item.style.left = `${cx + WHEEL_RADIUS * Math.cos(angle)}px`;
    item.style.top = `${cy + WHEEL_RADIUS * Math.sin(angle)}px`;
    keepFocus(item, () => {
      groups[side] = i;
      renderGroup(side);
      closeWheel();
    });
    wheelEl.appendChild(item);
  });

  const x = document.createElement("div");
  x.className = "wheel-x";
  x.innerHTML = svg("x");
  keepFocus(x, closeWheel);
  wheelEl.appendChild(x);

  wheelEl.addEventListener("pointerdown", backdropCancel);
  wheelEl.classList.add("open");
}

function backdropCancel(e) {
  if (e.target === wheelEl) {
    e.preventDefault();
    closeWheel();
  }
}

function closeWheel() {
  wheelEl.classList.remove("open");
  wheelEl.removeEventListener("pointerdown", backdropCancel);
  wheelEl.innerHTML = "";
}

// --- Corner buttons -------------------------------------------------------

const panBtn = document.getElementById("btn-pan");
panBtn.dataset.mode = "pan";
keepFocus(panBtn, () => setMode("pan"));

const hideBtn = document.getElementById("btn-hide");
keepFocus(hideBtn, () => {
  const hidden = document.body.classList.toggle("hidden-controls");
  hideBtn.classList.toggle("active", hidden);
});

// --- Toast ----------------------------------------------------------------

let toastTimer = null;
function showToast(text) {
  setStatus("connecting", text);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    if (ws && ws.readyState === WebSocket.OPEN) setStatus("connected", "Connected");
  }, 2500);
}

// --- Canvas gestures ------------------------------------------------------
// One finger acts per `touchMode`; two fingers always pinch-zoom.

function firstTwoPointers() {
  const it = pointers.values();
  return [it.next().value, it.next().value];
}

function beginPinch() {
  if (primary && primary.type === "drag") {
    send({ type: "pointer_up", x: primary.pos.x, y: primary.pos.y, button: "left" });
  }
  primary = null;
  const [p1, p2] = firstTwoPointers();
  const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
  const D = drawnRect();
  pinch = {
    startDist: Math.hypot(p1.x - p2.x, p1.y - p2.y),
    startScale: view.scale,
    qx: (mid.x - D.x) / D.w,
    qy: (mid.y - D.y) / D.h,
  };
}

canvas.addEventListener("pointerdown", (e) => {
  if (keyboardOpen()) e.preventDefault(); // a tap must not blur the keyboard field
  if (streamMode === "h264" && video.paused) video.play().catch(() => {}); // autoplay unlock
  if (e.isPrimary) {
    // Self-heal: Android WebView loses the occasional pointerup/cancel
    // (system edge gestures, palm) — a ghost entry would turn EVERY later
    // tap into a "pinch" until refresh. A new primary pointer is the
    // browser's guarantee that no other finger is really down.
    pointers.clear();
    pinch = null;
    primary = null;
  }
  canvas.setPointerCapture(e.pointerId);
  cancelScrollInertia();
  const p = toCanvasPx(e);
  pointers.set(e.pointerId, p);

  if (pointers.size >= 2) {
    beginPinch();
    return;
  }

  primary = { id: e.pointerId, startX: p.x, startY: p.y, moved: false, type: touchMode };
  if (touchMode === "drag") {
    primary.pos = toRemoteClamped(p.x, p.y);
    send({ type: "pointer_down", x: primary.pos.x, y: primary.pos.y, button: "left" });
  } else if (touchMode === "move") {
    send({ type: "pointer_move", ...toRemoteClamped(p.x, p.y) });
  } else if (touchMode === "scroll") {
    Object.assign(primary, { lastY: p.y, acc: 0, vel: 0, lastT: performance.now(), pos: toRemoteClamped(p.x, p.y) });
  }
});

canvas.addEventListener("pointermove", (e) => {
  const p = toCanvasPx(e);
  if (pointers.has(e.pointerId)) pointers.set(e.pointerId, p);

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
    return;
  }

  if (!primary || primary.id !== e.pointerId) return;

  if (primary.type === "drag") {
    primary.pos = toRemoteClamped(p.x, p.y);
    send({ type: "pointer_move", x: primary.pos.x, y: primary.pos.y });
  } else if (primary.type === "move") {
    send({ type: "pointer_move", ...toRemoteClamped(p.x, p.y) });
  } else if (primary.type === "scroll") {
    const now = performance.now();
    const dy = p.y - primary.lastY;
    primary.vel = dy / Math.max(1, now - primary.lastT);
    primary.lastY = p.y;
    primary.lastT = now;
    primary.acc += dy;
    const tickPx = SCROLL_PX_PER_TICK * devicePixelRatio;
    const ticks = Math.trunc(primary.acc / tickPx);
    if (ticks) {
      primary.acc -= ticks * tickPx;
      send({ type: "scroll", x: primary.pos.x, y: primary.pos.y, ticks });
    }
  } else if (primary.type === "pan") {
    view.tx += p.x - primary.startX;
    view.ty += p.y - primary.startY;
    primary.startX = p.x;
    primary.startY = p.y;
    clampView();
    redraw();
    scheduleViewport();
  } else {
    // right: track travel so an accidental swipe doesn't context-click
    if (Math.hypot(p.x - primary.startX, p.y - primary.startY) > TAP_MAX_MOVE * devicePixelRatio) {
      primary.moved = true;
    }
  }
});

function endPointer(e) {
  pointers.delete(e.pointerId);
  if (pinch && pointers.size < 2) pinch = null;

  if (primary && primary.id === e.pointerId) {
    if (primary.type === "drag") {
      send({ type: "pointer_up", x: primary.pos.x, y: primary.pos.y, button: "left" });
    } else if (primary.type === "scroll") {
      startScrollInertia(primary.vel, primary.pos);
    } else if (primary.type === "right" && !primary.moved && e.type === "pointerup") {
      const pos = toRemote(primary.startX, primary.startY);
      if (pos) {
        send({ type: "pointer_down", x: pos.x, y: pos.y, button: "right" });
        send({ type: "pointer_up", x: pos.x, y: pos.y, button: "right" });
      }
    }
    primary = null;
  }
  if (pointers.size === 0) scheduleViewport();
}

canvas.addEventListener("pointerup", endPointer);
canvas.addEventListener("pointercancel", endPointer);
window.addEventListener("contextmenu", (e) => e.preventDefault());

// --- Connection -----------------------------------------------------------

function connect() {
  setStatus("connecting", `Connecting to ${location.host}…`);
  ws = new WebSocket(`ws://${location.host}/ws`);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "auth", token }));
    lastSentViewport = { x: 0, y: 0, w: 1, h: 1 };
    scheduleViewport();
    setStatus("connected", "Connected");
  };

  ws.onmessage = (e) => {
    if (typeof e.data === "string") {
      const msg = JSON.parse(e.data);
      if (msg.type === "config") {
        // Full view reset — sent after auth and after every stream (re)start
        // (monitor switch, H.264 session reset).
        monitor = { w: msg.monitor_width, h: msg.monitor_height };
        const newMode = msg.stream || "jpeg";
        if (newMode !== streamMode) showToast(newMode === "h264" ? "H.264 stream" : "JPEG stream");
        streamMode = newMode;
        tailscaleUrl = msg.tailscale_url || null;
        if (IN_APP && window.Android.setTailscaleUrl) {
          // The shell stores the works-anywhere address (fresh token included)
          // and probes it on every start — the app then connects on mobile
          // data too, not only on the home Wi-Fi.
          window.Android.setTailscaleUrl(tailscaleUrl || "");
        }
        updateAnywhereBanner();
        view = { scale: 1, tx: 0, ty: 0 };
        detailRegion = { x: 0, y: 0, w: 1, h: 1 };
        if (baseBitmap) { baseBitmap.close(); baseBitmap = null; }
        if (detailBitmap) { detailBitmap.close(); detailBitmap = null; }
        lastSentViewport = { x: 0, y: 0, w: 1, h: 1 };
        cursorPos = null;
        if (streamMode === "h264") initMse(msg.codec);
        else teardownMse();
        computeBaseRect();
        redraw();
      } else if (msg.type === "cursor") {
        cursorPos = { x: msg.x, y: msg.y };
        if (streamMode !== "h264") redraw(); // h264 redraws every rAF anyway
      } else if (msg.type === "actions") {
        categories = msg.categories || [];
        groups.left = Math.min(msg.left ?? 0, categories.length - 1);
        groups.right = Math.min(msg.right ?? 0, categories.length - 1);
        renderGroup("left");
        renderGroup("right");
      } else if (msg.type === "toast") {
        showToast(msg.text);
      }
    } else if (streamMode === "h264") {
      mseQueue.push(e.data);
      pumpMse();
    } else {
      onFrame(e.data);
    }
  };

  ws.onclose = (e) => {
    teardownMse(); // free the decoder; reconnect starts a fresh stream
    if (e.code === 4401) {
      if (IN_APP) {
        // In the APK the fix is one tap — the shell reopens the QR scanner.
        setStatus("disconnected", "Link expired — tap here to scan the new QR");
        statusEl.addEventListener("click", () => window.Android.rescan(), { once: true });
        return;
      }
      setStatus("disconnected", "Invalid token — scan the fresh QR on the PC");
      return;
    }
    setStatus(
      "disconnected",
      document.hidden ? "Paused — screen away" : `Disconnected (code ${e.code}) — retrying…`
    );
  };
}

function ensureConnected() {
  if (document.hidden) return;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  connect();
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    if (ws) ws.close();
  } else {
    // Reconnect the moment the user comes back (app switch, image picker,
    // screen unlock) — waiting out the retry interval swallowed the first
    // taps and read as "input randomly dies".
    ensureConnected();
  }
});
window.addEventListener("pageshow", ensureConnected);

setInterval(ensureConnected, RECONNECT_MS);

connect();
