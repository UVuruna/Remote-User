"""A LAYOUT FROM A WINDOW THAT IS NOT OPEN YET (owner request 2026-08-09,
task 184, with his three jump-list screenshots).

Until this module the phone could only build a layout out of what was ALREADY
standing on the desk: "Tap a window" and "From a list" both enumerate the
present. His observation, and the whole feature:

    lang-ok: owner quote
    "recent imaju svi"

Every one of the three apps he adapts layouts around keeps a recent list that
the taskbar's own jump list already shows him. So the phone gets a THIRD
source — **New** — which offers those recents plus a plain new window, opens
the chosen thing on the PC, and hands the window that appears to the ordinary
creation flow.

## Where each list really comes from, and how hard each one is

This was recorded as an HONEST DIFFICULTY per app before a line was written,
because the three are not equally knowable and a module that hid that would
promise Chrome history it cannot read:

* **Explorer — a clean API.** The shell exposes Quick Access as a real folder,
  and `Shell.Application` enumerates it (`comtypes`, which ships with
  `uiautomation` and is therefore already in the app). TWO folders are read:
  `{3936E9E4-…}` (Frequent — the PINNED and frequent FOLDERS, which is what a
  window can be opened on) and `{679F85CB-…}` (Quick Access itself, whose
  entries are mostly recent FILES — filtered to folders, since opening a file
  is not opening an Explorer window).
* **VS Code — a plain read.** `%APPDATA%/Code/User/globalStorage/state.vscdb`
  (SQLite) carries `history.recentlyOpenedPathsList`, the LIVE list VS Code
  itself rewrites on every folder it opens and renders "Open Recent" from —
  most-recent-first, `folderUri`/`workspace.configPath` entries only.
  (Task 242 corrected this from `storage.json`'s `lastKnownMenubarData`, a
  cache of the menu's last PAINT that on this machine was stale enough to
  miss the project open in front of him.)
* **Chrome — honestly nothing yet.** Its "recently closed" lives in the
  session files (`Sessions/Session_*`), an undocumented binary command stream
  that changes between versions. Parsing it is deferred, and this module says
  so by offering what it CAN do without lying: **New window** and
  **Incognito**.

## The honest limits (named here, not discovered later)

* Chrome recents are NOT read. Two plain entries stand in their place.
* VS Code's list needs `state.vscdb` to exist and be readable. A profile
  that has never opened a folder, or a VS Code fork under another folder
  name, yields nothing — and nothing is what this returns, never a guess.
* Quick Access's own list is mostly recent FILES. Only its folders are
  offered, so it is usually shorter here than in Explorer's own pane.
* An entry names a PATH, and a path can be gone (a removed drive, a deleted
  folder). Opening it is what discovers that; the failure comes back to the
  phone as a toast, never as a silent nothing.

## What this module may NOT do

**It never takes the foreground on purpose.** Launching an app inevitably
makes Windows raise its window — that is the app's own doing and it is exactly
what the owner asked for — but nothing here calls `SetForegroundWindow`,
raises, places or pins anything. The window is opened, WATCHED FOR, and handed
back to the phone as an ordinary creation slot; every placement after that is
the creation flow's, through the paths that already exist.
"""

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import Request
from fastapi.responses import JSONResponse

import agents
import layout_popup
import window_manager as wm

logger = logging.getLogger(__name__)


# ═══════════════════════════ RULES ═══════════════════════════
# The three apps he adapts layouts around, in the order the phone lists them.
APPS = ("vscode", "chrome", "explorer")

# How many recents an app may contribute. The phone shows them in a scrolling
# list, so this is about the SIZE OF A CHOICE, not about the screen: past a
# dozen he is reading rather than recognising.
MAX_PER_APP = 12

# How long we wait for the window an entry opened. Cold-starting VS Code on a
# busy machine is several seconds; past this the honest answer is "it did not
# appear", and the phone says so instead of hanging on a spinner.
OPEN_TIMEOUT_S = 25.0
OPEN_POLL_S = 0.25

