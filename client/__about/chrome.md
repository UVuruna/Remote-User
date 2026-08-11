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

- `openMiniRadial(anchorEl, options)` places at most two options around the
  button that opened them, and `miniRadialPoints` is the geometry alone —
  PURE, so its gate drives every corner by argument.
- **An option is a real `.ctl`.** It is built by `makeButton` from
  [Controls](controls.md) — the same 58 px face, the same icon size, the same
  label treatment as the D-pad and the corners. There is no second button
  implementation to drift from them, which is the rule CLAUDE.md constraint 9
  exists for.
- **It leans away from the right edge.** Hide sits in the top-RIGHT corner, so
  a fixed south-east would open off the screen; the pair becomes south /
  south-WEST on the right half. The two directions stay distinct and diagonal,
  which is all a stick needs.
- **It is NOT the category wheel.** No veil, no ring, no centre ✕: the wheel
  replaces the whole screen with a choice of eight, this is two buttons beside
  one corner. A tap anywhere else cancels, exactly like the wheel's backdrop.
- **It blocks auto-hide** (`mini-radial` is in `AUTO_HIDE_BLOCKERS`): it draws
  outside `.group`, so the rule could not see it, and a set of options that
  vanishes while he is deciding between them is what the fence exists to stop.

Its first two users are the Layout button's sources ("From a list" / "Tap a
window", which used to be a full-screen card asking a two-answer question) and
the Hide button's two modes below.

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
- **A blocker still brings the controls back in BOTH modes.** A panel, a card
  or the wheel is something he must READ, and every one of them is reached
  THROUGH the controls — except the two that open themselves (the notices card
  on connect, the dictation card on the first Mic tap). Leaving a card on screen
  with its own controls hidden underneath is not "hidden stays hidden", it is a
  dialog with no way out.

Gate: `tests/test_phone_chrome.py` — the radial's two directions and its
edge lean, both modes' real behaviour, and that STICKY never hides by itself.
