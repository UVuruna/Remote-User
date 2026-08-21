"""The session-ledger half of the protocol (T111, 2026-08-17) — one message,
`ledger_state {}`, answering what the FOCUSED layout's project's ledger says
right now.

Same shape as `claude_api.send_state` and for the same reason (THE STRUCTURE
LAW): the project comes from `Layout.project()`, measured live in a thread,
never remembered; the desktop answers with an empty ledger because there is
no one project a bare desktop focus could name. The parsing and file lookup
belong to [session_ledger](session_ledger.py) — this module is transport
only, exactly as `claude_api.py`'s own docstring describes its job.
"""

import asyncio
import json
import time

import session_ledger

EMPTY = {
    "type": "ledger_state", "session_id": "", "updated": 0,
    "title": "", "project": "", "category": "", "tasks": [],
}


async def send_ledger(ws, layouts, conn: dict) -> None:
    """Answer `ledger_state` for the layout the phone is focused on."""
    index = conn.get("active")
    layout = (layouts.layouts[index]
              if index is not None and 0 <= index < len(layouts.layouts) else None)
    folder = await asyncio.to_thread(layout.project) if layout is not None else ""
    found = (await asyncio.to_thread(session_ledger.ledger_for_project, folder)
             if folder else None)
    if found is None:
        await ws.send_text(json.dumps(EMPTY))
        return
    session_id, path, parsed = found
    try:
        updated = int(path.stat().st_mtime)
    except OSError:
        updated = int(time.time())
    await ws.send_text(json.dumps({
        "type": "ledger_state", "session_id": session_id, "updated": updated,
        "title": parsed["title"], "project": parsed["project"],
        "category": parsed["category"], "tasks": parsed["tasks"],
    }))
