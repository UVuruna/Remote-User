# Session Ledger (T111, 2026-08-17)

A plain-Markdown to-do list an agent keeps beside its project, and the phone
reads through `ledger_state {}`. Frozen contract: `.claude/ledger-plan.md`.

## File

`<config.USER_DIR>/sessions/<session_id>.md` — one file per Claude Code
session, created by the `UserPromptSubmit` hook (`setup/ledger_hook.py`).

```
# <MAIN TITLE>
project: <absolute cwd>
- [ ] T1 Task title @fable
  > free description (optional)
  ? question for the human (required when state is [?])
  ! evidence: test/log/screenshot/commit (required for [x])
  - [x] T1a subtask title @sonnet
    ! tests/test_x.py 12/12
```

Indent is 2 spaces per nesting level, both for a child task and for that
task's own `>`/`?`/`!` lines.

## States and colors

| Mark | Color  | Meaning |
|------|--------|---------|
| `[ ]` | red    | not started |
| `[>]` | orange | in progress |
| `[?]` | yellow | waits for the human — needs a `?` line |
| `[~]` | blue   | done, no evidence |
| `[x]` | green  | done WITH `!` evidence |

**Downgrade rule**: `[x]` with no `!` evidence line reads as `[~]` blue, not
green — a claim of done the ledger cannot back is never shown as backed.
`[?]` with no `?` line stays yellow regardless (the plan's own wording: "a
`[?]` without `?` still yellow but question=\"\"") — a missing question is a
sloppy ledger, not a resolved one; the Stop hook is what actually refuses to
let that turn end quietly (see below).

## Server (piece A)

- `server/session_ledger.py` — pure parser + file lookup:
  - `parse(text: str) -> dict` — `{title, project, tasks: [...]}`, each task
    `{id, title, model, state, desc, question, evidence, children}`. Never
    raises; an unrecognized line is skipped.
  - `sessions_dir() -> Path` — `config.USER_DIR / "sessions"`.
  - `ledger_for_project(folder: str) -> tuple[session_id, Path, dict] | None`
    — the newest ledger whose `project:` line matches `folder`
    (case-insensitive, separator-normalized — Windows path comparison).
- `server/ledger_api.py` — `async def send_ledger(ws, layouts, conn) -> None`,
  modeled exactly on `claude_api.send_state`: the focused layout's
  `Layout.project()` (measured live, in a thread) decides which project's
  ledger answers; the desktop focus (or no match) sends an empty
  `ledger_state` frame.
- `server/web.py` — `elif kind == "ledger_state": await
  ledger_api.send_ledger(ws, layouts, conn)`, beside `claude_state`.

## Hook (piece B)

`setup/ledger_hook.py` — self-contained stdlib script, no repo imports (it
runs under the USER's python, exactly like `setup/agent_hook.py` beside it).

- `prompt` mode (`UserPromptSubmit`): creates `<session_id>.md` if absent
  (title = first line of the prompt, ≤80 chars; `project:` = the hook's own
  `cwd`), writes/refreshes a `<session_id>.stamp` sidecar with the current
  time, and prints the grammar plus the ledger's current content to stdout —
  that becomes part of the agent's own context for the turn.
- `stop` mode (`Stop`): if the `.md` file's mtime is not newer than the
  `.stamp` file's, or the ledger no longer parses to valid grammar (a `[?]`
  task with no `?` line), prints `{"decision": "block", "reason": "..."}` and
  exits 0 — Claude Code's own contract for sending a turn back. Guards
  against an infinite block loop via the payload's `stop_hook_active` flag.

Ledger directory: `%LOCALAPPDATA%/VibeCoder/sessions`, overridable with the
`VIBECODER_SESSIONS_DIR` environment variable (used by the gate, never by a
real install).

### Installation

`setup/agent_hook.py`'s `install()` registers BOTH hooks in one call: the
existing `Stop`/`Notification` pair for the agent-finished notice, and the
new `UserPromptSubmit`/`Stop` pair for the ledger (`LEDGER_MARKER =
"ledger_hook.py"`, `LEDGER_EVENT_MODES`). One Settings switch, one write to
`~/.claude/settings.json`.

The packaged desktop app (`server/notify.py`) copies `ledger_hook.py`
alongside `agent_hook.py` into `USER_DIR` whenever the notifier switch is
turned on or refreshed (`_ledger_hook_source`, `set_agent_hook`,
`refresh_agent_hook`), and `setup/build.py` bundles `setup/ledger_hook.py`
into the installer's payload gate the same way it already bundles
`agent_hook.py`.

## Honest limits

- The ledger and the hook script duplicate the grammar's regex on purpose —
  `ledger_hook.py` must run with nothing on `sys.path` but the standard
  library, so it cannot import `server/session_ledger.py`. A grammar change
  must be made in both places; nothing currently enforces that beyond the
  gate reading both.
- `ledger_for_project` matches on the `project:` line's TEXT, not a live
  process check — a stale ledger from a folder that no longer exists still
  "matches" if a layout's window happens to report that same folder name.
- The Stop hook's block is a nudge, not a lock: a determined agent (or one
  running under a harness that ignores hook blocks) can still end the turn
  with a stale ledger. The mechanism only works because Claude Code honors
  it.
