# Agents

**Script:** [Agents (script)](../agents.py) ·
**Flow:** [diagram](../__flow/agents.md)

## Purpose

Which agent tools are LIVE on this PC, and in which project — so the phone's
app-aware sets can appear by themselves instead of being ticked by hand.

**Why it exists** (owner, 2026-08-06): the previous round concluded that a
Claude Code conversation inside VS Code *cannot be identified*, and made him
tick a box for it —

> *"ono je od starta bio nakaradan način što ste implementirali da korisnik
> štiklira koji je prozor otvorio, to je idiotizam"*

That conclusion came from ONE source: UI Automation. The window title, the
tab's UIA class, `AutomationId`, `HelpText`, a full walk of the extracted
window's tree — none carry the word "claude", because VS Code hides webview
content from accessibility and Claude Code names its tab after the
CONVERSATION. All of that is still true. **The process table was never looked
at**, and it answers the question outright. A VS Code window title ends in the
project's folder:

```
"Ispravka UI dizajna meni… - Remote User - Visual Studio Code [Administrator]"
                             └── matched against the live session's cwd
```

## The three sources, strongest first (revised 2026-08-07)

The first version rested on ONE measurement — `claude.exe --resume=<uuid>` —
and it was already stale by the time the owner reported the set missing.
Re-probed on his own machine, extension `anthropic.claude-code-2.1.223` runs:

```
claude.exe 15928  parent Code.exe  9268  --output-format stream-json …
claude.exe 38044  parent Code.exe 37624  --output-format stream-json …
claude.exe 40272  parent Code.exe  9268  --claude-in-chrome-mcp
claude.exe 37872  parent Code.exe 37624  --claude-in-chrome-mcp
```

No `--resume` anywhere, and two of the four are not conversations at all.
Resting on one flag was the mistake, not the flag. The sources are now tiered,
and each only fills in what the one above could not name:

1. **`~/.claude/sessions/<pid>.json`** — Claude Code's own record, one file per
   live process, carrying `{pid, sessionId, cwd, procStart, kind, entrypoint}`.
   The project PATH outright: no slug to decode, no transcript to read, no
   freshness to guess. Cross-checked against the process table by PID **and
   process start time**, so a leftover file for a recycled PID can never name a
   project nobody is working in (`procStart` is a FILETIME; WMI reports the
   same instant truncated to microseconds, which is what `PROC_START_TOL`
   absorbs — measured `…595160` vs `…595168`).
2. **`--resume=<uuid>`** on the command line, for a CLI old enough to pass it:
   the id names `~/.claude/projects/<slug>/<id>.jsonl`, whose `cwd` names the
   project.
3. **Recently written transcripts** — and only as many of them as there are
   conversations tiers 1–2 could not name.

Verified on the owner's machine, 2026-08-07: tier 1 alone answered
`{15928: "uvuruna", 38044: "remote user"}`, tier 3 did not run at all, and
`agents_for("… - Remote User - Visual Studio Code [Administrator]")` returned
`["claude"]` while `… - DOMY Watch - …` returned `[]`.

## The honest limits, stated where they cannot be missed

- **Per PROJECT, not per window.** Every VS Code window belongs to the same
  Electron process, so a window handle cannot be tied to one extension host.
  Two windows open on the same folder both count as having the conversation
  when only one may show it. That is the one case this gets wrong, and it is
  a far better trade than asking the user to declare what his own screen
  already shows — the per-layout tick list that used to override this was
  removed on 2026-08-07 for exactly that reason (see window_manager.md).
- **The parent chain counts windows; it cannot name them.** The four
  `claude.exe` above hang off two different extension hosts (9268, 37624), so
  the chain proves HOW MANY VS Code windows run a conversation. It was
  investigated as a possible replacement for the title match on 2026-08-07 and
  it cannot be one: the hosts' full command lines were read and they are
  byte-identical apart from a mojo handle and a trace uuid — no workspace path,
  nothing to join a window to. Windows' own top-level windows all report the
  Electron main PID (2160 on his machine). The evidence is in the module
  docstring; do not re-open this without new evidence.
