"""Which torn-off VS Code window belongs to which trunk window — read from
VS Code's own record, never guessed from what we did ourselves.

WHY THIS EXISTS (owner report 2026-08-17): the layout list's star (`server/
layout_state.py`) marks a layout whose window is the TRUNK another layout's
content hangs off, and until this module it read that fact ONLY off
`Layout.sources` — written when WE tore a tab off during creation, in THIS
server run. A restart, a layout built from windows that were already open, or
the owner tearing a tab off BY HAND all leave no record, and the star simply
never appears. `Layout.sources` still wins wherever it has an answer (see
`layout_state.py`) — this module is the second source, for what we did not
watch happen.

WHERE THE ANSWER LIVES (measured on the owner's own desk, do not re-derive):
VS Code keeps this itself in `%APPDATA%\\Code\\User\\workspaceStorage\\<hash>\\
state.vscdb` (SQLite, table `ItemTable`), the SAME per-window database
`agents.py` already reads for the active-tab lookup:

  * `memento/workbench.parts.editor` -> the MAIN window's editor grid
    (`agents._tabs_from_memento` reads this one — for Claude Code panels only;
    left exactly as it is, including its known flat-key bug, per instruction).
  * `memento/workbench.editorParts` -> `{"editorparts.state": {"auxiliary":
    [...]}}`, a LIST of the torn-off ("floating editor") windows. Each entry
    carries `state` (the same nested `serializedGrid` shape as the main grid),
    `bounds` (that window's own rectangle) and other fields we do not need.
  * An editor inside either grid is `{"id": ..., "value": "<json string>"}`;
    the inner JSON has `"title"` — the tab title, elided with a real `…`
    exactly as the Windows window title is. A VS Code window title reads
    `<tab title> - <folder> - Visual Studio Code[ tail]`, so the window title
    STARTS WITH the tab title.

Verified on the owner's desk: 3 live windows of one project, main grid one
tab, auxiliary list two, the remaining window the trunk — independently
confirmed against the title bars.

THE REMAINDER RULE, and why it is deliberate (rule 4 below): matching a
branch to its auxiliary record only proves it is NOT the main window. The
main window's OWN bounds live in a different file (`workspace.json` names
nothing about the live grid), so rather than reading a third source, the
trunk is simply whatever is LEFT once every branch is accounted for. Zero or
several leftovers means the question cannot be answered honestly, and this
returns nothing for that folder rather than picking one.

READ POLICY (the owner's own question, and the reason for this shape): NO
timer, no polling, no read unless `trunk_map` is called. The auxiliary
records are cached per storage dir, keyed by the file's `(st_mtime,
st_size)` — a call whose file is unchanged costs one `os.stat` (measured
~6 us); a changed file costs one real read (measured ~2 ms on a 92 KB file:
a throwaway copy plus two SQL queries, via `agents._readonly_copy` — VS Code
holds the live file open and must never be touched directly). The hwnd
matching itself is pure and re-runs on every call (constraint 13 of this
project's CLAUDE.md — never remember geometry); nothing is cached against a
window handle, because Windows reuses handles.

HONEST LIMITS:
  * VS Code flushes this file LAZILY, as part of its own on-disk cache
    (measured 56 s old at one read, 4 minutes at another on the owner's own
    desk — it IS written during a session, not only on exit). A window torn
    off seconds ago may be absent until the next flush. That is exactly why
    rule 1 stands: a miss must always mean no star, never a guess.
  * VS Code only. Nothing here says anything about Chrome, Explorer or any
    other app's own multi-window story.
  * One project folder maps to one storage folder (`agents.
    _workspace_storage_dir` matches by the folder's full path). The SAME
    folder opened in two real main windows correctly leaves two windows
    "left over" for that folder, and rule 4 answers nothing rather than
    picking one.
  * The project folder is recovered through `agents.project_dir_of`, which
    reads it off a live Claude Code transcript for that folder — the same
    path `agents.claude_state` already depends on. A folder VS Code has open
    that Claude Code has never touched cannot be resolved to a storage dir
    at all, and this module returns {} for it rather than guessing a path
    from the window title's basename.
"""

import json
import logging
import os
import threading
from pathlib import Path

import agents
import lost_windows
import window_manager as wm

logger = logging.getLogger(__name__)

EDITORPARTS_KEY = "memento/workbench.editorParts"

# How far apart (px, x+y) a record's `bounds` and a candidate window's live
# frame may sit and still count as the same window. Generous on purpose —
# DWM frame vs. VS Code's own reported bounds can differ by its invisible
# border — but never used unless two candidates already tied on TITLE, so a
# loose tolerance here still never manufactures a match title did not.
BOUNDS_TOLERANCE_PX = 60

_cache_lock = threading.Lock()
# storage_dir -> ((mtime, size), parsed auxiliary records)
_cache: dict[Path, tuple[tuple[float, int], list[dict]]] = {}

_logged_lock = threading.Lock()
_logged_pairs: set[tuple[int, int]] = set()


