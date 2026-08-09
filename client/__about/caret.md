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

## What it is measured against (2026-08-09)

`caretLift({ caret, picture, canvasHeight, keyboardHeight })`. A caret is
**monitor-normalized** (0..1, from `server/caret.py`), so the only honest way
to turn it into a pixel is the rect the picture is actually **drawn** into —
`drawnRect()` in [Render](render.md):

```
caretTop    = picture.y + caret.y * picture.h
caretBottom = picture.y + (caret.y + caret.h) * picture.h
```

**It used to take the view TRANSFORM, and that was half of why five rounds
shipped a rise of exactly 0.** The old form was `caret.y * view.scale +
view.ty`, but `view.scale` is a ZOOM FACTOR and is **1 at home** — so a caret
at y=0.95 landed 0.95 *pixels* from the top of an 1800 px screen. Every caret
was already clear of every keyboard, forever, whatever height it was handed.

The drawn rect folds in the zoom, the pan **and** the letterbox offset the old
form dropped entirely, so "the lift follows the view, not the monitor" still
holds and a letterboxed layout — where he does most of his typing — is finally
measured where it really sits on his screen.

The other half was the plumbing: `window.__imeHeight` had been deleted as
collateral by a revert of unrelated streaming code, so the rule was being fed a
keyboard height of 0 as well. Two independent zeros, one symptom.

## When the PC cannot find a caret

Some apps expose none. An app that cannot say where it is typing is **never
guessed at**, and nothing moves.

There was a `"lift"` fallback here — his own idea of 2026-08-07, a Settings
switch for windows he knows sit at the bottom. It was **dead code**: the
desktop never grew the control, `config.ui` carries no such field, and the
page's `caretUnknownMode` was assigned nowhere, so the branch could not run
while a comment beside it promised a switch that did not exist. It was deleted
on 2026-08-09 (owner decree 2026-08-07 — legacy things are removed, not kept),
and [the gate](../../tests/test_caret_lift.py) now proves a caller still
passing the retired argument changes nothing. It comes back the day the desktop
Settings window grows the control that would feed it.

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
