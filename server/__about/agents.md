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
"Ispravka UI dizajna meni… - Vibe Coder - Visual Studio Code [Administrator]"
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
`agents_for("… - Vibe Coder - Visual Studio Code [Administrator]")` returned
`["claude"]` while `… - Watch Academy - …` returned `[]`.

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
  `u--Coding-UVuruna-Applications-VibeCoder` cannot be split back into
  "Vibe Coder" — the first version of `folder_of` returned "user" and matched
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

## What the conversation is running NOW (task 208, 2026-08-11)

`claude_settings()` answers *what the next session will start as*. It is
deliberately called **saved** and never *active* — a project or local
`.claude/settings.json`, `CLAUDE_CODE_EFFORT_LEVEL` / `ANTHROPIC_MODEL`, a
session-only switch in the picker and a resumed transcript all outrank it.

**Both halves of the frame are normalised through `model_family()`**
(independent grader, 2026-08-11). The live half always was; the saved half was
handed to the phone RAW, and the owner's own `settings.json` holds
`claude-fable-5[1m]` — a full id, which equals none of the five aliases the
phone's picker offers (`client/claude-state.js` → `CLAUDE_MODELS`). So on HIS
machine the "saved" mark could never light a row and the chip printed the raw
id back at him: a card whose only job is to say which model is chosen, unable
to say which model is chosen. `claude_settings()` now answers
`{model, model_family, effort}` — the raw id stays because it is a fact and a
panel may need to print it, and `model_family` is the field anything MATCHING
must read. A settings file naming something we do not know, or the alias
`default` (which names no family on purpose — it resolves to whatever the
account picks), leaves `model_family` OFF the frame entirely rather than
guessing a near one: the same rule `model_family()` itself obeys, and the
reason it never answers the closest family.

His report proved that the distinction is not academic: the Thinking panel
highlighted Medium while his PC was really on Max, because `/model` and
`/effort` apply to the **running session only** and no file on disk records
that. So the live answer is read from the transcript Claude Code writes as it
goes — `~/.claude/projects/<slug>/<session>.jsonl`, the same file tiers 2 and
3 above already resolve.

**The shape of that file was MEASURED here on 2026-08-11**, on real
transcripts, because task 208's own note ("effort has no such trail") was
FALSE and a fix built on it would have shipped a panel that could never say
anything:

- every `assistant` record carries BOTH `message.model` and a top-level
  `effort` — tool-call records included, and in a working session those are
  most of them. There is nothing to skip and nothing to search past;
- `permissionMode` rides only SOME `user` records — the real prompts. A tool
  RESULT is a `user` record too and carries none, so "the last user record" is
  the wrong rule and answers null nearly every time. The rule is **the last
  record that HAS the field**;
- a dedicated `{"type": "mode", "mode": …}` record exists, and read `normal` in
  all 373 of them across every project on this PC. It cannot currently
  distinguish plan mode from anything else and is deliberately NOT the source.

### Functions
- `model_family(model_id)` — `claude-opus-5[1m]` → `opus`. The `[1m]` is a
  context-window variant of the same family, stripped for the family and kept
  whole in `model_id`. An id we do not know answers `""`, never the nearest
  match: a panel lighting the wrong row is a lie the owner would act on.
- `newest_transcript(folder)` — the most recently written transcript of the
  project whose own `cwd` ends in `folder`. Matched through `folder_of()` and
  never through the slug's name (the slug flattens separators AND spaces into
  dashes — the bug that once made `folder_of` return "user").
- `_tail_records(path)` — the last `TAIL_BYTES` (256 KB) parsed, oldest first.
  A working transcript reaches tens of megabytes and the answer is always in
  its last few records. The first line of the slice is dropped whenever we
  seeked (it is a fragment of the record that straddled the cut), and anything
  that will not parse is skipped in silence — a transcript being APPENDED to
  while we read it legitimately ends mid-line.
- `claude_state(folder)` — the frame itself, `{type, model, model_id, effort,
  mode, saved}`. Every live field is independently nullable and **nothing here
  raises**: no project, no transcript, no assistant record yet, a half-written
  line — each simply answers `None` for what it could not read. A panel told
  nothing shows nothing, which is the honest state; an exception would take the
  whole message down instead. The exact wire contract lives in
  [Claude API](claude_api.md) → The wire contract.

### Gate
[`tests/test_claude_state.py`](../../tests/test_claude_state.py) — fail-closed
in `build.py` (0ac/6). It drives the real reader over transcripts built like
his, so a later round cannot quietly go back to a rule that reads nothing.
Since 2026-08-11 it also drives the SAVED half over the id shape his own file
carries (`check_a_saved_1m_id_lights_its_family_row`) and reads the page's own
matching code (`check_the_phone_matches_the_saved_row_by_family`) — a server
field nothing on the phone reads is a feature that does not exist, which is
the actions.json lesson of 2026-08-07.
