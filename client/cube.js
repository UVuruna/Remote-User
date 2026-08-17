// THE LOADING CUBE — the animation itself, as a small reusable gadget.
//
// Extracted from loading.js (2026-08-17) when the update card needed the
// SAME cube — the owner's own logo — spinning as a small badge while an APK
// downloads. Priority C of the root CLAUDE.md ("inheritance over
// duplication — never write the same function twice") ruled out a second
// copy of the spin/burst maths, and tests/test_loading_kind.py's own
// docstring had already named this move as the eventual step. This module
// therefore owns ONLY the motion: the corner-view face order, the idle spin
// speed and the momentum-burst decay, all UNCHANGED in value from the copy
// that used to live in loading.js. It knows nothing about overlays, cards,
// or which of the two loading kinds (constraint 16) is asking it to spin —
// that decision, and every pixel of layout around the cube, stays with
// whoever creates one.
//
// The DOM this needs is minimal by design (the settle-motion.js / grid-
// icons.js / view-anchor.js pattern): `createCube(el)` takes the `.cube`
// element itself (the one carrying the six `.cube-face` children) and
// returns a handle. It touches nothing else — no `#lay-loading`, no
// classList, no siblings — so a node test can hand it a bare fake element
// (anything with a `.style` object) with no real DOM at all.
"use strict";

// Every spin opens on the NEXT face, in the owner's order (top → left →
// back → right → front → bottom, looping — owner 2026-08-03: "each next
// time from a different angle"). Each entry is the corner view that makes
// its face dominant: dead-on plus a ~30° tilt on both axes, so the cube
// still reads as a cube instead of a flat coloured square. UNCHANGED from
// the loading.js original — the face order is the owner's own sketch, not
// this module's to renumber.
const CUBE_VIEWS = [
  { face: "top",    x: -62, y: 40 },
  { face: "left",   x: -28, y: 130 },
  { face: "back",   x: -28, y: 220 },
  { face: "right",  x: -28, y: 310 },
  { face: "front",  x: -28, y: 40 },
  { face: "bottom", x: 62,  y: 40 },
];

const CUBE_BASE_SPEED = 70;  // deg/s idle spin — unchanged
const CUBE_BURST = 300;      // extra degrees granted per whip() — unchanged

/** Build one independent spinning cube around `el` (the `.cube` element —
 *  the parent carrying the six faces; this never touches the parent). Every
 *  call gets its OWN view/angle/burst state, so two cubes on screen at once
 *  (the full overlay and the update card's badge, mid-download) spin
 *  independently and can be started/stopped without fighting each other. */
function createCube(el) {
  let view = -1;
  let tilt = -28;
  let angle = 40;
  let burst = 0;
  let raf = null;
  let last = 0;

  function paint() {
    el.style.transform = `rotateX(${tilt}deg) rotateY(${angle}deg)`;
  }

  function frame(now) {
    const dt = Math.min(100, now - last) / 1000;
    last = now;
    const burstSpeed = Math.min(burst * 3, 720);
    angle = (angle + (CUBE_BASE_SPEED + burstSpeed) * dt) % 360;
    burst = Math.max(0, burst - burstSpeed * dt);
    paint();
    raf = requestAnimationFrame(frame);
  }

  // Opens the NEXT face of CUBE_VIEWS and resets any burst in flight — the
  // same "fresh angle every showing" rule the overlay has always had.
  function nextFace() {
    view = (view + 1) % CUBE_VIEWS.length;
    tilt = CUBE_VIEWS[view].x;
    angle = CUBE_VIEWS[view].y;
    burst = 0;
    paint();
  }

  // Idempotent — a caller that is already spinning may call this again
  // (e.g. re-showing an overlay that never fully stopped through its fade)
  // without starting a second requestAnimationFrame loop.
  function start() {
    if (raf) return;
    last = performance.now();
    raf = requestAnimationFrame(frame);
  }

  function stop() {
    if (raf) cancelAnimationFrame(raf);
    raf = null;
  }

  // A momentum burst — each caller-defined "step" (a window the server
  // created, a chunk of APK bytes that landed) visibly whips the cube
  // onward, decaying back to the idle spin. Named `whip`, not `cubeNext`,
  // because `cubeNext` is loading.js's own public name for its face
  // advance — this module must not shadow that meaning.
  function whip() {
    burst += CUBE_BURST;
  }

  return { start, stop, nextFace, whip, isSpinning: () => raf !== null };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { createCube, CUBE_VIEWS, CUBE_BASE_SPEED, CUBE_BURST };
}
