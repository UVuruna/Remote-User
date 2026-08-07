// Finger canvas-px -> PC-normalized coordinate mapping, cursor-offset
// calibration, and scroll inertia. Part of the app.js split — loads after
// render.js. See client/__about/input-geometry.md.
"use strict";

// --- Coordinate mapping ---------------------------------------------------

// The one fence around a PC coordinate: the monitor, and inside a focused
// layout that layout's own region — the phone sees ONLY that window, so the
// cursor may never leave it however the coordinate was produced. A finger
// arrives here through toRemoteClamped (canvas pixels); the gamepad's left
// stick arrives here already normalized (client/gamepad.js), and both must be
// fenced by the same rule.
function clampRemote(x, y) {
  x = Math.min(Math.max(x, 0), 1);
  y = Math.min(Math.max(y, 0), 1);
  if (viewLocked()) {
    x = Math.min(Math.max(x, layoutRegion.x), layoutRegion.x + layoutRegion.w);
    y = Math.min(Math.max(y, layoutRegion.y), layoutRegion.y + layoutRegion.h);
  }
  return { x, y };
}

function toRemoteClamped(px, py) {
  const D = drawnRect();
  return clampRemote((px - D.x) / D.w, (py - D.y) / D.h);
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