# THE SECOND GIVE-UP POINT, and it is not an estimate of anything (constraint
# 15). His report 2026-08-13, picture 1: he picked a folder VS Code ALREADY had
# open, VS Code answered by raising the window it already held, no new handle
# ever came into being, and the phone watched the loading cube for the full
# OPEN_TIMEOUT_S over a screen where nothing would ever happen.
#
# `entries()` now greys those rows out, so this is the case that rule cannot
# cover: a folder opened on the PC in the seconds between the list and his tap.
# The CONDITION we are really waiting on is a cold start, and a cold start is
# the only reason 25 s was ever right — so when the app was ALREADY RUNNING
# before we launched (measured, not guessed: its own window was standing), the
# wait is this instead, and the toast NAMES what happened.
RUNNING_TIMEOUT_S = 5.0

# The shell folders Explorer's own Quick Access pane is made of.
QUICK_ACCESS = "shell:::{679f85cb-0220-4080-b29b-5540cc05aab6}"
FREQUENT_FOLDERS = "shell:::{3936E9E4-D92C-4EEE-A85A-BC16D5EA0819}"


# ═══════════════════════════ WHERE THE APPS LIVE ═══════════════════════════
def _env(name: str) -> str:
    return os.environ.get(name, "")


# Candidate install paths, tried in order. A running instance is asked FIRST
# (below), so a portable or store install nobody listed here still works.
_EXE_CANDIDATES = {
    "vscode": [
        Path(_env("LOCALAPPDATA")) / "Programs/Microsoft VS Code/Code.exe",
        Path(_env("ProgramFiles")) / "Microsoft VS Code/Code.exe",
        Path(_env("ProgramFiles(x86)")) / "Microsoft VS Code/Code.exe",
    ],
    "chrome": [
        Path(_env("ProgramFiles")) / "Google/Chrome/Application/chrome.exe",
        Path(_env("ProgramFiles(x86)")) / "Google/Chrome/Application/chrome.exe",
        Path(_env("LOCALAPPDATA")) / "Google/Chrome/Application/chrome.exe",
    ],
    "explorer": [Path(_env("WINDIR")) / "explorer.exe"],
}

_EXE_NAMES = {"vscode": "code.exe", "chrome": "chrome.exe",
              "explorer": "explorer.exe"}


def _running_exe(app: str) -> str:
    """The path of an ALREADY RUNNING instance, read off its own window.

    Cheaper and more truthful than guessing an install location: if he has the
    app open, that is the binary he uses. Costs one `list_windows` sweep, which
    the entry list pays once."""
    want = _EXE_NAMES[app]
    for win in wm.list_windows():
        if win["process"].lower() == want:
            path = wm._process_path(win["hwnd"])
            if path and os.path.exists(path):
                return path
    return ""


def app_exe(app: str) -> str:
    """The executable to launch for `app`, or "" when it is not installed."""
    found = _running_exe(app)
    if found:
        return found
    for cand in _EXE_CANDIDATES.get(app, []):
        if cand.parent.name and cand.exists():
            return str(cand)
    return ""


def _uri_to_path(uri: str) -> str:
    """`file:///u%3A/Coding/…` → `u:\\Coding\\…`. VS Code's own `file://`
    encoding — a drive letter is always followed by the encoded colon."""
    raw = unquote(urlparse(uri).path)          # -> "/u:/Coding/…"
    if len(raw) >= 3 and raw[0] == "/" and raw[2] == ":":
        raw = raw[1:]                          # -> "u:/Coding/…"
    return str(Path(raw))


