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
# How long a NEW connection waits for the PREVIOUS device's socket to take its
# 4409 before being served regardless (owner report 2026-08-07 — see
# `hand_over`). One second is generous for a peer that is really there and
# irrelevant for one that is not, and "one that is not" is the entire reason
# this number exists.
HANDOVER_TIMEOUT_S = 1.0


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


# ═══════════════════════════ HANDING THE SESSION OVER ═══════════════════════════
# Every task started here is held so the event loop is not its only reference:
# a bare create_task may be collected mid-await, which would silently skip the
# very close it exists for (same reason as web.py's excursion `holds`).
_handovers: set = set()


async def hand_over(prev) -> None:
    """Close the PREVIOUS device's socket with 4409 — without letting it hold
    up the device that is on the line NOW.

    One device at a time (owner 2026-08-02) means every new connection first
    evicts the old one, and this used to be a plain `await prev.close(4409)`
    ahead of everything the new client is sent: `actions`, the held notices,
    `layout_state`, the resumed layout, `config`, the stream, and every task
    that watches the connection — including the presence watchdog.

    That order is safe only while "the previous device" means ANOTHER device.
    In practice it is nearly always THE SAME PHONE on a route that has just
    died: home Wi-Fi dropped, a mobile-data handover, a Tailscale relay
    changing. Its socket is then a black hole — no RST, no FIN, an OS send
    buffer with a paused H.264 stream in it — and a close on such a socket does
    not fail, it WAITS. The phone meanwhile has already reconnected on its new
    route: the page's `onopen` fired, its status pill says "Connected", and
    `ensureConnected` will not retry a socket that is OPEN. So a page that is
    perfectly healthy sits in front of a server that has sent it nothing, for
    as long as the corpse takes to answer — which is the owner's report of
    2026-08-07: *"'Try again' retko kad pomogne... nekad čak i da zatvorimo
    celu aplikaciju"*. Killing the app was the only move because killing the
    app is what finally made the old socket fail.

    So: bounded wait, and the close runs on regardless afterwards. Nothing the
    dead device does can cost the live one its session."""
    async def _close() -> None:
        try:
            await prev.close(code=4409)  # taken over by this device
        except Exception:
            pass  # already closing, already gone, or never was — all fine

    task = asyncio.ensure_future(_close())
    _handovers.add(task)
    task.add_done_callback(_handovers.discard)
    try:
        await asyncio.wait_for(asyncio.shield(task), HANDOVER_TIMEOUT_S)
    except asyncio.TimeoutError:
        # It keeps trying in the background; this connection stops waiting.
        # `shield` is what makes that true — wait_for cancels the shield, never
        # the close underneath it.
        pass


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
    # session_end=True (defect 1, 2026-08-13): this IS constraint 23's real
    # session ending, unlike a plain Desktop tap — any adopted popup goes back
    # where Windows had it and is forgotten, not merely lowered for later.
    await asyncio.to_thread(layouts.minimize_members, session_end=True)
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
    layout out from under it (audit 2026-08-05).

    And when it DOES end a session it must also vacate the one-device slot
    (owner report 2026-08-07: "moramo... da zatvorimo celu aplikaciju"). That
    teardown is the only other place the slot is released, and it cannot run
    until the receive loop unblocks — which, on a link that simply went silent
    (mobile data handover, Wi-Fi dropped), waits out the OS TCP timeout, minutes
    away. Until then the returning phone is not a reconnect at all: it is a
    SECOND DEVICE arriving against its own corpse, and the first thing its
    connection does is `await prev.close(4409)` on a socket with nowhere to
    send. A session this watchdog has declared dead has no claim left on the
    slot; saying so here is what makes the next connection an ordinary one."""
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
        # Vacate the slot BEFORE the close: `ws.close()` on a socket whose peer
        # is unreachable can sit in the closing handshake, and the phone may
        # already be knocking on a new route while it does.
        if active_client is not None and active_client.get("ws") is ws:
            active_client["ws"] = None
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
