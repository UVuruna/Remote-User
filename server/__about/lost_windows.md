# Lost Windows

**Script:** [Lost Windows (script)](../lost_windows.py) ·
**Flow:** [flow](../__flow/lost_windows.md) ·
**Neighbour:** [Layout Popup](layout_popup.md) · **Gate:** `tests/test_lost_windows.py`

## Purpose

Answer one question about any window on this PC — **can he reach it at all?** —
and, when the answer is no, bring it back on his tap.

## The failure this module exists to prevent

The owner reported it **five times**, the last on 2026-08-12 calling it a
game-breaking bug. An agent finished a job while his phone was LOCKED and
opened its HTML report. It landed outside every screen. He can never bring it
back: a phone has no taskbar, the window is on no monitor, and until this
module nothing in this codebase could move a window it had not itself placed.

## Why four earlier rounds could not even see it

[Layout Popup](layout_popup.md) is the right answer to the window that opens
**while he watches**, and every rule in it stands on `baseline(conn)`: the
windows already standing when the phone connects are filed as KNOWN, so
`_is_new()` answers False for them forever. That is correct there — it is what
stops a layout adopting his second VS Code window.

It also makes his case structurally invisible:

| | |
|---|---|
| phone locked | no connection → no watcher → nobody sees the window open |
| he unlocks | a NEW connection → the baseline finds it standing → filed as old |

A window born during his absence can never be new. Four rounds fixed the LIVE
path, and the live path was never the one he was reporting. **That is the
process lesson, and it is bigger than the bug:** a feature whose trigger is a
connection cannot answer for what happened while there was none.

## So this module asks a different question

Not *who opened this window* — HISTORY, which we do not have — but **can he
reach it**, which is GEOMETRY, measured now. It needs no baseline, no
attribution, no process table and no memory of anything, so it answers for a
window opened by an agent, by Windows, by his PC hours before the phone ever
connected, or by us. There is no case it cannot see.

## The rules

* **Reachable means GRABBABLE, not visible.** A window is reachable when at
  least `GRAB_WIDTH_PX` × `TITLE_HEIGHT_PX` of its TITLE BAR lies inside some
  monitor's work area — what a hand needs to drag it back. A sliver of its
  corner showing at a screen edge is not a way out, and a window whose body is
  on screen while its caption sits above the top edge is just as lost. Pieces
  are never summed across monitors: two 60 px halves either side of a gap are
  not a 120 px handle.
* **A minimized window is judged by where it would RESTORE to**
  (`GetWindowPlacement.rcNormalPosition`). His report window went down with the
  layout that owned it, so a check that skipped minimized windows would have
  found nothing wrong — and restoring it would have put it straight back off
  the screen. A minimized window whose normal position is fine is NOT lost: the
  taskbar reaches it, and so does he.
* **Layout members are never lost.** The layout put them there and can move
  them; a rescue chip over a member would fight the arrangement he asked for.
* **Nothing moves until he taps.** The sweep only ever raises a chip.
* **Restore comes BEFORE the placement.** A minimized window takes
  `SetWindowPos` geometry into its stored placement without coming back, so the
  other order looks like a success and changes nothing he can see.
* **Never topmost** (constraint 10). A rescued window is a normal window on his
  desk; a topmost raise here would strand it above everything for the rest of
  the Windows session, which is what the ledger exists to prevent.
* **The monitor is read at his TAP**, through a callable the web layer puts in
  `conn` — constraint 13's lesson. The chip can stand for half a minute and he
  can switch monitors in it; a remembered rect would land the rescue on a
  screen he walked away from.

## Where it runs

`layout_popup.sweep_lost` every `LOST_EVERY_S`, from
[Focus Guard](focus_guard.md)'s watch loop — **outside** the layout gate, unlike
every other pass there: a window off every screen is lost at the desktop
exactly as it is inside a layout. The chip is the same one
[Layout Popup](layout_popup.md) already owns (`act:"rescue"`), so there is one
strip of screen and one dismissal rule, not a second thing to notice.

## Honest limits

* **Only while a session is live.** A window that goes off-screen with no phone
  connected is found by the first sweep after he connects — seconds, not
  never, which was the whole complaint.
* **A DECLINE is per connection** (`lost_left`), while an unanswered chip is
  re-offered on the next connection. Those mean different things: ignoring a
  chip may simply be missing it while reading the PC screen, and asking again
  is what makes this a guarantee instead of a lottery.
* **A window that refuses every rect** is restored and raised, and the failure
  is logged and reported so the next sweep asks again — never reported as a
  success.
