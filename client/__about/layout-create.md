# Layout creation

**Scripts:** [layout-create.js](../layout-create.js) ·
[layout-create.css](../layout-create.css) ·
**Flow:** [diagrams](../__flow/layout-create.md) ·
**Folder:** [Client](../___client.md) ·
**Living with layouts:** [Layouts](layouts.md)

One feature, two files, one doc — the `layouts.css`/`layouts.js` precedent.
The stylesheet holds only what the creation panel's ROWS need beyond the
layout list's own (`.lay-item` / `.lay-item-main`, reused rather than copied):
the indent a tab wears under its window, the dim an unavailable control wears,
and `touch-action` put back, because a row here is never carried and the list
must still scroll.

## Purpose

Making a layout — and only that. The source chooser, the armed canvas tap, the
slot panel, and the single `layout_create` that ends the session.

Split out of [Layouts](layouts.md) on 2026-08-08, when the ✕ chooser (task 116)
pushed `layouts.js` past THE STRUCTURE LAW's 1,000 lines. The boundary is a
responsibility, not an arithmetic cut: this file is a WIZARD. It owns one piece
of state (`creating`), gathers slots across several taps, and is finished the
moment the layout exists. `layouts.js` is everything you do once layouts DO
exist — the bar, the list, the ✕, the member chooser — and
[Layout Settings](layout-settings.md) is what a layout can be ASKED once it
does (2026-08-09).

Both halves render into the same overlay (`#layout-panel`) and share its
vocabulary, so the phone never has two competing card styles.

## Connections

### Uses

- [Layouts](layouts.md) — `layPanel`, `closeLayoutPanel`, `layChip`,
  `chooserBtn`, `nameField`, `showLayLoading` / `hideLayLoading`, and the
  `.lay-item` / `.lay-item-main` ROW markup its stylesheet owns. (`titleChip`
  and `.lay-chip.lay-title` — the wrapping title pill both lists used to be
  made of — were DELETED on 2026-08-09: this panel was their only caller, and
  task 168 turned both lists into real rows.)
- [Controls](controls.md) — `keepFocus`, `svg`, `showToast`
- [State](state.md) — `send`, `layoutArm`
- [Loading](loading.md) — `creating` (the session object lives there)
- [Grids](grids.md) — `GRID_CELLS`, how many slots a template needs

### Used by

- [Gestures](gestures.md) — an armed canvas tap sends `layout_pick`, then
  calls `refreshNewlayButton()`
- [Connection](connection.md) — `handleLayoutOffer(msg)` on every
  `layout_offer` frame
- [Layouts](layouts.md) — the backdrop tap cancels a creation session rather
  than closing the panel under it

## Key Functions & Data

| Name | What it does |
|------|--------------|
| `creating` | The whole session: `{source, entries, slots, name, mode, grid, orient, awaitingTap}`. `null` when no layout is being made. Declared in [Loading](loading.md), which needs it for the overlay. |
| `newCreation(source)` | A fresh session, `"list"` or `"tap"`. |
| `openSourceChooser()` | The two-act card: **From a list** (`layout_list`) or **Tap a window**. |
| `armNextTap()` | `layoutArm = true` — the NEXT canvas tap picks a window instead of moving the cursor. One shot. |
| `handleLayoutOffer(msg)` | Both answers: `entries` (the whole list) or one tapped `target`/`tab`. |
| `slotFromOffer` / `slotFromEntry` | The two sources reduced to ONE slot shape, so the panel below never asks where a slot came from. |
| `cellsNeeded()` | How many slots this mode still wants — 1 for solo, the template's cell count for a grid. |
| `availableMembers()` | How many members this desktop can really fill — the cap on the shape chooser AND the count in the list header. `null` for the tap source, where nothing is enumerated. |
| `ownTabConflict(slot)` | Is this slot the window of a chosen tab, or the tab of a chosen window? Those two cannot stand together. |
| `entryRow(opts)` | One row of either list: `{label, icon, tab, note, selected, off, onTap}`. A tab is drawn indented and carries no app icon. |
| `renderCreationPanel()` | The slot panel: mode, orientation, the chosen slots, the name field, Create. |
| `cancelCreation(silent)` | Ends the session and clears `layoutArm` — the + button's second tap, the backdrop tap, and Cancel all land here. |
| `refreshNewlayButton()` | Lights the + button while a session or an armed tap is live. |
| `keepRowTap(el, onTap)` | Task 227b's row activator — **now [client/row-tap.js](row-tap.md)**, the whole page's, not this panel's. Used by every row of every creation-panel list (`entryRow`, `recentRow`, `recentHistoryRow`), never `keepFocus`. It was moved out on 2026-08-15: the owner met the identical defect in the notification-voice card, and a rule kept inside one panel's file is read only by somebody already in that file. |
| `openRecentHistoryPanel()` / `handleLayoutRecent(msg)` | Task 228's Recent source: asks the server for `layout_history` (`layout_recent`) and shows it; a tap sends `layout_recent_use {id}` — matching, creating and the found/missing toast all happen server-side. Off the birth radial since 2026-08-12 (owner), panel and protocol kept whole. |

