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

## Speech is queued, never dropped

The engine takes a moment to initialise, and the first `speak()` after a cold
start would otherwise land after the sentence it was asked to say. Text
arriving before `onInit` is held and drained the moment the engine reports
success; a failed init clears the queue and logs why. `release()` (called from
`MainActivity.onDestroy`) shuts the engine down.

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
