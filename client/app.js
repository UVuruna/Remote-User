// Remote User client — stream rendering (base layer + sharp region), pinch zoom,
// two configurable D-pad groups with a tap-based category wheel, and mouse modes
// (right / drag / scroll / hover) held as modifier buttons.

"use strict";

// --- Tunables -------------------------------------------------------------
const ZOOM_MAX = 6;
const TAP_MAX_MOVE = 12;          // CSS px of finger travel before a tap stops being a tap
const SCROLL_PX_PER_TICK = 40;    // CSS px of finger travel per wheel tick
const SCROLL_FLING_MIN = 0.35;    // canvas px/ms — below this a release adds no momentum
const SCROLL_FLING_DECAY = 0.004; // exponential velocity decay per ms
const VIEWPORT_MARGIN = 0.15;     // extra region requested around the visible area
const VIEWPORT_THROTTLE_MS = 150;
const RECONNECT_MS = 2000;

// --- State ----------------------------------------------------------------
const canvas = document.getElementById("screen");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");

const token = new URLSearchParams(location.search).get("token");

let monitor = { w: 0, h: 0 };                // real monitor size (server `config`)
let baseRect = { x: 0, y: 0, w: 1, h: 1 };   // where the full monitor sits at zoom 1
let view = { scale: 1, tx: 0, ty: 0 };       // zoom/pan on top of baseRect

// Two-layer image: a full-monitor base (kept in memory so pan/zoom never flashes
// blank) plus the sharp region crop drawn on top when zoomed.
let baseBitmap = null;
let detailBitmap = null;
let detailRegion = { x: 0, y: 0, w: 1, h: 1 };
let ws = null;

// Gesture state
const pointers = new Map();
let tap = null;
let pinch = null;
let gestureHadPinch = false;
let dragState = null;   // {id, pos} — DRAG modifier holds the left button down
let hoverState = null;  // {id} — HOVER modifier moves the cursor, no button
let scrollState = null; // {id, lastY, acc, vel, lastT, pos}
const modifiers = { right: false, drag: false, scroll: false, hover: false };
let panMode = false;    // Move toggle: one finger moves the view, clicks blocked

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
  // Base layer: the whole monitor, always available so motion never goes blank.
  if (baseBitmap) ctx.drawImage(baseBitmap, D.x, D.y, D.w, D.h);
  // Sharp layer: the zoomed region's native pixels, on top of the base.
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

// Sizes the canvas to the visible area (shrinks the instant the soft keyboard
// appears) and publishes keyboard height / top offset for the controls.
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

// --- Icons (Lucide-style, inline) -----------------------------------------

const ICONS = {
  mouse: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 7v4"/>',
  right: '<rect x="6" y="3" width="12" height="18" rx="6"/><path d="M12 3v7"/><path d="M12 3h2a4 4 0 0 1 4 4v3h-6z" fill="currentColor" stroke="none"/>',
  drag: '<polyline points="5 9 2 12 5 15"/><polyline points="9 5 12 2 15 5"/><polyline points="15 19 12 22 9 19"/><polyline points="19 9 22 12 19 15"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/>',
  scroll: '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
  hover: '<path d="M3 3l7.4 18 2.3-7.3L20 11.4z"/>',
  keyboard: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M6 9h.01M10 9h.01M14 9h.01M18 9h.01M6 13h.01M18 13h.01M9 13h6"/>',
  monitor: '<rect x="2" y="4" width="14" height="10" rx="2"/><path d="M9 18h7"/><path d="M9 14v4"/><path d="m17 9 4 3-4 3"/>',
  snap: '<path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  x: '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
};

function svg(name) {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
}

// --- Built-in group actions (modes + functions) ---------------------------

const BUILTINS = {
  right:    { label: "Right",  icon: "right",    kind: "mod" },
  drag:     { label: "Drag",   icon: "drag",     kind: "mod" },
  scroll:   { label: "Scroll", icon: "scroll",   kind: "mod" },
  hover:    { label: "Hover",  icon: "hover",    kind: "mod" },
  keyboard: { label: "Keys",   icon: "keyboard", kind: "kb" },
  monitor:  { label: "Monitor", icon: "monitor", kind: "send", msg: { type: "monitor_switch" } },
  snap:     { label: "Snap",   icon: "snap",     kind: "send", msg: { type: "screenshot" } },
};

// --- Keyboard capture -----------------------------------------------------

const kbInput = document.getElementById("kb");
let kbPrev = "";

const SPECIAL_KEYS = {
  Enter: "enter", Backspace: "backspace", Tab: "tab", Escape: "escape",
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

function reflectKeyboardState() {
  const on = keyboardOpen();
  document.querySelectorAll('[data-action="keyboard"]').forEach((el) => el.classList.toggle("active", on));
}
kbInput.addEventListener("focus", reflectKeyboardState);
kbInput.addEventListener("blur", reflectKeyboardState);

kbInput.addEventListener("keydown", (e) => {
  const special = SPECIAL_KEYS[e.key];
  if (!special) return;
  e.preventDefault();
  send({ type: "key_special", key: special });
});

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
  if (inserted) send({ type: "key_text", text: inserted });
  kbPrev = value;
  if (!e.isComposing && value.length > 200) {
    kbInput.value = "";
    kbPrev = "";
  }
});

// --- D-pad groups ---------------------------------------------------------

const groupEls = {
  left: document.getElementById("group-left"),
  right: document.getElementById("group-right"),
};
const POSITIONS = ["up", "left", "right", "down"];

let categories = [];
const groups = { left: 0, right: 0 };

// Keeps focus on the hidden input so control taps never dismiss the keyboard.
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

