"""Notifications from THIS PC to the phone (ROADMAP Phase H, owner 2026-08-05).

The owner runs several agents at once, and a bare beep says nothing:

    *"nije dovoljno samo da kaže beep kad završi agent — najbolje od svega je
    da izbaci notifikaciju koja opisuje koji agent je završio, a ime agenta je
    ime sesije u suštini"*

So the message carries the AGENT's name, and the phone raises a real Android
notification with it (plus, on request, speaks it aloud). The PC never guesses
whether an agent is done — whatever finished TELLS us, by POSTing here. That
is what makes this reliable where screen-reading would not be: a long silent
build looks exactly like a finished one on screen, and nothing on screen can
tell four agents apart anyway.

Any tool that can run a command on completion can use it (`setup/agent_hook.py`
is the Claude Code `Stop` hook that does). Kept out of `web.py` on purpose:
this is its own responsibility with its own route, and the file it would
otherwise grow into is the busiest one in the project.

THREE CARRIERS, EXACTLY ONE PER NOTICE (owner 2026-08-07). His report was
*"notifikacije mi stižu tek kada podignem aplikaciju iako je sve vreme
otvorena u pozadini"*, and the cause was structural: every notice rode the
STREAMING socket, and that socket is closed on purpose the moment the page
hides (project CLAUDE.md constraint 8 — the session lives only while the owner
is looking). At the exact moment a notice matters there was no channel at all,
so it was queued until he opened the app himself — the queue doing a delivery
mechanism's job. So there is now a second, MINIMAL channel that the phone's
foreground service holds open while the page is gone (`/notices`, below), and
one function decides which carrier takes a notice: `deliver()`. The three are
tried in order and exactly one of them runs, which is the whole reason the
same notice can never arrive twice.
"""

import asyncio
import json
import logging
import pathlib
import shutil
import sys
import time

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from config import BUNDLE_DIR, FROZEN, PROJECT_ROOT, SETTINGS, USER_DIR

logger = logging.getLogger(__name__)

# What a notice may carry — clamped, because it is drawn on a phone and
# spoken out loud. The limits are the ones a notification line can show
# without the rest becoming an ellipsis nobody reads.
MAX_AGENT = 60
MAX_TEXT = 200

# Events we know how to phrase. An unknown event still gets through — it is
# just shown as-is, which beats swallowing a notice the owner asked for.
EVENT_WORDS = {
    "finished": "finished",
    "waiting": "needs you",
    "failed": "failed",
}

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

# --- The phone's own voices (round R2, owner 2026-08-07) ---------------------
# The desktop Settings window offers a "Voice" dropdown, and the only machine
# that knows which voices exist is the PHONE: TextToSpeech engines differ per
# device, per installed language pack, per Android version. So the phone lists
# them once per connection (`tts_info`) and the list is held HERE, beside the
# feature that uses it — never persisted, because a list read from a phone that
# is no longer connected would offer the owner voices he cannot hear.
#
# The stored CHOICE is a plain name in the settings file, not an index: a
# device that no longer has that voice simply falls back to its default rather
# than speaking in whichever voice happens to sit at that position now.
_voices: list[dict] = []


def set_voices(reported) -> int:
    """Remember what the phone can speak with. Anything unusable is dropped
    rather than trusted — this list is drawn in a dropdown on the PC."""
    global _voices
    clean_list = []
    for item in reported if isinstance(reported, list) else []:
        if not isinstance(item, dict):
            continue
        name = clean(item.get("name"), MAX_AGENT)
        if not name:
            continue
        clean_list.append({"name": name,
                           "label": clean(item.get("label"), MAX_AGENT, name),
                           "locale": clean(item.get("locale"), 24)})
    _voices = clean_list
    logger.info("Phone reported %d text-to-speech voice(s)", len(_voices))
    return len(_voices)


def voices() -> list[dict]:
    """What the Settings window draws in its Voice dropdown. Empty until a
    phone has connected at least once this run — the window says so."""
    return list(_voices)


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


def clean(value, limit: int, fallback: str = "") -> str:
    """One field of an incoming notice: string, trimmed, length-capped."""
    text = str(value if value is not None else "").strip()
    return (text or fallback)[:limit]


def compose(agent: str, event: str, text: str) -> tuple[str, str]:
    """(title, body) — what the phone shows and speaks.

    The AGENT leads, because that is the whole point (owner: several agents
    run at once). The event is the verb; free text, when the caller sent any,
    is the second line.
    """
    word = EVENT_WORDS.get(event, event)
    return f"{agent} {word}".strip(), text


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

