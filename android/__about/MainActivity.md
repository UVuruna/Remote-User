# Main Activity

**Script:** [Main Activity (script)](../app/src/main/java/com/uvuruna/vibecoder/MainActivity.kt) ·
**Flow:** [diagram](../__flow/MainActivity.md)

## Purpose

The client shell: a full-screen `WebView` on whichever stored address
answers, plus everything a browser tab cannot do by itself. The page
(`client/index.html`, loaded inside the `WebView`) carries ALL product UI
and guidance; this class only adds:

- **Dual-address resolution with failover** — the LAN address (from
  pairing) and the Tailscale address (learned from the page on every
  `config`, via the JS bridge) are probed on every start and the reachable
  one is loaded, LAN preferred. A single stored URL was the original live
  failure: the LAN address on mobile data meant minutes of
  `ERR_CONNECTION_TIMED_OUT` before anything showed.
- **A self-healing, cause-aware error card** — while shown, it re-probes
  itself on a 4 s timer AND immediately on every default-network change,
  instead of the old one-shot "Try again" that always fired mid-flap on flaky
  Wi-Fi. It also names WHY the connection failed and makes its primary button
  the fix for that cause (install Tailscale / open Tailscale / re-probe now)
  — see `classifyFailure()` below.
- **Document-health tracking (`pageAlive`)** so recovery never reloads a
  session that is actually fine — the classic case is screen unlock, where
  Wi-Fi takes 1–3 s to reassociate and a single ping fails on a perfectly
  healthy page whose own JS has already reconnected the WebSocket.
- **A foreign-Wi-Fi heads-up toast**, the `Android` JS bridge
  (`rescan` / `setTailscaleUrl` / `appVersion` / `update`), the native file
  chooser for phone→PC image upload, immersive system bars, and the
  keep-awake / rotation-survives-the-session / pause-on-background behavior.

See [Main Activity (flow)](../__flow/MainActivity.md) for the resolve/retry
state machine as a diagram — the logic below is dense enough that the prose
alone undersells it.

## Connections

### Uses
- [Prefs (script)](../app/src/main/java/com/uvuruna/vibecoder/Prefs.kt) — reads both stored URLs every
  `resolveAndLoad`; writes the Tailscale URL from the JS bridge; read by
  `Client.shouldOverrideUrlLoading` to recognize "our server" by port
- [Gamepad](Gamepad.md) — every pad key and stick event is offered to it
  before the view hierarchy sees it; released on `onPause`
- [Onboarding Activity](OnboardingActivity.md) — `repair()` launches it
  (`EXTRA_FORCE`) when no LAN address is stored, or the user taps "Scan a
  new QR" on the error card
- [Client (folder)](../../client/___client.md) — the entire product UI,
  loaded into the `WebView`; the `Android` bridge and the `config` message
  are the two-way contact points with the client's [Connection](../../client/__about/connection.md) script (the JS bridge calls and `config` handling both live there)
- The PC's HTTP/WebSocket server, conceptually (not a code dependency — this
  class talks to it only over the network): `GET /ping` for the reachability
  probe, `GET /app.apk` opened by the update bridge, and the page's own
  WebSocket to `/ws`. See [Web Layer](../../server/__about/web.md) and
  [Server (folder)](../../server/___server.md).

### Used by
- [Onboarding Activity](OnboardingActivity.md) — `openClient()` starts it
  once a pairing link is accepted
