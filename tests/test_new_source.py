"""THE NEW SOURCE GATE — what is already open, what an app can do, and whose
window it is (owner ballot 2026-08-13: T28 / T29 / T30).

His two pictures, and one measured cause each:

  * **Picture 1** — he picked a recent FOLDER that VS Code already had open.
    VS Code answered by raising the window it already held, so no NEW window
    ever came into being, and `recents.open_entry`'s poll ran its full
    25-second give-up point with the loading cube on his phone the whole time.
  * **Picture 2** — the phone asked him whether to move a window into the
    layout, about a window HE HAD JUST ASKED US TO OPEN. `layout_popup.mine()`
    exists for exactly this (constraint 19, point 4A) and the New source had
    never called it — the only caller was tab extraction.

What is held here, each proven by planting its own defect:

  1. A recent whose folder an app already holds comes back `open: True` — and
     the row is still IN the list (his own ballot: a project missing from the
     list is a thing he would hunt for; a dimmed row answers him).
  2. A recent nothing holds is NOT marked. A rule that dims everything is the
     same feature as no list at all.
  3. THE EXPLORER TITLE IS PARSED, NOT COMPARED WHOLE. Measured on his own
     desk while this was being built: Windows 11 titles the window
     `icons - File Explorer`, so the first version of the feature matched
     nothing at all and shipped a rule that could never fire.
  4. An app that was ALREADY RUNNING and produced no window gives up in
     `RUNNING_TIMEOUT_S`, not in `OPEN_TIMEOUT_S` — and the sentence NAMES
     what happened instead of leaving him with a shorter mystery.
  5. A COLD start still gets the full patience. The fast give-up is for the
     case that cannot end, never for a slow PC.
  6. A window the New source opens is marked `layout_popup.mine()` — his
     picture 2, and the whole of it.
  7. Every act in the catalogue asserts the PROCESS before it injects: a
     target that is not the app the row was drawn for costs ZERO injections.
  8. The layout's own group is EMPTY for an app we have no acts for, and for
     the desktop — a heading standing over nothing is a promise the panel
     cannot keep.
  9. The VS Code "new window" act refuses when it cannot find the project's
     PATH, rather than handing a constructed path to a launcher.

NOTHING HERE TOUCHES THE OWNER'S DESKTOP: no window is enumerated, opened,
raised or typed into. `list_windows` is a list this file writes, `Popen` is
recorded, and the injector counts its chords instead of firing them.

Run:  .venv\\Scripts\\python tests/test_new_source.py
"""

import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import content  # noqa: E402
import layout_acts  # noqa: E402
import layout_popup  # noqa: E402
import recents  # noqa: E402
import window_manager as wm  # noqa: E402

from _focus_fakes import run_checks  # noqa: E402

# The dispatcher harness is REUSED, never copied: `tests/test_layout_protocol.py`
# already owns a fake desk, a fake socket and a `drive()` that runs messages
# through the real `web._receive_input`. Importing it costs nothing (its checks
# only run under `__main__`) and a second copy of a Win32 fake is precisely how
# two gates come to disagree about what a desk is.
import test_layout_protocol as proto  # noqa: E402

VSCODE_WIN = 0x11
EXPLORER_WIN = 0x12
NEW_WIN = 0x21


# ═══════════════════════════ THE FAKE DESK ═══════════════════════════
class Desk:
    """The windows standing right now. `open_entry` reads this twice — before
    the launch and while polling — which is the whole newness argument, so the
    fake has to be able to CHANGE between the two."""

    def __init__(self, windows):
        self.windows = list(windows)

    def install(self):
        wm.list_windows = lambda: list(self.windows)
        wm.window_at_hwnd = lambda h: next(
            (dict(w) for w in self.windows if w["hwnd"] == h), None)
        return self

    def add(self, hwnd, process, title):
        self.windows.append({"hwnd": hwnd, "process": process, "title": title,
                             "icon": ""})


