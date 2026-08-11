# Window Offer

**Scripts:** [window-offer.js](../window-offer.js) ·
[window-offer.css](../window-offer.css)

## Purpose
Ask him where a window that just opened on the PC should go — **Show in
layout** or **Leave on desktop** — and send his answer back.

## Why it exists
Task 202 (owner report 2026-08-10, escalated 2026-08-11): an agent on the PC
opened its HTML report while he was watching a LAYOUT, and the window landed
outside the layout's region — under the members' always-on-top band, where the
phone could see it and not touch it, and where the only way to it (Desktop)
minimizes his whole layout.

The server can now bring such a window into the picture
([Layout Popup](../../server/__about/layout_popup.md)), and his amendment the
same day is that it must **ask first**: when something new opens, the program
asks whether to open it in the layout or normally on the desktop.

## The rules
1. **The prompt is on the PHONE.** A PC-side dialog would itself be a window he
   cannot reach — the disease, not the cure.
2. **It names the window.** The title rides the message and WRAPS rather than
   being cut (THE SPACE & LEGIBILITY LAW): two buttons under a title he cannot
   read are a guess.
3. **Ignoring it is an answer, and the answer is the desktop.** The chip fades
   after `WINDOW_OFFER_MS`, nothing on the PC moves, and the window stays
   exactly where Windows put it. Only *Show in layout* moves anything.
4. **One chip per window.** The server offers a window once (it is the side
   that knows what a window is); this page never re-raises one by itself.
5. **The answer goes over HTTP** (`POST /window_offer?token=…`), the same route
   shape the uploads use — no new message type on a socket dispatcher owned by
   another round, and one small route the page already knows how to speak.

## Wiring
- `connection.js` calls `showWindowOffer(msg)` on the server's `window_offer`
  frame.
- `index.html` carries the chip's markup (`#window-offer`) and loads this pair
  after `controls.js` (it reads the page's `token`) and before
  `connection.js`.
- Colours come from the shared tokens in `theme.css` only, so the chip wears
  every theme and both fills, and the phone audit measures it like every other
  card.

## What the independent grader corrected (2026-08-11)
Three defects on this one chip, all of them found by OPENING the picture and
then measured on the live page — none of them caught by any existing tooth,
because the round's new surfaces were measured for fit and contrast and for
nothing else.

1. **It rendered in Times New Roman.** `window-offer.css` set a `font-size`
   and nothing else, so the family fell back to the UA default while every
   other surface of this page is on the system stack — and the two buttons came
   out in Arial beside it, because a `<button>` does not inherit the page's
   font at all. Both now state the whole `font` shorthand, exactly as
   `style.css` does everywhere else.
2. **The primary action never wore its accent.** `#window-offer-in` is
   specificity (0,1,0) and `#window-offer button` above it is (0,1,1), so the
   plain chip fill won every cascade and *Show in layout* was byte-identical to
   *Leave on desktop* in all eight looks. Corrected by writing the accent rule
   to be more specific (`#window-offer #window-offer-in`), never by
   `!important`.
3. **The two buttons were 117 px and 137 px** — a control sized by the length
   of its own text, which is ALG-5. The title now takes a row of its own
   (`flex: 1 1 100%`) and the two acts split the row below it with the same
   `flex: 1 1 0`, so they are equal by construction rather than by a hardcoded
   number that goes stale the day a label is reworded. Measured after the fix:
   180 px each at 412x915, 211 px each at 915x412.
4. **`flex: 1 1 0` + `min-width: max-content` was still content-dependent**
   (grader flag b, task 233): it equalised width only while both labels' own
   min-content sizes were CLOSE — the `layout_new` variant's wording ("Make a
   layout" / "No") has one two-character label, and the flex algorithm handed
   it a floor far smaller than its sibling's, measuring 115 px vs 55 px — a
   different pair of unequal numbers from the same root cause. The buttons are
   now wrapped in `#window-offer-actions`, a CSS `grid-template-columns: 1fr
   1fr` — width by construction, independent of either label's length, so no
   future wording of either variant can land unequal again.
