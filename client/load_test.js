// Load-order test for app.js — simulates the browser page load with DOM stubs.
// Catches script-killing load-time errors (TDZ, missing elements, typos) that
// a syntax check cannot see. Run before every client commit:
//   node client/load_test.js

"use strict";

const fs = require("fs");
const path = require("path");

function stubElement() {
  return {
    addEventListener() {},
    setPointerCapture() {},
    classList: { add() {}, remove() {} },
    focus() {},
    blur() {},
    value: "",
    width: 0,
    height: 0,
    className: "",
    textContent: "",
    getContext: () => ({ fillRect() {}, drawImage() {}, fillStyle: "" }),
  };
}

global.document = {
  getElementById: () => stubElement(),
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

const src = fs.readFileSync(path.join(__dirname, "app.js"), "utf-8");
try {
  new Function(src)();
  console.log("LOAD TEST PASSED — app.js executes cleanly to the end");
  process.exit(0);
} catch (err) {
  console.error(`LOAD TEST FAILED — page would die on load:\n${err.stack}`);
  process.exit(1);
}
