# Notify — Flow

**About:** [description](../__about/notify.md)

## The whole path, PC to pocket

```
an agent finishes
      │
      ▼
Claude Code fires its `Stop` hook
      │  stdin: {session_id, cwd, transcript_path, …}
      ▼
setup/agent_hook.py
      ├─ agent name: $CLAUDE_AGENT_NAME → payload name → "<project> · <sid[:6]>"
      ├─ token  ← %LOCALAPPDATA%/RemoteUser/token.txt  (dev: ./logs/token.txt)
      ├─ port   ← the same folder's settings.json      (default 8777)
      └─ POST http://127.0.0.1:<port>/notify?token=…
             {"agent": "Remote User · 3f9c1a", "event": "finished", "text": ""}
      │
      ▼
server/notify.py  ── token wrong ─▶ 403, no body
      ├─ clean()   every field trimmed and capped
      ├─ compose() "Remote User · 3f9c1a finished"
      ├─ no phone connected ─▶ {"ok": false, "reason": "no phone connected"}
      └─ ws.send_text({"type": "notify", agent, event, title, text, speak})
      │
      ▼
client/connection.js  ── msg.type == "notify" ─▶ handleNotify(msg)
      │
      ▼
client/notify.js — three carriers, each covering what the others cannot
      ├─ Android.notify(title, text, TAG = agent)   the app may be backgrounded
      │      └─ Notifier.kt → NotificationCompat, heads-up channel, id per tag
      ├─ Android.speak("<title>. <text>")           his eyes are on the PC
      │      └─ Notifier.kt → TextToSpeech, queued until the engine is ready
      └─ showToast(...) + optional tone             only while the page is visible
```

## Why the TAG is the agent's name

```
tag = "Remote User · 3f9c1a"      tag = "ML · 77bb02"
  ├─ turn 1 finished  ─▶ line A     ├─ turn 1 finished ─▶ line B
  └─ turn 2 finished  ─▶ line A     └─ turn 2 finished ─▶ line B
        (replaced, not stacked)           (its own line, never merged)
```

One line per agent, always current — which is the whole point of naming them.
`Notifier.idFor(tag)` hashes the tag into a stable notification id, so the
grouping survives an app restart without keeping a table.

## Failure paths (none of them silent, none of them fatal)

```
no token file            → hook prints to stderr, turn is NOT failed
server not running       → hook prints to stderr, turn is NOT failed
no phone connected       → {"ok": false, "reason": …}; nothing queued
socket dies mid-send     → same answer, warning in the server log
POST_NOTIFICATIONS denied→ Notifier logs it; speech + toast still deliver,
                           and the page's __notifyDenied() hook is called
TextToSpeech unavailable → queued text dropped once, warning in logcat
tone throws              → client_log line, notification unaffected
```
