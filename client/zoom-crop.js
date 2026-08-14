// THE ZOOM IS A CROP, AND THE CROP IS GEOMETRY (T76, owner report
// 2026-08-14). In translation: "why is downscaling done even when the picture
// is zoomed — when we zoom on the phone we are enlarging that downscaled
// resolution so the picture is blurry, even though the whole screen does not
// need to be sent then either, because we are in a slice just like in layout
// mode". Everything a focused layout already had — the encoder crop,
// `stream_region`, the page mapping the video onto that rect, the decode
// ceiling sized by it — existed whole; only the PINCH was never wired into
// it, and its `viewport` message was discarded outright in H.264 mode.
//
// Two rules live here, both pure so the gate can run them whole (the
// view-anchor.js / decode-caps.js pattern — a rule the gate can only read as
// text is a rule nothing proves):
//
//   1. THE FLOOR. Inside a layout the crop may narrow further and may NEVER
//      widen past the layout's own region — a wider crop would stream windows
//      the layout deliberately does not show, and would break the model that
//      makes `layout_state`'s region trustworthy at all.
//   2. THE SETTLE. Every region change rebuilds this client's ffmpeg and the
//      picture blinks once, so the rect is sent only when the gesture has
//      STOPPED. That is an observation and not an estimate: constraint 15
//      forbids guessing how long ANOTHER program needs, and this measures the
//      owner's own hand — no pointer down, and the view transform identical
//      across two samples. The threshold is the give-up point of that
//      observation; a gesture that never stops never sends, however long it
//      runs.
"use strict";

/** The visible rect widened by a MARGIN and then held to its floor — in that
 *  order, so the margin can never be what widens the crop past a layout.
 *  `visible` and `floor` are monitor-normalized {x, y, w, h}; on the desktop
 *  the floor is the whole frame. An empty intersection returns the floor
 *  itself: a rect that has drifted off the layout entirely (a stale one from
 *  the layout just left) must fall back to what the layout frames, never to
 *  nothing. */
function zoomFloorRect(visible, floor, margin) {
  const mx = visible.w * margin;
  const my = visible.h * margin;
  const x1 = Math.max(floor.x, visible.x - mx);
  const y1 = Math.max(floor.y, visible.y - my);
  const x2 = Math.min(floor.x + floor.w, visible.x + visible.w + mx);
  const y2 = Math.min(floor.y + floor.h, visible.y + visible.h + my);
  if (x2 <= x1 || y2 <= y1) return { ...floor };
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

/** How far one rect moved from another — the largest edge move. A missing
 *  side is a whole change (the full frame is a different picture). */
function zoomRectDelta(a, b) {
  if (!a || !b) return 1;
  return Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y),
                  Math.abs(a.w - b.w), Math.abs(a.h - b.h));
}

/** One tick of the settle watcher.
 *
 *  `prev` = {sample, changedAt} — what the last tick saw and when it last saw
 *  something DIFFERENT. `ev` = {now, pointersDown, rect, settleMs}.
 *  Returns {sample, changedAt, settled}. `settled` is true only on the tick
 *  where the hand has been off the glass and the transform unmoved for the
 *  whole threshold; the caller sends then, and only then. */
function zoomSettleStep(prev, ev) {
  const moved = ev.pointersDown || !prev.sample ||
    zoomRectDelta(prev.sample, ev.rect) > 0.0005;
  if (moved) return { sample: ev.rect, changedAt: ev.now, settled: false };
  return {
    sample: prev.sample,
    changedAt: prev.changedAt,
    settled: ev.now - prev.changedAt >= ev.settleMs,
  };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { zoomFloorRect, zoomRectDelta, zoomSettleStep };
}