- **`--claude-in-chrome-mcp` is not a conversation.** It is an MCP helper
  started per extension host. Counting it as a session we failed to name is
  what used to drag tier 3 in on a PC where every conversation was already
  known.
- **The folder name comes from the transcript's `cwd`, never from the slug.**
  The slug flattens both path separators and spaces into dashes, so
  `u--Coding-UVuruna-Applications-Remote-User` cannot be split back into
  "Remote User" — the first version of `folder_of` returned "user" and matched
  nothing at all.
- **Tier 3 is bounded by COUNT, not tightened to seconds.** Recently-written
  transcripts cannot tell a just-closed session from a live one, so the number
  taken is exactly the number of conversations tiers 1–2 could not name: one
  unnamed conversation lights up one project, not every project touched in the
  last half hour. Narrowing the freshness window to seconds instead was
  considered and rejected — it breaks the case that matters most, an IDLE
  conversation with a finished answer on screen and the owner about to
  dictate, where nothing has been written for minutes.

## Connections

### Uses
- Nothing project-internal (leaf module) — the standard library, plus one
  PowerShell call

### Used by
- [Window Manager](window_manager.md) — every `layout_state` carries each
  layout's `agents`
- [Layout API](layout_api.md) — every `layout_offer` entry carries the same,
  so the creation panel can pre-tick before a layout exists
- `client/sets.js` — `appSetMatches()` answers an `agent` set from that list

## Contents

- `AGENTS` — `{agent name: process}`; the name is what an app set claims with
  `"agent": "claude"` in actions.json
- `_processes(exe)` — `(pid, creation FILETIME, command line)` for every
  running exe, via PowerShell: Windows 11 has no `wmic` any more, and reading a
  foreign PEB needs debug rights this app should not take. The creation time is
  what lets a `sessions/<pid>.json` be trusted
- `_is_conversation(cmd)` — a `claude.exe` the owner could be talking to, not
  an MCP helper (`HELPER_FLAGS`)
- `_live_sessions(procs)` — TIER 1: `{pid: project folder}` from
  `~/.claude/sessions/*.json`, keeping only files whose process is still alive
  AND still the process that wrote them
- `_project_of(session_id)` / `folder_of(dir)` — TIER 2: session id → project
  directory → the folder name a window title shows
- `_recent_projects(limit)` — TIER 3: the `limit` most recently written
  projects, newest first, none older than `FRESH_S`
- `live_agents()` — the cached scan, `{agent: {folder names}}`. `CACHE_S` = 2 s:
  short enough that opening a conversation is noticed before the owner reaches
  his phone, long enough that a layout switch never pays for it twice
- `first_folder(titles)` — the first of several titles that NAMES a project
  (owner report 2026-08-08). A window can have more than one title worth
  asking: a VS Code tab torn into its own window may be titled bare `Visual
  Studio Code`, while the window it came out of still carries the folder. The
  caller offers them in order of authority; see
  [Window Manager](window_manager.md) → `Layout.project`
- `agents_in(folder, live=None)` — the answer itself, for a caller that
  already knows the folder. A folder may be remembered; **this may not**
- `title_folder(title)` / `agents_for(title, live=None)` — the window-title
  side of the bridge (`agents_for` = `agents_in(title_folder(title))`).
  **Pass a `live` snapshot whenever you ask about more
  than one window.** Without it every call may reach the 1.85 s PowerShell
  probe the moment the cache lapses, and the callers that ask in a loop are
  async handlers — that time is the whole event loop stopped: no stream, no
  heartbeats. `layout_list` took one snapshot in a thread from 2026-08-07,
  and tests/test_layout_protocol.py counts the probes and fails at two.
