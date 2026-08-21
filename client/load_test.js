// Load-order test for the client scripts — simulates the browser page load
// with DOM stubs. Catches script-killing load-time errors (TDZ, missing
// elements, typos) that a syntax check cannot see. Run before every client
// commit:
//   node client/load_test.js
//
// The app was split (god-file refactor) into 12 classic scripts that share
// ONE global scope in the browser (multiple <script> tags evaluated in
// document order = the same semantics as one concatenated file). FILES below
// must list them in the EXACT order index.html loads them in — concatenating
// and running them as one `new Function` body reproduces that shared-scope
// behavior faithfully.

"use strict";

const fs = require("fs");
const path = require("path");

function stubElement() {
  return {
    addEventListener() {},
    setPointerCapture() {},
    classList: { add() {}, remove() {}, toggle() {} },
    focus() {},
    blur() {},
    appendChild() {},
    remove() {},
    click() {},
    querySelectorAll: () => [],
    files: [],
    style: {},
    dataset: {},
    value: "",
    width: 0,
    height: 0,
    className: "",
    textContent: "",
    innerHTML: "",
    getContext: () => ({
      fillRect() {}, drawImage() {}, fillStyle: "",
      // redraw() clips to the layout region while a layout is focused
      save() {}, restore() {}, beginPath() {}, rect() {}, clip() {},
    }),
  };
}

global.document = {
  getElementById: () => stubElement(),
  createElement: () => stubElement(),
  querySelectorAll: () => [],
  documentElement: { style: { setProperty() {} } },
  // `dataset`: theme.js writes data-theme / data-fill onto <body> at load
  // (build round R3) — the cached look, applied before the socket says
  // anything, which is the whole point of caching it.
  // `appendChild` because chrome.js now parks the mini-radial's own element on
  // <body> at load (2026-08-11). The real body has always had it; the stub was
  // simply narrower than the page, which made this test fail on a file it was
  // meant to be proving.
  body: {
    classList: { toggle: () => false }, dataset: {},
    appendChild() {}, addEventListener() {},
  },
  addEventListener() {},
  hidden: false,
  activeElement: null,
};
global.window = { addEventListener() {}, innerWidth: 1280, innerHeight: 800 };
// controls.js listens for orientation changes at load time (order_port,
// 0.0.166) — the stub was missing this and the load test was failing on
// HEAD too (found 2026-08-05).
global.matchMedia = () => ({ matches: false, addEventListener() {} });
// chrome.js reads `--corner` through getComputedStyle at load (MINI_FACE,
// 2026-08-15); an empty answer makes every token fall back to its default.
global.getComputedStyle = () => ({ getPropertyValue: () => "" });
global.devicePixelRatio = 2;
global.location = { search: "?token=test", host: "test:1" };
global.WebSocket = class WebSocket {
  static get OPEN() { return 1; }
  static get CONNECTING() { return 0; }
  static get CLOSED() { return 3; }
  constructor() { this.readyState = 0; }
  send() {}
  close() {}
};

// Must match index.html's <script> order exactly.
const FILES = [
  "state.js",
  "type-queue.js",
  "caret.js",
  "view-anchor.js",
  "cursor-shapes.js",
  // The Claude panels' pure half — the five models, the five thinking levels
  // and the mode ring (owner ballot verdict 2026-08-11). Loaded early, like
  // every other pure module, and read by claude-panels.js far below.
  "claude-state.js",
  // Also before render.js: the live-edge decision table + regulator
  // computeViewHome's neighbour, `applyLiveDecision`, calls (task 151,
  // 2026-08-10).
  "live-clock.js",
  "render.js",
  "input-geometry.js",
  "icons.js",
  "sets.js",
  "voice.js",
  // The invisible keyboard field's diff/caret rules, split off controls.js
  // (owner report 2026-08-13) — loaded before it, exactly as index.html does.
  "kb-sync.js",
  "controls.js",
  // THE LIST HAD DRIFTED FROM index.html, and the drift hid exactly the files
  // being worked on (found 2026-08-09, tasks 166–168): chrome.js, loading.js
  // and layout-create.js are all loaded by the page and none of the three was
  // listed here, so a load-time error in the creation wizard — the whole point
  // of this test — would have passed green. This file's own header says the
  // order must match index.html EXACTLY; it does again.
  // The cube's own motion (2026-08-17), split out of loading.js — loaded
  // before BOTH of its callers: update-banner.js right below (a small
  // badge) and loading.js further down (the full-screen overlay).
  "cube.js",
  // This round's new modules, in index.html's own order (2026-08-11): the
  // update banner split out of controls.js (task 207), and the window-offer
  // chip (task 202) — both loaded before chrome.js exactly as the page does.
  "update-banner.js",
  "window-offer.js",
  "chrome.js",
  "theme.js",
  "panels.js",
  "quality.js",
  // Both read panels.js's `ghostClickArmor` AT LOAD — exactly the class of
  // reference this test exists to catch (owner ballot verdict 2026-08-11).
  "claude-panels.js",
  "phone-panel.js",
  "set-editor.js",
  "region.js",
  "notify.js",
  "clipboard.js",
  "hold-gesture.js",
  // grids.js reads grid-icons.js AT LOAD (`GRID_THREE`), so the order here is
  // the order index.html loads them in — and both are listed, because a
  // load-time reference is exactly what this test exists to catch.
  // settle-motion.js is loading.js's pure stillness metric (task 194) and
  // the page loads it first — a load-time reference the test must see.
  "settle-motion.js",
  "loading.js",
  "grid-icons.js",
  "grids.js",
  "layouts.js",
  // The per-layout ⚙ sheet and the panels it opens, split off layouts.js on
  // 2026-08-09 (task 175). It reads `HOLD_DRAG_SLOP` from that file AT LOAD,
  // which is exactly the class of reference this test exists to catch, so the
  // order here is the order index.html loads them in.
  "layout-settings.js",
  // The creation wizard, split off layouts.js on 2026-08-08. It reads that
  // file's panel vocabulary at load, so it is listed straight after it.
  "layout-create.js",
  "gamepad.js",
  "gestures.js",
  "connection.js",
];

const src = FILES.map((f) => fs.readFileSync(path.join(__dirname, f), "utf-8")).join("\n");
try {
  new Function(src)();
  console.log(`LOAD TEST PASSED — ${FILES.join(", ")} execute cleanly to the end`);
  process.exit(0);
} catch (err) {
  console.error(`LOAD TEST FAILED — page would die on load:\n${err.stack}`);
  process.exit(1);
}