def vscode_recents() -> list[dict]:
    """VS Code's real, LIVE File ▸ Open Recent list.

    Task 242 (owner report, with screenshot): the previous version read
    `storage.json`'s `lastKnownMenubarData` — a snapshot of the menu taken the
    last time it happened to be RENDERED, which on this machine (checked
    2026-08-11) was stale enough to be missing the project open in front of
    him and full of places he had not touched in months (`M:\\nothing`,
    `U:\\$`, `V:\\Movies`) — "totalno ludacka mesta" (lang-ok: owner quote).
    That cache is not what "Open Recent" shows; it is whatever the menu bar
    happened to hold at its last paint.

    The list VS Code itself opens the menu FROM, and rewrites on every folder
    it opens, is `state.vscdb` (a plain SQLite file) under the key
    `history.recentlyOpenedPathsList` — verified against the real file on this
    machine, same session: entry 0 was the project last opened, entry 4 was
    THIS project. Only `folderUri` / `workspace.configPath` entries are used
    (a `fileUri` entry is a single FILE VS Code once opened loosely, never a
    window "Open Recent" would launch); order is the file's own order, which
    is already most-recent-first. A path that no longer exists is dropped
    here — Explorer's own "not there any more" toast still covers the window
    between this read and the phone's tap, but a gone folder should not even
    be offered as a choice. Every failure mode (no file, locked, unreadable,
    a shape a future version changed) yields an EMPTY list, same as before:
    the phone then shows "New window" alone, honest, instead of a broken
    row — never a fall back to the stale menu cache, which is exactly the bug
    reported."""
    path = Path(_env("APPDATA")) / "Code/User/globalStorage/state.vscdb"
    try:
        # Read-only: a running VS Code holds this file open in WAL mode, and
        # this must never block on, or disturb, its writer.
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
    except sqlite3.OperationalError as e:
        logger.info("VS Code recents unavailable: %s", e)
        return []
    try:
        row = con.execute(
            "SELECT value FROM ItemTable WHERE key = 'history.recentlyOpenedPathsList'"
        ).fetchone()
    except sqlite3.DatabaseError as e:
        logger.info("VS Code recents unavailable: %s", e)
        return []
    finally:
        con.close()
    if not row:
        return []
    try:
        entries = json.loads(row[0]).get("entries") or []
    except (ValueError, AttributeError) as e:
        logger.info("VS Code recents unavailable: %s", e)
        return []

    out: list[dict] = []
    seen: set[str] = set()
    for entry in entries:
        uri = entry.get("folderUri") or (entry.get("workspace") or {}).get("configPath")
        if not uri:
            continue                            # a fileUri — a loose file, not a window
        try:
            target = _uri_to_path(uri)
        except ValueError:
            continue
        key = target.lower()
        if key in seen or not os.path.exists(target):
            continue
        seen.add(key)
        out.append({"target": target, "label": Path(target).name or target,
                    "sub": target})
        if len(out) >= MAX_PER_APP:
            break
    return out


def _shell_folders(namespace: str) -> list[tuple[str, str]]:
    """`(name, path)` of every FOLDER in a shell namespace, via the documented
    `Shell.Application` automation object.

    COM is initialised per call and on THIS thread — the route runs it in a
    worker thread, and a worker thread has no apartment of its own."""
    try:
        import comtypes
        import comtypes.client
    except ImportError as e:      # pragma: no cover — comtypes ships with uiautomation
        logger.info("Quick Access unavailable: %s", e)
        return []
    try:
        comtypes.CoInitialize()
    except OSError:
        pass
    out: list[tuple[str, str]] = []
    try:
        shell = comtypes.client.CreateObject("Shell.Application", dynamic=True)
        items = shell.NameSpace(namespace).Items()
        for i in range(items.Count):
            item = items.Item(i)
            if not item.IsFolder:
                # Quick Access is mostly recent FILES. Opening a file is not
                # opening an Explorer window, so they are not offered.
                continue
            path = str(item.Path or "")
            if path and os.path.isdir(path):
                out.append((str(item.Name or Path(path).name), path))
    except Exception as e:        # noqa: BLE001 — any COM failure is "no list"
        logger.info("Quick Access enumeration failed (%s): %s", namespace, e)
    finally:
        try:
            comtypes.CoUninitialize()
        except OSError:
            pass
    return out


