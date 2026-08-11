"""Voice Gate: dictation types WHILE he speaks, and never types twice.

TWO rules, one module — `client/voice.js` (split out of controls.js on
2026-08-08 under THE STRUCTURE LAW, at the same 1,000-line wall sets.js was
split off at):

  RULE 1 — THE STREAM (owner 2026-08-08). His words: *"ne dopuštamo da on
  čeka dok ja stanem sa govorom, već da namjerno izvlačimo iz njega tekst"* —
  and the reason: *"mogu da pričam 10 minuta bez prestanka a onda ne upiše ni
  1 reč... usred toga dođe do prekida... nestane sve što sam do sada
  pričao"*. An Android round lasts as long as he keeps talking, so a ten
  minute instruction was one lump delivered at the end, and an interruption
  in the middle took all of it. The hypothesis is now typed AS IT SETTLES,
  which is also what bounds the loss: at most the held tail.
  We type into a FOREIGN app through SendInput and CANNOT UNSEND, so "settled"
  is a real question, not a formality — the checks below drive whole partial
  SEQUENCES, with a revision planted mid-stream, because a rule about
  revisions cannot be proven by one call.

  RULE 2 — THE ROUND-BOUNDARY TRIM (below), unchanged in meaning: streaming
  only made it matter more, since a round now dies with most of its words
  already on the PC.

--- RULE 2's history (task 75, and why it came back) ---------------------

REPEAT of task 75 (closed 0.0.293 / APK 0.0.091). His server.log carried 177
lines of `Phone: [voice] Voice error 5 (online)` (ERROR_CLIENT) in one
dictation session (00:12:50 -> 00:18:45, roughly every 3 s), and his own
dictated message to us that morning showed the NEW shape:

    "sa onih terminala ne znam ni ja koliko je otvoreno"
    "vidim neke reči neke reči dupliraju se dupliraju se reči"
    "Da li mogu Da li mogu da ih zatvaram"

A 1-4 word fragment repeated ONCE, at short intervals — NOT the OLD 40x
cumulative shred task 75 actually fixed (a round retried every 250 ms
re-typing its own growing partial), but a NEW, smaller failure AT THE
BOUNDARY between two rounds: a round that dies types a rescue of what it
heard so far, and 250 ms later the next round starts on the SAME live
microphone and re-transcribes the tail of the same audio as an INDEPENDENT
transcript, not a continuation — so `VoiceInput.kt`'s old
`lastOut.startsWith()` prefix trim never caught it.

PROCESS CAUSE (root CLAUDE.md law 6, THE REPEAT LAW): the 0.0.293 round
tested that a dying round types what it heard, and that a RETRIED round
(the SAME round, restarted after ERROR_CLIENT) does not re-type its own
cumulative partial. It never asked what a SECOND round — a fresh transcript
over the same live audio — does with what the first round already sent.
"The phone types something" was proven; "the phone types it once, across
the whole session" never was. That is a class of gap, not an oversight: a
feature tested for the exact failure shape it was written to fix, and for no
other failure shaped like it — and the answer was sitting in the same log
the fix was read from (forty ERROR_CLIENTs then, a hundred seventy-seven now).

The rule now lives on the PAGE (`client/voice.js`, owner design 2026-08-08)
instead of in VoiceInput.kt, precisely so it CAN be proven: this repo has no
JVM test runner, and an untestable Kotlin-only fix is exactly how task 75
shipped half-done the first time. This gate runs that module WHOLE in node —
a FRESH interpreter per scenario, so every test starts from a clean
`voiceLastOut` exactly like a fresh mic session would. voice.js is kept PURE
(no DOM, no socket, no bridge) so that whole-file run is possible at all, and
a check below fails the build if that purity is ever broken.

Run:  .venv\\Scripts\\python tests/test_voice_dedup.py
Requires: node on PATH — a HARD requirement (this gate is registered in
setup/build.py's release-blocking input_gate(), matching
test_link_recovery.py's node-is-mandatory precedent). Never skip it
silently: an unprovable fix is how task 75 shipped once already.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
VOICE = PROJECT / "client" / "voice.js"
CONTROLS = PROJECT / "client" / "controls.js"
KOTLIN = (PROJECT / "android" / "app" / "src" / "main" / "java" / "com" /
          "uvuruna" / "vibecoder" / "VoiceInput.kt")


def fail(msg: str) -> None:
    raise AssertionError(msg)


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        fail("node is required for this gate (it runs the REAL "
             "client/voice.js rules) — install Node.js. Never skip "
             "a gate silently: an unprovable fix is how task 75 shipped "
             "once already.")
    return node


def _module() -> str:
    """The WHOLE of client/voice.js — it was split out of controls.js as a
    pure module precisely so this is possible (controls.js touches the DOM at
    load time and cannot run in node; sets.js set the precedent)."""
    text = VOICE.read_text(encoding="utf-8")
    for needed in ("let voiceLastOut", "const VOICE_HOLD_WORDS",
                   "function voiceNormWord", "function voiceWords",
                   "function voiceStream", "function voiceStreamReset",
                   "function voiceDedup"):
        if needed not in text:
            fail(f"{needed!r} left client/voice.js — the gate cannot find "
                 "what it must test")
    return text


def _run(script_body: str) -> dict:
    """Runs client/voice.js plus `script_body` (which must end by printing
    one JSON line) in a FRESH node process per call — a fresh interpreter, so
    every scenario starts from a clean voiceLastOut exactly like a fresh mic
    session would."""
    script = f"{_module()}\n{script_body}\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.mjs"
        path.write_text(script, encoding="utf-8")
        out = subprocess.run([_node(), str(path)], capture_output=True,
                              text=True, timeout=30)
    if out.returncode != 0:
        fail(f"node failed:\n{out.stderr}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def check_rescue_then_next_round_trims_the_overlap() -> None:
    """His shape exactly: a rescue is sent, the round dies, the next round's
    transcript re-hears the tail of the same audio. Only the genuinely NEW
    words may reach the PC."""
    out = _run("""
