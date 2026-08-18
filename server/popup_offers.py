"""THE CHIP: the question the phone asks about a new window, and his tap.

Split out of `layout_popup.py` on 2026-08-18 (THE STRUCTURE LAW, VC-R5). One
responsibility — the offer registry, its expiry, the frames that carry a chip
to the phone, and `pick()`, which is where every answer he can give lands.

Every question this project asks about a window goes through `queue_offer`,
including the ones raised next door ([Layout Birth](layout_birth.py), [Lost
Windows](lost_windows.py)): each of them used to keep its own copy of the same
eight lines of bookkeeping, and three copies of that dance is three places for
the day one of them stops matching the others.
"""

import asyncio
import json
import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse

import lost_windows
import notice_channel
import popup_contain
import window_manager as wm

logger = logging.getLogger(__name__)

# How long an unanswered offer is kept. He is allowed to ignore the chip —
# that IS an answer, and the answer is "leave it on the desktop" — so this is
# only about not growing a dictionary for the life of the process.
OFFER_TTL_S = 10 * 60

# id -> {hwnd, lay, conn, at}. Module-level rather than per-connection because
# the answer comes back over HTTP (`register` below), which has no socket and
# no `conn` — the id is the whole handle. An offer whose connection has since
# died still resolves safely: the layout is checked, and a window that closed
# meanwhile is refused.
_OFFERS: dict[str, dict] = {}
_NEXT_ID = 0


def _expire() -> None:
    cutoff = time.monotonic() - OFFER_TTL_S
    for key in [k for k, o in _OFFERS.items() if o["at"] < cutoff]:
        del _OFFERS[key]


def queue_offer(conn: dict, hwnd: int, prefix: str, held: dict,
                payload: dict, asked_key: str) -> str:
    """Register one chip and queue it for the phone; returns its id.

    ONE FUNCTION FOR ALL THREE QUESTIONS this module asks (and for task 185's,
    which lives next door). Each of them used to keep its own copy of the same
    eight lines — expire, bump the counter, mint a key, file the offer, mark
    the window as asked, append the frame — and three copies of a bookkeeping
    dance is three places for the day one of them stops matching the others."""
    global _NEXT_ID
    _expire()
    _NEXT_ID += 1
    key = f"{prefix}{hwnd:x}-{_NEXT_ID}"
    _OFFERS[key] = {"hwnd": hwnd, "conn": conn, "at": time.monotonic(), **held}
    conn.setdefault(asked_key, set()).add(hwnd)
    conn.setdefault("popup_send", []).append(
        {"type": "window_offer", "id": key, **payload})
    return key


def offer(lay, hwnd: int, conn: dict, reason: str) -> str:
    """Queue the phone's two-button chip for this window and return its id.

    ONE PROMPT PER WINDOW (`popup_asked`): the watcher runs four times a
    second, and a chip that reappeared on every tick would be worse than the
    bug it answers."""
    # THE CHIP CARRIES BOTH ACTS (owner report 2026-08-17, and he has reported
    # this one more times than any other bug in this project). While a layout
    # is focused this sweep is the ONLY question a new window can raise —
    # `layout_birth.scan` stands down for anything this module can claim, which
    # is the one-window-one-question rule of constraint 18 — so "Move it in"
    # was the only thing the app could ever offer him there. His case is the
    # one that happens every day: an agent finishes, its HTML report opens in
    # Chrome, and what he wants from that window is a LAYOUT, not a corner of
    # the one he is already in. The old shape could not express it, whatever he
    # tapped.
    #
    # The answer is NOT a second chip — that is exactly what cost him a moved
    # window on 2026-08-12 (constraint 18: one strip, one live offer id, so a
    # second question silently replaces the first under his finger). It is one
    # chip with three answers: Make a layout · Move it in · Leave. The window's
    # own identity rides along (`hwnd`/`icon`), because "Make a layout" seeds
    # the ORDINARY creation panel with it — the identical mechanics of Tap,
    # List and New, and not a path of its own.
    key = queue_offer(conn, hwnd, "", {"lay": lay},
                      {"title": wm._title(hwnd),
                       "process": wm._process_name(hwnd),
                       "hwnd": hwnd,
                       "new_ok": True,
                       "icon": wm.icon_data_uri(wm._process_path(hwnd)),
                       "layout": lay.name}, "popup_asked")
    logger.info("Popup %s offered to the phone as %s (%s)",
                popup_contain.describe(hwnd), key, reason)
    return key


async def flush_offers(conn: dict) -> int:
    """Send whatever the watcher queued, over the page's own socket. Returns
    how many went out.

    The socket comes from [Notice Channel](notice_channel.py)'s one-device slot — the web
    layer's own registry, which this project deliberately keeps only one of.
    A phone that is gone simply drops the chip: an offer is about a window
    that opened just now, and a chip arriving after the next connection would
    ask him about something he has long since walked past."""
    pending = conn.get("popup_send")
    if not pending:
        return 0
    ws = notice_channel.page_socket()
    if ws is None:
        pending.clear()
        return 0
    sent = 0
    while pending:
        payload = pending.pop(0)
        try:
            await ws.send_text(json.dumps(payload))
        except Exception as e:      # noqa: BLE001 — a dead socket must not kill the watcher
            logger.warning("Window offer not delivered: %s", e)
            pending.clear()
            break
        sent += 1
    return sent


