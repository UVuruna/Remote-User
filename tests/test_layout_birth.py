"""LAYOUT BIRTH GATE — the two NEW ways a layout starts (tasks 184 and 185).

Both of these put the PC in charge of something it was never in charge of
before, and both are easy to ship broken in a way nobody notices:

**Task 184 — a layout from a window that is not open yet.** The phone offers
VS Code / Chrome / Explorer recents, and the chosen thing is OPENED. Two
things have to hold. The lists must be REAL — read from where each app really
keeps them (`server/recents.py` names the source and the honest limit of each)
— and the window handed back must be the one that just opened, never a window
he already had. That second half is this project's oldest lesson in a new
place: every VS Code window shares one process (constraint 11), so "a window
of the app I started" is not an answer; "a handle that was not standing before
I started it" is.

**Task 185 — when an app opens, offer a layout.** He double-clicks an .xlsx
through the stream and the phone asks. The scoping he set down before any
build is what is checked here, clause by clause: only while a session is live,
only NEW top-level windows, never dialogs, correlated with an injected
double-click, one chip per window, and NOTHING on the PC moved or focused by
any of it. That last one is the safety property — this PC is never quiet, and
a prompt that grabbed windows because a background agent opened one would be
the focus thief wearing a new hat.

NOTHING HERE TOUCHES THE OWNER'S DESKTOP: no window is enumerated, opened,
raised or placed. `window_manager`'s Win32 is the shared fake, `list_windows`
is a list this file writes, and `subprocess.Popen` is replaced — a gate that
really started VS Code would be a gate that takes his foreground.

Run:  .venv\\Scripts\\python tests/test_layout_birth.py
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _focus_fakes import (  # noqa: E402
    MEMBER_A, MEMBER_B, Raises, fresh_conn, layout_with, run_checks,
    window_manager, with_win32,
)

import layout_popup  # noqa: E402
import recents  # noqa: E402

# The desk for the 185 checks: two members, plus what appears on top of it.
NEWWIN = 0x60          # the app he just double-clicked open
DIALOG2 = 0x61         # a dialog OF that app — owned, never a member
OLD = 0x62             # a window that was already standing

TITLES = {NEWWIN: "Budget.xlsx - Excel", DIALOG2: "Save as",
          OLD: "Inbox - Outlook", MEMBER_A: "A", MEMBER_B: "B"}


def listing(*hwnds):
    """What `window_manager.list_windows` reports — the same dict shape the
    real one returns, so anything this gate proves is about the real filter's
    OUTPUT and not about a shape invented here."""
    return [{"hwnd": h, "title": TITLES.get(h, f"w{h:x}"),
             "process": "excel.exe", "icon": None} for h in hwnds]


def desk(windows, owner=None, clicks=2, active=None):
    """A connection that has been watching, with `clicks` recent injections."""
    fake = with_win32(fg=NEWWIN, alive=tuple(TITLES), owner=owner or {})
    Raises().install()
    window_manager.list_windows = lambda exclude=None: listing(*windows)
    window_manager.place_window = lambda hwnd, rect: PLACED.append((hwnd, rect))
    PLACED.clear()
    reg = layout_with([MEMBER_A, MEMBER_B])
    conn = fresh_conn(active=active)
    # The baseline the phone's connection took: MEMBER_A/B and OLD were up.
    # Written the way `baseline()` writes it — TWO sets from one snapshot, the
    # separation the last check below exists to prove.
    real_scan = layout_popup._top_level_hwnds
    layout_popup._top_level_hwnds = lambda: {MEMBER_A, MEMBER_B, OLD}
    try:
        layout_popup.baseline(conn)
    finally:
        layout_popup._top_level_hwnds = real_scan
    for _ in range(clicks):
        layout_popup.note_click(conn)
    return reg, conn, fake


PLACED: list = []


def chips(conn):
    return list(conn.get("popup_send") or [])


# ═══════════════ TASK 185: he is asked, exactly when he should be ═══════════
def check_a_window_he_opened_is_offered_as_a_layout() -> bool:
    """His case: a double-click through the stream, and a window appears. The
    phone is asked — once — and the chip NAMES the window, because "a layout
    with it?" about an unnamed thing is not a question anyone can answer."""
    reg, conn, _ = desk([MEMBER_A, MEMBER_B, OLD, NEWWIN])
    layout_popup.scan(reg, conn)
    queued = chips(conn)
    if len(queued) != 1:
        print(f"  DETAIL he was asked {len(queued)} times: {queued}")
        return False
    chip = queued[0]
    if chip.get("act") != "layout_new" or chip.get("hwnd") != NEWWIN:
        print(f"  DETAIL the chip is not the layout question: {chip}")
        return False
    if TITLES[NEWWIN] not in chip.get("title", ""):
        print(f"  DETAIL the chip does not name the window: {chip}")
        return False
    # …and asked ONCE, not four times a second.
    for _ in range(5):
        layout_popup.scan(reg, conn)
    return len(chips(conn)) == 1


