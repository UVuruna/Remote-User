# Controls Editor — Arrangement & Order

**Script:** [Controls Order (script)](../controls_order.py) ·
**Flow:** [diagram](../__flow/controls_order.md)

## Purpose

Every WHERE-does-a-thing-sit widget the Controls editor uses, split out of
`controls_widgets.py` in build round R5 (2026-08-07, owner: "he chooses the
ORDER of the sets around the phone's category wheel"). Two different rings,
one shared widget family:

| Widget | What it arranges |
|--------|-------------------|
| `SlotDelegate` / `SlotList` | the plumbing `OrderList` is built from |
| `OrderList` | one set's four ACTIVE buttons, per orientation (unchanged since 2026-08-05 — moved whole) |
| `WheelRing` | a small legend: the wheel is a RING, not a column |
| `WheelOrderDialog` | **new** — every set the file knows, in the ORDER the owner wants around the phone's wheel |

## The wheel order (build round R5)

The owner's spec, verbatim: position 1 sits at 12 o'clock, the rest follow
CLOCKWISE — and it has to READ as a circle, "ne kolona". Two pieces answer
that together:

- **`OrderList` needed no new shape.** Its `slots` parameter already named
  each row's fixed position for the D-pad ladder (`LAND_SLOTS`/`PORT_SLOTS`,
  a 4-tuple); it now ALSO accepts a `SlotNamer` callable (`int -> str`), so
  the wheel's ladder — however many sets the file has, never a fixed four —
  can label each row `ordinal(i+1)` ("1ˢᵗ", "2ⁿᵈ", … "13ᵗʰ") without a
  second list-widget implementation. `ordinal()` itself is new and also
  generates `PORT_SLOTS` now, so the D-pad's four ordinals and the wheel's
  N ordinals come from one function.
- **`WheelRing`** is the part text alone cannot say: a drawn circle, one
  decorative dot position per wheel slot — the CURRENT mode's cap, 8 under
  fixed and 10 under drop-out, passed in by the editor since 2026-08-12
  (it drew eight whatever the mode said, so the picture contradicted the
  "up to 10" the checkbox one line above it already stated: ONE screen may
  state ONE cap) — "1" bold over the
  highlighted dot at 12 o'clock, and a curved accent-coloured arrow sweeping
  clockwise. It never reflects the LIVE order — the ladder beside it does
  that in text — it only answers "why is this list drawn beside a clock
  face".
- **`WheelOrderDialog`** is a SEPARATE small dialog, not a fourth box in
  `ControlsEditor`'s already-stressed right column. An independent grader
  failed that window at 6/10 on 2026-08-07 for exactly this kind of crowding
  (the pool table scrolling beside an idle set list — see
  [Controls Editor](controls_editor.md)'s `arr` comment); a small dialog
  only has to fit itself, and none of the main window's existing columns
  change shape. It lists EVERY set the file knows, riding or not — a set not
  currently on the wheel is left out by the CLIENT's rendering
  (`client/sets.js` `sortByWheelOrder` + the existing cap trim), never out
  of this dialog, so the owner arranges the whole roster once and the ring
  closes up by itself around whichever subset actually rides.

## What the second independent grade changed (2026-08-07)

The dialog shipped at 7/10 dark, 6/10 light. Five findings, five answers:

1. **The ring was marooned.** A 108 px drawing alone in a ~125 px column with
   ~350 px of dead space above and below it, beside a full-height ladder. The
   ring and the caption say the SAME thing — one in a picture, one in words —
   so they now ride ONE ROW at the top and the ladder takes the dialog's whole
   width. The hole is not filled, it is gone. (`WheelRing.LABEL` came with it:
   the "1" was drawn off a circle centred in the whole widget, so the moment
   the widget stopped being stretched taller than it asked for, the label's
   rect landed at y = −6 and the digit came out with a flat top.)
2. **The ladder did not line up.** "10ᵗʰ" pushed its name ~13 px right of
   "1ˢᵗ"'s, because the row was ONE string. `SlotDelegate` paints two columns
   now — the slot name RIGHT-aligned in a column as wide as the widest one in
   the model, then the label — so the separator dots and the names form two
   straight edges in every ladder it serves, the wheel's thirteen ordinals and
   the D-pad's four direction words alike.
3. **On light the list had no card** and the ↑ ↓ buttons nearly vanished —
   fixed in the shared QSS ([Theme](theme.md): item views and group boxes are
   drawn by the native style, whose frame is invisible on a light page).
4. **↑ and ↓ were text glyphs.** They are drawn icons now (`arrow_icon`), the
   client's own `arrowu`/`arrowd` fragments in the button ink, cached per
   (name, ink) so a theme flip rebuilds rather than keeping a stale picture.
   DESIGN.md forbids a font glyph inside a control row, and this project has
   its own scar from one (the ✥ that came out a blunt cross).
5. **OK was not the primary button** while "Apply & restart" and "Update" carry
   the accent everywhere else. It has `objectName("primary")` now.

## Connections

### Uses
- [Controls Data](controls_data.md) — `DPAD_SLOTS` (sizes the D-pad ladder's
  four fixed slots), `load_client_icons()` (the ↑ ↓ fragments)
- [Controls Widgets](controls_widgets.md) — `icon_for()` for those two icons,
  and `RowDelegate`, so a selected ladder row wears this app's accent instead
  of the Windows one
- [Theme](theme.md) — `TOKENS` for every colour the ring and the ladder draw
  with; no hardcoded hex

### Used by
- [Controls Editor](controls_editor.md) — `order_land`/`order_port`
  (unchanged) and the new "Wheel order…" button, which opens
  `WheelOrderDialog`
- `tests/test_layout_audit_qt.py` — `WheelOrderDialog` is one of the audited
  windows, built in its FULLEST state (every shipped category + app set)

## Classes

- **`SlotDelegate`** — draws an arrangement row as rich text (the portrait/
  wheel ordinals' real superscript, `1ˢᵗ`) in TWO COLUMNS, the slot name
  right-aligned; reads `OrderList.SLOT_ROLE` / `BODY_ROLE`
- **`SlotList`** — a list that asks for exactly the height of its rows
  (SPACE & LEGIBILITY, ladder step 1)
- **`OrderList`** — a ring/ladder of items with ↑/↓; `slots` is a fixed
  4-tuple (D-pad) OR a callable ordinal namer (the wheel) — `labels()` reads
  back the reordered identity list directly (what the wheel dialog saves)
- **`WheelRing`** — the circle-not-a-column legend; purely decorative, fixed
  108×108, with a `LABEL` band at the top the circle is centred UNDER so the
  "1" can never fall outside the widget's own rect
- **`WheelOrderDialog`** — the global wheel-order editor: ring beside the
  caption, then the full-width ladder, then Default/OK(primary)/Cancel;
  computed minimum measured from the real widgets
  (`self.order.sizeHint()`, the caption's wrapped height at the dialog's own
  width) — never a hand-rolled guess, per THE SPACE & LEGIBILITY LAW

## Functions

- `ordinal(n)`: `1 -> "1<sup>st</sup>"` … the English ordinal suffix, as HTML
  so `SlotDelegate` renders a real superscript
- `arrow_icon(name)`: `arrowu`/`arrowd` from the client's icon set, in the
  button ink, cached per (name, ink)