def win(hwnd, process, title):
    return {"hwnd": hwnd, "process": process, "title": title, "icon": ""}


class Injector:
    """Counts what would have been fired. Every refusal in this gate is proven
    by this staying at zero — "it refused" and "it refused having already sent
    three keys into a stranger's window" are different products."""

    def __init__(self):
        self.chords = []
        self.keys = []

    def press_chord(self, chord):
        self.chords.append(chord)

    def press_key(self, key):
        self.keys.append(key)

    def type_text(self, text, guard=None):
        return ""

    @property
    def total(self):
        return len(self.chords) + len(self.keys)


def guard_for(hwnd):
    """A focus guard that always answers the same window — the fence holding."""
    return lambda: hwnd


def process_of(mapping):
    return lambda hwnd: mapping.get(hwnd, "")


# ═══════════════════════════ 1-3. WHAT IS ALREADY OPEN ═══════════════
def _entries_with(recent_paths, desk_windows):
    """`entries()` driven over a staged VS Code recent list and a staged desk.

    THROUGH `entries()` AND NEVER THROUGH `_is_open` (this project's own named
    failure mode, caught here live by planting): the first version of the two
    checks below called the helper directly, and the plant "never mark
    anything" — a defect that dims NOTHING on his phone — went through them
    green. The phone reads the `open` FIELD, so that is what a check must
    read; a rule proven only where nobody consumes it is not proven."""
    Desk(desk_windows).install()
    real_v, real_e, real_exe = (recents.vscode_recents,
                                recents.explorer_recents, recents.app_exe)
    recents.vscode_recents = lambda: [
        {"target": t, "label": Path(t).name, "sub": t} for t in recent_paths]
    recents.explorer_recents = lambda: []
    recents.app_exe = lambda app: "C:/fake/" + app + ".exe"
    try:
        return {e["target"]: e for e in recents.entries()
                if e["kind"] == "recent"}
    finally:
        (recents.vscode_recents, recents.explorer_recents,
         recents.app_exe) = real_v, real_e, real_exe


HELD = r"U:\Coding\UVuruna\Applications\VibeCoder"
FREE = r"U:\Coding\Other\PromptPainter"
VS_WINDOW = "main.py - VibeCoder - Visual Studio Code"


def check_a_folder_the_app_already_holds_is_marked_and_still_listed() -> bool:
    """His picture 1. The row must come back marked AND present: dropping it
    would answer a question he did not ask, and marking nothing at all is the
    defect itself."""
    rows = _entries_with([HELD, FREE], [win(VSCODE_WIN, "Code.exe", VS_WINDOW)])
    row = rows.get(HELD)
    return bool(row) and row["open"] is True and bool(row["why"])


def check_a_folder_nothing_holds_is_not_marked() -> bool:
    """The other half, and the one a too-eager rule breaks: a list where every
    row is dimmed is a list with nothing in it."""
    rows = _entries_with([HELD, FREE], [win(VSCODE_WIN, "Code.exe", VS_WINDOW)])
    row = rows.get(FREE)
    return bool(row) and row["open"] is False and row["why"] == ""


def check_the_explorer_title_is_parsed_and_not_compared_whole() -> bool:
    """MEASURED ON HIS DESK while this was being written, which is why it is a
    check and not a comment: Windows 11 reads `icons - File Explorer`. The
    first version compared the whole title, matched nothing ever, and would
    have shipped a feature that could not fire once."""
    Desk([win(EXPLORER_WIN, "explorer.exe", "icons - File Explorer")]).install()
    held = recents.open_folders()
    if "icons" not in held["explorer"]:
        return False
    # …and a folder whose own NAME contains the separator keeps it. A bare
    # split on " - " would leave him with half a folder name.
    return recents._explorer_folder("notes - drafts") == "notes - drafts"


