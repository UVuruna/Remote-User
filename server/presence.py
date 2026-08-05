"""Presence: is the owner still working with us, and whose desk are we on?

Layout members are forced always-on-top while the phone is showing them, so
the server MUST learn the moment the phone stops working with us — otherwise
those windows keep hovering over everything for the owner AT THE DESK. A clean
socket close cannot carry that news: a locked phone lets its Wi-Fi sleep and
the TCP connection simply goes quiet. So presence is a POSITIVE signal — the
client beats `hb` every few seconds and silence IS the leave — with a spoken
`away` as the fast path when the page knows it is going.

Split out of web.py on 2026-08-05 (THE STRUCTURE LAW: this is one
responsibility with its own rules, its own failure history and its own gate in
tests/test_presence.py, not a corner of the HTTP layer).

WHAT THIS MODULE EXISTS TO PREVENT, twice reported by the owner and twice
mis-diagnosed before: he locks the tablet, walks to his PC, and his own Chrome
and VSCode are still nailed above every other window. Three rules now stand
between him and that, and none of them is allowed to be the only one:

1. `away` carries a REASON the phone actually knows (the Android shell reads
   the screen/keyguard state and knows whether it launched a picker itself) —
   never a guess from a timer. A lock is a leave, always.
2. The excursion hold is short (`EXCURSION_MAX_S`), because it only has to
   outlast a real gallery pick.
3. THE DESK WINS: real local input on this PC while the phone is away ends the
   hold at once, whatever the phone claimed on its way out.
"""

import asyncio
import logging
import time

import window_manager
from input_injector import last_input_tick, tick_now

logger = logging.getLogger(__name__)


# ═══════════════════════════ TIMINGS ═══════════════════════════
HEARTBEAT_TIMEOUT_S = 12.0   # ~3 missed heartbeats (the client beats at 4 s)
# The far end of our patience with an excursion (image picker, camera, voice,
# a permission dialog): the page is hidden and beating nothing while the owner
# is very much still there.
#
# It used to be 300 s, and that number IS the 2026-08-05 failure. The page
# decided "excursion" from a 90-second timer armed by the last Mic/picker tap,
# so locking the tablet seconds after dictating was announced as an excursion
# and the layout hovered over the owner's desk for five full minutes. The
# server log measured it twice, to the second: excursion 18:41:56 -> released
# 18:46:56, and excursion 18:43:11 -> released 18:48:11. The reason is no
# longer guessed (rule 1 above), so this only has to cover a real pick.
EXCURSION_MAX_S = 45.0
WATCHDOG_POLL_S = 2.0
# Windows' last-input clock counts INJECTED input too, which is exactly why
# `owner_at_the_desk` is only ever consulted while the phone is away and we
# are injecting nothing. This grace covers the last event we ourselves sent
# just before the phone went quiet.
DESK_INPUT_GRACE_MS = 1500


# ═══════════════════════════ THE DESK ═══════════════════════════
def desk_baseline() -> int:
    """The tick to compare later input against — taken the moment the phone
    goes away, so anything newer is a human at this PC."""
    return tick_now() + DESK_INPUT_GRACE_MS


def owner_at_the_desk(baseline: int) -> bool:
    """True once real mouse/keyboard input arrives on this PC after the phone
    left. The owner sitting down outranks anything the phone said on its way
    out — his windows come back to him immediately (owner decree
    2026-08-05)."""
    tick = last_input_tick()
    return bool(tick) and tick > baseline


# ═══════════════════════════ LEAVING ═══════════════════════════
async def leave_session(layouts, conn: dict) -> None:
    """The phone stopped working with us — screen locked, app closed, killed,
    network gone. Everything the layouts hold on the PC is handed back to the
    desk: every member leaves the always-on-top band and gets minimized,
    exactly like choosing Desktop. Which layout was in use stays remembered in
    the registry — the next session resumes there.

    `clear_topmost()` runs after the minimize and is NOT redundant: it walks
    the topmost LEDGER, so a window that fell out of its layout meanwhile
    (closed, cloaked, extracted as a tab) is released too — that is the one no
    member list can still name, and the one that used to stay stranded.

    Idempotent: the watchdog and the socket's own teardown both call it."""
    if conn.get("left"):
        return
    conn["left"] = True
    conn["active"], conn["region"] = None, None
    logger.info("Phone left work mode — layout members minimized")
    await asyncio.to_thread(layouts.minimize_members)
    await asyncio.to_thread(layouts.clear_topmost)


