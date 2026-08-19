# `preview.html` — the specimen board

One look, drawn with the **product's own files**. The lab loads eight of these,
one per rendering (dark/light × plain/coloured × outlined/filled).

## What it loads, and why all of it

`client/theme.css`, `client/style.css`, `client/panels.css`,
`client/ledger-panel.css` and `client/theme.js` — the real cascade, and the
real paint-time arithmetic.

Half of what a coloured control looks like is **computed when it is painted**:
the ink walked in lightness until it reads on the surface it really lands on,
the fill nudged when neither black nor white clears AA on the raw hue, and the
shadow taken as the ink's opposite. A board that re-implemented any of that
would be showing the owner a second opinion of his own page. So `theme.js` runs
here exactly as it runs on the phone, and `paintSet` paints each specimen group.

Four stubs stand in for what only the real page has — `prefGet`, `prefSet`,
`setCanvasBackdrop` and the three set lists. Deliberately empty: a lab that
remembered a look between reloads would be showing a look the PC never sent.

## What is on the bench

- **A group per set** (Mouse, Claude, Attach, Input) carrying every state a
  control has: off, ON, held, ON+held, a chord button whose label is its whole
  face, and the smaller dashed set switcher. Four sets, so the light fills that
  need black ink are on screen beside the dark ones that need white.
- **A wall of EVERY shipped set**, one switcher each (round 2, 2026-08-19). He
  asked which sets come out with black letters and a black icon; four specimens
  could not answer it, because the palette has fourteen colours and the ones
  that take black ink are the light ones. Here they all are, in whichever look
  is on screen, so the question is answered by LOOKING.
- **The wheel** — four set circles, one of them current.
- **A panel card** — the surface every chooser and setting is drawn on, with a
  chosen row's accent edge.
- **The ledger's five state dots**, the one place five colours must be told
  apart from each other on one list — **on a card**, because that is where they
  are on the phone. Drawn bare on the board their `--text-primary` ink landed
  straight on whatever the PC screen was showing, and a grader photographed all
  five labels invisible over a white document. A defect of the BENCH, not of the
  product: the ledger is a panel, and its ink is measured against the panel's
  own surface.
- **The status toast**, the real `#status` element with its real fixed
  position, in whichever state the lab's Toast selector names — **and the
  sentence follows the state**. It used to be one fixed line (a layout refusal,
  in red) under whichever class was chosen, so picking "connecting" showed an
  amber pill still saying a window would not land. A specimen that says the
  wrong thing is a specimen you cannot judge.

## How much is on it

Two sizes, and what changes is only **how many D-pad groups** are laid out: one
dark-ink set and one light-ink set, or all four. Eight cards on one screen is
eight small cards, and four full groups is what actually makes a card too tall
to read.

Everything else is on the board either way — the wall of set colours, the wheel,
the panel card, the ledger dots — because the sidebar can point at what a value
touches, and a row that pointed at a card this bench happened to leave out would
outline nothing and read as a broken feature.

## Fit — nothing scrolls inside a card

The card is whatever size the lab's grid gave it, and the board has to be inside
it, so the whole document is **zoomed** down (or up) until it is. `zoom` and not
`transform: scale`, because zoom re-lays-out: the board's own `auto-fit` columns
get more room at a smaller zoom, which a transform would not do. `position:
fixed` — the toast, the PC screen — rides along, which a transform would have
broken.

**A bisection, not a walk.** The first version stepped the zoom by
`have / need` and it oscillated, because growing the board makes it TALLER: a
larger zoom means fewer CSS pixels across, the `auto-fit` columns collapse, and
the height jumps. It settled wherever the seventh pass happened to leave it, and
a grader measured **40 % of every card empty at the owner's own screen**. What
saves it is that *does it fit at this zoom* is MONOTONE — the board's pixel
height never falls as the zoom rises, and the frame's height does not move at
all — so the largest zoom that fits can simply be searched for. Nine halvings of
[floor, ceiling] land within a thousandth of it. Measured after: 1–2 % of a card
empty at 3072×1600, at 2458×1280 @1.25 and at 1366×768.

Two traps live in the measurement and both were walked into once each:

- **not** `documentElement.scrollHeight`. `#screen` is `position: fixed;
  inset: 0` and therefore always exactly one viewport tall, so the scroll height
  can never report LESS than the card — which is why the first version never
  grew and left the bottom half of every card empty.
- **not** `documentElement.clientHeight` as the other side of the comparison.
  Under `zoom` those two live in different coordinate spaces, and comparing them
  made a board that overflowed by half its wall look like a board that fitted.
  `getBoundingClientRect()` is already multiplied by the zoom, so
  `window.innerHeight` is its honest counterpart.

Below `FIT_FLOOR` (0.45) a control stops being a specimen — a button at a third
of its size says nothing about whether its label can be read — so the board does
not shrink further. It reports `floored` instead, and the LAB answers by giving
every card the height its board needs and letting the wall scroll
([design_lab.md](design_lab.md)). One scrollbar for the wall, never eight inside
the cards.

Each frame also reports the zoom it worked out, and the lab hands back the
smallest of the eight (`scale`), because a wall whose cards are at eight sizes
is not comparing anything.

## Pointing

`point` outlines everything a sidebar row touches, for exactly as long as the
pointer is on that row. The outline is the lab's colour and the ONE thing on
this page that is not the product's — `outline` and not `border`, so it takes no
space and cannot move the specimen it is pointing at, and `pointAt("")` clears
it, so it is never in a photograph of a look.

Two of its selectors are the board's own: **`:dark-ink`** and **`:light-ink`**
are answered from what `paintSet` really produced (`markInk` reads the shadow it
wrote — a white shadow means black letters), so the row about the white shadow
outlines the sets that really take black ink today rather than a list of names
written down once.

## The two shadow colours, live

They are `const`s in `client/theme.js`, so the page cannot be asked to recompute
with a different pair — the file has already been read. What the bench does
instead, and what a bench may do that a product may not, is **substitute**:
`paintSet` has just written `rgb(<base> / a)` into four custom properties, and
swapping the base triple for the one he is dragging gives exactly what a Save
and a reload would give. Nothing in `client/` knows it happens.

## What the bench owns, and what it does not

This page's own stylesheet contains **positions only** — where a specimen sits.
It names no colour, no radius and no shadow. Three positioning decisions are
worth knowing about:

- `#screen` — the element the stream is drawn into on the phone, wearing a
  picture chosen in the lab instead of a video frame. It is what makes "is this
  still legible over a white document" a question with an answer.
- `.bench-row .wheel-item { position: static }` — a wheel circle is
  `position: absolute` in the product because `client/controls.js` computes the
  ring when the wheel opens; on a bench with no wheel every circle would land on
  the same spot. Only the position is neutralised; size, fill, border and ink
  stay the product's.
- `--board-top` — the board starts below the toast's **measured** bottom edge,
  re-measured on resize and on every toast change. A hand-picked constant let
  the pill sit on the first row of buttons the first time this page was
  photographed, which is the law's own failure (nothing may overlap anything)
  committed by the tool built to find it.

## What the lab tells it

Each message is applied where the cascade puts it: `look` (through `applyUi`,
the one door, so the set-colour cache resets with it), `shape` (→ the document
element), `colour` (→ the **body's** inline style, because the light theme
declares its values on `body[data-theme="light"]` and an override on `:root`
would lose to it), `sets`, `jscolor` (the substitution above), `bench`, `fit`,
`scale`, `point`, `backdrop` and `toast`.

Up: [tools/___tools.md](../___tools.md) ·
Beside: [design_lab.md](design_lab.md)
