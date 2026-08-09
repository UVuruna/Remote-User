"""The hook that tells the phone an agent finished (ROADMAP Phase H).

Claude Code fires a `Stop` hook when a turn ends. This script is that hook: it
reads the hook payload on stdin, works out WHICH agent it was, and POSTs the
notice to the Remote User server already running on this PC — which forwards
it to the phone as a real notification.

Why a hook and not screen-watching: the tool KNOWS when it is done. Reading
the screen (UIA, pixels, a spinner) is a guess that fails in exactly the case
that matters — a long silent build looks identical to a finished one, and no
screen can tell four agents apart anyway.

It is deliberately dependency-free and import-free: it must run from any
directory, under whatever Python the hook host has, without the project on
sys.path.

Install (once, on this PC):

    python setup/agent_hook.py --install

which adds it to ~/.claude/settings.json as a `Stop` hook. `--uninstall`
removes it, `--test` sends one notice right now so the phone can be checked
without waiting for an agent.

The agent's NAME, in order of preference (owner: "ime agenta je ime sesije"):
  1. $CLAUDE_AGENT_NAME  — an explicit name, when the harness sets one
  2. the payload's session/agent name, if the hook host provides one
  3. the project folder + the session id's first 6 characters, e.g.
     "Remote User · 3f9c1a" — enough to tell four agents apart at a glance
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Where the server keeps the two things this script needs. Read from disk
# rather than passed in, so the hook keeps working after a token rotation or
# a port change (both are ordinary owner actions).
USER_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "RemoteUser"
DEV_DIR = Path(__file__).resolve().parent.parent / "logs"
DEFAULT_PORT = 8777
TIMEOUT_S = 3.0


def read_token() -> str | None:
    for base in (USER_DIR, DEV_DIR):
        path = base / "token.txt"
        try:
            token = path.read_text(encoding="utf-8").strip()
            if token:
                return token
        except OSError:
            continue
    return None


def read_port() -> int:
    for base in (USER_DIR, DEV_DIR):
        try:
            data = json.loads((base / "settings.json").read_text(encoding="utf-8"))
            port = int(data.get("port") or 0)
            if port:
                return port
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return DEFAULT_PORT


def agent_name(payload: dict) -> str:
    explicit = os.environ.get("CLAUDE_AGENT_NAME", "").strip()
    if explicit:
        return explicit[:60]
    for key in ("agent_name", "session_name", "name"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value[:60]
    project = Path(payload.get("cwd") or os.getcwd()).name
    session = str(payload.get("session_id") or "")[:6]
    return f"{project} · {session}".strip(" ·")[:60]


def agent_project(payload: dict) -> str:
    """WHERE this agent was working — the hook's own `cwd`.

    Owner 2026-08-08, task 110: a tap on the notification should take him to
    the layout that agent finished in. The PC could try to work that out by
    matching names, but it never has to: the finishing agent KNOWS its project,
    and this is the one moment it is asked. A guess we can replace with a fact
    is the pattern this project keeps paying for.

    Sent as the whole path; the server takes its last component. A server from
    before this round simply ignores the field.
    """
    return str(payload.get("cwd") or os.getcwd())[:260]


def send(agent: str, event: str, text: str, project: str = "") -> bool:
    token = read_token()
    if not token:
        print("agent_hook: no token file — is Remote User installed?", file=sys.stderr)
        return False
    url = f"http://127.0.0.1:{read_port()}/notify?token={token}"
    body = json.dumps({"agent": agent, "event": event, "text": text,
                       "project": project}).encode()
    request = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            answer = json.loads(response.read() or b"{}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        # The server not running is the ordinary case, not an error worth
        # breaking a turn over — a hook that fails loudly would make every
        # agent's last word an exception.
        print(f"agent_hook: could not reach Remote User ({e})", file=sys.stderr)
        return False
    if not answer.get("ok"):
        print(f"agent_hook: {answer.get('reason', 'not delivered')}", file=sys.stderr)
    return bool(answer.get("ok"))


# ═══════════════════════════ INSTALLATION ═══════════════════════════

SETTINGS = Path.home() / ".claude" / "settings.json"
MARKER = "agent_hook.py"


# WHICH HOOKS THIS SCRIPT INSTALLS, and why there are two.
#
# `Stop` fires when a turn ENDS — the agent is no longer working and the next
# move is his ("<agent> needs you").
#
# `Notification` fires when Claude Code stops to ASK — a permission, a choice,
# one of the votes on screen (owner 2026-08-09: "kada Claude nešto da na
# glasanje, da li možemo i to da izgovorimo"). It is a different event and it
# deserves a different sentence: a turn that ended can wait, a question has
# stopped everything until he answers. Same script, same delivery, one
# argument apart — `--asking` is passed on the hook's command line, because
# the payload does not name which hook invoked it.
HOOK_EVENTS = ("Stop", "Notification")


def hook_entry(script: Path | None = None, python: str | None = None,
               event: str = "Stop") -> dict:
    """One hook line. `script`/`python` are given by the desktop app's
    own switch (ROADMAP H2): the packaged EXE has no interpreter inside it, so
    it copies this file somewhere permanent and names a real python."""
    command = f'"{python or sys.executable}" "{(script or Path(__file__)).resolve()}"'
    if event == "Notification":
        command += " --asking"
    return {"matcher": "*", "hooks": [{"type": "command", "command": command}]}


def is_installed() -> bool:
    """Whether THIS hook is currently registered — the desktop switch shows
    the truth rather than remembering a setting of its own."""
    try:
        data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    # The Stop hook is the one that has always been here and the one the
    # desktop switch is about; a settings file written before 2026-08-09 has
    # only that one, and must still read as installed.
    return MARKER in json.dumps(data.get("hooks", {}).get("Stop") or [])


def install(remove: bool = False, script: Path | None = None,
            python: str | None = None) -> int:
    try:
        data = json.loads(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    except (OSError, json.JSONDecodeError) as e:
        print(f"Cannot read {SETTINGS}: {e}", file=sys.stderr)
        return 1
    hooks = data.setdefault("hooks", {})
    for event in HOOK_EVENTS:
        # Drop any earlier copy of OURS and leave every other hook alone —
        # this file is not the only thing that may live in his settings.
        kept = [h for h in hooks.get(event) or [] if MARKER not in json.dumps(h)]
        if not remove:
            kept.append(hook_entry(script, python, event))
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(("Removed from " if remove else "Installed into ") + str(SETTINGS))
    return 0


def main() -> int:
    if "--install" in sys.argv:
        return install()
    if "--uninstall" in sys.argv:
        return install(remove=True)
    if "--test" in sys.argv:
        probe = {"cwd": os.getcwd(), "session_id": "test00"}
        ok = send(agent_name(probe), "finished",
                  "Test notice from agent_hook.py", agent_project(probe))
        return 0 if ok else 1

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        payload = {}
    # "waiting", not "finished" (owner 2026-08-06: *"rekao mi je da si završio…
    # ali vidim da još radiš"*). A `Stop` hook fires when the agent ENDS A
    # TURN, which happens every time it answers — including mid-job, when it
    # stops to ask something. What is always true at that moment is that it is
    # no longer working and the next move is his, and that is what the phone
    # now says: "<agent> needs you".
    # WHICH hook fired is not in the payload, so the command line says it.
    # "asking" and "waiting" are two different sentences on the phone because
    # they are two different situations: a turn that ended can wait, a
    # question has stopped everything until he answers.
    asking = "--asking" in sys.argv
    # A Notification hook carries the text Claude Code would have shown him.
    # Passing it through means the phone can say WHAT is being asked instead
    # of only that something is.
    text = str(payload.get("message") or "")[:200] if asking else ""
    send(agent_name(payload), "asking" if asking else "waiting", text,
         agent_project(payload))
    return 0   # a hook must never fail the turn it reports on


if __name__ == "__main__":
    sys.exit(main())