async def excursion_backstop(layouts, active_client: dict) -> None:
    """An excursion legitimately keeps the layout standing with the socket
    closed — but only while the owner really is coming back. Two things end
    it: he sits down at this PC (checked every poll — his desk outranks the
    phone's parting word), or the patience runs out."""
    baseline = desk_baseline()
    deadline = time.monotonic() + EXCURSION_MAX_S
    while time.monotonic() < deadline:
        await asyncio.sleep(WATCHDOG_POLL_S)
        if active_client["ws"] is not None:
            return  # the phone came back — its own session takes over again
        if owner_at_the_desk(baseline):
            logger.info("Local input on this PC while the phone is away — "
                        "the desk gets its windows back now")
            await leave_session(layouts, {})
            return
    if active_client["ws"] is None:
        await leave_session(layouts, {})


async def watchdog(ws, layouts, conn: dict, active_client: dict | None = None) -> None:
    """Silence is the leave signal (see HEARTBEAT_TIMEOUT_S). A locked phone
    rarely manages a clean socket close — its Wi-Fi sleeps and the connection
    just goes quiet — so the layout's always-on-top windows would hover over
    the owner's desk forever. Missing heartbeats end the session instead, and
    during an excursion hold the owner's own keyboard ends it sooner.

    A watchdog may only end the session it belongs to. It is cancelled by its
    own connection's teardown, but that teardown cannot run until the receive
    loop unblocks — so after a 4409 takeover the OLD watchdog can still be
    polling with the NEW device already working, and it would minimize a live
    layout out from under it (audit 2026-08-05)."""
    baseline = desk_baseline()
    while True:
        await asyncio.sleep(WATCHDOG_POLL_S)
        if active_client is not None and active_client.get("ws") is not ws:
            return  # another device owns the session now
        silent = time.monotonic() - conn["seen"]
        away = conn.get("away")
        if away and owner_at_the_desk(baseline):
            logger.info("Local input on this PC during an excursion hold — "
                        "the desk gets its windows back now")
        elif silent >= (EXCURSION_MAX_S if away else HEARTBEAT_TIMEOUT_S):
            logger.info("No signal from the phone for %.0fs (%s) — session ends",
                        silent, "excursion" if away else "heartbeat")
        else:
            # Still with us. Keep the baseline fresh so that the moment the
            # phone DOES go away, "later than this" means the owner's own
            # hands and not the input we were injecting a minute ago.
            if not away:
                baseline = desk_baseline()
            continue
        await leave_session(layouts, conn)
        try:
            await ws.close(code=4408)  # gone quiet — the phone reconnects fresh
        except RuntimeError:
            pass
        return


# ═══════════════════════════ THE REASON THE PAGE GIVES ═══════════════════════════
# `away {reason}` — the word comes from the Android shell, which is the only
# component that can actually know. Anything we do not recognise is a LEAVE:
# the safe default is the owner's desk, never a window left hovering.
EXCURSION_REASONS = frozenset({"excursion"})


def is_excursion(msg: dict) -> bool:
    """Whether this `away` means "still working with you, back in a second".

    `reason` is the authoritative field. `excursion: true` is still honoured
    for an older page inside a newer server (the phone updates from the PC, so
    the two versions genuinely do meet), but a `reason` present in the message
    always wins over it — that is the whole point of the field."""
    reason = msg.get("reason")
    if isinstance(reason, str) and reason:
        return reason in EXCURSION_REASONS
    return bool(msg.get("excursion"))
