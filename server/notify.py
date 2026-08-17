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
import re
import shutil
import sys
import time

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from config import BUNDLE_DIR, FROZEN, PROJECT_ROOT, SETTINGS, USER_DIR
import session_log
import window_manager as wm  # the same live-title read `layout_state` already
                              # uses (layout_registry.py's member_titles) — no
                              # second copy of how a member's title is read

logger = logging.getLogger(__name__)

# What a notice may carry — clamped, because it is drawn on a phone and
# spoken out loud. The limits are the ones a notification line can show
# without the rest becoming an ellipsis nobody reads.
MAX_AGENT = 60
MAX_TEXT = 200
# The conversation TITLE (task: "da notifikacije bira layout u cijem se
# kreirao", owner 2026-08-13). Capped generously rather than at MAX_AGENT's 60:
# `agent` is already the title truncated to 60 for the banner, and truncating
# the MATCHING copy the same way would throw away exactly the tail that tells
# two long, similarly-started conversation titles apart.
MAX_TITLE = 200

# Events we know how to phrase. An unknown event still gets through — it is
# just shown as-is, which beats swallowing a notice the owner asked for.
EVENT_WORDS = {
    "finished": "finished",
    "waiting": "needs you",
    "failed": "failed",
    # A QUESTION, not an ending (owner 2026-08-09). Claude Code raises a
    # `Notification` hook when it stops to ask something — a permission, a
    # choice, one of the votes he sees on screen — and that is a DIFFERENT
    # event from a turn ending: it is the one where nothing at all moves until
    # he answers. It gets its own word so the phone says which of the two it
    # is without him having to look.
    "asking": "is asking you",
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

# WHERE THE NOTICE HAPPENED (owner 2026-08-08, task 110): "da klikom na
# notifikaciju nas odvede do tog layouta … gde je zavrsio taj sabagent ili
# glavni agent." A notice that names an agent but leaves him to find the
# window is half the job — he has to step the layout bar looking for it.
#
# Nothing is INFERRED here. The finishing agent sends its own `cwd`
# (setup/agent_hook.py -> agent_project), and every layout can be asked which
# project its windows really belong to, live (Layout.project). Matching those
# two is the whole feature; there is no name-guessing, no title heuristic, and
# no stored answer that could go stale between the notice and the tap.
_layouts = None      # the live LayoutRegistry, handed over by register()


# --- Matching a CONVERSATION TITLE to the window that carries it -----------
# Owner ruling 2026-08-13: notifications must choose the layout the
# conversation was really created in. When several windows of ONE project are
# spread across layouts (the exact case a project-folder match cannot tell
# apart), the tap must land in the layout that holds the CONVERSATION that
# finished, not merely a project it shares. A VS Code window running Claude
# Code is titled after the conversation (project CLAUDE.md constraint 11 /
# the `agents` notes); the hook already reads that title off the transcript's
# own `ai-title` record (task 198, `agent_hook.transcript_title`) to NAME the
# agent, so this reuses the exact same string rather than inventing a second
# way to find it — see `agent_hook.send()`, which now rides it as the `title`
# field.
#
# The tail is what makes an EQUALITY check wrong: VS Code appends
# " - <folder> - Visual Studio Code[ tail]" to every window title, and — per
# the owner's own example in constraint 19's report — elides a title too long
# for its tab with a trailing "…". So the window's title is not the
# conversation title, it is a (possibly truncated) PREFIX of it plus VS
# Code's own furniture. Both halves have to be undone before two strings can
# honestly be compared.
#
# Two shapes exist and neither can be assumed: a member window standing in a
# workspace carries the FOLDER segment ("<file> - <folder> - Visual Studio
# Code"), the same shape `agents.VSCODE_TITLE_RE` already reads a folder out
# of; a torn-off conversation tab dragged into its own window frequently
# carries NO folder segment at all ("<conversation> - Visual Studio Code") —
# exactly the shape this project's own test fixtures use for one. The FOLDER
# form is tried first (its middle segment is required to hold no dash of its
# own, same rule `agents.py` uses, so a conversation title that itself
# contains " - " is never mistaken for a folder); the BARE form is the
# fallback.
_VSCODE_TAIL_WITH_FOLDER_RE = re.compile(
    r"^(.*?)\s-\s[^-]+\s-\s*Visual Studio Code(?:\s*\[[^\]]*\])?\s*$")
_VSCODE_TAIL_BARE_RE = re.compile(
    r"^(.*?)\s-\s*Visual Studio Code(?:\s*\[[^\]]*\])?\s*$")


def _vscode_conversation_part(title: str) -> str:
    """The conversation-naming part of a VS Code window title — everything
    before its " - Visual Studio Code[ tail]" furniture, folder segment
    included when there is one — or "" when the title carries no such tail
    at all (a plain window, an app that isn't VS Code, a bare "Visual Studio
    Code" with nothing in front of it)."""
    text = str(title or "")
    for pattern in (_VSCODE_TAIL_WITH_FOLDER_RE, _VSCODE_TAIL_BARE_RE):
        match = pattern.match(text)
        if match:
            return match.group(1).strip()
    return ""


def _title_matches(conversation: str, window_title: str) -> bool:
    """Whether `window_title` is honestly THIS conversation, never a guess.

    Equal after VS Code's own furniture is stripped is the confident case.
    When the window's own copy ends in VS Code's ellipsis, it is a TRUNCATED
    prefix of the real title — matched with a strict `startswith`, because a
    fuzzy match loose enough to bridge two DIFFERENT elided titles would send
    him into a stranger's conversation. Whenever nothing matches confidently,
    this returns False and the caller falls back to the project-folder search
    rather than guess. No lower-casing either: a conversation title is prose,
    not a folder name, and two titles differing only in case are still two
    different sentences."""
    part = _vscode_conversation_part(window_title)
    if not conversation or not part:
        return False
    if part == conversation:
        return True
    for ellipsis in ("…", "..."):
        if part.endswith(ellipsis):
            return conversation.startswith(part[: -len(ellipsis)].rstrip())
    return False


def _layout_by_title(conversation: str):
    """The live layout carrying a member window titled after `conversation`,
    or None. Reads member titles the SAME way `layout_state` already presents
    them to the phone (`wm._title(h) for h in lay.members`) — a torn-off tab's
    OWN window is what carries the conversation title, never the window it
    was torn out of, so unlike `project()` there is no source to fall back
    to here."""
    for layout in _layouts.layouts:
        for hwnd in layout.members:
            if wm.is_alive(hwnd) and _title_matches(conversation, wm._title(hwnd)):
                return layout
    return None


def layout_of(project: str, title: str = "") -> dict | None:
    """`{index, name}` of the layout showing this project, or None.

    Blocking Win32 (each layout is asked for its members' titles), so callers
    reach it through `asyncio.to_thread`.

    The INDEX is what the phone acts on, and it only means anything after a
    prune — the same prune `layout_state` runs before numbering the list the
    phone is holding. The NAME rides along so the phone can check the index
    still points at what we meant: a layout removed between the notice and the
    tap slides every higher index down, and a jump into the wrong window is
    worse than no jump at all.

    `title` (owner ruling 2026-08-13) is the conversation's own title, when
    the hook sent one: it is tried FIRST, because it can tell apart several
    windows of the SAME project spread across layouts — the exact case a
    project-folder match cannot. An older hook sends no title at all
    (`data.get("title")` is simply absent), `title` arrives here as `""`, and
    the method falls straight through to today's project-folder search —
    byte-for-byte the same result an old hook always got.
    """
    folder = pathlib.Path(str(project or "").strip()).name.lower()
    if not folder or _layouts is None:
        logger.info("Notify: no layout jump — project=%r registry=%s",
                    project, "absent" if _layouts is None else "present")
        return None
    try:
        _layouts.prune()
        conversation = str(title or "").strip()
        if conversation:
            hit = _layout_by_title(conversation)
            if hit is not None:
                index = _layouts.layouts.index(hit)
                logger.info("Notify: %r matched by conversation title → "
                            "layout %d (%s)", conversation, index, hit.name)
                return {"index": index, "name": hit.name}
        for index, layout in enumerate(_layouts.layouts):
            if layout.project() == folder:
                return {"index": index, "name": layout.name}
        # A MISS IS SAID OUT LOUD (task 236 — his THIRD report of this one
        # feature). Until now the only line written was the one on SUCCESS, so
        # a notice that shipped with no `layout` field looked in the log
        # exactly like a notice that carried one, and two rounds closed this
        # bug without anyone being able to tell which half had failed. What is
        # printed is what the match was made of: the folder we were looking
        # for, and every folder each live layout really names.
        logger.info("Notify: no layout shows %r — live layouts: %s", folder,
                    "; ".join(f"{i}:{lay.name}={lay.projects() if hasattr(lay, 'projects') else [lay.project()]}"
                              for i, lay in enumerate(_layouts.layouts)) or "none")
    except Exception as e:  # noqa: BLE001 — a notice must never fail on this
        logger.warning("Could not match %r to a layout: %s", folder, e)
    return None

# --- The phone's own voices (round R2, owner 2026-08-07) ---------------------
# Only the PHONE knows which voices exist on it: TextToSpeech engines differ
# per device, per installed language pack, per Android version. So the phone
# lists them once per connection (`tts_info`) and the list is held HERE —
# never persisted, because a list read from a device that is no longer
# connected describes nothing that is currently true.
#
# NOTHING ON THE DESKTOP CHOOSES FROM IT ANY MORE (owner 2026-08-12). It fed a
# "Voice" dropdown in the Settings window until that dropdown moved onto the
# phone, and the reason it moved is exactly the reason this list is per-device:
# he uses a tablet AND a phone with different engines, so one PC-side choice
# could only ever name a voice that exists on one of them — and the other
# device would fall silently back to its own default while the window still
# showed a name. What remains here is DIAGNOSTIC: the log line below is how a
# session's transcript records what the connected device could speak with, and
# `voices()` is what a future diagnostic surface would read.
#
# `notify_voice` in the settings file is untouched and still rides every frame
# (`_frame`): a phone that has never made its own choice keeps obeying it, so
# the move costs no device its current behaviour. A phone WITH a choice ignores
# it (client/notify.js -> notifyVoicePref).
_voices: list[dict] = []


def set_voices(reported) -> int:
    """Remember what the phone can speak with. Anything unusable is dropped
    rather than trusted — a name that reaches the log must be a real one."""
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
    """What the last connected phone reported it can speak with. Empty until a
    phone has connected at least once this run. Diagnostic since 2026-08-12 —
    the choice itself is made on the device (see the note above)."""
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


def speak_summary(project, agent: str) -> str:
    """What the VOICE says — deliberately NOT what the banner shows.

    THE REPEAT (owner screenshots, v0.0.107): the banner's body is fine — the
    problem is that TTS read the WHOLE thing, body included, sentence after
    Serbian sentence, because `handleNotify()` on the phone had always been
    told to speak `title + ". " + body` and nothing here ever gave it a
    shorter alternative. His order: the spoken line is ONLY the project name
    plus the conversation/agent title, e.g. "Vibe Coder — Fix layout" — never
    the free-text body, which can be an arbitrarily long question or status
    line an agent wrote for the SCREEN, not for a voice.

    `project` = the human folder name from the agent's own `cwd` (never
    lower-cased, never guessed — the same field `layout_of` already reads,
    kept in its original case here because this one is READ ALOUD and
    "vibecoder" spoken is not the same word as "Vibe Coder" written).
    `agent` = the same string `compose()` turns into the title, taken
    BEFORE the " needs you"/"finished"/… suffix is appended and the body is
    never part of it, structurally — this function is never handed the body
    at all.
    """
    folder = pathlib.Path(str(project or "").strip()).name
    agent = str(agent or "").strip()
    if folder and agent:
        return f"{folder} — {agent}"
    return agent or folder


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

# The web layer's one-device-at-a-time slot, handed over by register(). Read
# ONLY — this module never writes it, and that is the whole reason a waiting
# channel can never be mistaken for a present phone (see the route below).
_page: dict = {"ws": None}


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


async def _wait_for_news(device: str = LEGACY_DEVICE):
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


def register(app, token: str, active_client: dict, layouts=None) -> None:
    """Adds `POST /notify` and `GET /notices` to the running server.

    `active_client` is the web layer's own one-device-at-a-time slot — this
    module deliberately keeps no second registry, so a phone that took the
    session over (code 4409) is the one that gets the notices.

    `layouts` is the live registry, used for one thing only: answering "which
    layout is this agent's project showing" at the moment a notice goes out
    (`layout_of`). None — a server built without layouts — simply means every
    notice carries no jump, and the feature is absent rather than wrong.
    """
    global _page, _layouts
    _page = active_client
    _layouts = layouts
    refresh_agent_hook()

    @app.get("/notices")
    async def notices(request: Request):  # noqa: ANN202 — FastAPI route
        """The phone's waiting state. Token-gated like every real endpoint:
        without it this would be a way to make any phone on the network buzz,
        and to learn that an agent runs here at all.

        `device` (task 209) is the shell's own per-install id and is what gives
        each of his phones a channel of its own. It is OPTIONAL on purpose: an
        APK that predates it sends none, lands on the LEGACY slot, and behaves
        exactly as it did before this PC was updated."""
        if request.query_params.get("token") != token:
            return JSONResponse({"ok": False}, status_code=403)
        device = device_key(request.query_params.get("device"))
        return StreamingResponse(_wait_for_news(device),
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
        speak_text = speak_summary(data.get("project"), agent)

        notice = {
            "type": "notify",
            "agent": agent,
            "event": event,
            "title": title,
            "text": body,
            # WHAT THE VOICE SAYS, kept apart from what the banner SHOWS
            # (owner order, v0.0.107 screenshots: the banner text is fine,
            # the spoken line must be short — project + conversation name,
            # never the body). See speak_summary() below.
            "speak_text": speak_text,
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
        # WHERE it happened, when we can say so honestly (task 110). Resolved
        # at SEND time, not at tap time: this is the moment the agent told us
        # its project, and the layout list is a live thing. Absent whenever
        # the agent's project is not on screen anywhere — a jump we cannot
        # make must not be offered.
        #
        # `title` (owner ruling 2026-08-13) is the conversation's own title —
        # the hook reads it off the transcript and rides it here separately
        # from `agent`, because `agent` is that SAME title already cut to 60
        # characters for the banner (or, when the hook found no title at all,
        # something else entirely — an explicit name, a project·session
        # fallback) and truncating the matching copy the same way would throw
        # away exactly the tail that tells two long titles apart. An older
        # hook sends no `title` field; `clean()` then hands `layout_of` "",
        # which is the same "no title" it already treats project-folder-only.
        where = await asyncio.to_thread(
            layout_of, data.get("project"), clean(data.get("title"), MAX_TITLE))
        if where:
            notice["layout"] = where
            logger.info("Notify: %s → layout %d (%s)", agent,
                        where["index"], where["name"])
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
MISSING_SCRIPT_TEXT = ("This copy of Vibe Coder is missing its notifier "
                       "script. Reinstalling the app from the latest release "
                       "puts it back.")
UNLOADABLE_SCRIPT_TEXT = "The notifier script could not be loaded on this PC."
NO_PYTHON_TEXT = ("This PC has no Python on PATH, and Claude Code's hooks "
                  "need one to run the notifier. Install Python and switch "
                  "this on again.")
HOOK_CHANGE_FAILED_TEXT = ("Vibe Coder could not change the notifier hook on "
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


def _ledger_hook_source() -> pathlib.Path:
    """`setup/ledger_hook.py` beside `agent_hook.py` — the session-ledger
    Stop/UserPromptSubmit hook (T111). Never imported (it needs nothing from
    this module), only copied — same reasoning as `_hook_module`'s own path
    fallback: a dev checkout has the repo file, a frozen build has it bundled
    beside the exe."""
    path = PROJECT_ROOT / "setup" / "ledger_hook.py"
    if not path.exists():
        path = BUNDLE_DIR / "setup" / "ledger_hook.py"
    return path


def agent_hook_installed() -> bool:
    try:
        return bool(_hook_module().is_installed())
    except OSError as e:  # noqa: BLE001 — a missing script is "not installed"
        logger.warning("agent hook state unreadable: %s", e)
        return False


def refresh_agent_hook() -> None:
    """Bring the installed copy of the hook up to date with the bundled one.

    The copy in USER_DIR is written only by `set_agent_hook(on=True)` — a
    toggle. An app update ships a newer script inside the bundle, but nothing
    re-toggled the switch, so the owner's machine kept running the OLD hook
    forever while the repo said fixed (found closing task 198). Called once at
    `register()`: when the hook is installed and the deployed bytes differ
    from the bundled ones, the deployed file is rewritten in place. Purely
    frozen-path: a dev checkout registers the repo file directly and has no
    second copy to age.
    """
    # THE REGISTRATION is healed first, frozen or not (owner report 2026-08-15,
    # top priority): a settings file that carries our `Stop` hook and lacks
    # our `Notification` hook was "installed" by every check this app made
    # and never announced a permission prompt to his phone. Re-register with
    # the SAME python and script the switch chose — the file heal below only
    # rewrites bytes, this rewrites the missing event lines.
    try:
        module = _hook_module()
        gap = module.missing_events() if module.is_installed() else ()
        if gap:
            pair = module.registered_command()
            if pair:
                ledger_script = (USER_DIR / "ledger_hook.py") if FROZEN else None
                module.install(script=pathlib.Path(pair[1]), python=pair[0],
                                ledger_script=ledger_script)
                logger.info("agent hook re-registered — %s hook(s) were missing",
                            ", ".join(gap))
    except OSError as e:
        logger.warning("agent hook registration heal failed: %s", e)
    if not FROZEN:
        return
    try:
        if not agent_hook_installed():
            return
        source = pathlib.Path(_hook_module().__file__)
        target = USER_DIR / "agent_hook.py"
        if not (target.exists() and target.read_bytes() == source.read_bytes()):
            USER_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            logger.info("agent hook refreshed to the bundled version (%s)", target)
        # The ledger hook rides beside it — same reasoning, same staleness
        # risk (T111): an update ships a newer ledger_hook.py and nothing
        # re-toggles the switch to pick it up otherwise.
        ledger_source = _ledger_hook_source()
        if ledger_source.exists():
            ledger_target = USER_DIR / "ledger_hook.py"
            if not (ledger_target.exists() and
                    ledger_target.read_bytes() == ledger_source.read_bytes()):
                USER_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ledger_source, ledger_target)
                logger.info("ledger hook refreshed to the bundled version (%s)",
                            ledger_target)
    except OSError as e:
        # A locked file or a permissions error must never stop the server —
        # the stale hook still works, it merely names agents the old way.
        logger.warning("agent hook refresh failed: %s", e)


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
        ledger_script = None
        if FROZEN:
            target = USER_DIR / "agent_hook.py"
            USER_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(script, target)
            script = target
            ledger_source = _ledger_hook_source()
            if ledger_source.exists():
                ledger_target = USER_DIR / "ledger_hook.py"
                shutil.copyfile(ledger_source, ledger_target)
                ledger_script = ledger_target
            python = shutil.which("python") or shutil.which("py") or ""
            if not python:
                return False, NO_PYTHON_TEXT
        module.install(script=script, python=python, ledger_script=ledger_script)
    except OSError as e:
        # Anything from here down (a locked target file, a full disk, a
        # permissions error writing ~/.claude/settings.json inside
        # agent_hook.install()) is OUR problem to phrase, not the owner's to
        # decode — the raw text goes to the log and ONLY the log.
        logger.error("agent hook %s failed: %s", "on" if on else "off", e)
        return False, HOOK_CHANGE_FAILED_TEXT
    logger.info("agent hook installed (%s %s)", python, script)
    return True, ""
