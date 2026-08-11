# NoticeLink (Android)

**Script:** [NoticeLink.kt](../app/src/main/java/com/uvuruna/remoteuser/NoticeLink.kt) ·
**Flow:** [diagram](../__flow/NoticeLink.md)

## Purpose

The waiting state, and nothing else (owner decree 2026-08-07):

> *"samo je važno da ta komunikacija koja mora da bude u pozadini bude
> minimalna … android strana čeka signal, ne prima ništa od kompjutera, ali
> ostane u stanju čekanja signala."*

**One thread.** It opens `GET /notices?token=…` on the PC and then BLOCKS in
`readLine()`. It sends nothing, asks for nothing, polls nothing, fetches
nothing, and holds no wake lock.

## What that costs

A blocked read costs no CPU at all — the thread is parked in the kernel until
a packet arrives, and an arriving packet is what wakes the device, which is
the radio's job for every app on the phone.

What comes down the socket, ever:

| | how often | how big |
|---|---|---|
| the PC's beat — a bare newline | every 60 s (`notify.BEAT_S`) | 1 byte of payload; ~100 bytes on the wire once TCP/IP framing and the ACK are counted |
| one JSON line | only when an agent has something to say | ~200 bytes |

So an idle day is roughly **1,440 beats ≈ 150 KB**, and the phone transmits
nothing but TCP acknowledgements. That is the same order as one chat app
sitting idle, and it is the price of the beat, not of the waiting.

## Why the beat exists at all (it is not a poll)

It travels **PC → phone**, which is the whole architecture in one sentence: the
phone waits, the PC speaks. It buys exactly two things:

1. **NAT.** A home router or a carrier NAT drops the mapping for an idle TCP
   connection; the tightest common timeout is 60 s, which is why the beat is
   60 s and not longer.
2. **Death detection.** A quiet socket and a dead socket look identical from
   both ends. A write that fails is a phone that is gone; hearing nothing for
   `BEAT_MISS` (3) beats is a link the phone must rebuild. Without it, a
   silently dead link would swallow notices while both sides believed they
   were connected — the original bug with extra steps.

## Why plain HTTP

This shell already speaks `HttpURLConnection` (it probes `/ping` with it), so
the waiting state costs the APK **no new dependency, no handshake, no library
and no third party** between the owner's PC and the owner's phone. A blocking
`readLine()` on a socket that says nothing is exactly the "state of waiting"
he described.

## Which phone this is (task 209, 2026-08-11)

The request carries `&device=<id>` — `Prefs.deviceId()`, a random UUID minted
on first use and kept in this app's own preferences. The PC keys **one waiting
channel per device** by it.

Why it had to exist: the PC used to keep a single slot, and the owner runs this
service on a tablet AND a phone, so each one's attach kicked the other's and
they ping-ponged every few seconds — all night, since 2026-08-09, in his own
log — while a notice reached only whichever held the slot at that instant.

It identifies an **install**, not a person and not a handset: deliberately not
`ANDROID_ID`, not IMEI, not any hardware id. Those are restricted, they survive
an uninstall, and they would be a real identifier travelling in a query string
for a job a throwaway random number does perfectly. A reinstall mints a new one;
the worst that costs is one stale channel on the PC until its socket dies.

An empty id is simply left off the URL, and a PC that never sees one keeps its
single-slot behaviour — which is exactly what an older PC does anyway.

## Reconnect policy

Three outcomes, not two (`Attempt`), because the old pair called a kick a
success and retried in five seconds — which is what turned one PC's single slot
into a ping-pong between two phones:

| Outcome | What it means | Next attempt |
|---------|---------------|--------------|
| `LIVE` | accepted, and at least one beat or notice arrived before it ended — the PC restarted, Wi-Fi moved | 5 s, and both backoffs reset |
| `SILENT` | accepted with a 200 and then ended **without a single line** — on an older PC that is a kick; it is also a link that died at birth | 5 → 15 → 45 → 60 s (`QUIET_BACKOFF_MAX_MS`): it must grow, or a fight stays a fight, and it must stay short, because his notices ride on it |
| `NONE` | nothing answered: out of the house, tunnel off, PC asleep, or a 403 | 5 s doubling to `BACKOFF_MAX_MS` 5 min — this is the one that must not spin all night, and it is what a background socket actually costs in battery |

Addresses are tried in the same order as the shell's own resolver: LAN first
(lower latency), Tailscale second. Only an exact **200** counts as the PC — a
captive portal answers anything with a login page, the same false positive
that once sent the WebView to a dead address (live failure 2026-07-27).

## Deliberately Android-UI-free

It knows addresses, sockets and lines. What to DO with a notice belongs to
[NoticeService](NoticeService.md).

## Connections

### Uses
- `Prefs.addresses()` — the two stored page URLs; the token rides in the
  query of the stored pairing URL, so the notice channel needs no second secret
- `Prefs.deviceId()` — this install's own id, handed in as a lambda by
  `NoticeService`: this class knows sockets and lines, never storage

### Used by
- [NoticeService](NoticeService.md) — owns one instance for its lifetime

### Speaks to
- [Notify (server)](../../server/__about/notify.md) — `GET /notices`, the
  other half of this contract, including the value of the beat
