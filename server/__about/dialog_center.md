# Dialog Center — a dialog opens in the middle of its parent, wherever the parent is

Source: [`server/dialog_center.py`](../dialog_center.py) ·
The rule it extends: [Popup Contain](popup_contain.md) (constraint 19) ·
The question it silences: [Layout Popup](layout_popup.md) · [Layout Birth](layout_birth.md) ·
The notice it sends: [Notify](notify.md) · [Notice Channel](notice_channel.md) ·
Driven by: [Focus Guard](focus_guard.md) · Phone side: `client/notify.js` (the jump)

## The report

2026-08-19, and it was a REPEAT of constraint 19 one layout over. His UVuruna
VS Code raised its *"open this link in Chrome?"* box while the phone was showing
ANOTHER layout. The box — 625×189, owned by that VS Code — was offered to him as
a new window, he said yes, and the app built a layout around a dialog that cannot
take a rect. His sentences, which are this module's whole specification:

- not a new window — the middle of **its parent**, not of whichever layout is up;
- if UVuruna's window raised it, the next time he comes to UVuruna it is in the
  middle of that window — and a **notice** says so, whose tap takes him there;
- **no layout at all** — still the middle of its parent.

## Why constraint 19 did not cover it

Its rule lives in [Layout Popup](layout_popup.md), whose every question is
asked of the **focused** layout: *is the owner root one of THIS layout's
members?* The owner was a member of a layout one step along the bar, so rule 1
failed, and rule 2 — *a new window of a member's process* — matched the focused
layout's own VS Code, which shares the exe. Correct rules, asked of the wrong
layout. And `is_listable` did not know what a dialog was, so the chip carried
**Make a layout**.

## What it does

Once a second, beside the birth scan and **outside** the defending gate (the
parent may be in any layout or in none; the phone may be at the desktop), for
every visible top-level window NEW since the desk was last watched:

1. `window_manager.is_dialog(hwnd)` — owned by a **visible** window. Anything
   else is judged once and ignored; so is a window we made ourselves and a
   dialog of our own process.
2. Walk the owner chain to its root. No living, non-minimized root → look again
   next pass (a dialog is often visible a moment before its owner is).
3. Which layout holds the root as a **member**?
   - the **focused** one → not this module's case; rule 1 of Layout Popup has
     placed that since 2026-08-13;
   - **another** one → the dialog is adopted into *that* layout (`adopted` +
     `adopted_home`, so the next `focus()` re-contains it and
     `release_adopted` owes it the way home), centred on its parent with a
     **plain, non-topmost** move (`place_window(..., topmost=False)` — the
     topmost band is the shown layout's alone, and Windows keeps an owned
     window above its owner by itself), and **one** notice is queued:
     `notify.make_notice(layout name, "dialog", …, where={index, name})` — the
     same frame an agent's *needs you* rides on, so the phone's tap jumps
     exactly as it does for an agent;
   - **none** → centred on its parent all the same; no adoption, no notice.
4. A dialog that refuses its rect is tried `MAX_CONTAIN_TRIES` times and then
   left where it is — never fought four times a second.

`flush_notices` runs from the watcher loop — the guard's only async context —
and hands each queued notice to `notice_channel.deliver`, the one carrier.

## What it leaves alone

It moves only dialogs, only new ones, never raises or foregrounds anything and
never touches the topmost band. Everything it adopts is released on the paths
every adopted popup already has.

## The rule underneath

**Measured, never remembered** (constraint 13): the parent's rect and the
dialog's own are read fresh on every pass, and "it will not take a rect" is a
window refusing, not a size we predicted. **A dialog is not a window a layout
could hold** — `is_dialog` is now asked by `is_listable`, so the creation list,
the popup chip and the birth chip refuse it through one definition, and a tap on
a dialog (`window_manager.window_at`) picks the application that raised it.

## Gate

`tests/test_dialog_center.py` — ten checks on the fake desk of
`tests/test_layout_popup.py` extended by a second layout and a lone
application, each proven by planting its own defect (the `held` rule in the
sweep, the notice's jump, the told-once set, the try bound, the focused-layout
exemption). The dialog definition itself is proven through the real
`is_listable` in `tests/test_layout_birth.py`.
