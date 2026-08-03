// Layouts (Phase F+): the loading animation, the top-center layout bar, the
// layout list, the aspect-ratio panel and the whole creation flow. Split out
// of controls.js when that file crossed THE STRUCTURE LAW's 1,000 lines
// (2026-08-03) — layouts are their own responsibility: the chrome in
// controls.js drives the PC directly, everything here composes and frames
// WINDOWS on it.
//
// Loads AFTER controls.js and before gestures.js: it uses `keepFocus`,
// `svg`, `showToast` and `IN_APP` from there, `send`/`layouts`/`layoutActive`
// /`layoutArm` from state.js and the frame sources from render.js, and
// gestures.js/connection.js call into it (`layoutArm` taps, `handleLayoutOffer`,
// `cubeNext`, `settleLayLoading`, `updateLayoutBar`, `applyOrientationLock`).
// See client/__about/layouts.md.
"use strict";

// --- Layouts (Phase F+ step 1) --------------------------------------------
// The + button opens a source CHOOSER (owner 2026-08-02): build the layout
// "From a list" (the server enumerates every window AND its content tabs) or
// "By tapping" windows/tabs in the stream — a grid then takes one tap per
// cell. A creation session (`creating`) collects SLOTS either way; Create
// ships them and the server extracts any tab slots into their own windows
// (a loading overlay covers those seconds). The top-center bar cycles
// Desktop → layout 1 → … , and its framed name opens the full layout list
// (owner 2026-08-03), where every layout also carries its ASPECT RATIO
// panel; the server owns the list (survives disconnects).

const newlayBtn = document.getElementById("btn-newlay");
const layPanel = document.getElementById("layout-panel");
const layLoading = document.getElementById("lay-loading");
const GRID_CELLS = { "2x1": 2, "1x2": 2, "2x2": 4 };

let creating = null; // {source, entries, slots, mode, grid, orient, awaitingTap}
let loadingTimer = null;

// The cube spins CONTINUOUSLY while the overlay is up — tilted corner view
// in orthographic projection, so it always reads as a real cube (owner
// sketch 2026-08-02). Every layout_progress (one per window the server
// creates) injects a momentum burst: each new window visibly whips it
// onward, decaying back to the idle spin.
const layCube = document.getElementById("lay-cube");
const CUBE_BASE_SPEED = 70;  // deg/s idle spin
const CUBE_BURST = 300;      // extra degrees granted per created window
const LOADING_FADE_MS = 280; // must match #lay-loading's CSS transition

// Every showing opens on the NEXT face, in the owner's order
// (top → left → back → right → front → bottom, looping — owner 2026-08-03:
// "each next time from a different angle"). Each entry is the corner view
// that makes its face dominant: dead-on plus a ~30° tilt on both axes, so
// the cube still reads as a cube instead of a flat coloured square.
const CUBE_VIEWS = [
  { face: "top",    x: -62, y: 40 },
  { face: "left",   x: -28, y: 130 },
  { face: "back",   x: -28, y: 220 },
  { face: "right",  x: -28, y: 310 },
  { face: "front",  x: -28, y: 40 },
  { face: "bottom", x: 62,  y: 40 },
];
let cubeView = -1;
let cubeTilt = -28;
let cubeAngle = 40;
let cubeBurst = 0;
let cubeRaf = null;
let cubeStopTimer = null;
let cubeLast = 0;

function cubeFrame(now) {
  const dt = Math.min(100, now - cubeLast) / 1000;
  cubeLast = now;
  const burstSpeed = Math.min(cubeBurst * 3, 720);
  cubeAngle = (cubeAngle + (CUBE_BASE_SPEED + burstSpeed) * dt) % 360;
  cubeBurst = Math.max(0, cubeBurst - burstSpeed * dt);
  layCube.style.transform = `rotateX(${cubeTilt}deg) rotateY(${cubeAngle}deg)`;
  cubeRaf = requestAnimationFrame(cubeFrame);
}

function cubeNext() {
  cubeBurst += CUBE_BURST;
}

