"""Notify Channels Gate: task 226, owner ballot verdict.

`client/notify.js` carries THREE per-device mute switches — banner / speak /
tone — persisted through `notifyPrefs()`/`saveNotifyPrefs()` and now wired to
a real door on the phone's Phone card (`client/phone-panel.js`). This gate
proves the two rules that must hold wherever a notice is handled:

  1. A muted carrier is genuinely SKIPPED — `handleNotify()` must not fire it.
  2. THE LAST-RESORT RULE — muting all three never means "send nothing":
     `effectiveNotifyPrefs()` answers banner-only when every switch is off.

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
                   "function effectiveNotifyPrefs", "function handleNotify"):
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
globalThis.document = { hidden: true };
globalThis.performance = { now: () => 0 };
globalThis.window = globalThis;
globalThis.IN_APP = true;
globalThis.Android = {
  notify: (title, body, tag) => __calls.push({ type: "banner", title, body, tag }),
  notifyAt: (title, body, tag, jump) => __calls.push({ type: "banner", title, body, tag, jump }),
  speak: (text) => __calls.push({ type: "speak", text }),
  speakAs: (text, voice, rate) => __calls.push({ type: "speak", text, voice, rate }),
};
document.getElementById = () => ({ addEventListener: () => {} });
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


CHECKS = [
    check_default_prefs_are_all_notice_carriers_on_except_tone,
    check_a_muted_carrier_is_really_skipped,
    check_muting_every_carrier_still_answers_banner_only,
    check_the_stored_prefs_are_never_rewritten_by_the_fallback,
    check_a_normal_mixed_choice_is_carried_through_unmodified,
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
