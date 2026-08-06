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
at**, and it answers the question outright:

```
claude.exe  PID 10016  parent Code.exe 37624  --resume=0eb7cbe2-…
claude.exe  PID 33104  parent Code.exe  9268  --resume=ed816316-…
```

Every running conversation is a `claude.exe` carrying its SESSION ID; a session
id is a file (`~/.claude/projects/<slug>/<id>.jsonl`); that transcript's first
lines carry the project's own `cwd`; and a VS Code window title ends in that
project's folder:

```
"Ispravka UI dizajna meni… - Remote User - Visual Studio Code [Administrator]"
                             └── matched against the live session's cwd
```

Verified on the owner's machine the day it was written: three live projects
(`remote user`, `uvuruna`, `domy watch`) matched his three VS Code titles, and
`Some Folder - Notepad` matched nothing.

## The honest limits, stated where they cannot be missed

- **Per PROJECT, not per window.** Every VS Code window belongs to the same
  Electron process, so a window handle cannot be tied to one extension host.
  Two windows open on the same folder both count as having the conversation
  when only one may show it. The owner's own per-layout ticks still win over
  detection (`lay.app_sets` in client/sets.js), so he can always correct it.
- **The folder name comes from the transcript's `cwd`, never from the slug.**
  The slug flattens both path separators and spaces into dashes, so
  `u--Coding-UVuruna-Applications-Remote-User` cannot be split back into
  "Remote User" — the first version of `folder_of` returned "user" and matched
  nothing at all.
- **A conversation with no `--resume`** (a brand new one) cannot be mapped from
  its command line, so recently-written transcripts fill that gap. Weaker: it
  cannot tell a just-closed session from a live one, which is why it is used
  only for what the session ids could not answer.

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
- `_command_lines(exe)` — every command line of a running exe, via PowerShell:
  Windows 11 has no `wmic` any more, and reading a foreign PEB needs debug
  rights this app should not take
- `_project_of(session_id)` / `_recent_projects()` / `folder_of(dir)` — session
  id → project directory → the folder name a window title shows
- `live_agents()` — the cached scan, `{agent: {folder names}}`. `CACHE_S` = 2 s:
  short enough that opening a conversation is noticed before the owner reaches
  his phone, long enough that a layout switch never pays for it twice
- `title_folder(title)` / `agents_for(title)` — the window-title side of the
  bridge
