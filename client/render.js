// Canvas rendering, view transform, and dual-mode (H.264 MSE / JPEG) frame
// decode. Part of the app.js split — loads after state.js. See
// client/__about/render.md.
"use strict";

// --- View transform -------------------------------------------------------

// The image is aspect-fitted into the FULL canvas, centered — no reserved
// margins (owner 2026-08-02: the pointer sits under the finger, so the old
// offset margins are gone and the image touches the screen edges).
function computeBaseRect() {
  if (!monitor.w) return;
  const aspect = monitor.w / monitor.h;
  const w = Math.min(canvas.width, canvas.height * aspect);
  const h = w / aspect;
  baseRect = { x: (canvas.width - w) / 2, y: (canvas.height - h) / 2, w, h };
}

function drawnRect() {
  return {
    x: baseRect.x * view.scale + view.tx,
    y: baseRect.y * view.scale + view.ty,
    w: baseRect.w * view.scale,
    h: baseRect.h * view.scale,
  };
}

// The rect the view may ever show, in unscaled base-canvas px: the whole
// monitor on the desktop, the layout's own region in layout focus. Panning
// never brings anything outside it into sight.
function viewBounds() {
  if (!viewLocked()) return baseRect;
  const r = layoutRegion;
  return {
    x: baseRect.x + r.x * baseRect.w,
    y: baseRect.y + r.y * baseRect.h,
    w: r.w * baseRect.w,
    h: r.h * baseRect.h,
  };
}

// The HOME transform = maximum zoom-out. On the desktop that is the plain
// aspect-fitted monitor (scale 1); in layout focus it is the region fitted
// into the FULL canvas — a matching-aspect region touches all four screen
// edges (owner 2026-08-02). A region NARROWER than the canvas letterboxes,
// and where it sits between the bars is the layout's own `pos` (owner decree
// 2026-08-09, the Move handle's fourth round — the anchor acts HERE, on the
// screen he sees; the math is client/view-anchor.js so its gate can run it
// whole). Pinch zoom works in BOTH modes and can never go below home (owner
// 2026-08-04 — layout focus is no longer a hard lock, it just starts and
// bottoms out at its own framing); the anchored home is also the fitted-view
// wall the zoom bottoms out at, and past it the slack is gone, so the anchor
// is moot while zoomed in.
let viewHome = { scale: 1, tx: 0, ty: 0 };

function computeViewHome() {
  if (!viewLocked() || !monitor.w) {
    viewHome = { scale: 1, tx: 0, ty: 0 };
    return;
  }
  viewHome = fitAnchorView(canvas.width, canvas.height, viewBounds(),
                           layoutAnchorPos());
}

// Snap all the way back out (layout switch, monitor switch, stream reset).
function resetViewHome() {
  computeViewHome();
  view = { ...viewHome };
  redraw();
}

function clampView() {
  const f = viewHome;
  if (view.scale <= f.scale) {
    view = { ...f };
    return;
  }
  view.scale = Math.min(view.scale, f.scale * ZOOM_MAX);
  const s = view.scale;
  const R = viewBounds();
  // Where the bounds rect sits when fully zoomed out — the zoomed view must
  // always cover it, so no letterbox/desktop ever creeps in at an edge.
  const hx = R.x * f.scale + f.tx;
  const hy = R.y * f.scale + f.ty;
  view.tx = Math.min(Math.max(view.tx, hx + R.w * f.scale - (R.x + R.w) * s), hx - R.x * s);
  view.ty = Math.min(Math.max(view.ty, hy + R.h * f.scale - (R.y + R.h) * s), hy - R.y * s);
}

// What the canvas is CLEARED with before the PC's picture is drawn on it —
// the theme's own page colour, not a literal (build round R3). It shows
// wherever the stream does not reach: before the first frame, in the
// letterbox around a layout region, and behind a panel's scrim. Cached,
// because `redraw` runs at frame rate and `getComputedStyle` has no business
// on a hot path; client/theme.js refreshes it whenever the look changes.
let canvasBg = "#0f172a";