const first = voiceDedup("šta se dešava sa onih terminala", false);
const second = voiceDedup("sa onih terminala ne znam ni ja", false);
console.log(JSON.stringify({ first, second }));
""")
    if out["first"] != "šta se dešava sa onih terminala":
        fail(f"a first-ever call must pass through whole, got {out['first']!r}")
    if out["second"] != "ne znam ni ja":
        fail("the round-boundary overlap was not trimmed to the new words "
             f"only: got {out['second']!r}")


def check_case_difference_across_the_boundary_is_still_caught() -> None:
    """His own evidence: "Da li mogu Da li mogu da ih" — the SAME words,
    different capitalization, must still count as the same overlap."""
    out = _run("""
voiceDedup("Da li mogu", false);
const second = voiceDedup("da li mogu da ih zatvaram", false);
console.log(JSON.stringify({ second }));
""")
    if out["second"] != "da ih zatvaram":
        fail("a case-only difference at the boundary defeated the trim: "
             f"got {out['second']!r}")


def check_punctuation_across_the_boundary_is_still_caught() -> None:
    out = _run("""
voiceDedup("reči.", false);
const second = voiceDedup("reči, dupliraju se", false);
console.log(JSON.stringify({ second }));
""")
    if out["second"] != "dupliraju se":
        fail("a punctuation-only difference at the boundary defeated the "
             f"trim: got {out['second']!r}")


def check_final_after_a_rescue_is_trimmed_not_retyped() -> None:
    """Path B: a rescue already reached the PC and cannot be unsent — a
    FINAL that repeats it must add only the genuinely new tail, never the
    whole utterance again."""
    out = _run("""
voiceDedup("šta se dešava", false);
const fin = voiceDedup("šta se dešava sa onih terminala", true);
console.log(JSON.stringify({ fin }));
""")
    if out["fin"] != "sa onih terminala":
        fail("a final arriving after a rescue re-typed instead of adding "
             f"only the new tail: got {out['fin']!r}")


def check_final_with_no_rescue_passes_through_whole() -> None:
    out = _run("""
