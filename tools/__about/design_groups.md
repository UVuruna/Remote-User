# `design_groups.py` — the catalogue

**Which** knobs exist, **in which group**, **what each one is for**, and **which
specimen it points at**. Split from `design_tokens.py` on 2026-08-19 (owner
round 2): that file is the ENGINE — where a value lives on disk and how it is
rewritten — and this one is the VOCABULARY. Two questions, two files, and
neither is near the structure wall now that the vocabulary can grow a sentence
and a picture per row.

## The owner's round-2 sentence is the spec

He asked for *"nicer descriptions, even with a little picture, saying what each
setting does"*, and gave the case that proved it was needed: he went looking
for the WHITE shadow drawn under black letters and a black icon, and could not
find it. Two different failures, and this file answers both.

**A knob with no sentence is a knob nobody turns.** Every row carries `help`:
one plain sentence saying what the number does and where on the phone you see
it. Not the token's name reworded — the token's name is already on the row, and
a name is not an explanation.

**A value that is not in the list cannot be found, however well the list is
grouped.** The white shadow lives in TWO places, and the first version of this
file offered neither as a colour:

- `SHADOW_LIGHT` / `SHADOW_DARK` in `client/theme.js` — the COLOURED looks,
  decided per button while it is painted. Rows of their own (`jscolor`) now.
- `--ink-shadow` / `--lbl-shadow` in `client/theme.css` — the PLAIN looks,
  decided per theme. They were offered as a STRENGTH only, and a note claimed
  that closed the question; an independent grader read the claim back and it
  was false. They are `shadow` rows now: a colour per theme **and** the
  strength, on one row.

[tests/test_design_lab.py](../../tests/test_design_lab.py) fails if either
pair ever leaves again.

## What every row carries

| field | what it is for |
|-------|----------------|
| `label` | the name a person would use, not the token's |
| `help` | one sentence: what it does, where it is seen |
| `pic` | the id of a mini diagram ([design_pics.md](design_pics.md)) — a radius, a gap, a halo is a picture before it is a word |
| `demo` | a CSS selector inside the specimen board. Hover the row and every element the value reaches is outlined in all eight frames at once |
| `min/max/step/unit` | the range a slider spans, for the number kinds |

`demo` is the answer to *"which setting is that?"* that no prose gives: the page
points at it. **A demo is a promise**, so a row whose value nothing on the bench
draws carries none and says where it IS drawn instead — a grader found five rows
pointing at elements that never read their token, and a pointer that lands on
the wrong thing is worse than no pointer, because it is believed.

Two of its selectors are the board's own rather than CSS — **`:dark-ink`** and
**`:light-ink`** are answered from what `paintSet` really produced a moment ago,
so the row about the white shadow outlines exactly the specimens that came out
with black letters, in whichever look is on screen. A list of set names written
here would be a copy of `server/config.py` and the copy nobody updates — and it
would also be wrong, because which sets take black ink depends on the FILL and
the THEME, not on the palette alone.

## The six kinds of row

- **theme** — one colour token with **two** values (dark and light), edited as
  one row, because "the card" is one idea with two answers and a page that made
  him find the light one elsewhere is a page that lets the two drift.
- **shape** — a number in `client/style.css`, with the range its slider spans.
- **shadow** — a colour token that is also a strength: the hue per theme, and
  one strength slider that lands in three places (both themes' tokens and the
  JS constant the coloured looks compute with). One knob for a value that has
  three homes is how the plain and the coloured looks stop drifting apart.
- **jscolor** — a colour that is a rule **in code** (`client/theme.js`), one
  value for both themes, because the rule that picks between them does not know
  what a theme is: it looks at the ink.
- **derived** — shown, never editable. `--on-gap` follows the page floor and
  `--topbar` is computed from the spacing; pinning either would turn a rule back
  into a constant.
- **sets** — the whole palette, one swatch per shipped set.

## The groups, and why they are these groups

A group is a **job**, not a file. "The ON ring is too tight" has to land in one
place, with the ring's colour and the ring's geometry side by side, even though
one lives in `theme.css` and the other in `style.css`.

The order is the order the questions get asked in — the two he asked first are
first:

| Group | What it answers |
|-------|-----------------|
| Shadows | all four shadow colours — two for coloured controls, two for plain — their strength and their geometry |
| Control shape | the face: size, radius, icon, label, the smaller set switcher — and the two FILLS the button wears, which belong with the button and not with the page's surfaces |
| ON state | the luminance flip: face, ink, glow, and the three-stop ring |
| Pressed | the halo's colour, its size and the inward scale — never mistakable for ON |
| Set palette | one colour per shipped set — one table, both themes |
| Surfaces | what the page is made of, plus the card's own elevation; every one is measured against later |
| Ink | text, including the `--on-*` inks that belong to a FILL |
| Accent | the one hue the page uses for itself |
| Status colours | the pill and the ledger dot, under a 4.5:1 floor |
| Wheel | what a set circle is made of |
| Page rhythm | the two spacings and how round a pill is |

## Pinned values

`PINNED` names, per token, the gate that has an opinion about it — the shadow
geometry and alphas (his ballot of 2026-08-15), the two shadow colours (each
must stay on its own side of the 0.179 crossover or a shadow stops being the
ink's opposite), the semantic fills measured to 4.5:1, the ledger yellow the
grader moved off the warning hue, the fill-solid he raised so the fill axis
could be seen at all, and the whole set palette under the contrast sweep.

They are **offered and saved like any other value**, and reported afterwards.
The reasoning is in [design_lab.md](design_lab.md) → *What the page does with a
save*.

Up: [tools/___tools.md](../___tools.md) ·
Beside: [design_tokens.md](design_tokens.md) · [design_pics.md](design_pics.md)
