"""How a notice REACHES the phone: the page socket, the per-device waiting
channels, and the queue that holds what neither could carry.

Split out of `notify.py` on 2026-08-18 (THE STRUCTURE LAW). `notify.py` owns
what a notice SAYS; this module owns how it travels, and the whole reason it
is one module is the rule it enforces: THREE CARRIERS, EXACTLY ONE PER NOTICE
(owner 2026-08-07). `deliver()` is the single choke every notice passes, and
one module holding all three carriers is what makes "exactly one" a chain of
`return`s rather than a promise.
"""

import asyncio
import json
import logging
import time

import session_log

logger = logging.getLogger(__name__)

# A notice for a phone that CANNOT BE REACHED AT ALL waits (owner 2026-08-06;
# narrowed 2026-08-07). The rule used to be "never queue — an alarm an hour
# late is worse than none", and for an alarm that is right; for "your agent
# finished" it is exactly wrong. The owner's own case: two agents finished
# while he was on the phone with someone, the app minimized or closed, and
# both notices were thrown away.
#
# What the queue must NOT be is the normal path, which is what it silently
# became: with the page hidden there was no other channel, so every notice he
# was not already looking at went in here and waited for him to open the app —
# the exact failure he reported on 2026-08-07. With the waiting channel below
# it is a real fallback again: reached only when the phone has no live channel
# of either kind (app killed, phone off, no network).
#
# The queue is SHORT and it is HONEST: nothing older than QUEUE_TTL_S is ever
# delivered (a five-minute-old "finished" is useful, an hour-old one is
# noise), at most QUEUE_MAX are held, and each carries the time it happened so
# the phone can say "8 minutes ago" instead of pretending it just landed.
# Both numbers are deliberately UNCHANGED: they were right for the case that
# is left, and nothing this round learned says otherwise.
QUEUE_TTL_S = 30 * 60
QUEUE_MAX = 20
_pending: list[dict] = []

NO_CLIENT = {"ok": False, "reason": "phone unreachable — held for its return"}
WAITING = {"ok": True, "reason": "handed to the phone's waiting channel"}


def queue(notice: dict) -> None:
    """Hold a notice for the phone's next connection."""
    _pending.append(notice)
    del _pending[:-QUEUE_MAX]


def drain(now: float) -> list[dict]:
    """Everything still worth showing, oldest first — and the queue is emptied
    whether or not anything survived, because a notice that timed out has no
    second chance either."""
    held, _pending[:] = list(_pending), []
    return [n for n in held if now - n.get("at", 0) <= QUEUE_TTL_S]



# ═══════════════════ THE WAITING CHANNEL (owner decree 2026-08-07) ═══════════
# *"Radimo taj mali servis — samo je važno da ta komunikacija koja mora da bude
#  u pozadini bude minimalna … android strana čeka signal, ne prima ništa od
#  kompjutera, ali ostane u stanju čekanja signala."*
#
# So: the phone WAITS and the PC SPEAKS. `GET /notices` is a response that
# never ends — the phone's foreground service opens it once and then blocks on
# a read. Nothing is polled, nothing is fetched, nothing is streamed. While
# there is no news the PC writes ONE BYTE, a newline, every BEAT_S; the phone
# reads it and goes straight back to blocking. When there is news the PC writes
# one JSON line, which is byte-for-byte the same `notify` frame the page gets.
#
# Why a plain chunked HTTP body and not a WebSocket: the shell already speaks
# HttpURLConnection (it probes /ping with it), so this costs the APK no new
# dependency and no handshake state — and a blocking readLine() on a socket
# that says nothing is exactly the "state of waiting" he asked for.
#
# THE BEAT IS NOT A POLL. It travels PC -> phone, it is one byte, and it is
# there for two things only: keeping the router's / carrier's NAT mapping for
# this TCP connection alive (the tightest common idle timeout is 60 s), and
# being the one way either side can notice a link that died silently — a write
# that fails is a phone that is gone, and a phone that hears nothing for
# BEAT_MISS beats reconnects. Without it a dead link would swallow notices
# while both ends believed they were connected.
BEAT_S = 60.0
BEAT_MISS = 3          # the shell keeps its own copy of this rule; see NoticeLink.kt

