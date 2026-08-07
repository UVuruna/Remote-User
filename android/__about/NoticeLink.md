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

## Reconnect policy

`BACKOFF_START_MS` 5 s, doubling to `BACKOFF_MAX_MS` 5 min. The distinction
the loop draws is between *"the link dropped"* (an address accepted us and
then ended — the PC restarted, Wi-Fi moved; reconnect promptly) and *"nothing
answered"* (the phone is out of the house with the tunnel off; back off hard).
The second case is what a background socket actually costs in battery, and a
retry every few seconds all night is the way to get that wrong.

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

### Used by
- [NoticeService](NoticeService.md) — owns one instance for its lifetime

### Speaks to
- [Notify (server)](../../server/__about/notify.md) — `GET /notices`, the
  other half of this contract, including the value of the beat
