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

// Send a cursor move and draw the arrow optimistically; the server `cursor`
// echo corrects it. The pointer is exactly under the finger (owner 2026-08-02
// — the offset/calibration system is gone).
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
