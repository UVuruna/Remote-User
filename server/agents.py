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
at**, and it answers the question outright — a live session names its project,
and a VS Code window title ends in that project's folder name:

    "Ispravka UI dizajna meni… - Remote User - Visual Studio Code [Administrator]"
                                 └── the folder a live session can be matched to

That is the whole bridge, and it needs nothing from the owner.

WHAT THIS MODULE READS, AND WHY IT CHANGED (2026-08-07)
-------------------------------------------------------
The first version rested on ONE measurement — `claude.exe --resume=<uuid>` —
and by the time the owner reported the Claude set missing, that measurement
was already stale. Re-probed on his machine, extension
`anthropic.claude-code-2.1.223` runs:

    claude.exe 15928  parent Code.exe  9268  --output-format stream-json …
    claude.exe 38044  parent Code.exe 37624  --output-format stream-json …
    claude.exe 40272  parent Code.exe  9268  --claude-in-chrome-mcp
    claude.exe 37872  parent Code.exe 37624  --claude-in-chrome-mcp

No `--resume` anywhere, and two of the four are not conversations at all (the
`--claude-in-chrome-mcp` helpers). Resting on one flag is the mistake, not the
flag — so the sources are now tiered, strongest first:

  1. **`~/.claude/sessions/<pid>.json`**, written by Claude Code itself. It
     carries `{pid, sessionId, cwd, procStart, kind, entrypoint}` — the
     project PATH, outright, with no slug to decode and no transcript to read.
     It is cross-checked against the live process table by PID **and process
     start time**, so a leftover file for a recycled PID can never name a
     project that is not running (`procStart` is a FILETIME; WMI reports the
     same instant truncated to microseconds, hence PROC_START_TOL).
  2. **`--resume=<uuid>`** on the command line, for a CLI old enough to pass
     it: the id names `~/.claude/projects/<slug>/<id>.jsonl`, whose `cwd`
     names the project.
  3. **Recently written transcripts**, and only as many of them as there are
     conversations we could not name. Bounding it by that count is the real
     sharpening: freshness alone cannot be tightened to seconds, because the
     moment the owner most needs the Claude wheel is when the conversation is
     IDLE — he is looking at a finished answer, about to dictate the next
     instruction, and nothing has been written for minutes.

`--claude-in-chrome-mcp` never counts as a conversation. It is an MCP helper
started per extension host; treating it as an unnamed session made the module
ask tier 3 for a project on a PC where every conversation was already known.

The honest limit, stated where it cannot be missed: every VS Code window
belongs to the same Electron process (PID 2160 on his machine), so a WINDOW
handle cannot be tied to one extension host. The parent chain does prove HOW
MANY windows run a conversation — the four processes above hang off two
different hosts, 9268 and 37624 — but it cannot say WHICH window: the hosts'
command lines were re-read in full on 2026-08-07 and they are byte-identical
apart from a mojo handle and a trace uuid, carrying no workspace path at all.
Windows' own top-level windows all report PID 2160. So the match stays per
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
from collections.abc import Iterable
from pathlib import Path

logger = logging.getLogger(__name__)

# ═══════════════════════════ WHAT WE LOOK FOR ═══════════════════════════
# One agent per entry: the process that proves it is running, and the name the
# phone's app-aware sets use (`"agent": "claude"` in actions.json).
AGENTS = {"claude": "claude.exe"}

CLAUDE_HOME = Path.home() / ".claude"
CLAUDE_PROJECTS = CLAUDE_HOME / "projects"
# Tier 1: Claude Code's own record of what it is running, one file per PID.
CLAUDE_SESSIONS = CLAUDE_HOME / "sessions"
RESUME_RE = re.compile(r"--resume[= ]([0-9a-fA-F-]{36})")

# A `claude.exe` that is NOT a conversation. These ride along with the VS Code
# extension (one per extension host) and would otherwise be counted as
# sessions we failed to name — which is what dragged tier 3 in on a PC where
# nothing needed it.
HELPER_FLAGS = ("--claude-in-chrome-mcp", "--mcp-serve", " mcp serve")

# WMI reports a process's creation time truncated to microseconds, so the
# FILETIME it gives is up to 9 ticks below the one Claude Code recorded
# (measured: 134305811380595160 vs 134305811380595168). A millisecond of slack
# is far more than that and far less than any chance of a PID being recycled
# onto the same executable.
PROC_START_TOL = 10_000

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
# phone should be told about — used only for the last-resort tier below.
FRESH_S = 30 * 60