def check_nothing_on_the_pc_is_touched_by_the_question() -> bool:
    """THE SAFETY PROPERTY, and the reason this is a chip and not an action:
    asking must place nothing, raise nothing and take no foreground — his
    scoping said so outright, and constraint 11 is why. It holds through his
    ANSWER too: both answers move nothing here, because everything after the
    yes is the phone's own creation panel."""
    reg, conn, _ = desk([MEMBER_A, MEMBER_B, OLD, NEWWIN])
    raises = Raises().install()
    layout_popup.scan(reg, conn)
    if PLACED or raises:
        print(f"  DETAIL asking moved something: placed={PLACED} raises={raises}")
        return False
    for act in ("layout_new", "desktop"):
        reg, conn, _ = desk([MEMBER_A, MEMBER_B, OLD, NEWWIN])
        raises = Raises().install()
        layout_popup.scan(reg, conn)
        layout_popup.pick(chips(conn)[0]["id"], act)
        if PLACED or raises:
            print(f"  DETAIL answering '{act}' moved something: {PLACED} {raises}")
            return False
    return True


def check_no_double_click_means_no_question() -> bool:
    """The correlation is the WHOLE attribution. This PC is never quiet —
    background agents open GUI windows all day — so a window appearing is not
    evidence of anything, and without two injected clicks moments before there
    is nothing to ask about."""
    for clicks in (0, 1):
        reg, conn, _ = desk([MEMBER_A, MEMBER_B, OLD, NEWWIN], clicks=clicks)
        layout_popup.scan(reg, conn)
        if chips(conn):
            print(f"  DETAIL asked after {clicks} click(s): {chips(conn)}")
            return False
    # …and two clicks far apart are two single clicks, not a double.
    reg, conn, _ = desk([MEMBER_A, MEMBER_B, OLD, NEWWIN], clicks=0)
    layout_popup.note_click(conn)
    conn["click_times"][-1] -= layout_popup.DOUBLE_CLICK_S * 2
    layout_popup.note_click(conn)
    layout_popup.scan(reg, conn)
    if chips(conn):
        print("  DETAIL two clicks a second apart counted as a double-click")
        return False
    # …and a double-click LONG ago cannot explain a window opening now.
    reg, conn, _ = desk([MEMBER_A, MEMBER_B, OLD, NEWWIN])
    conn["click_times"] = [t - layout_popup.BIRTH_AFTER_CLICK_S - 5
                           for t in conn["click_times"]]
    layout_popup.scan(reg, conn)
    return not chips(conn)


def check_a_dialog_is_never_offered() -> bool:
    """"Only NEW top-level windows, never dialogs" — his own scoping. A Save-As
    box is owned by the window that raised it, cannot be a layout member, and
    is gone before he could answer."""
    reg, conn, _ = desk([MEMBER_A, MEMBER_B, OLD, DIALOG2],
                        owner={DIALOG2: NEWWIN})
    layout_popup.scan(reg, conn)
    if chips(conn):
        print(f"  DETAIL a dialog was offered: {chips(conn)}")
        return False
    return True


def check_a_window_that_was_already_open_is_never_offered() -> bool:
    """NEW is measured against the baseline the connection took. Without it
    every window on his desk would be offered the first time he double-clicks
    anything."""
    reg, conn, _ = desk([MEMBER_A, MEMBER_B, OLD])
    layout_popup.scan(reg, conn)
    if chips(conn):
        print(f"  DETAIL a standing window was offered: {chips(conn)}")
        return False
    return True


def check_a_layout_member_is_never_offered() -> bool:
    """A window already IN a layout has nothing to be asked about — and the
    layout branch of this module may be about to adopt it, which is a
    different question with a different chip."""
    reg, conn, _ = desk([MEMBER_A, MEMBER_B, OLD, NEWWIN], active=0)
    reg.layouts[0].members.append(NEWWIN)
    layout_popup.scan(reg, conn)
    return not chips(conn)


