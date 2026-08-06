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

// THE OVERLAY IS THE FRONT — the work happens behind it (owner rule, said
// four times before it was finally right). It may fade out ONLY when the
// layout window is in place and alone on screen, or — for Desktop — when
// every layout member is really minimized. Two ends have to agree on that:
//
//   1. The SERVER now finishes for real before it answers: DWM's slide
//      animation is disabled per window and it VERIFIES each window stands on
//      its commanded rect (window_manager.wait_landed — position, not just
//      "stopped moving"; a refusal reaches the phone as a toast) and that
//      every member is really iconic on Desktop (wait_minimized).
//      `layout_state` therefore means "the desk is done, checked".
//   2. This side must not trust its own picture too early. THE BUG THE OWNER
//      SAW TWICE: sampling started the instant `layout_state` arrived, but
//      the phone was then still displaying the OLD frame — the encoder and
//      the network are a few hundred ms behind the PC. Two identical samples
//      of a STALE picture read as "settled", the cube left, and the new
//      frames — the ones with the window rising — arrived right after it.
//      So sampling only STARTS after SETTLE_CATCHUP_MS, by which time the
//      finished screen has certainly been decoded here.
const SETTLE_CATCHUP_MS = 650; // stream latency: never judge before this
const SETTLE_SAMPLE_MS = 140;
const SETTLE_DIFF = 2.6;      // mean |Δ| per colour channel that counts as "still"
const SETTLE_STABLE_HITS = 3; // ~420 ms of stillness — 2 let a paused move through
const SETTLE_MAX_MS = 4000;   // never wait longer than this after catching up
const LOADING_MIN_MS = 700;   // never flash the animation
const LOADING_MAX_MS = 40000; // absolute backstop (server never answered)

const settleCanvas = document.createElement("canvas");
settleCanvas.width = 64;
settleCanvas.height = 36;
const settleCtx = settleCanvas.getContext("2d", { willReadFrequently: true });
let settleTimer = null;
let settleStartTimer = null;
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

// Called when the server reports the desk is done (layout_state). The picture
// here is still the old one for another few hundred ms, so judging starts
// only after the catch-up delay — see the block comment above.
function settleLayLoading() {
  if (!layLoadingOpen || settleTimer || settleStartTimer) return;
  settleStartTimer = setTimeout(() => {
    settleStartTimer = null;
    if (!layLoadingOpen) return;
    settlePrev = null;
    settleHits = 0;
    settleDeadline = performance.now() + SETTLE_MAX_MS;
    settleTimer = setInterval(settleTick, SETTLE_SAMPLE_MS);
  }, SETTLE_CATCHUP_MS);
}

function showLayLoading(text) {
  layLoading.querySelector("span").textContent = text || "Working…";
  // A new operation — stop judging the old one; watch again when it answers.
  clearInterval(settleTimer);
  clearTimeout(settleStartTimer);
  settleTimer = null;
  settleStartTimer = null;
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
  clearTimeout(settleStartTimer);
  settleTimer = null;
  settleStartTimer = null;
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

function layRow(label, icon, selected, onTap, ...trailing) {
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
  trailing.filter(Boolean).forEach((el) => row.appendChild(el));
  return row;
}

function ratioLabel(lay) {
  if (!lay.ratio) return "Screen";
  // The stored ratio is FINE-GRAINED (see the aspect panel: w is sent on a
  // 1000-scale), so it is labelled by its closest small pair, not printed raw.
  const [n, d] = ratioPair(lay.ratio[0] / lay.ratio[1], 40);
  return `${n}:${d}`;
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
    // Rename (owner 2026-08-05): the auto name is only the window's title —
    // this is where a layout gets the owner's own name, any time later.
    const ren = document.createElement("button");
    ren.type = "button";
    ren.className = "lay-ratio lay-rename";
    ren.innerHTML = svg("edit");
    keepFocus(ren, () => openRenamePanel(i));
    const asp = document.createElement("button");
    asp.type = "button";
    asp.className = "lay-ratio";
    asp.innerHTML = svg("aspect") + `<span>${ratioLabel(lay)}</span>`;
    keepFocus(asp, () => openAspectPanel(i));
    card.appendChild(layRow(lay.name, lay.icon, i === layoutActive, () => {
      closeLayoutPanel();
      focusLayout(i);
    }, ren, asp));
  });

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Close", false, closeLayoutPanel));
  card.appendChild(actions);
  layPanel.appendChild(card);
}

