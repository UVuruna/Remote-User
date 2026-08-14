# Traffic Battery — Flow

**About:** [description](../__about/traffic_battery.md)

## Where the number comes from — every hop a place it could become a lie

```
THE PHONE (the only component that can measure)
 │  BatteryManager.getIntProperty(...)
 ├─ CAPACITY      → level, only when 0..100        (a refusal reads negative)
 └─ CURRENT_NOW   → Int.MIN_VALUE  → OMITTED       "this device will not say"
                    0              → OMITTED       (every stubbed impl)
                    anything else  → abs(value)    the SIGN is never trusted
    isCharging    → charging                        …the direction comes here
        │
        │  Bridge.batteryStats()  — a NEW method, never more of netStats():
        │  the page is served by the PC, the shell installed separately
        ▼
THE PAGE   client/state.js  phoneBattery()
 ├─ no such method (older APK)      → null
 ├─ drops any property not sent     → nothing is invented back
 └─ NO properties at all            → null, not {}      an empty object would
        │                                               claim a phone answered
        │  rides `hb` (every beat) and `away` (the closing reading)
        │  — no new message type, exactly as `net` does
        ▼
THE METER  server/traffic.py  note_battery()
 ├─ current <= 0 or level outside 0..100  → DROPPED   (a gate on one layer
 │                                                     holds only that layer)
 ├─ level_drop := first(session).level − newest.level
 ├─ avg_ua     := mean of the readings that CARRIED a draw
 └─ set_clients(0)  → battery_first = None, averages cleared
                      a level carried across an absence would report the
                      charge he gave it as a session cost
        │
        ▼
THE WORDS  gui/traffic_battery.py  battery_sentence(battery, clients)
```

## The sentence, and its two silences

```
battery_sentence(battery, clients)
 │
 ├─ battery is None
 │    ├─ clients > 0 → "this device does not report it — some phones will
 │    │                 not say, and an older app version cannot ask."
 │    └─ clients = 0 → "the phone reports its own level and draw while it
 │                      is connected."
 │        two different FACTS, so two different sentences — never a blank,
 │        never a dash, and never "0 mA" (which reads as "costs nothing")
 │
 └─ battery present — each half stated INDEPENDENTLY
      ├─ level      → "62%"          | "does not report its level"
      ├─ drop+span  → "4% used in 1 h with the app running"
      │                (or "no drop yet in …")
      ├─ draw       → "drawing 512 mA now, 480 mA average while connected"
      │             | "this device does not report its draw"   ← named, not
      │                                                          dropped
      └─ charging   → "charging"     changes what every number above MEANS
```
