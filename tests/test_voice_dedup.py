"""Voice Dedup Gate: dictation across a ROUND BOUNDARY never types twice.

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

The rule now lives on the PAGE (client/controls.js `voiceDedup`, owner
design 2026-08-08) instead of in VoiceInput.kt, precisely so it CAN be
proven: this repo has no JVM test runner, and an untestable Kotlin-only fix
is exactly how task 75 shipped half-done the first time. This gate runs the
REAL function, extracted from client/controls.js between the
VOICE_DEDUP_START/END markers, in node — a FRESH interpreter per scenario,
so every test starts from a clean `voiceLastOut` exactly like a fresh mic
session would.

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
CONTROLS = PROJECT / "client" / "controls.js"

START_MARKER = "// --- VOICE_DEDUP_START"
END_MARKER = "// --- VOICE_DEDUP_END"


def fail(msg: str) -> None:
    raise AssertionError(msg)


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        fail("node is required for this gate (it runs the REAL "
             "client/controls.js voiceDedup) — install Node.js. Never skip "
             "a gate silently: an unprovable fix is how task 75 shipped "
             "once already.")
    return node


def _extract_block() -> str:
    """Pulls the self-contained VOICE_DEDUP block out of client/controls.js
    by its markers, rather than running the whole file — controls.js touches
    `document`/DOM elements at top-level load time (unlike sets.js, which
    was written to be a pure module) and cannot run whole in node."""
    text = CONTROLS.read_text(encoding="utf-8")
    start = text.find(START_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end < start:
        fail("VOICE_DEDUP_START/END markers missing or out of order in "
             "client/controls.js — the gate cannot find what it must test")
    block = text[start:end]
    for needed in ("let voiceLastOut", "function voiceNormWord",
                   "function voiceWords", "function voiceDedup"):
        if needed not in block:
            fail(f"{needed!r} left the VOICE_DEDUP block in client/controls.js")
    return block


def _run(script_body: str) -> dict:
    """Runs the extracted block plus `script_body` (which must end by
    printing one JSON line) in a FRESH node process per call — a fresh
    interpreter, so every scenario starts from a clean voiceLastOut exactly
    like a fresh mic session would."""
    script = f"{_extract_block()}\n{script_body}\n"
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
]


def main() -> int:
    print("\n=== VOICE DEDUP GATE ===")
    if shutil.which("node") is None:
        print("VOICE DEDUP GATE FAILED — node is required (it runs the REAL "
              "client/controls.js voiceDedup) and is not on PATH. Never "
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
        print(f"\nVOICE DEDUP GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nVOICE DEDUP GATE PASSED — dictation never retypes across a "
          "round boundary.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
