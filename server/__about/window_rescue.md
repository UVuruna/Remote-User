# Window Rescue — can he reach it, asked of geometry alone

Source: [`server/window_rescue.py`](../window_rescue.py) ·
Measurement: [Lost Windows](lost_windows.md) ·
Chip and queue: [Layout Popup](layout_popup.md) ·
Driven by: [Focus Guard](focus_guard.md)

## Why it is its own module

Split out of [Layout Popup](layout_popup.md) on 2026-08-17 at THE STRUCTURE
LAW's wall, and **by responsibility**. Every other pass in that module asks
*whose window is this* and answers from evidence — an owner chain, a process,
a click, a baseline of what stood here before. This pass asks something a
measurement answers outright: **is a grabbable piece of this window's title bar
inside some monitor's work area, right now.**

That difference is not cosmetic. It is why this is the only pass that can speak
for a window opened hours before the phone ever connected (constraint 17), and
why it runs at the **desktop** as well as inside a layout — a lost window is
lost either way.

## What it does not do

It never moves anything. It queues the same chip every other pass uses — one
strip of screen, one dismissal rule — and the rescue itself happens only on his
tap, in [Lost Windows](lost_windows.md).

## The defence it was missing

**A window he just asked for is never a question — and this pass never knew
it** (found by an independent agent, 2026-08-17). Every other pass has consulted
`is_ours` since that rule was written; this one was added later, for a different
question, and simply never learned it. So a window we opened on his own tap that
happened to land off-screen — which is what a freshly opened window does before
anything places it — could be handed back to him as *"this is lost, shall I
rescue it?"*, with every other defence in the file intact and bypassed.

It is not a variant of the race [Window Claim](window_claim.md) closes: there
the guard was late, here it was **absent**. It now asks `is_ours` like everyone
else.

## The two memories, and why they are two

`lost_asked` and `lost_left` mean different things. An unanswered chip may
simply have been missed while he was reading the PC screen, so the next
connection asks again — that is what makes this a guarantee rather than a
lottery. A window he actually said *leave it* about is never raised again on
that connection.