// The overlay stays up until the SCREEN has settled (owner 2026-08-03, said
// repeatedly): the server's answer is not the end — windows restore from
// minimized, slide into their cells and repaint for a while after it, and the
// user must never watch that happen. So `layout_state` only ARMS the settle
// watcher: a 64x36 thumbnail of the live frame is sampled a few times a
// second and the overlay drops when two consecutive samples barely differ
// (or when the settle deadline passes — unrelated motion on the PC, e.g. a
// playing video, must not hold it forever).
const SETTLE_SAMPLE_MS = 140;
const SETTLE_DIFF = 2.6;      // mean |Δ| per colour channel that counts as "still"
const SETTLE_STABLE_HITS = 2;
const SETTLE_MAX_MS = 4000;   // never wait longer than this after the server is done
const LOADING_MIN_MS = 700;   // never flash the animation
const LOADING_MAX_MS = 40000; // absolute backstop (server never answered)

const settleCanvas = document.createElement("canvas");
settleCanvas.width = 64;
settleCanvas.height = 36;
const settleCtx = settleCanvas.getContext("2d", { willReadFrequently: true });
let settleTimer = null;
let settlePrev = null;
let settleHits = 0;
let settleDeadline = 0;
let layLoadingOpen = false;
let loadingSince = 0;

function settleStill() {
  // The frame source, not the canvas: the canvas carries the layout view
  // transform, which itself changes when a layout is focused.
  const src = streamMode === "h264"
    ? (video.readyState >= 2 ? video : null)
    : baseBitmap;
  if (!src) return false;
  settleCtx.drawImage(src, 0, 0, settleCanvas.width, settleCanvas.height);
  const data = settleCtx.getImageData(0, 0, settleCanvas.width, settleCanvas.height).data;
  let still = false;
  if (settlePrev) {
    let sum = 0;
    for (let i = 0; i < data.length; i += 4) {
      sum += Math.abs(data[i] - settlePrev[i]) +
             Math.abs(data[i + 1] - settlePrev[i + 1]) +
             Math.abs(data[i + 2] - settlePrev[i + 2]);
    }
    still = sum / (data.length / 4 * 3) < SETTLE_DIFF;
  }
  settlePrev = data;
  return still;
}

function settleTick() {
  settleHits = settleStill() ? settleHits + 1 : 0;
  const now = performance.now();
  if (now > settleDeadline ||
      (settleHits >= SETTLE_STABLE_HITS && now - loadingSince > LOADING_MIN_MS)) {
    hideLayLoading();
  }
}

// Called when the server reports the layout is done (layout_state): from here
// the animation runs only as long as the PICTURE still moves.
function settleLayLoading() {
  if (!layLoadingOpen || settleTimer) return;
  settlePrev = null;
  settleHits = 0;
  settleDeadline = performance.now() + SETTLE_MAX_MS;
  settleTimer = setInterval(settleTick, SETTLE_SAMPLE_MS);
}

function showLayLoading(text) {
  layLoading.querySelector("span").textContent = text || "Working…";
  clearInterval(settleTimer);   // a new operation — watch again when it answers
  settleTimer = null;
  clearTimeout(loadingTimer);
  loadingTimer = setTimeout(hideLayLoading, LOADING_MAX_MS);
  if (layLoadingOpen) return;
  layLoadingOpen = true;
  loadingSince = performance.now();
  cubeView = (cubeView + 1) % CUBE_VIEWS.length;
  cubeTilt = CUBE_VIEWS[cubeView].x;
  cubeAngle = CUBE_VIEWS[cubeView].y;
  cubeBurst = 0;
  layCube.style.transform = `rotateX(${cubeTilt}deg) rotateY(${cubeAngle}deg)`;
  layLoading.classList.add("open");
  clearTimeout(cubeStopTimer);
  if (!cubeRaf) {
    cubeLast = performance.now();
    cubeRaf = requestAnimationFrame(cubeFrame);
  }
}

