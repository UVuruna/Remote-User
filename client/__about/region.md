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
  frame appears  ──▶   4 corner handles + a centre Move handle
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
  every button in this app uses), `svg`, `showToast`, `send`
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