function setCanvasBackdrop(color) {
  if (color) canvasBg = color;
}

function redraw() {
    ctx.fillStyle = canvasBg;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  const D = drawnRect();
  // ONCE. This line was here TWICE from 0.0.349 until 2026-08-09 — a scripted
  // edit that meant to touch two different draw sites hit this one function
  // twice instead. The picture therefore rose by DOUBLE the caret's shortfall
  // whenever the keyboard was open, while `kbShift` (and so every touch
  // coordinate) still carried the single value: the row he was typing in went
  // out of sight and his finger no longer landed where the picture said. That
  // is his "tastatura je sakrila kursor" of 2026-08-09, and it was mine.
  D.y -= caretRise;  // the picture rises, the canvas does not

  ctx.save();
  if (viewLocked()) {
    // In layout focus the phone shows ONLY the framed region. Once a layout
    // carries its own aspect ratio the region no longer fills the screen, and
    // what is left over must stay the app's own background — NEVER the
    // desktop behind it (owner 2026-08-03). The PC cursor is clamped to the
    // very same rect (input-geometry.js `toRemoteClamped`), so nothing out
    // there is reachable either: the layout stays one window, whole.
    ctx.beginPath();
    ctx.rect(D.x + layoutRegion.x * D.w, D.y + layoutRegion.y * D.h,
             layoutRegion.w * D.w, layoutRegion.h * D.h);
    ctx.clip();
  }
  if (streamMode === "h264") {
    if (video.readyState >= 2) ctx.drawImage(video, D.x, D.y, D.w, D.h);
  } else {
    if (baseBitmap) ctx.drawImage(baseBitmap, D.x, D.y, D.w, D.h);
    if (view.scale > 1 && detailBitmap) {
      ctx.drawImage(
        detailBitmap,
        D.x + detailRegion.x * D.w,
        D.y + detailRegion.y * D.h,
        detailRegion.w * D.w,
        detailRegion.h * D.h
      );
    }
  }
  drawCursor(D);
  ctx.restore();
}

// The PC pointer, drawn client-side (screen capture never contains it).
// Screen-fixed size, independent of zoom.
//
// The SHAPE is the one the PC is really showing (owner request 2026-08-09,
// task 142): the server names the live system cursor and the name rides the
// `cursor` message, so a resize cursor at a window edge tells him the edge is
// grabbable — the whole reason a cursor changes at all. The geometry lives in
// client/cursor-shapes.js, pure so its gate can run it whole; the ORIGIN of
// every shape is its hotspot, which is why the translate below is unchanged
// and correct for all of them. The white fill + black outline + soft shadow
// stay exactly as they were: that treatment is what keeps the pointer legible
// over a white document AND a dark editor, so every new shape inherits it.
//
// The name lives HERE and not on `cursorPos`, because the finger writes that
// object itself while steering (gestures.js / input-geometry.js move the
// pointer optimistically, before the PC answers) — carrying the shape on it
// would drop back to an arrow on every touch, which is precisely when he is
// reaching for the edge he wants to grab.
let cursorShapeName;

function drawCursor(D) {
  if (!cursorPos) return;
  if (cursorPos.x < 0 || cursorPos.x > 1 || cursorPos.y < 0 || cursorPos.y > 1) return;
  ctx.save();
  ctx.translate(D.x + cursorPos.x * D.w, D.y + cursorPos.y * D.h);
  ctx.scale(devicePixelRatio, devicePixelRatio);
  ctx.beginPath();
  // Every polygon of the shape into ONE path: filled nonzero (so a
  // reverse-wound polygon is a hole, e.g. the ring of `no`) and stroked once.
  cursorPolys(cursorShapeName, 0, 0).forEach((poly) => {
    poly.forEach(([px, py], i) => (i ? ctx.lineTo(px, py) : ctx.moveTo(px, py)));
    ctx.closePath();
  });
  ctx.shadowColor = "rgba(0, 0, 0, 0.55)";
  ctx.shadowBlur = 3;
  ctx.fillStyle = "#fff";
  ctx.fill();
  ctx.shadowBlur = 0;
  ctx.strokeStyle = "#000";
  ctx.lineWidth = 1.25;
  ctx.stroke();
  ctx.restore();
}

