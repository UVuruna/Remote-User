# theme.css + theme.js — how the phone looks

One feature, two files, one doc (the same arrangement `layouts.css` and
`layouts.js` already use):

- **`client/theme.css`** — every colour the client uses, in three themes and
  two fills. Nothing in it positions anything.
- **`client/theme.js`** — which of those are in force right now, and the
  colour each SET wears.

Built in **build round R3** (owner-approved 2026-08-07), answering the round's
open question **P4** with "the phone's theme is chosen ON THE DESKTOP ONLY"
and **P5** with "adopt the proposed set-colour palette and tune later".

## The one rule everything else follows

**The desktop decides; the phone obeys.** The look arrives in every `config`
frame as `ui = {theme, fill, colors}` and that is the only input. There is no
theme menu on the phone, nothing is auto-detected, and the device's own
dark/light preference is deliberately ignored — one source of truth means the
owner never has to work out which of two places is winning. It is set in the
desktop **Settings → APPEARANCE** card (`server/gui/settings_window.py`) and
built by `config.ui_config()`.

## The two axes

| Attribute on `<body>` | Values | What it decides |
|---|---|---|
| `data-theme` | `dark` · `light` · `colored` | surfaces, ink, shadows |
| `data-fill` | `transparent` · `full` | outlined buttons, or filled ones |

They are independent, so there are **six** real renderings of every surface —
and the audit measures all six (below).

- **dark** — today's look, unchanged. It is the `:root` block, and the other
  two are overrides of it.
- **light** — elevation INVERTS (DESIGN.md): the raised card is the whitest
  thing and the page sits a step below it. The accent is deepened to `#0369a1`
  because the dark theme's `#38bdf8` sits at 2.2:1 on white. The icon and
  label shadows flip from black to white — the controls float over the PC's
  own screen, which can be any colour, so dark ink over a dark window needs a
  light halo or it vanishes.
- **colored** — the DARK surfaces, with every set wearing its own colour. The
  surfaces stay dark on purpose: what sits behind the controls is the PC's
  screen, and a colour per set is a statement about the buttons, not about the
  page.

`full` is carried by ONE token. `--glass-fill` (and its three relatives) is
what every button, chip and wheel item already paints itself with, so
`body[data-fill="full"]` re-points those four at `--fill-solid` and no rule
anywhere else needs to know which fill is active.

**The light theme's own transparent values were too close to opaque to prove
that** (independent grader, 2026-08-07 — graded 7/10: `Controls_light_transparent`
and `Controls_light_full` were "not perceptibly different, both show white
filled buttons"). Dark's transparent glass is a mere 0.20 alpha of its own
card colour, so a transparent `.ctl` reads as almost nothing over the stream
while `full` is a solid `#1e293b` box — an obvious pair. Light's transparent
values used to sit at 0.55–0.90 alpha of near-white, which was already most
of the way to `--fill-solid` (`#ffffff`), so `full` barely changed anything.
They now sit as low as dark's do (`--glass-fill` 0.14, `--glass-strong` 0.55,
`--chip`/`--chip-2` 0.55/0.40), so `transparent` genuinely drops the fill and
shows only the border, and `full` is the only state that reads as a filled
card. A dropped fill needed its own edge to still read as a shape, so a new
`--wheel-border` token (root = `var(--border)`, light = a stronger
`rgb(22 22 31 / 0.38)`) carries the wheel item's ring — `.wheel-item` /
`.wheel-x` in style.css read it instead of `--border` directly.

## Border, ink and fill are THREE different jobs (second grader, 2026-08-07)

`colored` used to compute one ink per set colour and use it everywhere —
border, outlined label and filled label alike. A second, independent grader
who actually MEASURED (not asserted) found that wrong on two fronts at once,
both now fixed in `theme.js`:

- **Outlined**: the border is a graphic (WCAG floor 3:1) and keeps the raw
  `--set-color` exactly as the desktop tuned it — the set's identity. The
  LABEL is text (a 9 px semibold `.lbl` wants 4.5:1, not the large-text
  floor), and it lands on `--glass-fill` composited over the page, never on
  the solid hue — a colour that reads fine AS a fill can still be a poor INK
  on that translucent surface. `--set-line` (`lineOn()`) is the same hue
  lifted along the straight line toward whichever of black/white the surface
  is further from, stopping at the FIRST step that clears **7:1 (AAA)** —
  not 4.5, because these buttons float over the PC's own unknowable screen,
  and AAA is the margin an unknown backdrop is owed. Most of the shipped
  palette needs no lift at all; the heaviest is VSCode's `#3B82F6`.
- **Filled**: the fill really is the hue, so black-or-white ink (`inkOn()`,
  whichever of the two wins on that exact colour) is correct in principle —
  but for a hue sitting near the luminance crossover (~0.179) BOTH options
  read poorly at almost the same weak ratio, and no ink choice can rescue
  that (VSCode's `#3B82F6` again: even its BETTER ink measured 4.27:1, under
  AA). The only remaining lever is the fill's own luminance: `--set-fill`
  (`fillOn()`) nudges the raw hue the SHORTEST distance — toward black or
  toward white, whichever clears AA in fewer steps — so the set stays
  unmistakably its own colour and only a hue that actually needs it moves at
  all (today just VSCode in the shipped thirteen). `--set-ink` is then chosen
  against that same nudged surface, never the raw hue. The border still wears
  the untouched `--set-color`, so a 1px ring never drifts from the desktop's
  own table.
