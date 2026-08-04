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
