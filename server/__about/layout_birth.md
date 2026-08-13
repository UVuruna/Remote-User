# Layout Birth — a layout from a window he just opened

[← Server index](../___server.md) · [Flow](../__flow/layout_birth.md) ·
[Source](../layout_birth.py)

He double-clicks a picture or an `.xlsx` through the stream, the viewer or
Excel opens, and the phone asks whether to make a layout with it. That is the
whole feature (owner request 2026-08-09, task 185).

## Why it is a separate module

It shipped inside [Layout Popup](layout_popup.md), whose subject is the
opposite one:

| | Layout Popup | Layout Birth |
|---|---|---|
| Whose window | the LAYOUT'S work opened it | HE opened it |
| What must happen | it must be brought into the picture | nothing, until he says so |
| Evidence | owner chain / process / ancestry | an injected double-click |

Living in one file made them read as one feature, and on 2026-08-12 that cost
him a moved window: both fired on the same window in the same tick, the phone
showed only the last chip, and his tap answered a question he had never read.
The split happened on 2026-08-13, when the popup module crossed the structure
law's wall — but the wall only forced the timing; the responsibilities are why
the cut fell here.

## The rules

* **A phone session must be live.** It runs inside
  [Focus Guard](focus_guard.md)'s watcher and stands down while the phone is
  away — those windows belong to his desk again.
* **A NEW top-level window, never a dialog.** `window_manager.list_windows`
  drops tool windows, cloaked windows, shell chrome, untitled windows and our
  own process; an OWNED window (`GW_OWNER`) is somebody's dialog.
* **Correlated with an injected DOUBLE-CLICK** (`DOUBLE_CLICK_S` = 0.7 s,
  `BIRTH_AFTER_CLICK_S` = 15 s). This PC is never quiet — background agents
  launch GUI apps all day — so "a window appeared" is evidence of nothing.
  No click, no question.
* **A window WE made is never his question** (`layout_popup.mine`, owner
  report 2026-08-13). Tearing a tab off is a double-click followed by a
  brand-new window of a member's process: every rule above is *correct* about
  it, which is exactly why no rule can fix it. Only the maker knows.
* **A window the focused layout can claim belongs to the other module.** One
  window, one question (constraint 18).
* **It never touches the PC.** No placement, no raise, no foreground — the
  offer is a sentence on the phone, and his yes opens the ordinary creation
  panel.

## Honest limits

* The click correlation is a **coincidence window, not proof**. A background
  agent's window landing inside the grace is offered too. The cost is a chip
  he can ignore, never a moved window.
* `mine()` records expire after `OURS_TTL_S`. A window handle is a number
  Windows re-uses, and a permanent record would one day mute a chip about a
  stranger's window that inherited it.

## Gate

`tests/test_layout_birth.py`, fail-closed in `setup/build.py`. Each defence is
proven by planting its own defect.