const fin = voiceDedup("Hello world", true);
console.log(JSON.stringify({ fin }));
""")
    if out["fin"] != "Hello world":
        fail("a final with nothing sent before it must pass through "
             f"unchanged, got {out['fin']!r}")


def check_a_genuine_repeat_within_one_round_is_never_eaten() -> None:
    """He can genuinely repeat himself in one breath — that repetition
    arrives inside a SINGLE call (one round produces one transcript), and
    this function only ever compares the START of a NEW call against the END
    of a PREVIOUS one. A fresh session (no prior lastOut) proves nothing
    inside the first call is ever touched."""
    out = _run("""
const once = voiceDedup("Da li Da li mogu da li mogu", false);
console.log(JSON.stringify({ once }));
""")
    if out["once"] != "Da li Da li mogu da li mogu":
        fail("a phrase repeated within ONE round's own transcript was "
             f"eaten: got {out['once']!r}")


def check_boundary_trim_never_reaches_past_the_first_overlap() -> None:
    """The adversarial version of the check above: a round boundary overlap
    AND a genuine same-round repeat land in the SAME call. "on je rekao" was
    already sent; the next round's own transcript happens to start with it
    (the real boundary artifact) and then say it AGAIN on purpose. Only the
    FIRST occurrence — the one that is actually the boundary artifact — may
    be trimmed; the second, genuine one must survive untouched."""
    out = _run("""
voiceDedup("on je rekao", false);
const second = voiceDedup("on je rekao on je rekao dodji", false);
console.log(JSON.stringify({ second }));
""")
    if out["second"] != "on je rekao dodji":
        fail("the boundary trim either ate the genuine repeat or failed to "
             f"trim the real boundary artifact: got {out['second']!r}")


def check_final_clears_state_for_the_next_utterance() -> None:
    """After a final, voiceLastOut resets — the next utterance owes nothing
    to the last one, even if the words happen to repeat."""
    out = _run("""
voiceDedup("prva recenica", true);
const next = voiceDedup("prva recenica opet", false);
console.log(JSON.stringify({ next }));
""")
    if out["next"] != "prva recenica opet":
        fail("a final did not clear the boundary memory — the next "
             f"utterance was trimmed against the previous one: got {out['next']!r}")


def check_resetting_voiceLastOut_clears_the_boundary_memory() -> None:
    """The state contract micStop() relies on (client/controls.js sets
    `voiceLastOut = ""` when the mic goes off) — proven here directly
    against the variable this block actually exports, so a rename of
    `voiceLastOut` breaks THIS test rather than silently detaching from
    micStop()."""
    out = _run("""
voiceDedup("ranije receno", false);
voiceLastOut = ""; // what micStop() does when the mic goes off
const next = voiceDedup("ranije receno opet", false);
console.log(JSON.stringify({ next }));
""")
    if out["next"] != "ranije receno opet":
        fail(f"clearing voiceLastOut did not reset the dedup memory: got {out['next']!r}")


# ── RULE 1: the stream (owner 2026-08-08) ────────────────────────────────
# These drive whole partial SEQUENCES. One call proves nothing about a rule
# whose whole subject is how a hypothesis CHANGES between calls — that is the
# same class of gap the header names for task 75.

# The scenario the next four checks share: one uninterrupted breath, the
# recognizer growing its hypothesis one word at a time.
BREATH = [
    "danas",
    "danas idemo",
    "danas idemo u",
    "danas idemo u grad",
    "danas idemo u grad da",
    "danas idemo u grad da kupimo",
    "danas idemo u grad da kupimo hleb",
    "danas idemo u grad da kupimo hleb i",
    "danas idemo u grad da kupimo hleb i mleko",
]
BREATH_JS = json.dumps(BREATH)


def check_a_growing_partial_stream_types_as_he_speaks() -> None:
    """His first ask: the text appears WHILE he talks. Everything settled goes
    out mid-round; the unsettled tail never does."""
    out = _run(f"""
