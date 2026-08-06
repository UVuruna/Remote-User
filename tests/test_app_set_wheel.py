"""Guard: the app-aware sets obey the owner's two rules of 2026-08-06.

Both came from him in one message, after the Claude set shipped:

  A. "Ali samo ako je otvoren tab claude komunikacija a ne ako je otvoren tab
     pa i transkripta ili bilo što drugo tekstualni dokument ili šta god" —
     the Claude set may appear for the Claude CONVERSATION and for nothing
     else. The first version matched `title` as a plain substring, so an open
     `CLAUDE.md`, a transcript, any file whose name happens to carry the word
     put the Claude wheel on screen. The test is now a WORD, and a title that
     looks like a document never matches at all.
  B. "ako označi oba ... onda može samo još 6 dodatnih umesto 7" — an app set
     costs a wheel slot like every other set. VSCode + Claude ride together on
     a Claude tab (the one case where two app sets appear at once), so ticking
     both leaves six of the eight slots for the rest. They used to be free,
     which let the picker promise eight while the wheel silently dropped two.

Rule A is also what keeps rule B honest: if the Claude set matched every
VSCode tab, the reserve would be two all the time.

The functions under test are pure and live in client/controls.js, which is a
browser script (it touches the DOM at load). The guard therefore lifts the
pure block out of the file and runs it in node with stubs — the same
parse-the-client trick the desktop Controls editor already uses to read ICONS
and BUILTINS out of the client.

Run:  .venv\\Scripts\\python tests/test_app_set_wheel.py
Requires: node on PATH.
"""

import json

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CONTROLS = PROJECT / "client" / "controls.js"
ACTIONS = PROJECT / "actions.json"


def pure_block() -> str:
    """The block under test: from the document-title regex through the wheel
    reserve. Lifted by markers, not by line numbers — controls.js moves."""
    text = CONTROLS.read_text(encoding="utf-8")
    start = text.index("const DOC_TITLE")
    end = text.index("\n}", text.index("function appSetReserve()")) + 2
    block = text[start:end]
    for needed in ("function titleMatches", "function appSetMatches",
                   "function appSetReserve"):
        assert needed in block, f"{needed} left the pure block of controls.js"
    return block


def run_js(body: str, app_sets: list, prefs: dict) -> object:
    """Runs the lifted block with the stubs it needs and returns the JSON the
    body prints. `setsPrefs`/`appSetOn` are the phone's own prefs helpers —
    stubbed, because what is under test is the RULES, not the storage."""
    script = f"""
const appSets = {json.dumps(app_sets)};
const PREFS = {json.dumps(prefs)};
function setsPrefs() {{ return PREFS; }}
function appSetOn(s) {{
  const c = PREFS.appState[s.name];
  return c !== undefined ? c : s.enabled !== false;
}}
{pure_block()}
{body}
"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.mjs"
        path.write_text(script, encoding="utf-8")
        out = subprocess.run([shutil.which("node") or "node", str(path)],
                             capture_output=True, text=True, check=False)
        if out.returncode != 0:
            raise AssertionError(f"node failed:\n{out.stderr}")
        return json.loads(out.stdout.strip())


def shipped_app_sets() -> list:
    return json.loads(ACTIONS.read_text(encoding="utf-8"))["app_sets"]


# -- A. only the Claude conversation wears the Claude set --------------------

# Titles a VSCode member window can carry. The extracted Claude tab is the
# ONLY one that may bring the Claude set out (owner 2026-08-06).
CLAUDE_TITLES = ["Claude Code", "claude code", "Claude"]
NOT_CLAUDE_TITLES = [
    "CLAUDE.md",                                   # the constitution itself
    "CLAUDE.md — Remote User — Visual Studio Code",
    "claude.md",
    "transcript.txt",
    "claude-transcript.json",                      # a document about Claude
    "controls.js",
    "README",                                      # a plain file, no keyword
    "Remote User — Visual Studio Code",
]


def test_only_the_claude_conversation_matches_the_claude_set():
    sets = shipped_app_sets()
    body = """
const layouts = process.argv.slice(2);
console.log(JSON.stringify(layouts.map((title) =>
  appSets.filter((s) => appSetMatches(s, { process: "code.exe", title }))
         .map((s) => s.name))));
"""
    prefs = {"apps": True, "appState": {}, "state": {}}

    def names_for(titles):
        script_body = body.replace("process.argv.slice(2)", json.dumps(titles))
        return run_js(script_body, sets, prefs)

    for title, got in zip(CLAUDE_TITLES, names_for(CLAUDE_TITLES)):
        assert "Claude" in got, f"the Claude conversation {title!r} lost its set: {got}"
        assert "VSCode" in got, (
            f"VSCode must ride ALONGSIDE Claude on {title!r} (owner 2026-08-06): {got}")

    for title, got in zip(NOT_CLAUDE_TITLES, names_for(NOT_CLAUDE_TITLES)):
        assert "Claude" not in got, (
            f"{title!r} is a document, not the Claude conversation — got {got}")
        assert "VSCode" in got, f"{title!r} is still VSCode: {got}"


def test_a_document_never_matches_even_a_process_only_set():
    """A Chrome tab named `report.pdf` is still Chrome — the document rule
    applies to the TITLE test only, never to the process."""
    sets = shipped_app_sets()
    body = ('console.log(JSON.stringify(appSets'
            '.filter((s) => appSetMatches(s, { process: "chrome.exe", title: "report.pdf" }))'
            '.map((s) => s.name)));')
    got = run_js(body, sets, {"apps": True, "appState": {}, "state": {}})
    assert got == ["Chrome"], got


# -- B. an app set costs a wheel slot ---------------------------------------

def test_the_reserve_is_the_largest_group_that_can_appear_at_once():
    sets = shipped_app_sets()
    body = "console.log(JSON.stringify(appSetReserve()));"

    all_on = {"apps": True, "appState": {}, "state": {}}
    assert run_js(body, sets, all_on) == 2, (
        "VSCode + Claude share one process and appear together — that is two "
        "wheel slots (owner 2026-08-06)")

    # Chrome and Explorer can never be on screen with VSCode: three ticked
    # sets of three different processes still cost ONE slot.
    only_others = {"apps": True, "state": {},
                   "appState": {"VSCode": False, "Claude": False}}
    assert run_js(body, sets, only_others) == 1, (
        "sets of different processes cannot appear together — they cost one slot")

    one_of_the_pair = {"apps": True, "state": {}, "appState": {"Claude": False}}
    assert run_js(body, sets, one_of_the_pair) == 1, (
        "untick Claude and the pair costs one slot again")

    master_off = {"apps": False, "appState": {}, "state": {}}
    assert run_js(body, sets, master_off) == 0, (
        "the master switch off means app sets charge nothing")


TESTS = [
    ("only the Claude conversation wears the Claude set",
     test_only_the_claude_conversation_matches_the_claude_set),
    ("a document never matches a process-only set",
     test_a_document_never_matches_even_a_process_only_set),
    ("the reserve is the largest group that can appear at once",
     test_the_reserve_is_the_largest_group_that_can_appear_at_once),
]


def main() -> int:
    if not shutil.which("node"):
        print("APP-SET WHEEL GUARD SKIPPED — node is not on PATH")
        return 0
    print("\n=== APP-SET WHEEL GUARD ===")
    failed = 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nAPP-SET WHEEL GUARD FAILED — {failed} rule(s) broken.")
        return 1
    print("\nAPP-SET WHEEL GUARD PASSED — app sets appear when they should "
          "and pay for their seat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
