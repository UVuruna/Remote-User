# VoiceInput.kt — the dictation subsystem

Split from `MainActivity` on 2026-08-05 (THE STRUCTURE LAW). Runs the
`SpeechRecognizer` for the page's Mic switcher and talks back through
`evaluateJavascript` callbacks: `__voiceHeard(text, isFinal)` per round — the
PREFERRED callback since 2026-08-08, with `__voiceResult(text)` as the
LEGACY fallback for a page that predates it (see "Round-boundary dedup moved
to the page" below) — `__voiceEnd(reason)` per round (`"denied"` /
`"unavailable"` / `"nolang"` / `""`), `__voiceState(state)` for the Mic
button's downloading look, and `__voiceInfo(text)` — SILENT diagnostics the
page forwards to the PC's server log (owner round 2, angrily: never a panel
flashed at the user).

## The language is a USER CHOICE (owner round 2, 2026-08-05)

Round-1 evidence: pinning to the phone's FIRST system locale transcribed the
owner's Serbian as English garbage — his phone lists English first. So:

- `candidates()` — JSON `[{tag, name, status}]` for the setup card: system
  locales + the keyboard's enabled languages (LANGUAGE-AGNOSTIC, nothing
  hardcoded); status `ready` (on-device model installed) / `download`
  (model exists, will be fetched) / `online` (internet recognition only).
- `chosenTag()` / `setChosen(tag)` — exactly ONE stored language
  (SharedPreferences `voice`); `""` means never chosen and `listen()` ends
  the round with `"nolang"` so the page opens the card instead.
- `listen()` — one round with `EXTRA_LANGUAGE = chosen`, ONE language
  everywhere: the round-1 silent gap was a wanted-but-missing language
  riding the on-device switch lists and hearing NOTHING with no error.

## Round 4 (owner 2026-08-05): lock, beeps, more languages

- **The LOCK button stops everything** — `onBackground()` (activity
  `onPause`) cancels the running round, unmutes, and refuses new `listen()`
  calls until `onForeground()`; the rounds used to keep cycling and beeping
  under a locked screen (the page's own visibility handler switches the mic
  OFF too — belt and braces).
- **Listening beeps muted by default** — Android tones every round
  start/stop and rounds cycle on each silence; `muteBeepsPref()` (default
  true, the card's checkbox flips it) mutes MUSIC/SYSTEM/NOTIFICATION for
  the listening session, restored on cancel/deny/background/destroy. Each
  stream is best-effort (DND policies may refuse one).
- **More languages** — `candidates()` marks with `extra: true` every
  language beyond the phone's own: all downloadable on-device models plus
  whatever the online service reports via the `ACTION_GET_LANGUAGE_DETAILS`
  broadcast (queried once); the card keeps them behind "More languages…".

## Engine choice + silent model download

`makeRecognizer`: on-device only when the chosen language's model is KNOWN
installed (`checkRecognitionSupport` evidence, not hope); otherwise Google's
online service pinned to the chosen language (the phone-default service —
Samsung's — garbled dictation outright, owner 2026-08-04), else the system
default. `checkSupport` runs once per app run — and again while a download
is pending: a missing-but-supported model auto-triggers
`triggerModelDownload` (the app drives its dependencies), `downloading`
styles the Mic button via `__voiceState`, dictation keeps working online on
the SAME language, and the moment the model lands the engine silently
rebuilds on-device (owner approved the silent switch).

## Nothing spoken is ever thrown away (owner 2026-08-06)
His words, shouted: *"izgovorim 10 rečenica, mikrofon nije ništa upisao... ja
pričam pola sata i neki program preseče i obriše sve što sam pričao"*.

A listening round delivers its text **only at the end** (`onResults`). Every
way a round can die before that — `ERROR_CLIENT` when something else takes the
recognition service, a network drop, the engine restarting — used to take
every word of that round with it, and the server log is full of exactly those
lines (`Voice error 5 (online)`, over and over).

So `EXTRA_PARTIAL_RESULTS` is ON, and `onPartialResults` keeps the running
hypothesis in `partial` as a **rescue copy**. Nothing is sent from it while the
round is alive — typing as he speaks would re-type the same sentence on every
update. `deliver()` is the only exit: a final result wins and clears the copy;
a round that dies without one types the copy instead. Either way the copy is
dropped, so no sentence can be typed twice.

This is the phone's half of the same failure the PC's
[Focus Guard](../../server/__about/focus_guard.md) answers: there, a program
that steals focus mid-dictation takes the window the words were meant for;
here, the same interruption used to take the words themselves.

## Round-boundary dedup moved to the page (task 75 REPEAT, 2026-08-08)

0.0.293 (above) fixed a round re-typing its OWN growing cumulative partial on
every retry. His server.log then showed **177** `Voice error 5 (online)`
(`ERROR_CLIENT`) lines in one dictation session, and his own dictated message
to us that morning showed a NEW, smaller shape — a 1-4 word fragment repeated
ONCE, at short intervals ("Da li mogu Da li mogu da ih zatvaram"). That is a
DIFFERENT bug: a round that dies types a rescue of what it heard; 250 ms
later the next round starts on the SAME live microphone and re-transcribes
the tail of the same audio as an INDEPENDENT transcript, not a continuation —
the OLD `lastOut.startsWith()` prefix trim only ever caught a continuation of
the SAME round, never an overlap between two DIFFERENT rounds.

The rule now lives in **`client/controls.js` `voiceDedup`** (owner design),
not here — this repo has no JVM test runner, so a Kotlin-only trim cannot be
proven by a fail-closed gate, which is exactly how the 0.0.293 fix shipped
provable for the case it was written for and unprovable for every other. See
[Controls](../../client/__about/controls.md) for the algorithm and
`tests/test_voice_dedup.py` for the proof. `deliver()` now hands
`__voiceHeard` the RAW per-round text plus `isFinal` and does no trimming of
its own on that path; the field `lastOut` and its old prefix trim survive
ONLY as a fallback for a page too old to define `__voiceHeard`.

**Investigated but NOT provable from this machine** — the 177 ERROR_CLIENTs
themselves, i.e. why rounds keep dying in the first place:

- `listen()` no longer calls `startListening()` synchronously right after
  `cancel()` on the same recognizer instance. Both calls post to this
  thread's message queue and run in order on OUR side, but the recognizer
  SERVICE they talk to lives in a separate process — our ordering does not
  guarantee its unbind finished before the rebind request lands. The start
  is now posted as a separate `Handler` message instead, giving the service
  one full run of the loop to settle the cancel first.
- `onError` now destroys and nulls `recognizer` specifically on
  `ERROR_CLIENT` — Android's own guidance is that the instance may be left
  unusable by it, and `listen()` lazily rebuilds.

Both are evidence-shaped, not proven; only his next server.log with this
build installed can confirm or refute the ERROR_CLIENT rate actually fell.
