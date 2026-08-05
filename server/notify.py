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
"""

import json
import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse

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

# The phone is asleep in the owner's pocket most of the time, so a notice is
# NOT queued when nobody is connected — an alarm that arrives an hour late is
# worse than none. The answer says so, and the caller decides what to do.
NO_CLIENT = {"ok": False, "reason": "no phone connected"}


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


def register(app, token: str, active_client: dict) -> None:
    """Adds `POST /notify` to the running server.

    `active_client` is the web layer's own one-device-at-a-time slot — this
    module deliberately keeps no second registry, so a phone that took the
    session over (code 4409) is the one that gets the notices.
    """

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

        ws = active_client.get("ws")
        if ws is None:
            return JSONResponse(NO_CLIENT)
        try:
            await ws.send_text(json.dumps({
                "type": "notify",
                "agent": agent,
                "event": event,
                "title": title,
                "text": body,
                "speak": bool(data.get("speak", True)),
                "at": time.time(),
            }))
        except RuntimeError:
            # The socket died between the check and the send — the phone left
            # mid-notice. Nothing to repair, and nothing to hide either.
            logger.warning("Notify dropped — the phone's socket closed mid-send")
            return JSONResponse(NO_CLIENT)
        return JSONResponse({"ok": True})