# ═══════════════════════════ 4-5. THE WAIT THAT CAN END ═══════════════
class FakeTime:
    """A clock this gate owns outright. `recents.time` is REPLACED rather than
    `time.sleep` patched: patching the real module would slow every other
    thread on this machine, and a gate must never be able to do that. The
    give-up points are real seconds and no check may spend them."""

    def __init__(self):
        self.now = 1000.0
        self.slept = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.slept += seconds
        self.now += seconds


def _run_open(target):
    """Drive `open_entry` with a launcher that opens NOTHING, and report how
    long it was willing to wait. The target really EXISTS on disk, because
    `open_entry` refuses a vanished path before it ever launches — an earlier
    version of this check pointed at a made-up folder and measured that
    refusal instead of the wait, which is a green check over an unproven
    rule."""
    clock = FakeTime()
    real_time, real_popen = recents.time, recents.subprocess.Popen
    recents.time = clock
    recents.subprocess.Popen = lambda *a, **k: None
    try:
        result = recents.open_entry(f"vscode|recent|{target}")
    finally:
        recents.time = real_time
        recents.subprocess.Popen = real_popen
    return clock.slept, result


def check_an_already_running_app_that_opens_nothing_gives_up_fast_and_names_it() -> bool:
    """His picture 1 surviving the grey-out: the folder was opened in the
    seconds between the list and his tap. The wait must end in
    RUNNING_TIMEOUT_S, and the sentence must say the PC brought the window it
    already had forward — a shorter spinner over the same mystery is not a
    fix."""
    Desk([win(VSCODE_WIN, "Code.exe", "x - VibeCoder - Visual Studio Code")]).install()
    waited, result = _run_open(PROJECT_DIR)
    if not result.get("error"):
        return False
    if waited > recents.RUNNING_TIMEOUT_S + recents.OPEN_POLL_S:
        return False
    # NAMED, not merely short. The whole point of the fast give-up is that he
    # learns what the PC did — five seconds of spinner over the same mystery
    # is not the fix he asked for — so the sentence must say the app brought
    # the window it ALREADY had FORWARD, and must say which app.
    said = result["error"].lower()
    return "forward" in said and "already" in said and "code.exe" in said


def check_a_cold_start_still_gets_the_full_patience() -> bool:
    """The fast give-up is for a wait that CANNOT end, never for a slow PC.
    With no window of that app standing, VS Code is really starting and the
    old 25 s is exactly right."""
    Desk([win(EXPLORER_WIN, "explorer.exe", "icons - File Explorer")]).install()
    waited, result = _run_open(PROJECT_DIR)
    return bool(result.get("error")) and waited > recents.RUNNING_TIMEOUT_S * 2


# ═══════════════════════════ 6. WHOSE WINDOW IT IS ═══════════════════
def check_a_window_the_new_source_opens_is_marked_as_ours() -> bool:
    """HIS PICTURE 2, and the whole of it. Without this line the popup sweep
    meets a brand-new top-level window of a known app and asks him about a
    window he asked US to open, seconds earlier."""
    desk = Desk([win(VSCODE_WIN, "Code.exe", "x - Other - Visual Studio Code")]).install()
    layout_popup._OURS.clear()

    def popen(*a, **k):
        # The launch really produces a window, which is the case the mark is
        # about — a launch that opens nothing has nothing to mark.
        desk.add(NEW_WIN, "Code.exe", "main.py - VibeCoder - Visual Studio Code")

    real_time, real_popen = recents.time, recents.subprocess.Popen
    recents.time, recents.subprocess.Popen = FakeTime(), popen
    try:
        info = recents.open_entry(f"vscode|recent|{PROJECT_DIR}")
    finally:
        recents.time, recents.subprocess.Popen = real_time, real_popen
    if info.get("hwnd") != NEW_WIN:
        return False
    return layout_popup.is_mine(NEW_WIN) if hasattr(layout_popup, "is_mine") \
        else NEW_WIN in layout_popup._OURS


