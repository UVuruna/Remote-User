# NoticeLink — Flow

**About:** [description](../__about/NoticeLink.md)

## The thread's whole life

```
NoticeService.onCreate
      │
      ▼
  link.start()  ── one daemon thread, "notice-link" ───────────────────┐
      │                                                               │
      ▼                                                               │
  ┌─ loop ────────────────────────────────────────────────────────┐   │
  │                                                               │   │
  │  addresses()  = [ LAN url, Tailscale url ]   (Prefs)          │   │
  │        │                                                      │   │
  │        ├─ for each, in order, until one ACCEPTS ──▶ wait(url) │   │
  │        │                                                      │   │
  │        ▼                                                      │   │
  │   accepted?                                                   │   │
  │     ├─ yes ─▶ backoff = 5 s     (the link merely dropped)     │   │
  │     └─ no  ─▶ backoff ×2, cap 5 min  (nothing answered)       │   │
  │        │                                                      │   │
  │        └──────────── sleep(backoff) ──────────────────────────┘   │
  │                                                                   │
  └── running == false ──▶ return ◀── stop(): disconnect + interrupt ─┘
```

## One attempt — `wait(url)`

```
   http://<host>:<port>/?token=T          the STORED pairing url
              │
              │  host + port + token reused verbatim
              ▼
   GET http://<host>:<port>/notices?token=T
       connectTimeout  8 s
       readTimeout   180 s   =  BEAT_S 60 × BEAT_MISS 3
              │
              ▼
        response code
         ├─ 403 ─────────▶ log, return false   (token rotated — pair again)
         ├─ not 200 ─────▶ log, return false   (captive portal, wrong host)
         └─ 200 ─────────▶ accepted = true
              │
              ▼
        ┌── readLine() ──────────────────────────────────────┐
        │        (the thread is PARKED here, ~all the time)  │
        │                                                    │
        │   ""      the beat, one byte ─▶ ignore, loop       │
        │   "{…}"   a notice          ─▶ onNotice(JSONObject)│
        │   null    the PC ended it   ─▶ break               │
        │   timeout 3 beats missed    ─▶ throw ─▶ reconnect  │
        └────────────────────────────────────────────────────┘
              │
              ▼
        finally: live = null, disconnect(), return accepted
```

## What travels, over a whole idle day

```
   PC  ──── "\n" ────▶  phone      every 60 s     1 byte payload
   PC  ◀─── ACK  ────   phone      (TCP only, no application data)

   PC  ──── {"type":"notify", "agent":…} ─▶ phone    only on real news

   phone ─────────── nothing, ever ──────────▶ PC
```

≈ 1,440 beats ≈ 150 KB of wire traffic per day, no CPU between packets, no
wake lock. Compare with the streaming session this deliberately is NOT: one
H.264 client is measured in megabits per second.

## Where it breaks, and what happens

```
Wi-Fi handover / Doze wakeup   → read throws → reconnect in 5 s
PC asleep or off               → connect fails on both addresses → back off ×2
phone out of the house, no VPN → same, until the 5-minute ceiling
token rotated on the PC        → 403 → back off; re-pairing fixes it
process reclaimed by Android   → START_STICKY restarts the service → start()
phone rebooted                 → NOTHING until the app is opened once
                                 (stated limit — see NoticeService)
```
