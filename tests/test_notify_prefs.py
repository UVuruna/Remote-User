"""Notify Channels Gate: task 226, owner ballot verdict.

`client/notify.js` carries THREE per-device mute switches — banner / speak /
tone — persisted through `notifyPrefs()`/`saveNotifyPrefs()` and now wired to
a real door on the phone's Phone card (`client/phone-panel.js`). This gate
proves the two rules that must hold wherever a notice is handled:

  1. A muted carrier is genuinely SKIPPED — `handleNotify()` must not fire it.
  2. THE LAST-RESORT RULE — muting all three never means "send nothing":
     `effectiveNotifyPrefs()` answers banner-only when every switch is off.

AND SINCE 2026-08-12, the same file owns WHICH VOICE and HOW FAST (owner
decision: the desktop's single dropdown could not serve a tablet and a phone
with different engines, so the choice moved to the device — with a preview,
because a list of engine names like "en-us-x-tpf-local" tells nobody anything).
Three more rules, each provable by planting its own defect:

  3. The phone's own pref OUTRANKS the frame's `voice`/`rate` — otherwise the
     move is cosmetic and the PC still decides.
  4. NO pref falls back to the frame — a device that has never opened the card
     must behave exactly as it did before, and an older PC that still carries
     a desktop choice must still be obeyed. Read the other way: this is why an
     empty pref is "no opinion", never "the engine default".
  5. The preview speaks EXACTLY ONE sample at a time. The shell hands text to
     TextToSpeech with QUEUE_ADD and exposes no stop, and the voice is set per
     CALL but applies to the whole queue — so a second tap during a sample
     would not replace the first, it would make BOTH speak in the second
     voice, which is precisely the comparison the preview exists to give him.

Driven the way test_voice_dedup.py drives client/voice.js — the REAL module,
run whole in a fresh node process per case, with `prefGet`/`prefSet`/`send`/
`window` stubbed to the minimum notify.js actually touches. notify.js is NOT
a pure module (it reaches for `window.Android`, `document.hidden`,
`showToast`), so the stub supplies exactly those surfaces rather than a DOM.

Run:  .venv\\Scripts\\python tests/test_notify_prefs.py
Requires: node on PATH.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
NOTIFY = PROJECT / "client" / "notify.js"


def fail(msg: str) -> None:
    raise AssertionError(msg)


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        fail("node is required for this gate (it runs the REAL "
             "client/notify.js rules) — install Node.js.")
    return node


def _module() -> str:
    text = NOTIFY.read_text(encoding="utf-8")
    for needed in ("function notifyPrefs", "function saveNotifyPrefs",
                   "function effectiveNotifyPrefs", "function handleNotify",
                   "function notifyVoicePref", "function notifyRatePref",
                   "function voicePreview", "function openNotifyVoicePanel"):
        if needed not in text:
            fail(f"{needed!r} left client/notify.js — the gate cannot find "
                 "what it must test")
    return text


# Stubs for everything notify.js reaches for outside its own functions. Kept
# to the minimum surface: prefGet/prefSet back a plain in-memory object (the
# same contract the shell's SharedPreferences bridge honors), `send` records
# what would have gone to client_log, `document`/`window`/`Android` give
# handleNotify() a banner+speak+tone target to record calls against instead
# of throwing on a missing DOM.
STUB = """
const __store = {};
function prefGet(key) { return Object.prototype.hasOwnProperty.call(__store, key) ? __store[key] : null; }
function prefSet(key, value) { __store[key] = String(value); }
const __calls = [];
function send(msg) { __calls.push(msg); }
function showToast(text) { __calls.push({ type: "toast", text }); }
function ghostClickArmor() {}
// panels.js's estimate of how long a sample takes to speak. STUBBED SHORT so
// the one-at-a-time check can also prove the guard RELEASES — a guard that
// never releases silences every later preview, which is the same feature dead
// in the other direction. The real number is panels.js's business and is
// documented there; what this gate owns is that a second tap during a sample
// is refused and a tap after it is not.
globalThis.dictSampleMs = () => 5;
function __el() {
  return { hidden: true, className: "", innerHTML: "", dataset: {},
    classList: { add() {}, remove() {}, toggle() {} },
    appendChild(c) { return c; }, append() {}, addEventListener() {},
    setAttribute() {}, querySelector: () => null, querySelectorAll: () => [] };
}
globalThis.document = { hidden: true, body: __el(),
  createElement: () => __el(), getElementById: () => __el() };