const emitted = {BREATH_JS}.map((p) => voiceStream(p));
console.log(JSON.stringify({{ emitted, typed: emitted.filter(Boolean).join(" ") }}));
""")
    if out["typed"] != "danas idemo u grad da kupimo":
        fail("the stream did not type the settled words as they settled: "
             f"got {out['typed']!r}")
    if not any(out["emitted"][:6]):
        fail("nothing was typed until the round was nearly over — this is the "
             "batch behaviour he asked us to end")
    for held in ("hleb", "i", "mleko"):
        if held in out["typed"].split():
            fail(f"the unsettled tail word {held!r} was typed while the "
                 "recognizer could still revise it — we cannot unsend it")


def check_the_final_flushes_exactly_the_remainder() -> None:
    """Across the WHOLE round: no word lost, no word doubled. The final's own
    text is the reference — what the PC ends up with must equal it."""
    out = _run(f"""
const emitted = {BREATH_JS}.map((p) => voiceStream(p));
const fin = voiceDedup("danas idemo u grad da kupimo hleb i mleko", true);
console.log(JSON.stringify({{ emitted, fin,
  typed: emitted.filter(Boolean).concat([fin]).join(" ") }}));
""")
    if out["fin"] != "hleb i mleko":
        fail(f"the final flushed the wrong remainder: got {out['fin']!r}")
    if out["typed"] != "danas idemo u grad da kupimo hleb i mleko":
        fail("streaming plus the final did not reproduce the utterance "
             f"exactly once: got {out['typed']!r}")


def check_a_round_that_dies_mid_stream_loses_only_the_tail() -> None:
    """His phone rings. The round dies and delivers its rescue copy — which
    must add ONLY the words the settle rule was still holding, because
    everything before them is already on the PC."""
    out = _run(f"""
const emitted = {BREATH_JS}.map((p) => voiceStream(p));
const rescue = voiceDedup({BREATH_JS}[{len(BREATH)} - 1], false);
console.log(JSON.stringify({{ rescue,
  typed: emitted.filter(Boolean).concat([rescue]).join(" ") }}));
""")
    if out["rescue"] != "hleb i mleko":
        fail("a dying round re-typed what streaming already delivered "
             f"instead of only the held tail: got {out['rescue']!r}")
    if out["typed"] != "danas idemo u grad da kupimo hleb i mleko":
        fail(f"an interrupted round did not deliver its speech exactly once: "
             f"got {out['typed']!r}")


def check_the_next_round_after_a_streamed_rescue_still_trims() -> None:
    """RULE 2 under RULE 1: the rescue is sent, the round is over, and the
    NEXT round re-transcribes the tail of the same live audio. The stream must
    stay silent until genuinely new speech arrives."""
    out = _run(f"""
{BREATH_JS}.forEach((p) => voiceStream(p));
voiceDedup({BREATH_JS}[{len(BREATH)} - 1], false);
const next = [
  "hleb", "hleb i", "hleb i mleko", "hleb i mleko a",
  "hleb i mleko a onda", "hleb i mleko a onda kuci",
  "hleb i mleko a onda kuci idemo",
].map((p) => voiceStream(p));
console.log(JSON.stringify({{ next, typed: next.filter(Boolean).join(" ") }}));
""")
    if out["typed"] != "a":
        fail("the next round's re-heard tail was streamed to the PC a second "
             f"time: got {out['typed']!r}")


def check_a_revised_word_is_never_typed_wrong_and_never_typed_twice() -> None:
    """The revision planted mid-stream: the engine hears "je", then corrects
    it to "jeste" two partials later. "je" must never reach the PC (we could
    not take it back), and the corrected word must arrive exactly once."""
    out = _run("""
