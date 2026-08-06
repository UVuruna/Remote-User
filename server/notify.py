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
import pathlib
import shutil
import sys
import time

from fastapi import Request
from fastapi.responses import JSONResponse

from config import BUNDLE_DIR, FROZEN, PROJECT_ROOT, USER_DIR

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

# A notice for a phone that is not here WAITS (owner 2026-08-06). The rule
# used to be "never queue — an alarm an hour late is worse than none", and for
# an alarm that is right; for "your agent finished" it is exactly wrong. The
# owner's own case: two agents finished while he was on the phone with someone,
# the app minimized or closed, and both notices were thrown away — he asked
# what he had to turn on and the answer was "be looking at it already".
#
# So the queue is SHORT and it is HONEST: nothing older than QUEUE_TTL_S is
# ever delivered (a five-minute-old "finished" is useful, an hour-old one is
# noise), at most QUEUE_MAX are held, and each carries the time it happened so
# the phone can say "8 minutes ago" instead of pretending it just landed.
QUEUE_TTL_S = 30 * 60
QUEUE_MAX = 20
_pending: list[dict] = []

NO_CLIENT = {"ok": False, "reason": "no phone connected — held for its return"}


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

        notice = {
            "type": "notify",
            "agent": agent,
            "event": event,
            "title": title,
            "text": body,
            "speak": bool(data.get("speak", True)),
            "at": time.time(),
        }
        ws = active_client.get("ws")
        if ws is None:
            queue(notice)
            return JSONResponse(NO_CLIENT)
        try:
            await ws.send_text(json.dumps(notice))
        except RuntimeError:
            # The socket died between the check and the send — the phone left
            # mid-notice. It is held for its return rather than dropped.
            logger.warning("Notify held — the phone's socket closed mid-send")
            queue(notice)
            return JSONResponse(NO_CLIENT)
        return JSONResponse({"ok": True})


async def send_pending(ws) -> int:
    """Everything that happened while the phone was away, on its return.

    Called once per authenticated connection. Oldest first, so the order the
    agents finished in is the order he reads.
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
        raise OSError("This copy of Remote User is missing its notifier "
                      "script. Reinstalling the app from the latest release "
                      "puts it back.")
    spec = importlib.util.spec_from_file_location("agent_hook", path)
    if spec is None or spec.loader is None:
        raise OSError("The notifier script could not be loaded on this PC.")
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
    the user). Two things the packaged app must handle and the dev checkout
    need not: the script lives inside the bundle and would vanish with the
    next update, so it is copied to the user directory; and there is no
    interpreter in the EXE, so a real python has to be found — if this PC has
    none, that is said plainly instead of leaving a switch that lies."""
    module = _hook_module()
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
            return False, ("This PC has no Python on PATH, and Claude Code's "
                           "hooks need one to run the notifier. Install Python "
                           "and switch this on again.")
    module.install(script=script, python=python)
    logger.info("agent hook installed (%s %s)", python, script)
    return True, ""
