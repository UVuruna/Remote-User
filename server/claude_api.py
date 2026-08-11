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


async def send_state(ws, layouts, conn: dict) -> None:
    """Answer `claude_state` for the layout the phone is focused on.

    The project comes from the layout itself (`Layout.project` — measured live
    every call, never a name remembered at creation), and the desktop answers
    for no project at all: at the full desktop there is no one conversation the
    panel could be describing, so every live field is null and only `saved`
    stands. Both reads go through a thread — one walks `~/.claude/projects`,
    the other reads a transcript's tail, and this handler runs on the event
    loop that is also carrying the stream."""
    index = conn.get("active")
    layout = (layouts.layouts[index]
              if index is not None and 0 <= index < len(layouts.layouts) else None)
    folder = await asyncio.to_thread(layout.project) if layout is not None else ""
    await ws.send_text(json.dumps(await asyncio.to_thread(agents.claude_state, folder)))
