"""CAN HE REACH IT — the one question here that needs no history at all.

Split out of [Layout Popup](layout_popup.py) on 2026-08-17 at THE STRUCTURE
LAW's wall, and BY RESPONSIBILITY. Every other pass in that module asks whose
window this is and answers from EVIDENCE — an owner chain, a process, a click,
a baseline of what stood here before. This pass asks something a measurement
answers outright: is a grabbable piece of this window's title bar inside some
monitor's work area, right now. That is why it is the only pass that can speak
for a window opened hours before the phone ever connected (constraint 17), and
why it runs at the DESKTOP as well as inside a layout — a lost window is lost
either way.

It rides the SAME chip as everything else (one strip of screen, one dismissal
rule) through [Layout Popup](layout_popup.py)'s `queue_offer`, and the geometry
itself belongs to [Lost Windows](lost_windows.py). This module is the sweep
between them.
"""

import logging
import time

import layout_popup
import lost_windows

logger = logging.getLogger(__name__)


# ═══════════════════ AND THE WINDOW NOBODY CAN REACH ═══════════════════
# Owner report 2026-08-12, the FIFTH on one failure: a window that opened while
# his phone was LOCKED sits off every screen and can never be shown again.
#
# Everything above this line asks WHO opened a window, and every one of those
# rules is built on `baseline` — which is exactly why none of them could ever
# see his case: a window born while no phone was connected is filed as KNOWN by
# the next connection's baseline and is never new again. See
# [Lost Windows](lost_windows.py) for the whole diagnosis.
#
# So this pass asks a different question — CAN HE REACH IT — which is geometry,
# measured now, and needs no history at all. It therefore answers for a window
# opened by an agent, by Windows, or hours before the phone ever connected.
#
# It rides the SAME chip as everything else here (one strip of screen, one
# dismissal rule) and, unlike every other pass in this module, it runs at the
# DESKTOP as well as inside a layout: a lost window is lost either way.
LOST_EVERY_S = 4.0


def _offer_lost(conn: dict, win: dict) -> None:
    """Queue the "bring it back?" chip for a window nobody can reach."""
    hwnd = win["hwnd"]
    layout_popup.queue_offer(conn, hwnd, "l", {"lay": None, "lost": True},
                {"act": "rescue", "title": win.get("title", ""),
                 "process": win.get("process", ""), "hwnd": hwnd,
                 "icon": win.get("icon")}, "lost_asked")
    logger.warning("Window %s is off every screen (%s%s) — rescue offered",
                   layout_popup._describe(hwnd), win.get("rect"),
                   ", minimized" if win.get("minimized") else "")


def sweep_lost(layouts, conn: dict) -> None:
    """One pass over the unreachable. Blocking Win32 — the watcher runs it on
    a worker thread, on its own slow cadence.

    ONE CHIP PER WINDOW PER CONNECTION (`lost_asked`), and ignoring it is an
    answer — but a DELIBERATE decline is remembered separately (`lost_left`),
    because the two mean different things: an unanswered chip may simply have
    been missed while he was reading the PC screen, and the next connection
    asking again is the behaviour that makes this a guarantee rather than a
    lottery. A window he actually said "leave it" about is never raised again
    on this connection."""
    if conn.get("away") or conn.get("left"):
        return
    now = time.monotonic()
    if now - conn.get("lost_swept", 0.0) < LOST_EVERY_S:
        return
    conn["lost_swept"] = now
    # A layout's own windows are where the layout put them and the layout can
    # move them; offering a rescue there would fight it.
    held: set[int] = set()
    for lay in getattr(layouts, "layouts", []) if layouts is not None else []:
        held.update(lay.members)
        held.update(getattr(lay, "adopted", ()))
    asked = conn.get("lost_asked", ())
    left = conn.get("lost_left", ())
    for win in lost_windows.lost(held):
        hwnd = win["hwnd"]
        if hwnd in asked or hwnd in left:
            continue
        if layout_popup._is_ours(hwnd):
            # A WINDOW HE JUST ASKED FOR IS NEVER A QUESTION, AND THIS PASS
            # NEVER ASKED IT (found by an independent agent, 2026-08-17). Every
            # other pass in this module has consulted `_is_ours` since the rule
            # was written; this one was added later, for a different question
            # (can he REACH it), and simply never learned it. So a window we
            # opened on his tap that happened to land off-screen — which is
            # exactly what a freshly opened window does before anything places
            # it — could be handed back to him as "this is lost, shall I
            # rescue it?", with every other defence in the file intact and
            # bypassed. It is not a variant of the race the claim above closes:
            # here the guard was never late, it was absent.
            continue
        _offer_lost(conn, win)