# ONE CHANNEL PER DEVICE, NOT ONE CHANNEL (owner's log, 2026-08-11, task 209).
#
# This used to be a single slot — `{"q": None}` — mirroring the web layer's
# one-device rule, and that mirroring was the mistake: the STREAMING session
# must be one device (two phones driving one mouse is nonsense), but WAITING
# for news is not driving anything. The owner runs the foreground service on
# his tablet AND his phone, so each attach kicked the other, the kicked one
# reconnected at once, and his log carried an attach→kick→retry ping-pong every
# few seconds, continuously, since 2026-08-09 — thousands of lines a night,
# both radios woken for nothing, and (the part he actually felt) a notice
# reaching ONLY whichever device held the slot that second while the other
# learned about it minutes later out of the queue: "notifications sometimes
# never arrive".
#
# So the channels are keyed by a DEVICE ID the shell supplies
# (`GET /notices?token=…&device=<id>`), and:
#
#   - a notice with no page to go to goes to EVERY waiting device, once each.
#     Per-device de-duplication is structural — a device has exactly one
#     channel, so it cannot be handed the same notice twice;
#   - a second attach from the SAME id replaces that device's own channel (its
#     service restarted, Wi-Fi moved) and touches no other device;
#   - a request with NO `device` is an older APK, and it keeps exactly today's
#     behaviour: it shares the one LEGACY key, so two old shells still fight
#     over one slot. Nothing about an old phone changes when this PC updates.
#
# The cap is not a policy, it is a stop: an id that changed on every attach
# (a broken shell) would otherwise grow this dict without limit. The oldest
# channel gives way, and it is said in the log.
LEGACY_DEVICE = ""     # the single slot an APK that sends no id shares
MAX_DEVICES = 8
_waiting: dict[str, asyncio.Queue] = {}


def device_key(value) -> str:
    """The device id as we are willing to keep it: trimmed, capped, and made
    of characters that are safe to print in a log line. Anything else — an
    absent parameter, a blank one, junk — falls back to the LEGACY slot, which
    is the behaviour an old shell already has."""
    text = str(value if value is not None else "").strip()[:64]
    clean_id = "".join(c for c in text if c.isalnum() or c in "-_.:")
    return clean_id or LEGACY_DEVICE

# The web layer's one-device-at-a-time slot, handed over by `set_page()` from
# `notify.register()`. The DICT is read only — this module never writes the
# `ws` key, and that is the whole reason a waiting channel can never be
# mistaken for a present phone (see `_carry`).
_page: dict = {"ws": None}


def set_page(active_client: dict) -> None:
    """The web layer's own one-device-at-a-time slot, handed over whole. This
    module deliberately keeps no second registry, so a phone that took the
    session over (code 4409) is the one that gets the notices."""
    global _page
    _page = active_client


def page_socket():
    """The LIVE page socket, or None — read only, for the one other module
    that has something to say to the page from a task the web layer did not
    hand a socket to ([Layout Popup](layout_popup.py)'s window offer, task
    202). It is this module's slot because the web layer handed it here and
    this project keeps exactly one registry of the connected phone; a second
    one is how a phone that took the session over (code 4409) starts getting
    someone else's messages."""
    return _page["ws"]


def waiting() -> bool:
    """Whether ANY device is holding a waiting channel open right now."""
    return bool(_waiting)


def waiting_devices() -> int:
    """How many devices are waiting. One line in the log, and the number the
    gate reads — the whole point of task 209 is that this can be 2."""
    return len(_waiting)


async def deliver(notice: dict) -> str:
    """The one choke every notice passes — so the use log's `notice.*` record
    is written HERE and nowhere else.

    A record per carrier at each `return` inside `_carry` would be three
    copies of one fact, and three copies drift. `waited_s` is measured from
    the notice's own `at` stamp, which is what tells a held notice apart from
    one that landed the second it was raised — the exact distinction the
    phone's own "8 min ago" suffix exists for.

    Never raises: a use log may not break a notice."""
    carrier = await _carry(notice)
    try:
        at = notice.get("at")
        waited_s = (round(max(0.0, time.time() - at), 1)
                    if isinstance(at, (int, float)) else None)
        session_log.LOG.record(
            f"notice.{carrier}",
            agent=notice.get("agent"), event=notice.get("event"),
            waited_s=waited_s,
            # HAD it waited — a notice raised now and delivered now, versus one
            # drained out of the queue on a later connection. A second of slack
            # so an ordinary round trip is never reported as a wait.
            waited=bool(waited_s is not None and waited_s > 1.0))
    except Exception:
        logger.exception("Use log: could not record a notice")
    return carrier


async def _carry(notice: dict) -> str:
    """Hand one notice to EXACTLY ONE CARRIER TYPE. Returns which took it.

    The order is the rule that makes a double notice impossible — it is a
    chain of `return`s, not three sends:

      "page"    — the app is open and the owner is looking at it. The page
                  toasts, speaks and raises the banner exactly as before.
      "waiting" — the page is gone but at least one device is holding a
                  channel open. This is the case the whole round exists for.
      "held"    — neither. Every device is off, killed or offline; the queue
                  is now what it was always meant to be.

    "One carrier" is a rule about the SAME DEVICE hearing a notice twice, and
    it still holds exactly: a device has one channel, and the page belongs to
    the device that is on screen. Since task 209 the waiting branch fans the
    notice out to EVERY waiting device once — his tablet and his phone are two
    ears, not two copies, and the alternative (one slot) meant one of them
    simply never heard it.

    The page's socket dying between the check and the send is not an error and
    not a queue: the phone has just hidden the page, its service is very
    probably already waiting, so the notice falls through to the next carrier.
    """
    ws = _page["ws"]
    if ws is not None:
        try:
            await ws.send_text(json.dumps(notice))
            return "page"
        except RuntimeError:
            logger.warning("The page's socket closed mid-notice — "
                           "trying the waiting channel")
    # A snapshot: a channel detaching while we hand out is harmless (its queue
    # is simply dropped with it), and iterating the live dict is not.
    channels = list(_waiting.values())
    if channels:
        for channel in channels:
            channel.put_nowait(notice)
        return "waiting"
    queue(notice)
    return "held"


