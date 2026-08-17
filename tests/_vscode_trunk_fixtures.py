"""The fake desk `tests/test_vscode_trunk.py` asks its questions of.

Split out of that file on 2026-08-17 (THE STRUCTURE LAW, at the coordinator's
own instruction): the seam is real, not a line-count dodge. This module BUILDS
a fake desk and a fake VS Code state — a real temp `state.vscdb`, a fake
window layer, fake `agents`/`lost_windows` lookups — and has its own reason
to change (a new VS Code memento shape, a new window field). The gate file
ASKS the questions of `server/vscode_windows.py` and has a different reason to
change (a new rule, a new failure mode). The precedent is `tests/
_audit_panels.py` / `tests/_audit_js.py` — a `_`-prefixed test HELPER module,
never itself a gate.

NOTHING HERE TOUCHES THE OWNER'S DESKTOP: `os.environ["APPDATA"]` is
redirected per `Storage`, `window_manager._title` / `_process_name`,
`lost_windows.resting_rect` and `agents.project_dir_of` / `agents.
_workspace_storage_dir` are all patched on the MODULE OBJECT (constraint 25 —
`wm` IS `window_manager` everywhere), and `_assert_isolated()` is the gate's
own proof that every folder a check registers resolves inside a temp
directory this module created, never the real profile.
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "server"))

import agents  # noqa: E402
import window_manager  # noqa: E402
import lost_windows  # noqa: E402


# ═══════════════════════════ THE FAKE DESKTOP ═══════════════════════════
# hwnd -> (title, process, rect_or_None). `rect` is (x, y, w, h) — what
# `window_manager._frame_rect` would report; a MINIMIZED window (`minimize`)
# reports its off-screen placeholder here instead, and its real resting
# place lives in RESTING.
WINDOWS: dict[int, tuple[str, str, tuple | None]] = {}
# hwnd -> (x, y, w, h) — what `lost_windows.resting_rect` reports. Defaults
# to WINDOWS' own rect for a window nobody declared minimized.
RESTING: dict[int, tuple] = {}
# folder (as `agents.title_folder` would lowercase it) -> storage dir Path.
FOLDER_STORAGE: dict[str, Path] = {}

_ORIG_APPDATA = os.environ.get("APPDATA")
_ORIG_TITLE = window_manager._title
_ORIG_PROCESS = window_manager._process_name
_ORIG_RESTING_RECT = lost_windows.resting_rect
_ORIG_PROJECT_DIR_OF = agents.project_dir_of
_ORIG_WORKSPACE_STORAGE_DIR = agents._workspace_storage_dir

MISSING_PLACEHOLDER = (-32000, -32000, 199, 34)


def _fake_title(hwnd):
    e = WINDOWS.get(hwnd)
    return e[0] if e else ""


def _fake_process(hwnd):
    e = WINDOWS.get(hwnd)
    return e[1] if e else ""


def _fake_resting_rect(hwnd):
    if hwnd in RESTING:
        return RESTING[hwnd]
    e = WINDOWS.get(hwnd)
    return e[2] if e else None


def _fake_project_dir_of(folder):
    # An arbitrary but STABLE string — its only job is to be the key
    # `_fake_workspace_storage_dir` looks up below; nothing reads it as a
    # real path.
    return f"FAKE-PROJECT-DIR::{folder}" if folder in FOLDER_STORAGE else ""


def _fake_workspace_storage_dir(project_dir):
    if not project_dir or not project_dir.startswith("FAKE-PROJECT-DIR::"):
        return None
    folder = project_dir[len("FAKE-PROJECT-DIR::"):]
    return FOLDER_STORAGE.get(folder)


def install_windows(windows: dict[int, tuple[str, str, tuple]]) -> None:
    """Point the window layer at a fake desk — every window standing
    normally, `_frame_rect` and `resting_rect` agreeing."""
    WINDOWS.clear()
    WINDOWS.update(windows)
    RESTING.clear()
    window_manager._title = _fake_title
    window_manager._process_name = _fake_process
    lost_windows.resting_rect = _fake_resting_rect
    agents.project_dir_of = _fake_project_dir_of
    agents._workspace_storage_dir = _fake_workspace_storage_dir


def minimize(hwnd: int, resting: tuple) -> None:
    """Declare `hwnd` MINIMIZED: its live frame becomes the fixed off-screen
    placeholder Windows really reports for an iconic window (measured on the
    owner's own desk — see `vscode_windows._match_record`'s own comment),
    and `resting_rect` — the only thing the tie-break may read — answers
    `resting` instead."""
    title, process, _ = WINDOWS[hwnd]
    WINDOWS[hwnd] = (title, process, MISSING_PLACEHOLDER)
    RESTING[hwnd] = resting


def restore_fakes() -> None:
    window_manager._title = _ORIG_TITLE
    window_manager._process_name = _ORIG_PROCESS
    lost_windows.resting_rect = _ORIG_RESTING_RECT
    agents.project_dir_of = _ORIG_PROJECT_DIR_OF
    agents._workspace_storage_dir = _ORIG_WORKSPACE_STORAGE_DIR


def restore_appdata() -> None:
    if _ORIG_APPDATA is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = _ORIG_APPDATA


# ═══════════════════════════ THE FAKE STORAGE ═══════════════════════════
def _editor(title: str) -> dict:
    """One `editors[]` entry — `{"id":..., "value": "<json string>"}`, the
    inner JSON carrying `"title"` exactly as the module docstring states."""
    return {"id": "workbench.editors.files.textFileEditor",
            "value": json.dumps({"title": title})}


def _leaf(*titles: str) -> dict:
    return {"type": "leaf",
            "data": {"id": 1, "editors": [_editor(t) for t in titles],
                      "mru": list(range(len(titles)))}}


def _grid(*titles: str) -> dict:
    return {"root": _leaf(*titles), "width": 800, "height": 600,
            "orientation": 0}


def aux(titles: tuple, bounds: dict | None = None) -> dict:
    """One `editorparts.state.auxiliary[]` record."""
    return {"state": {"serializedGrid": _grid(*titles)},
            "bounds": bounds if bounds is not None else
            {"x": 0, "y": 0, "width": 800, "height": 600},
            "zoomLevel": 0, "compact": False, "mode": "normal",
            "alwaysOnTop": False}


def write_vscdb(db_path: Path, *, auxiliary=None, editor_parts_raw=None,
                 malformed=False) -> None:
    """A real SQLite file, `ItemTable(key, value)` — the exact table
    `vscode_windows._parse_auxiliary` reads through `agents._readonly_copy`,
    left UNFAKED: a real copy-then-open of a real file. `auxiliary=None`
    omits `memento/workbench.editorParts` entirely (the missing-key failure
    mode)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS ItemTable "
                      "(key TEXT UNIQUE ON CONFLICT REPLACE, value TEXT)")
        if malformed:
            conn.execute("INSERT INTO ItemTable VALUES (?, ?)",
                          ("memento/workbench.editorParts", "{not json"))
        elif editor_parts_raw is not None:
            conn.execute("INSERT INTO ItemTable VALUES (?, ?)",
                          ("memento/workbench.editorParts", editor_parts_raw))
        elif auxiliary is not None:
            value = json.dumps({"editorparts.state": {"auxiliary": auxiliary}})
            conn.execute("INSERT INTO ItemTable VALUES (?, ?)",
                          ("memento/workbench.editorParts", value))
        conn.commit()
    finally:
        conn.close()


