# Notice Channel - Flow

**About:** [description](../__about/notice_channel.md)

The notice itself - how it is built and worded - is
[Notify - Flow](notify.md); this document starts where `deliver()` is called.

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
   ws.send_text(notice)              ┌─────────────────────────────┐
        │                            │ _waiting — any channels?    │  the
   ┌────┴───────────────────────┐    │  {device-id: Queue, …}      │  phones'
   │ RuntimeError — it just hid │    └───────────┬─────────────────┘  services
   └────┬───────────────────────┘        yes     │     no
        └────────── fall through ────────────────┘      │
              │                                         ▼
              ▼                                    queue(notice)
   for channel in channels:                    30 min / 20 deep, and
       channel.put_nowait(notice)              the phone appends
              │   (every DEVICE once)          "8 min ago" on arrival
              ▼                                       │
        return "waiting"                              ▼
                                                return "held"

   Exactly ONE branch runs, and within the waiting branch each DEVICE is
   handed the notice exactly once — a device has one channel, so there is
   still nothing to de-duplicate.
```

## One channel per device (task 209, 2026-08-11)

```
   BEFORE — one slot                    AFTER — one channel per device

   tablet ──attach──▶ [ q ] ◀─kick──    _waiting = {
   phone  ──attach──▶ [ q ] ──kick─▶      "a1b2…" : Queue  ← tablet
        (both retry at once, ~5 s)        "c3d4…" : Queue  ← phone
                                        }
   log: attach → gone → attach → …     an attach replaces ONLY its own key
   a notice reaches ONE of them        a notice reaches BOTH, once each

   no `device` parameter (an older APK) ─▶ key "" — today's single slot,
                                           unchanged, still displaced by a
                                           second id-less attach
```

## `GET /notices` — the waiting state

```
 phone (NoticeService)                              PC (notify._wait_for_news)
        │                                                    │
        │  GET /notices?token=T&device=D ────────────────▶   │  wrong token ▶ 403
        │       (device optional — an older APK sends none
        │        and lands on the LEGACY key, "")             │
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
        │                                                    del _waiting[D]
```

**What is NOT in that column, and is absent by construction:** the one-device
slot (`_page` is read, never written here), so no `stats.clients`, no traffic
session, no `presence.watchdog`, no `focus_guard.watch`, no layout registry,
no capture, no encoder, no injector. A waiting phone is a phone that is not
here — which is exactly why the topmost ledger and the layout defence keep
working while the owner sits at his own desk.

## Failure paths (none of them silent, none of them fatal)

```
no token file            → hook prints to stderr, turn is NOT failed
server not running       → hook prints to stderr, turn is NOT failed
phone truly unreachable  → {"ok": false, "reason": "phone unreachable — held…"}
socket dies mid-send     → warning in the log, falls THROUGH to the waiting
                           channel; only then the queue
notice channel drops     → the phone reconnects (5 s if the link had been
                           speaking; 5→15→45→60 s if it ended without one
                           beat — a kick; ×2 to 5 min if nothing answered at
                           all). Whatever arrived meanwhile is queued only if
                           NO device was waiting, and handed over on the next
                           attach
two devices waiting      → both get the notice, once each (task 209)
an older APK (no device) → the LEGACY key; unchanged behaviour, including
                           being displaced by a second id-less attach
POST_NOTIFICATIONS denied→ Notifier logs it; speech + toast still deliver,
                           and the page's __notifyDenied() hook is called
TextToSpeech unavailable → queued text dropped once, warning in logcat
tone throws              → client_log line, notification unaffected
```
