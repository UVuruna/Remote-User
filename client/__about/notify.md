# Notify (client)

**Script:** [notify.js](../notify.js)

## Purpose

The phone half of "the PC calls you" (ROADMAP Phase H, owner 2026-08-05).
`connection.js` hands it every `notify` frame; it delivers the notice three
ways, strongest first — because the situation this feature exists for is the
one where the owner is **not** looking at the phone:

| Carrier | Reaches him when | Bridge |
|---------|------------------|--------|
| Android notification | the app is backgrounded, the screen is off | `Android.notify(title, text, tag)` |
| Spoken aloud | his eyes and hands are on the PC | `Android.speakAs(text, voice, rate)`, or `Android.speak(text)` on an older shell |
| Toast + tone | he is looking at the page | in-page |

The **tag is the agent's name**, so a second notice from the same agent
replaces its own notification line while four agents keep four lines. That is
the owner's requirement in one detail: *"da izbaci notifikaciju koja opisuje
koji agent je završio"*.

## HOW it speaks is the PC's decision (round R2, owner 2026-08-07)

Nothing about the voice is stored on this phone. The desktop Settings window
picks a voice and a speaking pace, and both ride on **every** `notify` frame
(`msg.voice`, `msg.rate`) — so a reconnect can never leave the phone speaking
in a voice the desktop no longer selects. `speakAs` is preferred and plain
`speak` is the fallback: the page is served by the PC while the shell is
installed separately, so the two versions drift, and a notice must never be
lost to a shell version.

`sendTtsInfo()` is the other half. On every connection it asks
`Android.ttsVoices()` and sends `tts_info {voices:[{name, label, locale}…]}`
— the ONLY source the desktop's Voice dropdown can have, because a
TextToSpeech engine's voices differ per device, per language pack, per
Android version. A dev browser has no bridge and simply sends nothing.

`msg.speak` still wins over everything: the desktop's "Say it out loud" off
sends `false`, and the banner is raised regardless — muting one carrier never
loses a notice.

## A tap on the notice goes THERE (owner 2026-08-08, task 110)

The PC already worked out WHICH layout the notice belongs to and put it on the
frame as `layout {index, name}` ([Notify](../../server/__about/notify.md)).
This file carries it the last two steps.

**Out:** `Android.notifyAt(title, body, tag, jump)` — a NEW bridge method
beside `notify`, never a fourth argument on it. The page is served by the PC
while the shell is installed separately, so a changed arity would simply stop
resolving on an older shell and take the notice down with it. Same reasoning
as `speakAs`, same round's lesson.

**Back:** `takeNoticeJump()` PULLS the answer from the shell, and
`applyNoticeJump()` acts on it from the first `layout_state` of a connection.
A pull, because the tap may have COLD-STARTED the app — at that instant there
is no page and no layout list, so a push would land in nothing.

`noticeTarget()` VERIFIES before moving: the NAME decides, the index is only a
hint. Right where it points, else the one layout carrying that name, else
nothing at all plus a toast saying so. Landing him in a stranger's window is
worse than not moving, and a silent no-op after a deliberate tap reads as a
broken button.

A tap OUTRANKS the excursion auto-restore (`layoutRestore`): both want to
choose a layout on a fresh connection, and only one of them is something he
just did with his thumb.

## Per-device switches

`notifyPrefs()` / `saveNotifyPrefs()` in the shell's SharedPreferences (via
`prefGet`/`prefSet` — never bare localStorage, which splits per origin
between the LAN and Tailscale addresses):

- `banner` — the Android notification (default ON)
- `speak` — TextToSpeech (default ON)
- `tone` — the in-page chime (default **OFF**: it is the one that annoys when
  the phone sits on the desk beside the PC)

## The notice card (owner decree 2026-08-07)

His report: *"notifikacije mi stižu tek kada podignem aplikaciju iako je sve
vreme otvorena u pozadini"*. The shell now holds a small waiting channel of
its own so a notice arrives with **no page at all**
([NoticeService](../../android/__about/NoticeService.md)) — and that service
needs one thing only the user can give it: permission to run without Android
deferring its traffic while the phone is idle.

Everything a user must do is explained IN the app and nowhere else (hard owner
principle), so the words live here, on the page, beside every other piece of
guidance; the shell only opens the system dialog (`Android.noticeSetup()`).
`Android.noticeState()` supplies `{running, battery, notifications}` and the
card says something only when the exemption is missing.

**Offered once per app VERSION**, not once per device. "Not now" has to mean
something — a card that returns on every connect is the nagging he banned —
but a permanent refusal recorded by one tap would silently disable the feature
forever on a phone whose owner did not read the card. An update is the
natural, self-limiting moment to ask again. `window.__noticeStateChanged` is
called by the shell when the user returns from the dialog, so the card leaves
the screen the instant the exemption is granted.

## Connections

### Uses
- [Controls](controls.md) — `showToast`, `prefGet`/`prefSet`, `send` (the
  `client_log` diagnostics channel), `keepFocus`
- [Panels](panels.md) — `ghostClickArmor` for the notice card
- the shell's bridge — `Android.notify` / `Android.speak` /
  `Android.noticeState` / `Android.noticeSetup`
  ([Bridge](../../android/__about/Bridge.md), `Notifier.kt`)

### Used by
- [Connection](connection.md) — `msg.type === "notify"` → `handleNotify(msg)`
- [Notify (server)](../../server/__about/notify.md) — the frame's author

## Design Decisions

- **The tone is synthesised, not shipped.** Two sine notes through
  `AudioContext`: no file to fetch, no decoder, and the page has long had the
  user gesture autoplay policy asks for.
- **Every carrier fails alone.** A throwing tone, a refused notification
  permission and a missing TTS engine each land one `client_log` line in the
  PC's server log and leave the other two paths working. The owner never gets
  a panel about it — diagnostics go to the log, per his 2026-08-05 rule.
- **The page keeps no history.** A notice the page never saw was carried by
  another channel or held by the server (which stamps it with the time it
  happened, so `notifyWhen` can say "8 min ago"); this module never re-shows
  anything, because a stale alarm is worse than none.
- **This module is now one of THREE places a notice can land**, and the choice
  is the PC's alone: the page while it is open, the shell's waiting channel
  while it is not, and the server's short queue when neither exists. The page
  needs no de-duplication because the server's `deliver()` is a chain of
  returns — see [Notify (server)](../../server/__about/notify.md).
