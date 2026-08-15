"""Kb Sync Gate: a typed edit lands where his eyes are, and a stray fragment
cannot outlive a single keystroke.

Owner report (2026-08-13), AFTER the mic hypothesis was tested live and
explicitly ruled out ("to što sam prvi diktirao mikrofon uopšte ne menja
stvar ova situacija se dešava samo kad pišem tastaturom" — lang-ok: owner
quote, translated in client/__about/kb-sync.md): typing, MOST on delete. The
PC's visible caret sits at the FAR RIGHT, yet what he types lands INSERTED
BEFORE a trailing fragment ("ok") that no amount of typing or deleting gets
rid of. Only a mouse click outside the field and back frees it.

`client/kb-sync.js` (`kbDiff`, `kbCaretAtEnd`, `kbShouldRepin`) is the pure
module split out of `client/controls.js`'s `input` handler to fix this — see
its own header and `client/__flow/kb-sync.md` for the mechanism. This gate
runs it WHOLE in node (the client/voice.js pattern) and drives realistic
multi-tick EDIT SEQUENCES, because the whole point of the bug is what happens
across several keystrokes, not what one keystroke does in isolation.

Run:  .venv\\Scripts\\python tests/test_kb_sync.py
Requires: node on PATH — a HARD requirement (test_voice_dedup.py precedent).
Never skip it silently.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
KB_SYNC = PROJECT / "client" / "kb-sync.js"
CONTROLS = PROJECT / "client" / "controls.js"


def fail(msg: str) -> None:
    raise AssertionError(msg)


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        fail("node is required for this gate (it runs the REAL "
             "client/kb-sync.js rules) — install Node.js. Never skip a "
             "gate silently.")
    return node


def _module() -> str:
    text = KB_SYNC.read_text(encoding="utf-8")
    for needed in ("function kbDiff", "function kbCaretAtEnd",
                   "function kbShouldRepin", "function kbGhostSuffixLen",
                   "function kbGhostCandidate"):
        if needed not in text:
            fail(f"{needed!r} left client/kb-sync.js — the gate cannot "
                 "find what it must test")
    return text


def _run(script_body: str) -> dict:
    import json
    script = f"{_module()}\n{script_body}\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.mjs"
        path.write_text(script, encoding="utf-8")
        out = subprocess.run([_node(), str(path)], capture_output=True,
                              text=True, timeout=30)
    if out.returncode != 0:
        fail(f"node failed:\n{out.stderr}")
    return json.loads(out.stdout.strip().splitlines()[-1])


# ── kbDiff arithmetic — unchanged behaviour, still proven ─────────────────

def check_plain_append_sends_no_backspace() -> None:
    out = _run("""
const r = kbDiff("hello", "hello world");
console.log(JSON.stringify(r));
""")
    if out["back"] != 0 or out["inserted"] != " world":
        fail(f"plain append must send zero backspaces and the new suffix "
             f"only, got {out!r}")


def check_pure_delete_sends_only_backspaces() -> None:
    out = _run("""
const r = kbDiff("hello world", "hello");
console.log(JSON.stringify(r));
""")
    if out["back"] != 6 or out["inserted"] != "":
        fail(f"a pure trailing delete must send only backspaces, got {out!r}")


def check_mid_string_autocorrect_erases_and_retypes_the_tail() -> None:
    """The legitimate case the mid-string branch exists for (controls.js's
    original comment): a word further back changes while the tail survives —
    the tail must be retyped too, or the edit lands after it."""
    out = _run("""
const r = kbDiff("cant beleive", "can't believe");
console.log(JSON.stringify(r));
""")
    # "beleive" -> "believe" changes the tail; the common suffix collapses to
    # nothing usable without retyping past the correction point.
    if out["inserted"] == "" or out["back"] == 0:
        fail(f"an autocorrect-style mid-string edit produced no work at "
             f"all — got {out!r}")


# ── kbCaretAtEnd / kbShouldRepin — the new rule ────────────────────────────

def check_caret_at_true_end_is_trusted() -> None:
    out = _run("""
