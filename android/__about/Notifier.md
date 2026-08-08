# Notifier (Android)

**Script:** [Notifier.kt](../app/src/main/java/com/uvuruna/remoteuser/Notifier.kt)

## Purpose

The phone's delivery end of "the PC calls you" (ROADMAP Phase H, owner
2026-08-05). The page decides WHETHER to notify and speak
([Notify (client)](../../client/__about/notify.md)); this class knows HOW.

Two carriers, each covering what the other cannot:

- **A real system notification** — the only path that still reaches the owner
  with the app in the background or the screen off, which is the situation the
  whole feature exists for. Channel `agents`, `IMPORTANCE_HIGH` (heads-up),
  vibration on, `BigTextStyle` so a finished agent's whole sentence is
  readable, and a content intent that opens the app.
- **Speech** (`TextToSpeech`) — his *"izgovori neku reč"*, for when his eyes
  and hands are on the PC.

## The tag is the agent's name

`post(title, text, tag)` uses the agent's name as the notification tag and
`idFor(tag)` (a stable hash) as its id, so:

- the same agent finishing twice **replaces** its own line — always current;
- four agents keep four separate lines — which is the point of naming them.

## The tap carries a destination (owner 2026-08-08, task 110)

`post(..., jump)` puts the PC's `{index, name}` on the intent behind the
notification, and MainActivity reads it out when the tap arrives. Empty means
the PC could not say where, and the tap does what it always did — open the app.

The request code became **per agent** in the same change, and that is a fix,
not a detail: with one shared code, `FLAG_UPDATE_CURRENT` rewrites the SAME
PendingIntent every time, so four agents' notifications would all carry the
extras of whichever finished last — and the tap would open the wrong window
while looking perfectly right.

## Speech is queued, never dropped

The engine takes a moment to initialise, and the first `speak()` after a cold
start would otherwise land after the sentence it was asked to say. Text
arriving before `onInit` is held and drained the moment the engine reports
success; a failed init clears the queue and logs why. `release()` (called from
`MainActivity.onDestroy`) shuts the engine down.

Since round R2 the engine is bound in `init`, not at the first notice. It
always had that one reason; the second is new — `voices()` is asked the
moment the page connects, and an engine that has not bound yet has nothing to
report.

## HOW it speaks comes from the PC (round R2, owner 2026-08-07)

`speak(text, voice, rate)` applies both before it says anything:

- **rate** is `TextToSpeech.setSpeechRate` (1 = the engine's normal pace); the
  desktop offers 0.8 / 1 / 1.25 / 1.5.
- **voice** is a `Voice.name` this device itself reported. A voice the device
  does NOT have falls back to the engine's default and logs a warning — the PC
  may be remembering a different phone, and a missing voice must never mean a
  silent notice.

`voices()` is the list the desktop chooses from: JSON `[{name, label,
locale}…]`, where `name` is the identity the PC stores and sends back and
`label` is what a person reads (`"English female_2"` — the locale's display
language plus the distinguishing tail of the voice name). Voices whose data is
not downloaded (`KEY_FEATURE_NOT_INSTALLED`) are left out: offering one on the
PC would be a choice that silently fails. `getVoices()` throws on real devices
whose engine reports a null voice set, so it is wrapped — an empty list is a
usable answer, a crashed shell is not.

## Connections

### Uses
- `androidx.core` — `NotificationCompat` / `NotificationManagerCompat`
  (declared explicitly in `app/build.gradle.kts`, though appcompat already
  brings it: this file compiles against it directly)

### Used by
- [MainActivity](MainActivity.md) — the `notify(title, text, tag)` and
  `speak(text)` bridge methods, and the `POST_NOTIFICATIONS` request that
  precedes the first banner on Android 13+

## Design Decisions

- **A refused permission is not a failure.** `NotificationManagerCompat.notify`
  throws `SecurityException` when POST_NOTIFICATIONS was denied; it is caught
  and logged, speech and the toast still deliver, and the page's
  `__notifyDenied()` hook fires so the user can be told once, in plain words.
- **The permission is asked on the FIRST notice, not at startup.** A user who
  never turns the feature on is never asked, and the ask arrives with its
  reason visible on screen.