def explorer_recents() -> list[dict]:
    """Pinned + frequent folders first, then whatever folders Quick Access
    itself carries. Duplicates are dropped by PATH, keeping the first — the
    pinned ones he put there himself outrank the ones Windows guessed."""
    seen: set[str] = set()
    out: list[dict] = []
    for namespace in (FREQUENT_FOLDERS, QUICK_ACCESS):
        for name, path in _shell_folders(namespace):
            key = path.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({"target": path, "label": name, "sub": path})
            if len(out) >= MAX_PER_APP:
                return out
    return out


# ═══════════════════════ WHAT IS ALREADY OPEN ═══════════════════════
def open_folders() -> dict[str, set[str]]:
    """`{app: {folder name, …}}` — what VS Code and Explorer really hold NOW.

    Owner request 2026-08-13 (picture 1), and his own words for it: the
    application must be AWARE of what VS Code has open so a row that cannot
    do anything is greyed out and not clickable, rather than opening nothing
    and leaving the phone on a spinner.

    Read off the live windows, never remembered — the desk changes while he
    reads the list, so a stored answer would be the class of bug constraint 13
    is about. The folder a window holds is read from its TITLE, which is the
    only thing Windows offers about a foreign app's document: `agents`
    already owns that reading for VS Code (`title_folder`, the same regex the
    Claude wheel is decided by, so the two can never disagree), and Explorer
    titles its window with the folder's own name.

    THE HONEST LIMIT, named here rather than discovered later: a title carries
    a folder's NAME and not its PATH, so two different projects both called
    `src` are one name to this function and the second would be dimmed while
    it is really openable. The failure is a row he cannot tap, never a wrong
    window — and a full path is not available from a foreign window at all.
    """
    found: dict[str, set[str]] = {app: set() for app in APPS}
    for win in wm.list_windows():
        process = (win.get("process") or "").lower()
        title = win.get("title") or ""
        if process == _EXE_NAMES["vscode"]:
            name = agents.title_folder(title)
            if name:
                found["vscode"].add(name)
        elif process == _EXE_NAMES["explorer"]:
            name = _explorer_folder(title)
            if name:
                found["explorer"].add(name)
    return found


# What Windows 11 puts AFTER the folder's own name in an Explorer window's
# title. MEASURED on this PC 2026-08-13 while building the feature — the first
# version of `open_folders` compared the whole title and matched nothing at
# all, because his open Explorer read `icons - File Explorer` and not `icons`.
# A tuple and not one string: a localised Windows says it in its own words, and
# a suffix we do not know must leave the title alone rather than guess at a
# separator (a folder legitimately called `notes - drafts` would lose half its
# name to a bare split on " - ").
EXPLORER_TITLE_TAILS = (" - file explorer", " - windows explorer")


def _explorer_folder(title: str) -> str:
    """The folder an Explorer window is showing, from its title, lowercased."""
    name = (title or "").strip().lower()
    for tail in EXPLORER_TITLE_TAILS:
        if name.endswith(tail):
            return name[: -len(tail)].strip()
    return name


def _is_open(app: str, target: str, held: dict[str, set[str]]) -> bool:
    """Does `app` already hold this path? Compared by the folder's own name,
    which is all a foreign window's title can tell us (see `open_folders`)."""
    if not target:
        return False               # "New window" is never already open
    return (Path(target).name or target).lower() in held.get(app, set())


