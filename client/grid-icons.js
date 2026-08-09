// WHAT SHAPE A LAYOUT IS — the drawn silhouette per (member count,
// arrangement, orientation), pure by design (no DOM, no socket, no state of
// its own) so its gate can run it whole (the client/view-anchor.js /
// cursor-shapes.js pattern).
//
// Owner request 2026-08-09 (task 164). A row in the layout list showed a name
// and nothing about its SHAPE, so a solo window, a two-split and a four-grid
// read identically until he opened one. This module turns what `layout_state`
// already carries — `grid`, `members`, `orient` — into a little diagram of the
// real arrangement, which is the same rule that made the creation panel draw
// its choices in the first place (owner 2026-08-07, delivering the catalogue
// as a SHEET OF DRAWINGS — UV/grid_variations.png — and saying what it was
// for: "GRID kada korisnik bira budu skice ... a ne tekstovi tipa 'GRID 2x1'").
// lang-ok: owner quote
// A shape is chosen, and now also RECOGNISED, by LOOKING — never by reading
// the word "3-left".
//
// Why drawn geometry and never a font glyph: the owner has already been
// shipped a font character that came out wrong on his own phone (the ✥ move
// handle rendered as a blunt cross, 2026-08-05). client/icons.js is the app's
// stroked 24×24 half of that rule and client/cursor-shapes.js is its canvas
// half; this is the third family and it is separate for a plain reason — a
// grid icon is a PARTITION of a box whose own aspect leans with the
// orientation, not a symbol on a fixed square.
//
// Geometry contract:
//   * The box leans with the orientation — 30×20 landscape, 20×30 portrait.
//     That is load-bearing, not decoration: only "2" changes its PARTITION
//     with orientation (the server splits a portrait region into rows and a
//     landscape one into columns, server/grids.py `_cells`), so on a fixed
//     square a portrait three and a landscape three would be drawn
//     pixel-for-pixel identical — the exact "choose by reading, not by
//     looking" failure the drawings exist to kill.
//   * Cells are listed in MEMBER ORDER, the same order server/grids.py
//     `_cells` returns and `LayoutRegistry.focus` places into. So cell k of
//     the picture is member k of the layout — which is what lets a panel point
//     at a window by pointing at its cell.
//   * A layout may hold FEWER live members than its grid has cells (a window
//     closed at the desk is pruned and the template is left alone, and
//     `focus` then places into the first N cells). The picture draws those
//     first N cells, because that is what the PC screen really looks like.
//
// The shapes mirror server/grids.py exactly; tests/test_grid_icons.py compares
// the two partitions number for number, so one can no longer drift from the
// other in silence.
//
// See client/__about/grid-icons.md.
"use strict";

// The OUTER BOX every drawing is made on, in viewBox units.
const GRID_ICON_BOX = { landscape: [30, 20], portrait: [20, 30] };
// Inset per side and the corner radius — the numbers the creation panel's
// chips have always been drawn with, kept identical so delegating to this
// module changed no pixel there.
const GRID_ICON_INSET = 1;
const GRID_ICON_RADIUS = 2;
const GRID_ICON_SOLO_RADIUS = 3;

// Cells as [x, y, w, h] on a 2×2 UNIT grid, in member order. "2" is the one
// shape whose partition genuinely depends on the orientation (his rule, 2026
// -08-07: two and four may change nothing but portrait/landscape, and a
// portrait region split down the middle would give two slivers).
const GRID_ICON_CELLS = {
  "2:landscape": [[0, 0, 1, 2], [1, 0, 1, 2]],
  "2:portrait": [[0, 0, 2, 1], [0, 1, 2, 1]],
  "3-top": [[0, 0, 2, 1], [0, 1, 1, 1], [1, 1, 1, 1]],
  "3-bottom": [[0, 0, 1, 1], [1, 0, 1, 1], [0, 1, 2, 1]],
  "3-left": [[0, 0, 1, 2], [1, 0, 1, 1], [1, 1, 1, 1]],
  "3-right": [[0, 0, 1, 1], [0, 1, 1, 1], [1, 0, 1, 2]],
  "4": [[0, 0, 1, 1], [1, 0, 1, 1], [0, 1, 1, 1], [1, 1, 1, 1]],
};

