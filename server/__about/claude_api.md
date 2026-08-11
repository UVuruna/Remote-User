# Claude API

**Script:** [Claude API (script)](../claude_api.py)

## Purpose
The Claude Code half of the phone protocol — two messages, both about the conversation the owner is actually looking at. Split out of [Web Layer](web.md) on 2026-08-11 under THE STRUCTURE LAW: that file stands at the 1,000-line wall (the same wall that produced [Monitor API](monitor_api.md), [Layout API](layout_api.md) and [Layout Registry](layout_registry.md)), and neither of these handlers belongs to any of them.

Only the TRANSPORT lives here — the thread offload, the toast, the frame. The keystrokes stay in [Content](content.md) and the reading of Claude Code's own files stays in [Agents](agents.md), exactly where they were before this module existed.

**Why the two messages arrived together (owner verdict 2026-08-11).** They are the two halves of one complaint. A typed command failed because it went to whatever had the caret inside VS Code — the editor, the terminal, the file tree — instead of the prompt (task 200). And the panels that send those commands claimed a state they had never read: the Model panel marked nothing as current, and Thinking highlighted Medium while the PC was really on Max, because the chip was a per-device memory of what the phone last SENT (task 208).

## Connections

### Uses
- [Content](content.md) — `focus_claude_prompt()`, the palette sequence itself
- [Agents](agents.md) — `claude_state()`, the transcript read
- [Layout API](layout_api.md) — `toast()`, so a refusal reaches the phone as a sentence

### Used by
- [Web Layer](web.md) — `focus_prompt()` in the `paste_text` branch, `send_state()` on `claude_state`

## Functions
- `focus_prompt(ws, injector, guard) -> bool`: True when the caret is in Claude's prompt and the command may be typed. **False means nothing was injected** (or the sequence was abandoned before the Enter that would have run it) and the phone has already been told why — the caller simply skips the paste. Reached only from `paste_text {focus: "claude"}`; without the field the message behaves exactly as it has since 2026-08-05.
- `send_state(ws, layouts, conn)`: answers `claude_state` for the layout the phone is focused on. The project comes from `Layout.project()` — measured live on every call, never a name remembered at creation — and the DESKTOP answers for no project at all: there is no one conversation a panel could be describing there, so every live field is null and only `saved` stands. Both reads go through `asyncio.to_thread`; one walks `~/.claude/projects`, the other reads a transcript's tail, and this handler runs on the loop that is also carrying the stream.

## The wire contract

Client → server:

```json
{"type": "claude_state"}
```

Server → client, one frame per request:

```json
{"type": "claude_state",
 "model":    "fable",              // family, or null
 "model_id": "claude-fable-5",     // the raw id, [1m] and all, or null
 "effort":   "high",               // low | medium | high | max, or null
 "mode":     "plan",               // permissionMode: default | auto | acceptEdits | plan, or null
 "saved":    {"model": "claude-opus-5[1m]", "effort": "medium"}}
```

Three rules the page may rely on:

1. **Every live field is independently nullable.** No project, no transcript, a transcript with no assistant record yet — each answers `null` for what could not be read, and nothing here ever raises. A panel told nothing must show nothing; that is the honest state, and it is why `model` and `model_id` are separate fields rather than one string a page would have to parse.
2. **`saved` is not `active`.** It is the same read [Web Layer](web.md) already ships inside the `actions` frame (`agents.claude_settings()`), reused rather than duplicated — what the NEXT session will start as. The four live fields are what the conversation on his screen is running. The two genuinely differ, and the panel must say which is which.
3. **The frame is pulled, never pushed.** It is answered on request, so a panel opening is what pays for the read; nothing streams it, and nothing on the phone has to be kept in step between requests.

## Notes
`toast()` is borrowed from [Layout API](layout_api.md) rather than re-written: `web.py`'s own `_toast` is private to it, and a second copy of one `json.dumps` is exactly the drift this project splits modules to avoid.
