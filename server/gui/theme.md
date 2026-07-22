# Theme

**Script:** [Theme (script)](theme.py)

## Purpose
Every visual token of the desktop app in one file (root Rule #4 — no color or
radius literal in component code): the slate/cyan palette shared with the web
client, the QSS stylesheet built from those tokens, and the two effect helpers
QSS cannot express.

## Contents
- `TOKENS` — surfaces (elevation steps), text, one accent family, semantic colors, radii
- `FONT_STACK` — Inter first (design-system typeface), degrading to Segoe UI Variable
- `QSS` — window, cards, status-pill states (`[state="running"]` …), buttons (default / `#primary` gradient / `#danger`), combo boxes, menus, tooltips
- `card_shadow(widget)` — the DESIGN.md soft ambient shadow (Qt's defaults are the dated look; parameters always overridden)
- `repolish(widget)` — re-applies QSS after a dynamic property change

## Connections

### Uses
- Nothing project-internal (leaf module)

### Used by
- [Main Window](main_window.md) — stylesheet + effects
