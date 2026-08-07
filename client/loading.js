// The LOADING CUBE: the opaque overlay that covers every second in which the
// PC is actually moving windows, and the settle watcher that decides when it
// may leave.
//
// Split out of layouts.js on 2026-08-07 (THE STRUCTURE LAW) when the owner's
// grid catalogue pushed that file past 1,000 lines. It is a clean seam: this
// module knows nothing about layouts, only about "work is happening" and
// "the streamed picture has stopped moving".
//
// THE RULE IT EXISTS FOR (owner 2026-08-03, said more than once): the
// animation lasts as long as the WORK does — not until the server answers.
// `layout_state` only ARMS the watcher; the overlay drops when the streamed
// screen actually stands still, so the user never watches windows climb out
// of the taskbar.
//
// Loaded BEFORE layouts.js — `showLayLoading`/`hideLayLoading`/
// `settleLayLoading`/`cubeNext` are called from there and from connection.js.
"use strict";

const layLoading = document.getElementById("lay-loading");
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

