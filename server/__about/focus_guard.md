# Focus Guard

**Script:** [Focus Guard (script)](../focus_guard.py)

## Purpose
Decide **where the phone's typed input lands** — before a single key is
injected, instead of letting Windows decide it afterwards.

`SendInput` has no target. Every character the phone dictates or types goes to
whatever window Windows calls the FOREGROUND at that instant, so anything on
the PC that takes focus while the owner speaks takes the rest of his sentence
with it — silently, with the stream still showing the PC and no error anywhere.

Split out of [Web Layer](web.md) on 2026-08-06 (THE STRUCTURE LAW): one
responsibility, its own rules, its own failure history and its own gate
(`tests/test_focus_guard.py`).

## The failure this module exists to prevent
Owner report, 2026-08-06 — three trips back to the phone in one evening, and
the fourth report was the bug itself: a sentence he dictated **for another
project** arrived in *this* project's session. Mid-dictation the PC's focus
moved, and the words simply followed it:

```
he taps Mic  →  speaks  →  key_text "…" → foreground = his text box   ✔
             →  something on the PC takes focus (app start, dialog, agent)
             →  speaks  →  key_text "…" → foreground = SOMEONE ELSE'S window ✘
```

Nothing in the app could notice: the injector had no idea which window it was
aiming at, and the phone had no way to be told.

## The rules
1. **In a layout, the fence is the layout.** The phone is looking at that
   layout's member windows and at nothing else, so its keyboard may reach
   nothing else. A foreground outside the members is refused: focus goes back
   to the member the phone was last typing into, and only then do the keys go
   out.
2. **At the full desktop the guard builds a fence.** The window that held
   focus when the typing burst began IS the target, and it is re-armed only by
   things the owner did on purpose — an injected click (`pointer_down`,
   `click`, `press`), `next_input`, a layout switch, a monitor switch
   (`RETARGET_KINDS` in [Web Layer](web.md)). A thief arms nothing: it sends
   no message.
3. **A dialog of the target is the target.** Save As… is a window of its own
   and would fail both tests above, so ownership is walked up (`GW_OWNER`).
   Process identity is deliberately NOT used — every VSCode window shares one
   process, and one of those windows is exactly the thief.
4. **The thief is NAMED in the log** (exe + title + hwnd), every time. Being
   the last to find out is what made this bug cost three reports; a restored
   keystroke that logged nothing would only hide the next cause.

## Which member holds the keyboard
The target survives the connection, because the connection does not survive an
excursion: a picker or a permission dialog closes the socket by rule
([Presence](presence.md)), and the page re-focuses the layout on the new one.
So `Layout.last_member` lives in the registry ([Window
Manager](window_manager.md)), is updated whenever the guard sees a legitimate
member in front, follows a `prune` when that window is closed at the desk, and
is what `LayoutRegistry.focus()` raises **last** — the second half of the same
bug. Raising members in plain list order handed the keyboard to whichever
window sat last in the grid, so one excursion was enough to move his dictation
into the other pane.

## Cost
One `GetForegroundWindow` (plus at most eight `GetWindow` owner hops) per
typing message, on a worker thread. A raise happens only when focus was
actually stolen — the normal path touches no window at all.
