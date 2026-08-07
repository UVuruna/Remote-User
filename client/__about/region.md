# Region

**Script:** [region.js](../region.js)

## Purpose

The **Region grab** (Attach set, owner 2026-08-05): a rectangle the finger
sizes and moves anywhere on the screen, whose contents are then captured on
the PC and **pasted** — the phone's answer to Snipping Tool's rectangle.

The owner's spec was explicit about the two halves:

- *"ista mehanika kao da se podesava size i position LAYOUTA — samo što ovde
  nije vezan ni za jednu ivicu, dakle full freedom za dimenzije i poziciju"* —
  so the frame keeps **no ratio and no edge**, unlike the layout aspect panel
  whose region may only shrink along one axis;
- *"odmah lepi region kao i ceo Attach set"* — the capture ends the way every
  other Attach source does: PC clipboard, `Ctrl+V` injected by the server.

## How it works

Nothing new was needed on the server: `screenshot {x, y, w, h, paste: true}`
already crops an arbitrary rect, fills the clipboard and pastes (that is the
Shot button's protocol; Shot just computes the rect from the view instead of
from a frame the user drew).

```
Attach ▸ Region        openRegionPanel()
  frame appears  ──▶   rgDefaultBox() — in the band the chrome leaves free
                       4 corner handles + a centre Move handle
  drag a corner  ──▶   that corner moves, the opposite one stays put
  drag anywhere  ──▶   the whole frame travels
  Send           ──▶   rgToMonitor() → screenshot {x, y, w, h, paste: true}
  ✕ / backdrop   ──▶   closeRegionPanel(), nothing captured
```

`rgToMonitor()` converts the frame from screen CSS px to monitor-normalized
coordinates through the SAME `drawnRect()` the image itself is drawn with
(device px — hence `devicePixelRatio`), then clamps it to the view: in layout
focus the capture can never reach outside that layout's region.

## Connections

### Uses
- [Controls](controls.md) — `keepFocus` (the pointerup + stolen-tap rescue
  every button in this app uses), `svg`, `showToast`, `send`; and the chrome
  it reads to place the newborn frame (`.corner`, `#layout-bar`, `.group`)
- [Render](render.md) — `drawnRect()`, `viewLocked()`, `layoutRegion`
- [Icons](icons.md) — `region`, `move`, `x`
- [Style](style.md) — `#region-panel`, `.rg-*`

### Used by
- [Controls](controls.md) — the `region` built-in action opens the panel

## Design Decisions

- **The frame is dashed and the page is NOT dimmed to modal darkness.** The
  whole gesture is choosing what to capture, which means the PC screen must
  stay readable through it; only the area outside the frame is dimmed (one
  `box-shadow` spread), and the bar carries its own backdrop.
- **44 px handles.** A smaller target is a lottery on a phone; the drawn
  square inside stays 18 px so the frame still looks like a selection.
- **The box remembers its size between openings.** The PC screen does not
  move, so the second grab of the same area is one tap.
- **`pointercancel` just ends the drag.** A half-moved frame is a harmless
  state — unlike a stuck mouse button, which is why the hold buttons need a
  release path and this does not.
- **The clamp is at capture time, not while dragging** (the frame may hang off
  the image; the captured rect is intersected with the view). Dragging stays
  free — which is what "full freedom" asked for.
- **The frame is BORN in the band our own chrome leaves free**
  (`rgFreeBand` / `rgDefaultBox`, independent grader 2026-08-07). The panel
  draws at z-index 55, above every control, so a newborn frame that lands on
  one paints its dashed edge and its 44 px handles across that control's
  label — the grader's picture read **"Layou"** where the corner button says
  "Layout". The old default was two percentages (18 % / 22 % of the screen)
  that knew nothing about the chrome. The band is measured from the real
  `.corner` / `#layout-bar` / `.group` rects — anything above the screen's
  middle pushes its top down, anything below pulls its bottom up — and the
  frame plus its handles is centred in what is left. It is only the STARTING
  rect: a drag still takes the frame anywhere. Tooth: *"the Region frame
  opens clear of every control"* in `tests/test_layout_audit.py`, both
  orientations, which also measures the bar.
- **The bar is bounded on BOTH sides, and wraps** (same grader, THE SPACE &
  LEGIBILITY LAW's ladder). `left: 50%` with no `right` gives an absolutely
  positioned shrink-to-fit box an available width of exactly **50vw** — 206 px
  on a 412 px phone — of which Send, ✕ and the padding took 177, so "Drag the
  corners, then Send" was laid out in the 29 px that were left and broke into
  four lines. `max-width` could not help: the constraint was the AVAILABLE
  width, not the cap. Rung 1 — the bar takes the idle width, bounded by the
  corner column so it can never run under the D-pad (portrait: 205 → 248 px).
  Rung 2 — the row wraps, so on a narrow phone the hint gets a line of its own
  and the buttons sit under it, whole. Landscape needs neither: everything
  fits one line by measurement, not by a media query.
- **The "use from anywhere" pill stands down while the frame is up**
  (`body.region-open`). It is anchored to the same bottom centre as the bar
  and the bar's background is translucent, so it showed THROUGH it with the
  Send button sitting on its words.
