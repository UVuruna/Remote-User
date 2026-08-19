# `design_tokens.py` — the engine

**Where** each design value lives on disk, and **how** it is read and written
back. The catalogue — which knobs exist, in which group, what each is for —
moved next door to [design_groups.md](design_groups.md) on 2026-08-19 at the
structure wall. One door in both directions either way: the page can never offer
a knob the writer cannot save, and the writer can never touch a value the page
did not offer.

## The five sources

| id | file | where |
|----|------|-------|
| `dark` | `client/theme.css` | `:root { … }` |
| `light` | `client/theme.css` | `body[data-theme="light"] { … }` |
| `shape` | `client/style.css` | `:root { … }` |
| `sets` | `server/config.py` | `SET_COLORS = { … }` |
| `js` | `client/theme.js` | top-level `const NAME = "r g b";` |

The fifth is the round-2 addition (owner, 2026-08-19) and it is a different
SHAPE, not just a different file: the two shadow colours are a rule the page
applies per element, so they were never CSS and could never be a theme token.
Not a block either — the anchored `^const NAME = "` is what keeps a whole-file
search to one line — and the value is refused unless it is an `r g b` triple,
because `shadowFor` interpolates it straight into a CSS colour and anything
else would be a stylesheet that silently draws nothing.

Plus two **JS twins**: `INK_SHADOW_ALPHA` and `LBL_SHADOW_ALPHA` in
`client/theme.js`, which the coloured looks compute their shadows with. A
shadow's strength is one knob and three writes — the token on each theme and
the constant — because two places holding one number is how the plain and the
coloured looks drift apart without anyone editing either.

**Nothing here holds a value.** The values already have a home; a tuner that
kept its own copy would be a second source of truth, and the second one goes
stale.

## The groups, and the kinds of row

Both moved to [design_groups.md](design_groups.md) with the catalogue itself.

## What may be written, and what may not

`write_source` matches `--name: <value>;` (or `"Name": "#hex",`, or
`const NAME = "…";`) **by name**, inside one block, and refuses four things:

1. a token the registry does not offer for that source;
2. a value carrying a `;`, a newline or (in the palette and the constants) a
   quote — a page bug must not be able to become a broken stylesheet;
3. a shadow colour that is not an `r g b` triple;
4. a name the block does not already declare — nothing is ever **inserted**.

No rule, selector or comment is part of any match, which is why the owner's
verdicts and the graders' findings written around these values survive every
save. `with_alpha` additionally leaves an **unchanged** strength spelled exactly
as the file spells it: `0.80` and `0.8` are one strength and two lines, and a
save that reformatted every alpha it merely read would bury the one value he
moved.

## Pinned values

`PINNED` and `SET_PIN` live with the catalogue now
([design_groups.md](design_groups.md) → *Pinned values*); `pins_touched` here is
what reports them after a save.

Up: [tools/___tools.md](../___tools.md) ·
Beside: [design_groups.md](design_groups.md)
