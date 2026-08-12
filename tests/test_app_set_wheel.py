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

import asyncio
import json

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import agents  # noqa: E402
import layout_api  # noqa: E402
import uia  # noqa: E402
import window_manager  # noqa: E402
# The composition rules moved out of controls.js on 2026-08-06 (THE STRUCTURE
# LAW — controls.js hit 1000 lines). sets.js is the whole module under test
# now, and the guard runs it WHOLE rather than lifting a block out of it:
# the cap is enforced across storage, so a test that stubs the storage away
# would prove the arithmetic and miss the law.
SETS = PROJECT / "client" / "sets.js"
ACTIONS = PROJECT / "actions.json"


def run_js(body: str, app_sets: list, prefs: dict,
           categories: list | None = None, custom: list | None = None,
           wheel_order: list | None = None, wheel_mode: str = "fixed") -> object:
    """Runs client/sets.js in node behind the four things it borrows from its
    neighbours — the prefs bridge (state.js) and the focused layout
    (layouts.js) — and returns the JSON the body prints.

    DEFAULTS to FIXED mode (task 181, 2026-08-11): this whole file's "cap of
    8" checks predate the drop-out/fixed split and are written in terms of the
    ORIGINAL, single cap — fixed mode is exactly that cap, unchanged. The
    drop-out mode's own cap (10) and its placement-shedding rules are
    test_wheel_dropout.py's job.

    `wheel_mode` is a parameter and not a constant (2026-08-12) for the one
    check below that measures the SHIPPED FILE rather than an arithmetic case:
    that file carries its own mode, and asking it a question in a mode it does
    not run in is how a guard comes to state a cap the product does not have."""
    module = SETS.read_text(encoding="utf-8")
    for needed in ("function titleMatches", "function appSetMatches",
                   "function appSetReserve", "function enforceWheelCap",
                   "function capVictim", "function sortByWheelOrder"):
        assert needed in module, f"{needed} left client/sets.js"
    script = f"""
let STORE = {json.dumps({"setsPrefs": json.dumps(prefs)})};
function prefGet(k) {{ return STORE[k]; }}
function prefSet(k, v) {{ STORE[k] = v; }}
let layoutActive = null;
let layouts = [];
let groups = {{ left: 0, right: 0 }};
{module}
categories = {json.dumps(categories if categories is not None else [])};
appSets = {json.dumps(app_sets)};
customSets = {json.dumps(custom if custom is not None else [])};
wheelOrder = {json.dumps(wheel_order if wheel_order is not None else [])};
setWheelMode({json.dumps(wheel_mode)});
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
    "CLAUDE.md — VibeCoder — Visual Studio Code",
    "claude.md",
    "transcript.txt",
    "claude-transcript.json",                      # a document about Claude
    "controls.js",
    "README",                                      # a plain file, no keyword
    "VibeCoder — Visual Studio Code",
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

    # THE GROUP GREW TO THREE on 2026-08-12: Claude Tools ships ticked now that
    # drop-out's real cap of 10 has room for it, and it shares the `code`
    # process with VSCode and Claude. The RULE is untouched — the reserve is
    # the largest group that can appear TOGETHER — only the group's size moved.
    code_group = sum(1 for s in sets
                     if s.get("process") == "code" and s.get("enabled", True))
    all_on = {"apps": True, "appState": {}, "state": {}}
    assert run_js(body, sets, all_on) == code_group, (
        f"the {code_group} shipped `code` sets share one process and appear "
        "together — that is that many wheel slots (owner 2026-08-06)")

    # Chrome and Explorer can never be on screen with VSCode: three ticked
    # sets of three different processes still cost ONE slot.
    only_others = {"apps": True, "state": {},
                   "appState": {"VSCode": False, "Claude": False,
                                "Claude Tools": False}}
    assert run_js(body, sets, only_others) == 1, (
        "sets of different processes cannot appear together — they cost one slot")

    one_of_the_group = {"apps": True, "state": {},
                        "appState": {"Claude": False, "Claude Tools": False}}
    assert run_js(body, sets, one_of_the_group) == 1, (
        "untick the rest of the group and it costs one slot again")

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

        'Ispravka UI dizajna meni… - VibeCoder - Visual Studio Code [Administrator]'
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
    # THREE since 2026-08-11 (task 219): `Claude Tools` rides on exactly the
    # same `agent: "claude"` answer. This asserts MATCHING, not riding — the
    # new set ships `enabled: false` (the wheel is already full at 8, see
    # ACTIONS.md), so `appSetOn` keeps it off the ring until he ticks it. A
    # set that matches and is switched off is the ordinary case and always
    # was; what this check exists to prove is that the PC's answer, and only
    # the PC's answer, decides which sets BELONG to this window.
    got = run_js(body, sets, {"apps": True, "appState": {}, "state": {}})
    assert got["detected"] == ["VSCode", "Claude", "Claude Tools"], (
        "the PC says a Claude session is live in this window's project — every "
        f"claude set must match, with nobody ticking anything: {got['detected']}")
    assert got["plain"] == ["VSCode"], (
        "no live claude.exe in that project means plain VSCode — the wheel "
        f"must not carry Claude's slash commands into an editor: {got['plain']}")
    assert got["stale"] == ["VSCode", "Claude", "Claude Tools"], (
        "A LAYOUT MAY NOT CARRY AN ANSWER. This is the owner's bug of "
        "2026-08-07: a list written once at creation outranked a live "
        "detection that was saying 'claude' on every state frame, and his "
        f"wheel offered VS Code alone forever: {got['stale']}")


# -- D. the cap of 8 is a LAW over the STORED state too ---------------------

def test_the_shipped_defaults_cannot_tick_more_than_the_cap():
    """What the owner actually caught: "sam vidio da je po difoltu štiklirano
    9 a ne sme da bude". The shipped actions.json had SEVEN categories on by
    default and the two `code` app sets reserve two more — nine under a cap of
    eight. The file itself must obey the law, or every phone inherits it.

    IN ITS OWN MODE (2026-08-12). This is the only check in this file that
    measures the SHIPPED FILE, and it used to measure it in fixed mode like
    every arithmetic case around it — so it enforced a cap of 8 on a file that
    ships with no `wheel_mode` at all, which every load site in the product
    reads as drop-out, cap 10. The law is unchanged: a shipped default may not
    break the cap the phone will really apply to it. Only the number stopped
    being a constant."""
    data = shipped()
    mode = data.get("wheel_mode") or "dropout"
    cap = 8 if mode == "fixed" else 10
    body = "console.log(JSON.stringify(visibleCount()));"
    count = run_js(body, data["app_sets"], {"apps": True, "appState": {}, "state": {}},
                   categories=data["categories"], custom=data.get("custom_sets", []),
                   wheel_mode=mode)
    assert count <= cap, (
        f"the shipped actions.json ticks {count} sets by default — its wheel "
        f"({mode}) holds {cap}, and a default that breaks the cap is what put "
        "NINE on the owner's phone (owner 2026-08-06)")


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
    # Claude Tools is held OFF for this case (2026-08-12). The rule under test
    # is "a stored state one over the cap is brought back to it, and the app
    # set gives way first" — that needs a state exactly ONE over, and since
    # Claude Tools began shipping ticked the shipped roster is two over. The
    # fixture states the case; the shipped defaults have their own check above.
    got = run_js(body, sets, {"apps": True, "appState": {"Claude Tools": False},
                              "state": {}}, categories=cats)
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
            "title": "Ispravka UI dizajna meni… - VibeCoder - Visual Studio Code"}
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
        "Ispravka UI dizajna meni… - VibeCoder - Visual Studio Code [Administrator]": "vibecoder",
        "Kreiraj GUI smernice i p… - UVuruna - Visual Studio Code [Administrator]": "uvuruna",
        "ubacio sam 3 nove letter… - Watch Academy - Visual Studio Code": "watch academy",
        "Some Folder - Notepad": "",
        "": "",
    }
    for title, want in cases.items():
        got = agents_mod.title_folder(title)
        assert got == want, f"{title!r} -> {got!r}, expected {want!r}"


# -- E. the owner's WHEEL ORDER (build round R5, 2026-08-07) ----------------
# "on choose redosled setova po ringu na telefonu" — a new list in the desktop
# Controls editor, the SAME ladder widget already used for button arrangement,
# stored as `wheel_order` (a list of set NAMES) in actions.json. Position 1 =
# 12 o'clock, the rest clockwise — which `openWheel()` already draws correctly
# for ANY array order (i=0 is straight up, increasing i sweeps clockwise), so
# the whole feature IS `sortByWheelOrder()` ordering the array `allCats()`
# hands it. These four cases would all fail without that function.

def test_wheel_order_is_honoured():
    cats = [{"name": "Mouse", "required": True}, {"name": "Input", "required": True},
            {"name": "Settings", "required": True}, {"name": "Attach"},
            {"name": "Edit"}, {"name": "Navigate"}]
    body = "console.log(JSON.stringify(allCats().map((c) => c.name)));"
    order = ["Navigate", "Attach", "Mouse", "Input", "Settings", "Edit"]
    got = run_js(body, [], {"apps": True, "appState": {}, "state": {}},
                categories=cats, wheel_order=order)
    assert got == order, f"the wheel must ride in the OWNER's own order: {got}"


def test_a_non_riding_set_leaves_no_hole():
    """A set named in `wheel_order` but not currently ON (unticked) is simply
    absent from what rides — the ring closes up around it, never a gap."""
    cats = [{"name": "Mouse", "required": True}, {"name": "Input", "required": True},
            {"name": "Settings", "required": True},
            {"name": "Attach", "enabled": False},  # off — not riding right now
            {"name": "Edit"}, {"name": "Navigate"}]
    body = "console.log(JSON.stringify(allCats().map((c) => c.name)));"
    order = ["Navigate", "Attach", "Mouse", "Edit", "Input", "Settings"]
    got = run_js(body, [], {"apps": True, "appState": {}, "state": {}},
                categories=cats, wheel_order=order)
    assert got == ["Navigate", "Mouse", "Edit", "Input", "Settings"], (
        f"Attach is OFF — the ring must close up around it, not leave a hole "
        f"(no null/undefined entry, no gap in position): {got}")


def test_an_unknown_set_lands_at_the_end():
    """A set the owner's order does not mention (a future version's addition,
    or one he simply never dragged) goes to the END — after everything he DID
    arrange, never spliced into the middle of his own order."""
    cats = [{"name": "Mouse", "required": True}, {"name": "Input", "required": True},
            {"name": "Settings", "required": True},
            {"name": "Attach"}, {"name": "Edit"}, {"name": "Navigate"}]
    body = "console.log(JSON.stringify(allCats().map((c) => c.name)));"
    # His order never heard of "Edit" or "Navigate".
    order = ["Settings", "Mouse", "Input", "Attach"]
    got = run_js(body, [], {"apps": True, "appState": {}, "state": {}},
                categories=cats, wheel_order=order)
    assert got[:4] == order, f"the arranged sets must ride first, in his order: {got}"
    assert got[4:] == ["Edit", "Navigate"], (
        f"unmentioned sets land at the end, in their ORIGINAL relative order "
        f"(stable sort — never shuffled among themselves): {got}")


def test_cap_still_holds_with_a_wheel_order_and_app_sets_charging_it():
    """The cap of 8 (rule D/B above) must survive a custom order untouched —
    an app set still charges exactly what it always charged, a required set
    is never the one bumped, and the trim still comes from the arrangement's
    OWN end (build round R5 must not weaken the existing cap logic)."""
    sets = shipped_app_sets()  # VSCode + Claude share one process — 2 slots
    cats = [{"name": "Mouse", "required": True}, {"name": "Input", "required": True},
            {"name": "Settings", "required": True}, {"name": "Attach"},
            {"name": "Edit"}, {"name": "Navigate"}, {"name": "Cursor"}]
    # The app sets sit FIRST in the owner's order on purpose — the cap must
    # trim from the END OF THE SORTED RING, not silently favour app sets.
    order = ["Claude", "VSCode", "Cursor", "Navigate", "Edit", "Attach",
             "Mouse", "Input", "Settings"]
    body = """
