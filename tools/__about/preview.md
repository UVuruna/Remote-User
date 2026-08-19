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
- **The wheel** — four set circles, one of them current.
- **A panel card** — the surface every chooser and setting is drawn on, with a
  chosen row's accent edge.
- **The ledger's five state dots**, the one place five colours must be told
  apart from each other on one list.
- **The status toast**, the real `#status` element with its real fixed
  position, in whichever state the lab's Toast selector names.

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

Four messages, each applied where the cascade puts it: `look` (through
`applyUi`, the one door, so the set-colour cache resets with it), `shape`
(→ the document element), `colour` (→ the **body's** inline style, because the
light theme declares its values on `body[data-theme="light"]` and an override
on `:root` would lose to it), `sets`, `backdrop` and `toast`.

Up: [tools/___tools.md](../___tools.md) ·
Beside: [design_lab.md](design_lab.md)
