"""The session-ledger Claude Code hook (T111, 2026-08-17).

Keeps the ledger file described in `.claude/ledger-plan.md` in sync with an
agent's own turns, without the agent having to remember to do it:

  * `prompt` (Claude Code's `UserPromptSubmit`): creates `<session_id>.md` if
    it does not exist yet (title = the first line of the prompt, clamped;
    `project:` = the hook's own `cwd`), stamps the moment with a sidecar
    `<session_id>.stamp`, and prints the ledger's grammar plus its CURRENT
    content to stdout — that text becomes part of the agent's own context for
    the turn, which is how the instruction reaches it without a second
    channel.
  * `stop` (Claude Code's `Stop`): refuses to let the turn end silently if
    the ledger was never touched since the prompt stamp, or if it was touched
    but no longer parses — printing `{"decision":"block", "reason": …}` is
    how a Stop hook sends a turn back to the agent (Claude Code's own
    contract, not this project's).

Deliberately dependency-free and import-free of the rest of this repo — like
`agent_hook.py` beside it, this file runs standalone under WHATEVER python
the hook host has, on a stranger's PC, with nothing on `sys.path` but the
standard library.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

# %LOCALAPPDATA%/VibeCoder/sessions on a real install; overridable so a test
# never has to touch the real user directory (VIBECODER_SESSIONS_DIR).
_DEFAULT_USER_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "VibeCoder"


def sessions_dir() -> Path:
    override = os.environ.get("VIBECODER_SESSIONS_DIR")
    if override:
        return Path(override)
    return _DEFAULT_USER_DIR / "sessions"


TITLE_MAX_CHARS = 80

# The same grammar `server/session_ledger.py` parses — kept identical in
# spirit deliberately (a task line, then optional `>`/`?`/`!` lines one level
# deeper), duplicated here rather than imported because this script must run
# with NOTHING on sys.path but the standard library.
_TASK_RE = re.compile(r"^( *)- \[([ x>?~])\]\s*(.*)$")
_ANNOTATION_RE = re.compile(r"^( *)([>?!])\s?(.*)$")

GRAMMAR = """\
Session ledger grammar (this file, `{path}`):

  # <MAIN TITLE — one line, you may rewrite it>
  project: <absolute cwd>
  - [ ] T1 Task title @fable
    > free description (optional)
    ? question for the human (REQUIRED when the state is [?])
    ! evidence: test/log/screenshot/commit (REQUIRED for [x])
    - [x] T1a subtask title @sonnet
      ! tests/test_x.py 12/12

States: [ ] not started (red) · [>] in progress (orange) · [?] waits for the
human (yellow, needs a `?` line) · [~] done, no evidence (blue) · [x] done
WITH evidence (green — a [x] without a `!` line reads as blue, not green).
Indent is 2 spaces per level.

Update this file before you end the turn — an unchanged or malformed ledger
blocks the turn from ending quietly.
"""


def _stamp_path(md_path: Path) -> Path:
    return md_path.with_suffix(".stamp")


def _title_from_prompt(prompt: str) -> str:
    first_line = (prompt or "").strip().splitlines()[0] if prompt.strip() else "Session"
    return first_line[:TITLE_MAX_CHARS].strip() or "Session"


def _read_stdin_json() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        return {}


def cmd_prompt(payload: dict) -> int:
    session_id = str(payload.get("session_id") or "unknown")
    cwd = str(payload.get("cwd") or os.getcwd())
    prompt = str(payload.get("prompt") or "")

    directory = sessions_dir()
    directory.mkdir(parents=True, exist_ok=True)
    md_path = directory / f"{session_id}.md"

    if not md_path.exists():
        title = _title_from_prompt(prompt)
        md_path.write_text(f"# {title}\nproject: {cwd}\n", encoding="utf-8")

    _stamp_path(md_path).write_text(str(time.time()), encoding="utf-8")

    try:
        current = md_path.read_text(encoding="utf-8")
    except OSError:
        current = ""
    print(GRAMMAR.format(path=md_path))
    print("--- current ledger ---")
    print(current)
    return 0


def _grammar_ok(text: str) -> bool:
    """Whether every task line and every annotation line in `text` matches
    the frozen grammar — the same forgiving read `session_ledger.parse` uses
    would happily skip a bad line, which is exactly what this check exists
    to catch: a `[?]` task with no `?` line, or a checkbox line malformed
    badly enough that no state can be read from it. A LINE outside the
    grammar entirely (plain prose, blank lines, the title/project header) is
    not an error — only a line that LOOKS like a task or an annotation but
    breaks the state rule is."""
    stack_indent: list[int] = []
    pending_question: list[bool] = []  # per open [?] task: has it seen a `?` line?
    for raw_line in text.splitlines():
        m = _TASK_RE.match(raw_line)
        if m:
            indent, state, _rest = m.groups()
            level = len(indent)
            while stack_indent and stack_indent[-1] >= level:
                stack_indent.pop()
                pending_question.pop()
            stack_indent.append(level)
            pending_question.append(state == "?")
            continue
        m = _ANNOTATION_RE.match(raw_line)
        if m and stack_indent:
            indent, kind, _text = m.groups()
            if len(indent) == stack_indent[-1] + 2 and kind == "?":
                pending_question[-1] = False
    return not any(pending_question)


def cmd_stop(payload: dict) -> int:
    if payload.get("stop_hook_active"):
        return 0  # guard against an infinite block loop — Claude Code's own rule

    session_id = str(payload.get("session_id") or "unknown")
    directory = sessions_dir()
    md_path = directory / f"{session_id}.md"
    stamp_path = _stamp_path(md_path)

    if not md_path.exists():
        return 0  # never touched by `prompt` (e.g. a hook installed mid-session)

    try:
        md_mtime = md_path.stat().st_mtime
    except OSError:
        return 0
    try:
        stamp_mtime = stamp_path.stat().st_mtime
    except OSError:
        stamp_mtime = 0.0

    reason = None
    if md_mtime <= stamp_mtime:
        reason = ("The session ledger was not updated this turn. Update "
                   f"{md_path} before ending the turn.")
    else:
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if not _grammar_ok(text):
            reason = ("The session ledger has a task marked [?] with no `?` "
                       f"question line. Fix {md_path} before ending the turn.")

    if reason:
        print(json.dumps({"decision": "block", "reason": reason}))
    return 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    payload = _read_stdin_json()
    if mode == "prompt":
        return cmd_prompt(payload)
    if mode == "stop":
        return cmd_stop(payload)
    print(f"ledger_hook: unknown mode {mode!r} (expected prompt|stop)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