layoutActive = 0;
layouts = [{ process: "code.exe", title: "Claude Code", agents: ["claude"] }];
console.log(JSON.stringify(allCats().map((c) => c.name)));
"""
    got = run_js(body, sets, {"apps": True, "appState": {}, "state": {}},
                categories=cats, wheel_order=order)
    assert len(got) == 8, f"the cap of 8 must still hold: {got}"
    assert {"Mouse", "Input", "Settings"} <= set(got), (
        f"a required set must never be the one bumped: {got}")
    assert got == ["Claude", "VSCode", "Cursor", "Navigate", "Edit",
                   "Mouse", "Input", "Settings"], (
        f"Attach (the last non-required set in HIS order) gives way, in his "
        f"own arrangement's own end, exactly as the untouched trim rule "
        f"always worked: {got}")


# -- F. a layout made from an EXTRACTED TAB still names its project ---------
# Owner report 2026-08-08: he builds a layout out of the Claude Code TAB and
# the wheel offers VS Code alone.
#
# WHY NO GUARD SAW IT. Every check above — and every check in
# test_layout_protocol.py — hand-typed one half of the join and asserted on the
# other. The server gate faked `agents_for` outright and answered `_title` with
# ONE author-written string for every hwnd, so a parent window and a torn-off
# tab were indistinguishable by construction; the phone gate was handed
# `agents: ["claude"]` as an input. The only title the code was ever asked
# about was one WE wrote. So this section writes nothing the join can read: it
# hands `layout_create` a window, fakes only Windows and the PowerShell probe,
# and asks the real client/sets.js which set names come out.
#
# THE FIXTURES ARE CAPTURED, NOT INVENTED (measurement 2026-08-08, read-only
# EnumWindows on his PC + the VS Code 1.107.0 sources he actually runs). VS
# Code creates every "Move into New Window" BrowserWindow with
# `title: productService.nameLong` on about:blank and the workbench overwrites
# document.title only later, so a torn-off tab is BORN carrying a title no
# regex can match. Which of the family his machine hands us at the instant we
# read is not proven — so the guard covers the whole family, and every one of
# them must still find the project.
TAB_NAME = "Ispravka UI dizajna meni…, Window 2: Editor Group 1"
SOURCE_TITLE = "Provera ROOT pravila i G… - UVuruna - Visual Studio Code [Administrator]"
EXTRACTED_TITLES = {
    "born bare — the product name, before the workbench paints": "Visual Studio Code",
    "the tab's own name, no folder anywhere in it": TAB_NAME,
    "not titled yet at all": "",
    "settled, folder present": SOURCE_TITLE,
}
# The project both titles name is `uvuruna`, and a conversation is live there.
LIVE_HERE = {"claude": {"uvuruna"}}
# A live conversation, but in another project of his — the same PC, the same
# claude.exe, and the answer must be NO.
LIVE_ELSEWHERE = {"claude": {"loading cube"}}

# His own handles, from the server log of 2026-08-08 (0x40c0e was the
# short-lived fourth Code.exe window — the extracted one).
SOURCE_HWND, EXTRACTED_HWND = 0x10B3A, 0x40C0E
MON = (0, 0, 3840, 2160)


class FakeUser32:
    """Only what `prune()` asks: does this window still exist."""

    def __init__(self, alive):
        self.alive = alive

    def IsWindow(self, hwnd):  # noqa: N802 — mirrors the Win32 name
        return 1 if hwnd in self.alive else 0

    def __getattr__(self, name):
        return lambda *a, **k: 0


class FakeWs:
    def __init__(self):
        self.sent = []

    async def send_text(self, text):
        self.sent.append(json.loads(text))


class FakeStream:
    width, height, monitor_index = 3840, 2160, 0


def install_windows(titles: dict, alive: set, extracted) -> None:
    """Fake WINDOWS, and nothing above it. `_title` answers PER HWND — the
    distinction between a parent window and the tab torn out of it is the
    whole subject, and a guard that returns one string for every handle
    cannot see it."""
    wm = window_manager
    wm._title = lambda hwnd: titles.get(hwnd, "")
    wm.is_alive = lambda hwnd: hwnd in alive
    wm._process_name = lambda hwnd: "Code.exe"
    wm._process_path = lambda hwnd: "C:/Code.exe"
    wm.icon_data_uri = lambda path: None
    wm.place_window = lambda hwnd, rect: True
    wm.raise_window = lambda hwnd, topmost=True: None
    wm.drop_topmost = lambda hwnd: True
    wm.freeze_transitions = lambda hwnd, disabled=True: None
    wm.wait_minimized = lambda hwnds, timeout_s=0: None
    wm._frame_rect = lambda hwnd: (0, 0, 1000, 1000)
    wm._work_area = lambda rect: rect
    wm._ledger_save = lambda: None
    wm.user32 = FakeUser32(alive)
    wm.window_at_hwnd = lambda hwnd: (
        {"hwnd": hwnd, "title": titles.get(hwnd, ""), "process": "Code.exe",
         "icon": None} if hwnd in alive else None)
    layout_api.rect_for_size = lambda w, h, i: MON
    # The extraction itself is Windows' job (SendInput drag / a menu click) and
    # is refused on this machine by the safety rules — `extracted` is the hwnd
    # it would have produced, or None for the failure that falls back to the
    # whole window.
    uia.extract_tab = lambda rect, x, y, info, name=None: extracted


def layout_entry(extracted_title: str, live: dict, tab: bool = True,
                 extraction_works: bool = True, close_source: bool = False) -> dict:
    """Drive the REAL creation path for one slot and return the layout as the
    phone receives it. Only Windows and the PowerShell probe are faked;
    `resolve_slot`, `LayoutRegistry.create`, `Layout.project`,
    `agents.title_folder` and `agents.agents_in` all run for real."""
    titles = {SOURCE_HWND: SOURCE_TITLE, EXTRACTED_HWND: extracted_title}
    alive = {SOURCE_HWND, EXTRACTED_HWND}
    install_windows(titles, alive, EXTRACTED_HWND if extraction_works else None)
    agents.live_agents = lambda: live       # the 1.85 s subprocess, and ONLY it
    layouts = window_manager.LayoutRegistry()
    ws, conn = FakeWs(), {"ratio": 9 / 16, "active": None, "region": None}
    asyncio.run(layout_api.layout_create(ws, layouts, FakeStream(), conn, {
        "mode": "solo", "orient": "portrait",
        "slots": [{"hwnd": SOURCE_HWND, "x": 0.3, "y": 0.02,
                   "tab": {"name": TAB_NAME} if tab else None}]}))
    if close_source:
        alive.discard(SOURCE_HWND)          # he closed the parent VS Code window
        return layouts.state(0, None)["layouts"][0]
    frames = [m for m in ws.sent if m.get("type") == "layout_state"]
    assert frames, f"creation never answered with a layout_state: {ws.sent}"
    return frames[0]["layouts"][0]


def wheel_of(entry: dict) -> list:
    """The set names that ride the phone's wheel for this layout — the real
    client/sets.js, over the payload the server really sent."""
    body = (f"layoutActive = 0;\nlayouts = [{json.dumps(entry)}];\n"
            "console.log(JSON.stringify(allCats().map((c) => c.name)));")
    return run_js(body, shipped_app_sets(),
                  {"apps": True, "appState": {}, "state": {}})


def code_wheel_sets(with_claude: bool) -> list[str]:
    """The shipped `code` app sets that may ride the wheel, in file order.

    DERIVED, never typed out (2026-08-12). These assertions used to spell
    `["VSCode", "Claude"]` in four places, so the day Claude Tools started
    shipping ticked — drop-out's real cap of 10 having made the room — four
    checks failed for a reason that had nothing to do with what any of them
    tests. `with_claude=False` is the other half: a window whose project has
    no live conversation keeps only the sets that ask for no agent."""
    return [s["name"] for s in shipped_app_sets()
            if s.get("process") == "code" and s.get("enabled", True)
            and (with_claude or not s.get("agent"))]


def test_an_extracted_tab_keeps_the_claude_set():
    """His report, end to end. Whatever title the torn-off window carries at
    the moment we look, the layout must still find the project — because the
    window it was torn OUT of is alive and says so, and it is READ, not
    remembered."""
    for why, title in EXTRACTED_TITLES.items():
        got = wheel_of(layout_entry(title, LIVE_HERE))
        assert got == code_wheel_sets(True), (
            f"extracted window titled {title!r} ({why}) → wheel {got}. A live "
            "Claude conversation in this window's project must put the Claude "
            "set on the wheel beside VSCode (owner 2026-08-08).")


def test_a_whole_window_and_a_FAILED_extraction_keep_it_too():
    """The two paths that were never broken must not break now: a plain
    window slot, and a tab whose extraction failed and fell back to the whole
    window (that fallback is why his OTHER layouts kept working)."""
    assert wheel_of(layout_entry("", LIVE_HERE, tab=False)) == code_wheel_sets(True)
    got = wheel_of(layout_entry("", LIVE_HERE, extraction_works=False))
    assert got == code_wheel_sets(True), f"the whole-window fallback lost it: {got}"


def test_no_live_conversation_there_means_no_claude_set():
    """The other half, or the guard proves nothing: `claude.exe` running in
    ANOTHER of his projects must leave this window plain VSCode — including
    for the extracted title that DOES carry a folder."""
    for title in ("Visual Studio Code", SOURCE_TITLE):
        got = wheel_of(layout_entry(title, LIVE_ELSEWHERE))
        assert got == code_wheel_sets(False), (
            f"{title!r} with the conversation live elsewhere → {got}; the "
            "Claude commands must not be carried into a plain editor")


def test_the_source_window_may_die_and_the_project_survives():
    """He tears the tab off and then closes the VS Code window it came from.
    The folder read at creation is the last resort — and it is a FOLDER, not
    an answer: whether a conversation is live in it is still read from the
    process table, so the same layout goes plain the moment nothing runs
    there."""
    got = wheel_of(layout_entry("Visual Studio Code", LIVE_HERE, close_source=True))
    assert got == code_wheel_sets(True), (
        f"the project was lost with the window: {got}")
    got = wheel_of(layout_entry("Visual Studio Code", LIVE_ELSEWHERE,
                                close_source=True))
    assert got == code_wheel_sets(False), (
        f"a remembered FOLDER became a remembered ANSWER: {got}")



# -- E. the wheel remembers which category he had ---------------------------
# Owner report 2026-08-08: "kad god ucitam neku sliku ili nesto, kada uradi
# onaj blagi reset, aplikacija uvek mi vrati na ovaj default — levo Mouse set
# a desno Input set." An excursion hides the page, a hidden page closes the
# socket by rule, and the reconnect used to take the DESKTOP defaults every
# time. These checks pin the fix, and the third one is the reason it is stored
# by NAME: the list is not stable.

BASIC = [
    {"name": "Mouse", "required": True},
    {"name": "Input", "required": True},
    {"name": "Settings", "required": True},
    {"name": "Edit"},
    {"name": "Attach"},
]


def _groups(prefs, left_default, right_default, categories, **kw):
    # Seeded through prefSet rather than handed to run_js: its `prefs`
    # argument is the SETS PICKER's own blob (one key, `setsPrefs`), and the
    # remembered category is a separate key on the same bridge. Writing it the
    # way the page writes it is also the more honest fixture — the first
    # version of this helper passed the dict straight in, nothing was ever
    # read, and two checks passed for the wrong reason.
    seed = "\n".join(f'prefSet({k!r}, {v!r});' for k, v in prefs.items())
    return run_js(
        f"""
{seed}
const riding = allCats();
console.log(JSON.stringify({{
  left: riding[restoredGroup("left", {left_default}, riding)].name,
  right: riding[restoredGroup("right", {right_default}, riding)].name,
}}));
""", [], {}, categories=categories, **kw)


def test_his_choice_survives_the_excursion():
    """The report itself: he opened Edit on the left, went to the gallery, and
    came back to Mouse."""
    got = _groups({"groupLeft": "Edit", "groupRight": "Attach"}, 0, 1, BASIC)
    assert got == {"left": "Edit", "right": "Attach"}, got


def test_the_desktop_default_still_decides_a_first_connection():
    """Nothing remembered — a phone that has never chosen must land on what
    the desktop set, exactly as before."""
    got = _groups({}, 0, 1, BASIC)
    assert got == {"left": "Mouse", "right": "Input"}, got


def test_a_reorder_cannot_move_his_choice():
    """THE REASON IT IS A NAME. `wheel_order` reorders the ring, so the index
    that meant Edit yesterday means something else today. Same prefs, same
    sets, different order — the answer must not move."""
    order = ["Attach", "Edit", "Settings", "Input", "Mouse"]
    got = _groups({"groupLeft": "Edit", "groupRight": "Attach"}, 0, 1, BASIC,
                  wheel_order=order)
    assert got == {"left": "Edit", "right": "Attach"}, got


def test_a_set_that_left_the_wheel_falls_back_quietly():
    """An app-aware set rides only while its layout is focused, so a
    remembered set that is GONE is the normal case, not an error: fall back to
    the desktop default without complaint."""
    # BOTH remembered names must be absent, or the check tests nothing: the
    # first version named "Edit", which IS in BASIC, so the right group stayed
    # on it correctly and the assertion was simply wrong. Caught by running it.
    got = _groups({"groupLeft": "Claude", "groupRight": "Media"}, 2, 0, BASIC)
    assert got == {"left": "Settings", "right": "Mouse"}, got


def test_a_default_past_the_end_is_clamped():
    """A desktop default can outlive the set it pointed at (the owner unticks
    one in the picker). It may never index past the ring."""
    got = _groups({}, 99, 99, BASIC)
    assert got == {"left": "Attach", "right": "Attach"}, got

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
    ("the wheel order is honoured", test_wheel_order_is_honoured),
    ("a non-riding set leaves no hole", test_a_non_riding_set_leaves_no_hole),
    ("an unknown set lands at the end", test_an_unknown_set_lands_at_the_end),
    ("the cap of 8 still holds with a wheel order and app sets charging it",
     test_cap_still_holds_with_a_wheel_order_and_app_sets_charging_it),
    ("an EXTRACTED tab keeps the Claude set",
     test_an_extracted_tab_keeps_the_claude_set),
    ("a whole window and a FAILED extraction keep it too",
     test_a_whole_window_and_a_FAILED_extraction_keep_it_too),
    ("no live conversation there means no Claude set",
     test_no_live_conversation_there_means_no_claude_set),
    ("the source window may die and the project survives",
     test_the_source_window_may_die_and_the_project_survives),
    ("his chosen category survives an excursion",
     test_his_choice_survives_the_excursion),
    ("a first connection still takes the desktop default",
     test_the_desktop_default_still_decides_a_first_connection),
    ("a wheel reorder cannot move his choice (stored by NAME)",
     test_a_reorder_cannot_move_his_choice),
    ("a set that left the wheel falls back quietly",
     test_a_set_that_left_the_wheel_falls_back_quietly),
    ("a default past the end of the ring is clamped",
     test_a_default_past_the_end_is_clamped),
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
