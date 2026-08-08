# caret.js — how far the picture rises for the keyboard

**Script:** [Caret (script)](../caret.js) · **Flow:** [Caret (flow)](../__flow/caret.md)

## Purpose

One pure function, `caretLift()`, answering one question: **how many canvas
pixels should the PC's picture be raised so the row he is typing into is not
under the soft keyboard?** The answer is almost always **zero**.

## Why a fixed rule could never work

The owner asked for the opposite thing twice, and he was right both times.

| | What he asked for | What happened |
|---|---|---|
| 2026-08-03 | the keyboard should push the view up | built |
| 2026-08-07 | *"izbaci tekst koji se kuca iz vidokruga"* | withdrawn — `kbShift = 0` |

Both complaints are true at once, because they are about **different boxes on
the PC screen**. A box at the BOTTOM is covered unless the picture rises; a box
at the TOP leaves the screen if it does. So "always lift" and "never lift" are
each wrong half the time, and no constant can fix it. His own answer, the same
day:

> *"najoptimalnije rešenje bilo bi da naš program prepozna gde se nalazi, koja
> je pozicija na ekranu, kursora koji kuca."*

## The two promises the rule makes

**ONLY IF NEEDED.** A caret already clear of the keyboard moves nothing at all.

**ONLY BY THE SHORTFALL.** Never by the keyboard's full height — that is
precisely what made the 2026-08-03 version intolerable. And never past the top
margin: when the strip above the keyboard is shorter than the row needs, it
lifts what it can and leaves the rest covered, because **a covered row beats a
missing one**.

## Only the picture moves, never the filler

This is the half a naive implementation gets wrong, and he sent a screenshot to
say so: the first attempt moved everything, *"zaključno sa ovim delom koji nije
deo naše aplikacije"* — the navy filler that exists because a layout narrower or
shorter than the phone letterboxes.

> *"Poenta je da tastatura kada pomera sa offsetom ne pomera taj prazan deo već
> pomera samo vidljivi ekran gde se nalazi aplikacija, i to samo ako ima
> potrebe."*

The lift is expressed as **canvas pixels added to the view transform**, never as
a CSS transform on an element. The canvas and the colour behind it therefore
cannot move: the filler is the canvas backdrop showing where the picture is
*not*, so it cannot travel with the picture — it is not part of it.

## When the PC cannot find a caret

Some apps expose none. An app that cannot say where it is typing is **never
guessed at**: the fallback is his own Settings switch — `"cover"` (do nothing,
the behaviour he chose to live with) or `"lift"` (the old whole-keyboard lift,
for apps he knows sit at the bottom). `"cover"` is the default.

## Why it is its own file

It is pure — no DOM, no socket, no state — so
[its gate](../../tests/test_caret_lift.py) can run it **whole** in node. The
round before this one is the warning: a rule that lived where no gate could run
it shipped half-done and cost a release. Same reason [voice.js](voice.md) was
split out.

The two margins (`CARET_LIFT_MARGIN_PX`, `CARET_TOP_MARGIN_PX`) are named
constants carrying their reasoning, and the gate refuses them as bare numbers —
they decide whether he can read the row he is typing in, so they are his to
tune and must be findable.
