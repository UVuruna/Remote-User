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
// Loaded AFTER cube.js (its `createCube` factory, 2026-08-17) and
// settle-motion.js (its pure `changedFraction`/`isSettled`, task 194), and
// BEFORE layouts.js — `showLayLoading`/`hideLayLoading`/`settleLayLoading`/
// `cubeNext` are called from there and from connection.js.
"use strict";

const layLoading = document.getElementById("lay-loading");
let creating = null; // {source, entries, slots, mode, grid, orient, awaitingTap}
let loadingTimer = null;

// The cube spins CONTINUOUSLY while the overlay is up — tilted corner view
// in orthographic projection, so it always reads as a real cube (owner
// sketch 2026-08-02). Every layout_progress (one per window the server
// creates) injects a momentum burst: each new window visibly whips it
// onward, decaying back to the idle spin.
//
// THE MOTION ITSELF LIVES IN cube.js NOW (split out 2026-08-17, when the
// update card needed the SAME cube spinning as a small badge — priority C,
// "never write the same function twice"). This file keeps every name a
// caller already depends on (`cubeNext`, `showLayLoading`, `hideLayLoading`,
// `settleLayLoading`, `settleStreamReset`) and delegates the actual spin to
// one `createCube()` handle bound to `#lay-cube`. Nothing about the overlay's
// appearance or timing changed in this split — only where the maths live.
const layCube = document.getElementById("lay-cube");
const layCubeHandle = createCube(layCube);
const LOADING_FADE_MS = 500; // must match #lay-loading's CSS transition
// Delays STOPPING the spin until the fade-out finishes — see hideLayLoading.
// A plain `let`, same as before the split: this timer belongs to the
// overlay's own show/hide bookkeeping, not to the cube gadget itself.
let cubeStopTimer = null;

// Public name every caller (connection.js) already uses — one turn per
// window the server creates. Kept as its own function, not an alias, so a
// caller reading this file sees the same name it has always called.
function cubeNext() {
  layCubeHandle.whip();
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
//
// TASK 194 — "traje predugo ... radi kontra uslugu" (it takes too long, it
// works against him). Root cause: the OLD metric was a whole-thumbnail MEAN
// of |Δ| per channel, which required the picture to be near-PERFECTLY still
// before it counted a hit. A blinking caret is a tiny patch and washes out
// in a mean over 64x36 samples, but his agents actively typing/scrolling in
// a member window is real, LOCAL, ongoing motion covering a real share of
// the thumbnail — enough to keep pushing the mean over the old threshold for
// the entire watch window, every time. The server has ALREADY verified
// placement by the time `layout_state` arrives (window_manager.wait_landed,
// see the block above) — this side is not proving the windows landed, only
// that watching the raw stream a moment longer would not have looked better.
// So the metric moved into its own PURE module, client/settle-motion.js (the
// view-anchor.js/cursor-shapes.js pattern — loaded just before this file so
// `changedFraction`/`isSettled` are in scope here, and node can run it whole
// with no DOM for tests/test_loading_settle.py): "how big is the average
// change" became "what FRACTION of the picture actually changed" — a caret
// blink or a terminal's own cursor is a few percent of the frame and reads
// as settled, while a window actually sliding into place changes a large
// share of it and still does not. And because even a genuinely busy screen
// (multiple agents producing output at once) can keep the fraction above
// threshold for a while, SETTLE_MAX_MS is now a REAL "a few seconds", not a
// five-second last resort — the server already said the desk is done; this
// side owes him a moment to catch the stream up, not a fight to see the
// picture stop moving entirely.
// AND ON THE PATH HE COMPLAINED ABOUT, THIS TIMER NO LONGER RUNS AT ALL
// (2026-08-12). A layout change now ends the encoder session BEFORE
// `layout_state` goes out (server/layout_api.py), so the phone gets a fresh
// `config` moments later and `settleStreamReset` below throws this timer away
// and waits for the new session's FIRST DECODED FRAME instead — evidence in
// place of a guess, and typically sooner. The number therefore only still
// governs the cases where no new session arrives (a layout change that does
// not move the crop, JPEG), where its original job is untouched: the picture
// on this phone is genuinely a few hundred ms behind the PC, and two samples
// of a stale pre-move frame read as "settled". It is deliberately NOT cut on
// that path — nothing here can yet tell a stale frame from a fresh one, and
// the owner's rule is that the overlay leaves on evidence, never early.
const SETTLE_CATCHUP_MS = 650; // stream latency: never judge before this
const SETTLE_SAMPLE_MS = 140;
const SETTLE_STABLE_HITS = 3; // ~420 ms of stillness — 2 let a paused move through
const SETTLE_MAX_MS = 2200;   // "a few seconds" after catching up (task 194: was 4000)
// NO FLOOR (owner ruling 2026-08-12, and he rejected the idea by name: "what
// 700-millisecond floor? no floor is needed at all ... in any case we must not
// produce this counter-effect where the user waits BECAUSE OF the loading
// animation"). It was 700 ms of "never flash the animation", and on a fast
// return that was 700 ms of the app waiting on itself over a PC that had
// finished. What it was really protecting — a jarring blink — is now bought by
// the FADE instead (LOADING_FADE_MS, 500 ms): a fade runs over the picture it
// is uncovering, so he watches the screen appear through it and is never held
// by it, which is exactly the difference between covering time and adding it.
// Kept as a named 0 rather than deleted so the question cannot be re-asked
// silently, and so `settleTick` below still reads one rule in one place.
const LOADING_MIN_MS = 0;
const LOADING_MAX_MS = 40000; // absolute backstop (server never answered)

const settleCanvas = document.createElement("canvas");
settleCanvas.width = 64;
settleCanvas.height = 36;
const settleCtx = settleCanvas.getContext("2d", { willReadFrequently: true });
let settleTimer = null;
let settleStartTimer = null;
let settleWaitTimer = null;
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
  const still = isSettled(changedFraction(data, settlePrev));
  settlePrev = data;
  return still;
}

