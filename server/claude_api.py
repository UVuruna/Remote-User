"""THE CLAUDE CODE HALF OF THE PROTOCOL — two messages, both about the
conversation the owner is actually looking at.

Why its own module and not two more branches in `web.py` (THE STRUCTURE LAW):
`web.py` stands at the 1,000-line wall — `monitor_api.py`, `layout_api.py` and
`layout_registry.py` were each carved out of it for the same reason — and these
two handlers share a subject that none of those own. What lives here is the
TRANSPORT only: the thread offload, the toast, the frame. The keystrokes belong
to [content](content.py) and the reading of Claude Code's own files belongs to
[agents](agents.py), exactly as they did before this module existed.

  * `paste_text {focus: "claude"}` — put the caret in the Claude prompt before
    the command is typed (owner order 2026-08-11, task 200). A refusal costs
    zero injections and says so on the phone.
  * `claude_state {}` → `claude_state {model, model_id, effort, mode, saved}` —
    what the FOCUSED layout's conversation is running now, so the phone's Model
    and Thinking panels can stop presenting a per-device memory as live state
    (owner report 2026-08-11, task 208).
"""

import asyncio
import json

import agents
import content
import layout_api
import window_manager as wm


async def focus_prompt(ws, injector, guard) -> bool:
    """True when the caret is in Claude's prompt and the command may be typed.

    False means NOTHING was injected (or the sequence was abandoned before the
    Enter that would run it) and the phone has already been told why — the
    caller must simply skip the paste."""
    problem = await asyncio.to_thread(content.focus_claude_prompt, injector, guard)
    if problem:
        await layout_api.toast(ws, problem)
        return False
    return True


def _active_tab_title(layout, folder: str) -> str:
    """The raw window title that named `folder` for this layout — the SAME
    source and order `Layout.project()` already uses (each member, then the
    window it was torn out of), kept here rather than taught to `Layout`
    itself: this is the one extra read the active-tab lookup needs, and this
    module already owns the one Claude Code question `Layout` does not
    (module docstring). Read fresh, never remembered — a stale title would
    defeat the whole point of asking WHICH tab is active right now."""
    if not folder:
        return ""
    for hwnd in getattr(layout, "members", ()):
        for h in (hwnd, layout.sources.get(hwnd, 0)):
            if h and wm.is_alive(h):
                title = wm._title(h)
                if agents.title_folder(title) == folder:
                    return agents.tab_title_of(title)
    return ""


async def send_state(ws, layouts, conn: dict) -> None:
    """Answer `claude_state` for the layout the phone is focused on.

    The project comes from the layout itself (`Layout.project` — measured live
    every call, never a name remembered at creation), and the desktop answers
    for no project at all: at the full desktop there is no one conversation the
    panel could be describing, so every live field is null and only `saved`
    stands. The ACTIVE TAB's own title (`_active_tab_title`) rides along too
    (owner bug, 2026-08-15: two Claude Code tabs on one project, the phone
    showed whichever one wrote its transcript last rather than the one on
    screen) — `agents.claude_state` uses it to pick that tab's own session
    when VS Code's own memento can name it, and falls back to the old
    newest-transcript rule otherwise. Both reads go through a thread — one
    walks `~/.claude/projects`, the other reads a transcript's tail, and this
    handler runs on the event loop that is also carrying the stream."""
    index = conn.get("active")
    layout = (layouts.layouts[index]
              if index is not None and 0 <= index < len(layouts.layouts) else None)
    folder = await asyncio.to_thread(layout.project) if layout is not None else ""
    tab_title = _active_tab_title(layout, folder) if layout is not None else ""
    await ws.send_text(json.dumps(
        await asyncio.to_thread(agents.claude_state, folder, tab_title)))
