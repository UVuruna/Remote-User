# ConnectivityWatcher.kt

**Script:** [ConnectivityWatcher (script)](../app/src/main/java/com/uvuruna/vibecoder/ConnectivityWatcher.kt)

## Purpose

What network the phone is on, and when that changes. Split out of
[MainActivity](MainActivity.md) on 2026-08-18 (THE STRUCTURE LAW, VC-R7) on
the same seam [NoticeService](NoticeService.md), [Notifier](Notifier.md),
[Updater](Updater.md), [ScreenAwake](ScreenAwake.md) and [Insets](Insets.md)
were all cut on before it: MainActivity is about WHICH page to load and how to
survive losing it, and this is one job with one dependency — the system's
`ConnectivityManager`.

## Why a class and not an `object`

A `NetworkCallback` is registered against a live host and must be unregistered
with it. An instance whose lifetime IS the activity's is the honest shape, and
it is exactly what [Updater](Updater.md) already does: `watch()` from
`onCreate`, `release()` from `onDestroy`, never leak the callback.

`ScreenAwake` and `Insets` are the other pattern (an object / extension
functions) because they hold nothing that has to be handed back.

## What it deliberately does NOT own

`onWifi`, `onCellular`, `warnedForeignWifi` and `connectivity` stay fields of
`MainActivity`. Two other files read them off the activity — `Bridge.kt` asks
which transport the page is on (the phone's own auto-quality mode), and
`ConnectionError.kt` asks the manager for the live capabilities and flips the
foreign-Wi-Fi flag. Moving the STATE as well as the WATCHING would have been a
second change riding on a structural one.

This class is the thing that NOTICES; the activity remains the thing that
KNOWS.

## The two behaviours it carries over unchanged

- **`onAvailable` re-resolves, always** — not only while the error card is up.
  That `if (errorView.visibility == VISIBLE)` is the owner's 2026-08-07 report:
  a page that loaded on home Wi-Fi and is now retrying a `192.168` host from a
  mobile network is the state he is actually in, and nothing ran in it. Killing
  the app worked every time, which is what made "Try again" look broken.
- **`onCapabilitiesChanged` tracks the transport** — a VPN network (Tailscale)
  lists its underlying transports, and losing Wi-Fi re-arms the foreign-Wi-Fi
  notice so the next one warns again.

## Connections

### Uses
- `MainActivity` — `resolveAndLoad(silent = true)`, and the four fields above

### Used by
- [MainActivity](MainActivity.md) — one field, `watch()` in `onCreate`,
  `release()` in `onDestroy`

## Classes

### ConnectivityWatcher(host)
- `callback` — the `NetworkCallback`, registered on the DEFAULT network
- `watch()` — get the manager, hand it to the activity, register
- `release()` — unregister and clear; safe to call twice
