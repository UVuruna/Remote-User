# Ledger Hook

**Script:** [ledger_hook.py](../ledger_hook.py)

## Purpose

The Claude Code hook pair that keeps the session ledger (T111, 2026-08-17 —
see [Session Ledger](../../server/__about/session_ledger.md) for the file
grammar, the states and the phone's own reading of it) in sync with an
agent's turns, without the agent having to remember to touch it by hand:

- **`prompt`** (`UserPromptSubmit`): creates `<session_id>.md` if it does not
  exist yet — title from the first line of the prompt (clamped to 80 chars),
  `project:` from the hook's own `cwd` — stamps the moment with a sidecar
  `<session_id>.stamp`, and prints the grammar plus the ledger's CURRENT
  content to stdout. That text becomes part of the agent's own context for
  the turn — the instruction reaches it with no second channel.
- **`stop`** (`Stop`): refuses to let the turn end silently if the ledger
  file was never touched since the prompt stamp, or was touched but no
  longer parses to valid grammar (a `[?]` task with no `?` line) — printing
  `{"decision": "block", "reason": ...}` is Claude Code's own contract for
  sending a turn back, not this project's invention.

Like [Agent Hook](agent_hook.md) beside it, this script is deliberately
dependency-free and import-free of the rest of the repo: it runs standalone
under WHATEVER Python the hook host has, on a stranger's PC, with nothing on
`sys.path` but the standard library.

## Connections

### Uses
- `%LOCALAPPDATA%/VibeCoder/sessions` (`VIBECODER_SESSIONS_DIR` overrides it —
  used by the gate, never a real install) — the same directory
  `server/session_ledger.py`'s `sessions_dir()` names

### Used by
- Claude Code's `UserPromptSubmit` and `Stop` hook lists, registered by
  [Agent Hook](agent_hook.md)'s `install()` in the same call that wires the
  agent-finished notice

## Functions
- `sessions_dir() -> Path`: the sessions directory, override-aware — the
  same rule `server/session_ledger.py`'s own function follows, duplicated
  because this script may not import it.
- `cmd_prompt(payload) -> int`: creates the ledger file on first touch,
  refreshes the `.stamp` sidecar every call, and prints the grammar plus the
  file's current text to stdout for the agent to read.
- `_grammar_ok(text) -> bool`: whether every task line and annotation line in
  `text` obeys the frozen grammar — specifically, that no `[?]` task is left
  without its own `?` question line. A single-pass walk over an indent
  stack, tracking one pending flag per open task; a line that merely looks
  unlike a task or annotation (plain prose, a blank line, the title/project
  header) is not an error, only a checkbox line that breaks the state rule
  is.
- `cmd_stop(payload) -> int`: blocks the turn (prints the `decision: block`
  JSON) when the `.md` file's mtime is not newer than the `.stamp` file's, or
  when `_grammar_ok` fails on its current text. Guards against an infinite
  block loop via the payload's own `stop_hook_active` flag — Claude Code's
  own rule, not this hook's.

## Design Decisions

- **The grammar is duplicated on purpose, not imported.** `_TASK_RE` and
  `_ANNOTATION_RE` mirror `server/session_ledger.py`'s own patterns exactly —
  a grammar change must be made in both places, and nothing beyond the gate
  reading both currently enforces that (see Honest Limits in
  [Session Ledger](../../server/__about/session_ledger.md)).
- **It never fails the turn it is guarding.** Every early-return path (no
  ledger file yet, an unreadable stamp) exits 0 with nothing printed — a hook
  that raised would turn every agent's turn-end into an exception instead of
  a ledger nudge.
- **The block is a nudge, not a lock.** A determined agent — or a harness
  that ignores hook blocks — can still end the turn with a stale ledger; the
  mechanism only works because Claude Code honors the `decision: block`
  contract.

## Installation

Installed by [Agent Hook](agent_hook.md)'s `install()`, in the same call
that registers the existing `Stop`/`Notification` pair — one Settings
switch, one write to `~/.claude/settings.json`, both hook pairs at once
(`LEDGER_MARKER = "ledger_hook.py"`, `LEDGER_EVENT_MODES`).

The packaged desktop app (`server/notify.py`) copies this script alongside
`agent_hook.py` into `USER_DIR` whenever the notifier switch is turned on or
refreshed, and `setup/build.py` bundles it into the installer's payload gate
the same way it already bundles `agent_hook.py`.