globalThis.performance = { now: () => 0 };
globalThis.window = globalThis;
globalThis.IN_APP = true;
globalThis.Android = {
  notify: (title, body, tag) => __calls.push({ type: "banner", title, body, tag }),
  notifyAt: (title, body, tag, jump) => __calls.push({ type: "banner", title, body, tag, jump }),
  speak: (text) => __calls.push({ type: "speak", text }),
  speakAs: (text, voice, rate) => __calls.push({ type: "speak", text, voice, rate }),
};
"""


def _run(script_body: str) -> dict:
    script = f"{STUB}\n{_module()}\n{script_body}\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.mjs"
        path.write_text(script, encoding="utf-8")
        out = subprocess.run([_node(), str(path)], capture_output=True,
                              text=True, timeout=30)
    if out.returncode != 0:
        fail(f"node failed:\n{out.stderr}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def check_default_prefs_are_all_notice_carriers_on_except_tone() -> None:
    out = _run('console.log(JSON.stringify(notifyPrefs()));')
    if out != {"banner": True, "speak": True, "tone": False}:
        fail(f"defaults changed unexpectedly: {out}")


def check_a_muted_carrier_is_really_skipped() -> None:
    """Mute speak and tone, leave banner on: only the banner call fires."""
    out = _run("""
saveNotifyPrefs({ banner: true, speak: false, tone: false });
handleNotify({ agent: "claude", title: "Done", text: "finished" });
console.log(JSON.stringify(__calls));
""")
    kinds = [c["type"] for c in out]
    if "speak" in kinds:
        fail(f"speak fired while muted: {out}")
    if "banner" not in kinds:
        fail(f"the enabled banner carrier did not fire: {out}")


def check_muting_every_carrier_still_answers_banner_only() -> None:
    """THE LAST-RESORT RULE: all three off must not mean silence."""
    out = _run("""
saveNotifyPrefs({ banner: false, speak: false, tone: false });
handleNotify({ agent: "claude", title: "Done", text: "finished" });
console.log(JSON.stringify(__calls));
""")
    kinds = [c["type"] for c in out]
    if "banner" not in kinds:
        fail(f"all-off produced no banner — the last-resort rule was lost: {out}")
    if "speak" in kinds:
        fail(f"all-off spoke anyway — that is not the documented fallback: {out}")


def check_the_stored_prefs_are_never_rewritten_by_the_fallback() -> None:
    """The override lives only in the READ path (`effectiveNotifyPrefs`) —
    the raw all-off choice the owner made must still read back as all-off on
    the Phone card, or the switches would silently re-enable themselves."""
    out = _run("""
saveNotifyPrefs({ banner: false, speak: false, tone: false });
handleNotify({ agent: "claude", title: "Done", text: "finished" });
console.log(JSON.stringify(notifyPrefs()));
""")
    if out != {"banner": False, "speak": False, "tone": False}:
        fail(f"the stored prefs were mutated by the last-resort fallback: {out}")


def check_a_normal_mixed_choice_is_carried_through_unmodified() -> None:
    """Banner off, speak on: the fallback must not kick in when at least one
    carrier is genuinely on — it is an ALL-off rule, not a majority rule."""
    out = _run("""
saveNotifyPrefs({ banner: false, speak: true, tone: false });
handleNotify({ agent: "claude", title: "Done", text: "finished" });
console.log(JSON.stringify(__calls));
""")
    kinds = [c["type"] for c in out]
    if "banner" in kinds:
        fail(f"banner fired while off with speak on — the fallback over-fired: {out}")
    if "speak" not in kinds:
        fail(f"speak did not fire although it was on: {out}")


# ── THE VOICE IS THIS DEVICE'S OWN (owner 2026-08-12) ──────────────────────

def _spoken(out: list) -> dict:
    """The one `speak` call a notice produced — the gate fails loudly rather
    than indexing into an empty list, because "it never spoke" and "it spoke
    in the wrong voice" are two different bugs and must not read alike."""
    speaks = [c for c in out if c["type"] == "speak"]
    if len(speaks) != 1:
        fail(f"expected exactly one spoken notice, got {speaks}")
    return speaks[0]


def check_this_phones_own_voice_outranks_the_frame() -> None:
    """PLANTED DEFECT: read `msg.voice` first. The dropdown moved off the
    desktop precisely because one PC cannot name a voice that exists on two
    different devices — if the frame still wins, nothing moved."""
    out = _run("""
prefSet("notifyVoice", "phone-voice");
prefSet("notifyRate", "1.5");
handleNotify({ agent: "claude", title: "Done", text: "finished",
               voice: "pc-voice", rate: 0.8 });
console.log(JSON.stringify(__calls));
""")
    said = _spoken(out)
    if said["voice"] != "phone-voice":
        fail(f"the PC's voice outranked this phone's own choice: {said}")
    if said["rate"] != 1.5:
        fail(f"the PC's pace outranked this phone's own choice: {said}")


