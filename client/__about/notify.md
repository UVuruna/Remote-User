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

## HOW it speaks is THIS DEVICE's decision (owner 2026-08-12)

Round R2 (2026-08-07) put the voice and the speaking pace on the DESKTOP, and
his report is what that cost: he uses a tablet **and** a phone, their
TextToSpeech engines carry different voices, and one dropdown on one PC can
only ever name a voice that exists on one of them. Pick the tablet's, and the
phone falls back to its own engine default — silently, with the Settings
window still showing a name.

So the choice moved to the device that owns it. `notifyVoicePref()` /
`notifyRatePref()` read it through the SharedPreferences bridge
(`prefGet`/`prefSet`, never bare localStorage — that is keyed by ORIGIN and
split this app's state across its LAN and Tailscale addresses once already),
and **the frame's `msg.voice` / `msg.rate` remain the FALLBACK**:

| this device | the frame | what is spoken |
|-------------|-----------|----------------|
| chosen | anything | the device's choice — the pref outranks the PC |
| not chosen | carries a voice/rate | the frame's, exactly as before this change |
| not chosen | carries neither | the engine default, at 1× |

That fallback is what makes the move safe in both directions: a device that
has never opened the card behaves exactly as it did yesterday, and a PC still
carrying a desktop choice is still obeyed by it. Read the other way, it is
also why an empty pref means "no opinion HERE" rather than "the engine
default" — and the card says that in words instead of leaving him to infer it.
Voice and pace fall back **independently**: choosing a voice must not silently
reset the pace.

`speakAs` is preferred and plain `speak` is the fallback: the page is served
by the PC while the shell is installed separately, so the two versions drift,
and a notice must never be lost to a shell version.

`sendTtsInfo()` still runs on every connection — `Android.ttsVoices()` →
`tts_info {voices:[{name, label, locale}…]}`. Nothing on the desktop chooses
from that list any more; it is the PC's diagnostic record of what the
connected device could speak with ([server Notify](../../server/__about/notify.md)).
A dev browser has no bridge and simply sends nothing.

## Settings → Voice: the card, with a preview (owner 2026-08-12)

`openNotifyVoicePanel()` — reached from the Settings set's **Voice** button
(`notifyvoice` in controls.js's `BUILTINS`, wired through panels.js's
`PANEL_KINDS`). It lists this device's own voices from `Android.ttsVoices()`,
the same source `sendTtsInfo` uses and never a second one, plus a first row
that means *no opinion here*. A **Speaking pace** segmented row (0.8 / 1 /
1.25 / 1.5, `segRow` from panels.js) sits above the list, because the pace
applies to every row below it and to the previews.

**Every voice can be heard before it is chosen** — the same rule the dictation
card obeys (owner 2026-08-09: *"treba da mogu da CUJEM da bih odabrao"*).
A list of engine names like `en-us-x-tpf-local` tells nobody anything; the
sound does. One short English sample, always the SAME one — the language here
is fixed, so the only thing that varies between two taps is the voice, and a
changing sentence would be noise between the two things being compared. It
says what a notice says, so he judges a voice on the job it will actually do,
and it is spoken at the pace he has chosen, because a voice at 1.5× is a
different thing to listen to than the same voice at 0.8×.

**One sample at a time, and never a queue** (`voicePreview`, guarded by
`voiceSpeakingName` + a timer from panels.js's `dictSampleMs`). The shell hands
text to TextToSpeech with `QUEUE_ADD` and exposes no stop, and the voice is set
per CALL but applies to the whole QUEUE — so a second tap during a sample would
not replace the first, it would make BOTH speak in the second voice, destroying
the one comparison the control exists to give him. The guard is local to this
card rather than shared with the dictation one because only one full-screen
panel is reachable at a time: each covers the controls that would open the
other.

The preview button is a **sibling** of the row's `<label>`, never a child — a
click anywhere inside a label activates the control that label owns, so a
speaker nested in the row would also CHOOSE that voice, and the tap meaning
"let me hear it first" would have decided (the dictation card's own lesson).

**The honest limit is said once, and only when it is true**: a dev browser with
no bridge is told the voices live on the phone; a device whose engine has none
is told that; a device with no choice made is told what it falls back to. Never
a per-row repetition, never a footnote.

The panel's element is CREATED by this module (`#notify-voice-panel`, appended
to `document.body`) rather than declared in index.html — one file carries the
whole feature. It joins panels.css's three overlay selector lists exactly like
every declared panel, because the scrim, the fixed position and the centring
are properties of the ELEMENT; forgetting one of the three is the set-editor
bug of 2026-08-11.

`msg.speak` still wins over everything: the desktop's "Say it out loud" off
sends `false`, and the banner is raised regardless — a server-side mute is a
separate, higher-priority rule from the phone's own per-device switches below.

## Settings → Notices: WHEN this phone listens (owner 2026-08-12)

`openNoticeModePanel()` — reached from the Settings set's **Notices** button
(`notices` in controls.js's `BUILTINS`, wired through panels.js's
`PANEL_KINDS`, element `#notice-mode-panel` created here and registered in
panels.css's overlay selector lists like the Voice panel above).

His report, in translation: *"You keep swinging between two extremes — one is
that notifications arrive even when my app is closed, the other that they do
not arrive even when my phone is locked. … I want an OPTION in settings where
the user chooses."*

**Naming the two states apart IS the feature**, because they are what kept
being confused:

- the app **running in the background** — behind other apps, or with the phone
  locked and the screen off. A notice arrives here under BOTH choices, always.
  Locking removes no task, so Android never calls `onTaskRemoved` and the
  channel simply lives on. This is the case he reported as broken.
- the app **closed** — swiped out of recents. This, and only this, is what the
  setting is about.

Two rows, each a sentence rather than a segmented label:

- *"Only while the app is open in the background"* — the DEFAULT, and exactly
  what 0.0.127 shipped that morning under his own rule: the channel stops on a
  swipe and the PC's queue holds what finishes for up to 30 minutes / 20
  notices.
- *"Always, even after I close the app"* — the service is not stopped on the
  swipe, so a notice still reaches a shut app.

Stored per device as `noticeWhen` through the prefs bridge (`noticeMode()` /
`setNoticeMode()`) — never bare localStorage, which is keyed by ORIGIN and
split this app's state across its LAN and Tailscale addresses once already
(2026-08-05). Nothing about it rides the `config` frame: it is a fact about ONE
handset's service, like the voice above. The service reads the SAME store while
no page exists (`Prefs.noticeAlways` → `NoticeService.onTaskRemoved`), and
anything that is not the literal `"always"` reads as the shipped default, so a
device that never opens this card cannot be widened by accident.

**The honest limit is on the card, not in a footnote**: after a phone restart
notices resume only once Vibe Coder has been opened one time — true of both
choices, and the word "Always" must not be allowed to promise otherwise.

Gates: `tests/test_notice_channel.py` (default, the "always" branch, the locked
phone under either choice, the per-device store, and the four links that make
the card reachable) and `tests/test_notify_prefs.py`, which EXECUTES the page's
default rule in node.

### WHETHER it listens at all (T80b, owner-approved 2026-08-14)

The rows above answer WHEN. Until this round there was no answer to WHETHER:
the shell started its waiting service at every launch, and that channel's beat
wakes the radio about 1440 times a day whether or not he wants notices on this
handset. The card now carries an OFF switch ABOVE the two WHEN rows — whether
it listens comes before when it listens.

- `noticeChannelSupported()` / `noticeChannelOn()` / `setNoticeChannel(on)`
  wrap the NEW bridge methods `Android.setNoticeChannel` /
  `Android.noticeChannelOn`. A NEW method, never an extra argument on an
  existing one: this page is served by the PC while the shell is installed
  separately, so a changed signature simply stops resolving on the phone in his
  hand.
- **Feature-detected, and the row is hidden entirely when the method is
  absent** — an older APK cannot act on it, and a row that cannot act is a
  promise the panel cannot keep.
- The row states the consequence in plain words: off, nothing listens and no
  notice can arrive on its own — the PC holds them in its 30-minute queue and
  he gets them the next time he opens Vibe Coder.
- While it is off the two WHEN rows are DIMMED (`.sets-row.dict.chan-off` in
  panels.css) — they decide nothing then. Dimmed by BACKGROUND and BORDER,
  never `opacity`: opacity multiplies against the card and drops a token that
  passes 4.5:1 below it (task 233's own measured lesson), and these rows are
  two full sentences he must still be able to read.
- The switch acts on the phone immediately (`NoticeService.setEnabled`
  starts or stops the service) as well as being read at the next launch.

Gate: the two T80b checks in `tests/test_shell_battery.py` — the Kotlin half
is read from the source, since this repo has no JVM runner.

## THE LAST-RESORT RULE (task 226, owner ballot verdict)

`notifyPrefs()` reads what the switches below are set to; `handleNotify()`
never reads it directly — it reads `effectiveNotifyPrefs()`, which applies
one override: **if all three of `banner`/`speak`/`tone` are off, the banner
is answered ON anyway.** Muting every carrier at once is read as "give me
back whichever one costs the least", never as "send nothing" — the banner
needs no sound and is the only one of the three that still reaches him with
the screen off. The Phone card's banner switch is labelled to say this
("last resort — stays on if you mute the rest") so the override is never a
silent surprise. `notifyPrefs()` itself is untouched by the rule — it is the
raw, honestly-stored state the Phone card's UI reads back to show what he
actually ticked.

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

### Task 236 — the ordering that spent the tap before it could land

His THIRD report of this feature, and the page's half of it. The app is in the
BACKGROUND on another layout when the notification is tapped, so
`MainActivity.onNewIntent` nudges the page **at once** — before `onResume`,
while the page is still hidden and its socket is closed by rule (project
CLAUDE.md constraint 8). The old `__noticeJump` pulled the jump out of the
shell right there (the pull CLEARS it), `applyNoticeJump` called
`focusLayout`, and `state.js` dropped that message on the dead socket. A second
later the reconnect landed, the SERVER resumed the layout it remembered, and
the tap he had just made no longer existed anywhere: the previously open
layout, every time.

The rule now: **a jump is only ever pulled when it can be acted on.**
`noticeCanJump()` (the socket is OPEN) guards both `applyNoticeJump` and the
shell's nudge, so a jump the page cannot act on is left WHERE IT IS — in the
shell, unread, which also means a WebView reload cannot lose it — and the
first `layout_state` of the new connection is what pulls it. That call sits
ahead of the `layoutRestore` branch in `connection.js`, so the tap wins in
both orderings.

Gated in `tests/test_notify.py`: a second Playwright page carrying the shell
bridge from BEFORE its first line runs (`IN_APP` is a const read at load, and
the whole pull path is gated on it — a bridge injected afterwards proves
nothing), driving a real `layout_state` through the live socket with the server
resuming the OLD layout and `layoutRestore` pointing at it too.

## Per-device switches

`notifyPrefs()` / `saveNotifyPrefs()` in the shell's SharedPreferences (via
`prefGet`/`prefSet` — never bare localStorage, which splits per origin
between the LAN and Tailscale addresses):

- `banner` — the Android notification (default ON)
- `speak` — TextToSpeech (default ON)
- `tone` — the in-page chime (default **OFF**: it is the one that annoys when
  the phone sits on the desk beside the PC)

`saveNotifyPrefs()` was, until task 226, a function nothing called — the
switches existed in the read path and in `notifyPrefs()`'s defaults but had
no door on the phone to change them. The door is the Phone card's
"Notification channels" section
([Phone Panel](phone-panel.md)): one on/off row per key, saved through
`saveNotifyPrefs()` and re-read on the card's own re-render.

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
