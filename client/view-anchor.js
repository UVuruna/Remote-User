// WHERE THE LETTERBOXED PICTURE SITS ON THE PHONE — the fit-and-anchor math,
// pure by design (no DOM, no socket, no state of its own) so its gate can run
// it whole (the client/caret.js pattern).
//
// Owner decree 2026-08-09, the Move handle's FOURTH round. Three rounds moved
// WINDOWS along the free axis of the PC monitor — a screen he never sees —
// and every gate measured window rects there, so every round shipped green
// while his tablet stayed centred: the server crops the layout's region and
// streams the SAME picture wherever the windows sit inside the monitor. The
// position that exists FOR HIM is where the picture lands between the
// letterbox bars on his screen. So the server now always centres the windows
// (server/grids.py), `pos` rides `layout_state` to the phone unchanged, and
// THIS is the one place it acts: 0 = flush to the top/left of the slack axis,
// 0.5 = centred, 1 = flush bottom/right. Portrait full-width example: pos 0
// puts the app at the TOP with the empty space BELOW — what he dragged the
// handle up for, three rounds ago.
//
// Only one axis ever has slack — the fit pins the other — so a single
// fraction covers both orientations, exactly as it did on the server while
// the server still (wrongly) owned it.
"use strict";

/** The HOME transform for a region fitted into the canvas: `region` is
 *  {x, y, w, h} in unscaled base-canvas px (render.js `viewBounds()`), the
 *  result is {scale, tx, ty} for the view. `pos` anchors the fitted picture
 *  along the free axis; anything that is not a number (an old server, an
 *  entry with no pos) is the centre, and out-of-range values stop at the
 *  edges — an anchor past the edge would re-invent the letterbox creep
 *  `clampView` exists to prevent. */
function fitAnchorView(canvasW, canvasH, region, pos) {
  const p = typeof pos === "number" ? Math.min(1, Math.max(0, pos)) : 0.5;
  const s = Math.min(canvasW / region.w, canvasH / region.h);
  return {
    scale: s,
    tx: (canvasW - region.w * s) * p - region.x * s,
    ty: (canvasH - region.h * s) * p - region.y * s,
  };
}

/** The rect the region is DRAWN into at home — the geometry the owner judges,
 *  and therefore the surface the gate drives. Computed THROUGH fitAnchorView,
 *  never as a second formula: one source, so the transform render.js uses and
 *  the rect the gate proves can never disagree. */
function fitAnchorRect(canvasW, canvasH, region, pos) {
  const v = fitAnchorView(canvasW, canvasH, region, pos);
  return {
    x: region.x * v.scale + v.tx,
    y: region.y * v.scale + v.ty,
    w: region.w * v.scale,
    h: region.h * v.scale,
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { fitAnchorView, fitAnchorRect };
}