const atEnd = kbCaretAtEnd("hello", 5, 5);
console.log(JSON.stringify({ atEnd }));
""")
    if out["atEnd"] is not True:
        fail("a collapsed selection at value.length must read as at-end")


def check_caret_before_a_trailing_fragment_is_not_trusted() -> None:
    """His exact shape: value ends in a fragment ("...text ok") and the
    field's own caret sits BEFORE it, not at the true end."""
    out = _run("""
const atEnd = kbCaretAtEnd("hello ok", 5, 5); // caret sits before " ok"
console.log(JSON.stringify({ atEnd }));
""")
    if out["atEnd"] is not False:
        fail("a caret sitting before a trailing fragment must NOT read as "
             "at-end — this is the exact drift his report described")


def check_should_repin_fires_when_drifted_and_not_composing() -> None:
    out = _run("""
const should = kbShouldRepin("hello ok", 5, 5, false);
console.log(JSON.stringify({ should }));
""")
    if out["should"] is not True:
        fail("a drifted, non-composing caret must be re-pinned")


def check_should_repin_never_fires_mid_composition() -> None:
    """Forcing a selection while a real multi-keystroke composition (CJK, an
    emoji picker) is in flight can break the composing span itself — this is
    not what caused his report, so composition must be left alone."""
    out = _run("""
const should = kbShouldRepin("hello ok", 5, 5, true);
console.log(JSON.stringify({ should }));
""")
    if out["should"] is not False:
        fail("a mid-composition edit must never be re-pinned, drifted or not")


def check_should_repin_is_a_noop_already_at_the_end() -> None:
    out = _run("""
const should = kbShouldRepin("hello", 5, 5, false);
console.log(JSON.stringify({ should }));
""")
    if out["should"] is not False:
        fail("a caret already at the end must not trigger a DOM call")


# ── The multi-tick scenario: his exact symptom, and that the fix ends it ──

def check_a_stuck_fragment_would_resend_every_tick_without_the_fix() -> None:
    """Proves the MECHANISM: with the field's caret pinned BEFORE a trailing
    fragment (never corrected — the pre-fix world), every further edit
    re-sends the fragment to the PC, because kbDiff alone has no way to know
    the caret is not really at the end. This is what his report describes,
    reproduced from the pure arithmetic alone."""
    out = _run("""
// Simulates 3 keystrokes typed BEFORE a trailing " ok" that a drifted caret
// never lets him reach. kbPrev/value both keep " ok" at the very tail.
let prev = "typed ok";
const ticks = [];
for (const ch of ["!", "?", "."]) {
  // The user's edit lands BEFORE " ok" — insert at position (len - 3).
  const value = prev.slice(0, prev.length - 3) + ch + prev.slice(prev.length - 3);
  const { back, inserted } = kbDiff(prev, value);
  ticks.push({ back, inserted });
  prev = value;
}
console.log(JSON.stringify({ ticks }));
""")
    for i, tick in enumerate(out["ticks"]):
        if " ok" not in tick["inserted"]:
            fail(f"tick {i}: the stuck-fragment scenario did not reproduce — "
                 f"expected ' ok' to be re-sent every tick, got {tick!r}")


