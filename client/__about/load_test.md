# Load-Order Test

**Script:** [Load-Order Test (script)](../load_test.js)

## Purpose

A dev-only Node harness that concatenates and executes the six client
scripts, in load order, against a stubbed DOM/WebSocket/window — catching
script-killing load-time errors (TDZ, references to elements that don't
exist, typos) that a plain syntax check cannot see. Run before every client
commit: `node client/load_test.js`.

## What it stubs

`stubElement()` returns one fake DOM node (event listeners as no-ops,
`classList`, `getContext` returning no-op 2D-context methods, etc.) reused for
every `getElementById` / `createElement` call. `global.document`,
`global.window`, `global.location` (`?token=test`), and a minimal
`global.WebSocket` are faked just enough for the scripts' top-level code to
run without throwing.

## How it runs the code

The `FILES` array — `state.js`, `render.js`, `input-geometry.js`,
`controls.js`, `gestures.js`, `connection.js` — is read from disk and joined
with `"\n"` into one source string, executed via `new Function(src)()` inside
the stubbed globals. This mirrors the real page: `index.html` loads the same
six files as classic `<script>` tags in the same order, which share one
global scope exactly like one concatenated file would (see
[State](state.md) Design Decisions). Exit 0 + "LOAD TEST PASSED" on a clean
run; exit 1 + the stack trace on any thrown error.

**`FILES` must be kept in sync with `index.html`'s `<script>` order by hand**
— nothing enforces the two lists match automatically; a reordering or a new
file added to one and not the other would go undetected until a real load
fails.

## Connections

### Uses

- [State](state.md), [Render](render.md), [Input Geometry](input-geometry.md),
  [Controls](controls.md), [Gestures](gestures.md), [Connection](connection.md)
  — the six files it loads and executes, in this order

### Used by

- The owner / CI, manually — `node client/load_test.js` before every client
  commit

## Design Decisions

- **Real execution, not a linter.** A stub DOM is cheap and catches the exact
  class of bug a syntax check misses: code that parses fine but throws the
  instant it runs (TDZ order, `getElementById` returning null then calling a
  method on it, etc.).
- **Concatenate-then-run, not one file per `new Function` call.** Running each
  file in its own `Function` scope would NOT reproduce the browser's actual
  behavior — the six scripts intentionally share one global scope (root
  Priority S / THE STRUCTURE LAW split, still zero behavior change), and a
  cross-file forward reference that is safe in the real page (function
  hoisting across `<script>` tags in one document) would falsely fail if each
  file ran in isolation.

## Build round R3 (2026-08-07) — themes

`theme.js` joined `FILES` in build round R3, in the position `index.html`
loads it (7th, right after `controls.js`). The `<body>` stub gained a
`dataset` object with it — `theme.js` writes `data-theme` / `data-fill` onto
the body at load, which is exactly the kind of load-time error this harness
exists to catch, and it caught it.
