# NoticeService (Android)

**Script:** [NoticeService.kt](../app/src/main/java/com/uvuruna/vibecoder/NoticeService.kt)

## Purpose

The small foreground service the owner asked for on 2026-08-07. It exists so
that **an agent's notice reaches this phone when there is no page** — the app
minimised, closed, or the screen off.

## The failure it fixes

His report: *"notifikacije mi stižu tek kada podignem aplikaciju iako je sve
vreme otvorena u pozadini"*.

It was not a bug in the notice code. Every notice rode the **streaming
socket**, and that socket is closed on purpose the moment the page hides
(project CLAUDE.md constraint 8 — the session lives only while the owner is
looking). At the exact moment a notice mattered there was no channel at all,
so `server/notify.py` queued it until he opened the app himself. The queue was
built for "he was away"; it was never a delivery mechanism, and it had
silently become the normal path.

His decision:

> *"Radimo taj mali servis — samo je važno da ta komunikacija koja mora da bude
> u pozadini bude minimalna … android strana čeka signal, ne prima ništa od
> kompjutera, ali ostane u stanju čekanja signala."*

## What it is NOT

Not a second session. It never loads the page, never opens the stream, never
touches input, and **the PC does not count it as a present phone**: `/notices`
is a route of its own that never enters the one-device slot presence is built
on. The security rule, the presence/away protocol, the topmost ledger and the
layout defence all keep working exactly as before — when the page hides, the
session dies.

## Why a foreground service, and which type

A background thread would be killed within minutes and its socket with it, and
Android would defer its traffic long before that. A foreground service is the
only way to hold a socket open for hours. Android's price is a permanent
notification the user cannot dismiss.

**`foregroundServiceType="connectedDevice"`**, and it is the honest one: this
service exists solely to hold a network connection to ONE specific paired
device — the owner's own PC — which is precisely what that type describes.

- `dataSync` would be the lazy pick and is wrong twice over: nothing is being
  synchronised, and Android 15 **deprecated** it with a six-hour cap that
  would kill this at the end of every working day.
- `specialUse` is the escape hatch for things with no honest type. This one
  has one.

### The type has a price: a companion permission (live failure 2026-08-08)

Since Android 14 the `connectedDevice` type is only granted to a process that
ALSO holds one of `BLUETOOTH_CONNECT` / `BLUETOOTH_ADVERTISE` /
`BLUETOOTH_SCAN` / `CHANGE_NETWORK_STATE` / `CHANGE_WIFI_STATE` /
`CHANGE_WIFI_MULTICAST_STATE` / `NFC` / `TRANSMIT_IR` / `UWB_RANGING` / a USB
grant. v0.0.093 declared the type and none of those, so `startForeground`
threw `SecurityException` — **inside the service's own `onCreate`, which is
not on the caller's stack**: the `try/catch` around `startForegroundService`
in `NoticeService.start` never saw it, and the process died a second after
launch, every launch. The owner's report was the whole app: *"ne može više da
se pokrene aplikacija na telefonu, uopšte ne podigne ništa."*

The manifest now declares **`CHANGE_NETWORK_STATE`** — the honest one of that
list for a service whose entire job is a network connection to one paired
device, and a NORMAL permission, so it is granted at install and the user is
never asked.

And the second tooth, because the first only covers the reason we already
know: `startForeground` is wrapped in `try/catch` in `onCreate`, and a refusal
is logged, sets `running = false` and calls `stopSelf()` (`onStartCommand`
refuses to start the link when `running` is false). **The channel may fail;
the app may never die with it** — the page's notice card then honestly says
the channel is off while everything the owner actually opened the app for
still works. Both teeth are pinned by `tests/test_notice_channel.py`
(`the notice channel can never kill the app`), fail-closed in `build.py`.

## The three obstacles Android puts in the way, all handled in the app

| Obstacle | How it is met |
|----------|---------------|
| **The permanent notification** cannot be hidden | So it is written to earn its line: channel `notice_waiting` at `IMPORTANCE_MIN` (silent, no badge, no vibration), and copy that says what the app is doing, that nothing is being streamed, and that Android requires the line. Tapping it opens the app. |
| **POST_NOTIFICATIONS** (Android 13+) | Unchanged this round: asked once at app START, while the owner is looking (owner 2026-08-06 — asking on the first notice spent that notice on the dialog, and in the background the dialog cannot appear). Reported as `notifications` in `Bridge.noticeState()` so the page's card can say when it is off. |
| **Battery optimisation** | The foreground service keeps the PROCESS alive, but Doze can still defer an unexempted app's network traffic while the device is idle — a notice sitting on the wire until the phone next wakes, i.e. the original complaint. Only the user can grant the exemption, so the page explains it and `MainActivity.askBatteryExemption()` opens the system dialog. The app never pretends to have it: `batteryExempt()` reads the real state every time. |

## Delivering one notice

The frame is byte-for-byte what the page would have received, so what happens
to it is what [Notify (client)](../../client/__about/notify.md) does with it:
a banner tagged with the agent, and speech in the voice and at the pace the PC
chose. The user's own switches are honoured too — they live in the page's
preference store (`p_notifyPrefs`), and since the page is not here to read
them, the service reads the same store the page writes.

The page's third carrier, the toast, is deliberately absent: there is no page
on screen to toast onto.

The `Notifier` (and with it the TextToSpeech engine) is built on the FIRST
notice, not at start: an idle service must cost nothing, and an engine bound
all night for a sentence that may never come is not nothing. Speech is queued
until the engine is ready, so the first notice is late, never lost.

## Lifecycle

- **Started** from `MainActivity.onCreate` — Android 12+ refuses a foreground
  start from the background, and that is the one moment the app is certainly
  in the foreground.
- **Outlives the Activity, never the APP** (owner rule 2026-08-12: "notices
  only while the app runs in the background — closed is closed"). It survives
  the page hiding — the whole point is that a notice arrives when there is no
  page — but a task removal (the owner swipes the app out of recents) is a
  deliberate close, and `onTaskRemoved` stops the service and its channel on
  the spot. `running` is cleared BEFORE `stopSelf()` so a sticky restart
  racing the stop answers `START_NOT_STICKY` instead of re-arming the link.
  Gate: the closed-app check in `tests/test_notice_channel.py`.
- **`START_STICKY`** — if Android reclaims the process under memory pressure
  WHILE the app still lives, it brings the service back and the link
  reconnects. A notice channel that quietly stayed dead until the next app
  launch would be the same failure in a new place.

## Honest limit

**A phone reboot stops it.** The service comes back when the owner next opens
the app. Restarting from `BOOT_COMPLETED` was considered and left out: recent
Android versions restrict which foreground-service types may start at boot,
and a mechanism that is fragile per OEM is worse than a limitation that is
stated.

## Connections

### Uses
- [NoticeLink](NoticeLink.md) — the wire; this class knows nothing about sockets
- `Prefs.deviceId()` — handed to the link as a lambda so the PC can key one
  waiting channel per device (task 209): he waits on a tablet AND a phone, and
  until the PC could tell them apart each service kicked the other off the
  single channel every few seconds
- [Notifier](Notifier.md) — the banner and the speech
- `Prefs` — the two stored addresses, and the page's preference store

### Used by
- [MainActivity](MainActivity.md) — starts it
- [Bridge](Bridge.md) — `running` / `batteryExempt` / `batteryIntent` for the
  page's notice card
- [Notify (server)](../../server/__about/notify.md) — the other end
