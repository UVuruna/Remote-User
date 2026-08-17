"""THE WIRE FOR WHAT A LAYOUT'S OWN APPLICATION CAN DO (T29).

Split out of [Layout API](layout_api.py) on 2026-08-17, when that module
crossed THE STRUCTURE LAW's wall — and BY RESPONSIBILITY rather than by line
count, which is the split this project has made every time: `layout_api.py`
answers what layouts EXIST and what may be done TO them (create, focus, grow,
shrink, remove), while these two handlers ask a different question entirely —
what the program a layout is MADE OF can be asked to do, which touches no
layout at all and creates no member.

The catalogue and the injections themselves live one door further in
([Layout Acts](layout_acts.py)), deliberately free of websockets and JSON so
its gate can run it whole. This module is the wire between them: it reads which
layout is focused, hands the act off, and answers the phone.

## The one rule this module carries alone

**An act runs OFF the receive loop, and the phone is answered when it is really
finished.** Both halves were learned from one report (owner 2026-08-17) and
both are written into `layout_act` below — the first because our own handler
starved our own presence watchdog for 25 seconds and minimized his layout under
him, the second because a loading overlay has to end on a fact rather than on a
timer (constraint 15).
"""

import asyncio
import json
import logging

import focus_guard
import layout_acts as layout_acts_mod
from layout_api import focused, toast

logger = logging.getLogger(__name__)


async def layout_acts(ws, layouts, conn: dict) -> None:
    """What the FOCUSED layout's own application can do (owner ballot
    2026-08-13, T29 — the acts group above the New source's standard list).

    Answered even at the desktop, with an empty list and `in_layout: false`:
    the phone draws one group or two off this answer, and a panel that had to
    infer which case it is in from an absent message would be inferring, not
    reading (the same reasoning the two-group creation list already follows —
    constraint 21).

    The catalogue is read from the layout's PROCESS on every ask, never
    remembered: what a layout is made of is a live fact (constraint 13), and
    the Explorer rows are a folder list that changes on his desk."""
    lay = focused(layouts, conn)
    process = lay.process if lay else ""
    rows = await asyncio.to_thread(layout_acts_mod.catalogue, process)
    await ws.send_text(json.dumps({
        "type": "layout_acts",
        "in_layout": lay is not None,
        "app": layout_acts_mod.app_of(process),
        "name": layout_acts_mod.APP_NAME.get(
            layout_acts_mod.app_of(process), ""),
        "entries": rows,
    }))


async def layout_act(ws, layouts, conn: dict, injector, msg: dict) -> None:
    """Run one of them, or say why it was refused — in which case NOTHING was
    injected (`layout_acts.run`, whose first act is the fence check).

    Refused outright at the desktop: every act is an act on a MEMBER, and a
    chord fired with no member to fire it into is exactly the accident
    constraint 11 exists to prevent.

    IT NO LONGER RUNS INSIDE THE MESSAGE LOOP (owner report 2026-08-17, and his
    own log is what dated it). `await asyncio.to_thread(...)` does free the
    event loop, but it does NOT free THIS connection's receive loop — web.py
    awaits this handler before it reads the next message — and one act blocks
    for as long as its work takes: up to `layout_acts.LAUNCH_WATCH_S` (25 s)
    for the act that waits for a window to appear. For those 25 seconds not one
    `hb` was read, so presence did exactly what it is built to do:

        09:37:35 presence: No signal from the phone for 12s — session ends
        09:37:35 presence: Phone left work mode — layout members minimized
        09:37:48 RuntimeError: WebSocket is not connected

    That is the "blockade and a slight disconnect" he reported, and it was our
    own handler starving our own watchdog. The act runs as its OWN task now:
    the loop keeps reading heartbeats, and the answer comes when the work is
    really finished rather than when it was merely started — which is what lets
    the phone hold a loading overlay over the whole wait instead of guessing at
    its length (constraint 15).

    Nothing here is serialized on purpose: two acts are two independent
    injections, each behind its own fence check, and a queue would only make
    the second one act on a desk that has moved since he tapped it."""
    lay = focused(layouts, conn)
    if lay is None:
        await toast(ws, "Nothing was sent — no layout is focused")
        await _act_finished(ws)
        return
    asyncio.create_task(_run_act(
        ws, str(msg.get("id", "")), injector,
        focus_guard.typist(layouts, conn)))


async def _act_finished(ws) -> None:
    """The phone's overlay comes down on THIS and on nothing else.

    Sent on every ending an act can have — done, refused, crashed, or refused
    before it began — because an overlay whose end is one of several different
    messages is an overlay that will one day be left standing over his screen.
    A socket that has gone in the meantime is not an error worth a line: the
    page it fed went with it, and constraint 8 closes this socket every time he
    looks away."""
    try:
        await ws.send_text(json.dumps({"type": "layout_act_done"}))
    except Exception:
        pass


async def _run_act(ws, act_id: str, injector, guard) -> None:
    """One act, off the receive loop. See `layout_act` for why it is a task.

    An unexpected failure is REPORTED rather than swallowed into a silent
    overlay: this is a task now, so nothing above it is left to notice that it
    raised — the traceback would land in asyncio's own handler and the phone
    would sit under a veil waiting for an answer that no longer has anybody to
    send it."""
    try:
        problem = await asyncio.to_thread(
            layout_acts_mod.run, act_id, injector, guard)
    except Exception:
        logger.exception("Layout act %s failed", act_id)
        problem = "Nothing was sent — the PC could not run that"
    if problem:
        await toast(ws, problem)
    await _act_finished(ws)
