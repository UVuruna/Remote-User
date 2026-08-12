# Chrome — our own furniture

**Flow:** [diagrams](../__flow/chrome.md) ·
**Folder:** [Client](../___client.md) ·
**What drives the PC:** [Controls](controls.md)

## Purpose

The Hide button, the rule that hides the controls after a quiet spell, and the
toast.

Split out of [Controls](controls.md) on 2026-08-08, when auto-hide pushed that
file past THE STRUCTURE LAW's 1,000 lines. The boundary is worth saying out
loud: everything in `controls.js` **drives the PC** — a press becomes a click, a
wheel choice becomes a different set of commands. Nothing in this file ever
reaches the PC. It decides what our own chrome looks like and when it gets out
of the way, which is why it can be reasoned about without knowing the protocol
at all.

## Connections

### Uses

- [Controls](controls.md) — `keepFocus` (the one activator per button)
- [State](state.md) — `statusEl`, `setStatus`, `ws`
- [Layout creation](layout-create.md) / [State](state.md) — `creating`,
  `layoutArm`, read only to know a layout is being built

### Used by

- almost everything, for `showToast(text)`
- [Gamepad](gamepad.md) — a pad press dispatches `ru-pad`, which wakes the
  controls

## Key Functions & Data

| Name | What it does |
|------|--------------|
| `setControlsHidden(hidden)` | The ONE writer of `body.hidden-controls` and of the Hide button's own lit state. Both paths — the button and the timer — go through it, so the two can never disagree. |
| `AUTO_HIDE_MS` | 3000. The owner's number. |
| `AUTO_HIDE_BLOCKERS` | Every overlay that must keep the controls on screen. |
| `autoHideBlocked()` | Whether anything is open that forbids hiding. |
| `lastWake` | When the last contact was. A 250 ms tick compares it against `AUTO_HIDE_MS` — no timer to arm, cancel or leak. |
| `wakeControls()` | Any contact brings them back and re-arms. |
| `showToast(text)` | Borrows the status pill; fades in place rather than snapping back to "Connected". |

## Design Decisions

- **The button stays** (owner 2026-08-08). Auto-hide is the lazy path; the
  button is the immediate one — *"dugme moze uvek da ostane, tacno tako da uvek
  mozemo da ubrzamo da ne cekamo to vreme"* (lang-ok: his own words, quoted).
  They are the same state, which is why one function owns it.

- **The fence is the feature.** Nothing hides while a panel, the settings, a
  layout under construction, or the central set-picking wheel is open — only
  the bare working screen. A card he is reading may not vanish under his thumb.

- **A TICK, not a one-shot timer**, and the phone audit is what proved why. A
  blocker can open with NO touch at all: the notices card offers itself on
  connect, the dictation card opens itself on the first Mic tap, and the audit
  drives every panel through `page.evaluate`. A timer armed at load had already
  hidden the controls by then, so the wheel "opened" inside a `display: none`
  group. That was not an audit artefact — it is the same page his phone runs.
  So the rule is re-decided every 250 ms, and a blocker appearing while the
  controls are hidden **brings them back** rather than merely stopping a
  countdown.

- **ONE guard for the Hide button, not two.** `wakeControls` ignores a press on
  that button, and the handler is then free to read the current state. The
  first version ALSO remembered the pre-press state — and two mechanisms for
  one rule meant neither could be proven: planting a defect in either walked
  straight through the gate because the other covered it. With one, removing
  it fails three checks at once.

- **Blockers are asked by ELEMENT, not by a flag.** A panel added next month is
  covered the moment it uses the same `#id` convention, and a flag someone
  forgot to clear is exactly how a feature like this earns its reputation.

- **Capture-phase listeners.** `pointerdown` fires whatever the target is — the
  canvas, a button, a backdrop — and before anything can stop it propagating.

- **A move only counts while a button is down.** Waking on hover would mean the
  controls never leave, on any device with a stylus or a mouse.

- **The gamepad has its own event.** A pad press is neither a touch nor a
  keydown — the same hole the screen-awake timer fell into (CLAUDE.md
  constraint 12) — and a controller-only session would otherwise sit in front
  of hidden controls it is actively pressing.

- **A toast fades in place.** Going straight back to the "connected" state
  flashed a blue "Connected" pill after every toast (owner 2026-08-04), because
  that state's `opacity: 0` is reached through a 0.4 s transition while its
  blue background applies instantly.

- **The pill's ink comes from its fill**, not from the theme
  ([Theme](theme.md)): `--on-warning` / `--on-error`. It used to pin
  `--text-primary` over a saturated gradient — 1.97:1 on dark, in the element
  that carries every notice this product gives.