// The name field. A WRAPPING textarea, not a one-line input: window titles
// are long ("Claude Code - Remote User - Visual Studio Code [Administrator]")
// and a single line hides most of one behind its own horizontal scroll —
// exactly what THE SPACE & LEGIBILITY LAW forbids (caught by the layout
// audit, 2026-08-05). Newlines are stripped: a name is one line of text.
function nameField(value, placeholder) {
  const el = document.createElement("textarea");
  el.className = "lay-name-in";
  el.rows = 3;
  el.maxLength = 80;
  el.autocapitalize = "off";
  el.autocomplete = "off";
  el.spellcheck = false;
  el.placeholder = placeholder || "";
  el.value = value || "";
  el.addEventListener("input", () => {
    if (el.value.includes("\n")) el.value = el.value.replace(/\n/g, " ");
  });
  return el;
}

// Renaming an existing layout (owner 2026-08-05). Nothing on the PC moves —
// only what this layout is CALLED in the bar and the list changes.
function openRenamePanel(index) {
  const lay = layouts[index];
  if (!lay) return;
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card";
  const h = document.createElement("h2");
  h.textContent = "Layout name";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = "Call it whatever you like — the window's title is only the default.";
  const field = nameField(lay.name || "");
  card.append(h, sub, field);

  // The same app-shortcut ticks the creation panel offers, changeable for
  // good (owner 2026-08-06). They live here rather than as a third button in
  // every list row — the row already carries rename and ratio, and a fourth
  // control is what THE SPACE & LEGIBILITY LAW keeps catching.
  const picked = Array.isArray(lay.app_sets)
    ? lay.app_sets.slice()
    : appSets.filter((s) => appSetMatches(s, lay)).map((s) => s.name);
  if (appSets.length) {
    const appLbl = document.createElement("p");
    appLbl.className = "lay-sub";
    appLbl.textContent = "App shortcuts on the wheel for this layout:";
    const appRow = document.createElement("div");
    appRow.className = "lay-row";
    const draw = () => {
      appRow.innerHTML = "";
      appSets.forEach((s) => appRow.appendChild(
        layChip(s.name, picked.includes(s.name), () => {
          const i = picked.indexOf(s.name);
          if (i >= 0) picked.splice(i, 1); else picked.push(s.name);
          draw();
        })));
    };
    draw();
    card.append(appLbl, appRow);
  }

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Cancel", false, openLayoutPicker)); // back one step
  actions.appendChild(layChip("Save", true, () => {
    const name = field.value.trim();
    if (name && name !== lay.name) send({ type: "layout_rename", index, name });
    if (appSets.length) send({ type: "layout_apps", index, sets: picked });
    closeLayoutPanel();
  }));
  card.appendChild(actions);
  layPanel.appendChild(card);
  field.focus();
  field.select();
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

// The panel works on a CONTINUOUS ratio, not on whole units of the device pair
// (owner 2026-08-04): the pair is a coarse approximation of the screen (a
// tablet reduces to 7:5), so stepping it by one unit jumped in ~14% chunks and
// 8:5 was simply unreachable. The state is the plain number W/H; the W:H
// fields are only a readable rendering of it, and both are freely typeable.
// The ONE rule survives: the region may only shrink INWARD from the free axis
// — wide keeps the full height (top/bottom edges pinned), portrait keeps the
// full width (left/right edges pinned).
const ASP_MIN_FRAC = 0.15; // never let the region collapse to a slit
const ASP_SCALE = 1000;    // ratios are sent as round(a * 1000) : 1000

let aspecting = null; // {index, portrait, devA, a, pos, els}

function openAspectPanel(index) {
  const lay = layouts[index];
  if (!lay) return;
  const portrait = lay.orient === "portrait";
  const dev = devicePair(lay.orient);
  const devA = dev[0] / dev[1];
  aspecting = { index, portrait, devA, a: devA,
                pos: typeof lay.pos === "number" ? lay.pos : 0.5 };
  if (lay.ratio && lay.ratio[1] > 0) aspecting.a = clampAspect(lay.ratio[0] / lay.ratio[1]);
  renderAspectPanel();
}

// Fraction of the free axis the region currently uses (1 = the whole screen).
function aspFrac(a) {
  const s = aspecting;
  return s.portrait ? s.devA / a : a / s.devA;
}

function clampAspect(a) {
  const s = aspecting;
  if (!Number.isFinite(a) || a <= 0) return s.devA;
  const f = Math.min(1, Math.max(ASP_MIN_FRAC, aspFrac(a)));
  return s.portrait ? s.devA / f : s.devA * f;
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

  // W : H — BOTH are typeable now (owner 2026-08-04: "8:5" must be reachable
  // by typing it). Whatever pair is typed becomes the ratio, clamped by the
  // one rule; the fields are only refreshed while they are not being edited.
  const fields = document.createElement("div");
  fields.className = "asp-fields";
  const inW = document.createElement("input");
  const inH = document.createElement("input");
  [inW, inH].forEach((el) => {
    el.type = "number";
    el.inputMode = "numeric";
    el.min = "1";
    el.addEventListener("input", () => {
      const w = parseFloat(inW.value);
      const h = parseFloat(inH.value);
      if (!(w > 0) || !(h > 0)) return;
      a.a = clampAspect(w / h);
      a.typing = el;
      updateAspectPreview();
      a.typing = null;
    });
    // Leaving the field snaps its text back onto the (possibly clamped) value.
    el.addEventListener("blur", updateAspectPreview);
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
  screenBox.style.aspectRatio = `${a.devA} / 1`;
  if (a.portrait) screenBox.style.height = "100%";
  else screenBox.style.width = "100%";
  const region = document.createElement("div");
  region.className = "asp-region";
  ["t", "b", "l", "r"].forEach((side) => {
    const dot = document.createElement("i");
    const isFree = a.portrait ? (side === "t" || side === "b") : (side === "l" || side === "r");
    dot.className = `asp-h ${side}${isFree ? " free" : ""}`;
    region.appendChild(dot);
  });
  // The Move handle (owner 2026-08-05): dragging it slides the shrunken
  // region along the free axis — it no longer has to sit centered; a
  // double-tap re-centers it. Everything OUTSIDE the handle still resizes.
  const move = document.createElement("div");
  move.className = "asp-move";
  move.innerHTML = svg("move");
  dragMove(move, screenBox);
  region.appendChild(move);
  screenBox.appendChild(region);
  // The WHOLE preview drags, not just the two 18px dots — on a tablet those
  // dots were nearly unhittable, which is what read as "barely responsive".
  dragAspect(screenBox);
  prev.appendChild(screenBox);
  card.appendChild(prev);

  const value = document.createElement("div");
  value.className = "asp-value";
  card.appendChild(value);

  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Screen", false, () => {
    a.a = a.devA;
    updateAspectPreview();
  }));
  actions.appendChild(layChip("Cancel", false, () => {
    aspecting = null;
    openLayoutPicker(); // back one step, not out of the layouts entirely
  }));
  actions.appendChild(layChip("Apply", true, () => {
    // The full screen is "no override" (0/0); anything else goes as a fine
    // 1000-scale pair, so the server region is exactly what the preview showed.
    // `pos` (0–1000, 500 = centered) is the Move handle's position along the
    // free axis (owner 2026-08-05).
    const full = aspFrac(a.a) > 0.999;
    send({
      type: "layout_aspect", index: a.index,
      w: full ? 0 : Math.round(a.a * ASP_SCALE), h: full ? 0 : ASP_SCALE,
      pos: full ? 500 : Math.round(a.pos * 1000),
    });
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
  const [n, d] = ratioPair(a.a, 40);
  if (a.typing !== a.els.inW) a.els.inW.value = n;
  if (a.typing !== a.els.inH) a.els.inH.value = d;
  // The region sits at fraction `pos` of the free-axis slack (the Move
  // handle) — positioned explicitly, replacing the old centered transform.
  const frac = aspFrac(a.a);
  const pct = `${frac * 100}%`;
  const off = `${a.pos * (1 - frac) * 100}%`;
  const st = a.els.region.style;
  st.transform = "none";
  st.width = a.portrait ? "100%" : pct;
  st.height = a.portrait ? pct : "100%";
  st.left = a.portrait ? "0" : off;
  st.top = a.portrait ? off : "0";
  a.els.value.textContent = `${a.a.toFixed(3)}:1   (${n}:${d})`;
}

// Dragging anywhere in the preview resizes the region symmetrically around the
// centre — the region is always centred on the monitor, so a drag can only
// ever pull it IN from both sides at once. The motion is continuous: the ratio
// follows the finger pixel by pixel, with no whole-unit steps to snap to.
function dragAspect(screenBox) {
  const apply = (e) => {
    const a = aspecting;
    if (!a) return; // the panel closed under a captured pointer
    const r = screenBox.getBoundingClientRect();
    const raw = a.portrait
      ? Math.abs(e.clientY - (r.top + r.height / 2)) * 2 / r.height
      : Math.abs(e.clientX - (r.left + r.width / 2)) * 2 / r.width;
    const frac = Math.min(1, Math.max(ASP_MIN_FRAC, raw)); // never divide by 0
    a.a = a.portrait ? a.devA / frac : a.devA * frac;
    updateAspectPreview();
  };
  screenBox.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    screenBox.setPointerCapture(e.pointerId);
    apply(e);
  });
  screenBox.addEventListener("pointermove", (e) => {
    if (screenBox.hasPointerCapture(e.pointerId)) apply(e);
  });
}

// The Move handle's own drag (owner 2026-08-05): slides the region along the
// free axis; a double-tap re-centers. stopPropagation keeps the screen box's
// resize drag out of the gesture.
let moveTapAt = 0;
function dragMove(handle, screenBox) {
  const apply = (e) => {
    const a = aspecting;
    if (!a) return;
    const r = screenBox.getBoundingClientRect();
    const frac = aspFrac(a.a);
    const freePx = (a.portrait ? r.height : r.width) * (1 - frac);
    if (freePx < 1) return; // full-size region — nowhere to go
    const finger = a.portrait ? e.clientY - r.top : e.clientX - r.left;
    const regionPx = (a.portrait ? r.height : r.width) * frac;
    a.pos = Math.min(1, Math.max(0, (finger - regionPx / 2) / freePx));
    updateAspectPreview();
  };
  handle.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    e.stopPropagation();
    const now = performance.now();
    if (now - moveTapAt < 350) {
      // Double-tap = back to the middle (owner 2026-08-05).
      moveTapAt = 0;
      if (aspecting) {
        aspecting.pos = 0.5;
        updateAspectPreview();
      }
      return;
    }
    moveTapAt = now;
    handle.setPointerCapture(e.pointerId);
  });
  handle.addEventListener("pointermove", (e) => {
    if (handle.hasPointerCapture(e.pointerId)) apply(e);
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
    name: null,             // owner-typed name; null = follow slot 1's title
    apps: null,             // app sets ticked for it; null = follow the process
    mode: "solo",
    grid: null,
    orient: window.innerHeight >= window.innerWidth ? "portrait" : "wide",
    awaitingTap: false,
  };
}