const emitted = [
  "ja", "ja mislim", "ja mislim da", "ja mislim da je",
  "ja mislim da jeste", "ja mislim da jeste to",
  "ja mislim da jeste to dobro",
].map((p) => voiceStream(p));
const fin = voiceDedup("Ja mislim da jeste to dobro", true);
console.log(JSON.stringify({ emitted, fin,
  typed: emitted.filter(Boolean).concat([fin]).join(" ") }));
""")
    if "je" in out["typed"].split():
        fail("the guess 'je' was typed before the engine had finished "
             f"revising it — it cannot be unsent: got {out['typed']!r}")
    if out["typed"] != "ja mislim da jeste to dobro":
        fail("a revised tail was not delivered exactly once: "
             f"got {out['typed']!r}")


def check_a_final_that_corrects_a_typed_word_adds_only_the_tail() -> None:
    """The unfixable case, stated as behaviour: the final disagrees with a
    word that IS already on the PC ("da" was streamed; the final calls it
    "dva"). We do not own that text box, so the correction is DROPPED — and
    the changed word must not defeat the boundary trim into re-typing the
    words around it. This is the check that proves the second half of
    `voiceCovered`: the overlap finds nothing here, and the round's own sent
    count is what holds the line."""
    out = _run("""
const emitted = ["ja", "ja mislim", "ja mislim da", "ja mislim da nesto",
 "ja mislim da nesto tako", "ja mislim da nesto tako jeste"]
   .map((p) => voiceStream(p));
const fin = voiceDedup("ja mislim dva nesto tako jeste danas", true);
console.log(JSON.stringify({ typed: emitted.filter(Boolean).join(" "), fin }));
""")
    if out["typed"] != "ja mislim da":
        fail(f"the stream under test did not type 'da': got {out['typed']!r}")
    if out["fin"] != "nesto tako jeste danas":
        fail("a final that corrected an already-typed word re-typed the "
             f"words around it: got {out['fin']!r}")
    if "dva" in out["fin"].split():
        fail("the correction 'dva' was typed on top of the 'da' already on "
             f"the PC, doubling the word: got {out['fin']!r}")


def check_a_word_new_in_this_partial_is_never_typed_yet() -> None:
    """The settle rule's SECOND test, alone. The engine jumps four words at
    once: they sit outside the held tail, but they have had no chance to be
    revised, so only the word confirmed by the previous partial may go."""
    out = _run("""
voiceStream("prva");
const burst = voiceStream("prva druga treca cetvrta peta");
const after = voiceStream("prva druga treca cetvrta peta sesta");
console.log(JSON.stringify({ burst, after }));
""")
    if out["burst"] != "prva":
        fail("a burst of words the recognizer had never shown before was "
             f"typed on sight: got {out['burst']!r}")
    if out["after"] != "druga treca":
        fail("a word held by the settle rule was never released on the next "
             f"partial: got {out['after']!r}")


def check_the_mic_going_off_resets_the_stream_memory() -> None:
    """The state contract micStop() relies on: after the mic goes off, the
    SAME words must stream again — nothing may be suppressed as "already
    typed" from a session that is over."""
    out = _run("""
voiceStream("a b c d");
const first = voiceStream("a b c d");
voiceLastOut = "";     // what micStop() does when the mic goes off
voiceStreamReset();    // ...and the round in flight is abandoned with it
voiceStream("a b c d");
const again = voiceStream("a b c d");
console.log(JSON.stringify({ first, again }));
""")
    if out["first"] != "a" or out["again"] != "a":
        fail("the mic-off reset did not clear the streaming memory: "
             f"got {out!r}")


def check_micStop_also_resets_the_stream_state() -> None:
    """The WIRING of the check above: a mic session that ends mid-round must
    not leave its word count behind, or the next session's first words are
    silently swallowed as "already typed"."""
    text = CONTROLS.read_text(encoding="utf-8")
    m = re.search(r"function micStop\(\)\s*\{(.*?)\n\}", text, re.S)
    if not m:
        fail("micStop() not found in client/controls.js")
    if "voiceStreamReset(" not in m.group(1):
        fail("micStop() no longer resets the streaming state — the next "
             "dictation session would swallow its own first words")