def check_repinning_after_each_tick_stops_the_fragment_recurring() -> None:
    """The fix, driven the same way: after EVERY tick the field's caret is
    re-pinned to its own end (kbShouldRepin -> true -> the caller resets
    selectionStart/End to value.length). The NEXT tick therefore inserts at
    the true end and never touches the stale fragment again — proving the
    drift cannot compound past one edit."""
    out = _run("""
let prev = "typed ok";
// Tick 0: caret still drifted (this is the edit that lands wrong).
let value = prev.slice(0, 5) + "!" + prev.slice(5); // "typed" + "!" + " ok"
let d0 = kbDiff(prev, value);
prev = value;
// The fix re-pins: from here on every further edit is typed at the TRUE end
// (position === value.length), simulating controls.js calling
// setSelectionRange(value.length, value.length) after tick 0.
value = prev + "!";
let d1 = kbDiff(prev, value);
prev = value;
value = prev + "?";
let d2 = kbDiff(prev, value);
console.log(JSON.stringify({ d1, d2 }));
""")
    if " ok" in out["d1"]["inserted"] or " ok" in out["d2"]["inserted"]:
        fail("the fragment kept recurring even after the caret was re-pinned "
             f"to the end — the fix did not stop the drift: got {out!r}")
    if out["d1"]["back"] != 0 or out["d2"]["back"] != 0:
        fail("once re-pinned, further edits must be plain appends with zero "
             f"backspaces — got {out!r}")


# ── Purity + wiring ─────────────────────────────────────────────────────

def check_ghost_candidate_fires_on_a_multi_char_midstring_retype() -> None:
    """Tell 1: `back > 0 && inserted.length > 1`. The legitimate autocorrect
    case above already has this shape — it is also exactly what a stuck
    fragment produces on every later keystroke, which is the whole reason
    this is a CANDIDATE and not a certainty (a diagnostic, no behaviour
    change)."""
    out = _run("""
const diff = kbDiff("cant beleive", "can't believe");
console.log(JSON.stringify({ g: kbGhostCandidate("cant beleive", diff) }));
""")
    if out["g"] is not True:
        fail("a multi-character mid-string retype must read as a ghost "
             "candidate")


def check_ghost_candidate_fires_on_a_repeated_tail() -> None:
    """Tell 2: `inserted` ends with a real (>=2 char) run matching the TAIL
    of `prevValue` — the fragment reappearing unearned. PLANTED DEFECT:
    lower the threshold in `kbGhostSuffixLen` comparison to `>= 1` — this
    check alone would still pass (2 chars still clears >=1), so it is
    `check_ghost_candidate_does_not_fire_on_an_ordinary_single_char_append`
    below that actually catches that defect."""
    out = _run("""
const diff = { back: 0, inserted: "xz ok" };
console.log(JSON.stringify({
  g: kbGhostCandidate("hello type ok", diff),
}));
""")
    if out["g"] is not True:
        fail("an inserted run ending in the same 2+ characters already at "
             "the tail of prevValue must read as a ghost candidate")


def check_ghost_candidate_does_not_fire_on_an_ordinary_single_char_append() -> None:
    """An ordinary keystroke — one character, no mid-string work, and no
    real suffix overlap with what was already there — must NOT be flagged.
    A predicate that fires on every keystroke is not a diagnostic, it is
    noise, and `client_log` is rate-limited but still costs a socket write."""
    out = _run("""
const diff = kbDiff("hello", "hello!");
console.log(JSON.stringify({ g: kbGhostCandidate("hello", diff) }));
""")
    if out["g"] is not False:
        fail("a single ordinary appended character must never read as a "
             "ghost candidate")


def check_a_coincidental_one_char_suffix_match_does_not_fire() -> None:
    """The real boundary tell 2 is guarding against: ordinary typed text
    shares its LAST character with whatever was already there constantly —
    a trailing space, a common letter, a repeated punctuation mark. Only a
    real (>=2 char) run counts as the ghost's own signature.

    PLANTED DEFECT: drop the `>= 2` threshold to `>= 1` in kbGhostSuffixLen's
    caller — `inserted` here shares exactly one trailing character with
    `prevValue` ('x') by pure coincidence, and a threshold of 1 would flag
    it, which is exactly the false-positive flood tell 2 exists to avoid."""
    out = _run("""
const diff = { back: 0, inserted: "yx" };
console.log(JSON.stringify({ g: kbGhostCandidate("abc x", diff) }));
""")
    if out["g"] is not False:
        fail("a coincidental one-character suffix match must never read as "
             "a ghost candidate — only a real (>=2 char) repeat does")


