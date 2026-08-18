# Notice Channel

**Script:** [Notice Channel (script)](../notice_channel.py)
**Flow:** [Notice Channel - Flow](../__flow/notice_channel.md)

## Purpose

HOW a notice reaches the phone - never what it says. Split out of
[Notify](notify.md) on 2026-08-18 (THE STRUCTURE LAW): `notify.py` owns the
notice's fields, its two routes and the wording; this module owns the three
carriers, the per-device waiting channels and the short queue that holds what
neither carrier could take.

It is ONE module on purpose. THREE CARRIERS, EXACTLY ONE PER NOTICE is a rule
about a chain of `return`s inside a single function (`_carry`), and a rule like
that cannot be enforced across module boundaries - splitting the carriers apart
is exactly how "exactly one" would become a promise instead of a structure.

## Connections

### Uses
- `session_log` - the single `notice.<carrier>` use-log record (see below)

### Used by
- [Notify](notify.md) - hands it `active_client` at `register()`, then every
  composed notice through `deliver()`, and serves `wait_for_news()` as the body
  of `GET /notices`
- [Web Layer](web.md) - `send_pending(ws)` once per authenticated page
- [Update Handover](update_handover.md) - `queue()` for the post-restart
  verdict, `deliver()` for "installing now"
- [Layout Popup](layout_popup.md) - `page_socket()`, the one-device slot, for
  the window offer
- [Server Core](server_core.md) - `close_channels()` on every documented exit

## Functions

- `queue(notice)` / `drain(now)`: the short, honest hold - `QUEUE_TTL_S`,
  `QUEUE_MAX`, and the emptying that happens whether or not anything survived
- `device_key(value)`: the device id as we are willing to keep it
- `set_page(active_client)` / `page_socket()`: the web layer's one-device slot,
  handed over whole and read only
- `waiting()` / `waiting_devices()`: whether, and how many
- `deliver(notice)` -> carrier name: the single choke, and the only place the
  use log is written
- `_carry(notice)`: the chain of returns - page, waiting, held
- `wait_for_news(device)`: the endless `GET /notices` body
- `close_channels()`: ends every waiting response NOW, safely from any thread
- `send_pending(ws)`: everything held while the phone was unreachable

## Three carriers, exactly one per notice (owner decree 2026-08-07)

His report: *"notifikacije mi stižu tek kada podignem aplikaciju iako je sve
vreme otvorena u pozadini"*. The cause was structural, not a bug in this file:
every notice rode the **streaming socket**, and that socket is closed on
purpose the moment the page hides (`docs/DECISIONS.md` constraint 8 — the
session lives only while the owner is looking). At the exact moment a notice
mattered there was no channel, so it was queued until he opened the app
himself. The queue had silently become the normal path.

His decision was a small foreground service on the phone holding a **second,
minimal** channel — *"android strana čeka signal, ne prima ništa od
kompjutera, ali ostane u stanju čekanja signala"* — and `deliver()` is the one
function that chooses between them:

| Order | Carrier | When | Result |
|-------|---------|------|--------|
| 1 | **the page** — `active_client["ws"]` | the app is open and he is looking | unchanged behaviour: banner + speech + toast |
| 2 | **the waiting channels** — `GET /notices` | the page is gone, one or more devices are holding the line | banner + speech on EVERY waiting device, from [NoticeService](../../android/__about/NoticeService.md) |
| 3 | **the queue** | neither: app killed, phone off, no network | held, and handed over the moment either channel returns |

**A double notice is impossible by construction**, not by a de-duplication
rule: `deliver()` is a chain of `return`s, so exactly one branch runs. A page
socket that dies between the check and the send is not an error and not a
queue — the phone has just hidden the page, its service is very probably
already waiting, so the notice falls through to carrier 2. Carrier 2 hands the
notice to every waiting DEVICE once (below): "never twice" is a rule about one
device's ear, and the same notice on his tablet and on his phone is the feature.

## One channel per device (task 209, his own log, 2026-08-11)

The waiting channel used to be a single SLOT, mirroring the web layer's
one-device rule — and that mirroring was the mistake. The streaming session
must be one device (two phones driving one mouse is nonsense); WAITING for news
drives nothing. He runs the foreground service on his tablet **and** his phone,
so each attach kicked the other's channel, the kicked one reconnected at once,
and his log carried an attach→kick→retry ping-pong every few seconds,
continuously, since 2026-08-09:

- thousands of log lines a night (192.168.0.30 ↔ .27 on LAN, 100.95.132.34 via
  Tailscale), and both radios woken for nothing;
- and the half he actually felt: a notice reached only whichever device held
  the slot that second, while the other learned about it minutes or hours later
  out of the queue — *"notifications sometimes never arrive"*.

`_waiting` is therefore a dict keyed by a **device id** the shell supplies:

```
GET /notices?token=…&device=<per-install UUID>
```

| Case | What happens |
|------|--------------|
| two devices waiting | the notice goes to both, once each — per-device de-duplication is structural, since a device has exactly one channel |
| a second attach with the SAME id | that device's own older channel is ended (its service restarted); no other device is touched |
| **no `device` parameter** | an APK older than this round: it shares the LEGACY key, so two old shells still fight over one slot — exactly the behaviour they were built against. Nothing about an old phone changes when this PC updates |
| more than `MAX_DEVICES` (8) | the oldest channel gives way, and it is said in the log. Not a policy — a stop against a shell whose id changed on every attach |

`device_key()` trims, caps at 64 and keeps only characters safe to print in a
log line; anything else falls back to the legacy slot.

**The honest limit:** the queue is drained by whichever device attaches while
it is non-empty, and draining is destructive. A notice held while BOTH devices
were unreachable reaches the first one back, not both. That is the pre-existing
behaviour of the last-resort store and it is deliberately unchanged here — the
queue is the path taken when nothing is reachable, and the round's fix is that
it is now almost never taken at all.

**`close_channels()`** (task 234): ends every waiting response NOW, from any
thread — `ServerController.stop()`'s exit funnel calls it because `force_exit`
stops uvicorn from accepting work while an endless generator parked on its
queue is an open connection the shutdown drain still waits on: every Apply &
restart used to stall the full 10 s join and abandon the old thread. It feeds
the SAME `None` sentinel a displaced channel receives, via
`call_soon_threadsafe` on the loop captured at attach time, so each generator
returns through its own normal exit. Gated in `tests/test_notice_channel.py`
(the 234 check, planted-defect proven).

## `GET /notices` — the waiting channel

A response that never ends. The phone opens it once and blocks on a read; the
PC writes to it:

- **one bare newline every `BEAT_S` (60 s)** — the beat. It travels PC → phone
  only, and it buys exactly two things: keeping the router's / carrier's NAT
  mapping for this TCP connection alive (the tightest common idle timeout is
  60 s), and letting either side notice a link that died silently. A write
  that fails is a phone that is gone; the phone reconnects after `BEAT_MISS`
  (3) missed beats. Without it, a dead link would swallow notices while both
  ends believed they were connected.
- **one JSON line per notice** — byte-for-byte the frame the page would have
  received, so the owner cannot tell which carrier brought it.

Plain chunked HTTP rather than a WebSocket, because the Android shell already
speaks `HttpURLConnection` (it probes `/ping` with it): the waiting state costs
the APK no new dependency and no handshake.

## Why a waiting channel can never be mistaken for a present phone

This is the rule, and it is structural:

> **`_page` is written by `register()` and by nothing else in this module.**
> The `/notices` route only ever READS it.

`_wait_for_news()` can reach the notice queue and nothing else. It never
touches the one-device slot, so `stats.clients` stays 0, no traffic session
opens, `presence.watchdog` and `focus_guard.watch` are never armed, and the
layout registry, the capture, the encoder and the injector are not even in
scope. A waiting phone is a phone that is **NOT here** — which is what keeps
the topmost ledger, the presence/away protocol and the layout defence working
exactly as before. Proven by
[tests/test_notice_channel.py](../../tests/___tests.md).

One channel per DEVICE since task 209 (above): a second attach displaces only
the channel of the device it came from.

## One notice, one use-log record (T113, 2026-08-17)

`deliver()` is now a thin wrapper over `_carry()`, which holds the unchanged
three-carrier chain of returns. The wrapper exists for one reason: the use
log's `notice.<carrier>` record is written THERE and nowhere else. A record at
each of `_carry`'s three returns would be three copies of one fact, and three
copies drift — the same rule the carrier chain itself is built on.

The record carries the agent, the event, `waited_s` (measured from the
notice's own `at` stamp) and `waited` — whether it had really been held for a
later connection rather than landing the second it was raised, which is the
exact distinction the phone's own "8 min ago" suffix exists for. A second of
slack keeps an ordinary round trip from being reported as a wait.

Never raises. Gate: `tests/test_log_wiring.py` (0b24/6).
