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

  C. "kako hoćeš da Claude set zna da je to Claude" — answered by the owner on
     2026-08-06 after the probe proved no string can: Claude Code names its
     VSCode tab after the CONVERSATION, wears the same UIA class as the file
     tab beside it, and hides its content from accessibility. The layout now
     carries the owner's own ticks and they answer alone.
  D. "sam vidio da je po difoltu štiklirano 9 a ne sme da bude" — the cap of 8
     is a law over the STORED state, not a check that runs on a tap. The
     shipped actions.json itself had nine ticked.

The rules under test live in client/sets.js (split out of controls.js on
2026-08-06 under THE STRUCTURE LAW). The guard runs that module WHOLE in node
behind stubs for its two neighbours — the prefs bridge and the focused layout
— rather than lifting a block out of it: the cap is enforced across storage,
so a test that stubbed the storage away would prove the arithmetic and miss
the law.

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
# The composition rules moved out of controls.js on 2026-08-06 (THE STRUCTURE
# LAW — controls.js hit 1000 lines). sets.js is the whole module under test
# now, and the guard runs it WHOLE rather than lifting a block out of it:
# the cap is enforced across storage, so a test that stubs the storage away
# would prove the arithmetic and miss the law.
SETS = PROJECT / "client" / "sets.js"
ACTIONS = PROJECT / "actions.json"


def run_js(body: str, app_sets: list, prefs: dict,
           categories: list | None = None, custom: list | None = None) -> object:
    """Runs client/sets.js in node behind the four things it borrows from its
    neighbours — the prefs bridge (state.js) and the focused layout
    (layouts.js) — and returns the JSON the body prints."""
    module = SETS.read_text(encoding="utf-8")
    for needed in ("function titleMatches", "function appSetMatches",
                   "function appSetReserve", "function enforceWheelCap",
                   "function capVictim"):
        assert needed in module, f"{needed} left client/sets.js"
    script = f"""
let STORE = {json.dumps({"setsPrefs": json.dumps(prefs)})};
function prefGet(k) {{ return STORE[k]; }}
function prefSet(k, v) {{ STORE[k] = v; }}
let layoutActive = null;
let layouts = [];
{module}
categories = {json.dumps(categories if categories is not None else [])};
appSets = {json.dumps(app_sets)};
customSets = {json.dumps(custom if custom is not None else [])};
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


def shipped() -> dict:
    return json.loads(ACTIONS.read_text(encoding="utf-8"))


def shipped_app_sets() -> list:
    return shipped()["app_sets"]


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
const cases = process.argv.slice(2);
console.log(JSON.stringify(cases.map((title) =>
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


# -- C. the PC's answer decides, and no stored tick may outrank it ----------

def test_detection_decides_and_a_stored_tick_list_can_never_win():
    """THIS TEST USED TO PIN THE BUG (owner 2026-08-07, and it is the clearest
    example in the repo of how a green guard shipped a broken app).

    Its previous name was "the layout's own ticks win over the title guess",
    and it asserted exactly the line that kept the owner's Claude wheel dead:
    a layout carrying `app_sets` was answered from that list ALONE. Written
    from the same belief as the code, it could never have gone red. The belief
    was already obsolete when it was written — `agents` detection had shipped
    in the same round.

    His real window, probed on his own PC:

        'Ispravka UI dizajna meni… - Remote User - Visual Studio Code [Administrator]'
        TAB 'Ispravka UI dizajna meni…, Window 2: Editor Group 1'

    No string in it says "claude", the tab wears the same UIA class as
    `prompt.txt` beside it, AutomationId is empty. The title can never answer
    this. The PROCESS TABLE can, and does: `agents: ["claude"]` on the layout.
    So that is what must decide — every frame, freshly, with no stored copy of
    an older answer anywhere in the path."""
    sets = shipped_app_sets()
    body = """
