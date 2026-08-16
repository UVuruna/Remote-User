# Ledger API

**Script:** [Ledger API (script)](../ledger_api.py)

## Purpose
The session-ledger half of the phone protocol (T111, 2026-08-17) — one message, `ledger_state {}`, answering what the FOCUSED layout's project's session ledger says right now. See [Session Ledger](session_ledger.md) for the file grammar, the states and the on-disk contract this module reads.

Same shape as [Claude API](claude_api.md)'s `send_state`, and for the same reason (THE STRUCTURE LAW): the project comes from `Layout.project()`, measured live in a thread, never remembered; the desktop focus answers with an EMPTY ledger, because a bare desktop names no one project. Parsing and file lookup stay in `session_ledger.py` — this module is transport only.

## Connections

### Uses
- [Session Ledger](session_ledger.md) — `ledger_for_project()`, `EMPTY`'s shape mirrors `parse()`'s own

### Used by
- [Web Layer](web.md) — `send_ledger()` on the `ledger_state` message, beside `claude_api.send_state` on `claude_state`

## Functions
- `send_ledger(ws, layouts, conn) -> None`: answers `ledger_state` for the layout the phone is focused on. `conn["active"]` names the focused layout (or nothing, at the desktop); `layout.project()` is read fresh, in a thread, exactly like `claude_api.send_state`'s own read — never a name remembered from an earlier frame. No project, or no ledger matching that project, both answer `EMPTY` rather than an error: a stale layout index or a project with no ledger yet are both the honest "nothing to show" case, not a failure.

## The wire contract

Client → server:

```json
{"type": "ledger_state"}
```

Server → client, one frame per request:

```json
{"type": "ledger_state",
 "session_id": "abc123",
 "updated": 1755417600,          // the ledger file's own mtime, seconds
 "title": "Fix the mouse ghosting",
 "project": "U:\\Coding\\...\\VibeCoder",
 "tasks": [ /* the parsed tree — see session_ledger.md */ ]}
```

`EMPTY` is the same shape with every string blank and `tasks: []` — a panel that reads either shape the same way never has to special-case "no answer yet" against "an empty ledger".

## Notes
`updated` is read straight off the file's `st_mtime`; a race where the file is deleted between the lookup and the stat falls back to `time.time()` rather than failing the whole frame — the ledger the phone was just told about disappearing a moment later is not this module's problem to solve, only not to crash on.