## A two-job button drops its options beside it (owner 2026-08-09, task 158)

His instruction, and the reason behind it, in translation: when one of the
buttons up there has two or three functions, the central menu does not open —
those two options simply drop beside it, designed like every other button, with
a picture and with the words that say what they do. The geometry is his too:
SOUTH and SOUTH-EAST, chosen for the ANALOG STICK that is coming, so the same
two directions serve a thumb on a controller later.

- `openMiniRadial(anchorEl, options)` places at most `MINI_MAX` (3) options
  around the button that opened them, and `miniRadialPoints` is the geometry
  alone — PURE, so its gate drives every corner by argument.
- **Two options and three take different directions**, which is why
  `miniAngleSet(count)` writes each list out instead of spreading one from the
  count. A PAIR hangs below the button (SOUTH, SOUTH-EAST — Hide's two modes).
  A FAN opens across the whole free quadrant (EAST, SOUTH-EAST, SOUTH — the
  Layout button's three sources since 2026-08-12), every option 45° from its
  neighbour, which is the same separation the pair has and the reason a thumb
  can pick one without ambiguity. A fourth direction would have to halve that
  separation or leave the quadrant, so `MINI_MAX` says three out loud.
- **An option is a real `.ctl`.** It is built by `makeButton` from
  [Controls](controls.md) — the same icon size, the same label treatment as the
  D-pad and the corners. There is no second button implementation to drift from
  them, which is the rule CLAUDE.md constraint 9 exists for.
- **Its face is 74 px wide, not the corners' 58** (independent grader,
  2026-08-11). A `.ctl` caps its label at 54 px inside a 58 px face, which is a
  2 px inset under a 16 px radius — and ALG-6 ([GUI Rules](../../../../rules/GUI.md))
  wants 0.3·r = 4.8 px, because that is what a rounded corner geometrically
  eats. On the D-pad it never showed: those labels are one short word. These
  two are "From a list" and "Tap a window", the longest strings any face on
  this page carries, and they ran rim to rim. The answer is ROOM, not smaller
  words (the resolution ladder's first rung — the screen around these two
  buttons is empty): 74 px with 10 px of padding puts the same label 11 px
  clear of every edge, measured. **74 is not a taste** — it is the widest face
  that still opens straight below Layout (+) without the screen-edge clamp
  pushing it sideways: that corner's centre is `16 + 58/2 = 45` px in, and
  `74/2 + MINI_EDGE = 45`. A wider face would shift the first option off the
  anchor's axis, which is the geometry the owner chose for the stick and which
  `tests/test_phone_chrome.py` holds to 2 px. `openMiniRadial` therefore hands
  `miniRadialPoints` the OPTION's own size (74), not the anchor's — the clamp
  exists to keep an option on screen and must be told how big one is.
- **It leans away from the right edge.** Hide sits in the top-RIGHT corner, so
  a fixed south-east would open off the screen; the pair becomes south /
  south-WEST on the right half. The two directions stay distinct and diagonal,
  which is all a stick needs.
- **It is NOT the category wheel.** No veil, no ring, no centre ✕: the wheel
  replaces the whole screen with a choice of eight, this is two or three
  buttons beside one corner. A tap anywhere else cancels, exactly like the
  wheel's backdrop.
- **It blocks auto-hide** (`mini-radial` is in `AUTO_HIDE_BLOCKERS`): it draws
  outside `.group`, so the rule could not see it, and a set of options that
  vanishes while he is deciding between them is what the fence exists to stop.
- **It records the angle each option really landed at** (`miniAngles`,
  measured anchor-centre to option-centre AFTER the edge clamp, read by
  `miniRadialAngles()`). That is the CONTROLLER's half of the geometry: a ring
  lets the pad derive a direction from the item count, a fan does not, and a
  right-half anchor mirrors the directions on top of that. Recording what was
  placed means there is one geometry and the stick points at where an option
  IS — constraint 9 again, applied to arithmetic instead of to a handler.

Its users are the Layout button's three sources and the Hide button's two
modes below.

## Hide has two modes, and he named the trade-off himself (task 159)

- **`auto`** — what has always shipped: the controls go after a quiet spell and
  ANY contact brings them back. Its cost, in his words: sometimes he wants to
  move the mouse TO the place the buttons occupy and cannot, because the moment
  the finger moves they are back.
- **`sticky`** — hidden stays hidden until Hide is pressed again; nothing brings
  the controls back by itself, and nothing takes them away by itself either.
  Its cost, also his: the Hide corner is then permanently covered by whatever he
  is doing.

Neither is better, which is why both ship and the choice is his, per device
(`hideMode` through the shell's SharedPreferences bridge, never bare
localStorage — that is per-ORIGIN and split this device's state across the LAN
and Tailscale addresses once already).

- **The primary act is never lost.** A tap on Hide hides — the one thing this
  button has always done. The MODE lives on a HOLD (380 ms, the same hold a
  layout row is picked up by), so a radial can never swallow the press.
- **The hold survives a real finger's jitter** (owner repeat report
  2026-08-11): the timer used to cancel on ANY pointermove, and a fingertip on
  glass moves a pixel within milliseconds — the radial could only open under a
  perfectly still mouse, which is exactly what every gate drove. The hold now
  tolerates 12 px of wander (`HIDE_HOLD_SLOP`, the same allowance
  `hold-gesture.js` gives layout rows); real travel still cancels. Gated WITH
  injected jitter in `tests/test_phone_chrome.py`.
