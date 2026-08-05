# Agent Hook

**Script:** [agent_hook.py](../agent_hook.py)

## Purpose

The `Stop` hook that tells the phone an agent finished (ROADMAP Phase H,
owner 2026-08-05). Claude Code fires it when a turn ends; it works out WHICH
agent that was and POSTs the notice to the Remote User server already running
on this PC, which forwards it to the phone
([Notify](../../server/__about/notify.md)).

## The agent's name

The owner's rule — *"ime agenta je ime sesije u suštini"* — in order:

1. `$CLAUDE_AGENT_NAME`, when the harness sets an explicit one;
2. a name in the hook payload (`agent_name` / `session_name` / `name`);
3. **`<project folder> · <first 6 of the session id>`**, e.g.
   `Remote User · 3f9c1a` — enough to tell two agents in one repo apart at a
   glance, which is what he actually reads on a notification line.

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
- `%LOCALAPPDATA%/RemoteUser/token.txt` (dev: `./logs/token.txt`) — the same
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