// Names this page knows, and the ones layouts made before 2026-08-07 carry.
const GRID_ICON_LEGACY = { "2x1": "2", "1x2": "2", "2x2": "4" };
const GRID_ICON_NAMES = ["2", "3-top", "3-bottom", "3-left", "3-right", "4"];
// How many windows each shape holds — the same table server/grids.py keeps.
const GRID_ICON_COUNTS = {
  "2": 2, "3-top": 3, "3-bottom": 3, "3-left": 3, "3-right": 3, "4": 4,
};
// The only sane shape for a bare count, identical to the server's own default
// (`LayoutRegistry._template_for`). It is what makes an UNKNOWN arrangement
// safe: a layout from a newer server naming a shape this page has never heard
// of still draws the right NUMBER of windows instead of throwing or lying
// about being solo.
const GRID_ICON_DEFAULT = { 2: "2", 3: "3-top", 4: "4" };

// The four arrangements a THREE may choose among — and the ONLY size that has
// a choice at all (owner 2026-08-07, read straight off his sheet: the 2 row
// and the 4 row each hold one drawing per orientation, the 3 row holds four).
// A two or a four can flip portrait/landscape and nothing else, because there
// is only one sane way to cut a region into two or into four.
const GRID_ICON_THREE = ["3-top", "3-bottom", "3-left", "3-right"];

// THE CATALOGUE — every shape this app can actually build, in both
// orientations, and it is exactly his sheet: 2 in one arrangement, 3 in four,
// 4 in one, per orientation. Solo (no grid at all) is one of them: it is what
// he most needs told apart from a grid at a glance. Six arrangements + solo =
// 7, and 14 with the orientations. The gate iterates exactly this.
const GRID_ICON_CATALOGUE = ["landscape", "portrait"].reduce((all, orient) => {
  all.push({ count: 1, grid: null, orient });
  GRID_ICON_NAMES.forEach((grid) =>
    all.push({ count: GRID_ICON_COUNTS[grid], grid, orient }));
  return all;
}, []);

/** WHICH arrangements this layout may be switched between — four for a three,
 *  NOTHING for anything else (owner 2026-08-07). It lives here, pure and
 *  gated, rather than being re-derived wherever a panel happens to need it:
 *  the asymmetry is the rule, and a page that re-derives it is a page that can
 *  offer him a choice which does not exist. */
function gridIconChoices(count, grid) {
  const shape = gridIconShape(count, grid);
  return shape.name && GRID_ICON_COUNTS[shape.name] === 3
    ? GRID_ICON_THREE.slice()
    : [];
}

function gridIconRound(v) {
  return Math.round(v * 1e4) / 1e4;   // kill float noise; the gate compares these
}

/** The viewBox of the drawing for an orientation: [w, h]. Anything that is
 *  not "portrait" is landscape — the same reading the whole protocol uses. */
function gridIconBox(orient) {
  return GRID_ICON_BOX[orient === "portrait" ? "portrait" : "landscape"].slice();
}

/** A stored or incoming grid name → one this module draws, or null for solo. */
function gridIconName(grid) {
  if (!grid) return null;
  const name = GRID_ICON_LEGACY[grid] || grid;
  return GRID_ICON_COUNTS[name] ? name : null;
}

/** Which shape to DRAW for a layout, given what `layout_state` said about it.
 *  Never throws — an unknown arrangement falls back to the default shape for
 *  the member count, and only a layout that really holds one window (or whose
 *  count is missing/nonsense) draws the solo rectangle. */
function gridIconShape(count, grid) {
  const n = typeof count === "number" && count > 0 ? Math.floor(count) : 0;
  let name = gridIconName(grid);
  // A named shape too SMALL for the members it is supposed to hold cannot be
  // the truth about this layout; the count wins, because the count is what he
  // can see on the screen.
  if (name && n > GRID_ICON_COUNTS[name]) name = null;
  if (!name && n >= 2) name = GRID_ICON_DEFAULT[Math.min(n, 4)];
  if (!name) return { name: null, cells: 1 };
  // Fewer live members than cells: the first N, which is where `focus` really
  // places them.
  return { name, cells: n > 0 ? Math.min(n, GRID_ICON_COUNTS[name]) : GRID_ICON_COUNTS[name] };
}

