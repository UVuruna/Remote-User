// The GRID catalogue: which shapes exist, what each one looks like, and the
// one panel that asks him to choose between them.
//
// Split out of layouts.js on 2026-08-07 (THE STRUCTURE LAW) when the owner's
// grid sheet — two, three or four windows, with four arrangements for three
// (UV/grid_variations.png) — pushed that file past 1,000 lines.
//
// The SHAPES themselves left for client/grid-icons.js on 2026-08-09 (task
// 164): the layout list draws each row's shape now, so the partitions were
// about to have a third copy. That module is pure and its gate compares it to
// `server/grids.py` number for number — which is the check this file's old
// "if one changes, the other must" note asked for and never had.
//
// Loaded AFTER grid-icons.js (it delegates to it) and BEFORE layouts.js:
// `GRID_CELLS` is a const the list and the creation panel read at runtime.
"use strict";

// The owner's grid catalogue (2026-08-07, given as a drawing). Mirrors
// server/grids.py exactly — TWO, THREE or FOUR windows, and a THREE picks
// which edge its single window takes. Orientation decides what "2" means and
// nothing else (his rule: 2 and 4 may change only portrait/landscape).
const GRID_CELLS = { "2": 2, "3-top": 3, "3-bottom": 3, "3-left": 3, "3-right": 3, "4": 4 };
// The four arrangements a THREE may choose among — and the only size that has
// a choice (owner 2026-08-07). Held once, in the pure module, so a panel can
// never offer him a choice that does not exist: `gridIconChoices` answers it
// per layout, and this is the same list.
const GRID_THREE = GRID_ICON_THREE;
const GRID_LEGACY = { "2x1": "2", "1x2": "2", "2x2": "4" };
const gridOf = (g) => GRID_LEGACY[g] || (GRID_CELLS[g] ? g : null);

// The OUTER BOX and the shapes themselves moved to client/grid-icons.js on
// 2026-08-09 (owner request, task 164 — the layout LIST now draws each row's
// shape too). Everything below is a delegation, on purpose: the partitions
// were about to have a third copy (server/grids.py, here, and the list), and
// this file's own header already warns that two copies must be kept in step.
// The pure module is the one copy, and its gate compares it to the server's
// partition number for number — a drift nothing used to catch.
function orientBox(orient) {
  return gridIconBox(orient);
}

// A grid drawn as a real little diagram — the same shapes as his sheet, so
// the choice is made by LOOKING, never by reading "3-left". The partition
// (which cells exist) is fixed per grid — only "2" genuinely flips it — but
// the BOX it is drawn on leans with the orientation too: before that it was a
// fixed square, which left a landscape three and a portrait three drawn
// pixel-for-pixel identical — the exact "choose by reading, not by looking"
// failure the sheet exists to kill, one step removed.
function gridSketch(grid, orient) {
  return gridIconSvg(GRID_CELLS[gridOf(grid)] || 0, grid, orient);
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
  return gridIconSvg(1, null, orient);
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
    // LOADING: FULL — the server is merging windows into a grid
    showLayLoading("Building the grid…", LOADING_FULL);
    return;
  }
  const orient = dst.orient === "portrait" ? "portrait" : "landscape";
  layPanel.innerHTML = "";
  layPanel.hidden = false;
  const card = document.createElement("div");
  card.className = "lay-card card-columns";
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
    // LOADING: FULL — the server is merging windows into a grid
    showLayLoading("Building the grid…", LOADING_FULL);
  })));
  const actions = document.createElement("div");
  actions.className = "lay-actions";
  actions.appendChild(layChip("Cancel", false, openLayoutPicker));
  card.append(h, sub, row, actions);
  layPanel.appendChild(card);
}