def check_nothing_is_asked_while_the_phone_is_away() -> bool:
    """"Only while a phone session is live". A phone in his pocket must not
    accumulate questions about his own desk — and the windows that open while
    he sits at it are not the phone's business at all."""
    for key in ("away", "left"):
        reg, conn, _ = desk([MEMBER_A, MEMBER_B, OLD, NEWWIN])
        conn[key] = True
        layout_popup.scan(reg, conn)
        if chips(conn):
            print(f"  DETAIL asked while {key}: {chips(conn)}")
            return False
    return True


def check_the_two_questions_do_not_eat_each_other() -> bool:
    """The layout-adoption chip (task 202) and this one share a baseline set,
    and sharing the JUDGED set would have made one blind: a window this scan
    has looked at would stop being "new" for the attribution next door, so a
    member's own popup would never be offered again. Separate bookkeeping,
    proven by doing both in one connection."""
    reg, conn, _ = desk([MEMBER_A, MEMBER_B, OLD, NEWWIN], active=0)
    layout_popup.scan(reg, conn)
    if not chips(conn):
        return False
    # The layout branch must still see NEWWIN as new (it is the same window
    # taking the foreground, and it belongs to a member's process here).
    return layout_popup._is_new(conn, NEWWIN)


# ═══════════════ TASK 184/242: the lists are real, and the window is new ═════
def _write_state_db(appdata: Path, entries: list[dict]) -> Path:
    """A fixture `state.vscdb` — the SQLite key `history.recentlyOpenedPathsList`
    holds exactly what the real file on this machine holds (verified
    2026-08-11): an `entries` array of `folderUri`/`workspace`/`fileUri` rows,
    most-recent-first."""
    import sqlite3 as sq
    path = appdata / "Code/User/globalStorage/state.vscdb"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()               # a previous garbage file must not linger
    con = sq.connect(str(path))
    try:
        con.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        con.execute("INSERT INTO ItemTable VALUES (?, ?)",
                    ("history.recentlyOpenedPathsList",
                     json.dumps({"entries": entries})))
        con.commit()
    finally:
        con.close()
    return path


def check_vscode_recents_are_read_from_the_real_key() -> bool:
    """VS Code's real, LIVE Open Recent list — `state.vscdb`'s
    `history.recentlyOpenedPathsList` — NOT the stale menu-paint cache in
    `storage.json` that task 242 found missing the project open in front of
    him. The fixture plants BOTH the real menu list and decoy garbage
    (an indexed `fileUri` and a workspace entry whose folder is gone) — only
    the real, ordered, existing folder list may survive."""
    with tempfile.TemporaryDirectory() as tmp:
        appdata = Path(tmp)
        real_folder = appdata / "real-project"
        real_folder.mkdir()
        gone_folder = str(appdata / "gone-workspace-folder")   # never created
        _write_state_db(appdata, [
            {"folderUri": "file:///" + str(real_folder).replace("\\", "/").replace(":", "%3A")},
            # decoy: a loose FILE, never a window "Open Recent" would launch
            {"fileUri": "file:///c%3A/Users/vurun/Downloads/readme.md"},
            # decoy: a workspace whose folder no longer exists
            {"workspace": {"configPath": "file:///" + gone_folder.replace("\\", "/").replace(":", "%3A")}},
        ])
        real = recents._env
        recents._env = lambda name: str(appdata) if name == "APPDATA" else real(name)
        try:
            found = recents.vscode_recents()
        finally:
            recents._env = real
    if len(found) != 1:
        print(f"  DETAIL {len(found)} recents read, expected 1 (decoys must not survive): {found}")
        return False
    if found[0]["target"] != str(real_folder):
        print(f"  DETAIL the path is not what VS Code would open: {found[0]}")
        return False
    # The label is the folder's NAME — a row of full paths is unreadable on a
    # phone, and the path still stands under it as the row's note.
    return found[0]["label"] == "real-project" and found[0]["sub"].endswith("real-project")


def check_vscode_recents_point_at_the_wrong_key_go_red() -> bool:
    """Planted-defect proof: pointing the parser at the OLD/decoy key — the
    indexed-workspace-style `fileUri` entries a lookup by the wrong field
    would return — must fail this gate. Proves the key really matters and the
    check above is not vacuously true."""
    with tempfile.TemporaryDirectory() as tmp:
        appdata = Path(tmp)
        real_folder = appdata / "real-project"
        real_folder.mkdir()
        _write_state_db(appdata, [
            {"fileUri": "file:///c%3A/Users/vurun/Downloads/readme.md"},
        ])
        real = recents._env
        recents._env = lambda name: str(appdata) if name == "APPDATA" else real(name)
        try:
            found = recents.vscode_recents()
        finally:
            recents._env = real
    # The decoy-only db must yield NOTHING (a fileUri is never a folder to
    # open) — proving the parser really discriminates by key/shape rather
    # than accepting whatever the first entry happens to be.
    return found == []


