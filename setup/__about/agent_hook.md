# Agent Hook

**Script:** [agent_hook.py](../agent_hook.py)

## Purpose

The `Stop` hook that tells the phone an agent finished (ROADMAP Phase H,
owner 2026-08-05). Claude Code fires it when a turn ends; it works out WHICH
agent that was and POSTs the notice to the Vibe Coder server already running
on this PC, which forwards it to the phone
([Notify](../../server/__about/notify.md)).

## The agent's name

The owner's rule — *"ime agenta je ime sesije u suštini"* (lang-ok: owner quote) — in order:

1. `$CLAUDE_AGENT_NAME`, when the harness sets an explicit one;
2. a name in the hook payload (`agent_name` / `session_name` / `name`);
3. the conversation's own TITLE, read from its transcript (task 198,
   2026-08-10 — see below);
4. **`<project folder> · <first 6 of the session id>`**, e.g.
   `Vibe Coder · 3f9c1a` — enough to tell two agents in one repo apart at a
   glance, and still what he sees whenever a transcript carries no title yet.

## The name reads like a person, not a hash (task 198, 2026-08-10)

The owner reported that a notification named the agent by a session-id
fragment ("6ffb225") and asked whether it could say WHO and WHAT instead. The
`Stop` payload itself carries no name — but it does carry `transcript_path`,
and the transcript holds both pieces:

- **WHO** — `transcript_title(payload)` reads the conversation's own title.
  Verified against REAL transcripts on this PC before writing the function
  (FIXED = VERIFIED, not assumed): there is no top-level `slug` or `summary`
  field on any sampled transcript (30+, this project's own session history).
  The title lives in a record Claude Code writes as the conversation goes,
  `{"type": "ai-title", "aiTitle": "..."}`, rewritten every so often — the
  LAST such record in the file is therefore the current title. Falls back to
  the old `<project> · <session6>` form when the transcript carries none yet
  (a very young conversation) or is unreadable.
- **WHAT** — `transcript_summary(payload)` takes the first line (clamped to
  150 chars) of the LAST assistant message that actually carries a `text`
  block; an assistant record that ended in a tool call carries no text block
  and is skipped in favour of the real reply before it. A `Stop` fires right
  after that reply, so it is what belongs on the phone (e.g. "Ispravka UI
  dizajna: gates green, release published" instead of "Vibe Coder · 3f9c1a").

**Both read only the TAIL of the file** (`_tail_lines`, `TRANSCRIPT_TAIL_BYTES`
= 256 KB) — a real transcript on this PC ran past 80 MB / 9,000 lines, and
reading it whole on every `Stop` would make the hook the slowest thing in the
turn. Measured on that same 80 MB file: the last `ai-title` record sat at
line 8,944 of 8,956, comfortably inside the tail window. A seek that lands
mid-line drops that one partial line automatically (a truncated JSON string
never parses) — every line after it is clean.

Gate: the transcript-extraction checks in `tests/test_notify.py`, driven
against fake transcript files (title-wins-by-recency, tool-use-only skip,
absent-title fallback, a file far bigger than the tail window, and the tail
seek itself really excluding the front).

## Installation

```
python setup/agent_hook.py --install     # into ~/.claude/settings.json
python setup/agent_hook.py --uninstall
python setup/agent_hook.py --test        # one notice now, no agent needed
```

`--install` is idempotent: an earlier copy of this hook is dropped before the
current one is written, so re-running after a move never leaves two.

## Connections

### Uses
- `%LOCALAPPDATA%/VibeCoder/token.txt` (dev: `./logs/token.txt`) — the same
  pairing token the phone uses
- the same folder's `settings.json` for the port (default 8777)

### Used by
- Claude Code's `Stop` hook list, and any other tool that can run a command on
  completion — a build, a test suite, a render

## Design Decisions

- **Import-free and dependency-free.** It runs from any directory under
  whatever Python the hook host has, with the project nowhere on `sys.path` —
  so it reads the token and port off disk instead of importing `config`.
- **It never fails the turn it reports on.** Every failure path (no token, no
  server, no phone) prints one line to stderr and exits 0. A hook that raised
  would make every agent's last word an exception.
- **Paths are read at call time, not baked in.** A rotated token or a changed
  port keeps working without reinstalling the hook.

## Installed by a switch, not a command (owner 2026-08-06)

`install()` takes `script` and `python` now, and `is_installed()` reports the
current state. Both exist for the desktop app's own switch (ROADMAP H2): the
packaged EXE has no interpreter inside it and its copy of this file is
replaced by every update, so the app copies the script to the user directory
and names a real interpreter. Run from a checkout, the defaults are still
"this file, this python" and `--install` behaves exactly as before.
