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
- Nothing project-internal (leaf module) — only `PySide6.QtGui.QColor` and
  `PySide6.QtWidgets.QGraphicsDropShadowEffect` / `QWidget`

### Used by
- [Main Window](main_window.md) — applies `QSS` as the window stylesheet and
  calls both `card_shadow()` and `repolish()`

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
- `card_shadow(widget)` — the DESIGN.md soft ambient shadow (blur 28, offset
  0/6, black at 55/255 alpha) — Qt's `QGraphicsDropShadowEffect` defaults are
  the dated look (blur 1, offset 8/8), so every parameter is set explicitly
- `repolish(widget)` — `unpolish()` + `polish()`; Qt caches computed styles, so
  a QSS dynamic-property selector (e.g. `QLabel#pill[state="running"]`) needs
  this call after the property changes or the new state never repaints
