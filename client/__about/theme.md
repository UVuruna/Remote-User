# theme.css + theme.js — how the phone looks

One feature, two files, one doc (the same arrangement `layouts.css` and
`layouts.js` already use):

- **`client/theme.css`** — every colour the client uses, across two themes,
  the coloured-controls switch, and two fills. Nothing in it positions
  anything.
- **`client/theme.js`** — which of those are in force right now, and the
  colour each SET wears.

Built in **build round R3** (owner-approved 2026-08-07), answering the round's
open question **P4** with "the phone's theme is chosen ON THE DESKTOP ONLY"
and **P5** with "adopt the proposed set-colour palette and tune later". THE
AXES WERE CORRECTED on **2026-08-08** — see below.

**He tuned the palette the next day** (owner, 2026-08-07):

> "one boje koje si osmislio — kada je DARK tema treba da budu jako tamne
> nijanse, dakle mali lightness/brightness; a ovaj mod LIGHT treba da ima jako
> svetla slova, velikim, u boji, dakle ona klasična jaka. Sto saturacija ne
> treba ni u jednom modu."

Two sentences, two pages, and they cannot both be true of one table of
colours: on a dark page the colour is the BODY of the button and the white
label does the reading, so it must be dark; on a light page the colour is the
INK, so it must be strong. So the coloured look kept two palettes, one per
theme, and the lift that makes a colour readable stopped bleeding it white.
See [The set colours](#the-set-colours).

**Then he corrected the SHAPE itself, a day later** (owner, 2026-08-08):

> "što se tiče teme — teme postoje samo dve, svetla i tamna, i to je onaj
> switcher sunce mesec. zatim dalje pričam samo za ove komande sa kojim
> komuniciramo sa aplikacijom i za onaj kružni meni koji biramo — on može da
> bude obojen, neobojen, i može da bude transparentan ili pun. dakle to je
> ukupno osam kombinacija za ove dugmiće: tamna tema, svetla tema, puno,
> prazno, obojeno, neobojeno."

The 2026-08-07 shape had folded the colour question into a FOURTH theme
value (`colored` = dark page + colour, `colored-light` = light page +
colour). It rendered the same eight looks by accident, but it said the page
has four themes when the owner's own model is two themes plus two switches
that belong to the CONTROLS — the D-pad groups and the radial wheel — not the
page. `data-colored` is now its own axis, independent of `data-theme` and
`data-fill` alike.

## The one rule everything else follows

**The desktop decides; the phone obeys.** The look arrives in every `config`
frame as `ui = {theme, colored, fill, colors}` and that is the only input.
There is no theme menu on the phone, nothing is auto-detected, and the
device's own dark/light preference is deliberately ignored — one source of
truth means the owner never has to work out which of two places is winning.
It is set in the desktop **Settings → APPEARANCE** card
(`server/gui/settings_window.py`) and built by `config.ui_config()`.

## The three axes

| Attribute on `<body>` | Values | What it decides |
|---|---|---|
| `data-theme` | `dark` · `light` | surfaces, ink, shadows — the sun/moon switcher |
| `data-colored` | `true` · `false` | do the D-pad groups + radial wheel wear each set's own colour |
| `data-fill` | `transparent` · `full` | outlined buttons, or filled ones |

They are independent, so there are **eight** real renderings of every control
— and the audit measures all eight (below).

- **dark** — today's look, unchanged. It is the `:root` block, and `light` is
  an override of it.
- **light** — elevation INVERTS (DESIGN.md): the raised card is the whitest
  thing and the page sits a step below it. The accent is deepened to `#0369a1`
  because the dark theme's `#38bdf8` sits at 2.2:1 on white. The icon and
  label shadows flip from black to white — the controls float over the PC's
  own screen, which can be any colour, so dark ink over a dark window needs a
  light halo or it vanishes.
- **colored (`data-colored="true"`)** — every set wearing its own colour, on
  top of WHICHEVER theme is in force. It shares every surface token with the
  page's own theme (a light page is a light page whether or not the buttons
  are coloured; duplicating twenty tokens would be two files to retune the day
  the page grey changes) and adds nothing but the per-set rules at the bottom
  of theme.css. The palette a coloured look wears is picked by `data-theme`
  ALONE (dark shades on `dark`, strong inks on `light` — see below), never by
  a fourth theme name.