# One waiting phone at a time, mirroring the web layer's one-device rule: a
# second attach displaces the first rather than doubling every notice.
_waiting: dict = {"q": None}

# The web layer's one-device-at-a-time slot, handed over by register(). Read
# ONLY — this module never writes it, and that is the whole reason a waiting
# channel can never be mistaken for a present phone (see the route below).
_page: dict = {"ws": None}


def waiting() -> bool:
    """Whether a phone is holding the waiting channel open right now."""
    return _waiting["q"] is not None


async def deliver(notice: dict) -> str:
    """Hand one notice to EXACTLY ONE carrier. Returns which took it.

    The order is the rule that makes a double notice impossible — it is a
    chain of `return`s, not three sends:

      "page"    — the app is open and the owner is looking at it. The page
                  toasts, speaks and raises the banner exactly as before.
      "waiting" — the page is gone but the phone is holding the channel open.
                  This is the case the whole round exists for.
      "held"    — neither. The phone is off, killed or offline; the queue is
                  now what it was always meant to be.

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
    channel = _waiting["q"]
    if channel is not None:
        channel.put_nowait(notice)
        return "waiting"
    queue(notice)
    return "held"


async def _wait_for_news():
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
    previous, _waiting["q"] = _waiting["q"], channel
    if previous is not None:
        previous.put_nowait(None)   # the older channel ends itself
    logger.info("Notice channel attached — the phone is waiting for news")
    # Whatever piled up while the phone was truly unreachable is handed over
    # now, oldest first — but only when the page is not already about to be
    # handed the same thing on its own auth (web.py -> notify.send_pending).
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
        if _waiting["q"] is channel:
            _waiting["q"] = None
        logger.info("Notice channel gone — notices wait in the queue again")


def register(app, token: str, active_client: dict) -> None:
    """Adds `POST /notify` and `GET /notices` to the running server.

    `active_client` is the web layer's own one-device-at-a-time slot — this
    module deliberately keeps no second registry, so a phone that took the
    session over (code 4409) is the one that gets the notices.
    """
    global _page
    _page = active_client

    @app.get("/notices")
    async def notices(request: Request):  # noqa: ANN202 — FastAPI route
        """The phone's waiting state. Token-gated like every real endpoint:
        without it this would be a way to make any phone on the network buzz,
        and to learn that an agent runs here at all."""
        if request.query_params.get("token") != token:
            return JSONResponse({"ok": False}, status_code=403)
        return StreamingResponse(_wait_for_news(),
                                 media_type="application/x-ndjson",
                                 headers={"Cache-Control": "no-store"})

    @app.post("/notify")
    async def notify(request: Request):  # noqa: ANN202 — FastAPI route
        if request.query_params.get("token") != token:
            # Same rule as every other route: no token, no answer that could
            # be used to probe whether the PC is even running an agent.
            return JSONResponse({"ok": False}, status_code=403)
        try:
            data = await request.json()
        except (json.JSONDecodeError, ValueError):
            data = {}
        agent = clean(data.get("agent"), MAX_AGENT, "Agent")
        event = clean(data.get("event"), 24, "finished")
        text = clean(data.get("text"), MAX_TEXT)
        title, body = compose(agent, event, text)
        logger.info("Notify: %s | %s", title, body or "-")

        notice = {
            "type": "notify",
            "agent": agent,
            "event": event,
            "title": title,
            "text": body,
            # HOW the phone says it is the DESKTOP's decision (Settings
            # window, round R2). "Speak it out loud" off sends speak:false and
            # nothing more — the Android banner still appears, so a notice is
            # never lost by muting one of its three carriers. The voice name
            # and the rate ride along on every frame instead of being pushed
            # to the phone separately: there is then no state on the phone to
            # go stale, and a reconnect cannot leave it speaking in last
            # week's voice.
            "speak": bool(data.get("speak", True)) and SETTINGS.notify_speak,
            "voice": SETTINGS.notify_voice,
            "rate": SETTINGS.notify_rate,
            "at": time.time(),
        }
        # ONE carrier, chosen here and nowhere else (see deliver()). Nothing
        # about the notice itself changes with the carrier — same agent, same
        # line, same speak/voice/rate — so the owner cannot tell which one
        # brought it, which is the point.
        carrier = await deliver(notice)
        if carrier == "held":
            return JSONResponse(NO_CLIENT)
        return JSONResponse(WAITING if carrier == "waiting" else {"ok": True})


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


# ═══════════════════ THE SWITCH THAT TURNS IT ON (ROADMAP H2) ═══════════════
# The hook shipped working in v0.0.081 and then said nothing for a day on the
# owner's own PC, because it had never been registered — `agent_hook.py
# --install` is a command, and the rule is that an end user never types one.
# So the desktop window carries a switch, and these two functions are what it
# operates. They live here because this is the notification feature's module;
# the GUI only owns the checkbox.
#
# EVERY SENTENCE THIS SWITCH CAN PRINT IS NAMED HERE (round R2 grade,
# 2026-08-07, a SECOND independent grader). v0.0.251 already fixed the ONE
# path that used to leak — a missing bundled script — with the friendly text
# below; what it missed is that `set_agent_hook`'s own copy/install steps
# could still raise a BARE OSError (a locked target file, a full disk, a
# permissions error) straight through the GUI's `except OSError as e: ...
# str(e)`, which is exactly how a raw exception repr became the caption's
# text on the owner's own screen. So every risky step below is inside ONE
# try/except that turns anything unexpected into HOOK_CHANGE_FAILED_TEXT —
# `_hook_module()` is the only thing still allowed to raise past this
# function, and only with a message already written for a human.
MISSING_SCRIPT_TEXT = ("This copy of Remote User is missing its notifier "
                       "script. Reinstalling the app from the latest release "
                       "puts it back.")
UNLOADABLE_SCRIPT_TEXT = "The notifier script could not be loaded on this PC."
NO_PYTHON_TEXT = ("This PC has no Python on PATH, and Claude Code's hooks "
                  "need one to run the notifier. Install Python and switch "
                  "this on again.")
HOOK_CHANGE_FAILED_TEXT = ("Remote User could not change the notifier hook on "
                           "this PC — the log has the exact reason.")


def _hook_module():
    """`setup/agent_hook.py` imported by path — it is deliberately outside the
    server package (it must run standalone under any interpreter)."""
    import importlib.util
    path = PROJECT_ROOT / "setup" / "agent_hook.py"
    if not path.exists():                      # frozen: bundled beside the exe
        path = BUNDLE_DIR / "setup" / "agent_hook.py"
    if not path.exists():
        # v0.0.085 shipped without this file in the bundle, and the switch
        # answered the owner with a raw "[Errno 2] No such file or directory:
        # …\\_internal\\setup\\agent_hook.py". A path is not an explanation,
        # and it is not something HE can act on — the app is what is broken,
        # so the app says so in his words. (The build now refuses to package
        # without it: setup/build.py's payload gate.)
        logger.error("agent hook script missing from this build (%s)", path)
        raise OSError(MISSING_SCRIPT_TEXT)
    spec = importlib.util.spec_from_file_location("agent_hook", path)
    if spec is None or spec.loader is None:
        raise OSError(UNLOADABLE_SCRIPT_TEXT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def agent_hook_installed() -> bool:
    try:
        return bool(_hook_module().is_installed())
    except OSError as e:  # noqa: BLE001 — a missing script is "not installed"
        logger.warning("agent hook state unreadable: %s", e)
        return False


def set_agent_hook(on: bool) -> tuple[bool, str]:
    """Register or remove the Claude Code Stop hook. Returns (ok, what to tell
    the user) — NEVER an exception's own text (see the block comment above).
    Two things the packaged app must handle and the dev checkout need not: the
    script lives inside the bundle and would vanish with the next update, so
    it is copied to the user directory; and there is no interpreter in the
    EXE, so a real python has to be found — if this PC has none, that is said
    plainly instead of leaving a switch that lies."""
    module = _hook_module()  # may raise OSError — always with a human message
    try:
        if not on:
            module.install(remove=True)
            return True, ""
        script = pathlib.Path(module.__file__)
        python = sys.executable
        if FROZEN:
            target = USER_DIR / "agent_hook.py"
            USER_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(script, target)
            script = target
            python = shutil.which("python") or shutil.which("py") or ""
            if not python:
                return False, NO_PYTHON_TEXT
        module.install(script=script, python=python)
    except OSError as e:
        # Anything from here down (a locked target file, a full disk, a
        # permissions error writing ~/.claude/settings.json inside
        # agent_hook.install()) is OUR problem to phrase, not the owner's to
        # decode — the raw text goes to the log and ONLY the log.
        logger.error("agent hook %s failed: %s", "on" if on else "off", e)
        return False, HOOK_CHANGE_FAILED_TEXT
    logger.info("agent hook installed (%s %s)", python, script)
    return True, ""