- **The category button's own 0.85 opacity (`.ctl.cat`) is a REAL dilution,
  priced in up front.** It sits translucently over its own fill, pulling its
  ink 15% back toward that fill — a photograph of the phone shows exactly
  that, so `fillOn()` requires the DILUTED ink (85:15 toward the fill) to
  clear AA, not the plain undiluted one; a plain `.ctl` (no opacity) then
  clears it with room to spare. Missing this the first time is what let
  VSCode through at 4.27:1 even after the fill was otherwise correct.
- **A veil painted ON TOP counts too.** The grader's original 2.66:1 reading
  was not an ink bug at all — it was the category wheel's own full-screen
  `--scrim-soft` veil, which used to paint ABOVE the D-pad at a higher
  z-index, composited over every visible label. Under a 0.55 veil the
  maximum contrast achievable between ANY two colours is 4.83:1, so no ink
  computation could have answered it. The veil moved BELOW the app's own
  chrome instead (`body.wheel-open::before` in `style.css`).

## The set colours

The palette is the desktop's `SET_COLORS` table (`server/config.py`), shipped
verbatim in `ui.colors`:

Mouse `#38BDF8` · Input `#4ADE80` · Settings `#94A3B8` · Edit `#A78BFA` ·
Attach `#F59E0B` · Navigate `#2DD4BF` · Media `#F87171` · Windows `#818CF8` ·
VSCode `#3B82F6` · Chrome `#FACC15` · Explorer `#FB923C` · Claude `#D97757` ·
Cursor `#F472B6`

A **custom** set is not in that table and never will be — the owner names his
own sets in the Controls editor. `setColors()` therefore hands each unnamed
set the next colour of the SAME palette that nothing already wears, in the
order the sets arrive, cycling if he ever makes more sets than there are
colours. One table to tune, no second list to keep in step.

`paintSet(el, name, surfaceVar)` writes `--set-color`, `--set-fill`,
`--set-ink`, `--set-line` and `--set-glow` onto the element that OWNS a set —
a D-pad group, a wheel item — so its four buttons, its category button and
all their labels inherit them in one write instead of five. `surfaceVar`
names the token the caller's OWN buttons are painted with (`--glass-fill` for
a D-pad button, `--glass-strong` for a wheel item — really different
surfaces, 0.20 vs 0.85 of the same navy, and therefore different lifts); the
caller states it because it is the only one that knows. The properties are
written in every theme and READ only in `colored`: a rule that has to un-set
itself when the theme changes is a rule that will one day be left behind.

## The ink is COMPUTED, never tabled

`inkOn(surface)` returns `#0b1220` or `#ffffff`, whichever actually has the
better contrast on that exact surface — black and white cross over at a
relative luminance of about **0.179**. That is what keeps `colored` readable
without anyone tuning anything: the owner may retune `SET_COLORS` on the
desktop whenever he likes, and a hand-written ink per colour would be wrong
the first time he did (rules/CODE.md → Compute, Don't Generate). `lineOn()`
and `fillOn()` (above) are the same idea applied to the two surfaces that
actually exist — a translucent tint, and a fill that may need its own small
nudge — rather than one function pretending both are the same question.

## The cache

The choice is stored per device (`prefGet`/`prefSet` → the shell's
SharedPreferences, localStorage in a dev browser) and re-applied at load,
before the socket has said anything. Without it the page would paint the
previous theme for the third of a second it takes to connect — a flash on
every single connect. The cache is a HEAD START, never an authority: a
`config` without `ui` puts the phone back to the shipped default rather than
leaving it wearing a theme nobody chose.

## What proves it

`tests/test_layout_audit.py` sweeps **all six looks**. Its CONTRAST check
composites every translucent layer down to the page floor — read from the
live `--surface-0`, never a literal, so it is honest in light as well as
dark — AND every visible full-viewport layer painted ABOVE the element (the
wheel's veil, the loading overlay's own kind), AND every ancestor's own
`opacity` (`.ctl.cat`'s 0.85), because a check that only ever looks downward
through backgrounds cannot see either of those and a second grader proved it
by finding what it missed. **The floor itself is per-element, not one number
for everything** (the same grader, same round): WCAG's 3:1 is for LARGE text
only (≥24px, or ≥18.66px at bold) — every label this project draws is
smaller than that, so it is held to 4.5:1 unless it genuinely qualifies as
large.

`__sweepSetColours(names)` repaints the real D-pad and the real wheel with
**every** colour in the desktop's `SET_COLORS` table, not only the two or
three a fixture happens to show — a set the owner darkens tomorrow is
measured today, on both surfaces, in every look.

## Related

- [style.css](style.md) — shape and position; it reads these tokens and names
  no colour of its own.
- [connection.js](connection.md) — where `config.ui` arrives.
- [controls.js](controls.md) — calls `paintSet` per group and per wheel item.
- [sets.js](sets.md) — what the set list is in the first place.
- `server/gui/theme.py` — the desktop's own two palettes, same family.
