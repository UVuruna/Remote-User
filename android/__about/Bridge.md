# Bridge (Android)

**Script:** [Bridge.kt](../app/src/main/java/com/uvuruna/vibecoder/Bridge.kt)

## Purpose

`window.Android` — **everything the page is allowed to ask of this shell**,
in one file. Every method here is a name the web client calls
([Connection](../../client/__about/connection.md),
[Controls](../../client/__about/controls.md),
[Notify (client)](../../client/__about/notify.md),
[State](../../client/__about/state.md)).

## Why it is its own file (split 2026-08-07)

`MainActivity.kt` stood at 978 lines of a 1,000 ceiling and this round had to
add to it (THE STRUCTURE LAW: a session that must extend an over-threshold
file splits it first). The line was not "the file got long" — that only forced
the question. The two halves are genuinely different jobs:

| | responsibility | addressed by |
|---|---|---|
| [MainActivity](MainActivity.md) | **the window** — the WebView, the two stored addresses and the probe that picks one, the native error card, system bars, Android lifecycle | nothing outside the app |
| **Bridge** | **the protocol** — the names the page calls | the page, which is served by the PC while the shell is installed separately |

That second row is the argument. The page and the shell **version
independently**: the page arrives fresh from whichever PC answered, the shell
is whatever APK is installed. So these signatures are a compatibility surface
that outlives either side's version — which is why `speakAs` sits beside
`speak` instead of replacing it, and why `lockOrientation` still accepts the
retired word `wide`. A contract with that property belongs in one readable
place, not at the bottom of an Activity.

## The capability surface

Bridge is a plain class holding its host (`Bridge(host: MainActivity)`), not
an inner class, and the host members it reaches are `internal`. **That list IS
the shell's capability surface**, and making it visible was half the point of
the split: if it grows, the seam moved and should be re-drawn.

Reached today: `onWifi` / `onCellular`, `excursions`, `screenIsAway()`,
`repair()`, `voice`, `notifier`, plus three helpers that stay in the Activity
because Activity Result launchers are the Activity's own —
`startVoiceInput()`, `postNotice()`, `askBatteryExemption()`.

## The methods, by subject

| Subject | Methods |
|---------|---------|
| Pairing / addresses | `rescan`, `setTailscaleUrl`, `linkLost`, `appVersion`, `update` |
| Per-device storage | `prefGet`, `prefSet` — origin-independent, because the shell alternates between the LAN and Tailscale addresses and `localStorage` is keyed by ORIGIN (the "sets picker rotates" bug, 2026-08-05) |
| Network / presence | `transport`, `netStats`, `hideReason`, `keepAwake`, `lockOrientation` |
| Notices | `setNoticeChannel(on)`, `noticeChannelOn()` — T80b, 2026-08-14 |
| Dictation | `startVoice`, `stopVoice`, `voiceLangs`, `voiceChosen`, `voiceSetLang`, `voiceState`, `voiceMuteBeeps`, `voiceSetMuteBeeps` |
| Notices | `notify`, `speak`, `speakAs`, `ttsVoices`, `noticeState`, `noticeSetup` |

## `linkLost` — the one thing the page cannot do for itself (owner 2026-08-07)

The page's WebSocket can only ever go to `location.host` — the address the
**document** was loaded from. When the phone changes network the document is
still perfectly alive on an address that no longer reaches the PC, and nothing
in the page can move it: it retries the dead host forever, which is the owner's
report of *"prekid veze"* and of having to close the whole app.

The two stored addresses live in the shell, so the shell is the only component
that can answer. `linkLost()` is the page saying *I have lost the PC* — sent
after `LINK_LOST_TRIES` connections in a row that were never served (see
`client/__about/connection.md`) — and it hands straight to
`MainActivity.pageLostTheServer()`.

What happens next is the resolver's decision, not the page's: the current
address still answering leaves the document exactly where it is
(`sessionHealthy`), the other one answering moves us there, neither answering
brings up the error card with its own 4-second self-healing. So asking costs
nothing when the address was fine.

## `hideReason` did not change, and that matters

The streaming session must keep dying the moment the page hides — the owner's
security rule, the presence protocol, the topmost ledger and the layout
defence all rest on it. The waiting channel added in the same round
([NoticeService](NoticeService.md)) is a **second, separate** channel that
carries notices only; it never claims the phone is present, and the PC would
not believe it if it did (`/notices` never touches the server's one-device
slot — see [Notify (server)](../../server/__about/notify.md)).

## `noticeState` / `noticeSetup`

The two new methods, and the only part of the waiting channel the page is
involved in at all. The service starts with the app and needs no user; what it
DOES need is the one thing Android will not let an app take for itself —
exemption from battery optimisation, without which Doze defers the socket's
traffic and a notice can sit unheard until the phone next wakes.

Asking for it requires an explanation, and every explanation in this product
lives in the page (hard owner principle). So `noticeState()` reports
`{running, battery, notifications}`, the page's card says why in his own
words, and `noticeSetup()` opens the system dialog. Nothing is explained in a
manual, in chat, or in a toast.

## Connections

### Uses
- [MainActivity](MainActivity.md) — its host; the `internal` members above
- [VoiceInput](VoiceInput.md) — the whole dictation subsystem
- [Notifier](Notifier.md) — banners and speech
- [NoticeService](NoticeService.md) — `running` / `batteryExempt` /
  `batteryIntent` for the page's notice card
- `Prefs` — the two stored addresses and the page's own preference store

### Used by
- The web client, by name, through `window.Android` — see
  [Client (folder)](../../client/___client.md)
