# Window Offer

**Scripts:** [window-offer.js](../window-offer.js) ·
[window-offer.css](../window-offer.css)

## Purpose
Ask him where a window that just opened on the PC should go — **Move it in**
or **Leave on desktop** — and send his answer back.

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
   exactly where Windows put it. Only *Move it in* moves anything.
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

## The chip may not change its question under his finger (2026-08-12)

His report, with a screenshot: he clicked around on the PC desktop, the phone
offered *"a layout with it?"*, he tapped yes — and the window was **resized to
the phone's aspect while no layout was created**.

**His own server log settles it**, and the creation path was never involved —
`LayoutRegistry.create` did not run at all after that tap:

```
20:29:58,356  New window python.exe "Controls …" offered as a layout (185)
20:29:58,373  Popup     python.exe "Controls …" offered as 570a0a-3 (240)
20:29:58,403  New window python.exe "Record a shortcut" offered … (185)
20:29:58,569  New window python.exe "Wheel order" offered … (185)
20:29:58,752  New window python.exe "Traffic …" offered … (185)
20:30:03,565  POST /window_offer  200        <- his ONE tap
```

Two defects, and it took both:

1. **One window, two questions.** [Layout Popup](../../server/__about/layout_popup.md)'s
   `scan` (task 185) and its popup sweep (202/240) are two features that never
   knew about each other, and they fired on the same window in one tick. The
   server now refuses that: a window the FOCUSED layout can claim is the
   sweep's question — "show it in this layout?" — never the birth question.
2. **One chip slot.** This module had a single strip and a single live offer
   id, so every arriving `window_offer` silently replaced the last. Four
   questions vanished and the one his finger landed on was not the one he had
   read — and its yes runs `_contain`, which PLACES the window into the
   layout's region. Window resized to the phone's shape, no layout. His
   sentence exactly.

A chip standing for less than `WIN_OFFER_SETTLE_MS` is therefore **not
replaced**: the newcomer waits in a short bounded queue and goes up when the
current one is answered or fades. A queue and not a second strip, because a
second floating prompt is a second thing to notice and a second thing in the
way of the controls.

Gate: `tests/test_window_offer_queue.py`, fail-closed in `build.py` (0ay/6),
four checks each proven by planting its own defect — the server plant
reproduces his log line verbatim (`one window, 2 chips: ['layout_new',
'layout']`). The phone half runs this REAL module in node against a DOM shim,
since a rule about *which question a tap answers* cannot be proven in Python.

---

## What the chip no longer asks (owner report 2026-08-13)

Two questions left this chip on 2026-08-13, and both left because they could
not be answered:

* **A member's own dialog.** It is now PLACED on its parent by the server,
  without asking — the owner chain is Windows' own statement about whose window
  it is, not a guess (see `server/__about/layout_popup.md`).
* **A window no layout could hold.** The chip used to name tool windows and
  shell surfaces that the creation list would not carry when he tapped.

Nothing on this page changed for either: a question that is never sent is a
question this page never renders. It is recorded here because "the chip used to
appear here and no longer does" is exactly the sort of change that gets
re-reported as a regression.

## The wording must name the ACT (owner report 2026-08-13, defect 2)

He read *"X opened"* / *Show in layout* as an offer to CREATE a layout — it
never was. The `"layout"` chip's yes has only ever run `_contain`, which MOVES
the window into the layout he is already watching; the chip's own words never
said "move" and used the word "layout" in a way that read exactly like the
sibling `"layout_new"` chip's real offer to build one. Corrected to say the act
plainly and briefly enough for a phone chip: `"${n} opened outside this
layout"` / **Move it in** / **Leave on desktop**. `layout_new`'s wording did not
change — it already named its own act ("Make a layout").