function hideLayLoading() {
  clearTimeout(loadingTimer);
  loadingTimer = null;
  clearInterval(settleTimer);
  settleTimer = null;
  settlePrev = null;
  if (!layLoadingOpen) return;
  layLoadingOpen = false;
  layLoading.classList.remove("open"); // CSS cross-fades it away
  // Keep spinning THROUGH the fade — a frozen cube during the fade-out is
  // exactly the stutter the smooth exit is meant to remove.
  clearTimeout(cubeStopTimer);
  cubeStopTimer = setTimeout(() => {
    if (layLoadingOpen || !cubeRaf) return;
    cancelAnimationFrame(cubeRaf);
    cubeRaf = null;
  }, LOADING_FADE_MS);
}

function refreshNewlayButton() {
  newlayBtn.classList.toggle("active", layoutArm || creating !== null);
}

function cancelCreation(silent) {
  creating = null;
  layoutArm = false;
  refreshNewlayButton();
  closeLayoutPanel();
  hideLayLoading();
  if (!silent) showToast("Layout creation cancelled");
}

keepFocus(newlayBtn, () => {
  if (creating || layoutArm) {
    cancelCreation();
    return;
  }
  openSourceChooser();
});

const layoutBar = document.getElementById("layout-bar");
const layPickBtn = document.getElementById("lay-pick");
const layNameEl = document.getElementById("lay-name");
const layIconEl = document.getElementById("lay-icon");
const layCloseBtn = document.getElementById("lay-close");

function updateLayoutBar() {
  layoutBar.hidden = layouts.length === 0;
  layCloseBtn.hidden = layoutActive === null;
  const lay = layoutActive === null ? null : layouts[layoutActive];
  layNameEl.textContent = lay ? lay.name : "Desktop";
  layIconEl.hidden = !(lay && lay.icon);
  if (lay && lay.icon) layIconEl.src = lay.icon;
}

// Switching a layout means the PC restores and re-places real windows — the
// cube covers ALL of it (owner 2026-08-03), never the phone showing windows
// climbing out of the taskbar.
function focusLayout(index) {
  send({ type: "layout_focus", index });
  showLayLoading(index < 0 ? "Back to the desktop…" : "Opening the layout…");
}

// The bar cycles positions [Desktop, layout 0, layout 1, …]; index -1 on the
// wire means "back to the full desktop" (the server then minimizes every
// layout member — the desktop shows only non-layout windows).
function layoutStep(dir) {
  if (!layouts.length) return;
  const total = layouts.length + 1;
  const pos = layoutActive === null ? 0 : layoutActive + 1;
  focusLayout(((pos + dir + total) % total) - 1);
}

keepFocus(document.getElementById("lay-prev"), () => layoutStep(-1));
keepFocus(document.getElementById("lay-next"), () => layoutStep(1));
keepFocus(layPickBtn, openLayoutPicker);
keepFocus(layCloseBtn, () => {
  if (layoutActive !== null) send({ type: "layout_remove", index: layoutActive });
});

// --- Layout list + aspect ratio (owner 2026-08-03) -------------------------
// Tapping the bar's name opens every layout at once — stepping ‹ › through a
// dozen of them to reach one was the reported pain. Each row also carries its
// ASPECT button: the region a layout is framed in may be made SMALLER than
// the phone's own shape (portrait keeps the phone's width and only loses
// height, landscape keeps its height and only loses width). Nothing moves on
// the PC until "Apply" — dragging the handle re-arranges only the preview.

function layRow(label, icon, selected, onTap, aspectBtn) {
  const row = document.createElement("div");
  row.className = "lay-item";
  const main = document.createElement("button");
  main.type = "button";
  main.className = "lay-item-main" + (selected ? " sel" : "");
  if (icon) {
    const img = document.createElement("img");
    img.src = icon;
    img.alt = "";
    main.appendChild(img);
  } else {
    main.insertAdjacentHTML("beforeend", svg("desktop"));
  }
  const name = document.createElement("span");
  name.textContent = label;
  main.appendChild(name);
  keepFocus(main, onTap);
  row.appendChild(main);
  if (aspectBtn) row.appendChild(aspectBtn);
  return row;
}