def check_the_shell_streams_partials_and_the_page_receives_them() -> None:
    """The lesson of 2026-08-07 ("a field we invent must be PROVEN to reach
    HIS file"): a rule nobody calls is a feature that does not exist. Both
    ends of the new bridge are checked here — the shell forwarding every
    partial, and the page routing it into the settle rule."""
    kt = KOTLIN.read_text(encoding="utf-8")
    m = re.search(r"override fun onPartialResults\(.*?\n        \}", kt, re.S)
    if not m:
        fail("onPartialResults not found in VoiceInput.kt")
    if "stream(" not in m.group(0):
        fail("VoiceInput.onPartialResults no longer forwards the live "
             "partial — dictation is back to typing only when he stops")
    if "__voicePartial" not in kt:
        fail("VoiceInput.kt never names __voicePartial — the shell would be "
             "streaming into nothing")
    controls = CONTROLS.read_text(encoding="utf-8")
    if "window.__voicePartial" not in controls:
        fail("client/controls.js does not define window.__voicePartial — the "
             "shell's stream would land nowhere")
    m = re.search(r"window\.__voicePartial = .*?\n\};", controls, re.S)
    if not m or "voiceStream(" not in m.group(0):
        fail("window.__voicePartial does not run the settle rule "
             "(voiceStream) — raw partials would be typed unrevised")


def check_the_lock_button_still_stops_everything() -> None:
    """Owner round 4 (2026-08-05), unweakened by streaming: onBackground must
    cancel the round and clear every piece of state, and no partial already in
    flight from the recognizer's own process may be forwarded after it."""
    kt = KOTLIN.read_text(encoding="utf-8")
    m = re.search(r"fun onBackground\(\)\s*\{(.*?)\n    \}", kt, re.S)
    if not m:
        fail("onBackground() not found in VoiceInput.kt")
    body = m.group(1)
    for needed in ("background = true", "cancel()", "partial = \"\"",
                   "streaming = false"):
        if needed not in body:
            fail(f"onBackground() no longer does {needed!r} — the LOCK button "
                 "must stop EVERYTHING (owner round 4)")


def check_the_hold_is_a_named_constant_with_its_reasoning() -> None:
    """rules/CODE.md: no magic numbers. The hold is the number that decides
    both how fast the text follows him and what an interruption costs, so it
    is named, reasoned about where it is defined, and used by the settle
    computation rather than being re-typed as a literal."""
    text = VOICE.read_text(encoding="utf-8")
    m = re.search(r"const VOICE_HOLD_WORDS = (\d+);", text)
    if not m:
        fail("VOICE_HOLD_WORDS is no longer a named constant in voice.js")
    if not (1 <= int(m.group(1)) <= 6):
        fail(f"VOICE_HOLD_WORDS = {m.group(1)} is outside anything defensible: "
             "smaller types guesses that cannot be unsent, larger drifts back "
             "to the batch behaviour the owner asked us to end")
    head = text[:m.start()]
    if "WHY" not in head[-1200:]:
        fail("the reasoning for VOICE_HOLD_WORDS left its comment — the "
             "number is a judgement call and must carry the judgement")
    if text.count("VOICE_HOLD_WORDS") < 2:
        fail("VOICE_HOLD_WORDS is defined but never used")


def check_voice_js_stays_pure() -> None:
    """This gate runs the module WHOLE in node — that is only possible while
    voice.js touches no DOM, no socket and no Android bridge. A rule that
    reaches for them belongs in controls.js, and this check is what stops the
    module from quietly becoming untestable again."""
    text = VOICE.read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines()
                     if not ln.lstrip().startswith(("//", "*", "/*")))
    for forbidden in ("document", "window.", "send(", "Android"):
        if forbidden in code:
            fail(f"client/voice.js reaches for {forbidden!r} — it must stay "
                 "pure so the gate can run it whole (the sets.js pattern)")


