# Cursor Shapes

**Script:** [Cursor Shapes (script)](../cursor-shapes.js) ·
**Folder:** [client](../___client.md)

## Purpose

The drawn silhouette of the PC's cursor, one per name the server can send —
arrow, I-beam, hand, the four resize arrows, move, wait, cross, no, up-arrow,
app-starting and help. Pure geometry (no DOM, no canvas, no socket), so its
gate can run it whole; loads right before [Render](render.md), which draws it.

## Why it exists (owner request 2026-08-09 — task 142)

Screen capture never contains the pointer, so this page has always drawn it —
as ONE fixed arrow. From the tablet, a draggable window edge, a text box, a
link and plain background were the same picture. The PC now names the live
system cursor ([Cursor Shape](../../server/__about/cursor_shape.md)) on the
`cursor` message it already sends, and this table turns that name into a
shape.

## Key Functions

- `cursorPolys(name, x, y)` — the polygons to draw for `name`, with the
  shape's HOTSPOT landing exactly on `(x, y)`. The only surface
  [Render](render.md) uses and the only surface the gate drives.
- `CURSOR_SHAPES` — name → polygons, hotspot at the origin.
- `CURSOR_FALLBACK` — `"arrow"`, the shape for every name this table does not
  know.

## Design Decisions

- **The ORIGIN of every shape is its hotspot.** `drawCursor` translates to the
  commanded point and draws these coordinates straight, so a shape can never
  drift off the pixel it names. An arrow-family cursor points with its TIP
  (arrow, hand, up-arrow, and the two badged arrows); the
  resize/move/wait/I-beam/cross/no family is centred, which is Windows' own
  rule and what makes a resize arrow read as *this edge, right here*.
- **Canvas PATHS, never font glyphs.** The owner has already been shipped a
  font character that came out wrong on his own phone (the ✥ move handle
  rendered as a blunt cross, 2026-08-05). A drawn path looks the same on every
  device. [Icons](icons.md) is the SVG half of the same rule; this is the
  canvas half — separate because a cursor is filled-and-outlined geometry with
  a hotspot, not a stroked 24×24 icon.
- **One source for the four resize arrows.** `size-ns`/`size-nwse`/`size-nesw`
  are `size-we` rotated, so the set can never drift apart in weight or length
  — it only works if the four read as siblings at a glance.
- **Closed polygons only, filled white and stroked black** by
  [Render](render.md) — the treatment the original arrow already used, and the
  reason it stays legible over a white document AND a dark editor. Every new
  shape inherits it instead of re-deciding it. A hole (the ring of `no`) is a
  polygon wound the other way; canvas fills nonzero.
- **An unknown, missing or `custom` name draws the EXACT original arrow.** An
  application's own cursor matches nothing on the PC, and a name from a newer
  server means nothing here. Falling back to the arrow is the honest answer; a
  near-miss shape would promise a grabbable edge that is not there. The gate
  pins the original arrow's coordinates as a literal.

## Used by

- [Render](render.md) — `drawCursor()`
- [Connection](connection.md) — sets `cursorShapeName` from the `cursor`
  message's optional `shape` field
- `tests/test_cursor_shape.py` — the gate, fail-closed in `setup/build.py`