// The full viewport for the CURRENT orientation, remembered across keyboard
// openings. The soft keyboard shrinks the viewport (the WebView is resized, or
// visualViewport reports less — depending on the device), and re-fitting the
// picture into that shorter box squeezed the whole layout (owner report
// 2026-08-03). The width is the tell: it never changes when the keyboard
// appears, only on rotation — so a width change resets the remembered height,
// and otherwise the tallest height ever seen for this width IS the full one.
let fullView = { w: 0, h: 0 };

function updateViewport() {
  const vv = window.visualViewport;
  const w = vv ? vv.width : window.innerWidth;
  const visibleH = vv ? vv.height : window.innerHeight;
  // HOW TALL THE KEYBOARD IS, asked of whoever can actually answer.
  //
  // `innerHeight - visualViewport.height` is the browser's own answer and it
  // is RIGHT only while the window is resized by the IME. Under edge-to-edge
  // on targetSdk 35 Android stops doing that — `adjustResize` is declared in
  // our manifest and quietly does nothing — so this subtraction returns 0 with
  // the keyboard wide open. That zero is why the caret rule, rebuilt across
  // five rounds, never lifted anything: it was never given a keyboard to lift
  // over (owner, 2026-08-09, for the sixth time and rightly furious).
  //
  // The shell reads the real `WindowInsets.ime()` and pushes it here in CSS
  // px. The browser's own number stays as the fallback for a dev browser and
  // for any device where the window really is resized; the LARGER of the two
  // wins, because a zero from either must never win over a real measurement.
  const kbSelf = vv ? Math.max(0, window.innerHeight - vv.height - vv.offsetTop) : 0;
  const kb = Math.max(kbSelf, imeHeight);
  if (Math.abs(w - fullView.w) > 1) fullView = { w, h: visibleH }; // rotation
  else fullView.h = Math.max(fullView.h, visibleH);
  // THE KEYBOARD'S OWN HEIGHT NEVER MOVES ANYTHING (owner decree 2026-08-07,
  // withdrawing his own 2026-08-03 request after living with it). The canvas
  // used to be LIFTED by the keyboard's height so its bottom edge sat just
  // above the keys. It reads well on paper and is wrong in the hand: the row
  // he is typing into is almost never at the very bottom of the PC screen, so
  // lifting the picture by a whole keyboard drove the text he was watching
  // off the top — "izbaci tekst koji se kuca ... iz vidokruga" (lang-ok: owner
  // quote). What CAN move the picture is the caret's own SHORTFALL, computed
  // at the end of this function and almost always zero — the keyboard covers
  // what it covers, and only a row that would actually be buried is rescued.
  const h = fullView.h;
  canvas.style.transform = "";
  // NOTE: do NOT blur the keyboard field on a keyboard-height drop. Switching
  // to the IME's voice/mic input transiently shrinks the keyboard, and a blur
  // there tore down the field mid-dictation (had to re-tap Keys to get back —
  // owner report 2026-07-22). Focus is only released by the Keys toggle now.
  const root = document.documentElement.style;
  root.setProperty("--kb", `${kb}px`);
  root.setProperty("--vtop", `${vv ? vv.offsetTop : 0}px`);
  canvas.style.width = `${w}px`;
  canvas.style.height = `${h}px`;
  canvas.width = Math.round(w * devicePixelRatio);
  canvas.height = Math.round(h * devicePixelRatio);
  computeBaseRect();
  computeViewHome(); // rotation / keyboard resize re-fits the layout's region
  clampView();       // ...and keeps whatever zoom the user pinched into
  // ONLY THE PICTURE, ONLY IF NEEDED, ONLY BY THE SHORTFALL — the rule lives
  // in client/caret.js and is almost always answered with 0. The canvas is
  // never transformed: that is what carried the navy filler with it in the
  // 2026-08-03 attempt he rejected.
  //
  // LAST, and deliberately so (2026-08-09): the rule is measured against the
  // rect the picture is really DRAWN into, so it has to run after the canvas
  // has been resized and the home transform re-fitted — otherwise a rotation
  // would grade the caret against the previous orientation's picture.
  // `drawnRect()` is the un-risen rect (redraw subtracts `caretRise` from its
  // own copy at draw time), so feeding it back in here cannot compound.
  const pic = drawnRect();
  caretRise = caretLift({
    caret: pcCaret,
    picture: pic,
    canvasHeight: canvas.height,
    keyboardHeight: kb * devicePixelRatio,
  });
  // The inverse mapping for every finger: a touch on a risen picture must
  // still land on the PC pixel under it (state.js `toCanvasPx`).
  kbShift = caretRise / devicePixelRatio;
  reportKeyboard(kb, kbSelf, pic);
  redraw();
  scheduleViewport();
}
window.addEventListener("resize", updateViewport);
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", updateViewport);
  window.visualViewport.addEventListener("scroll", updateViewport);
}

