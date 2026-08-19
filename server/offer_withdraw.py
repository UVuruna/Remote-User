"""A QUESTION WHOSE SUBJECT IS GONE IS TAKEN BACK — the window closed, or a
layout holds it now.

Owner report 2026-08-18, with a screenshot of his phone: *"agenti kad rade …
otvaraju i zatvaraju gomilu prozora i onda meni kada koristim telefon moram
1.000 puta da pritisnem no"* (lang-ok: owner quote). The chip in that shot asks
whether to make a layout out of a window that had closed long before he picked
the phone up — and its yes could not have worked either, because there is no
window behind a dead handle.

Until this round the only things that ever took a chip down were his tap and
the phone's own 30 s timer. Nothing watched the SUBJECT of the question. On a
machine that runs background agents all day (constraint 11) that is a queue of
unanswerable questions waiting for him, one tap each.

This module is the watch. It is the project's oldest rule applied to our own
questions — **measured, never remembered** (constraint 13): an offer is not a
note about a window that once existed, it is a question about the desktop as it
is NOW, and when the desktop stops holding the subject the question goes with
it.

## Why it is its own module

Split from [Layout Popup](layout_popup.py) at THE STRUCTURE LAW's wall, the
same way [Window Rescue](window_rescue.py) was, and by the same test —
responsibility. Every pass in that file asks *whose window is this and where
does it belong*, and each of them ENDS in a question. This one asks nothing and
answers nothing: it is the only code here whose subject is a question already
asked, and whose whole job is to unask it.
"""

import logging

import popup_contain
import popup_offers
import layout_popup
import window_manager as wm

logger = logging.getLogger(__name__)


# Both halves of an offer's life are withdrawn: the chips already on the phone
# (a `window_offer_cancel` frame naming the id) and the frames still waiting in
# `popup_send` for the next flush — a chip that would arrive dead should never
# be sent at all, or the phone shows it for a frame and he sees a flicker he
# cannot answer.
#
# The window's hwnd leaves the `*_asked` sets too, so nothing is left believing
# a question is outstanding. That cannot make the app re-ask about the same
# window: Windows reuses handles, and whatever wears that handle next is judged
# by the sweeps on its own merits — which is the correct answer for a different
# window.
_ASKED_KEYS = ("popup_asked", "birth_asked", "lost_asked")


def _held_by(layouts, hwnd: int):
    """The layout that holds this window — member or adopted — or None."""
    for lay in getattr(layouts, "layouts", None) or ():
        if hwnd in lay.members or hwnd in getattr(lay, "adopted", ()):
            return lay
    return None


def withdraw_moot(conn: dict, layouts=None) -> list[str]:
    """Drop every offer of this connection whose question no longer has a
    subject; returns the ids withdrawn, with their cancel frames queued for
    the next `popup_offers.flush_offers`.

    Two ways a question loses its subject, and both are MEASURED:

    * the window is GONE — `window_manager.is_alive`, the same three questions
      the sweeps themselves are built on (a handle that still exists, visible,
      not cloaked), so a window this module calls dead is exactly one the
      passes next door would no longer offer;
    * the window is HELD by a layout now (owner report 2026-08-19): "make a
      layout with it?" was asked about an UNPLACED window, and the moment he
      placed it — through the other chip, through the panel, through anything
      — the question describes nothing. Left standing, it was answered again
      with a yes, and a second layout was built around a window the first
      already held; closing one closed both. `layouts` is the live registry,
      and None (a caller without one) keeps this half silent.

    Blocking Win32, a handful of calls per open offer — the watcher runs it on
    a worker thread like every other pass."""
    gone: list[str] = []
    for key, offer in list(popup_offers.open_offers().items()):
        if offer.get("conn") is not conn:
            continue
        hwnd = offer["hwnd"]
        holder = _held_by(layouts, hwnd) if layouts is not None else None
        if wm.is_alive(hwnd) and holder is None:
            continue
        popup_offers.drop_offer(key)
        for asked in _ASKED_KEYS:
            conn.get(asked, set()).discard(hwnd)
        gone.append(key)
        if holder is None:
            logger.info("Offer %s withdrawn — %s has closed", key,
                        popup_contain.describe(hwnd))
        else:
            logger.info("Offer %s withdrawn — %s is in layout %r now", key,
                        popup_contain.describe(hwnd), holder.name)
    if not gone:
        return gone
    pending = conn.get("popup_send") or []
    dead = set(gone)
    # A frame that never went out is simply forgotten; only what the phone can
    # actually be showing is worth a cancel frame of its own.
    still_queued = {p.get("id") for p in pending
                    if p.get("type") == "window_offer"}
    pending[:] = [p for p in pending
                  if not (p.get("type") == "window_offer"
                          and p.get("id") in dead)]
    for key in gone:
        if key not in still_queued:
            pending.append({"type": "window_offer_cancel", "id": key})
    conn["popup_send"] = pending
    return gone
