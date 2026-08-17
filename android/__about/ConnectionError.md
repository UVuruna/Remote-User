# ConnectionError — why the PC can't be reached, and the one button that fixes it

**Script:** [ConnectionError.kt](../app/src/main/java/com/uvuruna/vibecoder/ConnectionError.kt) ·
**Folder:** [Android](../___android.md) ·
**Owner of the page:** [MainActivity](MainActivity.md)

## Purpose

The native error card's whole brain: which of five causes explains why
neither stored address answered, and what its one button should do about
each one.

Split out of `MainActivity.kt` on 2026-08-17 (THE STRUCTURE LAW: the in-app
update feature's addition pushed the file past the 1,000-line ceiling, and
the law says a session that must extend an over-threshold file splits it
first). The seam is the same one [Insets](Insets.md)/[ScreenAwake](ScreenAwake.md)
were cut on — extension functions on `MainActivity`, exactly like
`showLayer()`, rather than a wrapper class holding a second reference to the
same Activity: every function here needs the window's own error-card views
and network state, so a class would only be one more thing to keep in step
with `host`.

MainActivity is about WHICH page to load and how to survive losing it; this
is about WHY none of them answered.

## The five causes, in decision order

`classifyFailure()` — each state is only reached once the ones above it are
ruled out (owner-approved decision flow 2026-08-04):

1. **`NO_NET`** — no network at all.
2. **`PC_NO_TUNNEL`** — the PC never reported a Tailscale address; the
   missing step is on the PC, not the phone.
3. **`TS_MISSING`** — Tailscale is not installed here (needs the manifest
   `<queries>` entry, Android 11+).
4. **`TS_OFF`** — installed, no VPN tunnel up.
5. **`PC_DOWN`** — the tunnel is up, so the PC itself is not answering.

**Honest limits, stated rather than hidden:** Android exposes no "is
Tailscale connected" API, only "some VPN is up" (`tunnelUp()` checks the
default network's `TRANSPORT_VPN` / `NOT_VPN` capabilities); and telling the
home Wi-Fi from a foreign one would cost the location permission just to
read an SSID. So `TS_OFF`'s copy also covers "at home, Tailscale off, PC
asleep" — turning the tunnel on is the phone's only move either way.

## The card names the cause and its button IS the fix

One generic "Try again" for five different causes was the whole problem
(owner report 2026-08-04) — including the everyday one, phone away from home
with Tailscale off, where Try again can never work. `showErrorCard()` maps
each `ConnectionFail` to its own title/body string and its own primary
action: **Install Tailscale** (Play Store), **Turn Tailscale on** (opens the
app — Android has no API to flip another app's VPN switch, so the button
opens Tailscale and the copy names the one control to press), or **Try
again** (re-probe). Re-rendered on every failed resolve, so the card follows
the phone's live state.

Nothing here replaces the self-healing in `MainActivity`: the 4 s retry timer
and the network-change callback keep re-probing regardless, so a user who
flips Tailscale on and comes back finds the session already loading.

## Key functions

| Name | What it does |
|------|--------------|
| `showErrorCard()` | `classifyFailure()` → render + bind the button → `showLayer(error = true)`. |
| `classifyFailure()` | The five-cause decision tree above. |
| `hasNetwork()` / `tunnelUp()` / `activeCaps()` | Three readings off `ConnectivityManager`, no extra permission. |
| `tailscaleLauncher()` | `null` when Tailscale is not installed (package visibility via the manifest `<queries>`). |
| `openTailscale()` / `installTailscale()` | The two fix actions; `installTailscale` falls back from `market:` to the web listing when no Play Store app resolves the scheme. |
| `warnIfForeignWifi()` | The one-per-stay heads-up when the LAN probe fails but the tunnel answers over Wi-Fi (owner request 2026-07-27) — called from `MainActivity.resolveAndLoad()`, not from this file's own flow. |

## Connections

### Uses
- `MainActivity` — `errorTitle`/`errorBody`/`errorAction` (promoted from
  `private` to `internal` for this split), `connectivity`, `warnedForeignWifi`,
  `onWifi`, `resolveAndLoad()`, the companion's `TAILSCALE_PKG`
- [ScreenAwake](ScreenAwake.md) — `showLayer()`
- `Prefs` — `tsUrl()`

### Used by
- [MainActivity](MainActivity.md) — `resolveAndLoad()`'s failure branch and
  `Client.onReceivedError` both call `showErrorCard()`; `resolveAndLoad()`
  also calls `warnIfForeignWifi()` directly

## Honest limits

Kotlin cannot be executed in this repo (no JVM test runner) — this split
moved code verbatim (only visibility changed, `private` → `internal`, on the
handful of `MainActivity` members it needs) rather than rewriting any of its
logic, to keep the risk of a blind refactor as low as the move allows.