class _Cache:
    def __init__(self):
        self.at = 0.0
        self.value: dict[str, set[str]] = {}
        self.lock = threading.Lock()


_CACHE = _Cache()


# ═══════════════════════════ THE PROCESS TABLE ═══════════════════════════
def _processes(exe: str) -> list[tuple[int, int, str]]:
    """`(pid, creation FILETIME, command line)` for every running `exe`.

    PowerShell because Windows has no cheaper way to read another process's
    arguments — `wmic` is gone from Windows 11 and reading a foreign PEB needs
    debug rights we do not want. The creation time comes along for one reason:
    it is what lets a `sessions/<pid>.json` be trusted (see the module
    docstring — a stale file plus a recycled PID would otherwise name a
    project nobody is working in).
    """
    script = (
        f"Get-CimInstance Win32_Process -Filter \"Name='{exe}'\" | ForEach-Object "
        "{ $s = if ($_.CreationDate) { $_.CreationDate.ToFileTimeUtc() } else { 0 }; "
        "\"$($_.ProcessId)|$s|$($_.CommandLine)\" }")
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning("agent probe failed for %s: %s", exe, e)
        return []
    found: list[tuple[int, int, str]] = []
    for line in out.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        try:
            found.append((int(parts[0]), int(parts[1]), parts[2]))
        except ValueError:
            continue
    return found


def _is_conversation(cmd: str) -> bool:
    """A `claude.exe` the owner could actually be talking to — not one of the
    MCP helpers the VS Code extension starts beside it."""
    low = cmd.lower()
    return not any(flag in low for flag in HELPER_FLAGS)


