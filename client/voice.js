// Voice — the dictation TEXT rules: WHICH recognized words reach the PC, and
// WHEN.
//
// Split out of controls.js on 2026-08-08 (THE STRUCTURE LAW) at exactly the
// wall sets.js was split off at on 2026-08-06: controls.js stood at 974 of its
// 1,000 lines and dictation had just grown a second rule. Both rules live on
// the PAGE rather than in `android/.../VoiceInput.kt` for two reasons — a rule
// that ships with the page reaches him without a new APK (CLAUDE.md constraint
// 12's own reasoning), and this repo has no JVM test runner, so a Kotlin-only
// rule cannot be proven by a fail-closed gate, which is exactly how task 75
// shipped half-done.
//
// The module is PURE on purpose — no DOM, no socket, no Android bridge — so
// `tests/test_voice_dedup.py` runs it WHOLE in node (the sets.js pattern).
// controls.js owns the mic switcher and does the typing; every function here
// only answers "which words may go out now?".
//
// ── RULE 1: THE STREAM (owner 2026-08-08) ─────────────────────────────────
// His words: *"ne dopuštamo da on čeka dok ja stanem sa govorom, već da
// namjerno izvlačimo iz njega tekst"*. An Android recognition round lasts as
// long as he keeps talking, so ten minutes of speech arrived as ONE lump at
// the end — and an interruption in the middle (his phone rings) took all of
// it: *"nestane sve što sam do sada pričao"*. The running hypothesis is
// therefore typed AS IT SETTLES, and the interruption costs only the tail.
//
// It cannot simply be typed as it ARRIVES. A recognizer revises what it
// guessed ("je" becomes "jeste" two words later) and we type into a FOREIGN
// application through SendInput: no composing region, no undo, NO WAY TO
// UNSEND A WORD. What Google's own keyboard may do inside its own text field
// we cannot do inside his. So only words the engine is done revising go out:
//
//     settled = outside the held tail  AND  unchanged since the last partial
//
// ── RULE 2: THE ROUND-BOUNDARY TRIM (task 75 REPEAT, 2026-08-08) ──────────
// A round that dies types a rescue of what it heard; 250 ms later the next
// round starts on the SAME live microphone and re-transcribes the tail of the
// same audio as an INDEPENDENT transcript ("Da li mogu Da li mogu da ih" — his
// own evidence). The trim is the longest suffix of what already went out that
// equals the prefix of what just came in, on word boundaries, case- and
// punctuation-insensitive. It never reaches INSIDE one hypothesis, so a phrase
// he genuinely repeated in one breath is never eaten.
//
// The two rules share ONE memory (`voiceLastOut`): a streamed word and a
// rescued word are both "already on the PC", and a round that dies after
// streaming must not re-type what streaming already delivered.

// ── State ─────────────────────────────────────────────────────────────────

// Every word already typed, across rounds — the trim's memory. Cleared by a
// final result (the utterance is over) and by the mic going off.
let voiceLastOut = "";

// The previous partial's words — the settle rule's second opinion — and how
// many words of THIS round's hypothesis have already been typed. Both belong
// to the running round only: the next round is an independent transcript, so
// its word indices mean nothing here.
let voiceStreamPrev = [];
let voiceStreamSent = 0;

// How many words are held back at the tail of a LIVE hypothesis.
//
// WHY 3. The engine rescores the phrase it is still forming, so a revision
// lands in the last one to three words and essentially never further back —
// that is the whole premise of typing early, and the number has to cover it
// with a little room. Three words is also the length the re-heard fragments of
// RULE 2 ran to in his own evidence (1-4 words: "Da li mogu", "sa onih
// terminala"), so a shorter hold would let a duplicate out before the overlap
// has enough words to be recognized at all. At normal dictation speed (~2.5
// words/s) it is ~1.2 s — the text still visibly follows him, and 1.2 s is
// what an interruption costs, which is the number this whole task is about.
// Larger drifts back towards the batch behaviour he asked us to end; smaller
// starts typing guesses into his prompt that we can never take back.
const VOICE_HOLD_WORDS = 3;

