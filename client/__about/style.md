# Style

**Script:** [Style (script)](../style.css) ·
**Flow:** [diagram](../__flow/style.md)

## Purpose

Every visual rule for the tablet page: design tokens (dark surface, one
accent — per root DESIGN.md), the connection-state pill, the invisible
keyboard-capture field, the offscreen video surface, the see-through control
buttons, the two-column D-pad groups (grid areas in landscape, a stacked
column in portrait), the category wheel, the "access from anywhere" banner +
guided wizard, the hide-all-controls mode and the Region grab's frame.
`touch-action: none` is set everywhere the page must own gestures itself
rather than the browser.

**The OVERLAY CARDS left this file on 2026-08-09** (THE STRUCTURE LAW — the
dictation card's per-language listen control pushed it past 1,000 lines).
`client/panels.css` now owns every full-screen panel and the `.sets-card` /
`.sets-row` / `.sets-list` / `.sets-done` vocabulary they share, including the
short-landscape reflow; it is documented with `panels.js` in
[Panels](panels.md). What stayed here is the WORKING SCREEN — everything the
user looks at while the PC is on screen. Notes below that describe a panel
card's rules still hold; the rules themselves live in the other file.

## Connections

### Uses

- Nothing project-internal — design tokens only, no external stylesheet, no
  build step

### Used by

- [Page Shell](index.md) — `<link rel="stylesheet" href="/static/style.css">`
- [State](state.md) — `setStatus()` toggles `#status`'s state classes
- [Render](render.md) — `updateViewport()` writes the live `--kb`/`--vtop`
  custom properties
- [Controls](controls.md) — toggles `body.hidden-controls`, `.ctl.active`
  (mode/keyboard/mic buttons), `.ctl.held` (a CLICK/HOLD mouse button while
  the finger keeps the PC button pressed — pressed-in scale, not the latched
  glow), `.wheel-item.current`, and the wizard's step classes
- [Web Layer](../../server/__about/web.md) — served from `/static/style.css` (the
  `StaticFiles` mount over `client/`)

## Design Decisions

- **Buttons stay see-through** (low-opacity fill, no backdrop blur) so the
  live screen underneath is never obscured; legibility comes from icon/text
  drop-shadows instead of an opaque backing.
- **`--kb` / `--vtop` are live custom properties [Render](render.md)'s
  `updateViewport()` writes** from `visualViewport` — the D-pad groups and
  top corners read them to clear the soft keyboard and any top system-bar
  offset, instead of the CSS guessing viewport geometry on its own.
- **`install.html` does not use this file** — it is self-contained (its own
  inline `<style>`) so the one page an app-less phone can reach never depends
  on anything else in the client.

## Layouts (Phase F+ step 1)
`#layout-bar` is a top-center pill (same glass look as the status pill);
`#layout-panel` / `.lay-card` / `.lay-chip` mirror the wizard card's styling; `.lay-item` rows, `.lay-ratio` and the `.asp-*` aspect widget (dashed screen box, accent region, round handles) belong to the layout list and aspect panel. `#lay-loading` is visible through the `open` class with an opacity transition, NEVER the `hidden` attribute — `hidden` would kill the cross-fade (owner 2026-08-03).
Both are hidden by Hide-all.

## Two live fixes (owner 2026-08-03)
- **The layout bar is bounded, not centered.** It used to be
  `left:50%` + `translateX(-50%)` + `max-width:62vw`, so a long layout name
  pushed the `›` arrow and the ✕ off the screen. It now spans
  `left/right: var(--space-m) + var(--corner) + var(--space-s)` — strictly
  between the Layout (+) and Hide corner buttons (`--corner` is the shared
  corner-button size token, also used by `.ctl`). Inside it, `#lay-frame` is
  the rectangle that holds BOTH the name and the ✕, and `#lay-name` wraps to
  at most two lines (`-webkit-line-clamp: 2`) — the name is the only thing
  that gives.
- **The orange bar over the top of the stream is gone.** `#kb` had transparent
  text, caret, background and border, but nothing turned off the FOCUS RING —
  `outline` is not painted with `color`, and Android WebView draws it in the
  system accent (orange on the owner's phone), so every keyboard opening put a
  full-width rectangle across the top. `outline`/`box-shadow` are now cleared
  in every focus state (and the shell also disables the platform focus
  highlight — see [Android (folder)](../../android/___android.md)).

## Build round R3 (2026-08-07) — themes

**Every colour left this file.** `theme.css` owns them now — four themes
(dark / light / colored / colored-light) times two fills (outlined / filled) —
and it is
loaded BEFORE this one so its `:root` tokens are already resolved. What stayed
in `:root` here is shape and geometry only: `--kb`, `--vtop`, `--topbar`,
`--corner`, `--radius-pill`, `--space-s`, `--space-m`.

Every hardcoded literal went with them. `.sets-card`/`.wiz-card`'s `#1E293B`
became `var(--card)`; `#06212E` and `#06121f` (ink on the accent) became
`var(--on-accent)`; `#22C55E` became `var(--success)`; the eleven
`rgb(15 23 42 / ..)` backdrops became `--bar` / `--scrim` / `--scrim-soft` /
`--dim-out` by what each one IS; the icon and label shadows became
`--ink-shadow` / `--lbl-shadow`, which is what lets light mode flip them from
black to white so a dark icon over a dark PC window still reads.

One that was already a bug: `.sets-live.on` painted its ink `var(--surface-0)`
— correct by accident on dark, and a light badge on a light accent the moment
a light theme existed. It is `var(--on-accent)`.

A grep for a hex literal or `rgb(` in this file now returns nothing. See
[theme.css + theme.js](theme.md).

## Independent grader round, 2026-08-07 — five fixes

- **The fill axis did nothing on light** — see [theme.md](theme.md) and
  [its flow doc](../__flow/theme.md). Fixed in `theme.css` alone; nothing
  here changed.
- **Emoji among drawn icons.** 🌍 (`#anywhere-banner`) and ⬆️
  (`#update-banner`) were literal characters, and `#lay-close`/`#wiz-close`
  carried a literal `✕` — the same class of bug `icons.js` already documents
  for the `move` handle's `✥`. All four now render the matching SVG from
  `ICONS` (`globe`, `reload`, `x`), embedded inline the same way the corner
  buttons and layout-bar arrows already were. `#anywhere-banner`/
  `#update-banner` gained `display:inline-flex; gap:8px` and an
  `svg{width:16px;height:16px}` rule; `#lay-close`/`#wiz-close` gained
  `display:flex;align-items:center;justify-content:center` and a 15px svg
  rule, replacing the bare font-size styling text no longer needs.
- **Unselected wheel items were borderless on light.** `.wheel-item`/
  `.wheel-x` now read `var(--wheel-border, var(--border))` instead of
  `var(--border)` directly — see theme.md for the token itself.
- **An unchecked checkbox was the brightest object on the card** (the Quality
  panel's "Save data on mobile networks", but every `.sets-row` checkbox had
  the same defect): the WebView's native unchecked-box chrome ignores
  `accent-color` entirely. `.sets-row input[type="checkbox"]` is now
  `appearance:none` with its own `--glass-fill`/`--border` background and a
  drawn corner-check (`::after`, `--on-accent` border) on `:checked` — no
  radio input is touched, the selector is type-scoped on purpose.
- **The dictation card's language rows broke in both columns at once**
  (`"Srpski"` cut from its own `"(Srbija)"` while ~60px sat unused between
  the name and status columns, and the status's own wrapped second line
  orphaned into that same gap) — ladder rung 1 (free width) could not fix it,
  the measured longest pair genuinely does not fit one line at 412px. Rung 2:
  `.sets-row.dict` is now a two-column CSS grid (`20px 1fr`) with the radio
  spanning both rows and `.dict-name`/`.dict-status` stacked in the second
  column instead of sharing one flex line — each takes the full row width,
  and the card grows into the ~225px of empty space that used to stand above
  it rather than starving either line.
- **The category wheel's veil dimmed our own buttons, not the PC's screen.**
  `#wheel` (z-index 35) carried `--scrim-soft` as its own background, above
  the D-pad (20) and the corner buttons (30), so opening the wheel washed
  every control on screen: the "Click" label measured 4.22:1 in `dark` and
  2.66:1 in `colored`, because a veil costs a chromatic colour far more
  luminance than it costs white. No ink could answer it — under a 0.55 veil
  the contrast ACHIEVABLE between the brightest and darkest possible pixels
  is 4.83:1, and a filled coloured button tops out near 2.8:1 whichever ink
  it wears. The veil is now `body.wheel-open::before`, a layer of its own at
  z-index 10: over the stream, under everything we draw. `#wheel` still
  covers the viewport, so a tap outside an item cancels exactly as before,
  and a full modal PANEL (`--scrim`, z-index 50) still dims the controls —
  a panel really does replace the screen; a small radial menu does not.
  Measured after: 15.9:1 dark, 8.1:1 colored outlined, 8.8:1 colored filled.
- **`.ctl.cat` was made recessive by dimming its own text** (`opacity: 0.85`),
  which put the set NAME — the one word saying which set your thumb is on —
  at 3.35:1 in dark and 4.27:1 on a filled VSCode-blue button. The dashed
  border and the smaller size already say "switcher, not action" without
  spending legibility, so the opacity is gone. Found by the audit's new
  ancestor-opacity check, which the old one could not see through.
- **In LANDSCAPE every panel card kept its portrait width and scrolled.**
  `min(420px, 100%)` is right on a 412px screen and absurd on a 915px one:
  495px of width standing idle while `92vh` fell to 379px, so seven of the
  ten panels scrolled — the Sets picker by 235px, the grid catalogue by
  256px, the creation panel's Create button below the fold entirely. That is
  BUG A of THE SPACE & LEGIBILITY LAW drawn exactly. Rung 1 then 2, in one
  `@media (orientation: landscape) and (max-height: 560px)` block: the card
  takes `min(760px, 100%)` (which alone collapses each `.lay-row` of chips
  onto one line) and its content reflows into `column-count: 2`. Only the
  ROWS are `break-inside: avoid` — making every direct child unbreakable
  spilled a THIRD column off the right edge (the Cancel button at x=957 on a
  915px screen), because a fixed column count with nothing splittable in it
  has no other way to place a block that will not fit. The Name textarea
  drops to 64px there and `.lay-list` gives up its own `max-height`, which
  inside a column only re-introduces a scrollbar. Measured after: the tallest
  card falls from 633px of content to 355px in a 379px box and nothing
  scrolls in either orientation; portrait is untouched, and the query needs
  BOTH landscape and a short screen so an upright tablet never sees it.
  The rule names `.lay-card` too, although that class is declared in
  layouts.css — one rule about one thing, and `body` prefixes the selector
  because layouts.css loads later and would otherwise win the width.