# ═══════════════════════════ 7-9. THE LAYOUT'S OWN ACTS ══════════════
def check_an_act_into_the_wrong_app_costs_zero_injections() -> bool:
    """Rule 2 of the module, and constraint 11's whole subject: `Ctrl+T` is a
    GLOBAL chord fired into whatever really holds the keyboard. A fence
    pointing at anything but the app this row was drawn for must cost nothing
    at all — not a refused act after two keys."""
    injector = Injector()
    problem = layout_acts.run(
        "chrome|tab", injector, guard_for(0x55),
        process_of={0x55: "notepad.exe"}.get and process_of({0x55: "notepad.exe"}))
    return bool(problem) and injector.total == 0


def check_the_right_app_really_gets_its_chord() -> bool:
    """The other half — a check that only ever proves refusals proves a
    feature that does nothing."""
    injector = Injector()
    problem = layout_acts.run(
        "chrome|tab", injector, guard_for(0x66),
        process_of=process_of({0x66: "chrome.exe"}))
    return problem == "" and injector.chords == ["ctrl+t"]


def check_an_app_with_no_acts_offers_no_group() -> bool:
    """A heading over an empty list is a promise the panel cannot keep — and
    the desktop (no process at all) is the same case."""
    return layout_acts.catalogue("notepad.exe") == [] \
        and layout_acts.catalogue("") == []


def check_the_three_apps_each_offer_their_own_acts() -> bool:
    """What he ticked, by id, so a row silently disappearing is a red line."""
    ids = {app: [r["id"] for r in layout_acts.catalogue(proc)]
           for app, proc in layout_acts.PROCESS_OF_APP.items()}
    return ("vscode|claude" in ids["vscode"] and "vscode|window" in ids["vscode"]
            and {"chrome|tab", "chrome|reopen", "chrome|clip"} <= set(ids["chrome"])
            and {"explorer|tab", "explorer|up"} <= set(ids["explorer"]))


def check_a_project_whose_path_is_unknown_is_refused_not_guessed() -> bool:
    """A window title carries a folder's NAME and never its path. When VS
    Code's own recent list cannot say where that project lives, the honest act
    is a sentence — a constructed path handed to a launcher opens a stranger's
    folder or nothing, and both are worse."""
    injector = Injector()
    real = recents.vscode_recents
    recents.vscode_recents = lambda: []          # nothing to match against
    try:
        problem = layout_acts.run(
            "vscode|window", injector, guard_for(0x77),
            folder="vibecoder", process_of=process_of({0x77: "code.exe"}))
    finally:
        recents.vscode_recents = real
    return bool(problem) and injector.total == 0


def check_the_claude_command_is_the_extension_s_real_one() -> bool:
    """READ from the extension's own package.json on 2026-08-13
    (`claude-vscode.newConversation`), never invented — the palette's Enter
    runs whatever the filter left standing, so a wrong name is an arbitrary VS
    Code command. Held to the same standard `CLAUDE_FOCUS_COMMAND` is."""
    return (layout_acts.CLAUDE_NEW_COMMAND == "Claude Code: New Conversation"
            and content.CLAUDE_FOCUS_COMMAND == "Claude Code: Focus input")


# ═════════ 13-15. THE ACTS, THROUGH THE REAL DISPATCHER ═════════
# Owner ballot 2026-08-13 (T29). The checks above prove the CATALOGUE and the
# fence as functions; these three drive the two new messages through
# `web._receive_input` itself, which is the only thing that can catch a handler
# that RAISES before sending anything — which leaves the phone on a spinner
# forever and is invisible to every unit test. `layout_list` shipped exactly
# that defect once (a shadowed name, four green guards, "nothing happens").
#
# They live here rather than in tests/test_layout_protocol.py, which asks the
# same question of every OTHER layout message, for one reason and it is not
# taste: that file stands at THE STRUCTURE LAW's wall, and this gate's subject
# IS the New source. A file split by responsibility beats a ratchet.
def check_layout_acts_answers_at_the_desktop() -> bool:
    """From the desktop the answer must still ARRIVE, saying `in_layout:
    false` with an empty list — the phone draws one group or two off this
    frame, so an absent answer is a panel that never renders."""
    proto.install_fakes()
    ws, _, _ = proto.drive([{"type": "layout_acts"}])
    frames = proto.sent_of(ws, "layout_acts")
    return (len(frames) == 1 and frames[0]["in_layout"] is False
            and frames[0]["entries"] == [])