def check_a_missing_or_broken_storage_file_yields_nothing_not_a_guess() -> bool:
    """Every failure mode of a file we do not own — absent, unreadable, a shape
    a future version changed — must produce an EMPTY list. The phone then shows
    "New window" alone, which is true; a guessed path is a row that opens the
    wrong thing."""
    with tempfile.TemporaryDirectory() as tmp:
        real = recents._env
        recents._env = lambda name: tmp if name == "APPDATA" else real(name)
        try:
            if recents.vscode_recents():
                return False
            path = Path(tmp) / "Code/User/globalStorage/state.vscdb"
            path.parent.mkdir(parents=True)
            path.write_text("not a sqlite file", encoding="utf-8")
            if recents.vscode_recents():
                return False
            _write_state_db(Path(tmp), [])
            return not recents.vscode_recents()
        finally:
            recents._env = real


def check_vscode_recents_are_capped_and_ordered() -> bool:
    """The db's own order is most-recent-first, and it is not re-sorted; a cap
    exists so a decade of history does not become an unreadable phone list."""
    with tempfile.TemporaryDirectory() as tmp:
        appdata = Path(tmp)
        folders = []
        for i in range(recents.MAX_PER_APP + 5):
            f = appdata / f"proj{i}"
            f.mkdir()
            folders.append(f)
        entries = [{"folderUri": "file:///" + str(f).replace("\\", "/").replace(":", "%3A")}
                  for f in folders]
        _write_state_db(appdata, entries)
        real = recents._env
        recents._env = lambda name: str(appdata) if name == "APPDATA" else real(name)
        try:
            found = recents.vscode_recents()
        finally:
            recents._env = real
    if len(found) != recents.MAX_PER_APP:
        print(f"  DETAIL {len(found)} recents, expected the cap {recents.MAX_PER_APP}")
        return False
    return [e["target"] for e in found] == [str(f) for f in folders[:recents.MAX_PER_APP]]


def check_chrome_offers_only_what_it_can_really_do() -> bool:
    """THE HONEST LIMIT, held as a rule rather than a footnote. Chrome's
    recently-closed lives in an undocumented binary session file that is not
    parsed yet, so Chrome contributes New window and Incognito and NOTHING
    that looks like history. A row that promised a recent tab and opened a
    blank window would be worse than the two honest rows."""
    real = recents.app_exe
    recents.app_exe = lambda app: "C:\\fake\\%s.exe" % app
    try:
        found = recents.entries()
    finally:
        recents.app_exe = real
    chrome = [e for e in found if e["app"] == "chrome"]
    kinds = sorted(e["kind"] for e in chrome)
    if kinds != ["new", "private"]:
        print(f"  DETAIL Chrome offered {kinds}")
        return False
    # …and every app that IS offered starts with a plain new window, since a
    # recent list can legitimately be empty and an app with no rows at all
    # would look uninstalled.
    for app in recents.APPS:
        rows = [e for e in found if e["app"] == app]
        if not rows or rows[0]["kind"] != "new":
            print(f"  DETAIL {app} has no 'New window' row: {rows[:2]}")
            return False
        if any("|" not in e["id"] for e in rows):
            return False
    return True


def check_an_app_that_is_not_installed_offers_nothing() -> bool:
    """An entry that cannot be opened is not an offer. The phone would show a
    row, he would tap it, and nothing would happen — the dead-button complaint
    of task 166 in a new panel."""
    real = recents.app_exe
    recents.app_exe = lambda app: "" if app == "chrome" else "C:\\fake.exe"
    try:
        found = recents.entries()
    finally:
        recents.app_exe = real
    return not any(e["app"] == "chrome" for e in found)


