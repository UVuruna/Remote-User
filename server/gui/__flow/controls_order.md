# Controls Editor — Arrangement & Order — Flow

**About:** [description](../__about/controls_order.md)

## OrderList — one widget, two namers

```
OrderList(title, slots)
 slots = ("Top","Left","Right","Bottom")     ← D-pad, fixed 4-tuple
        | ("1st","2nd","3rd","4th")          ← Stack, fixed 4-tuple
        | lambda i: ordinal(i+1)             ← Wheel, DYNAMIC (round R5)

_slot_name(slot)
 callable(self.slots) ? self.slots(slot) : self.slots[slot] (or "")

_relabel()  — re-draws SLOTS[slot] + " · " + label from the row
              order, every move — the ladder itself can never
              reorder, only the ITEMS travel through it. It writes
              THREE values now (2026-08-07), and the split is what
              makes the ladder line up:
                SLOT_ROLE   "10<sup>th</sup>"   ← its own column
                BODY_ROLE   "·&nbsp; VSCode"    ← what follows it
                DisplayRole the whole line      ← Qt's sizeHintForColumn
                                                  and the layout audit
```

## The ladder's two columns (`SlotDelegate`)

```
        │◀── slot column ──▶│gap│◀── body
        │        1ˢᵗ        │ · Mouse
        │       10ᵗʰ        │ · VSCode
        ▲ RIGHT-aligned, width = the widest slot name IN THE MODEL
          (re-measured per paint: a move renumbers every row)
```

It was one string until 2026-08-07 — so "10ᵗʰ" pushed its name ~13 px right
of "1ˢᵗ"'s and an independent grader failed a numbered list whose numbers did
not line up. Serving both ladders from one delegate means the D-pad's
Top/Left/Right/Bottom line up on the separator too.

## WheelOrderDialog — the shape (revised 2026-08-07)

```
┌─ Wheel order ───────────────────────────────────┐
│   ⓵      Position 1 sits at 12 o'clock on the   │  ◀── ring + caption on ONE
│ ( ↷ )    phone's wheel — the rest follow        │      row: the picture and
│ 10 slots CLOCKWISE. The ring is the WHEEL, and  │      the words say the same
│          it holds 10 slots; the ladder below is │      thing — and since
│          every set that can be ordered, which   │      2026-08-12 the ring
│          is more. …                             │      states its OWN number
│ Sets, top to bottom — top = 12 o'clock          │      in a foot line
│ ┌─────────────────────────────────────────────┐ │
│ │   1ˢᵗ · Mouse                               │ │  ◀── the ladder takes the
│ │   …                                         │ │      whole width now
│ │  13ᵗʰ · Explorer                            │ │
│ └─────────────────────────────────────────────┘ │
│ [↑][↓]                                          │  ◀── DRAWN icons (arrowu /
│ [Default]                    [ OK ] [Cancel]    │      arrowd), never glyphs
└─────────────────────────────────────────────────┘        OK = #primary
```

The ring used to sit in a column of its own BESIDE the ladder — 108 px of
drawing in a ~125 px strip with ~350 px of dead space above and below it,
which is what an independent grader failed on 2026-08-07. Moving it beside the
caption removes the hole rather than filling it, and the measured minimum went
404×572 → **377×592**: narrower, and its ladder card now carries 10 px of band
under the last row instead of 46.

Measured again 2026-08-12 with the full shipped roster (14 sets) and the ring's
new foot line: **395×636**, both palettes, audit clean at the minimum and at
+50%. The proof file had carried 790×1236 for this window — the SHOT's pixel
size (audit shots render at 2×), not the window's — which is why it looked like
a minimum that could not fit a 1920×1080 desktop.

## WheelOrderDialog — build round R5 data flow

```
ControlsEditor._open_wheel_order()
 ├─ _store_current()                     screen → self.data (RAM)
 ├─ effective_wheel_order(self.data)     saved order, extended, unmentioned → end
 ├─ natural_order(self._shipped)         the Default button's target
 └─ WheelOrderDialog(current, default, self).exec()
       ├─ OrderList(dynamic ordinal namer).set_order(current, identity)
       ├─ ↑ / ↓                          reorder, exactly like the D-pad ladder
       ├─ Default                        _reset(): default names first (that
       │                                 ARE still present), then whatever
       │                                 else is currently listed, in place
       └─ OK → dlg.order_names()         → self.data["wheel_order"]
             Cancel → self.data untouched

Save (ControlsEditor._save, unchanged) → self.data written whole,
including "wheel_order" if the dialog was ever accepted
```

## Reading the ring (`WheelRing.paintEvent`)

```
angle(i) = -π/2 + i · 2π/8         ◀── SAME formula client/controls.js's
                                        openWheel() uses for the real wheel
i=0 → -π/2 = straight UP (12 o'clock)   ◀── the highlighted dot + "1"
i>0 → sweeps CLOCKWISE on screen        ◀── the curved accent arrow, i=1..2
(8 dots total = the wheel's own cap, controls_data.WHEEL_MAX)
```

The ring is deliberately the SAME angle formula the client draws its real
wheel with (`angle = -PI/2 + i * 2*PI/n` in `client/controls.js`
`openWheel()`) — not a coincidence, a promise: what the desktop shows as
"12 o'clock, clockwise" is exactly the geometry the phone will draw.

## Client half (not this module, cross-referenced)

```
server: wheel_order (list of set NAMES) ──▶ ws "actions" message
client (client/sets.js): sortByWheelOrder(list)
  rank = Map(name -> index in wheelOrder)
  sort by rank, unranked = Infinity (stable — original order among them)
allCats() = sortByWheelOrder(filtered sets) then the existing cap trim
```

See [client/sets.js](../../../client/__about/controls.md) for the client
side in full; this module only produces the `wheel_order` list, it never
renders the wheel itself.
