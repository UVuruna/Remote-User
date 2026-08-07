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
      └─ deliver(notice) ── ONE carrier, a chain of returns ───────────┐
      │                                                               │
      ▼                                                               │
client/connection.js  ── msg.type == "notify" ─▶ handleNotify(msg)     │
      │                                                               │
      ▼
client/notify.js — three carriers, each covering what the others cannot
      ├─ Android.notify(title, text, TAG = agent)   the app may be backgrounded
      │      └─ Notifier.kt → NotificationCompat, heads-up channel, id per tag
      ├─ Android.speak("<title>. <text>")           his eyes are on the PC
      │      └─ Notifier.kt → TextToSpeech, queued until the engine is ready
      └─ showToast(...) + optional tone             only while the page is visible
```

## `deliver()` — which carrier, and why never two

The 2026-08-07 decree. The page's socket dies the moment the page hides (the
security rule), so for the case this feature exists for there used to be no
channel at all.

```
        deliver(notice)
              │
   ┌──────────┴───────────┐
   │  _page["ws"]  set?   │   the STREAMING socket — he is looking at the app
   └──────────┬───────────┘
       yes    │    no ────────────────────────┐
        │     │                               │
        ▼     │                               ▼
   ws.send_text(notice)              ┌─────────────────────────┐
        │                            │ _waiting["q"]   set?    │  the phone's
   ┌────┴────┐                       └───────────┬─────────────┘  foreground
   │ RuntimeError — it just hid │        yes     │     no          service
   └────┬────┘                                   │      │
        └────────── fall through ────────────────┘      │
              │                                         ▼
              ▼                                    queue(notice)
   channel.put_nowait(notice)                  30 min / 20 deep, and
              │                                the phone appends
              ▼                                "8 min ago" on arrival
        return "waiting"                       return "held"

   Exactly ONE branch runs. There is no de-duplication rule because
   there is nothing to de-duplicate.
```

## `GET /notices` — the waiting state

```
 phone (NoticeService)                              PC (notify._wait_for_news)
        │                                                    │
        │  GET /notices?token=T   ───────────────────────▶   │  wrong token ▶ 403
        │                                                    │
        │  ◀────────── 200, chunked, never ends ──────────   │
        │                                                    │
        │                                    drain(): whatever was HELD,
        │  ◀────────── {"type":"notify",…}\n ─────────────   oldest first
        │                                                    │
        │          ... nothing at all ...                    │
        │  ◀────────── "\n"  every 60 s ─────────────────    BEAT_S
        │      (NAT stays open; a failed write = phone gone)  │
        │                                                    │
        │  ── never writes a single byte ──────────────▶ ×   the phone WAITS
        │                                                    │
        │  socket dies ───────────────────────────────────▶  finally:
        │                                                    _waiting["q"] = None
```

**What is NOT in that column, and is absent by construction:** the one-device
slot (`_page` is read, never written here), so no `stats.clients`, no traffic
session, no `presence.watchdog`, no `focus_guard.watch`, no layout registry,
no capture, no encoder, no injector. A waiting phone is a phone that is not
here — which is exactly why the topmost ledger and the layout defence keep
working while the owner sits at his own desk.

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
phone truly unreachable  → {"ok": false, "reason": "phone unreachable — held…"}
socket dies mid-send     → warning in the log, falls THROUGH to the waiting
                           channel; only then the queue
notice channel drops     → the phone reconnects (5 s, backing off to 5 min);
                           whatever arrived meanwhile is queued and handed
                           over on its next attach
POST_NOTIFICATIONS denied→ Notifier logs it; speech + toast still deliver,
                           and the page's __notifyDenied() hook is called
TextToSpeech unavailable → queued text dropped once, warning in logcat
tone throws              → client_log line, notification unaffected
```
