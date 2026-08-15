"""One task per connection: the Claude wheel appears the moment the process
table says so, not only on the next `layout_state` a human action already
caused.

Owner report 2026-08-15: he built a new layout on a VS Code window that was
still loading its previous Claude conversation. `agents_in()` answered empty
at that instant — the transcript had not been written yet — and the wheel
stayed silent until he switched to Desktop and back, because nothing else
ever re-asked. `layout_state.state()` already computes `agents` live on every
send (`agents.live_agents()`, `server/agents.py`); the gap was that nothing
re-SENT it when the process table changed on its own, between the human
actions (focus, switch, aspect, member add/remove) that already trigger a
send. This is that missing trigger, and only that — it never touches a
window, never places anything, and it changes nothing else `layout_state`
already carries.

Same family as `caret.watch` / `clipboard_sync.watch` / `focus_guard.watch`:
started in `web.py` alongside them, cancelled with the connection, and quiet
while the phone is not actually looking (see `_defending`-style away/left
check below).

NEVER SPAM. Constraint 27's own lesson — a `layout_state` that changes
nothing keeps the pinch and must never be sent for nothing else's sake
either — so this task computes a comparable SIGNATURE of "which agents does
each live layout hold" and re-sends through the one existing choke point,
`layout_api.send_layout_state`, only when that signature actually moved.
"""

import asyncio

import agents
import layout_api

# Slow enough that the process-table scan (`agents._scan`, a `Path.iterdir`
# walk plus process-table reads) is not run needlessly often, fast enough
# that a Claude conversation which finishes loading a few seconds after the
# layout was made reaches the wheel without the owner doing anything.
POLL_S = 5.0


def _signature(layouts) -> tuple:
    """One fact per live layout worth re-telling the phone: which agent
    tools it holds, by identity so a rename or a re-ordered list never reads
    as a change. `live_agents()` is `agents.py`'s own 2 s cache — calling it
    here costs nothing beyond what `layout_state.state()` already pays on
    every ordinary send."""
    live = agents.live_agents()
    return tuple(
        (id(lay), tuple(agents.agents_in(lay.project(), live)))
        for lay in layouts.layouts)


async def watch(ws, layouts, conn: dict) -> None:
    """While a phone session is live, notice a process-table change that
    `layout_state` was never asked about and say so — once, only when the
    answer actually moved.

    Goes quiet while the phone is away (an excursion or a leave): nobody is
    reading the wheel then, and a send now would only teach the returning
    connection's own resume logic to race it."""
    last = await asyncio.to_thread(_signature, layouts)
    while True:
        await asyncio.sleep(POLL_S)
        if conn.get("away") or conn.get("left"):
            continue
        if not layouts.layouts:
            continue
        try:
            sig = await asyncio.to_thread(_signature, layouts)
        except RuntimeError:
            return   # socket closed under us — the receive loop logs it
        if sig == last:
            continue
        last = sig
        try:
            await layout_api.send_layout_state(ws, layouts, conn)
        except RuntimeError:
            return
