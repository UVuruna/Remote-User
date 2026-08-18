# UpdateReturn — the way back in, after the app replaces itself

**Script:** [UpdateReturn.kt](../app/src/main/java/com/uvuruna/vibecoder/UpdateReturn.kt) ·
**Folder:** [Android](../___android.md)

## Purpose

[Updater](Updater.md) installs a new version of this app over itself. When
that install SUCCEEDS, Android tears down our process and installs the new
package — **but it starts no activity**. The app simply disappears off the
screen, and the owner has to find it and open it by hand (his report,
2026-08-18).

This receiver is the only thing that can do anything about it, because it is
the only part of this app that runs at a moment when the app does not.

## Why `Updater` cannot do this itself

Its own class header says it: the success it would report happens **after the
process that would report it is gone**. That is also why the update card has
no "success" state and never will. Nothing running before the commit can
speak after it; only something the SYSTEM starts afterwards can.

## Why `MY_PACKAGE_REPLACED`, and not `PACKAGE_REPLACED`

`ACTION_MY_PACKAGE_REPLACED` is delivered to **our own package only**, exactly
once, exactly when this app was the one replaced. That is the entire question
this feature asks, answered by the platform for free.

`ACTION_PACKAGE_REPLACED` is the broad one: it fires for every app the device
updates. It would need package visibility, an extra to filter on, and it would
wake us for work that is none of our business — to learn the same fact the
narrow action already states.

## Why the manifest, and never a runtime registration

A runtime-registered receiver lives **inside a running process**. At the moment
this broadcast is sent our process is dead — it is the very thing the install
killed. A manifest entry is the only kind of receiver that can bring a package
back from nothing, so the manifest declaration is not a style choice here, it
is the mechanism.

`android:exported="false"`: nothing outside this app has any business reaching
it, and the system delivers this protected broadcast regardless.

## TWO CARRIERS, AND ONLY ONE OF THEM IS RELIABLE

This is the shape of the file, and it must not be "simplified" into one.

| Carrier | Standing |
|---|---|
| `startActivity(MainActivity)` with `FLAG_ACTIVITY_NEW_TASK` | **Best effort ONLY.** Since Android 10 a process started by a background broadcast is normally FORBIDDEN from launching an activity. We are exactly that process. Worse, the refusal is usually **silent** — the system logs it and drops the start, so no `catch` here can detect it. Some OEM builds and some states (the app was in the foreground when the update landed) do allow it, which is why it is attempted at all: when it works, he is back in the app with nothing to tap. |
| A notification, "Vibe Coder is up to date — tap here to open it again" | **The mechanism that works**, and therefore posted **ALWAYS** — never in an `else` behind the start above, because there is no reliable way to learn that the start was refused. A start that succeeded leaves him one notice to swipe away; a start that was refused leaves him one tap from the app. Only the second case is the one this feature exists for. |

The `try/catch` around the start exists for the *throwing* refusals
(`SecurityException`, `ActivityNotFoundException`, an OEM's own): a crash there
would cost him the notification, i.e. the carrier that actually works.

## One notification builder in this app

The notice goes through [Notifier](Notifier.md) — monorepo priority C,
inheritance over duplication. No second builder, no second channel and no
second `PendingIntent` shape live here; the tap lands in
[MainActivity](MainActivity.md) because that is where `Notifier.post` always
sends it. Its tag is `vibecoder-update`, its own: an update notice must never
replace an agent's line, and a later update replaces its own predecessor
rather than stacking.

`Notifier` binds a TextToSpeech engine in its constructor. Nothing is spoken
here, and a receiver may keep nothing alive after `onReceive` returns, so the
engine is `release()`d in a `finally` instead of being left bound to a process
the system is about to stop again.

The copy itself lives in `strings.xml`, like every other user-facing sentence
in this shell.

## Honest limits

- **If notifications are refused** (POST_NOTIFICATIONS, Android 13+) there is
  nothing left: `Notifier.post` logs the refusal and the app stays closed
  until he opens it. The app asks for that permission once at START, while he
  is looking (owner 2026-08-06), so this is the same grant everything else in
  the notice path already depends on.
- **Nothing here is proven on this repo's machine.** The receiver's real
  behaviour — whether this particular Android build allows the direct start —
  is only ever observed on the owner's device. The gate
  (`tests/test_apk_update.py`, promises 9–11) proves the STRUCTURE: declared
  in the manifest with the narrow action and not exported, posting through the
  one `Notifier`, and a start that cannot crash the receiver.

## Connections

### Uses
- [Notifier](Notifier.md) — the notification, and the only builder
- [MainActivity](MainActivity.md) — what both carriers open

### Used by
- Nothing in this app calls it. **Android does**, and only after
  [Updater](Updater.md) has committed a session that succeeded.
