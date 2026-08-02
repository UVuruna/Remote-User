// Finger canvas-px -> PC-normalized coordinate mapping, cursor-offset
// calibration, and scroll inertia. Part of the app.js split — loads after
// render.js. See client/__about/input-geometry.md.
"use strict";

// --- Coordinate mapping ---------------------------------------------------

function toRemoteClamped(px, py) {
  const D = drawnRect();
  let x = Math.min(Math.max((px - D.x) / D.w, 0), 1);
  let y = Math.min(Math.max((py - D.y) / D.h, 0), 1);
  if (viewLocked()) {
    // Layout focus: the finger may travel past the framed window's edge but
    // the PC cursor must never leave it — the phone sees ONLY this region.
    x = Math.min(Math.max(x, layoutRegion.x), layoutRegion.x + layoutRegion.w);
    y = Math.min(Math.max(y, layoutRegion.y), layoutRegion.y + layoutRegion.h);
  }
  return { x, y };
}

// --- Cursor offset --------------------------------------------------------

// Feed one touch sample; locks the per-session finger radius at the MAX seen.
function sampleFinger(e) {
  if (fingerRadiusPx !== null || e.pointerType !== "touch") return;
  const r = Math.max(e.width, e.height) / 2; // CSS px, the contact ellipse
  if (r <= 2) return;                         // ignore bogus 0/1 defaults
  if (r > fingerMaxPx) fingerMaxPx = r;
  if (++fingerSampleCount >= CURSOR_CALIB_SAMPLES) {
    fingerRadiusPx = fingerMaxPx; // MAX → the pointer clears the fingertip in every press
    computeBaseRect();            // the edge margin tracks the offset distance
    clampView();
    applyLayoutView();
    redraw();
    if (calibrating) {
      calibrating = false;
      showToast(`Calibrated — pointer offset ${Math.round(offsetDistancePx())}px`);
    }
  }
}

// Re-arm calibration (Settings → Calibrate): forget the locked radius and
// re-measure over the next few touches.
function startCalibration() {
  fingerRadiusPx = null;
  fingerMaxPx = 0;
  fingerSampleCount = 0;
  calibrating = true;
  computeBaseRect(); // the offset falls back to the default until re-locked —
  clampView();       // the edge margin must track it, or far edges go unreachable
  applyLayoutView();
  redraw();
  showToast("Calibrating — tap the screen a few times with your finger");
}

// Constant offset distance in CSS px: measured finger radius + margin, clamped.
function offsetDistancePx() {
  const base = fingerRadiusPx === null
    ? CURSOR_OFFSET_FALLBACK
    : fingerRadiusPx + CURSOR_OFFSET_MARGIN;
  return Math.min(Math.max(base, CURSOR_OFFSET_MIN), CURSOR_OFFSET_MAX);
}

// Finger canvas-px point → remote (offset) coords. The pointer sits one offset
// away in the FIXED handedness diagonal — up-left for right-handed (315°),
// up-right for left-handed (45°) — so the hand never covers it. The margin
// reserved in computeBaseRect makes the far edges reachable.
function offsetRemote(p) {
  const d = offsetDistancePx() * devicePixelRatio; // CSS px → canvas px
  const dx = (hand === "left" ? d : -d) * Math.SQRT1_2;
  const dy = -d * Math.SQRT1_2;
  return toRemoteClamped(p.x + dx, p.y + dy);
}

// One entry point: touch fingers get the offset, mouse/pen (desktop dev) don't.
function toRemoteMaybeOffset(p, offset) {
  return offset ? offsetRemote(p) : toRemoteClamped(p.x, p.y);
}

// Send a cursor move and draw the arrow optimistically; the server `cursor`
// echo corrects it. `remote` is the already-offset {x, y}.
function sendCursor(remote) {
  cursorPos = remote;
  send({ type: "pointer_move", ...remote });
  redraw();
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