function ratioLabel(lay) {
  return lay.ratio ? `${lay.ratio[0]}:${lay.ratio[1]}` : "Screen";
}

function openLayoutPicker() {
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card";
  const h = document.createElement("h2");
  h.textContent = "Layouts";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = "Tap one to open it, or its ratio to reshape it.";
  card.append(h, sub);

  card.appendChild(layRow("Desktop", null, layoutActive === null, () => {
    closeLayoutPanel();
    focusLayout(-1);
  }));

  layouts.forEach((lay, i) => {
    const asp = document.createElement("button");
    asp.type = "button";
    asp.className = "lay-ratio";
    asp.innerHTML = svg("aspect") + `<span>${ratioLabel(lay)}</span>`;
    keepFocus(asp, () => openAspectPanel(i));
    card.appendChild(layRow(lay.name, lay.icon, i === layoutActive, () => {
      closeLayoutPanel();
      focusLayout(i);
    }, asp));
  });

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Close", false, closeLayoutPanel));
  card.appendChild(actions);
  layPanel.appendChild(card);
}

// The phone's own side ratio as small whole numbers: raw pixels reduce to
// unusable pairs (412x892 → 103:223), so this is the best approximation with
// a denominator of at most 40 — 412x892 → 6:13, 1080x2400 → 9:20.
function ratioPair(value, maxDen) {
  let best = [1, 1];
  let bestErr = Infinity;
  for (let d = 1; d <= maxDen; d++) {
    const n = Math.max(1, Math.round(value * d));
    const err = Math.abs(value - n / d);
    if (err < bestErr - 1e-9) {
      bestErr = err;
      best = [n, d];
    }
  }
  return best;
}

function devicePair(orient) {
  const s = Math.min(window.screen.width, window.screen.height);
  const l = Math.max(window.screen.width, window.screen.height);
  const [n, d] = ratioPair(s / l, 40); // short : long
  return orient === "portrait" ? [n, d] : [d, n];
}

let aspecting = null; // {index, dev:[W,H], val:[W,H], portrait}

function openAspectPanel(index) {
  const lay = layouts[index];
  if (!lay) return;
  const portrait = lay.orient === "portrait";
  const dev = devicePair(lay.orient);
  // An existing override only ever shrank the free axis, so it is re-read on
  // the device's own scale; anything larger is clamped back to the screen.
  let val = dev.slice();
  if (lay.ratio) {
    const a = lay.ratio[0] / lay.ratio[1];
    val = portrait
      ? [dev[0], Math.max(1, Math.min(dev[1], Math.round(dev[0] / a)))]
      : [Math.max(1, Math.min(dev[0], Math.round(dev[1] * a))), dev[1]];
  }
  aspecting = { index, dev, val, portrait };
  renderAspectPanel();
}