def entries() -> list[dict]:
    """Everything the New source offers, grouped by app, in APPS order.

    `kind` is what OPENING it means, and it is the only thing `open_entry`
    reads: `new` = a fresh empty window, `private` = Chrome's incognito, and
    `recent` = open this path. An app that is not installed contributes
    nothing at all — an entry that cannot be opened is not an offer.

    A row the app ALREADY holds carries `open: True` and the `why` the phone
    prints on it; it is drawn dimmed and refuses the tap (owner 2026-08-13).
    It is still SHOWN rather than dropped, on his own ballot: a project that is
    simply missing from the list is a thing he would hunt for, while a dimmed
    row with a reason answers the question he came with."""
    held = open_folders()
    out: list[dict] = []
    for app in APPS:
        if not app_exe(app):
            continue
        out.append({"app": app, "kind": "new", "target": "",
                    "label": "New window", "sub": "",
                    "id": f"{app}|new|"})
        if app == "chrome":
            # THE HONEST HALF (see the module docstring): Chrome's recently
            # closed lives in an undocumented binary session file. Until that
            # is parsed, Chrome offers what it can really do.
            out.append({"app": app, "kind": "private", "target": "",
                        "label": "Incognito", "sub": "",
                        "id": f"{app}|private|"})
            continue
        recents = vscode_recents() if app == "vscode" else explorer_recents()
        for rec in recents:
            busy = _is_open(app, rec["target"], held)
            out.append({"app": app, "kind": "recent", "target": rec["target"],
                        "label": rec["label"], "sub": rec["sub"],
                        "open": busy,
                        "why": "already open" if busy else "",
                        "id": f"{app}|recent|{rec['target']}"})
    return out


# ═══════════════════════════ OPENING ONE ═══════════════════════════
def _command(app: str, kind: str, target: str) -> list[str] | None:
    exe = app_exe(app)
    if not exe:
        return None
    if app == "vscode":
        # `-n` FORCES a new window. Without it VS Code reuses the window that
        # already holds the folder, and this flow would produce no new member
        # at all — it would silently join a window the layout may already own.
        return [exe, "-n"] + ([target] if kind == "recent" and target else [])
    if app == "chrome":
        if kind == "private":
            return [exe, "--incognito"]
        return [exe, "--new-window", "about:blank"]
    # Explorer: a path opens that folder, nothing opens Home. Always a NEW
    # window, because Explorer's own default is one window per invocation.
    return [exe] + ([target] if kind == "recent" and target else [])


def _visible_hwnds() -> dict[int, str]:
    """`{hwnd: process}` for every window a layout could hold — the same
    filter the creation list uses, so a window this module reports is a window
    the creation panel can accept."""
    return {w["hwnd"]: w["process"].lower() for w in wm.list_windows()}


