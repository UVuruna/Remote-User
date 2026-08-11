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
* **VS Code — a plain read.** `%APPDATA%/Code/User/globalStorage/storage.json`
  carries `lastKnownMenubarData`, VS Code's own cached File menu, whose
  "Open Recent" submenu is exactly the list he sees in the jump list. Verified
  against the real file on this machine (2026-08-11): the entries are
  `{"id": "openRecentFolder", "label": "U:\\\\…", "uri": {...}}`. It is a
  CACHE of a menu, which is the honest limit named below.
* **Chrome — honestly nothing yet.** Its "recently closed" lives in the
  session files (`Sessions/Session_*`), an undocumented binary command stream
  that changes between versions. Parsing it is deferred, and this module says
  so by offering what it CAN do without lying: **New window** and
  **Incognito**.

## The honest limits (named here, not discovered later)

* Chrome recents are NOT read. Two plain entries stand in their place.
* VS Code's list is a cached MENU. A profile that has never opened its File
  menu, or a VS Code fork under another folder name, yields nothing — and
  nothing is what this returns, never a guess.
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
import subprocess
import time
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

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


# ═══════════════════════════ THE LISTS ═══════════════════════════
def vscode_recents() -> list[dict]:
    """VS Code's own cached File ▸ Open Recent submenu.

    Read straight out of `storage.json` — no VS Code process is touched and no
    command is run. Every failure mode (no file, unreadable JSON, a menu shape
    a future version changed) yields an EMPTY list: the phone then shows the
    plain "New window" entry alone, which is honest, instead of a broken row."""
    path = Path(_env("APPDATA")) / "Code/User/globalStorage/storage.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        logger.info("VS Code recents unavailable: %s", e)
        return []
    menus = (data.get("lastKnownMenubarData") or {}).get("menus") or {}
    items = (menus.get("File") or {}).get("items") or []
    out: list[dict] = []
    for item in items:
        # "Open &&Recent" — the ampersands are the menu's accelerator markup.
        if "recent" not in str(item.get("label", "")).lower():
            continue
        for sub in (item.get("submenu") or {}).get("items") or []:
            if not str(sub.get("id", "")).startswith("openRecent"):
                continue
            label = str(sub.get("label") or "").replace("&&", "&")
            if not label:
                continue
            out.append({"target": label, "label": Path(label).name or label,
                        "sub": label})
            if len(out) >= MAX_PER_APP:
                return out
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


def entries() -> list[dict]:
    """Everything the New source offers, grouped by app, in APPS order.

    `kind` is what OPENING it means, and it is the only thing `open_entry`
    reads: `new` = a fresh empty window, `private` = Chrome's incognito, and
    `recent` = open this path. An app that is not installed contributes
    nothing at all — an entry that cannot be opened is not an offer."""
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
            out.append({"app": app, "kind": "recent", "target": rec["target"],
                        "label": rec["label"], "sub": rec["sub"],
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
    try:
        # No shell, no console, and NO foreground call of our own: the app
        # raises its own window, which is what he asked for, and nothing here
        # ever reaches for SetForegroundWindow (constraint 11).
        subprocess.Popen(cmd, close_fds=True)
    except OSError as e:
        logger.error("Could not start %s: %s", cmd[0], e)
        return {"error": f"Could not start {os.path.basename(cmd[0])}"}

    deadline = time.monotonic() + OPEN_TIMEOUT_S
    while time.monotonic() < deadline:
        time.sleep(OPEN_POLL_S)
        for hwnd, process in _visible_hwnds().items():
            if hwnd in before or process != want:
                continue
            info = wm.window_at_hwnd(hwnd)
            if info and info["title"]:
                logger.info("Recents opened %s (%s) as %s",
                            target or kind, app, info["title"][:60])
                return info
    logger.warning("Recents: %s (%s) opened no window within %.0fs",
                   target or kind, app, OPEN_TIMEOUT_S)
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
