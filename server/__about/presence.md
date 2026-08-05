# Presence

**Script:** [Presence (script)](../presence.py)

## Purpose
Answer one question, continuously and correctly: **is the owner still working
with us, and whose desk are we on?**

Layout members are forced always-on-top while the phone shows them ([Window
Manager](window_manager.md)), so the server must learn the instant the phone
stops working — otherwise those windows hover over everything for the owner
**at his desk**. A clean socket close cannot carry that news: a locked phone
lets its Wi-Fi sleep and the connection simply goes quiet. So presence is a
POSITIVE signal — the client beats `hb` every 4 s and silence IS the leave —
with a spoken `away` as the fast path when the page knows it is going.

Split out of [Web Layer](web.md) on 2026-08-05 (THE STRUCTURE LAW): one
responsibility, its own rules, its own failure history and its own gate
(`tests/test_presence.py`).

## The failure this module exists to prevent
Reported by the owner **twice**, and mis-diagnosed once before: he locks the
tablet, walks to his PC, and his own Chrome and VSCode are still nailed above
every other window.

The second time, the live server log dated the cause to the second. The page
decided "excursion" from a 90-second timer armed by the last Mic/picker tap,
so locking the tablet six seconds after dictating was announced to the PC as
*"back in a moment"*:

```
18:41:49  Phone: [voice] Voice error 5 (online)      ← he was dictating
18:41:56  Phone announced an excursion — layout held ← he locked the tablet
18:46:56  Phone left work mode — layout members minimized
```

Exactly 300 s — the old `EXCURSION_MAX_S`. The log shows the same gap twice
(18:43:11 → 18:48:11). He was at his desk for all five minutes of it.

## The three rules, and why none of them may be the only one
1. **The reason is never guessed.** `away` carries a `reason` the phone
   actually knows — the Android shell reads the screen/keyguard state and
   knows whether *it* launched a picker (`Android.hideReason()`). `is_excursion`
   treats everything it does not recognise as a LEAVE, because the safe
   default is the owner's own desk. A `reason` present in the message always
   beats a legacy `excursion: true` flag riding along with it.
2. **The hold is short.** `EXCURSION_MAX_S` is 45 s, not 300 — it now only has
   to outlast a real gallery pick.
3. **THE DESK WINS.** Real local input on this PC while the phone is away means
   the owner is sitting *here*, whatever the phone claimed on its way out, and
   the hold ends at once. Windows counts injected input in the same last-input
   clock, which is exactly why this is consulted only while the phone is gone
   and we are injecting nothing.

## Interface
| Name | Meaning |
|------|---------|
| `HEARTBEAT_TIMEOUT_S` = 12 | three missed 4-second beats and the session ends |
| `EXCURSION_MAX_S` = 45 | the far end of our patience with an announced excursion |
| `WATCHDOG_POLL_S` = 2 | how often the watchdog looks |
| `DESK_INPUT_GRACE_MS` = 1500 | covers the last event WE injected before the phone went quiet |
| `desk_baseline()` / `owner_at_the_desk(baseline)` | the desk rule, in two calls |
| `leave_session(layouts, conn)` | minimize every member **and** empty the topmost ledger; idempotent |
| `excursion_backstop(layouts, active_client)` | the hold, ended early by the phone returning or by the owner's own keyboard |
| `watchdog(ws, layouts, conn, active_client)` | the per-connection poller; only ever ends the session it belongs to |
| `is_excursion(msg)` | the `away` vocabulary, with the legacy flag honoured |

`leave_session` calls `clear_topmost()` **after** the minimize, and that is not
redundant: it walks the ledger, so a window that fell out of its layout
meanwhile (closed, cloaked, extracted as a tab) is released too — the one no
member list can still name is exactly the one that used to stay stranded.

## Connections
### Uses
- [Window Manager](window_manager.md) — `minimize_members`, `clear_topmost`
- [Input Injector](input_injector.md) — `last_input_tick`, `tick_now`

### Used by
- [Web Layer](web.md) — starts the watchdog per connection, arms the backstop
  on an announced excursion, and routes `away` through `is_excursion`

### Flow
- [Presence — Flow](../__flow/presence.md)