def open_entry(entry_id: str) -> dict:
    """Open it and WAIT for its window.

    Returns the creation-slot dict the phone needs (`hwnd`/`title`/`process`/
    `icon`) or `{"error": …}`. Blocking — the route runs it in a thread.

    NEWNESS is the whole correctness argument, and it is measured the only way
    that survives this project's own lesson (constraint 11: every VS Code
    window shares one process, and one of them is exactly the wrong one). The
    handles standing BEFORE the launch are written down; the window we return
    is one that was not among them and whose process is the one we started.
    A window he already had open can therefore never be handed back as "the
    window that just opened"."""
    app, _, rest = entry_id.partition("|")
    kind, _, target = rest.partition("|")
    if app not in APPS:
        return {"error": "Unknown app"}
    cmd = _command(app, kind, target)
    if cmd is None:
        return {"error": "That app is not installed on the PC"}
    if kind == "recent" and target and not os.path.exists(target):
        return {"error": f"{target} is not there any more"}

    before = _visible_hwnds()
    want = _EXE_NAMES[app]
    # WAS IT ALREADY RUNNING? Measured before the launch, because afterwards
    # the answer is always yes. It decides only how long we are willing to
    # wait and what the phone is told (see RUNNING_TIMEOUT_S).
    was_running = any(process == want for process in before.values())
    # ARMED BEFORE THE LAUNCH (owner report 2026-08-17): the poll below only
    # calls `mine()` once it has FOUND the window, and a cold app start leaves
    # the window standing for as long as it takes the poll's next tick to come
    # round — while the popup sweep runs every second on its own thread. The
    # claim covers that gap by process; `mine()` still names the handle.
    layout_popup.expect(want)
    try:
        # No shell, no console, and NO foreground call of our own: the app
        # raises its own window, which is what he asked for, and nothing here
        # ever reaches for SetForegroundWindow (constraint 11).
        subprocess.Popen(cmd, close_fds=True)
    except OSError as e:
        logger.error("Could not start %s: %s", cmd[0], e)
        return {"error": f"Could not start {os.path.basename(cmd[0])}"}

    # LOOK FIRST, SLEEP AFTER (2026-08-12, the loading-overlay round). The
    # sleep used to come first, so an app that already had its window up by the
    # time `Popen` returned — Explorer on a warm cache, a second Chrome window —
    # still cost a flat OPEN_POLL_S before anyone looked. That is 250 ms of the
    # phone's loading cube spent watching a window that was already there. The
    # poll is otherwise unchanged: the sleep is simply at the END of the turn.
    wait_s = RUNNING_TIMEOUT_S if was_running else OPEN_TIMEOUT_S
    deadline = time.monotonic() + wait_s
    while True:
        for hwnd, process in _visible_hwnds().items():
            if hwnd in before or process != want:
                continue
            info = wm.window_at_hwnd(hwnd)
            if info and info["title"]:
                # OURS, AND THE SWEEP MUST NEVER ASK ABOUT IT (his report
                # 2026-08-13, picture 2). A window WE opened on his behalf is
                # a brand-new top-level window of a known app appearing out of
                # nowhere, which is exactly what `layout_popup`'s attribution
                # rules are built to notice — so every New-source window used
                # to raise a chip asking whether to move it into the layout it
                # was already on its way into. `mine()` is the maker saying so,
                # the same statement tab extraction already makes
                # (`layout_api.py`, constraint 19 point 4A); it is bounded in
                # time there because Windows re-uses handles.
                layout_popup.mine(hwnd)
                logger.info("Recents opened %s (%s) as %s",
                            target or kind, app, info["title"][:60])
                return info
        if time.monotonic() >= deadline:
            break
        time.sleep(OPEN_POLL_S)
    logger.warning("Recents: %s (%s) opened no window within %.0fs "
                   "(%s was already running: %s)",
                   target or kind, app, wait_s, want, was_running)
    if was_running:
        # NAMED, not shrugged off. This is his picture-1 case surviving the
        # grey-out (the folder was opened between the list and the tap), and
        # the sentence has to say what the PC did instead — otherwise the only
        # difference he sees is a shorter spinner before the same mystery.
        return {"error": f"{os.path.basename(cmd[0])} opened no new window — "
                         "it most likely brought the one it already has forward"}
    return {"error": "The window never appeared — is the app still starting?"}


# ═══════════════════════════ THE ROUTES ═══════════════════════════
def register(app, token: str) -> None:
    """`GET /recents` (what can be opened) and `POST /recents/open` (open one).

    Over HTTP rather than on the WebSocket, exactly like the window offer next
    door: the socket's dispatcher lives in [Web Layer](web.py), owned by
    another round, and both of these are plain request/response — a list, and
    one window. Registered from `server_core` beside the other routes."""
    @app.get("/recents")
    async def recents(request: Request):        # noqa: ANN202 — FastAPI route
        if request.query_params.get("token") != token:
            return JSONResponse({"ok": False}, status_code=403)
        found = await asyncio.to_thread(entries)
        return JSONResponse({"ok": True, "entries": found})

    @app.post("/recents/open")
    async def recents_open(request: Request):   # noqa: ANN202 — FastAPI route
        if request.query_params.get("token") != token:
            return JSONResponse({"ok": False}, status_code=403)
        try:
            data = await request.json()
        except ValueError:
            return JSONResponse({"ok": False}, status_code=400)
        info = await asyncio.to_thread(open_entry, str(data.get("id") or ""))
        if info.get("error"):
            return JSONResponse({"ok": False, "error": info["error"]})
        return JSONResponse({"ok": True, "window": info})