/** The rects of the drawing, in viewBox units, in MEMBER ORDER — each
 *  `{x, y, w, h, r}`. This is the surface a panel builds per-cell hit targets
 *  from, and the surface the gate measures. */
function gridIconRects(count, grid, orient) {
  const [vw, vh] = gridIconBox(orient);
  const inset = GRID_ICON_INSET;
  const shape = gridIconShape(count, grid);
  if (!shape.name) {
    return [{ x: inset, y: inset, w: vw - inset * 2, h: vh - inset * 2,
              r: GRID_ICON_SOLO_RADIUS }];
  }
  const key = shape.name === "2"
    ? "2:" + (orient === "portrait" ? "portrait" : "landscape")
    : shape.name;
  const unitW = vw / 2;
  const unitH = vh / 2;
  return GRID_ICON_CELLS[key].slice(0, shape.cells).map(([x, y, w, h]) => ({
    x: gridIconRound(x * unitW + inset),
    y: gridIconRound(y * unitH + inset),
    w: gridIconRound(w * unitW - inset * 2),
    h: gridIconRound(h * unitH - inset * 2),
    r: GRID_ICON_RADIUS,
  }));
}

/** One rounded rect as SVG path data — also valid for `new Path2D(d)`, so the
 *  same geometry can be stroked on a canvas without a second formula. */
function gridIconRectPath(rect) {
  const k = gridIconRound(Math.min(rect.r, rect.w / 2, rect.h / 2));
  const n = gridIconRound;
  const x = rect.x, y = rect.y, w = rect.w, h = rect.h;
  return `M${n(x + k)} ${n(y)}`
    + `H${n(x + w - k)}A${k} ${k} 0 0 1 ${n(x + w)} ${n(y + k)}`
    + `V${n(y + h - k)}A${k} ${k} 0 0 1 ${n(x + w - k)} ${n(y + h)}`
    + `H${n(x + k)}A${k} ${k} 0 0 1 ${n(x)} ${n(y + h - k)}`
    + `V${n(y + k)}A${k} ${k} 0 0 1 ${n(x + k)} ${n(y)}Z`;
}

/** The whole drawing as one path `d`. `cells` is an optional array of member
 *  indices — that is how a panel draws ONE cell lit and the rest dimmed
 *  without a second geometry. */
function gridIconPath(count, grid, orient, cells) {
  const rects = gridIconRects(count, grid, orient);
  const pick = Array.isArray(cells)
    ? cells.filter((i) => i >= 0 && i < rects.length).map((i) => rects[i])
    : rects;
  return pick.map(gridIconRectPath).join("");
}

/** The row's little diagram, ready to drop into `innerHTML`.
 *  `opts` — `{className, cell}`: `cell` (a member index) draws that one cell
 *  solid and the others faint, which is how the member chooser says "this
 *  window is THIS square" without a word. */
function gridIconSvg(count, grid, orient, opts) {
  const o = opts || {};
  const [vw, vh] = gridIconBox(orient);
  const cls = "lay-grid-ico" + (o.className ? " " + o.className : "");
  const head = `<svg class="${cls}" viewBox="0 0 ${vw} ${vh}" `
    + `fill="currentColor" aria-hidden="true">`;
  if (typeof o.cell !== "number") {
    return head + `<path d="${gridIconPath(count, grid, orient)}"/></svg>`;
  }
  const all = gridIconRects(count, grid, orient).map((_, i) => i);
  const rest = all.filter((i) => i !== o.cell);
  // Inline opacity rather than a class: this drawing is used inside panels
  // that style nothing of their own, and `currentColor` already carries the
  // theme — a class here would need CSS in a file this module does not own.
  return head
    + (rest.length
      ? `<path opacity="0.3" d="${gridIconPath(count, grid, orient, rest)}"/>`
      : "")
    + `<path d="${gridIconPath(count, grid, orient, [o.cell])}"/></svg>`;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    GRID_ICON_CATALOGUE, GRID_ICON_CELLS, GRID_ICON_COUNTS, GRID_ICON_NAMES,
    GRID_ICON_DEFAULT, GRID_ICON_THREE, gridIconBox, gridIconName,
    gridIconShape, gridIconChoices, gridIconRects, gridIconPath, gridIconSvg,
  };
}