function renderAspectPanel() {
  const a = aspecting;
  const lay = layouts[a.index];
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card";

  const h = document.createElement("h2");
  h.textContent = "Aspect ratio";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = `${lay ? lay.name : "Layout"} — ${a.portrait ? "portrait" : "wide"}: ` +
    (a.portrait ? "full width, free height" : "full height, free width");
  card.append(h, sub);

  // W : H — the pinned side is locked, the free side is typed or dragged.
  const fields = document.createElement("div");
  fields.className = "asp-fields";
  const inW = document.createElement("input");
  const inH = document.createElement("input");
  [inW, inH].forEach((el) => {
    el.type = "number";
    el.inputMode = "numeric";
    el.min = "1";
  });
  inW.value = a.val[0];
  inH.value = a.val[1];
  inW.max = String(a.dev[0]);
  inH.max = String(a.dev[1]);
  inW.disabled = a.portrait;
  inH.disabled = !a.portrait;
  const free = a.portrait ? inH : inW;
  const freeIdx = a.portrait ? 1 : 0;
  free.addEventListener("input", () => {
    const n = parseInt(free.value, 10);
    if (!Number.isFinite(n)) return;
    a.val[freeIdx] = Math.max(1, Math.min(a.dev[freeIdx], n));
    updateAspectPreview();
  });
  const wLbl = document.createElement("b");
  wLbl.textContent = "W";
  const colon = document.createElement("b");
  colon.textContent = ":";
  const hLbl = document.createElement("b");
  hLbl.textContent = "H";
  fields.append(wLbl, inW, colon, hLbl, inH);
  card.appendChild(fields);

  // Preview: dashed phone screen, solid region inside it (owner reference —
  // the Prompt Painter aspect widget).
  const prev = document.createElement("div");
  prev.className = "asp-prev";
  const screenBox = document.createElement("div");
  screenBox.className = "asp-screen";
  screenBox.style.aspectRatio = `${a.dev[0]} / ${a.dev[1]}`;
  if (a.portrait) screenBox.style.height = "100%";
  else screenBox.style.width = "100%";
  const region = document.createElement("div");
  region.className = "asp-region";
  ["t", "b", "l", "r"].forEach((side) => {
    const dot = document.createElement("i");
    const isFree = a.portrait ? (side === "t" || side === "b") : (side === "l" || side === "r");
    dot.className = `asp-h ${side}${isFree ? " free" : ""}`;
    if (isFree) dragHandle(dot, screenBox);
    region.appendChild(dot);
  });
  screenBox.appendChild(region);
  prev.appendChild(screenBox);
  card.appendChild(prev);

  const value = document.createElement("div");
  value.className = "asp-value";
  card.appendChild(value);

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Screen", false, () => {
    a.val = a.dev.slice();
    renderAspectPanel();
  }));
  actions.appendChild(layChip("Cancel", false, () => {
    aspecting = null;
    openLayoutPicker(); // back one step, not out of the layouts entirely
  }));
  actions.appendChild(layChip("Apply", true, () => {
    send({ type: "layout_aspect", index: a.index, w: a.val[0], h: a.val[1] });
    aspecting = null;
    closeLayoutPanel();
    showLayLoading("Reshaping the layout…");
  }));
  card.appendChild(actions);
  layPanel.appendChild(card);

  a.els = { inW, inH, region, value };
  updateAspectPreview();
}

function updateAspectPreview() {
  const a = aspecting;
  if (!a || !a.els) return;
  a.els.inW.value = a.val[0];
  a.els.inH.value = a.val[1];
  a.els.region.style.width = a.portrait ? "100%" : `${(a.val[0] / a.dev[0]) * 100}%`;
  a.els.region.style.height = a.portrait ? `${(a.val[1] / a.dev[1]) * 100}%` : "100%";
  a.els.value.textContent =
    `${(a.val[0] / a.val[1]).toFixed(3)}:1   (${a.val[0]}:${a.val[1]})`;
}

// Dragging a free-axis handle resizes the preview symmetrically around the
// centre — the region is always centred on the monitor, so the handle can
// only ever pull the region IN from both sides at once.
function dragHandle(dot, screenBox) {
  dot.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    dot.setPointerCapture(e.pointerId);
  });
  dot.addEventListener("pointermove", (e) => {
    if (!dot.hasPointerCapture(e.pointerId)) return;
    const a = aspecting;
    if (!a) return; // the panel closed under a captured pointer
    const r = screenBox.getBoundingClientRect();
    const frac = a.portrait
      ? Math.abs(e.clientY - (r.top + r.height / 2)) * 2 / r.height
      : Math.abs(e.clientX - (r.left + r.width / 2)) * 2 / r.width;
    const i = a.portrait ? 1 : 0;
    a.val[i] = Math.max(1, Math.min(a.dev[i], Math.round(frac * a.dev[i])));
    updateAspectPreview();
  });
}

