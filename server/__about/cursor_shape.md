# Cursor Shape

**Module:** [cursor_shape.py](../cursor_shape.py) ·
**Folder:** [server](../___server.md)

## Purpose

Names the cursor Windows is showing RIGHT NOW — `arrow`, `ibeam`, `size-we`,
`hand`, … — so the phone can draw that shape instead of one eternal arrow.
One short word per frame; no image ever leaves the PC.

## Why it exists (owner request 2026-08-09 — task 142)

DXGI capture never contains the pointer, so the page has always drawn it
itself, and it drew a single fixed arrow. From the tablet that made a
draggable window edge, a text box, a link and plain background look
identical — the one thing a cursor is FOR (telling you what the pixel under
it does) was missing. A resize cursor at a window edge is how a person knows
the edge is grabbable.

## How it reads the shape

`GetCursorInfo` returns the live `HCURSOR`. Every SYSTEM cursor has a stable
handle obtainable from `LoadCursorW(NULL, IDC_*)`, so matching the two names
the shape without touching a single pixel.

## Key Functions

- `CursorNamer.name_for(handle)` — handle → name, over the cached system
  table. The seam this module is designed around: the gate
  (`tests/test_cursor_shape.py`) drives the REAL resolver with faked handles
  by passing its own `load`, rather than stubbing the resolution itself.
- `CursorNamer.current()` — the live cursor's name, or `None` when Windows
  refuses the read (secure desktop, lock screen — the same moments
  [Input Injector](input_injector.md)'s `cursor_norm()` returns `None`). A
  HIDDEN cursor (fullscreen video, a game drawing its own) reports the plain
  arrow: the phone must keep drawing something to aim with.
- `current_cursor_name()` — the process-wide entry point
  [Web Layer](web.md)'s `_send_cursor` loop calls, so the system table is
  loaded once for the whole run.

## Design Decisions

- **The handles are resolved ONCE.** This is called inside the ~30 Hz cursor
  loop; a `LoadCursorW` sweep per frame would be a per-frame syscall storm
  for an answer that only changes when the user changes their cursor SCHEME.
- **…but a cursor SCHEME change heals itself.** Windows hands out new handles
  for every system cursor when the style or accessibility size changes, and a
  table cached at start would then call every cursor on the machine `custom`
  for the rest of the session. An UNMATCHED handle may reload the table, at
  most once per `RELOAD_SECONDS` — bounded, and only while something we do
  not recognise is actually on screen.
- **An unmatched handle is `custom`, never a guess.** Applications ship their
  own cursors and those match nothing here; the phone then draws the plain
  arrow. A near-miss ("looks like a resize one") would be worse than the
  arrow — it would promise a grabbable edge that is not there.
- **Nothing here touches DPI or injection.** Only `hCursor` is read;
  `ptScreenPos` is deliberately ignored, so position stays
  `input_injector.cursor_norm()`'s job (mapped through the monitor rect) and
  the process-wide DPI declaration this project depends on is untouched.
- **`move`, not "size-all"** for `IDC_SIZEALL`: what it means to the person
  looking at it is "this thing moves", and the phone already calls that shape
  `move`.

## Used by

- [Web Layer](web.md) — `_send_cursor()` puts the name on the existing
  `cursor` message as the optional `shape` field
- [Cursor Shapes](../../client/__about/cursor-shapes.md) — the phone's table
  of drawn silhouettes, keyed by exactly these names
- `tests/test_cursor_shape.py` — the gate, fail-closed in `setup/build.py`