function settleTick() {
  settleHits = settleStill() ? settleHits + 1 : 0;
  const now = performance.now();
  const still = settleHits >= SETTLE_STABLE_HITS && now - loadingSince > LOADING_MIN_MS;
  if (now > settleDeadline || still) {
    // WHY it left is half the measurement (task 203): "the picture stood
    // still" and "we ran out of patience" are different bugs, and only one of
    // them is this module's fault. `hideReason` is read by hideLayLoading and
    // reported once per return in connection.js.
    hideLayLoading(still ? "picture settled" : "settle cap");
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

// A NEW ENCODER SESSION ARRIVED WHILE THE OVERLAY IS UP (2026-08-12).
//
// Called from connection.js on every `config`, which is the page's only news
// that the stream was rebuilt — a layout region change and a quality change
// both end one ffmpeg and open another, and that takes about half a second on
// the owner's own PC. Two things go wrong if the watcher is left alone through
// it, and they pull in opposite directions:
//
//   * It can hide the cube on a LIE. Between the old session ending and the
//     new one decoding, the picture on this phone is frozen by definition —
//     nothing is arriving. Three identical samples of that stopped picture is
//     exactly what `settleTick` counts as "settled", and with the last frame
//     now held across the swap (render.js `initMse`), `readyState` is no
//     longer there to save us for the whole gap. He would watch the windows
//     land under a page that had already declared itself ready — the very
//     complaint this module exists for.
//   * Or it wastes the wait. The catch-up it is sitting through was measured
//     against the OLD session's latency; the new one starts from nothing.
//
// So the watcher is re-armed on EVIDENCE, not on a fresh timer: sampling
// begins when this session has really decoded a frame, and not one tick
// before. That is both stricter and faster than restarting the catch-up —
// there is no stale picture left to drain once a new frame has been shown.
// LOADING_MAX_MS above is still the only backstop, unchanged.
// Has the NEW session put a frame on the canvas yet? `render.js` clears
// `sessionDrew` in `initMse` and sets it on that session's first successful
// draw, and nothing weaker will do: `video.readyState` can still read 2 for
// the OLD buffer after a teardown (`video.load()` is asynchronous), and that
// stale picture is frozen — the exact input `settleTick` scores as settled.
// JPEG has no session to wait for. The `undefined` arm is for the audit
// harness, which loads this module without render.js.
function streamHasPainted() {
  if (streamMode !== "h264") return true;
  if (typeof sessionDrew === "undefined") return video.readyState >= 2;
  return sessionDrew;
}

function settleStreamReset() {
  if (!layLoadingOpen) return;
  clearInterval(settleTimer);
  clearTimeout(settleStartTimer);
  clearInterval(settleWaitTimer);
  settleTimer = null;
  settleStartTimer = null;
  settlePrev = null;
  settleHits = 0;
  settleWaitTimer = setInterval(() => {
    if (!layLoadingOpen) {
      clearInterval(settleWaitTimer);
      settleWaitTimer = null;
      return;
    }
    if (!streamHasPainted()) return;
    clearInterval(settleWaitTimer);
    settleWaitTimer = null;
    settlePrev = null;
    settleHits = 0;
    settleDeadline = performance.now() + SETTLE_MAX_MS;
    settleTimer = setInterval(settleTick, SETTLE_SAMPLE_MS);
  }, SETTLE_SAMPLE_MS);
}

// THE TWO KINDS OF LOADING (owner decree 2026-08-12, and he named them
// himself: "1. vrsta je loading full screen / 2. vrsta je loading samo CUBE
// bez background" — lang-ok: owner quote).
//
// The distinction is about WHAT IS HAPPENING BEHIND, and nothing else:
//
//   LOADING_FULL — the PC's own picture is about to change in a way he must
//     not watch: windows climbing out of the taskbar, a grid being built, a
//     layout being torn apart. The overlay is opaque and the whole screen
//     becomes the animation. This is what the module was born for.
//
//   LOADING_CUBE — we are only WAITING FOR AN ANSWER, or watching something
//     open that is worth seeing open. His own example: while Chrome loads,
//     the cube spins over a transparent page, "so the user will know loading
//     is happening but will also SEE it opening in the background, that is,
//     that it is not finished yet". Hiding that would be a lie of omission —
//     there is nothing ugly to cover, only time to account for.
//
// The overlay is the FRONT in BOTH kinds and gates nothing behind it (his
// rule, restated 2026-08-12: "loading animacija je uvek FRONT i nikada ne
// treba da zavisi od nje ono što se dešava iza" — lang-ok: owner quote).
// Neither kind is on any code path the server waits for; the work runs to
// completion whether the overlay is up, bare, or absent.
//
// Both kinds still BLOCK taps. Bare is transparent, not inert: the operation
// really is in flight, and a second tap through it would fire a second
// action against a PC already working on the first.
//
// Every call site declares its kind EXPLICITLY and carries the matching
// `// LOADING: FULL|CUBE — why` comment, so the classification can be read
// off the code rather than inferred. Both halves are gated by
// tests/test_loading_kind.py, which also exists so the eventual move to the
// shared Loading Cube gadget has the full inventory in one grep.
const LOADING_FULL = "full";
const LOADING_CUBE = "cube";

function showLayLoading(text, kind) {
  layLoading.classList.toggle("cube-only", kind === LOADING_CUBE);
  layLoading.querySelector("span").textContent = text || "Working…";
  // A new operation — stop judging the old one; watch again when it answers.
  clearInterval(settleTimer);
  clearTimeout(settleStartTimer);
  clearInterval(settleWaitTimer);
  settleTimer = null;
  settleStartTimer = null;
  settleWaitTimer = null;
  clearTimeout(loadingTimer);
  loadingTimer = setTimeout(hideLayLoading, LOADING_MAX_MS);
  if (layLoadingOpen) return;
  layLoadingOpen = true;
  loadingSince = performance.now();
  layCubeHandle.nextFace();
  layLoading.classList.add("open");
  clearTimeout(cubeStopTimer);
  layCubeHandle.start(); // idempotent — safe even if the fade-out timer below never fired
}

function hideLayLoading(why) {
  clearTimeout(loadingTimer);
  loadingTimer = null;
  clearInterval(settleTimer);
  clearTimeout(settleStartTimer);
  clearInterval(settleWaitTimer);
  settleTimer = null;
  settleStartTimer = null;
  settleWaitTimer = null;
  settlePrev = null;
  if (!layLoadingOpen) return;
  layLoadingOpen = false;
  // The overlay leaving is the END of a return from an excursion — the last
  // hop, and the one he actually watches (task 203). Guarded because this
  // module is loaded by the audit harness too, with no connection.js in scope.
  if (typeof noteReturnDone === "function") {
    noteReturnDone(why || "backstop or an outside hide");
  }
  layLoading.classList.remove("open"); // CSS cross-fades it away
  // Keep spinning THROUGH the fade — a frozen cube during the fade-out is
  // exactly the stutter the smooth exit is meant to remove.
  clearTimeout(cubeStopTimer);
  cubeStopTimer = setTimeout(() => {
    if (layLoadingOpen || !layCubeHandle.isSpinning()) return;
    layCubeHandle.stop();
  }, LOADING_FADE_MS);
}