// THE SHELL'S PUSH — the page's half of the keyboard-height pipe, and the one
// number that decides whether any of this can work at all.
//
// It is placed HERE, beside `updateViewport`, ON PURPOSE. It used to live at
// the bottom of this file among the MSE starve-recovery code, and on
// 2026-08-09 a revert of that streaming block took this function with it as
// collateral — the commit message never mentioned the keyboard, nothing else
// referenced `window.__imeHeight`, and `imeHeight` silently stayed 0 for
// another release. Physical adjacency to code with a different lifetime is
// what cost that; the receiver belongs next to its only consumer.
//
// The shell calls it whenever the IME opens, closes or resizes — see
// `updateViewport` for why the page cannot measure this for itself.
window.__imeHeight = (px) => {
  const next = Math.max(0, Number(px) || 0);
  // Say it in the log whatever it is, including a zero: "the shell reached us
  // and reported nothing" and "the shell never reached us" are two different
  // faults and only one of them can be fixed on the phone.
  if (next !== imeHeight) kbReportNext = true;
  imeHeight = next;
  updateViewport();
};

// ONE LINE PER KEYBOARD EVENT, in his own server log (task 150). Every round
// of this bug argued about numbers nobody could see; this prints them from HIS
// device, and it discriminates between the ways it can still be wrong:
//
//   ime=0 browser=0 ............ the shell is not reaching the page at all
//   ime=780 caret=unknown ...... the PC cannot see the caret in that app
//   ime=780 caret=0.951 rise=0 . the arithmetic is still wrong
//   ime=780 caret=0.951 rise=311 fixed, and hand-checkable against pic/kbTop
//
// It fires on every keyboard OPEN and every CLOSE — never once per page load,
// which is what the previous attempt did: one line, at the moment the pipe
// first carried a number, and then silence for the whole session where the
// evidence was. A close is worth a line too, because `ime=0 browser=0` is only
// observable if a zero can reach the log at all.
let kbWasOpen = false;
let kbReportNext = false;   // the shell pushed a new inset: say so, even a 0
let kbReportTimer = null;
let kbReportState = null;

function reportKeyboard(kb, kbSelf, pic) {
  const worthSaying = (kb > 0) !== kbWasOpen || kbReportNext;
  kbWasOpen = kb > 0;
  kbReportNext = false;
  kbReportState = { kb, kbSelf, pic };
  if (!worthSaying) return;
  // SETTLE FIRST. Android ANIMATES the keyboard in and fires the inset
  // listener on every frame of it, so reporting each one would bury the answer
  // under twenty half-open keyboards — and would print a rise computed against
  // a keyboard that was still moving. The timer is restarted by every further
  // change, so one open costs exactly one line, with the settled numbers.
  if (kbReportTimer) clearTimeout(kbReportTimer);
  kbReportTimer = setTimeout(() => {
    kbReportTimer = null;
    const s = kbReportState;
    send({ type: "client_log", text:
      `[keyboard] ime=${Math.round(imeHeight)} browser=${Math.round(s.kbSelf)} ` +
      `caret=${pcCaret ? pcCaret.y.toFixed(3) : "unknown"} ` +
      `pic=${Math.round(s.pic.y)}+${Math.round(s.pic.h)} ` +
      `kbTop=${Math.round(canvas.height - s.kb * devicePixelRatio)} ` +
      `rise=${Math.round(caretRise)} dpr=${devicePixelRatio}` });
  }, KB_REPORT_SETTLE_MS);
}

