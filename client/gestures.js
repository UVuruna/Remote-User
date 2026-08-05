// Pointer-event handling on the canvas: pinch-zoom and the one-active-finger
// gesture dispatch (move/drag/scroll/pan per touchMode). Part of the app.js
// split — loads after controls.js. See client/__about/gestures.md.
"use strict";

// --- Canvas gestures ------------------------------------------------------
// One finger acts per `touchMode`; two fingers always pinch-zoom.

function firstTwoPointers() {
  const it = pointers.values();
  return [it.next().value, it.next().value];
}

// Font-zoom staircase (owner 2026-08-05, LAYOUT FOCUS ONLY): pinching out at
// the fitted view keeps "zooming out" by shrinking the window's own content —
// Ctrl+'-' to the PC, step by step — so an article wider than the region
// becomes fully visible. Pinching back in first restores the content toward
// 100% (Ctrl+'='), and only then continues as normal visual zoom. The steps
// already sent are tracked per layout; the effect is whatever the focused app
// does with Ctrl+-/= (browsers/editors scale, some apps ignore it — owner
// accepted). Desktop pinch is untouched.
const FONT_ZOOM_STEP = 1.2; // pinch factor worth one Ctrl+-/= step
const FONT_ZOOM_MAX = 10;
// fontZoomByLayout (index -> steps applied) lives in state.js.

function fontZoomSteps() {
  return (layoutActive !== null && fontZoomByLayout.get(layoutActive)) || 0;
}

function beginPinch() {
  if (primary && primary.type === "drag") {
    send({ type: "pointer_up", x: primary.pos.x, y: primary.pos.y, button: "left" });
  } else if (primary && primary.type === "move" && primary.prevCursor) {
    // The first pinch finger relocated the PC cursor on landing — put it
    // back, or the cursor-relative Click button acts at the stray spot.
    send({ type: "pointer_move", x: primary.prevCursor.x, y: primary.prevCursor.y });
  }
  primary = null;
  const [p1, p2] = firstTwoPointers();
  const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
  const D = drawnRect();
  pinch = {
    startDist: Math.hypot(p1.x - p2.x, p1.y - p2.y),
    startScale: view.scale,
    startFont: viewLocked() ? fontZoomSteps() : 0,
    qx: (mid.x - D.x) / D.w,
    qy: (mid.y - D.y) / D.h,
  };
}

canvas.addEventListener("pointerdown", (e) => {
  // A tap on the stream switches the input switchers OFF by itself (owner
  // 2026-08-04, reversing the old keep-focus rule): clicking outside the
  // textarea is the natural "done typing" — no manual toggle-off needed.
  // (Only for the primary finger — a second pinch finger must not close it.)
  if (e.isPrimary && !layoutArm) inputOff();
  if (streamMode === "h264" && video.paused) video.play().catch(() => {}); // autoplay unlock
  if (layoutArm && e.isPrimary) {
    // Armed by the Layout (+) button: this tap PICKS a window instead of
    // acting — the server answers with layout_offer (nothing is injected).
    layoutArm = false;
    refreshNewlayButton();
    const p0 = toCanvasPx(e);
    send({ type: "layout_pick", ...toRemoteClamped(p0.x, p0.y) });
    pointers.clear();
    pinch = null;
    primary = null;
    return;
  }
  if (e.isPrimary) {
    // Self-heal: Android WebView loses the occasional pointerup/cancel
    // (system edge gestures, palm) — a ghost entry would turn EVERY later
    // tap into a "pinch" until refresh. A new primary pointer is the
    // browser's guarantee that no other finger is really down.
    if (primary && primary.type === "drag" && primary.pos) {
      // The lost pointerup left the PC's left button DOWN — release it,
      // or every later cursor move becomes an OS drag.
      send({ type: "pointer_up", x: primary.pos.x, y: primary.pos.y, button: "left" });
    }
    pointers.clear();
    pinch = null;
    primary = null;
  }
  canvas.setPointerCapture(e.pointerId);
  cancelScrollInertia();
  const p = toCanvasPx(e);
  pointers.set(e.pointerId, p);

  if (pointers.size >= 2) {
    // Two fingers pinch in EVERY mode, layout focus included (owner
    // 2026-08-04) — there the zoom just bottoms out at the layout's own
    // framing instead of the whole monitor.
    beginPinch();
    return;
  }

  // The pointer is exactly under the finger (owner 2026-08-02 — no offset).
  primary = { id: e.pointerId, startX: p.x, startY: p.y, type: touchMode };
  if (touchMode === "drag") {
    primary.pos = toRemoteClamped(p.x, p.y);
    send({ type: "pointer_down", x: primary.pos.x, y: primary.pos.y, button: "left" });
    cursorPos = primary.pos; // optimistic
  } else if (touchMode === "move") {
    primary.prevCursor = cursorPos; // restore point if this turns into a pinch
    sendCursor(toRemoteClamped(p.x, p.y));
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
    const raw = pinch.startScale * (dist / pinch.startDist);
    let s = Math.min(Math.max(raw, viewHome.scale), viewHome.scale * ZOOM_MAX);
    if (viewLocked()) {
      // The staircase: `z` is the finger position in steps relative to the
      // fitted view (negative = below it). Fingers below the floor turn
      // into Ctrl+- steps; on the way back the same steps are undone with
      // Ctrl+= BEFORE any visual zoom resumes.
      const z = Math.log(raw / viewHome.scale) / Math.log(FONT_ZOOM_STEP);
      const desired = Math.min(FONT_ZOOM_MAX,
        Math.max(0, Math.round(pinch.startFont - z)));
      const current = fontZoomSteps();
      if (desired !== current) {
        const chord = desired > current ? "ctrl+minus" : "ctrl+plus";
        for (let i = 0; i < Math.abs(desired - current); i++) {
          send({ type: "chord", chord });
        }
        fontZoomByLayout.set(layoutActive, desired);
      }
      s = Math.min(
        viewHome.scale * Math.pow(FONT_ZOOM_STEP, Math.max(0, z - pinch.startFont)),
        viewHome.scale * ZOOM_MAX
      );
    }
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
    sendCursor(primary.pos);
  } else if (primary.type === "move") {
    sendCursor(toRemoteClamped(p.x, p.y));
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
    }
    primary = null;
  }
  if (pointers.size === 0) scheduleViewport();
}

canvas.addEventListener("pointerup", endPointer);
canvas.addEventListener("pointercancel", endPointer);
window.addEventListener("contextmenu", (e) => e.preventDefault());
