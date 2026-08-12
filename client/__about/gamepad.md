# Gamepad (phone) — the controller, mapped onto the controls that exist

[← client](../___client.md) · code: [gamepad.js](../gamepad.js) · flow: [__flow/gamepad.md](../__flow/gamepad.md)

The Bluetooth game controller (build rounds G1/G2, owner spec 2026-08-07).
The pad pairs with the **phone**, not with the PC, and the WebView does not
reliably expose the Gamepad API — so the Android shell
([Gamepad.kt](../../android/__about/Gamepad.md)) captures every `KeyEvent` and
`MotionEvent` and calls this module. That split is the house rule: the shell
adds only what a browser cannot, and the **mapping lives on the page**, on the
existing protocol. The server learns nothing new — every message a pad
produces (`press`, `click`, `pointer_move`, `scroll`, `key_special`, `chord`,
`layout_focus`) already existed.

## The one law: a pad press IS a button press

Every mapped button goes through `buttonPress()` in
[Controls](controls.md) — the same activator object the finger's `pointerup`
runs. There is no second implementation of what a button does, and there must
never be one: CLAUDE.md constraint 9 exists because a parallel button path is
exactly what died on the real device (an up-only handler that had drifted from
Android's stolen touches killed every control at once). So:

- a **CLICK/HOLD** mouse button held by a pad arrow holds the PC button down,
  between `buttonPress(el, true)` and `buttonPress(el, false)` — identical to a
  finger resting on it;
- every other button acts on the **release**, which is exactly where a
  finger's `pointerup` acts;
- `keepFocus`'s pointercancel rescue and `holdButton`'s stuck-button guarantee
  are untouched, because the pad never sees them — it sees the activator.

Start and Select have no on-screen twin to press, so they call the same
FUNCTIONS the on-screen buttons call: `toggleKeyboard()` (the Keys button) and
`openLayoutPicker()` (the layout bar's framed name).

## The mapping (the owner's table)

| Control | Does | Source |
|---|---|---|
| D-pad ↑ ↓ ← → | the LEFT group's four buttons, **by slot** — the pad presses what he SEES in that direction | his spec |
| △ ◻ ○ ✕ | the RIGHT group's four — △ top, ◻ left, ○ right, ✕ bottom | his spec |
| L1 / R1 **held** | opens that side's category wheel; a stick POINTS; releasing confirms | his spec |
| L2 · R2 | Layout (+) · Hide | his spec |
| L1 / R1 **tapped** | previous / next layout (the ‹ › bar) | adopted (P2) |
| left stick | cursor — speed rises with deflection | adopted (P2) |
| right stick | scroll — vertical (`ry`) AND horizontal (`rx`) | adopted (P2) |
| L3 / R3 | double left click · middle click | adopted (P2) |
| Start · Select | keyboard (Keys) · the layout list | adopted (P2) |

Buttons are named by **position**, never by a vendor's letter: △ ◻ ○ ✕ and
Y X B A sit in the same four places, so `f_up` is the top face button on either
brand and the page never learns which one is in his hands. Slots are looked up
by the grid area `makeActionButton` stamps on the element, so the arrows keep
matching the arrangement even when a set carries its own `order_land` /
`order_port`.

## The stick curve

`padCurve(v)` = deadzone, then a power curve:

```
|v| <= PAD_DEADZONE            -> 0
otherwise  sign(v) * ((|v| - PAD_DEADZONE) / (1 - PAD_DEADZONE)) ^ PAD_CURVE
```

| Constant | Start value | Why that number |
|---|---|---|
| `PAD_DEADZONE` | 0.15 | sticks rest within ~±0.08–0.12 of centre when new and drift further as they wear; 0.15 clears that and still leaves 85% of the travel usable |
| `PAD_CURVE` | 2 | half tilt = a quarter of top speed. Linear (1) makes precise placement on a 4K desktop nearly impossible; cubed (3) leaves the middle of the stick feeling dead |
| `PAD_CURSOR_SPEED` | 0.9 | monitor widths per second at full tilt — a full traverse in ~1.1 s |
| `PAD_SCROLL_TICKS` | 12 | wheel ticks per second at full tilt |
| `PAD_TAP_MS` | 320 | a shoulder held less than this, having pointed at nothing, was a TAP |
| `PAD_POINT_MIN` | 0.45 | well above the deadzone: resting drift must never pick a set |

**These are start values.** The owner's answer to the open question was
"start from this table and tune it on the real controller", so every number
here is meant to move. The gate therefore pins the **shape** and not the
numbers: it reads these constants out of the page and recomputes the expected
coordinate independently, so retuning the feel can never turn a build red
while changing the FORMULA must.

In layout focus the step is scaled by the region's size — the cursor lives
inside one framed window, a fraction of the monitor, and the same tilt must not
fly across it in a tenth of a second. Both a finger and the stick are fenced by
the same `clampRemote()` in [Input geometry](input-geometry.md).

## The wheel, held and pointed

As the user experiences it: **hold L1** and the left group's category wheel
opens; **tilt a stick** and the ring's own frame moves onto the set being
pointed at; **let L1 go** and that set is taken. Let go while pointing at
nothing and nothing changes — and if the whole press was quick, that same
button was the layout ‹ › step instead.

Either thumb may point (whichever stick is further from centre wins): the
sticks have no other job while a wheel is up, and which hand is free depends on
which shoulder is being held. The frame is the wheel's existing `.current`
ring, so no new styling was needed; released back to centre it returns to the
set the group is actually showing.

`openWheel()` places item *i* at `-PI/2 + i * 2PI/n` — i = 0 straight up,
increasing *i* sweeping clockwise — so the stick's own angle, turned a quarter
turn, IS the index.

## What the pad may never leave behind

- A held pad button remembers the **element** it pressed, not the slot: a
  category switch re-renders the group and throws the button away, and a PC
  mouse button left down would never be released.
- Pressing a shoulder releases everything held first — nothing of ours may
  stay pressed under an open wheel.
- The shell's `onPause` calls `releaseAll()`, so leaving the app lifts every
  pad button and zeroes both sticks.
- **A pad press holds the screen awake** (`padAwake()` → `touchedNow()`, at
  most once every `PAD_AWAKE_THROTTLE_MS`). A pad press is neither a touch nor
  a keydown — the shell claims it at `dispatchKeyEvent` and hands it over
  through `evaluateJavascript` — so the two listeners in
  [Connection](connection.md) never hear it. Without this, a session driven
  ENTIRELY from the controller goes dark after `KEEP_AWAKE_MS`, the page hides,
  and the PC correctly packs the layout away in the middle of the work.

## Horizontal scroll (owner spec — "scroll vertikalni i horizontalni")

`padScrollStep(dt)` now spends BOTH right-stick axes when no wheel is open:
`ry` still drives the vertical `ticks` exactly as before, and `rx` drives a
second sub-tick accumulator (`padScrollAccH`) into `hticks` on the SAME
`PAD_SCROLL_TICKS` rate. The `scroll` message only grows the `hticks` key when
there is a whole horizontal tick to send (`if (wholeH) msg.hticks = wholeH`) —
a pure-vertical push is byte-for-byte the message this project sent before
this round, and an old page (or the finger's own Scroll mode in
[Gestures](gestures.md)) that never sets `hticks` still reaches
`InputInjector.wheel()` with it defaulted to 0.0, i.e. vertical-only, no
`MOUSEEVENTF_HWHEEL` at all (see [Input Injector](../../server/__about/input_injector.md)).

**Sign — no negation, unlike the vertical axis.** Pushing the stick RIGHT must
scroll right. Windows documents `MOUSEEVENTF_HWHEEL`'s positive `mouseData` as
"the wheel was tilted to the right"
([learn.microsoft.com/.../wm-mousehwheel](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-mousehwheel)),
and Android reports the right stick's `AXIS_Z`/`AXIS_RX` the same way normal
touch/screen X coordinates work — positive is right, not inverted. The
vertical axis needs `ticks: -whole` because Android's Y axes (`AXIS_RZ`/
`AXIS_RY`) report "up" as NEGATIVE while Windows' `MOUSEEVENTF_WHEEL` documents
"forward, away from the user" (= up) as POSITIVE — that mismatch is what the
existing negation corrects. X has no such mismatch on either side, so `hticks`
is `wholeH` unchanged: `rx > 0` (right) → `hticks > 0` → `MOUSEEVENTF_HWHEEL`
positive → Windows' own "tilted right".

## Used by
- [Controls](controls.md) — `buttonPress`, `groupButton`, `openWheel`/
  `closeWheel`, `groups`/`renderGroup`, `toggleKeyboard`
- [Layouts](layouts.md) — `layoutStep`, `openLayoutPicker`
- [Input geometry](input-geometry.md) — `sendCursor`, `clampRemote`
- [Gamepad (Android)](../../android/__about/Gamepad.md) — calls
  `__padButton` / `__padAxis` / `__padInfo`
- [Tests (folder)](../../tests/___tests.md) — `test_input_pipeline.py` drives
  the real mapping with synthetic pad events (fail-closed in `build.py`)

## L2 carries the Layout button's two jobs (owner 2026-08-09, task 186)

His sketches said L1; L1 held is already the left category wheel, so the
mapping flag was raised and he moved it:

> "aha ok onda L2, u pravu si" <!-- lang-ok: owner quote -->

* **Tap** — arms the tap-pick, exactly as the Layout button did before it grew
  a radial (`layoutTapSource`, which is also what the button itself runs when a
  creation is already live: the second tap cancels).
* **Hold** — opens the layout-birth radial, the stick points at an option and
  the release takes it. Releasing while pointing at nothing changes nothing;
  a hold shorter than `PAD_TAP_MS` was the tap. Since 2026-08-12 that radial
  is an anchored FAN beside the Layout button rather than a centered ring, so
  the directions are **New = east, Tap = south-east, List = south** (see
  [Chrome](chrome.md)).

**Pointing at a fan is not pointing at a ring**, and the pad now says which it
is doing. `padStickAngle()` answers where the pointing thumb is aimed (or null
inside `PAD_POINT_MIN`), and two readers sit on it: `padPointedIndex(items)`
for the category WHEEL, where the items divide the whole circle and every
direction belongs to exactly one, and `padPointedAt(angles)` for the radial,
which matches the stick against the angles `chrome.js` recorded when it PLACED
the options — nearest wins, and only inside `PAD_POINT_CONE` (60°, wider than
the fan's own 45° spacing so neighbouring cones overlap and a thumb between
two options still picks one). The cone is what keeps "released at nothing" a
real answer: a fan leaves most of the circle unclaimed, while a ring never
could, and the ring arithmetic applied to three options would have answered
"north = New" for a thumb pointing away from every one of them.

That is `padShoulderPress` with a different menu in it, deliberately: the owner
learns ONE grammar and it is already the one his shoulders speak. The radial
itself is opened by `openSourceChooser` — the very function the finger runs —
and confirmed through the option element's own handler, so there is no
controller-only option list to drift from the touch one (constraint 9).

R2 keeps its own two modes (tap = hide now, hold = the Hide radial).

Gate: `tests/test_birth_radial.py` — hold opens, the stick lights the option it
points at, the release runs that option's real handler, a long release at
nothing does nothing, and a tap arms the pick.
