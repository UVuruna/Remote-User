// A ROW MUST NOT STEAL THE SCROLL — the one row activator of this page.
//
// Owner report 2026-08-11 (task 227b) fixed this for the creation panel's
// rows, IN that panel's own file. Owner report 2026-08-15 is the same bug in
// the notification-voice card's language list, and his ruling is about the
// PROCESS rather than that list: "ne mogu da ti dam primedbu na problem koji
// ste implementirali a da ga sredite samo na jednom mestu a ne svuda gde se
// on provlači u aplikaciji" (lang-ok: owner quote). A rule that lives inside
// one panel's file is a rule the next panel's author never sees — so it is a
// MODULE now, exactly as `hold-gesture.js` became one for the same reason.
//
// The mechanism, unchanged: `keepFocus` (controls.js) is right for every
// ordinary BUTTON on this page and wrong for a row inside a list that
// scrolls. It calls `e.preventDefault()` on pointerdown to guarantee touch
// activation (the file picker and the IME need it), and that same call is
// what stops the browser from ever recognising the touch as a scroll — every
// drag that started on a row became a selection instead of a scroll. Its
// `pointerup` fires regardless of travel too, so even a drag that DID scroll
// still selected the row the finger happened to lift over.
//
// A row therefore never calls `preventDefault` (the browser is free to start
// scrolling) and decides on RELEASE, by travel alone, reusing `pressVerdict`
// from hold-gesture.js rather than re-deriving the rule (constraint 9: one
// activator, never a second copy that can drift) — a tap that stayed under
// `ROW_TAP_SLOP` selects; a drag past it, or already past it when it ends,
// never does. The pointercancel rescue keeps the Android edge-gesture case of
// constraint 9 alive: a stolen tap under slop still counts.
//
// WHERE IT BELONGS: anything a finger might legitimately start a scroll on —
// every row of every list, and every control that sits INSIDE a scrolling
// card. Ordinary buttons that are not in a scroll container keep `keepFocus`,
// and anything needing transient user activation (a file picker, the IME)
// MUST keep it — that is the one thing this function deliberately gives up.
//
// tests/test_row_tap.py extracts exactly the block between the two markers
// below and runs it, whole, in node against `hold-gesture.js`'s real
// `pressVerdict` — never a re-typed copy of the logic. Move the markers WITH
// the code if this ever moves; a gate that silently starts extracting stale
// text is worse than no gate. The same gate also sweeps the client for row
// builders that went back to `keepFocus`, because the defect the owner
// reports is never one call site.
"use strict";

// ROW_TAP_GATE_START
const ROW_TAP_SLOP = 12; // CSS px — a still finger's own wander, no more
function keepRowTap(el, onTap) {
  let down = null; // {id, x, y}
  el.addEventListener("pointerdown", (e) => {
    down = { id: e.pointerId, x: e.clientX, y: e.clientY };
  });
  el.addEventListener("pointerup", (e) => {
    if (!down || e.pointerId !== down.id) return;
    const at = { x: e.clientX, y: e.clientY };
    if (pressVerdict(down, at, 0, ROW_TAP_SLOP, Infinity) === PRESS_TAP) onTap(e);
    down = null;
  });
  el.addEventListener("pointercancel", (e) => {
    const at = { x: e.clientX, y: e.clientY };
    if (down && e.pointerId === down.id &&
        pressVerdict(down, at, 0, ROW_TAP_SLOP, Infinity) === PRESS_TAP) onTap(e);
    down = null;
  });
}
// ROW_TAP_GATE_END

if (typeof module !== "undefined" && module.exports) {
  module.exports = { keepRowTap, ROW_TAP_SLOP };
}
