// HOW FAR THE PICTURE RISES FOR THE SOFT KEYBOARD — and it is almost always
// zero. Pure geometry: no DOM, no socket, no state of its own, so its gate can
// run it whole (the pattern client/voice.js was split out for).
//
// HIS PROBLEM, both halves of it, in his own words. When he types into a box at
// the BOTTOM of the PC screen the keyboard covers the very row he is typing
// into. When the box is at the TOP, lifting carries that row off the screen
// instead: "izbaci tekst koji se kuca iz vidokruga". So neither rule can be
// fixed in advance — "always lift" and "never lift" are each wrong half the
// time, which is why the 2026-08-03 lift was withdrawn on 2026-08-07 and
// `kbShift` has been 0 since. His answer, 2026-08-07: "najoptimalnije rešenje
// bilo bi da naš program prepozna gde se nalazi, koja je pozicija na ekranu,
// kursora koji kuca."
//
// AND ONLY THE PICTURE MOVES. This is the half a naive implementation gets
// wrong, and he sent a screenshot to say so: the previous attempt moved
// EVERYTHING, "zaključno sa ovim delom koji nije deo naše aplikacije" — the
// navy filler above and below, which exists because a layout narrower or
// shorter than the phone letterboxes. "Poenta je da tastatura kada pomera sa
// offsetom ne pomera taj prazan deo već pomera samo vidljivi ekran gde se
// nalazi aplikacija, i to samo ako ima potrebe."
// In this client that is exactly what a change to the VIEW TRANSFORM does: the
// canvas and the colour behind it do not move at all; only what is drawn
// through the transform rises. The filler is the canvas backdrop showing where
// the picture is not — it cannot travel with the picture, because it is not
// part of it. That is the whole reason the lift is expressed as canvas pixels
// added to `view.ty` and never as a CSS transform on an element.
//
// --- CARET_LIFT_START (tests/test_caret_lift.py extracts this block) --------

// A caret sitting exactly ON the keyboard's edge is unreadable — a descender
// and the row's own padding are already under it. Small, because every pixel
// of lift is a pixel of the PC screen leaving at the top.
const CARET_LIFT_MARGIN_PX = 14;

// The caret must not be pushed against the very top edge either: a text row is
// read with a line or two of context above it, and a caret at y=0 reads as
// "the picture jumped" rather than "the row was rescued".
const CARET_TOP_MARGIN_PX = 24;

/** How far to raise the PICTURE, in canvas pixels. Zero means: do nothing,
 *  which is the answer whenever the caret is already clear of the keyboard —
 *  and that is most of the time, which is the point.
 *
 *  `caret` is the typing caret in MONITOR-NORMALIZED coordinates
 *  ({x, y, w, h}, 0..1 of the displayed monitor) as the PC reported it, or
 *  null when the PC could not find one — some apps expose no caret at all, and
 *  an app that cannot say where it is typing must not be guessed at.
 *  `view` is the live transform ({scale, tx, ty}); `unknownMode` is his
 *  Settings switch for the no-caret case: "cover" (do nothing — the behaviour
 *  he has now) or "lift" (the old whole-keyboard lift, for apps he knows sit
 *  at the bottom). "cover" is the default because it is the one he chose to
 *  live with when the caret was not available at all.
 */
function caretLift({ caret, view, canvasHeight, keyboardHeight, unknownMode }) {
  // No keyboard on screen: there is nothing to be covered BY. This is checked
  // first so that a stale caret can never lift a picture nobody is typing on.
  if (!(keyboardHeight > 0)) return 0;
  const keyboardTop = canvasHeight - keyboardHeight;
  if (keyboardTop <= 0) return 0; // a keyboard taller than the screen: give up

  if (!caret) {
    // The PC could not say. Never guess a position — obey his switch.
    if (unknownMode !== "lift") return 0;
    // The old rule, kept only as HIS fallback: lift by what is covered, and
    // never past the top margin.
    return Math.max(0, Math.min(keyboardHeight, canvasHeight - CARET_TOP_MARGIN_PX));
  }

  const scale = view.scale;
  const caretTop = caret.y * scale + view.ty;
  const caretBottom = (caret.y + caret.h) * scale + view.ty;

  // ONLY IF NEEDED. The caret is already above the keyboard, with room to
  // read: the picture does not move, and this is the ordinary case.
  const shortfall = caretBottom + CARET_LIFT_MARGIN_PX - keyboardTop;
  if (shortfall <= 0) return 0;

  // ONLY BY THE SHORTFALL — never by the keyboard's full height, which is what
  // made the 2026-08-03 attempt intolerable. And never so far that the row we
  // are rescuing leaves at the top: if the strip above the keyboard is shorter
  // than the caret needs, we lift as much as it can take and the rest stays
  // covered. Lifting past that would trade a covered row for a missing one.
  const headroom = caretTop - CARET_TOP_MARGIN_PX;
  return Math.max(0, Math.min(shortfall, headroom));
}

// --- CARET_LIFT_END --------------------------------------------------------

if (typeof module !== "undefined" && module.exports) {
  module.exports = { caretLift, CARET_LIFT_MARGIN_PX, CARET_TOP_MARGIN_PX };
}