// What the app-shortcut ticks start out as: every set whose `process` matches
// the layout's first window, EXCEPT one that also demands a title — Claude is
// exactly that case, and pre-ticking it for every VSCode window would put its
// slash commands on the wheel of a plain editor. The owner adds it with one
// tap on the Claude layout; everything else is right without him.

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
    // What the PC found running in this window's project — the whole reason
    // Claude no longer needs a tick (owner 2026-08-06).
    agents: msg.target.agents || [],
    tab: msg.tab || null,
    x: msg.x,
    y: msg.y,
  };
}

function slotFromEntry(e) {
  return {
    hwnd: e.hwnd, title: e.title, process: e.process, icon: e.icon,
    agents: e.agents || [],
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

  // The layout's NAME (owner 2026-08-05): the window/tab title is only the
  // default offered here — whatever stands in this field is what the layout
  // bar and the list will call it. Emptying it falls back to the title.
  const nameLbl = document.createElement("p");
  nameLbl.className = "lay-sub";
  nameLbl.textContent = "Name:";
  const nameIn = nameField(
    c.name !== null ? c.name : (c.slots.length ? c.slots[0].title : ""),
    c.slots.length ? c.slots[0].title : "The window's own title");
  nameIn.addEventListener("input", () => { c.name = nameIn.value; });
  card.append(nameLbl, nameIn);

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

  // WHICH app shortcuts this layout carries (owner 2026-08-06). This exists
  // because no string on the PC can identify Claude Code: it names its VSCode
  // tab after the conversation ("Ispravka UI dizajna meni…"), wears the same
  // UIA class as a file tab, and hides its content from accessibility — so
  // the automatic title test could never fire, and the owner marks it here
  // instead. Pre-ticked from the process match, which is right for Chrome,
  // Explorer and plain VSCode and only ever needs a correction for Claude.
  if (appSets.length) {
    const appLbl = document.createElement("p");
    appLbl.className = "lay-sub";
    appLbl.textContent = "App shortcuts on the wheel for this layout:";
    const appRow = document.createElement("div");
    appRow.className = "lay-row";
    if (c.apps === null) c.apps = autoAppSets(c.slots);
    appSets.forEach((s) => appRow.appendChild(
      layChip(s.name, c.apps.includes(s.name), () => {
        const i = c.apps.indexOf(s.name);
        if (i >= 0) c.apps.splice(i, 1); else c.apps.push(s.name);
        renderCreationPanel();
      })));
    card.append(appLbl, appRow);
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
      name: (c.name || "").trim(), // "" = keep the window/tab title
      // An empty list is a real answer ("no app shortcuts here") — the server
      // only falls back to the process guess when the key is missing entirely.
      app_sets: c.apps || autoAppSets(c.slots),
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

