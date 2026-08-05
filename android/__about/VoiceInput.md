# VoiceInput.kt — the dictation subsystem

Split from `MainActivity` on 2026-08-05 (THE STRUCTURE LAW). Runs the
`SpeechRecognizer` for the page's Mic switcher and talks back through
`evaluateJavascript` callbacks: `__voiceResult(text)` per utterance,
`__voiceEnd(reason)` per round (`"denied"` / `"unavailable"` / `"nolang"` /
`""`), `__voiceState(state)` for the Mic button's downloading look, and
`__voiceInfo(text)` — SILENT diagnostics the page forwards to the PC's
server log (owner round 2, angrily: never a panel flashed at the user).

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