`body[data-colored="true"]` is ONE selector for both surfaces, because every
value its rules use is computed by `theme.js` against the surface actually in
force. Nothing about the light page needs a rule of its own, and a duplicated
block per theme would be the first thing to fall out of step.

`full` is carried by ONE token. `--glass-fill` (and its three relatives) is
what every button, chip and wheel item already paints itself with, so
`body[data-fill="full"]` re-points those four at `--fill-solid` and no rule
anywhere else needs to know which fill is active.

## Backward compatibility (owner correction 2026-08-08)

Two places can still hand this file the OLD four-value `theme`
(`"colored"` / `"colored-light"`), and both are translated, never reset,
because the owner's SAVED CHOICE must not silently become something else:

- **A server not yet rebuilt.** `client/theme.js` → `legacyTheme()` runs
  inside `mergedUi()` — the one point every incoming `ui` object passes
  through — and turns `theme: "colored"` into `{theme: "dark", colored:
  true}`, `"colored-light"` into `{theme: "light", colored: true}`.
- **This device's OWN cache** (`prefGet("uiLook")`), written by an older page
  before this build ever ran. `restoreUi()` reads it at load, before any
  socket exists, so a server-side translation alone could never reach it —
  it goes through the SAME `mergedUi()` / `legacyTheme()` path.

The server side of the same fix is `config._migrate_legacy_ui()` — see
[config.md](../../server/__about/config.md).

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
  on that translucent surface. `--set-line` (`lineOn()`) is the same colour
  with only its **HSL lightness** walked away from the surface — up on a dark
  page, down on a light one — stopping at the FIRST step that clears **7:1
  (AAA)**, not 4.5, because these buttons float over the PC's own unknowable
  screen and AAA is the margin an unknown backdrop is owed.
  **Lightness, not a mix toward white** (owner correction 2026-08-07): mixing
  toward white raises lightness AND drains saturation, so a palette of dark
  shades would have arrived on the phone as a row of greys — the previous
  version's own comment claimed "hue and saturation ride along" and that was
  simply false of a straight RGB mix. Walking lightness in HSL keeps both, so
  a dark teal lifts to a lighter teal, and that is what lets the dark page's
  palette be as dark as the owner asked while the OUTLINED look stays
  legible.
- **Filled**: the fill really is the hue, so black-or-white ink (`inkOn()`,
  whichever of the two wins on that exact colour) is correct in principle —
  but for a hue sitting near the luminance crossover (~0.179) BOTH options
  read poorly at almost the same weak ratio, and no ink choice can rescue
  that (VSCode's `#3B82F6` again: even its BETTER ink measured 4.27:1, under
  AA). The only remaining lever is the fill's own lightness: `--set-fill`
  (`fillOn()`) walks it the SHORTER way — darker or lighter, whichever clears
  AA in fewer steps — so the set stays unmistakably its own hue at its own
  saturation. `--set-ink` is then chosen against that same surface, never the
  raw hue. The border still wears the untouched `--set-color`, so a 1px ring
  never drifts from the desktop's own table.
  **Neither shipped palette triggers it today** — both are chosen at
  lightnesses that clear AA on their own, so what the desktop shows is
  exactly what the phone paints. `fillOn` stays as the net under a colour the
  owner retunes tomorrow, because the day he does is the day nobody is
  measuring.
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

**Two tables, one per surface** (`server/config.py` — owner correction
2026-08-07, replacing the single table he had adopted the day before). The
DESKTOP resolves which one a theme wears (`config.set_colors`), so the wire
shape never changed: `ui.colors` is still one flat `{set: hex}` map and this
page has no idea two tables exist. Sending both and letting the phone choose
would have put the same decision in two places, and the phone's copy is the
one that drifts.

