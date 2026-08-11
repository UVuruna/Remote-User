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