// In the APK, layout focus locks the phone's rotation to the layout's chosen
// orientation; the full desktop unlocks it (owner 2026-08-02). "" = unlock.
function applyOrientationLock() {
  if (!IN_APP || !window.Android.lockOrientation) return;
  window.Android.lockOrientation(
    layoutActive !== null && layouts[layoutActive] ? layouts[layoutActive].orient : "");
}

// --- Layout creation -------------------------------------------------------

function closeLayoutPanel() {
  layPanel.hidden = true;
  layPanel.innerHTML = "";
  aspecting = null;
}

layPanel.addEventListener("pointerdown", (e) => {
  if (e.target !== layPanel) return;
  // Backdrop tap = out. Only a creation session has anything to cancel; the
  // list and the aspect panel just close (nothing was sent).
  if (creating) cancelCreation();
  else closeLayoutPanel();
});

function layChip(label, selected, onTap, icon) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "lay-chip" + (selected ? " sel" : "");
  if (icon) {
    const img = document.createElement("img");
    img.src = icon;
    img.alt = "";
    el.appendChild(img);
  }
  el.appendChild(document.createTextNode(label));
  keepFocus(el, onTap);
  return el;
}

function newCreation(source) {
  return {
    source,                 // "list" | "tap"
    entries: null,          // list source: [{kind, hwnd, title, process, icon, tab?, x?, y?}]
    slots: [],              // chosen cells, in order — slot 1 names the layout
    mode: "solo",
    grid: null,
    orient: window.innerHeight >= window.innerWidth ? "portrait" : "wide",
    awaitingTap: false,
  };
}

function openSourceChooser() {
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card";
  const h = document.createElement("h2");
  h.textContent = "New layout";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = "Where should the windows come from?";
  const row = document.createElement("div");
  row.className = "lay-row lay-sources";
  // The two sources carry the owner's icons (clipboard list / window+plus).
  function sourceBtn(iconName, label, onTap) {
    const el = document.createElement("button");
    el.type = "button";
    el.className = "lay-chip lay-source";
    el.innerHTML = svg(iconName) + `<span>${label}</span>`;
    keepFocus(el, onTap);
    return el;
  }
  row.appendChild(sourceBtn("list", "From a list", () => {
    creating = newCreation("list");
    refreshNewlayButton();
    closeLayoutPanel();
    showLayLoading("Collecting windows and tabs…");
    send({ type: "layout_list" });
  }));
  row.appendChild(sourceBtn("newwin", "Tap a window", () => {
    creating = newCreation("tap");
    armNextTap();
  }));
  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Cancel", false, () => cancelCreation()));
  card.append(h, sub, row, actions);
  layPanel.appendChild(card);
}

function armNextTap() {
  creating.awaitingTap = true;
  layoutArm = true;
  refreshNewlayButton();
  closeLayoutPanel();
  showToast("Tap a window or tab on the screen…");
}

function cellsNeeded() {
  return creating.mode === "grid" ? (GRID_CELLS[creating.grid] || 2) : 1;
}

function slotFromOffer(msg) {
  return {
    hwnd: msg.target.hwnd,
    title: msg.tab ? msg.tab.name : msg.target.title,
    process: msg.target.process,
    icon: msg.target.icon,
    tab: msg.tab || null,
    x: msg.x,
    y: msg.y,
  };
}

function slotFromEntry(e) {
  return {
    hwnd: e.hwnd, title: e.title, process: e.process, icon: e.icon,
    tab: e.tab || null, x: e.x, y: e.y,
  };
}

// The layout_offer handler (connection.js delegates here): either the list
// arrived, or one tap's result — both feed the same creation session.
function handleLayoutOffer(msg) {
  hideLayLoading();
  layoutArm = false;
  if (!creating) creating = newCreation("tap");
  if (msg.entries) {
    creating.entries = msg.entries;
  } else if (msg.target) {
    creating.slots.push(slotFromOffer(msg));
    creating.awaitingTap = false;
  }
  refreshNewlayButton();
  renderCreationPanel();
}

function sameSlot(a, b) {
  return a.hwnd === b.hwnd &&
    (a.tab ? b.tab && a.tab.name === b.tab.name : !b.tab);
}