const real = { process: "code.exe", title: "Ispravka UI dizajna meni…" };
console.log(JSON.stringify({
  detected: appSets.filter((s) => appSetMatches(s,
      { ...real, agents: ["claude"] })).map((s) => s.name),
  plain: appSets.filter((s) => appSetMatches(s, { ...real, agents: [] }))
      .map((s) => s.name),
  stale: appSets.filter((s) => appSetMatches(s,
      { ...real, agents: ["claude"], app_sets: ["VSCode"] })).map((s) => s.name),
}));
"""
    got = run_js(body, sets, {"apps": True, "appState": {}, "state": {}})
    assert got["detected"] == ["VSCode", "Claude"], (
        "the PC says a Claude session is live in this window's project — both "
        f"sets must ride, with nobody ticking anything: {got['detected']}")
    assert got["plain"] == ["VSCode"], (
        "no live claude.exe in that project means plain VSCode — the wheel "
        f"must not carry Claude's slash commands into an editor: {got['plain']}")
    assert got["stale"] == ["VSCode", "Claude"], (
        "A LAYOUT MAY NOT CARRY AN ANSWER. This is the owner's bug of "
        "2026-08-07: a list written once at creation outranked a live "
        "detection that was saying 'claude' on every state frame, and his "
        f"wheel offered VS Code alone forever: {got['stale']}")


# -- D. the cap of 8 is a LAW over the STORED state too ---------------------

def test_the_shipped_defaults_cannot_tick_more_than_the_cap():
    """What the owner actually caught: "sam vidio da je po difoltu štiklirano
    9 a ne sme da bude". The shipped actions.json had SEVEN categories on by
    default and the two `code` app sets reserve two more — nine under a cap of
    eight. The file itself must obey the law, or every phone inherits it."""
    data = shipped()
    body = "console.log(JSON.stringify(visibleCount()));"
    count = run_js(body, data["app_sets"], {"apps": True, "appState": {}, "state": {}},
                   categories=data["categories"], custom=data.get("custom_sets", []))
    assert count <= 8, (
        f"the shipped actions.json ticks {count} sets by default — the wheel "
        "holds 8, and a default that breaks the cap is what put NINE on the "
        "owner's phone (owner 2026-08-06)")


def test_a_stored_state_over_the_cap_is_brought_back_to_it():
    """The cap used to be tested only at the moment of a tap, so any state
    that arrived another way sailed past it. Now the stored state is
    normalized — and the app set gives way first, which is the owner's own
    rule: "ako samo 7 osnovnih onda mora jedan od claude i vscode da bude
    iskljucen"."""
    sets = shipped_app_sets()
    cats = [{"name": "Mouse", "required": True}, {"name": "Input", "required": True},
            {"name": "Settings", "required": True}, {"name": "Attach"},
            {"name": "Edit"}, {"name": "Navigate"}, {"name": "Cursor"}]
    body = """
const before = visibleCount();
const dropped = enforceWheelCap();
console.log(JSON.stringify({ before, dropped, after: visibleCount(),
  apps: appSets.filter(appSetOn).map((s) => s.name) }));
"""
    got = run_js(body, sets, {"apps": True, "appState": {}, "state": {}}, categories=cats)
    assert got["before"] == 9, f"the case must start over the cap: {got['before']}"
    assert got["after"] == 8, f"the cap was not restored: {got}"
    assert got["dropped"] == ["Claude"], (
        "the app set gives way first — his seven chosen basics are the ones he "
        f"ticked on purpose (owner 2026-08-06): {got['dropped']}")

    # Nothing to give away on the app side: the basics take the cut instead.
    no_apps = {"apps": False, "appState": {}, "state": {}}
    cats9 = cats + [{"name": "Media"}, {"name": "Windows"}]
    got2 = run_js(body, sets, no_apps, categories=cats9)
    assert got2["after"] == 8, f"the cap must hold without app sets too: {got2}"
    assert got2["dropped"] == ["Windows"], (
        f"the LAST optional basic gives way, not an arbitrary one: {got2['dropped']}")



# -- C. the PC's own answer, not a guess about the title ---------------------

def test_the_pc_decides_whether_claude_is_live():
    """The whole point of server/agents.py (owner 2026-08-06, after he called
    the manual ticking what it was).

    The Claude set carries `agent: "claude"`, and the server sends each layout
    the agents it found RUNNING in that window's project — a live claude.exe
    carrying its session id, the session id naming its project. So the set
    appears on a window whose title says nothing about Claude, and it stays
    away from one whose title screams it while nothing is running. The title
    guess could never do either.
    """
    sets = shipped_app_sets()
    body = ('const lay = JSON.parse(process.argv[2]);'
            'console.log(JSON.stringify(appSets.filter((s) => appSetMatches(s, lay))'
            '.map((s) => s.name)));')
    prefs = {"apps": True, "appState": {}, "state": {}}

    def names_for(lay):
        return run_js(body.replace("JSON.parse(process.argv[2])", json.dumps(lay)),
                      sets, prefs)

    # His real window: the tab is named after the CONVERSATION, and there is
    # not one letter of "claude" anywhere in it.
    live = {"process": "code.exe", "agents": ["claude"],
            "title": "Ispravka UI dizajna meni… - Remote User - Visual Studio Code"}
    got = names_for(live)
    assert "Claude" in got, f"a LIVE session must bring the Claude set out: {got}"
    assert "VSCode" in got, f"VSCode rides alongside it as always: {got}"

    # Nothing running: the PC's "no" outranks a title that says otherwise.
    dead = {"process": "code.exe", "agents": [], "title": "Claude Code"}
    got = names_for(dead)
    assert "Claude" not in got, (
        f"no live session means no Claude set, whatever the title claims: {got}")
    assert got == ["VSCode"], got

    # An older server sends no `agents` at all — the title guess still answers,
    # so an update of one side alone never blanks the wheel.
    legacy = {"process": "code.exe", "title": "Claude Code"}
    assert "Claude" in names_for(legacy), "the pre-agents fallback must survive"


def test_the_window_title_names_the_project():
    """The server half, pure: which folder a VS Code title names. Measured
    against the owner's own titles."""
    sys.path.insert(0, str(PROJECT / "server"))
    import agents as agents_mod
    cases = {
        "Ispravka UI dizajna meni… - Remote User - Visual Studio Code [Administrator]": "remote user",
        "Kreiraj GUI smernice i p… - UVuruna - Visual Studio Code [Administrator]": "uvuruna",
        "ubacio sam 3 nove letter… - DOMY Watch - Visual Studio Code": "domy watch",
        "Some Folder - Notepad": "",
        "": "",
    }
    for title, want in cases.items():
        got = agents_mod.title_folder(title)
        assert got == want, f"{title!r} -> {got!r}, expected {want!r}"


TESTS = [
    ("only the Claude conversation wears the Claude set",
     test_only_the_claude_conversation_matches_the_claude_set),
    ("detection decides — a stored tick list can never win",
     test_detection_decides_and_a_stored_tick_list_can_never_win),
    ("the shipped defaults cannot tick more than the cap",
     test_the_shipped_defaults_cannot_tick_more_than_the_cap),
    ("a stored state over the cap is brought back to it",
     test_a_stored_state_over_the_cap_is_brought_back_to_it),
    ("a document never matches a process-only set",
     test_a_document_never_matches_even_a_process_only_set),
    ("the reserve is the largest group that can appear at once",
     test_the_reserve_is_the_largest_group_that_can_appear_at_once),
    ("the PC decides whether Claude is live, not the title",
     test_the_pc_decides_whether_claude_is_live),
    ("a VS Code title names its project folder",
     test_the_window_title_names_the_project),
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
