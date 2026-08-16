"""The session ledger — a plain-Markdown to-do list an agent keeps beside a
project and the phone reads (T111, 2026-08-17).

The contract is frozen in `.claude/ledger-plan.md` — this module parses
exactly that grammar and nothing more:

    # <MAIN TITLE>
    project: <absolute cwd>
    - [ ] T1 Task title @fable
      > free description (optional)
      ? question for the human (required when state is [?])
      ! evidence: test/log/screenshot/commit (required for [x])
      - [x] T1a subtask title @sonnet
        ! tests/test_x.py 12/12
    - [>] T2 Another task @opus

States: `[ ]` red · `[>]` orange · `[?]` yellow · `[~]` blue · `[x]` green.
Indent is 2 spaces per nesting level, both for a child task and for its own
`>`/`?`/`!` annotation lines (one level deeper than the task itself).

Pure module — no I/O in `parse()`, so its gate can run it whole against
hand-written text. The two functions that DO touch disk (`sessions_dir`,
`ledger_for_project`) are kept to a few lines each for the same reason:
a parsing bug and a file-lookup bug should never hide behind one signature.
"""

import re
from pathlib import Path

import config

STATE_COLORS = {" ": "red", ">": "orange", "?": "yellow", "~": "blue", "x": "green"}

_TITLE_RE = re.compile(r"^#\s+(.*)$")
_PROJECT_RE = re.compile(r"^project:\s*(.*)$")
_TASK_RE = re.compile(r"^( *)- \[([ x>?~])\]\s*(.*)$")
_ANNOTATION_RE = re.compile(r"^( *)([>?!])\s?(.*)$")
_MODEL_RE = re.compile(r"^(.*?)\s+@(\S+)$")
_ID_RE = re.compile(r"^(T\d+[a-z]*)\s+(.*)$")


def _split_task_text(rest: str) -> tuple[str, str, str]:
    """`"T1 Task title @fable"` -> (id, title, model). Any piece may be
    absent — a task line needs none of them to be valid, only the checkbox."""
    model = ""
    m = _MODEL_RE.match(rest)
    if m:
        rest, model = m.group(1).rstrip(), m.group(2)
    task_id = ""
    m = _ID_RE.match(rest)
    if m:
        task_id, rest = m.group(1), m.group(2)
    return task_id, rest.strip(), model


def _new_task(indent: str, state: str, rest: str) -> dict:
    task_id, title, model = _split_task_text(rest)
    return {
        "id": task_id, "title": title, "model": model, "state": state,
        "desc": "", "question": "", "evidence": "", "children": [],
        "_indent": len(indent),
    }


def _finalize(task: dict) -> dict:
    """The downgrade rule (frozen in the plan): `[x]` with no `!` evidence
    reads as `[~]` blue — a claim of DONE the ledger cannot back is not a
    claim this parser will color green. `[?]` with no `?` line stays yellow
    regardless — a missing question is a sloppy ledger, not a resolved one."""
    state = task.pop("_raw_state", task["state"])
    if state == "x" and not task["evidence"]:
        color = "blue"
    else:
        color = STATE_COLORS.get(state, "red")
    task["state"] = color
    task["children"] = [_finalize(c) for c in task["children"]]
    task.pop("_indent", None)
    return task


def parse(text: str) -> dict:
    """The ledger's whole content, tree-shaped and colored. Never raises —
    a line this grammar does not recognize is simply skipped, because a
    ledger is edited by hand (and by an agent under deadline) and a strict
    parser would turn one typo into a phone panel that shows nothing at
    all."""
    title = ""
    project = ""
    roots: list[dict] = []
    stack: list[dict] = []  # tasks currently open, outermost first

    for raw_line in text.splitlines():
        if not title:
            m = _TITLE_RE.match(raw_line)
            if m:
                title = m.group(1).strip()
                continue
        if not project:
            m = _PROJECT_RE.match(raw_line)
            if m:
                project = m.group(1).strip()
                continue

        m = _TASK_RE.match(raw_line)
        if m:
            indent, raw_state, rest = m.groups()
            task = _new_task(indent, raw_state, rest)
            task["_raw_state"] = raw_state
            level = len(indent)
            while stack and stack[-1]["_indent"] >= level:
                stack.pop()
            if stack:
                stack[-1]["children"].append(task)
            else:
                roots.append(task)
            stack.append(task)
            continue

        if not stack:
            continue  # an annotation line before any task — nothing to attach to
        m = _ANNOTATION_RE.match(raw_line)
        if not m:
            continue
        indent, kind, text_part = m.groups()
        current = stack[-1]
        if len(indent) != current["_indent"] + 2:
            continue  # not this task's own annotation (wrong depth)
        if kind == ">":
            current["desc"] = (current["desc"] + "\n" + text_part).strip("\n") \
                if current["desc"] else text_part
        elif kind == "?":
            current["question"] = text_part
        elif kind == "!":
            current["evidence"] = text_part

    tasks = [_finalize(t) for t in roots]
    return {"title": title, "project": project, "tasks": tasks}


def sessions_dir() -> Path:
    return config.USER_DIR / "sessions"


def _normalized(path: str) -> str:
    """Case-insensitive, separator-normalized — Windows paths compare equal
    whatever slashes or casing the two sides used to write them."""
    return str(Path(path)).replace("\\", "/").casefold()


def ledger_for_project(folder: str) -> tuple[str, Path, dict] | None:
    """The newest ledger file whose `project:` line names `folder` — an agent
    may keep more than one session going, and the newest is the one he is
    watching. Returns (session_id, path, parsed_dict) or None when no ledger
    matches (an empty/missing sessions dir counts as no match, never an
    error)."""
    if not folder:
        return None
    target = _normalized(folder)
    directory = sessions_dir()
    if not directory.is_dir():
        return None
    best: tuple[float, str, Path, dict] | None = None
    for path in directory.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        parsed = parse(text)
        if _normalized(parsed["project"]) != target:
            continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        if best is None or mtime > best[0]:
            best = (mtime, path.stem, path, parsed)
    if best is None:
        return None
    _, session_id, path, parsed = best
    return session_id, path, parsed