- **A blocker still brings the controls back in BOTH modes.** A panel, a card
  or the wheel is something he must READ, and every one of them is reached
  THROUGH the controls — except the two that open themselves (the notices card
  on connect, the dictation card on the first Mic tap). Leaving a card on screen
  with its own controls hidden underneath is not "hidden stays hidden", it is a
  dialog with no way out.
- **In `sticky` the Hide button itself stays on screen** (owner report
  2026-08-12: pressing Hide made everything vanish for good). `hidden-controls`
  hid the button along with everything else — right for `auto`, where any
  touch brings it all back, and unrecoverable in `sticky`, where by design
  nothing does. His own spec for the mode had already named the exception:
  the one thing that must remain in that mode is the Hide button. So
  `setControlsHidden` — still the ONE writer of this state — also toggles
  `body.hide-sticky` from the live mode, and `client/style.css` hides
  `.corner-tr` only under `body.hidden-controls:not(.hide-sticky)`. The LAYOUT
  corner (`.corner-tl`) goes in both modes: hidden means hidden, and the
  exception is a door out, not a second button.

Gate: `tests/test_phone_chrome.py` — the radial's two directions and its
edge lean, both modes' real behaviour, that STICKY never hides by itself, and
that STICKY leaves the Hide button (and ONLY the Hide button) standing.

## The centered ring is GONE (owner decision 2026-08-12)

Between 2026-08-09 and that date the radial had a SECOND placement. Once the
Layout button's options became three, the owner moved it to the middle of the
screen, behind the category wheel's veil and around the wheel's own ✕ —

> "najbolje da se držimo istog pravila" <!-- lang-ok: owner quote -->

— on the reasoning that a corner cannot hold three unambiguous directions.
Task 228 then grew that ring to four (Recent).

**He reversed it after using it**: the options open BESIDE the button, exactly
like Hide's two modes, in ALL situations — his own check is that it fits phone
portrait too, since the Layout button's row stands above the picture. Recent
left the radial in the same decision (its panel and the whole `layout_recent`
protocol stay — see [Layout create](layout-create.md)). The corner turned out
to hold three directions perfectly well: **E / SE / S**, 45° apart, all inside
the quadrant a top-left button has free, which is what `miniAngleSet` above
now spreads.

So the ring, `MINI_RING_RADIUS`, `miniRingPoints`, the `body.mini-open::before`
veil layer and the `.mini-x` ✕ were **deleted** the same day rather than left
standing unreachable — a second placement nobody opens is exactly the legacy
CLAUDE.md constraint 6 is about. The pad's pointing followed: `padPointedAt`
matches the stick against the recorded angles instead of deriving them from
the count (see [Gamepad](gamepad.md)).

The only ring left on this page is the D-pad's own category wheel
(`wheelPoints`), which is a different component with a different job.

## The layout bar switches by SWIPE too (owner 2026-08-11)

Reported with a screenshot of v0.0.107, in which the bar's corner-sized arrows
had squeezed the name frame so hard that not one letter of the layout name
showed. Two halves of one correction: the arrows shrink to a big glyph in a
very small footprint (`client/layouts.css`), and a **horizontal drag anywhere on
the bar steps the layouts** — so a smaller arrow costs nothing, because the
whole bar became the target.

It lives here because nothing in this file reaches the PC: a swipe calls
`layoutStep`, the very function the arrows call. The listener is in the
CAPTURE phase on `#layout-bar`, which is load-bearing — the bar's inner
controls fire on pointerup, so a drag ending on the framed name would otherwise
step the layout AND open the list. A real swipe stops the event there; anything
under 44 px, or more vertical than horizontal, is left alone and reaches the
button it landed on.

Gate: `tests/test_phone_chrome.py` — the frame keeps at least 60% of the bar,
the arrows stay under 40 px while their glyphs stay 24 px+, and a swipe sends
`layout_focus` while a wobble does not.
