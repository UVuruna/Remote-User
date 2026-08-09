// WHAT THE PC's CURSOR ACTUALLY LOOKS LIKE — the drawn shape per name, pure
// by design (no DOM, no canvas, no socket) so its gate can run it whole (the
// client/caret.js / view-anchor.js pattern).
//
// Owner request 2026-08-09 (task 142). DXGI capture never contains the
// pointer, so this page has always drawn it — as ONE fixed arrow. From the
// tablet that made a draggable window edge, a text box, a link and plain
// background look identical, which is the one job a cursor has. The server
// now NAMES the live system cursor (server/cursor_shape.py) on the `cursor`
// message it already sends, and this table turns that name into a silhouette.
//
// Why canvas PATHS and not glyphs: the owner has already been shipped a font
// character that came out wrong on his own phone (the ✥ move handle rendered
// as a blunt cross, 2026-08-05). A drawn path looks the same on every device.
// The whole app follows that rule — client/icons.js is its SVG half; this is
// the canvas half, separate because a cursor is filled-and-outlined geometry
// with a HOTSPOT, not a stroked 24×24 icon.
//
// Geometry contract, the same for every entry:
//   * CSS pixels, and the ORIGIN IS THE HOTSPOT — the pixel the cursor
//     points at. render.js translates to the commanded point and draws these
//     coordinates straight, so a shape can never drift off the point it
//     names. An arrow's hotspot is its TIP; a resize/move/wait/I-beam
//     hotspot is its CENTRE (that is where Windows puts them, and it is what
//     makes a resize arrow read as "this edge, right here").
//   * A shape is a list of CLOSED polygons, filled white and stroked black by
//     render.js — the treatment the old arrow already used, and the reason it
//     stays legible over both a white document and a dark editor. Holes are
//     wound the other way (canvas fills nonzero), which is how the ring of
//     `no` is a ring.
//
// A name with no entry here — an application's own cursor (`custom`), or a
// name from a NEWER server — draws the arrow, unchanged. That fallback is the
// honest answer: a near-miss shape would promise him a grabbable edge that
// is not there.
//
// See client/__about/cursor-shapes.md.
"use strict";

const CURSOR_FALLBACK = "arrow";

// --- small builders (run once, at load) -----------------------------------

function cursorRound(v) {
  return Math.round(v * 1e4) / 1e4; // kill float noise; the gate compares these
}

function cursorRotate(poly, deg) {
  const a = (deg * Math.PI) / 180;
  const c = Math.cos(a);
  const s = Math.sin(a);
  return poly.map(([x, y]) => [cursorRound(x * c - y * s),
                               cursorRound(x * s + y * c)]);
}

function cursorScaled(poly, k, dx, dy) {
  return poly.map(([x, y]) => [cursorRound(x * k + dx), cursorRound(y * k + dy)]);
}

function cursorBox(x0, y0, x1, y1) {
  return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
}

// An arc BAND (outer edge out, inner edge back) — one closed polygon.
// Angles in degrees, canvas convention: 0 = right, 90 = down.
function cursorArc(cx, cy, ri, ro, a0, a1, steps) {
  const pts = [];
  const at = (r, t) => {
    const a = ((a0 + (a1 - a0) * t) * Math.PI) / 180;
    pts.push([cursorRound(cx + r * Math.cos(a)), cursorRound(cy + r * Math.sin(a))]);
  };
  for (let i = 0; i <= steps; i++) at(ro, i / steps);
  for (let i = steps; i >= 0; i--) at(ri, i / steps);
  return pts;
}

// A full ring as TWO polygons wound in opposite directions — the inner one
// becomes a hole under canvas's nonzero fill, so the ring is a ring and not
// a disc. (One closed band would leave a radial seam the stroke draws.)
function cursorRing(cx, cy, ri, ro, steps) {
  const circle = (r, dir) => {
    const pts = [];
    for (let i = 0; i < steps; i++) {
      const a = (dir * i * 2 * Math.PI) / steps;
      pts.push([cursorRound(cx + r * Math.cos(a)), cursorRound(cy + r * Math.sin(a))]);
    }
    return pts;
  };
  return [circle(ro, 1), circle(ri, -1)];
}

// --- the shapes -----------------------------------------------------------

// The arrow, unchanged since the first release — the fallback for every name
// this table does not know, so its coordinates are also the promise that
// "nothing recognised" still looks exactly like it always did.
const CURSOR_ARROW = [
  [0, 0], [0, 16.5], [3.6, 13.3], [6, 19], [8.7, 17.9], [6.3, 12.4], [11.2, 11.9],
];

// One double-headed arrow, centred on its hotspot; the other three resize
// cursors are THIS, rotated. Built from one source so the four can never
// drift apart in weight or length — the set only works if they read as
// siblings at a glance on a shrunken 4K stream.
const CURSOR_DOUBLE = [
  [-10, 0], [-5, -5], [-5, -1.8], [5, -1.8], [5, -5], [10, 0],
  [5, 5], [5, 1.8], [-5, 1.8], [-5, 5],
];

// The hourglass, also used at half size as the `app-starting` badge.
const CURSOR_HOURGLASS = [
  [-5, -9], [5, -9], [5, -6.5], [1.2, 0], [5, 6.5], [5, 9],
  [-5, 9], [-5, 6.5], [-1.2, 0], [-5, -6.5],
];

