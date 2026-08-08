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