## Design Decisions

- **A Recent row's trailing fact no longer starves its name** (grader flag c,
  task 233): `.lc-note` (shared with every other row's trailing fact) had no
  width cap, and the Recent-history row's note can be a full relative time —
  unbounded, it took whatever room its own text needed and left the NAME to
  shrink first, the thing he actually reads on that row. `recentHistoryRow`
  now tags it `lc-recent-note` too, a narrower selector (`client/layout-create.css`)
  that caps and ellipses the note itself instead.
- **Two sources, one slot shape.** A window picked from the list and a window
  tapped on the stream reach the panel as the same object. Everything after
  the pick is written once.

- **The armed tap is one shot.** `layoutArm` clears the moment the tap is
  spent, so a forgotten arm can never turn a later cursor move into a pick.

- **A grid takes one tap per cell.** `cellsNeeded()` is what the panel counts
  against, and its label says which cell is being asked for — "Tap window 2 of
  4" — because a silent wait for more taps reads as a broken button.

- **The shape chooser is capped by what can fill it** (owner report
  2026-08-09, task 166: *"it offers a grid of 4 when the desktop holds 3"*).
  There was no cap of any kind — the 2/3/4 chips were an unconditional
  literal, `cellsNeeded()` read the mode and never looked at what was open,
  and the token `entries.length` appeared nowhere in the client.

  **The quantity is not `entries.length`**, and that is the whole subtlety: a
  VS Code with three tabs emits FOUR entries (the window plus its tabs) and
  still cannot yield four independent members. What a window is worth is *the
  tabs that can be extracted, plus the window itself only if at least one tab
  stays in it* — take k of its N tabs and you hold k windows plus the original
  while `k < N`, which is **N** either way. So a window offering N ≥ 2 tabs is
  worth N, a window offering none is worth 1, and `availableMembers()` sums
  that over the windows. (Since task 167 the server never offers a lone tab; a
  `1` could only come from an older PC, and 1 is the honest answer for it too.)

  A shape that cannot be filled is not drawn, the missing chips are explained
  in one line, and a chosen shape the desk can no longer fill is stepped down
  rather than left unreachable.

- **An unavailable control says so, twice.** A not-ready Create used to carry
  no disabled state, no dimming and no word: it looked live and swallowed the
  tap, which is the half the owner actually feels. It is dimmed (`lc-off`,
  `aria-disabled`) **and** it answers a tap with what is missing — "Pick one
  more window first". It deliberately stays tappable: a truly disabled button
  cannot answer, and "why is nothing happening" is the complaint.

- **A window and one of its own tabs cannot both be chosen** (task 167). The
  tab is torn out of the very window standing in the cell beside it, so the
  layout would hold one window twice — and when extraction fails (six visible
  seconds of synthetic mouse drag) the fallback IS that window, so both cells
  name it outright. Conflicting rows are dimmed and refuse with a word. Two
  different tabs of one window are fine and are the point of tab layouts.

- **A tab is drawn INDENTED under its window, in both lists** (owner
  2026-08-09, task 168, in translation): *"the indentation stays — a column.
  It does not have to be the same row as its parent, because a sub-tab of a
  window does NOT belong to the same kin group as its parent; that is exactly
  why a minimal indent is allowed… Right now there are arrows, but that is
  less noticeable and less intuitive."*

  Both lists were a wrapping FLOW of pills, which has no per-row box to indent
  at all — a tab was marked by a literal `"↳ "` glued to its title. They are
  real rows now; his kin ruling is what makes the narrower child legal under
  task 163, and the indent is exactly the icon column (20 px icon + 10 px gap)
  so a tab's title lands under its parent's title while its box sits visibly
  further in. In the CHOSEN list the parent is never a row beside it — a
  window and its own tab can no longer be chosen together — and the indent
  there says the thing that still matters at a glance: this member is a tab.
  Slot ORDER is never re-grouped; slot 1 names the layout and each one after
  it is a cell.

- **The icon belongs to the window.** It used to be drawn for the wrong one of
  the two: a tab wore its PARENT's app icon among the chosen slots and no icon
  at all in the list below — the same tab drawn two ways, one of them claiming
  to be an app. A tab is marked by the indent and by nothing else.

- **A minimized window says why it shows no tabs.** Windows reports it as
  having no size, so it enumerates zero tabs whatever it holds; the server
  refuses to ask and sends `tabs_hidden` ([UIA](../../server/__about/uia.md)),
  and the row carries a `minimized` note with one line under the list. A list
  that silently changes shape between two openings is the defect.

- **The name is prefilled and overridable** (owner 2026-08-05): the first
  slot's window title is offered, an empty field keeps it, and anything he
  types wins. `Layout.title` on the server keeps the ORIGINAL title whatever
  he renames it to — the app-set match reads that, never the name.

- **The loading overlay covers the real work, not the reply.** Tab extraction
  takes visible seconds on the PC; `showLayLoading` opens before the message
  goes out and closes when the streamed screen actually stops moving
  ([Loading](loading.md)).

## A scrolling list may not live inside a columned card (2026-08-09)

Found by PHOTOGRAPHING this panel at 915×412 — this round's own verification,
not a report. The landscape reflow of task 172 gave the card `column-count: 2`,
which makes it a **fragmentainer**, while the window list inside it is a
**scroll container**. The two do not compose, and the picture says it plainly:
the fourth of six rows came out sliced through the middle, ten pixels above the
"Shape:" block in the same column, with rows five and six nowhere and no
scrollbar to say they existed. Measured in the real Chromium this app runs in —
a scroller inside a multicol is not clipped by its own box at all (`overflow:
hidden` does not clip it either, and `column-span: all` does not fix it), and
the same list with twenty windows put fourteen rows off the bottom of the
screen while the card reported no scroll of its own to make.

The columns are still right for this panel (one column does not fit it in
either landscape size — 630 px of content in a 377 px card at 915×412, 749 px
in 734 px on a tablet, which is BUG A with 155 px and 520 px of width standing
idle). So the card keeps two columns and **stops being a fragmentainer**: an
explicit FLEX split (`.lc-split` → `.lc-cols` → `.lc-side` + `.lc-main`), whose
children are ordinary boxes a scroller works inside.

What that buys, beyond the fix: the list gets a whole column of its own height
instead of an arbitrary 38vh, its own header finally stands above it (the
multicol left the caption in the LEFT column introducing a list on the right),
and the actions row sits under both columns so **Create can never fall below a
fold**. Each half scrolls on its own when it must — rung 4, and genuinely
earned on a 412 px-tall screen holding a name field, four shape chips, two
orientation chips, a window list and two buttons.

Three details are deliberate and measured:

- **Only the LIST source splits.** A "Tap a window" session has nothing that
  scrolls, so it keeps the `card-columns` behaviour that was measured for it;
  a split there would leave one column empty.
- **The halves are `flex: 1 1 0`, equal.** The rows of BOTH halves are one kin
  group under task 163 (`__kinRows` groups by indent, not by column), so halves
  of different widths would make the chosen rows and the list rows different
  sizes — the very defect that rule exists to stop.
- **The halves are `display: block`, not flex columns.** A flex column makes
  every child shrinkable, and the first thing that shrank was the Name textarea
  — `panels.css` gives it a 64 px height in landscape and it came out ~40 px,
  cutting the placeholder through the middle (seen in this round's own
  screenshot, one fix after the other).

Portrait is untouched by construction: `.lc-split` and `.lc-cols` are plain
blocks outside the landscape query, so the halves stack in build order. Gate:
`__scrollInColumns` in `tests/_audit_js.py`, run on the creation-list staging
at all four audited viewports — a structural rule with no number to tune, which
catches any future panel that puts a scroller in a columned card.

## The footer stopped eating the column's height (owner 2026-08-10, task 214)

What he saw on a landscape tablet: on the New layout card the "Shape:" pill row
at the bottom left was CUT — the pills half-visible, with the Cancel/Create row
sitting across them. Measured at 915×412 before the fix: the left column held
368 px of content in 282, hiding 86, and the two orientation chips ended at
y=402 while the column ended at 321 and the actions row began at 336. He read
that as the footer drawn ON TOP of the content; mechanically it was the column
scrolling — rung 4 of the ladder — while rungs 1 and 2 still had moves left.

**His own second suggestion is the fix, and it is rung 2**: Cancel and Create go
into a VERTICAL container at the far right, one under the other, so the row they
used to occupy is given back to the content. In landscape the card becomes a ROW
— the two content columns, then the actions column — which costs width, of which
this card has 660 px standing idle on his tablet and 16 px on the narrowest
phone, and buys back the footer's whole 51 px of height at every size.

**His first suggestion — make the footer transparent so the pills show through —
is deliberately not taken**: the pills would still be UNDER two buttons and
untappable, so it would hide the symptom and keep the defect. An element you can
see but cannot press is worse than one you can see is missing.

Rung 1 comes first anyway: a card with 22 px of pure air top and bottom, a 52 px
name field and 6 px row margins is what a 412 px-tall screen cannot afford.
Trimming that air plus the footer's height takes the left column from 86 px
hidden to none — the column no longer scrolls at any size this project ships to.
Nothing readable got smaller. The two actions are also one kin group in one
column and take the same width (task 156's rule, ALG-5).

## A THIRD source: New — a window that is not open yet (owner 2026-08-09, task 184)

> "recent imaju svi" <!-- lang-ok: owner quote -->

The source radial offers **New / Tap / List** (one word each, each with its
own drawn face in `icons.js` — his ruling that the SVG matters more than the
word; that array's ORDER is the fan's E / SE / S mapping since 2026-08-12, see
below). New asks the PC what it can open (`GET /recents`), draws the answer
grouped by app with each app's recents indented under its heading, and opens
the chosen one (`POST /recents/open`). The window that appears becomes a slot
and everything from there is the ordinary creation flow — nothing new on the
wire, because `layout_create` already resolves a slot from a handle.

The PC owns every hard part, including the honest per-app limits (Chrome offers
only New window / Incognito): [Recents](../../server/__about/recents.md).

A grid can be filled this way too — each cell is another thing opened, through
the same chip the tap source shows.

## And a window he JUST opened is already a slot (owner 2026-08-09, task 185)

He double-clicks an .xlsx through the stream, Excel opens, and the phone asks
"a layout with it?" — the chip is `client/window-offer.js`, the PC's side is
`server/layout_popup.py`. His yes lands in `startFromWindow`, which is the only
thing task 185 adds here: the creation panel he already knows, pre-seeded with
that window and offering the usual single/grid and portrait/landscape choices.
There is no second wizard.

Gates: `tests/test_birth_radial.py` (the phone half) and
`tests/test_layout_birth.py` (the PC half).

## The footer is pinned, the list scrolls (owner report 2026-08-11, task 227a)

A long window list scrolled Cancel/Create off with it — `.lay-card` was one
block (`max-height: 92vh; overflow-y: auto`) covering EVERYTHING, header
through footer, so a chosen row, the name field, the shape rows and a tall
list together could push the footer below the fold with nothing on screen
suggesting a further scroll would ever reach it.

Both creation renderers (`renderCreationPanel`, `renderRecentsPanel`,
`renderRecentHistoryPanel`) now wrap everything EXCEPT `.lay-actions` in one
`.lc-scrollwrap` div; `.lc-panel` (`layout-create.css`) turns the card itself
into a fixed-height flex COLUMN, so `.lc-scrollwrap` is the one child that
scrolls and `.lay-actions` — appended to `card` directly, always last — can
never be scrolled past. This coexists with two pre-existing reflows without
touching either:

- **The task-214 landscape split** (`.lc-split`, above) still turns the card
  into a row with its own two-column footer; `.lc-scrollwrap` there just
  takes `.lc-cols`'s old place as the flex child, and `.lc-cols` is
  unchanged inside it.
- **The short-landscape multicol reflow** (`panels.css`, `.card-columns`) —
  where the whole PANEL scrolls and the card must stay a plain fragmentainer
  — sets `.lc-scrollwrap { display: contents }` there, which removes the
  wrapper from the box tree while its children stay exactly where the
  multicol algorithm expects them.

Gate: `tests/test_creation_footer.py` — a REAL page in a real headless
Chromium, staged with a twenty-row list, at both target sizes (portrait
412×915, landscape 915×412); Cancel/Create's own bounding rects must sit
inside the viewport the instant the panel renders, with no scroll performed.

## A row must not steal the scroll (owner report 2026-08-11, task 227b)

Every row used `keepFocus` (`controls.js`) — the page's ordinary button
activator, which calls `preventDefault()` on `pointerdown` to guarantee real
touch activation. That same call is exactly what stops the browser from ever
recognising the touch as a scroll: the moment a finger landed on a row, the
row selected, and a drag over it never scrolled the list at all.

`keepRowTap` (above) is the row-only replacement: it never `preventDefault`s,
so the browser is free to start a scroll, and it decides on RELEASE, by
travel alone — under `ROW_TAP_SLOP` (12px) selects, past it (a scroll) does
not — reusing `pressVerdict` from `hold-gesture.js` rather than a second copy
of that rule (constraint 9). The `pointercancel` rescue still fires under
slop, so the Android edge-gesture theft (constraint 9) is defended on a row
exactly as it is on every other button.

Gate: `tests/test_row_tap.py` — extracts the REAL `keepRowTap` source out of
`client/row-tap.js` (between `ROW_TAP_GATE_START`/`_END` markers, never a
re-typed copy; the block lived in THIS file until 2026-08-15) and runs it in
node against the real `hold-gesture.js`. It also sweeps every named list on
the page, so a panel that goes back to `keepFocus` fails there instead of on
his device. It caught a real
bug during its own writing (`pressVerdict` was called with the raw pointer
event instead of `{x, y}`, so travel was always `NaN` and every drag
selected regardless).

## A FOURTH source: Recent — a layout already built before (owner report 2026-08-11, task 228)

Tap / List / New all build from what stands on the desk NOW; none of them
remember what he built YESTERDAY. **Recent** asks the server for its persisted
creation log
(`layout_recent {}`) and shows it (`renderRecentHistoryPanel`, reusing
`.lay-item` row styling and `keepRowTap`). A tap sends
`layout_recent_use {id}` and shows the ordinary loading cube — everything
else (matching the remembered members against what is open now, creating,
and the "N of M found" toast) happens entirely server-side; see
[Layout History](../../server/__about/layout_history.md).

**It is no longer ON the radial** (owner decision 2026-08-12). It rode the
centred ring as its fourth option for one day; when he reversed that ring for
an anchored three-option fan (see [Chrome](chrome.md)) he dropped Recent from
the options at the same time. Everything BEHIND it was deliberately kept —
`openRecentHistoryPanel`, `handleLayoutRecent`, `renderRecentHistoryPanel`,
the `layout_recent` / `layout_recent_use` messages and the PC's whole history
file — so the next door onto this list costs one call and no server work.
Only the entry point was withdrawn.

Gate: `tests/test_layout_history.py` (the server half — dedupe, ranking,
re-match, each proven by planting its own defect).
