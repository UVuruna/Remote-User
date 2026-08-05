// The Region grab (Attach set, owner 2026-08-05): a rectangle the finger
// sizes and moves anywhere on the screen, whose contents are then captured on
// the PC and PASTED — the phone-side equivalent of Snipping Tool's rectangle.
//
// Two things make it different from the layout aspect panel, whose drag
// mechanics it borrows: this rectangle is bound to NO edge and keeps no
// ratio (owner: "full freedom za dimenzije i poziciju"), and it captures
// instead of arranging. Nothing is captured until Send — the frame is dashed
// for exactly that reason.
//
// The capture itself is the protocol we already have: `screenshot {x, y, w,
// h, paste: true}` crops any rect on the server, fills the clipboard and
// injects Ctrl+V. Loads after controls.js (uses keepFocus/svg/showToast/send)
// and after render.js (drawnRect/viewLocked/layoutRegion).
// See client/__about/region.md.
"use strict";

const regionPanel = document.getElementById("region-panel");

const RG_MIN = 44;    // CSS px — a box smaller than a fingertip cannot be grabbed
const RG_EDGE = 8;    // keep the box off the very screen edge, where Android steals touches

// The box in CSS px, in screen coordinates. Reopened at the same size, so a
// second grab of the same shape is one tap (the PC screen does not move).
let rgBox = null;
let rgEl = null;

function rgClamp() {
  const maxW = window.innerWidth - 2 * RG_EDGE;
  const maxH = window.innerHeight - 2 * RG_EDGE;
  rgBox.w = Math.max(RG_MIN, Math.min(rgBox.w, maxW));
  rgBox.h = Math.max(RG_MIN, Math.min(rgBox.h, maxH));
  rgBox.x = Math.max(RG_EDGE, Math.min(rgBox.x, window.innerWidth - RG_EDGE - rgBox.w));
  rgBox.y = Math.max(RG_EDGE, Math.min(rgBox.y, window.innerHeight - RG_EDGE - rgBox.h));
}

function rgApply() {
  rgClamp();
  rgEl.style.left = `${rgBox.x}px`;
  rgEl.style.top = `${rgBox.y}px`;
  rgEl.style.width = `${rgBox.w}px`;
  rgEl.style.height = `${rgBox.h}px`;
}

// One drag handler for both jobs: `corner` null = move the whole box, else the
// corner being pulled. Pointer capture keeps the drag alive when the finger
// slides off the 44px handle, and pointercancel simply ends it — a half-moved
// box is a harmless state, unlike a stuck mouse button.
function rgDrag(el, corner) {
  let start = null;
  el.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    e.stopPropagation();
    el.setPointerCapture(e.pointerId);
    start = { x: e.clientX, y: e.clientY, box: { ...rgBox } };
  });
  el.addEventListener("pointermove", (e) => {
    if (!start) return;
    const dx = e.clientX - start.x;
    const dy = e.clientY - start.y;
    const b = start.box;
    if (!corner) {
      rgBox.x = b.x + dx;
      rgBox.y = b.y + dy;
    } else {
      // Pulling a corner moves the two edges it owns; the opposite corner
      // stays where it is, which is what makes the gesture feel like a
      // selection and not like a resize dialog.
      const left = corner.includes("w");
      const top = corner.includes("n");
      const x2 = b.x + b.w;
      const y2 = b.y + b.h;
      if (left) {
        rgBox.x = Math.min(b.x + dx, x2 - RG_MIN);
        rgBox.w = x2 - rgBox.x;
      } else {
        rgBox.w = Math.max(RG_MIN, b.w + dx);
      }
      if (top) {
        rgBox.y = Math.min(b.y + dy, y2 - RG_MIN);
        rgBox.h = y2 - rgBox.y;
      } else {
        rgBox.h = Math.max(RG_MIN, b.h + dy);
      }
    }
    rgApply();
  });
  const end = () => { start = null; };
  el.addEventListener("pointerup", end);
  el.addEventListener("pointercancel", end);
}

// Screen CSS px -> monitor-normalized, through the SAME drawn rect the image
// itself uses (device px, hence devicePixelRatio), then clamped to the view:
// in layout focus the capture can never reach outside that layout's region.
function rgToMonitor() {
  const D = drawnRect();
  const s = window.devicePixelRatio || 1;
  let x1 = (rgBox.x * s - D.x) / D.w;
  let y1 = (rgBox.y * s - D.y) / D.h;
  let x2 = ((rgBox.x + rgBox.w) * s - D.x) / D.w;
  let y2 = ((rgBox.y + rgBox.h) * s - D.y) / D.h;
  let lo = { x: 0, y: 0, w: 1, h: 1 };
  if (viewLocked()) lo = layoutRegion;
  x1 = Math.max(lo.x, Math.min(x1, lo.x + lo.w));
  x2 = Math.max(lo.x, Math.min(x2, lo.x + lo.w));
  y1 = Math.max(lo.y, Math.min(y1, lo.y + lo.h));
  y2 = Math.max(lo.y, Math.min(y2, lo.y + lo.h));
  return { x: x1, y: y1, w: Math.max(0, x2 - x1), h: Math.max(0, y2 - y1) };
}

function openRegionPanel() {
  if (!rgBox) {
    rgBox = {
      x: window.innerWidth * 0.18,
      y: window.innerHeight * 0.22,
      w: window.innerWidth * 0.64,
      h: window.innerHeight * 0.5,
    };
  }
  regionPanel.innerHTML = "";

  rgEl = document.createElement("div");
  rgEl.className = "rg-box";
  const move = document.createElement("div");
  move.className = "rg-move";
  move.innerHTML = svg("move");
  rgEl.appendChild(move);
  for (const corner of ["nw", "ne", "sw", "se"]) {
    const h = document.createElement("div");
    h.className = `rg-h rg-${corner}`;
    rgEl.appendChild(h);
    rgDrag(h, corner);
  }
  rgDrag(move, null);
  rgDrag(rgEl, null);   // dragging anywhere inside the frame moves it too
  regionPanel.appendChild(rgEl);

  const bar = document.createElement("div");
  bar.className = "rg-bar";
  const hint = document.createElement("span");
  hint.className = "rg-hint";
  hint.textContent = "Drag the corners, then Send";
  const send_ = document.createElement("button");
  send_.type = "button";
  send_.className = "rg-send";
  send_.textContent = "Send";
  keepFocus(send_, () => {
    const r = rgToMonitor();
    if (r.w <= 0 || r.h <= 0) {
      showToast("Nothing inside the frame — move it over the screen");
      return;
    }
    send({ type: "screenshot", paste: true, ...r });
    showToast("Region pasted on the PC");
    closeRegionPanel();
  });
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "rg-cancel";
  cancel.innerHTML = svg("x");
  keepFocus(cancel, closeRegionPanel);
  bar.append(hint, send_, cancel);
  regionPanel.appendChild(bar);

  rgApply();
  regionPanel.hidden = false;
}

function closeRegionPanel() {
  regionPanel.hidden = true;
  regionPanel.innerHTML = "";
  rgEl = null;
}