class Storage:
    """A temp directory standing in for ONE project's
    `workspaceStorage/<hash>` folder — `FOLDER_STORAGE` maps a folder name
    straight at it, so `agents._workspace_storage_dir` never has to parse a
    real `workspace.json`."""

    def __init__(self, folder: str):
        self.folder = folder.lower()
        self._tmp = tempfile.TemporaryDirectory(prefix="vscode_trunk_gate_")
        self.dir = Path(self._tmp.name)

    def db(self) -> Path:
        return self.dir / "state.vscdb"

    def install(self) -> None:
        FOLDER_STORAGE[self.folder] = self.dir
        os.environ["APPDATA"] = str(self.dir.parent)  # defense in depth only

    def cleanup(self) -> None:
        FOLDER_STORAGE.pop(self.folder, None)
        self._tmp.cleanup()


def assert_isolated() -> None:
    """This gate's own safety net: every folder a check registered must
    resolve to a path INSIDE a temp dir this module created — proving a
    check that forgot to install its fakes fails LOUD instead of quietly
    reaching for a real project (constraint 33)."""
    tmp_root = Path(tempfile.gettempdir())
    for folder, d in FOLDER_STORAGE.items():
        assert tmp_root in d.parents or d == tmp_root, \
            f"folder {folder!r} resolves outside the temp tree: {d}"


def win(title, process="code.exe", rect=(100, 100, 800, 600)):
    return (title, process, rect)
