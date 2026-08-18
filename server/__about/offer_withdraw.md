# Offer Withdraw — a question about a window that is gone

Source: [`server/offer_withdraw.py`](../offer_withdraw.py) ·
Registry and chip: [Layout Popup](layout_popup.md) ·
The questions it withdraws: [Layout Birth](layout_birth.md) ·
[Window Rescue](window_rescue.md) ·
Driven by: [Focus Guard](focus_guard.md) ·
Phone side: `client/window-offer.js`

## The report

2026-08-18, with a screenshot of the phone: the agents open and close a heap of
windows while they work, and by the time he picks the phone up there is a stack
of chips asking *"X opened — a layout with it?"* about windows that closed
minutes ago. He has to tap **No** through every one of them, and the yes would
not have worked either — a layout cannot be made out of a handle with no window
behind it.

The cause was a gap, not a bug in any rule: a chip was only ever taken down by
his tap or by the phone's own 30 s timer. **Nothing watched the subject of the
question.**

## What it does

Once per watcher tick, for the connection's own offers only:

1. Ask `window_manager.is_alive(hwnd)` — the same three questions the sweeps
   themselves stand on (the handle exists, it is visible, it is not cloaked).
   A window this module calls dead is exactly one the passes next door would no
   longer offer.
2. Drop the offer from the registry, so a stale tap on a dead handle can never
   be honoured.
3. Forget the hwnd in `popup_asked` / `birth_asked` / `lost_asked`.
4. Queue a `window_offer_cancel` frame naming the id — the phone drops that
   chip, whether it is the one on screen or one waiting in its queue.

An offer whose frame has **not been sent yet** is deleted where it stands and
gets no cancel: a chip nobody saw needs no withdrawal, and sending one that is
already dead would show him a flicker he cannot answer.

## Why it is its own module

Split from [Layout Popup](layout_popup.md) at THE STRUCTURE LAW's wall, the way
[Window Rescue](window_rescue.md) was, and by the same test — responsibility.
Every pass in that file asks *whose window is this, and where does it belong*,
and each of them ENDS in a question. This one asks nothing and answers nothing.
It is the only code here whose subject is a question already asked, and whose
whole job is to unask it.

`layout_popup` keeps ownership of the registry: this module reads it through
`open_offers()` and removes through `drop_offer()`, so there is still exactly
one place an offer can be born and one place it can die.

## The rule underneath

**Measured, never remembered** (constraint 13). An offer is not a note about a
window that once existed — it is a question about the desktop as it is now.
When the desktop stops holding the subject, the question goes with it.

## Gate

`tests/test_window_offer_queue.py`, five checks, each proven by planting its own
defect: the withdrawal itself, the never-sent chip that is dropped rather than
sent, a living window that keeps its question through a second of ticks, and
the two phone-side ones that run the real `client/window-offer.js` in node — a
withdrawn chip leaves the strip (its queued sibling never going up at all), and
the next living question is still asked and still answered.