def _bare(title: str) -> str:
    """Strip a trailing elision `…` — VS Code's live title and its own
    flushed memento do not always agree on which side elided (see
    `agents.session_for_tab`, the same rule)."""
    return (title or "").rstrip("…").rstrip()


def _bounds_rect(bounds) -> tuple[float, float, float, float] | None:
    """`(x, y, w, h)` from whichever shape `bounds` turns out to be at
    runtime, or None when it cannot be understood — treated as no help,
    never as a crash."""
    if not isinstance(bounds, dict):
        return None
    try:
        if all(k in bounds for k in ("x", "y", "width", "height")):
            return (float(bounds["x"]), float(bounds["y"]),
                     float(bounds["width"]), float(bounds["height"]))
        if all(k in bounds for k in ("left", "top", "right", "bottom")):
            return (float(bounds["left"]), float(bounds["top"]),
                     float(bounds["right"]) - float(bounds["left"]),
                     float(bounds["bottom"]) - float(bounds["top"]))
    except (TypeError, ValueError):
        return None
    return None


def _editor_titles(node) -> list[str]:
    """Every tab title under a `serializedGrid` node.

    A different shape from `agents._tabs_from_memento`'s Claude-webview
    descriptors (`viewType` + `title` directly on the dict): an ordinary
    editor entry here is `{"id": ..., "value": "<json string>"}`, and the
    title lives inside that inner JSON string. Walked generically, like
    `agents._walk_editors`, because the exact grid depth is not a contract
    this module wants to hold either."""
    out: list[str] = []
    stack = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            value = cur.get("value")
            if isinstance(value, str):
                try:
                    inner = json.loads(value)
                except (json.JSONDecodeError, ValueError):
                    inner = None
                if isinstance(inner, dict) and isinstance(inner.get("title"), str):
                    out.append(inner["title"])
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return out


def _parse_auxiliary(storage_dir: Path) -> list[dict]:
    """`[{"titles": [...], "bounds": <raw>}]` — one entry per auxiliary
    (torn-off) VS Code window this project's storage remembers.

    [] on ANY failure — a missing file, a missing key, malformed JSON, a
    locked database, a VS Code old enough to have never written this
    memento. This runs inside the `layout_state` frame and must never
    raise (rule 7)."""
    vscdb = storage_dir / "state.vscdb"
    if not vscdb.is_file():
        return []
    try:
        with agents._readonly_copy(vscdb) as conn:
            row = conn.execute(
                "SELECT value FROM ItemTable WHERE key = ?",
                (EDITORPARTS_KEY,)).fetchone()
    except Exception as e:  # sqlite3.DatabaseError, OSError, and friends —
        # a locked/corrupt copy must never take the whole frame down.
        logger.debug("vscode_windows: could not read %s: %s", vscdb, e)
        return []
    if row is None:
        return []
    try:
        memento = json.loads(row[0])
    except (json.JSONDecodeError, ValueError, TypeError):
        return []
    state = memento.get("editorparts.state") if isinstance(memento, dict) else None
    auxiliary = state.get("auxiliary") if isinstance(state, dict) else None
    if not isinstance(auxiliary, list):
        return []
    out: list[dict] = []
    for entry in auxiliary:
        if not isinstance(entry, dict):
            continue
        aux_state = entry.get("state")
        grid = aux_state.get("serializedGrid") if isinstance(aux_state, dict) else None
        titles = _editor_titles(grid) if grid is not None else []
        if titles:
            out.append({"titles": titles, "bounds": entry.get("bounds")})
    return out


def _cached_auxiliary(storage_dir: Path) -> list[dict]:
    """`_parse_auxiliary`, cached by the file's own `(mtime, size)` — see
    the module docstring's READ POLICY."""
    try:
        st = os.stat(storage_dir / "state.vscdb")
        key = (st.st_mtime, st.st_size)
    except OSError:
        return []
    with _cache_lock:
        cached = _cache.get(storage_dir)
    if cached is not None and cached[0] == key:
        return cached[1]
    records = _parse_auxiliary(storage_dir)
    with _cache_lock:
        _cache[storage_dir] = (key, records)
    return records


def _log_once(trunk: int, branch: int) -> None:
    """A resolved pair is logged at INFO exactly once — `layout_state` asks
    on every focus and every frame, and the owner's log must be able to
    answer "did it see it" without being flooded by a pair it sees on
    every one of them (rule 6)."""
    with _logged_lock:
        if (trunk, branch) in _logged_pairs:
            return
        _logged_pairs.add((trunk, branch))
    logger.info("vscode_windows: trunk %s -> branch %s", trunk, branch)


