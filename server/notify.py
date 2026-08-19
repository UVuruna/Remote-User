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

WHAT THIS MODULE IS, AFTER THE 2026-08-18 SPLIT (THE STRUCTURE LAW): the
NOTICE ITSELF — the fields it may carry, how they are clamped, what the banner
shows and what the voice says — plus the two routes that put it on the wire.
Three neighbours own the rest, each one responsibility:

- [Notice Channel](notice_channel.py) — HOW it travels: the page socket, the
  per-device waiting channels, the held queue, and the rule that exactly one
  of them carries any notice (`deliver()`).
- [Notify Layout](notify_layout.py) — WHERE it happened: the layout showing
  the conversation that finished (`layout_of`).
- [Agent Hook Switch](agent_hook_switch.py) — what makes any of it fire at
  all: registering Claude Code's hooks on this PC from the Settings checkbox.
"""

import asyncio
import json
import logging
import pathlib
import time

from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from config import SETTINGS
import agent_hook_switch
import notice_channel
import notify_layout

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
    # A DIALOG IS WAITING in a layout he is not looking at (2026-08-19,
    # server/dialog_center.py): its parent's own box, centred on it there.
    "dialog": "has a dialog waiting",
}

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


def make_notice(agent: str, event: str, text: str, speak_text: str,
                speak: bool = True, where: dict | None = None) -> dict:
    """ONE `notify` frame — the shape every notice carrier and the phone
    agree on — built here and nowhere else. The HTTP route below feeds it an
    agent's hook; [Dialog Center](dialog_center.py) feeds it a dialog waiting
    in a layout (2026-08-19). `where` is the layout jump, when there honestly
    is one."""
    title, body = compose(agent, event, text)
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
        "speak": bool(speak) and SETTINGS.notify_speak,
        "voice": SETTINGS.notify_voice,
        "rate": SETTINGS.notify_rate,
        "at": time.time(),
    }
    if where:
        notice["layout"] = where
    return notice


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


def register(app, token: str, active_client: dict, layouts=None) -> None:
    """Adds `POST /notify` and `GET /notices` to the running server.

    `active_client` is the web layer's own one-device-at-a-time slot, handed
    straight to [Notice Channel](notice_channel.py) — this feature
    deliberately keeps no second registry, so a phone that took the
    session over (code 4409) is the one that gets the notices.

    `layouts` is the live registry, used for one thing only: answering "which
    layout is this agent's project showing" at the moment a notice goes out
    (`notify_layout.layout_of`). None — a server built without layouts — simply means every
    notice carries no jump, and the feature is absent rather than wrong.
    """
    notice_channel.set_page(active_client)
    notify_layout.set_layouts(layouts)
    agent_hook_switch.refresh_agent_hook()

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
        device = notice_channel.device_key(request.query_params.get("device"))
        return StreamingResponse(notice_channel.wait_for_news(device),
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
        speak_text = speak_summary(data.get("project"), agent)
        notice = make_notice(agent, event, text, speak_text,
                             speak=bool(data.get("speak", True)))
        logger.info("Notify: %s | %s", notice["title"], notice["text"] or "-")
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
            notify_layout.layout_of, data.get("project"), clean(data.get("title"), MAX_TITLE))
        if where:
            notice["layout"] = where
            logger.info("Notify: %s → layout %d (%s)", agent,
                        where["index"], where["name"])
        # ONE carrier, chosen here and nowhere else (see deliver()). Nothing
        # about the notice itself changes with the carrier — same agent, same
        # line, same speak/voice/rate — so the owner cannot tell which one
        # brought it, which is the point.
        carrier = await notice_channel.deliver(notice)
        if carrier == "held":
            return JSONResponse(notice_channel.NO_CLIENT)
        return JSONResponse(notice_channel.WAITING if carrier == "waiting" else {"ok": True})