# THE OFFERS ARE READABLE FROM OUTSIDE, so a question can be UNASKED
# (owner report 2026-08-18). [Offer Withdraw](offer_withdraw.py) is the only
# caller: it takes back the chips whose window has closed, which is a subject
# of its own and lives in its own file. Two functions rather than a shared
# dictionary, so the registry keeps one owner and every removal still goes
# through this module.
def open_offers() -> dict:
    """Every unanswered offer, keyed by id."""
    return _OFFERS


def drop_offer(key: str) -> dict | None:
    """Forget one offer; returns it if it was still open."""
    return _OFFERS.pop(key, None)


def pick(offer_id: str, act: str) -> bool:
    """His tap. `act` is "layout" (place it by the rules above) or anything
    else, which is "leave it on the desktop" — the safe answer, so an act we
    do not recognise lands on the one that moves nothing.

    Blocking Win32 on the accept path; the route below runs it in a thread."""
    _expire()
    offer = _OFFERS.pop(offer_id, None)
    if offer is None:
        return False
    lay, hwnd, conn = offer["lay"], offer["hwnd"], offer["conn"]
    if offer.get("lost"):
        # THE RESCUE (owner report 2026-08-12). `act` is "rescue" or anything
        # else, which is "leave it" — the safe answer, so an act we do not
        # recognise lands on the one that moves nothing, exactly as below.
        conn.get("lost_asked", set()).discard(hwnd)
        if act != "rescue":
            conn.setdefault("lost_left", set()).add(hwnd)
            logger.info("Lost window %s left where it is — his choice",
                        popup_contain.describe(hwnd))
            return True
        # THE MONITOR IS ASKED FOR, NEVER REMEMBERED (constraint 13): `mon_rect`
        # is a callable the web layer put here, so a monitor switch between the
        # chip going out and his tap cannot land the rescue on a screen he
        # stopped watching.
        getter = conn.get("mon_rect")
        mon = getter() if callable(getter) else None
        # Either way the window leaves `lost_asked` (above) and NOT
        # `lost_left`: a rescue that failed is still a window he cannot reach,
        # so the next sweep asks again — and a rescue that worked simply is not
        # lost any more, which the sweep measures rather than remembers.
        return lost_windows.rescue(hwnd, mon)
    if offer.get("birth"):
        # Task 185's chip. NOTHING on the PC moves either way — a yes opens the
        # creation panel on the phone, seeded with this window, and every step
        # after that is the ordinary creation flow. All that is settled here is
        # that the question has been answered and will not be asked again.
        conn.get("birth_asked", set()).discard(hwnd)
        return bool(wm.user32.IsWindow(hwnd))
    # The question is answered, so it stops being a question. `popup_asked` is
    # ONLY "a chip is out for this window": what stops it being offered again
    # afterwards is his ANSWER — `popup_declined` for the desktop, membership
    # of `lay.adopted` for the layout. Keeping it here instead would make the
    # decline record dead code and hide the day it stopped working.
    conn.get("popup_asked", set()).discard(hwnd)
    if act == "layout_new":
        # "MAKE A LAYOUT" ON THE SWEEP'S OWN CHIP (owner report 2026-08-17).
        # Nothing on the PC moves here, exactly as on task 185's birth chip:
        # the phone opens the ordinary creation panel seeded with this window
        # and every later step is the creation flow that already exists. It is
        # deliberately NOT recorded in `popup_declined` — he has not left the
        # window on the desktop, he has taken it somewhere, and the creation
        # that follows makes it a member, which silences the sweep by itself.
        logger.info("Popup %s goes into a NEW layout — his choice",
                    popup_contain.describe(hwnd))
        return bool(wm.user32.IsWindow(hwnd))
    if act != "layout":
        # Remembered, so the watcher does not ask again and never places it:
        # he has answered this window.
        conn.setdefault("popup_declined", set()).add(hwnd)
        logger.info("Popup %s stays on the desktop — his choice", popup_contain.describe(hwnd))
        return True
    if not wm.user32.IsWindow(hwnd) or hwnd in lay.members:
        return False
    if hwnd not in lay.adopted:
        lay.adopted.append(hwnd)
    popup_contain.contain(lay, hwnd, conn)
    return True


def register(app, token: str) -> None:
    """Add `POST /window_offer` — the phone's answer coming back.

    Over HTTP and not over the WebSocket for one honest reason: the socket's
    message dispatcher lives in [Web Layer](web.py), and this feature was
    built while that file was owned by another round. The route is the same
    shape every other one here has (token-gated, JSON in, `{ok}` out), and
    the page already speaks it for uploads.

    Registered from `server_core` beside the app, so nothing about it is
    hidden inside another module's setup."""
    @app.post("/window_offer")
    async def window_offer(request: Request):  # noqa: ANN202 — FastAPI route
        if request.query_params.get("token") != token:
            return JSONResponse({"ok": False}, status_code=403)
        try:
            data = await request.json()
        except (json.JSONDecodeError, ValueError):
            return JSONResponse({"ok": False}, status_code=400)
        ok = await asyncio.to_thread(pick, str(data.get("id") or ""),
                                     str(data.get("act") or ""))
        return JSONResponse({"ok": ok})
