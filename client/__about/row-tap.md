# row-tap.js — the one row activator

[← client](../___client.md)

**What it is:** `keepRowTap(el, onTap)` — the activator every row of every
scrollable list on the phone wears, plus `ROW_TAP_SLOP` (12 CSS px).

**Why it exists.** The page's ordinary button activator is `keepFocus`
(`controls.js`), and it is right for a button: it calls `e.preventDefault()`
on `pointerdown` so a touch grants real activation (the file picker and the
IME need it) and fires on `pointerup` whatever the finger did in between.
Inside a list that scrolls, both halves are wrong:

- the `preventDefault` stops the browser ever recognising the touch as a
  scroll, so a drag that starts on a row can never scroll the list;
- the travel-blind `pointerup` selects whatever row the finger happens to
  lift over, so even a drag that DID scroll ends in a selection.

`keepRowTap` never prevents the default (the browser decides) and acts only
on RELEASE, by travel alone, asking `pressVerdict` from
[hold-gesture.js](hold-gesture.md) rather than re-deriving the rule
(constraint 9: one activator, never a second copy that can drift). A press
that stayed under `ROW_TAP_SLOP` selects; a drag past it never does. The
`pointercancel` rescue of constraint 9 survives: a stolen touch under slop
still counts, so a row near an Android edge-gesture zone is still tappable.

It carries no duration test on purpose — a hold does not travel, so a list
that must tell a hold from a tap (the layout list's drag-to-merge) refuses in
its own handler, where its own limits are known.

**Where it belongs.** Anything a finger might legitimately begin a scroll on:
every row of every list, and every control inside a card that scrolls.
Ordinary buttons keep `keepFocus`, and anything needing transient user
activation (a file picker, the IME) **must** keep it — that is the one thing
this function gives up.

**Why it is a module.** It shipped 2026-08-11 (task 227b) inside
`layout-create.js`, fixing that panel's rows. On 2026-08-15 the owner met the
identical defect in the notification-voice card's language list, and his
report was about the process rather than the card: a rule kept inside one
panel's file is read only by somebody already in that file. Four other panels
carried the same defect at the time — the dictation card, the Claude
model/effort pickers, the Sets picker, the layout list and its ⚙/shape
buttons. Moving it out is the same lesson `hold-gesture.js` was made from.

**Gate:** [tests/test_row_tap.py](../../tests/test_row_tap.py) — extracts the
real function between its `ROW_TAP_GATE_START`/`_END` markers and runs it whole
in node against the real `pressVerdict`, and then sweeps the client so a panel
that goes back to `keepFocus` fails here instead of on his device.
