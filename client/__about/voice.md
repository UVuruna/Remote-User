# voice.js — the dictation text rules

**Script:** [Voice (script)](../voice.js) · **Flow:** [Voice (flow)](../__flow/voice.md)

## Purpose

WHICH recognized words reach the PC, and WHEN. Two rules, one memory:

1. **The stream** — the running hypothesis is typed **as it settles**, while
   he is still speaking.
2. **The round-boundary trim** — a tail re-heard by the next listening round
   is never typed a second time.

Split out of [Controls](controls.md) on 2026-08-08 (THE STRUCTURE LAW), at
exactly the 1,000-line wall [Sets](sets.md) was split off at two days
earlier: controls.js stood at 974 lines and dictation had just grown a second
rule.

## Why the rules live on the page

Two reasons, and both are lessons this project already paid for:

- a rule that ships with the PAGE reaches him with the PC's next release, not
  with a new APK (CLAUDE.md constraint 12's own reasoning for the gamepad
  mapping);
- this repo has **no JVM test runner**, so a rule written in
  `VoiceInput.kt` cannot be proven by a fail-closed gate — which is exactly
  how task 75 shipped half-done the first time.

The module is therefore **pure**: no DOM, no socket, no Android bridge. That
is what lets `tests/test_voice_dedup.py` run it WHOLE in node (the
[Sets](sets.md) pattern), and a gate check fails the build if the purity is
ever broken. The shell hands text over; controls.js does the typing.

## Rule 1 — the stream (owner 2026-08-08)

His words: *"ne dopuštamo da on čeka dok ja stanem sa govorom, već da namjerno
izvlačimo iz njega tekst"* — and the reason, which is the real requirement:
*"mogu da pričam 10 minuta bez prestanka a onda ne upiše ni 1 reč... usred
toga dođe do prekida... nestane sve što sam do sada pričao"*.

An Android recognition round lasts as long as he keeps talking. A ten-minute
instruction was therefore ONE delivery at the end, and any interruption in the
middle — his phone ringing — took all of it.

It cannot simply be typed as it ARRIVES, either. A recognizer revises what it
guessed ("je" becomes "jeste" two words later) and we type into a FOREIGN
application through SendInput: no composing region, no undo, **no way to
unsend a word**. What Google's own keyboard may do inside its own text field
we cannot do inside his. So a word goes out only once it has **settled**:

    settled = outside the held tail  AND  unchanged since the previous partial

- **The held tail** is `VOICE_HOLD_WORDS` (3). The engine rescores the phrase
  it is still forming, so a revision lands in the last one to three words and
  essentially never further back. Three is also the length the re-heard
  fragments of rule 2 ran to in his own evidence (1-4 words), so a shorter
  hold would let a duplicate out before the overlap has enough words to be
  recognized at all. At ~2.5 words/s it is ~1.2 s — the text visibly follows
  him, and 1.2 s is what an interruption costs.
- **Unchanged since the previous partial** is not redundant with it. The tail
  rule assumes the engine dribbles words out one at a time; when it instead
  jumps four words at once, those words have had no chance to be revised
  however far from the tail they land. The second test costs one partial
  interval (~0.3 s) in exactly that case and nothing at all in the ordinary
  one, and a word it holds is never lost — the next partial, or the round's
  end, releases it.

What goes out is always a **contiguous prefix**: we type sequentially into a
box we do not own, so a hole could never be filled in later.

**A final that CORRECTS an already-typed word cannot be applied.** Blind
backspaces would eat whatever the PC caret is really sitting in — he may have
clicked elsewhere, an autocomplete menu may have moved it, the server's
[Focus Guard](../../server/__about/focus_guard.md) may have re-targeted the
window. A wrong word he can see and fix beats deleting text nobody asked us to
touch, so the correction is dropped and only the new tail goes out.

## Rule 2 — the round-boundary trim (task 75 REPEAT, 2026-08-08)

A round that dies types a rescue of what it heard; 250 ms later the next round
starts on the SAME live microphone and re-transcribes the tail of the same
audio as an INDEPENDENT transcript — his own evidence, dictated to us: *"Da li
mogu Da li mogu da ih zatvaram"*. `VoiceInput.kt`'s old `lastOut.startsWith`
prefix trim only ever caught a continuation of the SAME round.

`voiceOverlap` finds the longest **suffix** of what already went out that
equals the **prefix** of what just came in, word by normalized word (case- and
punctuation-insensitive: his evidence crossed a boundary as "Da li" → "da li").
It never reaches INSIDE one hypothesis, so a phrase he genuinely repeated in
one breath is never eaten.

## One memory, two rules

`voiceLastOut` holds every word already typed. A streamed word and a rescued
word are equally "already on the PC", so a round that dies after streaming
flushes only the tail it was still holding. `voiceCovered` takes the FURTHER
of two answers — the boundary overlap and this round's own sent count — because
each covers the other's blind spot: a revised head defeats the overlap, and a
fresh round zeroes the count.

## Connections

### Uses

Nothing. The module is pure by design (see above).

### Used by

- [Controls](controls.md) — `window.__voicePartial` runs `voiceStream` on every
  live partial, `window.__voiceHeard` runs `voiceDedup` at each round's end,
  and `micStop()` clears both memories (`voiceLastOut`, `voiceStreamReset()`)
- [VoiceInput.kt](../../android/__about/VoiceInput.md) — the shell that
  produces the partials and the round-end text
- [Tests (folder)](../../tests/___tests.md) — `test_voice_dedup.py` runs this
  module whole in node, over realistic partial SEQUENCES