def _match_record(record: dict, candidates: list[int],
                   titles_by_hwnd: dict[int, str]) -> int | None:
    """Which of `candidates` this auxiliary record names, or None when it
    cannot be answered without guessing (rule 1)."""
    bare_record_titles = {_bare(t) for t in record["titles"]}
    matched = []
    for hwnd in candidates:
        bare_tab = _bare(titles_by_hwnd[hwnd])
        if bare_tab and any(bare_tab.startswith(rt) or rt.startswith(bare_tab)
                             for rt in bare_record_titles):
            matched.append(hwnd)
    if not matched:
        logger.debug("vscode_windows: no live window title matches record "
                     "titles %r", record["titles"])
        return None
    if len(matched) == 1:
        return matched[0]
    # Two or more windows share a tab title — the bounds tie-break (rule 3).
    # Judged by where the window RESTS (`lost_windows.resting_rect` —
    # `GetWindowPlacement.rcNormalPosition` when minimized, the live frame
    # otherwise), never by `wm._frame_rect` alone: a MINIMIZED window's live
    # frame is a fixed off-screen rect regardless of which window it really
    # is (measured `(-32000, -32000, 199, 34)` for every minimized window on
    # the owner's desk), so `_frame_rect` alone could never break a tie for a
    # minimized window. `resting_rect` already exists for this identical
    # problem (constraint 17); it is imported, never re-derived.
    #
    # BUT THIS ONLY HELPS WHERE THE WINDOWS ACTUALLY SIT APART (measured,
    # 2026-08-17): a SOLO layout places its one member into the layout's own
    # region, and every solo layout on the same desk uses that SAME region —
    # so on the owner's own machine three minimized solo-layout members all
    # rest at the identical rect. `resting_rect` cannot separate windows WE
    # put in one place; no geometry can. A genuine title collision inside one
    # layout's region is UNRESOLVABLE BY DESIGN, and it stays that way: the
    # cost is a missing ⭐ (rule 1 working as intended), never a wrong one.
    target = _bounds_rect(record.get("bounds"))
    if target is None:
        logger.debug("vscode_windows: %d windows tie on title %r and bounds "
                     "could not be read — leaving it out",
                     len(matched), record["titles"])
        return None
    tx, ty, _tw, _th = target
    scored = []
    for hwnd in matched:
        rect = lost_windows.resting_rect(hwnd)
        if rect is None:
            continue
        x, y, _w, _h = rect
        scored.append((abs(x - tx) + abs(y - ty), hwnd))
    if not scored:
        logger.debug("vscode_windows: %d windows tie on title %r, no live "
                     "rect could be read — leaving it out",
                     len(matched), record["titles"])
        return None
    scored.sort(key=lambda pair: pair[0])
    best_dist, best_hwnd = scored[0]
    if best_dist > BOUNDS_TOLERANCE_PX:
        logger.debug("vscode_windows: closest bounds match is %d px off "
                     "(tolerance %d) — leaving it out", best_dist, BOUNDS_TOLERANCE_PX)
        return None
    if len(scored) > 1 and scored[1][0] - best_dist < 1:
        logger.debug("vscode_windows: bounds tie-break itself tied — "
                     "leaving it out")
        return None
    return best_hwnd


def trunk_map(hwnds: list[int]) -> dict[int, int]:
    """{branch window -> its trunk window} for the VS Code windows among
    `hwnds`. {} when the answer is not known.

    Groups `hwnds` by project folder (`agents.title_folder`), and for each
    folder: reads that folder's auxiliary (torn-off) window records from VS
    Code's own storage, matches each record to one of the folder's live
    windows by tab title (with a bounds tie-break for a title collision),
    and calls whatever is LEFT of the folder's windows the trunk — but only
    when exactly one is left (rule 4). A folder with no resolvable storage,
    no auxiliary records, or an ambiguous remainder contributes nothing; it
    is never a reason to fail the whole call. See the module docstring for
    the full contract and its honest limits."""
    out: dict[int, int] = {}
    if not hwnds:
        return out
    code_hwnds = [h for h in hwnds if wm._process_name(h).lower() == "code.exe"]
    if not code_hwnds:
        return out
    titles_by_hwnd = {h: wm._title(h) for h in code_hwnds}
    by_folder: dict[str, list[int]] = {}
    for h in code_hwnds:
        folder = agents.title_folder(titles_by_hwnd[h])
        if folder:
            by_folder.setdefault(folder, []).append(h)

    for folder, folder_hwnds in by_folder.items():
        project_dir = agents.project_dir_of(folder)
        storage_dir = (agents._workspace_storage_dir(project_dir)
                       if project_dir else None)
        if storage_dir is None:
            logger.debug("vscode_windows: no workspace storage resolved "
                         "for folder %r", folder)
            continue
        records = _cached_auxiliary(storage_dir)
        if not records:
            continue

        remaining = list(folder_hwnds)
        branches: list[int] = []
        for record in records:
            branch = _match_record(record, remaining, titles_by_hwnd)
            if branch is not None:
                branches.append(branch)
                remaining.remove(branch)
        if not branches:
            continue

        trunks = [h for h in folder_hwnds if h not in branches]
        if len(trunks) != 1:
            logger.debug("vscode_windows: folder %r left %d windows as "
                         "trunk candidates — refusing to guess",
                         folder, len(trunks))
            continue
        trunk = trunks[0]
        for branch in branches:
            out[branch] = trunk
            _log_once(trunk, branch)
    return out
