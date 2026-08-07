// The GRID catalogue: which shapes exist, what each one looks like, and the
// one panel that asks him to choose between them.
//
// Split out of layouts.js on 2026-08-07 (THE STRUCTURE LAW) when the owner's
// grid sheet — two, three or four windows, with four arrangements for three —
// pushed that file past 1,000 lines. It mirrors `server/grids.py` shape for
// shape; if one changes, the other must.
//
// Loaded BEFORE layouts.js: `GRID_CELLS` is a const the list and the creation
// panel read at runtime.
"use strict";

// The owner's grid catalogue (2026-08-07, given as a drawing). Mirrors
// server/grids.py exactly — TWO, THREE or FOUR windows, and a THREE picks
// which edge its single window takes. Orientation decides what "2" means and
// nothing else (his rule: 2 and 4 may change only portrait/landscape).
const GRID_CELLS = { "2": 2, "3-top": 3, "3-bottom": 3, "3-left": 3, "3-right": 3, "4": 4 };
const GRID_THREE = ["3-top", "3-bottom", "3-left", "3-right"];
const GRID_LEGACY = { "2x1": "2", "1x2": "2", "2x2": "4" };
const gridOf = (g) => GRID_LEGACY[g] || (GRID_CELLS[g] ? g : null);

// The OUTER BOX every sketch is drawn on: wide for landscape, tall for
// portrait (owner round 3, 2026-08-07, re-reading his own sheet — the
// landscape column draws EVERY shape, 2/3/4, in a wide box, the portrait
// column in a tall one). A 2x2 unit grid, same as the cell coordinates below
// use, so a cell's `[x, y, w, h]` in units maps straight onto it.
function orientBox(orient) {
  return orient === "portrait" ? [20, 30] : [30, 20];
}

// A grid drawn as a real little diagram — the same shapes as his sheet, so
// the choice is made by LOOKING, never by reading "3-left". The partition
// (which cells exist) is fixed per grid — only "2" genuinely flips it — but
// the BOX it is drawn on now leans with the orientation too: before this it
// was a fixed square, which left a landscape three and a portrait three
// drawn pixel-for-pixel identical — the exact "choose by reading, not by
// looking" failure the sheet exists to kill, one step removed.
function gridSketch(grid, orient) {
  const cells = {
    "2": orient === "portrait" ? [[0, 0, 2, 1], [0, 1, 2, 1]]
                               : [[0, 0, 1, 2], [1, 0, 1, 2]],
    "3-top": [[0, 0, 2, 1], [0, 1, 1, 1], [1, 1, 1, 1]],
    "3-bottom": [[0, 0, 1, 1], [1, 0, 1, 1], [0, 1, 2, 1]],
    "3-left": [[0, 0, 1, 2], [1, 0, 1, 1], [1, 1, 1, 1]],
    "3-right": [[0, 0, 1, 1], [0, 1, 1, 1], [1, 0, 1, 2]],
    "4": [[0, 0, 1, 1], [1, 0, 1, 1], [0, 1, 1, 1], [1, 1, 1, 1]],
  }[grid] || [];
  const [vw, vh] = orientBox(orient);
  const unitW = vw / 2, unitH = vh / 2;
  const rects = cells.map(([x, y, w, h]) =>
    `<rect x="${x * unitW + 1}" y="${y * unitH + 1}" width="${w * unitW - 2}" height="${h * unitH - 2}" rx="2"/>`).join("");
  return `<svg class="lay-grid-ico" viewBox="0 0 ${vw} ${vh}" fill="currentColor">${rects}</svg>`;
}


// A grid choice is a picture, not a word (owner 2026-08-07 — he sent a sheet
// of drawings, not a list of names).
function gridChip(grid, orient, selected, onTap) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "lay-chip lay-grid" + (selected ? " sel" : "");
  el.innerHTML = gridSketch(grid, orient);
  keepFocus(el, onTap);
  return el;
}

// "Only one" has no cells to split — the drawing is a single rectangle
// filling the same tall/wide `orientBox` every other sketch uses: a solo
// window has nothing else to show, so the box shape is the only picture
// available for its orientation (owner round 2, 2026-08-07).
function soloSketch(orient) {
  const [vw, vh] = orientBox(orient);
  return `<svg class="lay-grid-ico" viewBox="0 0 ${vw} ${vh}" fill="currentColor">` +
    `<rect x="1" y="1" width="${vw - 2}" height="${vh - 2}" rx="3"/></svg>`;
}

// A drawing with a small caption under it — used where the picture alone
// still needs a word to anchor it (a plain "1" square, or which of the two
// orientation pictures is "Portrait"): the DRAWING is what is tapped and
// what carries the meaning, the caption only echoes it (owner round 2,
// 2026-08-07: "budu skice ... a ne tekstovi tipa 'GRID 2x1'").
function shapeChip(sketchHtml, caption, selected, onTap) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "lay-chip lay-grid lay-shape" + (selected ? " sel" : "");
  el.innerHTML = sketchHtml + `<span>${caption}</span>`;
  keepFocus(el, onTap);
  return el;
}

// Orientation is exactly the COLUMN of his sheet (LANDSCAPE | PORTRAIT) — so
// it too is picked as a picture: the same shape drawn once per orientation,
// side by side, the chosen one lit. `sketchFor(orient)` draws whatever is
// being oriented — a grid's own cells, or a solo rectangle.
function orientChips(sketchFor, current, onPick) {
  return ["landscape", "portrait"].map((o) => shapeChip(
    sketchFor(o), o === "portrait" ? "Portrait" : "Landscape",
    current === o, () => onPick(o)));
}



// Dropping one layout onto another. 1+1 and 1+3 have exactly one possible
// shape, so nothing is asked; 1+2 becomes a THREE, and a three has four
// arrangements — that is the one case where he gets the choice (owner
// 2026-08-07).
function mergeLayouts(source, target) {
  const dst = layouts[target];
  const size = (GRID_CELLS[gridOf(dst && dst.grid)] || 1) + 1;
  if (size !== 3) {
    send({ type: "layout_merge", source, target });
    closeLayoutPanel();
    showLayLoading("Building the grid…");
    return;
  }
  const orient = dst.orient === "portrait" ? "portrait" : "landscape";
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card";
  const h = document.createElement("h2");
  h.textContent = "Three windows";
  const sub = document.createElement("p");
  sub.className = "lay-sub";
  sub.textContent = "Where does the single window go?";
  const row = document.createElement("div");
  row.className = "lay-row";
  GRID_THREE.forEach((g) => row.appendChild(gridChip(g, orient, false, () => {
    send({ type: "layout_merge", source, target, grid: g });
    closeLayoutPanel();
    showLayLoading("Building the grid…");
  })));
  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Cancel", false, openLayoutPicker));
  card.append(h, sub, row, actions);
  layPanel.appendChild(card);
}

