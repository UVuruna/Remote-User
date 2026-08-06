"""Which agent tools are LIVE on this PC, and in which project.

Why this module exists at all (owner, 2026-08-06, and he was right to shout):
the previous round concluded that a Claude Code conversation inside VS Code
*cannot be identified*, and made the owner tick a box for it by hand —

    *"ono je od starta bio nakaradan način što ste implementirali da korisnik
    štiklira koji je prozor otvorio, to je idiotizam"*

That conclusion was drawn from ONE source: UI Automation. The window title, the
tab's UIA class, `AutomationId`, `HelpText` and a full walk of the extracted
window's tree — none of them carry the word "claude", because VS Code hides
webview content from accessibility, and Claude Code names its tab after the
CONVERSATION. All of that is still true. **The process table was never looked
at**, and it answers the question outright. Probed on the owner's own machine:

    claude.exe  PID 10016  parent Code.exe 37624  --resume=0eb7cbe2-…
    claude.exe  PID 33104  parent Code.exe  9268  --resume=ed816316-…

Every running conversation is a `claude.exe` carrying its SESSION ID, and a
session id is a file: `~/.claude/projects/<slug>/<session-id>.jsonl`, where the
slug is the project's own path. So a live session names its project, and a VS
Code window title ends in that project's folder name:

    "Ispravka UI dizajna meni… - Remote User - Visual Studio Code [Administrator]"
                                 └── the folder a live session can be matched to

That is the whole bridge, and it needs nothing from the owner.

The honest limit, stated where it cannot be missed: every VS Code window
belongs to the same Electron process (PID 2160 on his machine), so a WINDOW
handle cannot be tied to one extension host. The match is therefore per
PROJECT FOLDER — two windows open on the same folder both count as having the
conversation, when only one of them may actually show it. That is the one case
this gets wrong, and it is a far better trade than asking a user to declare
what his own screen already shows.
"""

import json
import logging
import re
import subprocess
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# ═══════════════════════════ WHAT WE LOOK FOR ═══════════════════════════
# One agent per entry: the process that proves it is running, and the name the
# phone's app-aware sets use (`"agent": "claude"` in actions.json).
AGENTS = {"claude": "claude.exe"}

CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
RESUME_RE = re.compile(r"--resume[= ]([0-9a-fA-F-]{36})")

# A window title ends "<something> - <folder> - Visual Studio Code[ tail]".
# The folder is the second-to-last dash-separated part, and it is the only
# part a project slug can be compared with.
VSCODE_TITLE_RE = re.compile(r"-\s*([^-]+?)\s*-\s*Visual Studio Code", re.I)

# Reading the process table costs a subprocess, so it is CACHED. Two seconds
# is short enough that opening a conversation is noticed before the owner can
# switch to his phone, and long enough that a layout switch never pays for it
# twice.
CACHE_S = 2.0

# A session whose transcript has not been touched in this long is not what the
# phone should be told about — used only for the fallback below.
FRESH_S = 30 * 60


class _Cache:
    def __init__(self):
        self.at = 0.0
        self.value: dict[str, set[str]] = {}
        self.lock = threading.Lock()


_CACHE = _Cache()


# ═══════════════════════════ THE PROCESS TABLE ═══════════════════════════
def _command_lines(exe: str) -> list[str]:
    """Every command line of a running `exe`. PowerShell because Windows has
    no cheaper way to read another process's arguments — `wmic` is gone from
    Windows 11 and reading a foreign PEB needs debug rights we do not want."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             f"Get-CimInstance Win32_Process -Filter \"Name='{exe}'\" "
             "| ForEach-Object { $_.CommandLine }"],
            capture_output=True, text=True, timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning("agent probe failed for %s: %s", exe, e)
        return []
    return [line for line in out.stdout.splitlines() if line.strip()]


def _project_of(session_id: str) -> Path | None:
    """The project directory a session belongs to — the one holding its
    transcript."""
    try:
        for slug in CLAUDE_PROJECTS.iterdir():
            if (slug / f"{session_id}.jsonl").exists():
                return slug
    except OSError:
        return None
    return None


def _recent_projects() -> set[Path]:
    """Fallback for a conversation that carries no `--resume` (a brand new
    one): the projects whose transcripts were written recently. Weaker than
    the session id — it cannot tell a closed session from a live one — so it
    is used only to fill in what the ids could not."""
    fresh: set[Path] = set()
    cutoff = time.time() - FRESH_S
    try:
        for slug in CLAUDE_PROJECTS.iterdir():
            try:
                if any(f.stat().st_mtime >= cutoff for f in slug.glob("*.jsonl")):
                    fresh.add(slug)
            except OSError:
                continue
    except OSError:
        pass
    return fresh


def folder_of(slug_dir: Path) -> str:
    """The project's folder name, lowercased — what a VS Code title shows.

    Read from the transcript's own `cwd`, never guessed from the directory
    name: the slug flattens BOTH path separators and spaces into dashes, so
    `u--Coding-UVuruna-Applications-Remote-User` cannot be split back into
    "Remote User" — the first version of this function returned "user" and
    matched nothing. One line of JSON gives the exact path.
    """
    try:
        files = sorted(slug_dir.glob("*.jsonl"),
                       key=lambda f: f.stat().st_mtime, reverse=True)
    except OSError:
        return ""
    for transcript in files[:3]:
        try:
            with transcript.open(encoding="utf-8", errors="replace") as fh:
                for _ in range(8):
                    line = fh.readline()
                    if not line:
                        break
                    try:
                        cwd = json.loads(line).get("cwd")
                    except (json.JSONDecodeError, ValueError, AttributeError):
                        continue
                    if cwd:
                        return Path(cwd).name.lower()
        except OSError:
            continue
    return ""


def _scan() -> dict[str, set[str]]:
    """{agent name: {project folder names it is live in}}."""
    live: dict[str, set[str]] = {}
    for agent, exe in AGENTS.items():
        lines = _command_lines(exe)
        if not lines:
            continue
        folders: set[str] = set()
        unresolved = 0
        for line in lines:
            match = RESUME_RE.search(line)
            if not match:
                unresolved += 1
                continue
            slug = _project_of(match.group(1))
            if slug:
                folders.add(folder_of(slug))
        if unresolved:
            # Sessions without an id on the command line — new conversations.
            # They ARE running; we just cannot name their project from the
            # process alone, so the recent transcripts answer instead.
            folders |= {folder_of(s) for s in _recent_projects()}
        live[agent] = {f for f in folders if f}
    return live


def live_agents() -> dict[str, set[str]]:
    """Cached `_scan()`. Safe to call per layout, per focus, per state send."""
    now = time.time()
    with _CACHE.lock:
        if now - _CACHE.at < CACHE_S:
            return _CACHE.value
    value = _scan()
    with _CACHE.lock:
        _CACHE.at, _CACHE.value = time.time(), value
    return value


# ═══════════════════════════ WINDOW → AGENT ═══════════════════════════
def title_folder(title: str) -> str:
    """The project folder a VS Code window title names, lowercased, or ""."""
    match = VSCODE_TITLE_RE.search(title or "")
    return match.group(1).strip().lower() if match else ""


def agents_for(title: str) -> list[str]:
    """Which agents are live in the project this window title names.

    Deliberately title-driven rather than hwnd-driven: see the module
    docstring — every VS Code window shares one process, so the handle cannot
    single out an extension host, while the title carries the folder that a
    live session can be matched against.
    """
    folder = title_folder(title)
    if not folder:
        return []
    return sorted(agent for agent, folders in live_agents().items()
                  if folder in folders)
