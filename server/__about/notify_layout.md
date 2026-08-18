# Notify Layout

**Script:** [Notify Layout (script)](../notify_layout.py)

## Purpose

WHERE a notice happened: the layout showing the conversation an agent just
finished in, so a tap on the banner lands there. Split out of
[Notify](notify.md) on 2026-08-18 (THE STRUCTURE LAW).

Nothing is inferred here. The finishing agent sends its own `cwd`, every layout
can be asked which project its windows really belong to (live), and matching
those two is the whole feature - no name-guessing, no stored answer that could
go stale between the notice and the tap.

## Connections

### Uses
- `window_manager` - the same live-title read `layout_state` already uses, so
  there is no second copy of how a member's title is read
- the live `LayoutRegistry`, handed over by `set_layouts()`

### Used by
- [Notify](notify.md) - `layout_of(project, title)` at SEND time, off-thread
- [Session Ledger](session_ledger.md) - the same folder-basename rule, named

## Functions

- `set_layouts(layouts)`: the live registry, or None (the feature is then
  absent rather than wrong)
- `_vscode_conversation_part(title)` / `_title_matches(conversation, window)`:
  the title rule - VS Code's own tail stripped, containment rather than equality
- `_layout_by_title(conversation)`: the title match across live layouts
- `layout_of(project, title="")`: the answer the notice carries, title first
  and project folder second

## Where the tap leads (owner 2026-08-08, task 110)

*"da klikom na notifikaciju nas odvede do tog layouta … gde je zavrsio taj
sabagent ili glavni agent."* A notice that names an agent but leaves him to
find the window is half the job — he has to step the layout bar looking for
it.

Nothing here is inferred. The finishing agent reports its own `cwd`
(`setup/agent_hook.py` → `agent_project`), and every layout can be asked which
project its windows really belong to (`window_manager.Layout.project`).
`layout_of(project, title)` matches the two and returns `{index, name}`, which
rides the notice as `layout`.

### The conversation TITLE, not just the project (owner ruling 2026-08-13)

*"da notifikacije bira layout u cijem se kreirao"* — the notice must land in
the layout the conversation was really created in. His report: with several
windows of ONE project spread across layouts, the tap always took him to the
⭐ PARENT layout instead of the window the agent actually finished in. The ⭐
was never involved — `layout_of` had no tie-break at all, and simply returned
the FIRST layout in list order whose project matched; the parent happens to
sit at the lowest index because it exists before anything is torn off it.

The hook already reads the conversation's own title off the transcript's
`ai-title` record to NAME the agent (task 198, `agent_hook.transcript_title`).
`agent_hook.send()` now rides that SAME string a second time, unabbreviated,
as its own `title` field — separate from `agent`, which may be the same title
already cut to 60 characters for the banner, or, when no title exists yet,
something else entirely (an explicit name, a project·session fallback) that
names no window at all.

`layout_of` tries the title FIRST: `_layout_by_title` walks every layout's
live member titles (the same `wm._title(h) for h in lay.members` reading
`layout_state` already sends the phone) and looks for the one that is really
this conversation. A VS Code window's title is the conversation title PLUS
VS Code's own furniture (`" - <folder> - Visual Studio Code[ tail]"`), and
VS Code elides a title too long for its tab with a trailing "…" — so the
comparison (`_title_matches`) strips the tail, then requires either an exact
match or, when the window's own copy ends in that ellipsis, a strict
`startswith` (the window's copy is a truncated PREFIX of the real title,
never a fuzzy neighbour of it — two different elided titles must never
collide). Only when nothing matches confidently does it fall through to
today's project-folder search — the loop this feature had all along, and
exactly what an OLDER hook (no `title` field, so `layout_of` receives `""`)
still gets, unchanged.

Three details, each of which would be a bug without it:

- It **prunes first**, because the index it returns is the one the PHONE is
  holding, and `layout_state` numbers its list after the same prune. One dead
  layout still in the list and the tap lands one window off.
- It sends the **name beside the index**, so the phone can check the index
  still points at what we meant. A layout removed between the notice and the
  thumb slides every higher index down.
- The field is **absent** whenever that project is on no layout. A tap that
  cannot land must not be offered.

Resolved at SEND time, not at tap time: this is the one moment the agent told
us its project, and it costs one cheap Win32 read per layout, off the loop.

### Task 236 — his THIRD report, and the two halves that made it possible

*"still takes me to the previously open layout."* Two rounds closed this with
green gates. Both halves are fixed here and in `client/notify.js`.

**A miss was SILENT.** Only the SUCCESS path wrote a log line, so a notice
that shipped with no `layout` field looked in his log exactly like one that
carried it — there was no way to tell which half had failed, and the app was
the last to know. `layout_of` now logs at **INFO** on every miss, naming the
project it looked for and every project each live layout really holds
(`Layout.projects()`).

**`Layout.project()` could not reach the agent's window.** It asked
`members[0]` and the window THAT member was torn out of, and nothing else. His
Claude layout is a GRID: the agent's window is as often cell 2 as cell 0, and a
torn-off Claude tab is titled after the CONVERSATION — never after the folder.
So a match that was structurally impossible reported as an honest "that project
is on no layout". Every member is asked now, each followed by its own source,
authority-first. The gate builds exactly that layout (a Chrome cell 0, a
torn-off conversation cell 1) instead of stubbing `project()` away, which is
what let the previous rounds pass while the real function could not answer.