// The pointing hand: index finger up (its tip IS the hotspot, as on Windows),
// three knuckles stepping down to the right, thumb bulging left.
const CURSOR_HAND = [
  [0, 0], [2.2, 2.2], [2.2, 8],
  [3.6, 6.8], [5.6, 6.8], [5.6, 9.2],
  [5.8, 8.2], [7.8, 8.2], [7.8, 10.6],
  [8, 9.8], [10, 9.8], [10, 12.2],
  [10, 17.5], [7.6, 21], [0, 21], [-3.2, 18.6], [-4.4, 14],
  [-6.8, 10.6], [-5.8, 9], [-3.6, 10.4], [-2.2, 8.6], [-2.2, 2.2],
];

// The question mark of `help`: an open hook curling from lower-left over the
// top and back down to the middle, then a stem and a dot under it.
const CURSOR_HELP_HOOK = cursorArc(13.6, 7, 1.3, 3.1, 180, 430, 16);
const CURSOR_HELP_END = [
  cursorRound(13.6 + 2.2 * Math.cos((70 * Math.PI) / 180)),
  cursorRound(7 + 2.2 * Math.sin((70 * Math.PI) / 180)),
];

// name -> the polygons to draw, hotspot at (0, 0).
const CURSOR_SHAPES = {
  arrow: [CURSOR_ARROW],
  // The I-beam of a text field — serifs top and bottom so a thin bar cannot
  // be mistaken for a caret or a window border.
  ibeam: [[
    [-3, -10], [3, -10], [3, -8.6], [1, -8.6], [1, 8.6], [3, 8.6], [3, 10],
    [-3, 10], [-3, 8.6], [-1, 8.6], [-1, -8.6], [-3, -8.6],
  ]],
  hand: [CURSOR_HAND],
  "size-we": [CURSOR_DOUBLE],
  "size-ns": [cursorRotate(CURSOR_DOUBLE, 90)],
  "size-nwse": [cursorRotate(CURSOR_DOUBLE, 45)],
  "size-nesw": [cursorRotate(CURSOR_DOUBLE, -45)],
  // The four-way move arrow, traced as ONE outline (four overlaid arrows
  // would stroke a cross through their own middle). Each head's barbs stop
  // just SHORT of the neighbouring head's base — 4 against 4.5 — so the
  // outline never crosses itself; overshooting punched four holes where the
  // arms meet, under both fill rules.
  move: [[
    [0, -10], [4, -4.5], [2, -4.5], [2, -2], [4.5, -2], [4.5, -4],
    [10, 0], [4.5, 4], [4.5, 2], [2, 2], [2, 4.5], [4, 4.5],
    [0, 10], [-4, 4.5], [-2, 4.5], [-2, 2], [-4.5, 2], [-4.5, 4],
    [-10, 0], [-4.5, -4], [-4.5, -2], [-2, -2], [-2, -4.5], [-4, -4.5],
  ]],
  wait: [CURSOR_HOURGLASS],
  cross: [[
    [-1.2, -10], [1.2, -10], [1.2, -1.2], [10, -1.2], [10, 1.2], [1.2, 1.2],
    [1.2, 10], [-1.2, 10], [-1.2, 1.2], [-10, 1.2], [-10, -1.2], [-1.2, -1.2],
  ]],
  // "Not here": the ring, plus a bar whose ends stop exactly on the inner
  // circle so the outline meets it instead of crossing it.
  no: [...cursorRing(0, 0, 6, 9, 32),
       cursorRotate(cursorBox(-5.8, -1.5, 5.8, 1.5), 45)],
  "up-arrow": [[
    [0, 0], [5, 7], [2, 7], [2, 20], [-2, 20], [-2, 7], [-5, 7],
  ]],
  // Busy-but-usable: the arrow it still behaves like, with the hourglass at
  // half size beside it. Same tip, so the hotspot rule does not change.
  "app-starting": [CURSOR_ARROW, cursorScaled(CURSOR_HOURGLASS, 0.55, 13.5, 10)],
  help: [CURSOR_ARROW, CURSOR_HELP_HOOK,
         cursorBox(CURSOR_HELP_END[0] - 0.9, CURSOR_HELP_END[1],
                   CURSOR_HELP_END[0] + 0.9, CURSOR_HELP_END[1] + 2.9),
         cursorBox(CURSOR_HELP_END[0] - 0.9, CURSOR_HELP_END[1] + 4,
                   CURSOR_HELP_END[0] + 0.9, CURSOR_HELP_END[1] + 5.8)],
};

/** The polygons to draw for `name`, with the shape's HOTSPOT landing exactly
 *  on (x, y). An unknown, missing or null name is the arrow — see the header:
 *  a wrong shape would lie about what the pixel under it does. */
function cursorPolys(name, x, y) {
  const shape = CURSOR_SHAPES[name] || CURSOR_SHAPES[CURSOR_FALLBACK];
  return shape.map((poly) => poly.map(([px, py]) => [px + x, py + y]));
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { CURSOR_SHAPES, CURSOR_FALLBACK, cursorPolys };
}