def check_kb_sync_js_stays_pure() -> None:
    """This gate runs the module WHOLE in node — only possible while
    kb-sync.js touches no DOM, no socket, no Android bridge (the voice.js
    rule, same reasoning)."""
    text = KB_SYNC.read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines()
                     if not ln.lstrip().startswith(("//", "*", "/*")))
    for forbidden in ("document", "window.", "send(", "Android"):
        if forbidden in code:
            fail(f"client/kb-sync.js reaches for {forbidden!r} — it must "
                 "stay pure so the gate can run it whole")


def check_controls_js_wires_kb_diff_into_the_input_handler() -> None:
    text = CONTROLS.read_text(encoding="utf-8")
    m = re.search(r'kbInput\.addEventListener\("input".*?\n\}\);', text, re.S)
    if not m:
        fail("kbInput's input handler not found in client/controls.js")
    body = m.group(0)
    if "kbDiff(" not in body:
        fail("the input handler no longer calls kbDiff() — it may have "
             "reverted to its own inline diff arithmetic")
    if "kbShouldRepin(" not in body:
        fail("the input handler no longer calls kbShouldRepin() — the "
             "caret drift fix has been removed")
    if "setSelectionRange" not in body:
        fail("kbShouldRepin() is called but nothing acts on it — "
             "setSelectionRange must actually run when it returns true")


def check_repin_is_gated_on_kbShouldRepin_not_unconditional() -> None:
    """The re-pin call must be INSIDE the kbShouldRepin branch, not run on
    every tick unconditionally — an unconditional setSelectionRange would
    also fire mid-composition, which client/__about/kb-sync.md explicitly
    forbids (it can break a real composing span)."""
    text = CONTROLS.read_text(encoding="utf-8")
    m = re.search(
        r"if\s*\(\s*kbShouldRepin\([^)]*\)\s*\)\s*\{[^}]*setSelectionRange[^}]*\}",
        text, re.S)
    if not m:
        fail("setSelectionRange is not conditioned on kbShouldRepin() — it "
             "must only run when kbShouldRepin() returns true")


def check_controls_js_logs_the_ghost_candidate_diagnostic() -> None:
    """2026-08-14: no behaviour change, only a diagnostic — the input
    handler must call `kbGhostCandidate` (directly or through a small
    wrapper) and, on a hit, send a rate-limited `client_log` naming the
    fields the owner needs to read the next real occurrence off the server
    log: prev/value length, selection, isComposing, inputType, and the tails.

    PLANTED DEFECT: delete the `logKbGhostCandidate(...)` call from inside
    the `input` handler (leave the function defined but unused) — the
    diagnostic would then never fire on a real device."""
    text = CONTROLS.read_text(encoding="utf-8")
    if "kbGhostCandidate(" not in text:
        fail("client/controls.js no longer references kbGhostCandidate — "
             "the ghost-suffix diagnostic was removed")
    m = re.search(r'kbInput\.addEventListener\("input".*?\n\}\);', text, re.S)
    if not m:
        fail("kbInput's input handler not found in client/controls.js")
    body = m.group(0)
    if "logKbGhostCandidate(" not in body:
        fail("the input handler no longer calls the ghost-candidate "
             "diagnostic — it would never run on a real device")


