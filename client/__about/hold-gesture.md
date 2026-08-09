# Hold Gesture

**Script:** [Hold Gesture (script)](../hold-gesture.js) ·
**Folder:** [client](../___client.md)

## Purpose

WHEN A PRESS IS A HOLD, A DRAG OR A TAP — one pure rule, asked by every gesture
in this page that has to tell the three apart. Today that is the layout list's
row drag ([Layouts](layouts.md)): hold a row and it is picked up, drop it on
another and the two become a grid, drop it in a gap and the list only re-orders.

## Why it exists (owner report 2026-08-09, task 162)

He held his finger on a layout row without moving it, meaning to pick it up, and
the layout simply OPENED. The gesture was not missing — the client drag block,
`layout_merge`, `layout_reorder` and the registry's `merge`/`reorder` all
shipped on 2026-08-07, and the panel's own subtitle promises it in words. It was
defeated on the phone, twice over:

1. **The root cause.** The row's `pointermove` handler cleared the 380 ms hold
   timer on ANY movement, with zero tolerance. A capacitive digitizer does not
   report "the finger" — it reports the CENTROID of a contact patch that pulses
   with the blood in the fingertip and spreads as the finger settles, so a
   resting finger wanders a pixel or three every frame. The timer essentially
   never survived a real hold.
2. **The second, independent path.** `keepFocus` ([Controls](controls.md))
   fires its tap on `pointerup` with no duration test, and its stolen-tap
   rescue fires for any `pointercancel` under 18 px of travel — while Chrome on
   Android hands out that cancel at ~8 dp, the moment it decides the touch is a
   scroll. Both land inside the rescue window, so even with the timer fixed the
   row would still have opened.

**The process lesson, which is the bigger half.** Three hundred and fifty lines
below the broken code, [Layouts](layouts.md) already documented THE SAME CLASS
OF BUG under its own heading — "A DOUBLE TAP IS TWO TAPS, NOT TWO TOUCHES",
where the Move handle read a tap-then-drag as a double tap — and fixed it with
exactly this idea, a slop constant, on the SAME DAY this gesture was written
with none. The lesson went into a comment, and a comment is read only by
somebody already looking at that line. So the rule is a module with a gate now,
and `MOVE_TAP_SLOP` is DERIVED from `HOLD_DRAG_SLOP`: one digitizer asking one
question has one number.

## Key Functions

- `pressVerdict(down, at, elapsedMs, slop, holdMs)` → `"tap"` / `"hold"` /
  `"drag"`. Both limits are the caller's, not this module's — only the RULE
  lives here. `"tap"` answers two questions with one word, deliberately: a
  press that has not moved and has not lasted is a tap if it ends here AND
  still a candidate hold if it continues, so there is no third state to keep in
  step. `"drag"` is terminal — travel already belonged to something else (a
  scroll, a carry, a swipe the system is about to steal), and standing still
  again cannot undo it.
- `pressTravel(down, at)` — straight-line distance from where the finger
  landed. Straight-line on purpose: a per-axis test lets a 9 + 9 px diagonal
  through, which is 12.7 px of real movement, and a diagonal is exactly how a
  thumb leaves a row.

## Design Decisions

- **Pure by design** (no DOM, no timer, no socket — the
  [Caret](caret.md) / [View Anchor](view-anchor.md) pattern): the gate runs the
  module WHOLE in node. That is the entire point — the old arming logic was not
  extractable, which is why it was never tested and why it shipped broken.
- **Proven by a SEQUENCE, never by one call** — `tests/test_hold_gesture.py`
  drives a modelled resting finger sampled at ~60 Hz for 400 ms and a real
  20 px pull. A rule about jitter cannot be proven by one call.
- **Honest limit:** there is no Android device in the loop. The 12 px slop is a
  reasoned model of a resting fingertip, not a measurement of the owner's own
  tablet, and Chrome's real scroll slop on his device is likewise unmeasured.
  If a hold still fails to arm on the glass, `HOLD_DRAG_SLOP` is the thing to
  move — not the rule.

## Used by

- [Layouts](layouts.md) — the layout list's row press (`pointermove` verdict,
  and the constants the row's tap guard reads)
- `tests/test_hold_gesture.py` — the gate, fail-closed in `setup/build.py`
