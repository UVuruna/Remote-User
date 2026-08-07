# Gamepad (Android)

**Script:** [Gamepad.kt](../app/src/main/java/com/uvuruna/remoteuser/Gamepad.kt)

## Purpose

Forward a Bluetooth game controller to the page (build round G1, owner spec
2026-08-07). The pad pairs with the **phone**, and the WebView does not
reliably expose the Gamepad API — but this shell sees every button as a
`KeyEvent` and both sticks as a `MotionEvent`. So the shell captures and
forwards, which is the house rule stated exactly: *the shell adds only what a
browser cannot*.

## What this is NOT

The mapping. Which button presses which on-screen control, how far a stick has
to tilt, what the cursor does with it — all of that is the page's
([Gamepad (phone)](../../client/__about/gamepad.md)), on the existing
protocol. Two consequences that are the whole reason for the seam:

- the **PC needs nothing new** — every message a pad produces already existed;
- a mapping change ships with the PC's page, not with a new APK.

This file is an **adapter**: platform events in, three page callbacks out, no
policy of its own. That is why it is Standard tier rather than Algorithmic,
the same reading as [Bridge](Bridge.md).

## Position names, never vendor letters

Android reports △ ◻ ○ ✕ on a PlayStation pad as the same `BUTTON_Y/X/B/A` an
Xbox pad sends, and those four sit in the same four places on both. So the
names crossing to the page are positional — `f_up`, `f_left`, `f_right`,
`f_down`, `d_up`…, `l1`, `r1`, `l2`, `r2`, `l3`, `r3`, `start`, `select` — and
the page never learns which brand is in the owner's hands.

## Three sources, one press

The same physical press can arrive more than once: a D-pad as `KEYCODE_DPAD_*`
**and** as `AXIS_HAT_X/Y`, a trigger as `KEYCODE_BUTTON_L2` **and** as
`AXIS_LTRIGGER`/`AXIS_BRAKE`. Holding a button repeats its key forever. So
every name goes through `set()`, which emits only on a real change — the page
therefore sees a clean down/up pair per press and needs no deduplication of
its own.

Right-stick axes differ too: `AXIS_Z`/`AXIS_RZ` on most modern pads,
`AXIS_RX`/`AXIS_RY` on some older ones. Whichever the device actually declares
(`getMotionRange`) is the one read; the device's own `flat` slop is zeroed
before the value crosses, and the page's deadzone sits on top of that.

## Why the keys are taken at `dispatchKeyEvent`

`MainActivity` overrides `dispatchKeyEvent` / `dispatchGenericMotionEvent`, so
pad events are claimed **before the view hierarchy sees them**. The WebView's
own D-pad focus handling would otherwise fight the mapping for every arrow
press. Anything not from a `SOURCE_GAMEPAD`/`SOURCE_JOYSTICK` device falls
straight through untouched — a Bluetooth keyboard's arrows still belong to the
page.

## Nothing may be left held

`releaseAll()` lifts every held button and zeroes both sticks, and
[MainActivity](MainActivity.md) calls it from `onPause`. Without it, a release
this shell never saw (the app backgrounded mid-press) would leave a PC mouse
button down for the rest of the session — the pad's version of the stuck-button
guarantee the on-screen buttons already carry.

## Diagnostics

`__padInfo` — one line per controller the first time it sends anything (its
name and the axes it declares), plus any keycode the table does not know. It
goes to the **PC's server log** via `client_log`, never to a panel on the
phone: the same rule the dictation diagnostics live by (owner, round 2
2026-08-05, angrily). It is the only way to identify an unfamiliar controller
on the owner's own device without putting anything in his face.

## Used by
- [MainActivity](MainActivity.md) — owns the instance, routes the two dispatch
  overrides into it, and releases it on `onPause`
- [Gamepad (phone)](../../client/__about/gamepad.md) — the receiving end:
  `window.__padButton`, `window.__padAxis`, `window.__padInfo`