async def wait_for_news(device: str = LEGACY_DEVICE):
    """The body of `GET /notices`: a response that never ends.

    Everything a streaming session normally drags along is absent here, and
    absent BY CONSTRUCTION rather than by care — this generator can reach the
    notice queue and nothing else. It never touches `_page`, so the server's
    one-device slot stays empty and presence keeps its meaning; it never sees
    the layout registry, the capture, the encoder or the injector, so no
    window can be raised, held always-on-top or typed into on its account.
    A waiting phone is a phone that is NOT here.
    """
    channel: asyncio.Queue = asyncio.Queue()
    # The loop every channel lives on — captured here because `close_channels`
    # (task 234) is called from the GUI thread, and an asyncio.Queue may only
    # be fed through call_soon_threadsafe from there.
    global _loop
    _loop = asyncio.get_running_loop()
    # Only THIS device's own channel is displaced (task 209). A second attach
    # from the same id is the same phone whose service restarted; a different
    # id is a different phone, and taking its channel away is what made his
    # tablet and his phone fight over one slot all night.
    previous = _waiting.get(device)
    _waiting[device] = channel
    if previous is not None:
        previous.put_nowait(None)   # its own older channel ends itself
    while len(_waiting) > MAX_DEVICES:
        # Insertion order, so the oldest attach gives way — a stop against an
        # id that changes on every attach, never something his two phones meet.
        oldest = next(iter(_waiting))
        logger.warning("More than %d waiting devices — dropping the oldest "
                       "channel (%s)", MAX_DEVICES, oldest or "no id")
        _waiting.pop(oldest).put_nowait(None)
    logger.info("Notice channel attached (device %s) — %d waiting",
                device or "no id (older app)", len(_waiting))
    # Whatever piled up while the phone was truly unreachable is handed over
    # now, oldest first — but only when the page is not already about to be
    # handed the same thing on its own auth (web.py -> notice_channel.send_pending).
    if _page["ws"] is None:
        for notice in drain(time.time()):
            channel.put_nowait(notice)
    try:
        while True:
            try:
                notice = await asyncio.wait_for(channel.get(), BEAT_S)
            except asyncio.TimeoutError:
                yield b"\n"          # the beat — one byte, PC to phone
                continue
            if notice is None:
                return               # displaced by a newer channel
            yield (json.dumps(notice) + "\n").encode()
    finally:
        if _waiting.get(device) is channel:
            del _waiting[device]
        logger.info("Notice channel gone (device %s) — %d still waiting",
                    device or "no id (older app)", len(_waiting))


_loop: asyncio.AbstractEventLoop | None = None


def close_channels() -> None:
    """Ends every waiting `/notices` response NOW (task 234, his blanket GO).

    `force_exit` stops uvicorn from accepting work, but an endless
    StreamingResponse generator parked on its queue is an open connection the
    shutdown still waits on — every Apply & restart cost the stop() join its
    full 10 s and abandoned the old thread. The sentinel is the SAME one a
    displaced channel receives, so each generator returns through its own
    normal exit and the finally-block bookkeeping runs unchanged. Safe from
    any thread (the GUI's stop() is not the server loop): the queue is fed
    through call_soon_threadsafe on the loop captured at attach time. A loop
    that is already gone means the generators are gone with it — nothing to
    end, nothing to raise on the way out."""
    loop = _loop
    channels = list(_waiting.values())
    if not channels or loop is None or loop.is_closed():
        return
    for channel in channels:
        try:
            loop.call_soon_threadsafe(channel.put_nowait, None)
        except RuntimeError:
            return  # the loop closed between the check and the call — done



async def send_pending(ws) -> int:
    """Everything that happened while the phone was UNREACHABLE, on its return.

    Called once per authenticated page connection (web.py). Oldest first, so
    the order the agents finished in is the order he reads. Since 2026-08-07
    this is normally empty and that is the fix, not a regression: a notice
    that arrived while the page was merely hidden went down the waiting
    channel at the time and was never queued at all.
    """
    held = drain(time.time())
    for notice in held:
        try:
            await ws.send_text(json.dumps(notice))
        except RuntimeError:
            queue(notice)          # gone again mid-drain — keep what is left
            break
    if held:
        logger.info("Delivered %d notice(s) held while the phone was away",
                    len(held))
    return len(held)