def _live_sessions(procs: list[tuple[int, int, str]]) -> dict[int, str]:
    """TIER 1 — `{pid: project folder}` from `~/.claude/sessions/<pid>.json`,
    keeping only files whose process is still alive AND still the process that
    wrote them."""
    named: dict[int, str] = {}
    # Looked up BY PID rather than by globbing the directory: the file is
    # named after the process, the directory is never cleaned, and reading
    # every leftover from months of sessions to throw almost all of them away
    # would put the cost of this scan on the owner's history instead of on
    # what is running.
    for pid, start, _cmd in procs:
        try:
            info = json.loads(
                (CLAUDE_SESSIONS / f"{pid}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if info.get("pid") != pid:
            continue
        try:
            recorded = int(info.get("procStart") or 0)
        except (TypeError, ValueError):
            recorded = 0
        # No recorded start means an older writer; a recorded one that
        # disagrees means the PID was recycled onto another process.
        if recorded and abs(recorded - start) > PROC_START_TOL:
            continue
        cwd = info.get("cwd")
        if cwd:
            named[pid] = Path(cwd).name.lower()
    return named


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


def _recent_projects(limit: int) -> list[Path]:
    """TIER 3 — the `limit` projects whose transcripts were written most
    recently, newest first, none older than `FRESH_S`.

    Weaker than the two tiers above: it cannot tell a closed session from a
    live one. What keeps it honest is `limit` — the caller passes the number
    of conversations it could NOT name, so one unnamed conversation can light
    up exactly one project instead of every project the owner touched in the
    last half hour. Tightening the freshness window instead would break the
    case that matters most: an idle conversation, finished answer on screen,
    the owner about to dictate, nothing written for minutes.
    """
    if limit <= 0:
        return []
    cutoff = time.time() - FRESH_S
    dated: list[tuple[float, Path]] = []
    try:
        for slug in CLAUDE_PROJECTS.iterdir():
            try:
                touched = max((f.stat().st_mtime for f in slug.glob("*.jsonl")),
                              default=0.0)
            except OSError:
                continue
            if touched >= cutoff:
                dated.append((touched, slug))
    except OSError:
        return []
    dated.sort(key=lambda pair: pair[0], reverse=True)
    return [slug for _, slug in dated[:limit]]


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
    """{agent name: {project folder names it is live in}} — the three tiers of
    the module docstring, strongest first, each one only filling in what the
    one above could not name."""
    live: dict[str, set[str]] = {}
    for agent, exe in AGENTS.items():
        procs = _processes(exe)
        talking = [(pid, start, cmd) for pid, start, cmd in procs
                   if _is_conversation(cmd)]
        if not talking:
            continue
        by_pid = _live_sessions(talking)          # tier 1
        folders = set(by_pid.values())
        unnamed = []
        for pid, _start, cmd in talking:
            if pid in by_pid:
                continue
            match = RESUME_RE.search(cmd)         # tier 2
            slug = _project_of(match.group(1)) if match else None
            if slug:
                folders.add(folder_of(slug))
            else:
                unnamed.append(pid)
        if unnamed:                               # tier 3, bounded by count
            folders |= {folder_of(s) for s in _recent_projects(len(unnamed))}
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


def first_folder(titles: Iterable[str]) -> str:
    """The first of these titles that NAMES a project, lowercased, or "".

    A window can have more than one title worth asking (owner report
    2026-08-08): a VS Code tab torn into its own window may be titled bare
    `Visual Studio Code` — the product name, no folder, nothing any regex can
    match — while the window it was torn OUT of still carries the folder. So
    the caller offers the titles in order of authority and takes the first
    that answers, instead of freezing whichever string happened to exist at
    creation time. See `window_manager.Layout.project`.
    """
    for title in titles:
        folder = title_folder(title)
        if folder:
            return folder
    return ""


def agents_in(folder: str, live: dict[str, set[str]] | None = None) -> list[str]:
    """Which agents are live in THIS project folder — the answer itself.

    Split from `agents_for` on 2026-08-08 so a caller that already knows the
    folder (a layout: see `window_manager.Layout.project`) does not have to
    own a title to ask the question. The folder may be remembered; this
    answer may not — a conversation the owner opens after the layout was made
    must still bring its shortcuts with it, so it is read on every frame.
    """
    if not folder:
        return []
    if live is None:
        live = live_agents()
    return sorted(agent for agent, folders in live.items()
                  if folder in folders)


def agents_for(title: str, live: dict[str, set[str]] | None = None) -> list[str]:
    """Which agents are live in the project this window title names.

    Deliberately title-driven rather than hwnd-driven: see the module
    docstring — every VS Code window shares one process, so the handle cannot
    single out an extension host, while the title carries the folder that a
    live session can be matched against.

    `live` is a SNAPSHOT from `live_agents()`. Pass one whenever you are about
    to ask this for more than one window: without it every call may reach the
    1.85 s PowerShell probe (measured on the owner's PC, 2026-08-07) the
    moment the two-second cache lapses between two entries — and the callers
    that ask it in a loop are async handlers, so that time is the whole event
    loop stopped: no stream, no heartbeats, nothing. Taking the snapshot once,
    in a thread, is the difference between a list that arrives and a phone
    that looks frozen (owner: "treba mu jako dugo da učita").
    """
    return agents_in(title_folder(title), live)


# ═══════════════════════════ WHAT CLAUDE CODE IS SET TO ═══════════════════════════
# For the phone's Model / Thinking choosers, so a list of nine options can say
# which one is already chosen (owner 2026-08-08: "treba da bude stiklirano ono
# koje je trenutno aktivno").
#
# AND IT IS THE SAVED SETTING, NOT THE LIVE ONE — the distinction is the whole
# honesty of this function and the phone must say it that way. Claude Code's own
# docs are explicit that several things outrank this file: a project or local
# `.claude/settings.json`, the CLAUDE_CODE_EFFORT_LEVEL / ANTHROPIC_MODEL
# environment variables, a session-only switch made with `s` in the picker, and
# a session RESUMED from a transcript, which keeps the model it was saved with
# whatever the settings say. `max` and `ultracode` cannot be written here at
# all — they are session-only by design.
#
# So this answers "what will the next session start as", and marking it as
# ACTIVE would be a small lie of exactly the kind this project keeps paying for.
# The picker marks it as SAVED.
CLAUDE_SETTINGS = CLAUDE_HOME / "settings.json"


def claude_settings() -> dict:
    """`{"model": ..., "effort": ...}` from Claude Code's user settings — the
    keys it writes itself (`model`, `effortLevel`). Missing keys mean he has
    never chosen, which is a real answer: nothing is marked."""
    try:
        raw = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    out = {}
    if isinstance(raw.get("model"), str):
        out["model"] = raw["model"]
    if isinstance(raw.get("effortLevel"), str):
        out["effort"] = raw["effortLevel"]
    return out