**No third chip was added for "make a layout instead" while inside a focused
layout**, and that is deliberate, not an oversight: constraint 18 settles it —
a window the FOCUSED layout can claim is the sweep's question and NEVER the
birth one, because "make a new layout out of the layout's own work" was never
a sensible offer to begin with (the same reasoning that moved the sweep's
attribution ahead of the birth scan's on 2026-08-12). A third button on this
chip would violate that rule directly.

## THE THIRD ANSWER (owner report 2026-08-17) — and why the paragraph above was wrong

Corrected in place rather than deleted, because the wrong reasoning is the
evidence: it is the sentence that made this the bug he has reported more times
than any other in this project, and it read as a settled decision, so round
after round walked past it.

Its two claims fail separately.

* **"A third CHIP"** is what constraint 18 forbids, and nobody was asking for
  one. Constraint 18 is about the STRIP: one live offer id, so a second chip
  silently replaces the first under his finger and his tap answers a question
  he never read. Three answers on ONE chip about ONE window is the exact
  opposite of that failure — one question, asked once, fully written down
  before he touches it.
* **"The layout's own work"** describes rules 1-4 of `_attribute`, and since
  2026-08-17 the sweep also offers a window under a rule that says nothing
  about the layout at all: *nobody has placed this anywhere*. His agent's HTML
  report is that window every single day, and what he wants from it is a
  LAYOUT. So the premise ("a new layout out of the layout's own work") is not
  even true of the window this chip is usually about.

The shape: `new_ok` on the frame, and the page draws **Make a layout** on a row
of its OWN above the pair — not a third column, which would put all three
below a thumb's width (THE SPACE & LEGIBILITY LAW). It is the accented one and
"Move it in" steps back to the plain fill, so there is still exactly one
primary. Its tap runs `startFromWindow(win)` — the SAME function task 185's
chip, Tap, List and New all end in, which is his own requirement: *"let the
identical mechanics happen as if I were making it through any other mode"*.
The server moves nothing on that answer and does not file the window as left
on the desktop; the creation that follows makes it a member, which silences
the sweep by itself.


## Nothing may overlap anything (owner decree 2026-08-17)

His words on seeing the audit shots: *sredi to, ne sme da se preklapa ništa*
(lang-ok: owner quote). The status pill and this chip both live at the top
centre — the pill at `--topbar`, the chip just under it — and a toast arriving
while a chip stood landed straight over the chip's TITLE, which is the sentence
naming WHICH window he is being asked about. Without it the three answers are a
guess.

**The pill gives way, not the chip**, and that is a rule rather than an accident
of which one drew last: the chip is a question he must answer and must read
whole; the toast is a notice that leaves by itself. `syncToastShift()` writes
`--status-top` from the chip's MEASURED bottom edge on every show and clears it
on every hide — measured, because the chip's height depends on its wording, on
whether it carries the create answer, and on how many lines the title wraps to,
so any constant would be wrong for some real chip.

**The move is INSTANT, and that was measured rather than reasoned.** The first
version slid the pill over 0.2 s, which reads well in principle and photographed
badly: the audit's screenshot caught it mid-flight, sitting inside the chip it
was in the act of leaving — the exact picture the decree is about. Nobody was
going to admire the slide.

Gates: `tests/test_window_offer_queue.py` (the shift is written from the
measured box and dropped when the chip goes; the pill's own CSS really reads
it) and the phone audit's `the toast never covers the window chip`, which
measures a real rect intersection with both up at once, on all four screens —
the first tooth in that file to ask whether two independent overlays intersect
at all, which is why this shipped in its own screenshots for two rounds unseen.

## The window closed, so the question goes (owner report 2026-08-18)

His screenshot: a chip asking *"Restore pipeline steps - Glory opened — a layout
with it?"* about a window an agent had opened and closed again long before he
picked the phone up. *"Agenti … otvaraju i zatvaraju gomilu prozora i onda meni
kada koristim telefon moram 1.000 puta da pritisnem no i leave"* (lang-ok: owner
quote), and his own reading of it is the rule: **a layout cannot be made out of
a window that does not exist**, so the question should never have still been
standing.

Until this round a chip was taken down by exactly two things — his tap and the
30 s timer in this file. Neither of them knows anything about the window. Now
the PC watches it ([Offer Withdraw](../../server/__about/offer_withdraw.md)) and
sends `window_offer_cancel {id}` the moment it is gone.

`cancelWindowOffer(id)` is the whole phone half, and it sweeps **both** places a
question can be:

* the chip on screen — hidden, and whatever was waiting behind it gets its turn
  immediately, because that window may well still be there;
* the QUEUE — a withdrawn question that merely moved down the queue is the same
  tap arriving one beat later, which is exactly what he was complaining about.

An id this page does not know is a no-op: the chip may have faded on its own
before the PC noticed the window, and the two mechanisms must never fight.