function renderCreationPanel() {
  const c = creating;
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card";

  const h = document.createElement("h2");
  h.textContent = "New layout";
  card.appendChild(h);

  // chosen slots — tap one to remove it
  if (c.slots.length) {
    const sub = document.createElement("p");
    sub.className = "lay-sub";
    sub.textContent = `Chosen (${c.slots.length}/${cellsNeeded()}) — tap to remove:`;
    card.appendChild(sub);
    const row = document.createElement("div");
    row.className = "lay-row";
    c.slots.forEach((s, i) => row.appendChild(
      layChip(s.title.length > 30 ? s.title.slice(0, 29) + "…" : s.title, true,
              () => { c.slots.splice(i, 1); renderCreationPanel(); }, s.icon)));
    card.appendChild(row);
  }

  const modeRow = document.createElement("div");
  modeRow.className = "lay-row";
  modeRow.appendChild(layChip("Only one", c.mode === "solo", () => {
    c.mode = "solo";
    c.grid = null;
    c.slots = c.slots.slice(0, 1);
    renderCreationPanel();
  }));
  ["2x1", "1x2", "2x2"].forEach((g) => modeRow.appendChild(
    layChip(`Grid ${g}`, c.mode === "grid" && c.grid === g, () => {
      c.mode = "grid";
      c.grid = g;
      c.slots = c.slots.slice(0, GRID_CELLS[g]);
      renderCreationPanel();
    })));
  card.appendChild(modeRow);

  if (c.source === "list" && c.entries) {
    const hint = document.createElement("p");
    hint.className = "lay-sub";
    hint.textContent = "Windows and tabs on the PC:";
    card.appendChild(hint);
    const list = document.createElement("div");
    list.className = "lay-row lay-list";
    c.entries.forEach((e) => {
      const slot = slotFromEntry(e);
      const idx = c.slots.findIndex((s) => sameSlot(s, slot));
      const label = (e.kind === "tab" ? "↳ " : "") +
        (e.title.length > 34 ? e.title.slice(0, 33) + "…" : e.title);
      list.appendChild(layChip(label, idx >= 0, () => {
        if (idx >= 0) c.slots.splice(idx, 1);          // tap again = deselect
        else if (c.slots.length < cellsNeeded()) c.slots.push(slot);
        else c.slots[c.slots.length - 1] = slot;       // full = replace last
        renderCreationPanel();
      }, e.kind === "window" ? e.icon : null));
    });
    card.appendChild(list);
  } else if (c.source === "tap" && c.slots.length < cellsNeeded()) {
    const row = document.createElement("div");
    row.className = "lay-row";
    row.appendChild(layChip(`Tap window ${c.slots.length + 1} of ${cellsNeeded()}`,
                            false, armNextTap));
    card.appendChild(row);
  }

  const orientRow = document.createElement("div");
  orientRow.className = "lay-row";
  orientRow.appendChild(layChip("Portrait", c.orient === "portrait", () => {
    c.orient = "portrait";
    renderCreationPanel();
  }));
  orientRow.appendChild(layChip("Wide", c.orient === "wide", () => {
    c.orient = "wide";
    renderCreationPanel();
  }));
  card.appendChild(orientRow);

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Cancel", false, () => cancelCreation()));
  const ready = c.slots.length === cellsNeeded();
  actions.appendChild(layChip("Create", ready, () => {
    if (!ready) return;
    send({
      type: "layout_create",
      slots: c.slots.map((s) => ({ hwnd: s.hwnd, tab: s.tab, x: s.x, y: s.y })),
      mode: c.mode,
      grid: c.grid,
      orient: c.orient,
    });
    creating = null;
    refreshNewlayButton();
    closeLayoutPanel();
    // Tab extraction takes a few seconds of visible work on the PC — the
    // overlay says so instead of a frozen-looking phone (owner 2026-08-02).
    showLayLoading("Arranging the windows…");
  }));
  card.appendChild(actions);
  layPanel.appendChild(card);
}

