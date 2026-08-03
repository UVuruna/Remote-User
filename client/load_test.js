// Load-order test for the client scripts — simulates the browser page load
// with DOM stubs. Catches script-killing load-time errors (TDZ, missing
// elements, typos) that a syntax check cannot see. Run before every client
// commit:
//   node client/load_test.js
//
// The app was split (god-file refactor) into 7 classic scripts that share
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
  body: { classList: { toggle: () => false } },
  addEventListener() {},
  hidden: false,
  activeElement: null,
};
global.window = { addEventListener() {}, innerWidth: 1280, innerHeight: 800 };
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
  "render.js",
  "input-geometry.js",
  "controls.js",
  "layouts.js",
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