def check_micStop_actually_clears_voiceLastOut() -> None:
    """The functional check above proves the CONTRACT; this proves the
    WIRING — that micStop() in client/controls.js really does clear
    voiceLastOut, not just that clearing it would work if something did."""
    text = CONTROLS.read_text(encoding="utf-8")
    m = re.search(r"function micStop\(\)\s*\{(.*?)\n\}", text, re.S)
    if not m:
        fail("micStop() not found in client/controls.js")
    if "voiceLastOut = " not in m.group(1):
        fail("micStop() no longer resets voiceLastOut — a session that ends "
             "mid-rescue would leak its tail into the NEXT dictation session")


CHECKS = [
    ("rescue then next round trims the overlap (his exact shape)",
     check_rescue_then_next_round_trims_the_overlap),
    ("a case difference across the boundary is still caught",
     check_case_difference_across_the_boundary_is_still_caught),
    ("a punctuation difference across the boundary is still caught",
     check_punctuation_across_the_boundary_is_still_caught),
    ("a final after a rescue is trimmed, not retyped (Path B)",
     check_final_after_a_rescue_is_trimmed_not_retyped),
    ("a final with no rescue passes through whole",
     check_final_with_no_rescue_passes_through_whole),
    ("a genuine repeat within one round's own transcript is never eaten",
     check_a_genuine_repeat_within_one_round_is_never_eaten),
    ("a boundary trim never reaches past the first overlap",
     check_boundary_trim_never_reaches_past_the_first_overlap),
    ("a final clears state for the next utterance",
     check_final_clears_state_for_the_next_utterance),
    ("resetting voiceLastOut clears the boundary memory (the mic-off contract)",
     check_resetting_voiceLastOut_clears_the_boundary_memory),
    ("micStop() actually clears voiceLastOut (the wiring, not just the contract)",
     check_micStop_actually_clears_voiceLastOut),
    # RULE 1 — the stream (owner 2026-08-08)
    ("a growing partial stream types as he speaks, tail held",
     check_a_growing_partial_stream_types_as_he_speaks),
    ("the final flushes exactly the remainder — nothing lost, nothing doubled",
     check_the_final_flushes_exactly_the_remainder),
    ("a round that dies mid-stream loses only the held tail (his phone call)",
     check_a_round_that_dies_mid_stream_loses_only_the_tail),
    ("the next round after a streamed rescue still trims the re-heard tail",
     check_the_next_round_after_a_streamed_rescue_still_trims),
    ("a revised word is never typed wrong and never typed twice",
     check_a_revised_word_is_never_typed_wrong_and_never_typed_twice),
    ("a final that corrects a typed word adds only the tail",
     check_a_final_that_corrects_a_typed_word_adds_only_the_tail),
    ("a word new in THIS partial is not typed yet (the settle rule's 2nd test)",
     check_a_word_new_in_this_partial_is_never_typed_yet),
    ("the mic going off resets the streaming memory",
     check_the_mic_going_off_resets_the_stream_memory),
    ("micStop() also resets the stream state (the wiring)",
     check_micStop_also_resets_the_stream_state),
    ("the shell streams partials and the page receives them (both ends)",
     check_the_shell_streams_partials_and_the_page_receives_them),
    ("the LOCK button still stops everything (owner round 4)",
     check_the_lock_button_still_stops_everything),
    ("the hold is a named constant carrying its reasoning",
     check_the_hold_is_a_named_constant_with_its_reasoning),
    ("client/voice.js stays pure, so the gate can run it whole",
     check_voice_js_stays_pure),
]


def main() -> int:
    print("\n=== VOICE GATE ===")
    if shutil.which("node") is None:
        print("VOICE GATE FAILED — node is required (it runs the REAL "
              "client/voice.js rules) and is not on PATH. Never "
              "skip a gate silently: an unprovable fix is how task 75 "
              "shipped once already.")
        return 1
    failed = 0
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nVOICE GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nVOICE GATE PASSED — dictation types while he speaks, and never "
          "types a word twice.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