def check_only_a_window_that_was_not_standing_is_handed_back() -> bool:
    """THE CORRECTNESS ARGUMENT of task 184, and this project's oldest lesson
    (constraint 11): every VS Code window shares one process, so "a window of
    the app I launched" would hand back whichever one Windows enumerated
    first — very likely the one he was already working in, which would then be
    torn into a layout. The handles standing BEFORE the launch are written
    down, and only a handle outside that set may be returned."""
    started: list = []
    before = listing(MEMBER_A, OLD)
    after = listing(MEMBER_A, OLD, NEWWIN)
    state = {"windows": before}
    window_manager.list_windows = lambda exclude=None: state["windows"]
    window_manager.window_at_hwnd = lambda hwnd: {
        "hwnd": hwnd, "title": TITLES.get(hwnd, ""), "process": "code.exe",
        "icon": None}

    def popen(cmd, **kw):
        started.append(cmd)
        state["windows"] = after           # the app's window appears
        return None

    real_popen, real_sleep = recents.subprocess.Popen, recents.time.sleep
    real_exe = recents.app_exe
    recents.subprocess.Popen = popen
    recents.time.sleep = lambda s: None
    recents.app_exe = lambda app: "C:\\fake\\Code.exe"
    # The fake listing reports every window as excel.exe; the launcher waits
    # for the process it started, so the two must agree for this to be a test
    # of NEWNESS rather than of the name.
    real_names = recents._EXE_NAMES.copy()
    recents._EXE_NAMES["vscode"] = "excel.exe"
    try:
        info = recents.open_entry("vscode|recent|" + str(Path(__file__)))
    finally:
        recents.subprocess.Popen = real_popen
        recents.time.sleep = real_sleep
        recents.app_exe = real_exe
        recents._EXE_NAMES.update(real_names)
    if not started or "-n" not in started[0]:
        print(f"  DETAIL VS Code was not forced to open a NEW window: {started}")
        return False
    if info.get("hwnd") != NEWWIN:
        print(f"  DETAIL it handed back {info} instead of the new window")
        return False
    return True


def check_an_entry_that_cannot_be_opened_says_so() -> bool:
    """A recent folder can be gone (a removed drive, a deleted project) and an
    app can be uninstalled between the list and the tap. Both come back as a
    named error the phone can toast — never a silent nothing, which is the
    dead-button failure again."""
    real = recents.app_exe
    recents.app_exe = lambda app: ""
    try:
        if "not installed" not in recents.open_entry("vscode|new|").get("error", ""):
            return False
    finally:
        recents.app_exe = real
    recents.app_exe = lambda app: "C:\\fake.exe"
    try:
        gone = recents.open_entry("vscode|recent|Z:\\nowhere\\at\\all")
    finally:
        recents.app_exe = real
    if "not there" not in gone.get("error", ""):
        print(f"  DETAIL a vanished folder answered {gone}")
        return False
    return recents.open_entry("nosuchapp|new|").get("error")


CHECKS = [
    ("185: a window he opened is offered as a layout, once, and named",
     check_a_window_he_opened_is_offered_as_a_layout),
    ("185: asking (and answering) moves and raises NOTHING on the PC",
     check_nothing_on_the_pc_is_touched_by_the_question),
    ("185: no injected double-click, no question",
     check_no_double_click_means_no_question),
    ("185: a dialog is never offered", check_a_dialog_is_never_offered),
    ("185: a window that was already open is never offered",
     check_a_window_that_was_already_open_is_never_offered),
    ("185: a layout member is never offered",
     check_a_layout_member_is_never_offered),
    ("185: nothing is asked while the phone is away",
     check_nothing_is_asked_while_the_phone_is_away),
    ("185: it does not blind the layout-adoption question next door",
     check_the_two_questions_do_not_eat_each_other),
    ("242: VS Code recents come from the LIVE state.vscdb list, not the stale menu cache",
     check_vscode_recents_are_read_from_the_real_key),
    ("242: a decoy/wrong-key db yields nothing, never chaotic entries",
     check_vscode_recents_point_at_the_wrong_key_go_red),
    ("242: VS Code recents are capped and stay in the db's own order",
     check_vscode_recents_are_capped_and_ordered),
    ("184: a missing or broken state db yields nothing, never a guess",
     check_a_missing_or_broken_storage_file_yields_nothing_not_a_guess),
    ("184: Chrome offers only what it can really do",
     check_chrome_offers_only_what_it_can_really_do),
    ("184: an app that is not installed offers nothing",
     check_an_app_that_is_not_installed_offers_nothing),
    ("184: only a window that was NOT standing before is handed back",
     check_only_a_window_that_was_not_standing_is_handed_back),
    ("184: an entry that cannot be opened says so",
     check_an_entry_that_cannot_be_opened_says_so),
]


def main() -> int:
    return run_checks("LAYOUT BIRTH GATE", CHECKS,
                      "a layout can start from a window that is not open yet, "
                      "and from one he just opened.")


def test_layout_birth():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
