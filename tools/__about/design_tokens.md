# `design_tokens.py` — the registry

**Which** design value is tunable, **where** it lives, **what kind** of thing it
is, and **which group** it belongs to. One table, read and written through, so
the page can never offer a knob the writer cannot save and the writer can never
touch a value the page did not offer.

## The four sources

| id | file | block |
|----|------|-------|
| `dark` | `client/theme.css` | `:root { … }` |
| `light` | `client/theme.css` | `body[data-theme="light"] { … }` |
| `shape` | `client/style.css` | `:root { … }` |
| `sets` | `server/config.py` | `SET_COLORS = { … }` |

Plus two **JS twins**: `INK_SHADOW_ALPHA` and `LBL_SHADOW_ALPHA` in
`client/theme.js`, which the coloured looks compute their shadows with. A
shadow's strength is one knob and three writes — the token on each theme and
the constant — because two places holding one number is how the plain and the
coloured looks drift apart without anyone editing either.

**Nothing here holds a value.** The values already have a home; a tuner that
kept its own copy would be a second source of truth, and the second one goes
stale.

## The groups, and why they are these groups

A group is a **job**, not a file. "The ON ring is too tight" has to land in one
place, with the ring's colour and the ring's geometry side by side, even though
one lives in `theme.css` and the other in `style.css`.

| Group | What it answers |
|-------|-----------------|
| Surfaces | what the page is made of — every one is a surface an ink is later measured against |
| Ink | text, including the `--on-*` inks that belong to a FILL rather than to the theme |
| Accent | the one hue the page uses for itself |
| Status colours | the pill and the ledger dot, under a 4.5:1 floor |
| ON state | the luminance flip: face, ink, glow, and the three-stop ring's geometry |
| Pressed | the momentary hue and the inward scale — never mistakable for ON |
| Shadows | strength and geometry of the icon/label shadows, plus the card's elevation |
| Control shape | the face: size, radius, icon, label, the smaller set switcher |
| Wheel | what a set circle is made of |
| Page rhythm | spacing and the pill end |
| Set palette | one colour per shipped set — one table, both themes |

## The five kinds of row

- **theme** — one colour token with **two** values (dark and light), edited as
  one row, because "the card" is one idea with two answers and a page that made
  him find the light one elsewhere is a page that lets the two drift.
- **shape** — a number in `client/style.css`, with the range its slider spans.
- **alpha** — the strength slot of a colour whose **hue is a rule, not a
  choice**: a shadow is the ink's opposite (`client/theme.js → shadowFor`), so
  only how strong it is may be tuned.
- **derived** — shown, never editable. `--on-gap` follows the page floor and
  `--topbar` is computed from the spacing; pinning either would turn a rule
  back into a constant.
- **sets** — the whole palette, one swatch per shipped set.

## What may be written, and what may not

`write_source` matches `--name: <value>;` (or `"Name": "#hex",`) **by name**,
inside one block, and refuses three things:

1. a token the registry does not offer for that source;
2. a value carrying a `;`, a newline or (in the palette) a quote — a page bug
   must not be able to become a broken stylesheet;
3. a name the block does not already declare — nothing is ever **inserted**.

No rule, selector or comment is part of any match, which is why the owner's
verdicts and the graders' findings written around these values survive every
save. `with_alpha` additionally leaves an **unchanged** strength spelled exactly
as the file spells it: `0.80` and `0.8` are one strength and two lines, and a
save that reformatted every alpha it merely read would bury the one value he
moved.

## Pinned values

`PINNED` names, per token, the gate that has an opinion about it — the shadow
geometry and alphas (his ballot of 2026-08-15), the semantic fills measured to
4.5:1, the ledger yellow the grader moved off the warning hue, the fill-solid
he raised so the fill axis could be seen at all, and the whole set palette under
the contrast sweep.

They are **offered and saved like any other value**, and reported afterwards.
See the reasoning in [design_lab.md](design_lab.md) → *What the page does with
a save*.

Up: [tools/___tools.md](../___tools.md)
