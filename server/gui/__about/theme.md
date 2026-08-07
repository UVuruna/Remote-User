# Theme

**Script:** [Theme (script)](../theme.py) ·
**Flow:** [diagram](../__flow/theme.md)

## Purpose

Every visual token of the desktop app in one file (root Rule #4 — no color or
radius literal in component code), now in **TWO palettes**: the slate/cyan
dark one the app was born with, and a light one (build round R3, owner-approved
2026-08-07). The QSS stylesheet is GENERATED from whichever is active, and
`apply_theme` puts it on the **QApplication**, so one call re-themes every
window the app has open and every window it opens later.

The dark palette still matches the web client's core, verified against
[Client (folder)](../../../client/___client.md)'s `theme.css`:
`surface0`/`text`/`text2`/`accent`/`warning`/`error` match `--surface-0`/
`--text-primary`/`--text-secondary`/`--accent`/`--warning`/`--error` exactly
(case-insensitive hex). One divergence, honestly noted: `accentDark`
(`#0EA5E9`, the gradient's darker cyan stop) has no counterpart in the client
tokens, and the client's `--accent-2` (`#8b5cf6`, violet) has none here — the
shared palette is the surface/text/accent/semantic core, not a byte-for-byte
mirror.

## THE PALETTE IS READ LATE — the whole point of round R3

Until this round the dark palette was baked into a module-level `QSS` string
and every window pasted that string onto ITSELF. Both halves made a runtime
switch impossible, and DESIGN.md → Live theme switching names them by name:

- **a module-level f-string evaluates once at import** and can never be
  flipped, so `QSS` became `qss()`. The same defect lived in two more places
  and both were fixed with it: `traffic_window.OUT_COLOR/IN_COLOR` (module
  QColors — the chart would have kept bright cyan and amber on a white card
  forever) and `controls_widgets.ICON_STROKE` (a literal `#cbd5e1` that all
  but disappears on a white list);
- **a per-widget stylesheet WINS over its parent's**, so re-styling the main
  window would have left Controls, Traffic, Settings and the wheel-order
  dialog in the previous theme. `MainWindow.__init__` no longer calls
  `setStyleSheet` at all.

`TOKENS` is the ACTIVE palette and is mutated IN PLACE by `set_theme` — every
existing `TOKENS["accent"]` inside a `paintEvent` therefore reads the live
value with no call-site change at all.

## The two palettes

Elevation INVERTS between them (DESIGN.md): on dark, higher is lighter; on
light, the raised card is the whitest thing and the page sits a step below it.
Reusing the dark ordering is what makes light modes look sunken.

The accent is the same cyan family in both, **deepened** on light: `#38BDF8`
sits at 2.16:1 on white, which is unreadable, so light runs `#0369A1` (6.1:1
under white ink) with `#075985` as its gradient stop. A light theme that
reuses a dark theme's accent is the single most common light-mode bug.

`onAccent` exists because "ink on the accent" is not a surface token: it is
`#06212E` on dark and `#FFFFFF` on light, and the client's `--on-accent`
carries exactly the same idea.

## The lesson the light palette keeps teaching (2026-08-07, third time)

**A sentence written about elevation is a DARK sentence until it is tested on
light.** Round R3 found it with disabled buttons (`surface1` = "one step back
down the ladder" on dark, = pure WHITE on light, so every dead button was the
brightest thing on screen). An independent grader found the same shape twice
more, and both are now tokens rather than reasoning:

- **`fieldFill` / `fieldEdge`** — `QLineEdit` had no rule at all, so it fell
  through to the base `QWidget` rule and wore the PAGE colour. On dark that
  accidentally looks like a field; on light three of the Controls editor's
  inputs were page-coloured boxes with a hairline or no line at all, and read
  as static labels. An input RISES out of the page on dark (the control
  surface a combo uses) and is WHITE inside a real `#C7CBDD` line on light.
- **`fieldOff`** — and the SAME lesson a fourth time, inside the fix above.
  `QLineEdit:disabled` was written as `controlOff`, which on light is
  `#EDEFF5`: measured off the re-shot picture, the two fields the grader had
  named by name — the set `Name [Claude]` (disabled unless the set is custom)
  and `Shortcut [e.g. ctrl+shift+p]` (disabled on a built-in command) — came
  back at **(237,239,245) on a page of (236,238,246)**, one unit per channel,
  while only the always-editable third field had really been fixed. The cause
  is that `controlOff` is two ideas under one name: a disabled BUTTON owes the
  user nothing but its label and may recede flat, a disabled INPUT still
  carries a VALUE he must read and owes him a box. Two meanings, two tokens —
  `#F7F8FC` on light is 11 steps above the page and 8 below an editable field.
- **`checkAsset` / `caretAsset`** — two marks the QSS loads as FILES. QSS
  `image:` cannot re-tint what it loads (`theme.icon()` can, and does — but a
  checkbox indicator and a combo's caret are drawn by the stylesheet, not by
  us), so which file to load is a palette decision like any other. The tick
  is dark ink on the bright dark-mode accent and white on the deep light-mode
  one; the caret is each palette's `text2`.

## Two marks that were not drawings at all

- **The combo caret was a solid 10×10 BLOCK** in every combo of every window,
  in both palettes (sampled off the screenshots 2026-08-07: 100 identical ink
  pixels, not one antialiased edge). The QSS built it out of CSS border
  triangles — `border-left/right: 4px solid transparent` over a `border-top` —
  which is a browser trick Qt's subcontrol renderer does not perform. It is a
  drawn SVG now (`assets/caret.svg`), same family and stroke weight as the
  other icons. Same rule as the ✥ the owner rejected on his phone: **a mark is
  drawn**, never a font glyph and never a trick the renderer can silently drop.
- **`color(value)`** exists because `QColor` cannot parse the `rgba(r, g, b, a)`
  form every wash in this table is written in — it returns an INVALID colour,
  which paints opaque BLACK. QSS parses those strings perfectly, so the bug is
  invisible until a widget paints ITSELF: the Controls editor's `required`
  tick boxes came out solid black in both palettes. Custom painting reads
  tokens through `color()`, never through a bare `QColor(...)`.

## What the QSS may NOT say

`QHeaderView::section` must stay qualified `:horizontal`. Unqualified it also
reaches the VERTICAL header — which the commands table hides — and Qt takes
that padded section height as the floor for every ROW: 26 px rows became 39,
which cost the Controls editor 169 px and pushed its minimum outside the
declared 1280×1000 frame. Measured both ways.

## Connections

### Uses
- [Config](../../__about/config.md) — `BUNDLE_DIR`, `FROZEN`, `PROJECT_ROOT`,
  to build `ASSET_URL`: QSS reaches an asset by PATH, and the path differs
  between a checkout and the installed app

### Used by
- [Switch](switch.md) — `TOKENS` for the pill's own painting, `apply_theme`
  for the flip
- [Main Window](main_window.md) — calls `apply_theme(SETTINGS.ui_theme)` once
  at construction, plus `card()`, `icon()`, `repolish()`
- [Settings Window](settings_window.md) — `card()` for all five of its cards
- [Traffic Window](traffic_window.md) — `TOKENS` at paint time, `card_shadow`
- [Controls Editor](controls_editor.md) — the set list's tick, drawn by its
  delegate (an item view has no widget for QSS to style)
- [Controls Widgets](controls_widgets.md) — `TOKENS["text2"]` as the icon
  preview's stroke, and `color()` for every colour its `paint_check` /
  `RowDelegate` draw with
- [Controls Order](controls_order.md) — `TOKENS["accent"]`/`["text"]`/`["text2"]`
  for the wheel-order ring's dots/arrow/rule and the ↑ ↓ icons' ink

## Contents

- `PALETTES` — the two palettes, whole, in one table. Adding a token means
  adding it to BOTH, and `set_theme` refills from one of them, so a key that
  exists only in dark can never reach a light window as a KeyError at paint
  time. Both are pure literals, which keeps the whole table DECLARATIVE for
  the structure guard (rules/CODE.md — a table that computes is logic again)
- `TOKENS` — the ACTIVE palette; mutated in place, never rebound
- `DEFAULT_THEME` — `"dark"`; also what an unknown name falls back to
- `FONT_STACK` — Inter first, degrading to `"Segoe UI Variable Display"` then
  `"Segoe UI"` then generic `sans-serif`
- `QSS_TEMPLATE` / `qss()` — the stylesheet as a TEMPLATE and the function
  that fills it from the active palette. Covers the base widget, cards,
  labels, the status pill's four `state` variants, buttons (default /
  `#primary` gradient / `#danger`), combo boxes, **text inputs**, **group
  boxes and item views** (unstyled, both are drawn by the native style, whose
  frame is a hairline that simply vanishes on a light page — the Controls
  editor lost its set list's card and all three of its boxes),
  **item selection** (left to the native style a selected row wears the
  WINDOWS system accent, gold on the owner's PC, against this app's blue —
  two accents in one window), checkboxes, menus, tooltips.
  A combo's `min-width` is a FLOOR for an empty one (92 px), never a claim on
  space — at the old 140 px two combos in a row held 280 px while the shortcut
  field beside them was squeezed to "ift+tab" (owner screenshot 2026-08-05)
- `set_theme(name)` — swap the active palette; an unknown name falls back to
  the default AND says so in the log (a settings file carrying a theme this
  version dropped must not take the window down with it)
- `apply_theme(name)` — `set_theme` + `app.setStyleSheet(qss())`, then the
  three things QSS cannot do by itself: re-colour every card's
  `QGraphicsDropShadowEffect` (a black shadow under a white card reads as
  dirt), rebuild any widget's icon when it carries the dynamic property
  `iconName` (Qt's SVG renderer does not resolve `currentColor`, so the tint
  is baked into the source and an old icon is a picture in the old ink), and
  `update()` every widget so the custom-painted ones repaint
- `current_theme()` — which palette is on
- `ASSET_DIR` / `ASSET_URL` — the assets folder as a `Path` (for `icon()`) and
  as a POSIX path for QSS `url()`; the QSS one is quoted at every use site,
  because the installed path holds spaces (`C:/Program Files/Remote User/…`)
- `qrPaper` — a QR is a MEASUREMENT, not decoration: it is scanned by a camera
  and stays white in both palettes. Named rather than inlined so nobody
  "fixes" it into a surface token one day
- **Checkboxes** (owner screenshot 2026-08-06 — "CHECKBOX vizuelno
  neprihvatljiv, ima background color različit od elementa u kojem se nalazi"):
  a `QCheckBox` had no rule at all, so it took the base `QWidget` rule and
  carried the WINDOW's `surface0` into the `surface1` card it sits in. The
  label is transparent now, and the indicator is the same control surface as a
  combo, filled with the accent when on and wearing `assets/check.svg`
- `color(value)` → `QColor` — a palette VALUE as a colour, `rgba(...)`
  included. Every custom `paintEvent` reads tokens through this; see above for
  what a bare `QColor("rgba(…)")` silently paints
- `card(margins, spacing)` → `(QFrame#card, QVBoxLayout)` — one soft-shadowed
  card and its column, the bento tile every window is built out of
- `icon(name, color)` → `QIcon` — an SVG asset from `assets/`, tinted with a
  theme token. Keeping the palette OUT of the asset is what lets one icon file
  serve both themes; a missing or unreadable asset yields an empty `QIcon` and
  a logged error, so the button keeps working with its label alone. **Never a
  font glyph** — the ✥ that came out a blunt cross on the owner's phone
  (2026-08-05) is the same rule, applied to the desktop
- `card_shadow(widget)` — the DESIGN.md soft ambient shadow (blur 28, offset
  0/6), coloured from `shadowRgba` so light gets a soft slate tint instead of
  black; Qt's defaults ARE the dated look (blur 1, offset 8/8)
- `repolish(widget)` — `unpolish()` + `polish()`; Qt caches computed styles, so
  a QSS dynamic-property selector (e.g. `QLabel#pill[state="running"]`) needs
  this call after the property changes