- The Android task/Recents system on resume (no other internal caller — this
  is the app's terminal screen)

## Classes

### MainActivity
The activity itself (`AppCompatActivity`) — owns the `WebView`, the loading/
error overlay views, the network callback, and the resolve/retry state
(`resolveEpoch`, `pageAlive`, `lastLoadFailed`, `onWifi`,
`warnedForeignWifi`). Key methods: `resolveAndLoad(silent)` (the probe/
failover core — see the flow doc), `scheduleRetry(epoch)`, `pingOk(url)`
(the strict-204 `/ping` probe), `showErrorCard()` / `renderErrorCard()` /
`classifyFailure()` and the actions they bind (`openTailscale()`,
`installTailscale()`, with `hasNetwork()` / `tunnelUp()` /
`tailscaleLauncher()` as the three readings behind the diagnosis),
`warnIfForeignWifi()`, `hideSystemBars()`,
`repair()` (hands off to `OnboardingActivity`), `onResume()` /
`onPause()` / `onDestroy()` lifecycle wiring.

### The game controller — claimed before the WebView (build round G1, 2026-08-07)

`dispatchKeyEvent` / `dispatchGenericMotionEvent` route every event into
[Gamepad](Gamepad.md) first, so pad keys never reach the view hierarchy: the
WebView's own D-pad focus handling would otherwise fight the page's mapping for
every arrow press. Anything not from a gamepad/joystick source falls straight
through untouched. `onPause` calls `pad.releaseAll()` — a release this shell
never saw would leave a PC mouse button held for the rest of the session.

The Activity owns the instance (and hands it the `evaluateJavascript` sink)
for the same reason it owns `voice`: it is the thing with a WebView. The
mapping itself is not here and not in the APK at all — it is the page's
([Gamepad (phone)](../../client/__about/gamepad.md)).

### netCallback (`ConnectivityManager.NetworkCallback`, anonymous, field)
Registered via `registerDefaultNetworkCallback` in `onCreate`, unregistered
in `onDestroy`. `onAvailable` kicks a silent `resolveAndLoad` — **always**,
since 2026-08-07; `onCapabilitiesChanged` tracks whether the default network
carries a Wi-Fi transport (`onWifi`) and re-arms the foreign-Wi-Fi toast the
next time Wi-Fi drops.

### Losing the route mid-session (owner report 2026-08-07)

*"kada nismo na wi-fi mreži … dešava nam se prekid veze, i ovo 'Try again'
dugme retko kad pomogne … nekad čak i da zatvorimo celu aplikaciju."*

`onAvailable` used to re-resolve only `if (errorView.visibility == VISIBLE)`,
and that condition is the bug. The error card is a **cold-start** state: it
means no address answered before a page ever loaded. The state he is actually
in is the opposite one — a page that loaded perfectly on the home Wi-Fi and is
now retrying a `192.168.*` host from a mobile network. There, nothing here ran;
and nothing in the page could stand in for it either, because the page's socket
can only ever reach `location.host`, the address the **document** was loaded
from. The only code path in the whole app that re-probes both addresses was a
fresh process. So he killed the app, and it worked, every single time — which is
precisely what made "Try again" look broken.

Two things changed, and a third had to change with them:

- `onAvailable` re-resolves whatever is on screen;
- `pageLostTheServer()` (reached from `Bridge.linkLost`) lets the PAGE ask for
  the same thing, after a run of connections that were never served — the page
  notices a dead route long before the OS reports a network change, and often
  no network change ever comes (a Tailscale relay moving, the PC's tunnel
  flapping). Throttled by `LINK_LOST_THROTTLE_MS` = 5 s, deliberately shorter
  than the page's own escalation so a real network change is never swallowed;
- `sessionHealthy` now compares **origins**, not whole URL strings. `web.url`
  is what the document reports — the server's path, a fragment the page added,
  a token re-issued since pairing — while the candidates are the addresses as
  pairing stored them. With the callback firing on live pages, a text mismatch
  there would reload a working session on every blip. `origin()` reduces both
  to `scheme://host:port`, which is the only part that says *which address we
  are on*.

Resolving on a live page is safe by construction: `sessionHealthy` keeps a
document whose own address still answers, because the page's own JS reconnects
in milliseconds while a `loadUrl` tears the whole session down (the 2026-07-29
unlock race).

Gated by `tests/test_link_recovery.py`.

### The JS bridge — MOVED OUT on 2026-08-07

`window.Android` used to be an inner class here. It is now its own file,
[Bridge](Bridge.md) (THE STRUCTURE LAW — this file stood at 978 lines of a
1,000 ceiling and the notice-service round had to add to it).

The line is not "the file got long"; that only forced the question. This class
is **the window** — the WebView, the two stored addresses and the probe that
picks one, the native error card, system bars, Android lifecycle — and nothing
in it is addressed by name from outside the app. `Bridge` is **the protocol**:
every method there is a name the PAGE calls, and the page arrives fresh from
whichever PC answered while the shell is whatever APK is installed. Those
signatures are a compatibility surface that outlives either side's version,
and that belongs in one readable place.

What stays here, because Activity Result launchers are the Activity's own:
`startVoiceInput()` (the `RECORD_AUDIO` ask, counted as an EXCURSION so the PC
does not hand the owner's windows back mid-sentence), `postNotice()` (the
`POST_NOTIFICATIONS` ask, holding the notice until it is granted), and
`askBatteryExemption()`.

The members `Bridge` reaches are `internal` — `onWifi`, `onCellular`,
`excursions`, `screenIsAway()`, `repair()`, `voice`, `notifier`, plus those
three helpers. **That list IS the shell's capability surface**, and making it
visible was half the point of the split.

### NoticeService — started here, outlives this Activity

`onCreate` starts [NoticeService](NoticeService.md), the small foreground
service that lets an agent's notice reach the phone with **no page at all**
(owner decree 2026-08-07). Started from `onCreate` because Android 12+ refuses
a foreground service start from the background, and that is the one moment the
app is certainly in the foreground; never stopped by the lifecycle, because
the whole point is that it keeps waiting after the Activity is gone.

**T80b (2026-08-14) — the OFF switch.** The start is now conditional on
`Prefs.noticeChannel(this)`. Default ON, so nothing changes for anyone who
never opens the page's Notices row; OFF and the service never starts at all,
leaving the PC's 30-minute queue as the whole delivery path. Turning it on or
off later goes through `NoticeService.setEnabled` — the one function in this
app allowed to stop that service, deliberately NOT in the lifecycle, since a
pause, a screen-off or a keyguard taking the channel down is the bug of
2026-08-12. It acts immediately as well as at the next launch: a switch that
only takes effect after a restart is not one he can trust.

Nothing about the streaming session changed: the page still closes its socket
the moment it hides, and `hideReason()` still answers exactly as before. The
notice channel is a second, separate line that the PC never counts as a
present phone.

### askBatteryExemption — and why it uses a launcher

Doze can defer an unexempted app's network traffic while the device is idle,
which for the notice channel means a notice sitting on the wire until the
phone next wakes — the very complaint the service exists to fix. Only the user
can grant the exemption, so the page explains it (the notice card in
[Notify (client)](../../client/__about/notify.md)) and this opens the system
dialog.

It goes through an `ActivityResultLauncher` rather than a bare
`startActivity` for one reason that matters: it gives us the moment the user
comes BACK, so the excursion count is balanced. An unbalanced one would make
`hideReason()` answer `"excursion"` forever, and the PC would hold layout
windows over his desk through every later screen lock.

### Client (inner class, `WebViewClient`)
- `shouldOverrideUrlLoading`: keeps navigation to the paired server's own
  host:port inside the `WebView`; every other link (Google Play, tailscale.com)
  opens as a real external app via `ACTION_VIEW`
- `onReceivedError` (main frame only): marks `pageAlive = false`, swaps the
  loader for the error card, schedules a retry — a failed page load
  self-heals through the same machinery as a failed probe
- `onPageStarted` / `onPageFinished`: track `pageAlive` (`onPageFinished`
  fires even after `onReceivedError`, so a failed load must not read as a
  live document)

### Chrome (inner class, `WebChromeClient`)
`onShowFileChooser`: routes the page's pickers by what its input asked for
(owner 2026-08-04): `capture` → the camera itself (`TakePicture` into
`cache/camera/` via FileProvider — CAMERA runtime permission required because
the manifest declares it for the QR scanner); `multiple` →
`GetMultipleContents`; otherwise a single `GetContent` of the input's accept
type. Voice input lives in [VoiceInput](VoiceInput.md) (the `voice` field,
destroyed in `onDestroy`).

### Fail (private enum)
The five causes the phone can honestly distinguish, in decision order:
`NO_NET` (no network at all) → `PC_NO_TUNNEL` (no Tailscale address was ever
reported by the PC — the missing step is on the PC) → `TS_MISSING`
(Tailscale not installed here) → `TS_OFF` (installed, no VPN up) →
`PC_DOWN` (tunnel up, so the PC itself is not answering). `showErrorCard()`
maps each to its own title/body and its own primary button.

### Companion object
`PING_TIMEOUT_MS` (3000), `RETRY_INTERVAL_MS` (4000) — the two tunables
behind the probe timeout and the self-healing error-card cadence — and
`TAILSCALE_PKG` (`com.tailscale.ipn`), which must stay in sync with the
manifest's `<queries>` entry and the page's Play Store link.

`update(url)` falls back to an Intent chooser when no direct ACTION_VIEW
handler resolves ("no app can open this" — owner report 2026-08-02).

## The shell answers what the page could only guess (owner failure 2026-08-05)

The page decided why it was hiding from a 90-second timer, so a screen LOCK
moments after a Mic tap was reported to the PC as "back in a second" and the
owner's windows stayed always-on-top for five minutes. The shell is the only
component that can actually know, so the shell answers now.

- **`hideReason()`** → `"lock"` when `PowerManager.isInteractive` is false or
  the keyguard is locked · `"excursion"` when THIS shell launched a picker /
  camera / voice / permission dialog and is still waiting for its result ·
  `""` otherwise (switched away, closed). The lock test comes **first**: a
  picker can be open when the screen goes off, and the screen wins.
- **`beginExcursion()` / `endExcursion()`** — one counter, marked at every
  launch site (`onShowFileChooser`, the audio-permission request) and cleared
  in every result callback. The camera permission dialog is a step INSIDE the
  chooser trip, not a separate one, so only a refusal ends it there.
- **`netStats()`** → this app's and the whole device's `TrafficStats` counters
  as JSON, for the PC's Traffic window.
- **`keepAwake(on)`** — `FLAG_KEEP_SCREEN_ON` was set once in `onCreate` and
  never cleared, so the tablet NEVER slept by itself: the presence signal the
  layout design rests on could only fire if the owner locked it by hand, and
  the screen burned battery over a stream nobody was watching. The page holds
  it while he works and releases it after 3 idle minutes.

  **T80a (2026-08-14) — who OWNS the flag.** Handing it to the page fixed the
  session and left the other half open: the page was the ONLY thing that could
  clear it, and the page is not always alive. While the native error card is up
  — no network, PC unreachable, Tailscale off — there is no page at all, so the
  flag taken in `onCreate` was never released and the phone burned its screen
  over a card saying the session was dead. Ownership moved to
  [ScreenAwake](ScreenAwake.md), which is the shell's only writer of the flag;
  this bridge method records the page's wish and is weighed with the three
  facts only the window knows. What is left in MainActivity is the four inputs
  themselves — `started` (onStart/onStop), `pageAlive` (the load callbacks) and
  the two layers, which now move only through `showLayer`. Gate:
  `tests/test_shell_battery.py` (source-read — Kotlin cannot be run here).
- **`onStart` / `onStop`** — nothing probes, retries or LOADS while there is no
  window on screen. The resolver's 4 s timer and the network callback used to
  run on regardless, and a `loadUrl` from either woke a pocketed phone into a
  full session; `resolveAndLoad` now checks `started` before loading.