def check_no_choice_here_falls_back_to_the_frame() -> None:
    """The other half, and the reason the move is safe in both directions: a
    device that has never opened the card behaves exactly as it did before,
    and a PC still carrying a desktop choice is still obeyed by it.

    PLANTED DEFECT: send "" and 1 whenever the pref is unset. Every phone that
    never opened the card would silently lose the voice the owner picked."""
    out = _run("""
handleNotify({ agent: "claude", title: "Done", text: "finished",
               voice: "pc-voice", rate: 1.25 });
console.log(JSON.stringify(__calls));
""")
    said = _spoken(out)
    if said["voice"] != "pc-voice" or said["rate"] != 1.25:
        fail(f"an unset pref did not fall back to the frame: {said}")

    # And each half falls back on its OWN: choosing a voice here must not
    # silently reset the pace to 1, which is what a single combined "has the
    # phone chosen anything?" test would do.
    mixed = _run("""
prefSet("notifyVoice", "phone-voice");
handleNotify({ agent: "claude", title: "Done", text: "finished",
               voice: "pc-voice", rate: 1.25 });
console.log(JSON.stringify(__calls));
""")
    said = _spoken(mixed)
    if said["voice"] != "phone-voice" or said["rate"] != 1.25:
        fail(f"voice and pace did not fall back independently: {said}")

    # A frame with neither field is the oldest server there is — speak, at 1.
    bare = _run("""
handleNotify({ agent: "claude", title: "Done", text: "finished" });
console.log(JSON.stringify(__calls));
""")
    said = _spoken(bare)
    if said["voice"] != "" or said["rate"] != 1:
        fail(f"a frame carrying no voice at all must speak plainly: {said}")


def check_the_preview_speaks_one_sample_at_a_time() -> None:
    """The shell hands text to TextToSpeech with QUEUE_ADD and exposes no
    stop, and the voice is set per CALL but applies to the whole QUEUE — so a
    second tap during a sample would make BOTH samples speak in the second
    voice, destroying the one comparison the preview exists to give him.

    PLANTED DEFECT: drop the `if (voiceSpeakingName) return;` guard — the two
    rapid taps below then produce two calls. PLANTED DEFECT, the other way:
    never clear `voiceSpeakingName`, and the third tap (after the sample's
    window) is refused too, which silences the control for the rest of the
    session."""
    out = _run("""
const btn = { classList: { add() {}, remove() {} } };
voicePreview({ name: "voice-a" }, btn);
voicePreview({ name: "voice-b" }, btn);   // during the first — must be refused
setTimeout(() => {
  voicePreview({ name: "voice-c" }, btn); // after it — must be allowed
  console.log(JSON.stringify(__calls));
}, 40);
""")
    voices = [c["voice"] for c in out if c["type"] == "speak"]
    if voices != ["voice-a", "voice-c"]:
        fail("the preview must speak exactly one sample at a time and free "
             f"itself afterwards — heard {voices}")


def check_the_preview_speaks_at_the_pace_he_chose() -> None:
    """A voice at 1.5x is a different thing to listen to than the same voice
    at 0.8x, and the pair is what he will actually hear. PLANTED DEFECT: pass
    a literal 1 — the card would then preview at a pace it never uses."""
    out = _run("""
prefSet("notifyRate", "1.25");
const btn = { classList: { add() {}, remove() {} } };
voicePreview({ name: "voice-a" }, btn);
console.log(JSON.stringify(__calls));
""")
    said = _spoken(out)
    if said["rate"] != 1.25:
        fail(f"the preview ignored the chosen pace: {said}")


CHECKS = [
    check_default_prefs_are_all_notice_carriers_on_except_tone,
    check_a_muted_carrier_is_really_skipped,
    check_muting_every_carrier_still_answers_banner_only,
    check_the_stored_prefs_are_never_rewritten_by_the_fallback,
    check_a_normal_mixed_choice_is_carried_through_unmodified,
    check_this_phones_own_voice_outranks_the_frame,
    check_no_choice_here_falls_back_to_the_frame,
    check_the_preview_speaks_one_sample_at_a_time,
    check_the_preview_speaks_at_the_pace_he_chose,
]


def main() -> int:
    results: dict[str, bool] = {}
    for check in CHECKS:
        try:
            check()
            results[check.__name__] = True
        except AssertionError as e:
            results[check.__name__] = False
            print(f"  DETAIL {check.__name__}: {e}")

    print("\n=== NOTIFY CHANNELS GATE ===")
    failed = 0
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    if failed:
        print(f"\nNOTIFY CHANNELS GATE FAILED — {failed} check(s).", file=sys.stderr)
        return 1
    print("\nNOTIFY CHANNELS GATE PASSED — a muted carrier is skipped, and "
          "muting all three still leaves the banner as the last resort.")
    return 0


def test_notify_prefs():
    """pytest entry — skipped where node is absent."""
    import pytest
    if shutil.which("node") is None:
        pytest.skip("node not on PATH")
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