function wireModifier(el, name) {
  el.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    el.setPointerCapture(e.pointerId);
    modifiers[name] = true;
    el.classList.add("active");
  });
  const release = () => {
    modifiers[name] = false;
    el.classList.remove("active");
    if (name === "drag") finishDrag();
    if (name === "hover") hoverState = null;
  };
  el.addEventListener("pointerup", release);
  el.addEventListener("pointercancel", release);
}

function makeActionButton(btn, pos) {
  let el;
  if (btn.action && BUILTINS[btn.action]) {
    const b = BUILTINS[btn.action];
    el = makeButton("ctl", b.icon, b.label);
    el.dataset.action = btn.action;
    if (b.kind === "mod") {
      wireModifier(el, btn.action);
    } else if (b.kind === "kb") {
      keepFocus(el, toggleKeyboard);
    } else if (b.kind === "send") {
      keepFocus(el, () => send(b.msg));
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
  reflectKeyboardState();
}

// --- Category wheel (tap to open, tap an item, X to cancel) ---------------

const wheelEl = document.getElementById("wheel");
const WHEEL_RADIUS = 118; // CSS px

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

  // Tapping the dim backdrop (outside any item) also cancels.
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

// --- Corner buttons: Move (pan) + Hide ------------------------------------

const panBtn = document.getElementById("btn-pan");
keepFocus(panBtn, () => {
  panMode = !panMode;
  panBtn.classList.toggle("active", panMode);
});

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

function finishDrag() {
  if (!dragState) return;
  send({ type: "pointer_up", x: dragState.pos.x, y: dragState.pos.y, button: "left" });
  dragState = null;
}

function firstTwoPointers() {
  const it = pointers.values();
  return [it.next().value, it.next().value];
}

canvas.addEventListener("pointerdown", (e) => {
  if (keyboardOpen()) e.preventDefault(); // tapping the screen must not close the keyboard
  canvas.setPointerCapture(e.pointerId);
  cancelScrollInertia();
  const p = toCanvasPx(e);

  if (modifiers.drag && !dragState) {
    dragState = { id: e.pointerId, pos: toRemoteClamped(p.x, p.y) };
    send({ type: "pointer_down", x: dragState.pos.x, y: dragState.pos.y, button: "left" });
    return;
  }
  if (modifiers.hover && !hoverState) {
    hoverState = { id: e.pointerId };
    send({ type: "pointer_move", ...toRemoteClamped(p.x, p.y) });
    return;
  }
  if (modifiers.scroll && !scrollState) {
    scrollState = {
      id: e.pointerId, lastY: p.y, acc: 0, vel: 0,
      lastT: performance.now(), pos: toRemoteClamped(p.x, p.y),
    };
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
      qx: (mid.x - D.x) / D.w,
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
  if (hoverState && hoverState.id === e.pointerId) {
    send({ type: "pointer_move", ...toRemoteClamped(p.x, p.y) });
    return;
  }
  if (scrollState && scrollState.id === e.pointerId) {
    const now = performance.now();
    const dy = p.y - scrollState.lastY;
    scrollState.vel = dy / Math.max(1, now - scrollState.lastT);
    scrollState.lastY = p.y;
    scrollState.lastT = now;
    scrollState.acc += dy;
    const tickPx = SCROLL_PX_PER_TICK * devicePixelRatio;
    const ticks = Math.trunc(scrollState.acc / tickPx);
    if (ticks) {
      scrollState.acc -= ticks * tickPx;
      send({ type: "scroll", x: scrollState.pos.x, y: scrollState.pos.y, ticks });
    }
    return;
  }
  if (!pointers.has(e.pointerId)) return;
  const prev = pointers.get(e.pointerId);
  pointers.set(e.pointerId, p);

  if (panMode && pointers.size === 1 && !pinch) {
    view.tx += p.x - prev.x;
    view.ty += p.y - prev.y;
    clampView();
    redraw();
    scheduleViewport();
    return;
  }
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
  if (hoverState && hoverState.id === e.pointerId) {
    hoverState = null;
    return;
  }
  if (scrollState && scrollState.id === e.pointerId) {
    const { vel, pos } = scrollState;
    scrollState = null;
    startScrollInertia(vel, pos);
    return;
  }

  pointers.delete(e.pointerId);
  if (pinch && pointers.size < 2) pinch = null;
  if (pointers.size > 0) return;

  if (tap && !tap.moved && !gestureHadPinch && !panMode && e.type === "pointerup") {
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
        monitor = { w: msg.monitor_width, h: msg.monitor_height };
        view = { scale: 1, tx: 0, ty: 0 };
        detailRegion = { x: 0, y: 0, w: 1, h: 1 };
        if (baseBitmap) { baseBitmap.close(); baseBitmap = null; }
        if (detailBitmap) { detailBitmap.close(); detailBitmap = null; }
        lastSentViewport = { x: 0, y: 0, w: 1, h: 1 };
        computeBaseRect();
        redraw();
      } else if (msg.type === "actions") {
        categories = msg.categories || [];
        groups.left = Math.min(msg.left ?? 0, categories.length - 1);
        groups.right = Math.min(msg.right ?? 0, categories.length - 1);
        renderGroup("left");
        renderGroup("right");
      } else if (msg.type === "toast") {
        showToast(msg.text);
      }
    } else {
      onFrame(e.data);
    }
  };

  ws.onclose = (e) => {
    if (e.code === 4401) {
      setStatus("disconnected", "Invalid token — scan the fresh QR on the PC");
      return;
    }
    setStatus(
      "disconnected",
      document.hidden ? "Paused — screen away" : `Disconnected (code ${e.code}) — retrying…`
    );
  };
}

document.addEventListener("visibilitychange", () => {
  if (document.hidden && ws) ws.close();
});

setInterval(() => {
  if (document.hidden) return;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  connect();
}, RECONNECT_MS);

connect();