def check_layout_acts_answers_inside_a_layout() -> bool:
    """And inside one it names the app and offers its acts."""
    proto.install_fakes()
    ws, conn, layouts = proto.drive([
        {"type": "layout_list"},
        {"type": "layout_create", "mode": "solo", "orient": "landscape",
         "slots": [{"hwnd": proto.WIN_A, "tab": None, "x": 0.5, "y": 0.5}]},
        {"type": "layout_acts"},
    ])
    frames = proto.sent_of(ws, "layout_acts")
    if len(frames) != 1 or frames[0]["in_layout"] is not True:
        return False
    # The member's process decides the catalogue; a fake desk of Notepad windows
    # would legitimately offer nothing, so this asserts the SHAPE both ways.
    entries = frames[0]["entries"]
    return isinstance(entries, list) and bool(frames[0].get("app")) == bool(entries)


def check_an_act_at_the_desktop_is_refused_and_not_injected() -> bool:
    """Every act is an act on a MEMBER. At the desktop the handler must refuse
    with a toast — and never reach `layout_acts.run`, which would fire a global
    chord at whatever holds the keyboard (constraint 11)."""
    proto.install_fakes()
    fired = []
    real_run = proto.layout_api.layout_acts_mod.run
    proto.layout_api.layout_acts_mod.run = lambda *a, **k: fired.append(a) or ""
    try:
        ws, _, _ = proto.drive([{"type": "layout_act", "id": "chrome|tab"}])
    finally:
        proto.layout_api.layout_acts_mod.run = real_run
    return not fired and len(proto.sent_of(ws, "toast")) == 1


CHECKS = [
    ("a folder the app already holds is marked, and still listed",
     check_a_folder_the_app_already_holds_is_marked_and_still_listed),
    ("a folder nothing holds is not marked",
     check_a_folder_nothing_holds_is_not_marked),
    ("the Explorer title is parsed, not compared whole",
     check_the_explorer_title_is_parsed_and_not_compared_whole),
    ("an already-running app that opens nothing gives up fast, and names it",
     check_an_already_running_app_that_opens_nothing_gives_up_fast_and_names_it),
    ("a cold start still gets the full patience",
     check_a_cold_start_still_gets_the_full_patience),
    ("a window the New source opens is marked as ours",
     check_a_window_the_new_source_opens_is_marked_as_ours),
    ("an act into the wrong app costs zero injections",
     check_an_act_into_the_wrong_app_costs_zero_injections),
    ("the right app really gets its chord",
     check_the_right_app_really_gets_its_chord),
    ("an app with no acts offers no group",
     check_an_app_with_no_acts_offers_no_group),
    ("each of the three apps offers its own acts",
     check_the_three_apps_each_offer_their_own_acts),
    ("a project whose path is unknown is refused, never guessed",
     check_a_project_whose_path_is_unknown_is_refused_not_guessed),
    ("the Claude command is the extension's real one",
     check_the_claude_command_is_the_extension_s_real_one),
    ("layout_acts answers at the desktop, through the dispatcher",
     check_layout_acts_answers_at_the_desktop),
    ("layout_acts answers inside a layout, through the dispatcher",
     check_layout_acts_answers_inside_a_layout),
    ("an act at the desktop is refused, and injects nothing",
     check_an_act_at_the_desktop_is_refused_and_not_injected),
]


def main() -> int:
    return run_checks("NEW SOURCE GATE", CHECKS,
                      "what is open, what an app can do, and whose window it is")


if __name__ == "__main__":
    raise SystemExit(main())