// ── Rules ─────────────────────────────────────────────────────────────────

function voiceNormWord(w) {
  return w.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
}

function voiceWords(text) {
  return text.split(/\s+/).filter(Boolean);
}

// RULE 2's core: the longest suffix of `lastWords` that equals the prefix of
// `rawWords`, compared word by normalized word (his evidence crossed a
// boundary as "Da li" -> "da li", and punctuation differs across rounds too).
function voiceOverlap(lastWords, rawWords) {
  for (let cand = Math.min(lastWords.length, rawWords.length); cand > 0; cand--) {
    const tail = lastWords.slice(lastWords.length - cand);
    if (tail.every((w, i) => voiceNormWord(w) === voiceNormWord(rawWords[i]))) return cand;
  }
  return 0;
}

// How many leading words of a hypothesis are already ON the PC: the boundary
// overlap (a tail re-heard from the previous round) or what this round has
// already streamed, whichever reaches further. Each covers the other's blind
// spot — a revised head defeats the overlap, and a fresh round zeroes the
// count — and between them no word can ever be typed twice.
function voiceCovered(words) {
  return Math.max(voiceOverlap(voiceWords(voiceLastOut), words), voiceStreamSent);
}

function voiceRemember(out) {
  voiceLastOut = voiceLastOut ? `${voiceLastOut} ${out}` : out;
}

// The round is over, or the mic went off: the next hypothesis is independent.
function voiceStreamReset() {
  voiceStreamPrev = [];
  voiceStreamSent = 0;
}

/** RULE 1. A LIVE partial from the shell — returns the words that have
 *  SETTLED and may be typed now ("" while nothing has).
 *
 *  A word settles when it is outside the held tail AND unchanged since the
 *  previous partial. The second test is not redundant: the first assumes the
 *  engine dribbles words out one at a time, and when it instead jumps four
 *  words at once those words have had NO chance to be revised yet, however
 *  far from the tail they land. It costs one partial interval (~0.3 s) in
 *  exactly that case and nothing at all in the ordinary one, and a word it
 *  holds is never lost — the next partial, or the round's end, releases it.
 *
 *  What goes out is always a contiguous prefix: we type sequentially into a
 *  box we do not own, so a hole cannot be filled in later. */
function voiceStream(raw) {
  const words = voiceWords(raw);
  const prev = voiceStreamPrev;
  voiceStreamPrev = words;
  let agreed = words.length;
  for (let i = 0; i < words.length; i++) {
    if (i >= prev.length || voiceNormWord(prev[i]) !== voiceNormWord(words[i])) {
      agreed = i;
      break;
    }
  }
  const settled = Math.min(agreed, words.length - VOICE_HOLD_WORDS);
  const from = voiceCovered(words);
  if (settled <= from) return "";
  const out = words.slice(from, settled).join(" ");
  voiceStreamSent = settled;
  voiceRemember(out);
  return out;
}

/** RULE 2, and the flush. A round ENDED: `isFinal` true for a real result,
 *  false for the rescue copy of a round that died. Either way everything
 *  still held is released here — so an interruption costs the tail and never
 *  the monologue — with whatever streaming already sent trimmed off the
 *  front.
 *
 *  A final that CORRECTS an already-typed word cannot be applied. We do not
 *  own that PC text box: blind backspaces would eat whatever the caret is
 *  really sitting in (he may have clicked elsewhere, an autocomplete menu may
 *  have moved it, the server's focus guard may have re-targeted the window),
 *  and a wrong word we can read and fix beats deleting text nobody asked us
 *  to touch. So the correction is dropped and only the new tail goes out. */
function voiceDedup(raw, isFinal) {
  const rawWords = voiceWords(raw);
  const from = voiceCovered(rawWords); // reads voiceStreamSent — BEFORE the reset
  voiceStreamReset();
  if (!rawWords.length) return "";
  const out = rawWords.slice(from).join(" ");
  if (isFinal) voiceLastOut = ""; // the utterance is over — the next one is new
  else if (out) voiceRemember(out);
  return out;
}