**`SET_COLORS_DARK`** — dark shades, HSL lightness **22–40%**, saturation
capped at **66%**. The floor is measured, not taste: darker than that and the
fill stops reading as a button against the `#0f172a` page. The ceiling is
where a white label stops clearing AA on it.

Mouse `#1D6A86` · Input `#1C693C` · Settings `#4B5B71` · Edit `#572B82` ·
Attach `#7D561C` · Navigate `#175E57` · Media `#86282E` · Windows `#354297` ·
VSCode `#1C3878` · Chrome `#5D5113` · Explorer `#944D1E` · Claude `#8D4834` ·
Cursor `#7E2A57`

**`SET_COLORS_LIGHT`** — the classic strong inks, lightness **26–54%**,
saturation capped at **72%**: vivid enough to be "ona klasična jaka" and dark
enough to be read on `#eceef6`.

Mouse `#186B89` · Input `#14713B` · Settings `#476185` · Edit `#702BB6` ·
Attach `#C38322` · Navigate `#146F65` · Media `#BA2630` · Windows `#4356D0` ·
VSCode `#204DB6` · Chrome `#A58E1D` · Explorer `#DC7028` · Claude `#A3472E` ·
Cursor `#B02971`

Neither reaches 100% saturation, in either mode — that was the third of his
three sentences. The two ceilings differ because the jobs differ: 72% is what
the classic strong inks actually measure, and on a dark page a shade that
saturated turns muddy as it darkens.

**Hue AND lightness separate the sets that share the wheel** — the one
property of the first palette worth keeping. The four blues (Mouse 196,
Settings 215, VSCode 222, Windows 232) and the four warms (Claude 13,
Explorer 24, Attach 36, Chrome 50) are pulled apart in lightness as well as
hue, so an eye that cannot tell two hues apart still has a second signal.

A **custom** set is not in either table and never will be — the owner names his
own sets in the Controls editor. `setColors()` therefore hands each unnamed
set the next colour of the palette IN FORCE that nothing already wears, in the
order the sets arrive, cycling if he ever makes more sets than there are
colours. One table per surface, no third list to keep in step.

**The ACTIVE halo rides the LIFTED colour too** (same correction). `--set-glow`
used to be the raw hex at 0.30 alpha, which was fine while the palette was
bright and became no signal at all the moment it went dark — a `#1C3878` navy
halo on a `#0f172a` page. It is now derived from `--set-line`, which is by
construction far from its surface (lighter on a dark page, darker on a light
one), so "switched on" stays visible whichever theme is in force, without a
token per theme.

`paintSet(el, name, surfaceVar)` writes `--set-color`, `--set-fill`,
`--set-ink`, `--set-line` and `--set-glow` onto the element that OWNS a set —
a D-pad group, a wheel item — so its four buttons, its category button and
all their labels inherit them in one write instead of five. `surfaceVar`
names the token the caller's OWN buttons are painted with (`--glass-fill` for
a D-pad button, `--glass-strong` for a wheel item — really different
surfaces, 0.20 vs 0.85 of the same navy, and therefore different lifts); the
caller states it because it is the only one that knows. The properties are
written in every look and READ only when `data-colored="true"`: a rule that
has to un-set itself when the axis changes is a rule that will one day be
left behind.

## The ink is COMPUTED, never tabled

`inkOn(surface)` returns `#0b1220` or `#ffffff`, whichever actually has the
better contrast on that exact surface — black and white cross over at a
relative luminance of about **0.179**. That is what keeps a coloured look
readable without anyone tuning anything: the owner may retune the palette on
the desktop whenever he likes — he did, one day after adopting the first one,
and not one ink rule had to change — and a hand-written ink per colour would
have been wrong the first time he did (rules/CODE.md → Compute, Don't
Generate). `lineOn()`
and `fillOn()` (above) are the same idea applied to the two surfaces that
actually exist — a translucent tint, and a fill that may need its own small
nudge — rather than one function pretending both are the same question.