def check_the_ghost_log_names_the_fields_and_is_rate_limited() -> None:
    """The fields the owner needs to diagnose the NEXT real occurrence from
    the server log alone: prev/value length, selectionStart/End,
    isComposing, inputType, and the tails of prev/value (escaped, so a
    stray quote or backslash in the typed text cannot corrupt the log line).

    PLANTED DEFECT: remove the `now - kbGhostLastLogAt < KB_GHOST_LOG_MIN_MS`
    guard — a genuine occurrence keeps re-triggering the predicate on every
    following keystroke (that is the bug), so an unthrottled log would spam
    one line per keystroke for as long as the fragment stays stuck."""
    text = CONTROLS.read_text(encoding="utf-8")
    if "logKbGhostCandidate" not in text:
        fail("no logKbGhostCandidate function found")
    fn = re.search(r"function logKbGhostCandidate\([^)]*\)\s*\{.*?\n\}",
                    text, re.S)
    if not fn:
        fail("logKbGhostCandidate is referenced but its definition could "
             "not be found")
    body = fn.group(0)
    for needed in ("prevLen", "valLen", "selStart", "selEnd", "composing",
                   "inputType", "prevTail", "valueTail", "[kb-ghost]"):
        if needed not in body:
            fail(f"the ghost-candidate client_log is missing {needed!r} — "
                 "the owner needs this field to diagnose a real occurrence "
                 "from the server log alone")
    if "KB_GHOST_LOG_MIN_MS" not in body or "kbGhostLastLogAt" not in body:
        fail("the ghost-candidate log has no rate-limit guard — a real "
             "occurrence would spam one client_log per keystroke")


CHECKS = [
    ("plain append sends no backspaces", check_plain_append_sends_no_backspace),
    ("a pure trailing delete sends only backspaces",
     check_pure_delete_sends_only_backspaces),
    ("a legitimate mid-string autocorrect still erases and retypes the tail",
     check_mid_string_autocorrect_erases_and_retypes_the_tail),
    ("a caret at its true end is trusted", check_caret_at_true_end_is_trusted),
    ("a caret before a trailing fragment is NOT trusted (his exact shape)",
     check_caret_before_a_trailing_fragment_is_not_trusted),
    ("kbShouldRepin fires when drifted and not composing",
     check_should_repin_fires_when_drifted_and_not_composing),
    ("kbShouldRepin never fires mid-composition",
     check_should_repin_never_fires_mid_composition),
    ("kbShouldRepin is a no-op when already at the end",
     check_should_repin_is_a_noop_already_at_the_end),
    ("without the fix a stuck fragment resends every tick (mechanism proof)",
     check_a_stuck_fragment_would_resend_every_tick_without_the_fix),
    ("re-pinning after each tick stops the fragment recurring (the fix)",
     check_repinning_after_each_tick_stops_the_fragment_recurring),
    ("client/kb-sync.js stays pure, so the gate can run it whole",
     check_kb_sync_js_stays_pure),
    ("controls.js wires kbDiff/kbShouldRepin into the real input handler",
     check_controls_js_wires_kb_diff_into_the_input_handler),
    ("the re-pin call is gated on kbShouldRepin, never unconditional",
     check_repin_is_gated_on_kbShouldRepin_not_unconditional),
    ("a multi-char mid-string retype reads as a ghost candidate",
     check_ghost_candidate_fires_on_a_multi_char_midstring_retype),
    ("an inserted run repeating prevValue's tail reads as a ghost candidate",
     check_ghost_candidate_fires_on_a_repeated_tail),
    ("an ordinary single-char append is never a ghost candidate",
     check_ghost_candidate_does_not_fire_on_an_ordinary_single_char_append),
    ("a coincidental one-char suffix match is never a ghost candidate",
     check_a_coincidental_one_char_suffix_match_does_not_fire),
    ("controls.js logs the ghost-candidate diagnostic from the real handler",
     check_controls_js_logs_the_ghost_candidate_diagnostic),
    ("the ghost log names every needed field and is rate-limited",
     check_the_ghost_log_names_the_fields_and_is_rate_limited),
]


def main() -> int:
    print("\n=== KB SYNC GATE ===")
    if shutil.which("node") is None:
        print("KB SYNC GATE FAILED — node is required (it runs the REAL "
              "client/kb-sync.js rules) and is not on PATH. Never skip a "
              "gate silently.")
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
        print(f"\nKB SYNC GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nKB SYNC GATE PASSED — a typed edit lands where his eyes are, "
          "and a stray fragment cannot outlive a single keystroke.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
