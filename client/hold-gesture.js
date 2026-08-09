// WHEN A PRESS IS A HOLD, A DRAG OR A TAP — the arming rule the layout list's
// drag gesture lives by, pure by design (no DOM, no timer, no state of its
// own) so its gate can run it whole (the client/view-anchor.js and
// client/cursor-shapes.js pattern).
//
// Owner report 2026-08-09, task 162: he held his finger on a layout row
// without moving it, meaning to pick it up and drop it on another one, and the
// layout simply OPENED. The gesture was not missing — it had shipped whole
// (client drag block, `layout_merge` / `layout_reorder`, the registry's
// `merge`/`reorder`), and the panel's own subtitle promises it in words. It
// was DEFEATED in its first millisecond: the row's `pointermove` handler
// cleared the hold timer on ANY movement, with zero tolerance. A finger
// resting on a capacitive digitizer never stands still — the reported point is
// the CENTROID of a contact patch that breathes with the pulse and spreads as
// the finger settles — so a pixel of wander is not the user changing his mind,
// it is the hardware, and the 380 ms timer essentially never survived a real
// hold.
//
// THE PROCESS LESSON, which is the bigger half. Three hundred and fifty lines
// below that code, client/layouts.js already documents THE SAME CLASS OF BUG
// under its own heading — "A DOUBLE TAP IS TWO TAPS, NOT TWO TOUCHES" — where
// the Move handle read a tap-then-drag as a double tap and re-centred the
// region under his finger. It was fixed with exactly this idea, a slop
// constant (`MOVE_TAP_SLOP`), on the SAME DAY the hold gesture was written
// with none. The lesson went into a comment, and a comment is only read by
// somebody already looking at that line. So the rule is a MODULE now, and it
// has a gate (tests/test_hold_gesture.py) that drives it with a realistic
// jitter SEQUENCE: every gesture in this product that must tell a tap from a
// drag from a hold asks this one function, and a rule about jitter is never
// again proven by one call.
"use strict";

// The three things a press can be. Named, because the callers read like
// prose with them and a typo in a bare string is silent.
const PRESS_TAP = "tap";    // still inside both limits — a tap if it ends now
const PRESS_HOLD = "hold";  // stood still long enough — pick the row up
const PRESS_DRAG = "drag";  // travelled past the slop — a scroll or a carry

/** How far the finger has travelled from where it landed, in CSS px.
 *  Straight-line distance on purpose: a per-axis test lets a 9+9 px diagonal
 *  through, which is 12.7 px of real travel and no longer a still finger. */
function pressTravel(down, at) {
  return Math.hypot(at.x - down.x, at.y - down.y);
}

/** What this press IS at the instant it is asked.
 *
 *  `down` / `at` are `{x, y}` in CSS px (where the finger landed, where it is
 *  now), `elapsedMs` is how long it has been down, `slop` is the travel a
 *  RESTING finger is allowed and `holdMs` is how long standing still takes to
 *  become a hold.
 *
 *  Both limits are the caller's, not this module's: the layout list holds a
 *  row for 380 ms inside 12 px, and the next gesture that needs this will
 *  want its own numbers. Only the RULE lives here.
 *
 *  PRESS_TAP answers two questions with one word, and deliberately: a press
 *  that has not moved and has not lasted is a tap if it ends here AND still a
 *  candidate hold if it continues. There is no third state to keep in step.
 *  PRESS_DRAG is terminal — once the finger has travelled it cannot become a
 *  hold by standing still again, because the travel already belonged to
 *  something else (a scroll, a carry, a swipe the system is about to steal). */
function pressVerdict(down, at, elapsedMs, slop, holdMs) {
  if (pressTravel(down, at) > slop) return PRESS_DRAG;
  return elapsedMs >= holdMs ? PRESS_HOLD : PRESS_TAP;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { pressTravel, pressVerdict, PRESS_TAP, PRESS_HOLD, PRESS_DRAG };
}