// The first fit. It runs AFTER the two `let`s above, because `reportKeyboard`
// reads them and a `let` in its temporal dead zone is a thrown ReferenceError
// on the very first paint — the page would die on load.
updateViewport();

// --- Region streaming -----------------------------------------------------

function currentViewport() {
  if (view.scale <= 1) return { x: 0, y: 0, w: 1, h: 1 };
  const D = drawnRect();
  let x1 = Math.max(0, -D.x / D.w);
  let y1 = Math.max(0, -D.y / D.h);
  let x2 = Math.min(1, (canvas.width - D.x) / D.w);
  let y2 = Math.min(1, (canvas.height - D.y) / D.h);
  const mx = (x2 - x1) * VIEWPORT_MARGIN;
  const my = (y2 - y1) * VIEWPORT_MARGIN;
  x1 = Math.max(0, x1 - mx);
  y1 = Math.max(0, y1 - my);
  x2 = Math.min(1, x2 + mx);
  y2 = Math.min(1, y2 + my);
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

function scheduleViewport() {
  if (streamMode !== "jpeg") return; // region streaming is a JPEG-path concept
  if (viewportTimer) return;
  viewportTimer = setTimeout(() => {
    viewportTimer = null;
    const vp = currentViewport();
    const d = Math.max(
      Math.abs(vp.x - lastSentViewport.x), Math.abs(vp.y - lastSentViewport.y),
      Math.abs(vp.w - lastSentViewport.w), Math.abs(vp.h - lastSentViewport.h)
    );
    if (d > 0.01) {
      lastSentViewport = vp;
      send({ type: "viewport", ...vp });
    }
  }, VIEWPORT_THROTTLE_MS);
}

async function onFrame(buffer) {
  const r = new Float32Array(buffer, 0, 4);
  const bitmap = await createImageBitmap(new Blob([new Uint8Array(buffer, 16)]));
  const isFull = r[0] <= 0.001 && r[1] <= 0.001 && r[2] >= 0.999 && r[3] >= 0.999;
  if (isFull) {
    if (baseBitmap) baseBitmap.close();
    baseBitmap = bitmap;
  } else {
    if (detailBitmap) detailBitmap.close();
    detailBitmap = bitmap;
    detailRegion = { x: r[0], y: r[1], w: r[2], h: r[3] };
  }
  redraw();
}

// --- H.264 decode (MSE) ---------------------------------------------------
// The server sends one continuous fragmented-MP4 byte stream; chunks are
// appended in arrival order. currentTime chases the buffered end to stay
// live, and played-out history is trimmed so memory stays flat.

const video = document.getElementById("vid");
let mediaSource = null;
let sourceBuffer = null;
let mseQueue = [];
let rafId = null;

function initMse(codec) {
  teardownMse();
  const ms = new MediaSource();
  mediaSource = ms;
  video.src = URL.createObjectURL(ms);
  ms.addEventListener("sourceopen", () => {
    if (ms !== mediaSource) return; // torn down before it opened (fast reconnect)
    URL.revokeObjectURL(video.src);
    sourceBuffer = ms.addSourceBuffer(`video/mp4; codecs="${codec}"`);
    sourceBuffer.addEventListener("updateend", onMseUpdateEnd);
    pumpMse();
  }, { once: true });
  video.play().catch(() => {}); // muted+playsinline is allowed; retried on touch
  renderLoop();
}

function teardownMse() {
  mseQueue = [];
  if (rafId) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
  if (sourceBuffer) {
    sourceBuffer.removeEventListener("updateend", onMseUpdateEnd);
    sourceBuffer = null;
  }
  mediaSource = null;
  video.removeAttribute("src");
  video.load();
}

function pumpMse() {
  if (!sourceBuffer || sourceBuffer.updating || !mseQueue.length) return;
  try {
    sourceBuffer.appendBuffer(mseQueue.shift());
  } catch (err) {
    // Decoder/buffer wedged (e.g. quota, codec hiccup) — never freeze
    // silently: drop the connection, auto-reconnect brings a fresh stream.
    console.error("MSE append failed:", err);
    setStatus("disconnected", `Stream error: ${err.name} — reconnecting…`);
    if (ws) ws.close();
  }
}

// WHY 10 fps FEELS SMOOTHER THAN 60 (owner 2026-08-07, task 83 — and it is
// the right question: "koja je svrha slati toliko velik bitrate i mnogo
// frejmova ako to dovodi do suprotnog efekta").
//
// The hypothesis, read out of the six lines below rather than guessed: the
// catch-up is a SEEK. An MSE live stream plays at 1x from wherever it started,
// so every hiccup adds latency permanently; when the drift passes half a
// second, `currentTime` is thrown forward — which flushes the decoder and
// costs a visible stutter. More fps at native 4K means more bytes than the
// link drains, means the drift reaches the threshold sooner, means that
// stutter repeats. Lower fps never reaches it at all.
//
// This counts what actually happens instead of arguing about it: how far
// behind the picture runs, and how often it is thrown forward. Reported to the
// SERVER log every LIVE_REPORT_S while streaming, so his own log answers the
// question on the next session he runs — no panel, nothing for him to do.
let liveSeeks = 0;
let liveStarves = 0;
let liveDriftMax = 0;
let liveDriftMin = 0;
let liveReportAt = 0;

function reportLiveDrift(behind) {
  liveDriftMax = Math.max(liveDriftMax, behind);
  // The MINIMUM matters more than the maximum and the first version of this
  // line did not record it: `peak` was a plain `Math.max`, so through two
  // solid minutes of a frozen picture at -11 s it printed `peak=0.00s`. The
  // measurement was blind to the exact failure it was written to find.
  liveDriftMin = Math.min(liveDriftMin, behind);
  const now = performance.now();
  if (!liveReportAt) { liveReportAt = now; return; }
  if (now - liveReportAt < LIVE_REPORT_S * 1000) return;
  send({ type: "client_log", text:
    `[live] behind=${behind.toFixed(2)}s peak=${liveDriftMax.toFixed(2)}s ` +
    `low=${liveDriftMin.toFixed(2)}s jumps=${liveSeeks} ` +
    `starves=${liveStarves} in ${Math.round((now - liveReportAt) / 1000)}s` });
  liveReportAt = now;
  liveSeeks = 0;
  liveStarves = 0;
  liveDriftMax = 0;
  liveDriftMin = 0;
}

// REVERTED to the pre-2026-08-09 rule, the same night my replacement shipped.
// The starve case is REAL — his log proved currentTime overtaking the buffer
// and pinning at -11 s — but my fix for it seeks, a seek flushes the decoder,
// and it went out beside two other changes of mine into a screen he could not
// use. Nothing can be attributed while three things move at once. This comes
// back ALONE, with him watching, after the app is usable again.
function onMseUpdateEnd() {
  const b = video.buffered;
  if (b.length) {
    const end = b.end(b.length - 1);
    const behind = end - video.currentTime;
    reportLiveDrift(behind);
    if (behind > LIVE_MAX_BEHIND_S) {
      liveSeeks++;
      video.currentTime = end - LIVE_TARGET_BEHIND_S; // fell behind (jank, slow link) — jump
    }
    if (end - b.start(0) > BUFFER_KEEP_S * 2 && sourceBuffer && !sourceBuffer.updating) {
      sourceBuffer.remove(0, end - BUFFER_KEEP_S);
    }
    if (video.paused) video.play().catch(() => {});
  }
  pumpMse();
}

function renderLoop() {
  if (rafId) return;
  const step = () => {
    rafId = requestAnimationFrame(step);
    redraw();
  };
  rafId = requestAnimationFrame(step);
}
