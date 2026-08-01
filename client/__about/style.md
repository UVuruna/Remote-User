# Style

**Script:** [Style (script)](../style.css) ·
**Flow:** [diagram](../__flow/style.md)

## Purpose

Every visual rule for the tablet page: design tokens (dark surface, one
accent — per root DESIGN.md), the connection-state pill, the invisible
keyboard-capture field, the offscreen video surface, the see-through control
buttons, the two-column D-pad groups (grid areas in landscape, a stacked
column in portrait), the category wheel, the "access from anywhere" banner +
guided wizard, and the hide-all-controls mode. `touch-action: none` is set
everywhere the page must own gestures itself rather than the browser.

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
  (mode/keyboard buttons), `.wheel-item.current`, and the wizard's step
  classes
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
