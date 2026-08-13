# The New source — a window that is not open yet, and this layout's own acts

Source: [`client/layout-new.js`](../layout-new.js) ·
Server halves: [`server/recents.py`](../../server/__about/recents.md),
[`server/layout_acts.py`](../../server/__about/layout_acts.md) ·
Wizard it feeds: [`client/layout-create.js`](layout-create.md)

## Why it is its own file

Split out of `layout-create.js` on 2026-08-13, at THE STRUCTURE LAW's wall and
by RESPONSIBILITY rather than by line count. `layout-create.js` is the WIZARD:
it owns one piece of state (`creating`), collects slots over several taps and
ends in a single `layout_create`. Everything here is about the PC's own
PROGRAMS — what they can OPEN, and what the focused layout's app can DO. The
two questions have different owners on the server too.

## The two groups, and why the panel is TOLD which case it is in

Opened from inside a layout the panel shows two groups; from the desktop, one.
That is the owner's rule for the creation list (constraint 21) applied here
(his ballot, 2026-08-13, T29).

```
  From a LAYOUT (VS Code)            From the DESKTOP
  ┌────────────────────────────┐     ┌────────────────────────┐
  │ Open a window              │     │ Open a window          │
  │ IN THIS LAYOUT — VS Code   │     │ VS Code                │
  │  ▸ New Claude Code         │     │  ▸ New window          │
  │  ▸ New window, same folder │     │    ▸ VibeCoder  ALREADY OPEN
  │ VS Code                    │     │    ▸ PromptPainter     │
  │  ▸ New window              │     │ Chrome …               │
  │    ▸ VibeCoder  ALREADY OPEN     └────────────────────────┘
  └────────────────────────────┘
```

`in_layout` arrives ON the `layout_acts` answer instead of being deduced from
the layout bar: the page can READ a field and cannot check an inference. Same
reasoning as the two-group creation list carrying `group` on every entry.

There is no timer around the ask (constraint 15 — we never estimate how long
another program needs). The standard list renders when the HTTP list lands and
gains its top group when the socket answers; a connection that dies takes the
whole panel with it, which is already true of every other panel here.

## A row that cannot be tapped LOOKS like one

His report of 2026-08-13 (picture 1): he tapped a recent folder VS Code already
had open, VS Code answered by raising the window it already held, no new window
ever came into being, and he watched the loading cube out. The server now marks
such a row `open` with its `why`; here it is drawn dimmed, with the reason as a
pill on the row, and the tap handler is **never attached** — a real `disabled`
button, because a handler that decides to do nothing is a handler that one day
forgets to.

The row is still SHOWN rather than dropped, on his own ballot: a project simply
missing from the list is a thing he would hunt for, while a dimmed row with a
reason answers the question he came with. The dimming floor (`.55`) is chosen
so the folder name stays readable — knowing WHICH project it is, is the point.

## What an act row does, and what it deliberately does not

A tap sends one `layout_act` and closes the wizard silently. None of these acts
produces a SLOT (a conversation, a tab, a folder), so leaving the creation
panel standing would promise a **Create** button with nothing to create.

The one act that really opens a window — VS Code's "New window, same folder" —
still does not join the layout by itself. That is his tap on the ordinary
window offer, never ours (constraints 18 and 19). The server marks that window
as OURS for the popup sweep's own attribution
([`layout_popup.mine`](../../server/__about/layout_popup.md)), which is a
different statement: it stops the phone asking about a window he had just asked
us to open, and it does not decide anything for him.
