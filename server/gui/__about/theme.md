# Theme

**Script:** [Theme (script)](../theme.py) ·
**Flow:** [diagram](../__flow/theme.md)

## Purpose

Every visual token of the desktop app in one file (root Rule #4 — no color or
radius literal in component code): the slate/cyan palette, the QSS stylesheet
built from those tokens, and the two effect helpers QSS cannot express (drop
shadow, re-polish after a dynamic-property change).

The module docstring claims the "same slate/cyan palette as the web client
(`client/style.css`)". Verified against [Client (folder)](../../../client/___client.md)'s
`style.css`: `surface0`/`text`/`text2`/`accent`/`warning`/`error` match the
client's `--surface-0`/`--text-primary`/`--text-secondary`/`--accent`/
`--warning`/`--error` exactly (case-insensitive hex). One divergence, honestly
noted: `accentDark` (`#0EA5E9`, the gradient's darker cyan stop) has no
counterpart in the client tokens, and the client's `--accent-2` (`#8b5cf6`,
violet) has no counterpart here — the shared palette is the surface/text/accent/
semantic core, not a byte-for-byte token mirror.

## Connections

### Uses
- [Config](../../__about/config.md) — `BUNDLE_DIR`, `FROZEN`, `PROJECT_ROOT`,
  to build `ASSET_URL`: QSS reaches an asset by PATH, and the path differs
  between a checkout and the installed app

### Used by
- [Main Window](main_window.md) — applies `QSS` as the window stylesheet and
  calls both `card_shadow()` and `repolish()`
- [Controls Editor](controls_editor.md) — `TOKENS["accent"]` for the tick its
  delegate draws (an item view has no widget for QSS to style)

## Contents

- `TOKENS` — dict of every color/radius value, grouped under comment banners:
  Surfaces, Text, Accent, Semantic, Shape (see [flow](../__flow/theme.md) for
  the full key tree)
- `FONT_STACK` — Inter first (design-system typeface), degrading to
  `"Segoe UI Variable"` then `"Segoe UI"` then generic `sans-serif`
- `QSS` — the stylesheet string, built via `.format(font=FONT_STACK, **TOKENS)`;
  covers the base widget, cards, labels, the status pill's four `state`
  variants, buttons (default / `#primary` gradient / `#danger`), combo boxes,
  menus, tooltips. A combo's `min-width` is a FLOOR for an empty one (92 px),
  never a claim on space — at the old 140 px two combos in a row held 280 px
  while the shortcut field beside them was squeezed to "ift+tab" (owner
  screenshot 2026-08-05; THE SPACE & LEGIBILITY LAW forbids a neighbour
  holding slack next to a starving element). Qt already sizes a combo to its
  longest item
- `ASSET_URL` — the assets folder as a POSIX path for QSS `url()`; quoted at
  every use site, because the installed path holds spaces
  (`C:/Program Files/Remote User/…`) and a bare `url()` breaks on them
- **Checkboxes** (owner screenshot 2026-08-06 — "CHECKBOX vizuelno
  neprihvatljiv, ima background color različit od elementa u kojem se nalazi"):
  a `QCheckBox` had no rule at all, so it took the base `QWidget` rule and
  carried the WINDOW's `surface0` into the `surface1` card it sits in — a
  darker block around the label, next to Windows' own gray tick box. The label
  is transparent now, and the indicator is the same control surface as a combo
  (`surface2`, 1 px border, 5 px radius), filled with the accent when on and
  wearing `assets/check.svg` — a DRAWN tick, dark ink on accent, the same
  pairing as the primary button. If the SVG ever fails to load the box is still
  unmistakably filled; nothing depends on a font glyph
- `card_shadow(widget)` — the DESIGN.md soft ambient shadow (blur 28, offset
  0/6, black at 55/255 alpha) — Qt's `QGraphicsDropShadowEffect` defaults are
  the dated look (blur 1, offset 8/8), so every parameter is set explicitly
- `repolish(widget)` — `unpolish()` + `polish()`; Qt caches computed styles, so
  a QSS dynamic-property selector (e.g. `QLabel#pill[state="running"]`) needs
  this call after the property changes or the new state never repaints