## The cache — and why silence is not an instruction

The choice is stored per device (`prefGet`/`prefSet` → the shell's
SharedPreferences, localStorage in a dev browser) and re-applied at load,
before the socket has said anything. Without it the page would paint the
previous theme for the third of a second it takes to connect — a flash on
every single connect.

The cache is a HEAD START, not an authority — but it IS the fallback, and
that distinction is the product bug a third independent grader found by
measuring pixels (2026-08-07). `applyUi` used to default every missing field
to `UI_DEFAULT`, so:

| what the server said | what the phone used to do | what it does now |
|---|---|---|
| `ui = {theme, fill, colors}` | obey | obey — unchanged |
| **no `ui` at all** | **reset to dark/outlined** | **nothing at all** |
| **`ui = {theme}` only** | **reset the fill and the colours** | **merge; only the theme moves** |

The owner would choose Filled in the desktop's Appearance card, see the phone
change, and see it change back within half a second. The old code justified
itself with "a server that stops sending `ui` (an older PC) must put the phone
back to the look that PC actually renders for", and that sentence is not true
of anything: the PC renders nothing for the phone — the phone paints itself. A
server too old to have a `phone_theme` setting has no opinion about appearance
to impose, and replacing the owner's only choice with a compiled-in constant is
not obedience, it is a reset.

So the rule is **ignore-or-merge**, and `UI_DEFAULT` is the SEED a device that
has never been told anything is born with (`restoreUi`), never a fallback:

- **no `ui`** → `applyUi` returns immediately. No state change, no pref write,
  no repaint. The look in force stays in force.
- **partial `ui`** → `mergedUi(ui, next)` lays it over the look in force, field
  by field, so naming the theme cannot silently discard the fill or the set
  colours.

`client/connection.js` passes `msg.ui` across EXACTLY as it arrived, absence
included (it used to write `msg.ui || null`) — deciding what silence means
belongs here, beside the look and the cache that remembers it.

**The desktop still wins whenever it speaks.** A reconnect carrying a full
`ui` overrides whatever the phone was wearing, which is the whole "the desktop
decides" rule; what changed is only that saying nothing is no longer a way of
saying "dark, outlined".

## What proves it

`tests/test_layout_audit.py` sweeps **all eight looks**. Its CONTRAST check
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
**every** colour of the palette the theme in force actually ships (the audit
fetches it through `config.ui_config()`, so the light page is never measured
with the dark table), not only the two or three a fixture happens to show — a set the owner darkens tomorrow is
measured today, on both surfaces, in every look.

**And every look-named screenshot now has to BE that look** (`_shoot`, same
round). Twelve `Controls*` pictures carried a theme and a fill in their
filenames and nothing had ever compared those two words against
`body.dataset.theme` / `body.dataset.fill` at the moment the shutter fired —
so two of the twelve showed a different look while every check printed PASS,
and three rounds of graders were handed them. `_shoot` asserts first and FAILS
the audit (not warns) when the page has drifted, naming both looks; the picture
is still written, because a grader has to be able to see what was measured.
`_apply_look` also moves the DESKTOP's own `phone_theme`/`phone_fill` — the
audit runs the real server in-process, so the look it asks for is the look
every later `config` frame carries, instead of the audit fighting its own
server.

## Related

- [style.css](style.md) — shape and position; it reads these tokens and names
  no colour of its own.
- [connection.js](connection.md) — where `config.ui` arrives.
- [controls.js](controls.md) — calls `paintSet` per group and per wheel item.
- [sets.js](sets.md) — what the set list is in the first place.
- `server/gui/theme.py` — the desktop's own two palettes, same family.
- [config.py](../../server/__about/config.md) — where the two set palettes
  live and which theme wears which.
