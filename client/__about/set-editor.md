# set-editor.js — one set's own editor, on the phone

New 2026-08-11 (owner **2026-08-04 18:27**, delivered as **task 218b**). Opened
from the edit door on every row of the [Wheel sets picker](panels.md), and it
does on the phone exactly what the desktop Controls editor does to a set's
interior: **which pool commands ride the controls, and in which slot.**

## Why it exists — and why so late

His 2026-08-04 spec for the wheel ends with the sentence this feature was owed:
he gives the user the arrangement of a set's buttons in **both** shapes, the
D-pad cross and the portrait column, "dakle obe te opcije dozvoljavamo mu da
slobodno bira raspored batona u tom setu" <!-- lang-ok: owner quote -->. The
same message then limits the PHONE's copy of that menu to not **creating** sets.

Creating was what he withheld. Arranging never was — and it is the half that
can only honestly be judged with the device in the hand: which arm of the cross
the thumb actually reaches, which button he keeps hitting by mistake. Sending
him to the desk to answer a question the desk cannot see is what left this
unbuilt until he raised it again on 2026-08-11, in his own words, as a request
so old it worried him that nobody had mentioned it.

The PROCESS half is recorded with the task: it never received a task number,
and the list only executes what enters it.

## What it may and may not do

| | |
|---|---|
| **Edits** | a set's INTERIOR — `active` (the ≤4 pool commands that ride, BY ID) and the arrangement (`order_land` / `order_port`) |
| **Never touches** | the wheel's COMPOSITION — which sets ride is the picker's job and the cap of 8 is a law over that, untouched here |
| **Never edits** | a COMMAND. He picks from the pool; he does not rewrite it (his decision 2026-08-05). That includes custom sets — a custom set's commands are made on the PC, where a keyboard and a chord recorder exist |
| **Scope** | built-in, app-aware and custom sets alike. A `required` set is locked against the picker's TICK and fully editable here: "always on the wheel" says nothing about what is on its D-pad, and Mouse and Input are the two he arranges most |

**A rename is deliberately not here**, although the desktop allows it. This
page's typing goes through the invisible full-width capture textarea that feeds
`key_text` to the PC (CLAUDE.md constraint 5), so a real text field in an
overlay would be fighting the one element the whole input pipeline depends on
holding focus. A rename is a desk job; an arrangement is not.

## The two controls

**The arrangement is a DRAWING** — the cross drawn as a cross, the column as a
column, each cell holding the button that will really be there, on the same
`grid-template-areas` the live D-pad uses. Never a list of words, and never a
font glyph (the ✥ move handle came out a blunt cross on his phone, 2026-08-05).
Which shape is drawn is `padColumn()` — the one question the rest of the page
asks (task 177 made the shape a choice, not the orientation), so the editor and
the control it edits can never disagree about which order is being arranged.

**Tap one position, tap another, they swap.** Tap-to-swap and not drag: drag on
his device has failed three times (tasks 81 / 162 / 196), and a position picker
that needs a working drag is a position picker he cannot use. Tapping the same
cell twice cancels — an armed state with no way out is a trap on a touch screen.

Changing WHICH buttons ride resets BOTH arrangements to the shipped order, and
the card says so. Preserving the survivors' positions has no honest answer for
the button that just arrived, and an order that half-survives reads as the
panel doing something it was not asked to.

## Where it saves — not in this phone

Every other phone-side switch is per DEVICE on purpose (his tablet and his
phone want different wheels). A set's arrangement is not: it is the OWNER's,
and he must find the same D-pad in the PC's Controls editor and on both
devices. So Save sends one `actions_update` and writes nothing locally:

```
actions_update {set, active, order_land, order_port}
      ↓
server/actions_api.py  — validate against the pool, write the SAME
                         actions.json the desktop editor writes
      ↓
actions {…}            — re-broadcast, and the wheel changes under his finger
```

There is **no optimistic re-render**. The PC owns the file, and the `actions`
frame it broadcasts back is what redraws the wheel — a phone that painted the
new D-pad itself would show a state the PC may have refused, which is the exact
shape of the bug the layout Move handle took four rounds to close.

## Gate

`tests/test_set_editor.py` (fail-closed in `setup/build.py`). Four promises,
each proven by planting its own defect: the edit lands in the USER's
actions.json (driven from a file of an OLDER shape, never `copy(shipped)`); a
non-owner key is refused whole; an id outside the pool is refused; and the
re-broadcast reaches the page. Its last block opens the REAL page in a REAL
Chromium and walks his own path — Settings → Sets → the edit door → untick,
tick, swap, Save — then reads the message off the wire and measures that the
LIVE D-pad changed, because a module nobody calls is a feature that does not
exist (the actions.json lesson of 2026-08-07).

`tests/test_actions_migration.py` carries the other side: what the phone wrote
must survive the NEXT release's shipped-pool merge.

## Related

- [panels.js](panels.md) — the Wheel sets picker this opens from
- [sets.js](sets.md) — which sets ride, and the cap of 8 this never touches
- [controls.js](controls.md) — `activeButtons`, `btnId`, `padColumn`, the D-pad
  this is a picture of
- `server/__about/actions_api.md` — the PC's half
