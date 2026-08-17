"""THE TRUNK GATE — pairing a torn-off VS Code window back to its parent.

`server/vscode_windows.py`'s `trunk_map(hwnds) -> {branch: trunk}`: when the
owner tears an editor group out of VS Code with VS Code's OWN gesture (not
our extraction — constraint 19's `mine()` only knows windows WE opened), the
new window is a total stranger to every rule in `layout_popup.py`. VS Code
records the fact itself, in `state.vscdb`'s `memento/workbench.editorParts`
key, and this module's job is to read it honestly: pair a branch to a trunk
ONLY when the DB and the live desktop agree, and answer `{}` — never a guess
— the instant they do not (a wrong pair stars the wrong layout and tells him
a window is safe to close when it is not).

THE HARNESS lives in `tests/_vscode_trunk_fixtures.py` (THE STRUCTURE LAW,
split by RESPONSIBILITY, not line count): that module BUILDS a fake desk and
a fake VS Code state, this one ASKS the questions of the real module — two
different reasons to change.

ROUND 2 (kept as the finding, not scrubbed): the first version faked only
the window layer and left `agents.project_dir_of` / `agents.
_workspace_storage_dir` REAL, so every synthetic folder resolved to "" and
every "-> {}" check was GREEN FOR THE WRONG REASON, caught only when the
coordinator diffed this gate against the owner's real desk. ROUND 3: two
"-> {}" checks (bounds-cannot-settle, identical-resting-rects) staged a
THIRD, trunk-eligible window alongside the ambiguous pair — so a correct
refusal AND a wrong pick both left two trunk candidates and rule 4 masked
the difference; both restaged with ONLY the ambiguous pair, so a wrong pick
now resolves the OTHER twin as a false trunk instead of coinciding with the
right answer.

Every check is proven by planting its own defect — PLANT TABLE reported
alongside this file, not inline (it lives against the real module, which
this gate must never edit).

Run:  .venv\\Scripts\\python tests/test_vscode_trunk.py
"""

import json
import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "server"))
sys.path.insert(0, str(PROJECT_DIR / "tests"))

import agents  # noqa: E402

from _vscode_trunk_fixtures import (  # noqa: E402
    Storage, aux, assert_isolated, install_windows, minimize,
    restore_appdata, restore_fakes, win, write_vscdb,
)
import lost_windows  # noqa: E402  (re-exported for _wrap_readonly_copy below)

try:
    import vscode_windows
except ImportError as e:
    print("=== VSCODE TRUNK GATE ===")
    print(f"  FATAL: cannot import server/vscode_windows.py: {e!r}")
    print("  This gate proves the contract for "
          "vscode_windows.trunk_map(hwnds: list[int]) -> dict[int, int].")
    print("  It has not been written yet (or is not importable) — that is a "
          "legitimate red, not a crash in this gate.")
    sys.exit(1)

if not hasattr(vscode_windows, "trunk_map"):
    print("=== VSCODE TRUNK GATE ===")
    print("  FATAL: server/vscode_windows.py has no trunk_map(...) function.")
    sys.exit(1)


def check_isolation_assertion_really_fires():
    """This gate's own safety net (constraint 33): `assert_isolated()` must
    actually raise when a folder resolves OUTSIDE the temp tree, never just
    exist as decoration.

    Plant: point a folder at a real-looking non-temp path and confirm the
    assertion catches it (proven inline, not against the module)."""
    from _vscode_trunk_fixtures import FOLDER_STORAGE
    FOLDER_STORAGE["bogus"] = Path("C:/Users/vurun/Documents")
    try:
        assert_isolated()
        return False   # should have raised
    except AssertionError:
        return True
    finally:
        FOLDER_STORAGE.pop("bogus", None)


# ═══════════════════════ 1-4: WHOSE WINDOW IS WHOSE ═══════════════════════
def check_happy_path_pairs_both_branches_to_the_remainder():
    """Two auxiliary records + one code.exe window left over -> both
    branches point at the remainder (the module's ordinary case).

    Plant: return the FIRST live code.exe window of the folder as trunk
    regardless of matching, instead of "whichever window is left after every
    auxiliary record was matched" -> paired with
    check_two_remainders_yields_no_pairs, which a first-window guess cannot
    survive (see PLANT A in the report)."""
    storage = Storage("Proj")
    try:
        TRUNK, B1, B2 = 0x301, 0x302, 0x303
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            B1: win("foo.py - Proj - Visual Studio Code"),
            B2: win("bar.py - Proj - Visual Studio Code"),
        })
        write_vscdb(storage.db(), auxiliary=[
            aux(("foo.py",)), aux(("bar.py",))])
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([TRUNK, B1, B2])
        return result == {B1: TRUNK, B2: TRUNK}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_zero_remainder_yields_no_pairs():
    """Every code.exe window for this folder is claimed by an auxiliary
    record -> NOTHING is left to be a trunk, so no pairs at all — not a
    guess at which branch is "really" the trunk.

    Plant: fall back to pairing branches to each other (or to the first
    branch) when the remainder count is 0 -> reddens here while the happy
    path stays green."""
    storage = Storage("Proj")
    try:
        B1, B2 = 0x304, 0x305
        install_windows({
            B1: win("foo.py - Proj - Visual Studio Code"),
            B2: win("bar.py - Proj - Visual Studio Code"),
        })
        write_vscdb(storage.db(), auxiliary=[
            aux(("foo.py",)), aux(("bar.py",))])
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([B1, B2])
        return result == {}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_two_remainders_yields_no_pairs():
    """The SAME folder open in two main windows (the module docstring's own
    named example): one auxiliary record is claimed, TWO windows are left
    over, and neither may be guessed at as the trunk.

    Plant: `trunks[0]` instead of asserting `len(trunks) == 1` -> silently
    answers with one of the two mains as if it were certain."""
    storage = Storage("Proj")
    try:
        M1, M2, B1 = 0x306, 0x307, 0x308
        install_windows({
            M1: win("readme.md - Proj - Visual Studio Code"),
            M2: win("other.md - Proj - Visual Studio Code"),
            B1: win("foo.py - Proj - Visual Studio Code"),
        })
        write_vscdb(storage.db(), auxiliary=[aux(("foo.py",))])
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([M1, M2, B1])
        return result == {}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_non_code_exe_window_never_appears():
    """A Chrome window with a title that happens to prefix-match must never
    enter the answer.

    Plant: drop the `process == "code.exe"` filter -> the Chrome hwnd is
    treated as a folder candidate."""
    storage = Storage("Proj")
    try:
        TRUNK, B1, CHROME = 0x309, 0x30A, 0x30B
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            B1: win("foo.py - Proj - Visual Studio Code"),
            # Same folder-matching TITLE SHAPE as a real VS Code window
            # (ends "- Proj - Visual Studio Code") so it groups into the
            # SAME folder and the only thing telling it apart is `process`
            # — a title that reads as Chrome's own would never even reach
            # the process filter, proving nothing about it.
            CHROME: win("foo.py - Proj - Visual Studio Code",
                         process="chrome.exe"),
        })
        write_vscdb(storage.db(), auxiliary=[aux(("foo.py",))])
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([TRUNK, B1, CHROME])
        return CHROME not in result and result == {B1: TRUNK}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_title_prefix_with_real_ellipsis():
    """The tab title is truncated with a REAL `…` and the window title
    still names the same tab — the real matcher (`_bare` + a prefix test
    either direction) must recognise the truncated DB title against the
    untruncated window title.

    Plant: comparing full string equality instead of stripping the
    trailing `…` before the prefix test -> the truncated DB title never
    matches the live window title."""
    storage = Storage("Proj")
    try:
        TRUNK, B1 = 0x30C, 0x30D
        truncated = "a very long file name that got cut…"
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            B1: win(f"{truncated} - Proj - Visual Studio Code"),
        })
        write_vscdb(storage.db(), auxiliary=[aux((truncated,))])
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([TRUNK, B1])
        return result == {B1: TRUNK}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_bounds_tiebreak_resolves_two_same_titled_windows():
    """Two live windows share one tab title ("foo.py" torn off twice) —
    title alone cannot tell them apart, and rule 4's "exactly one
    remainder" forbids a THIRD decoy riding along (a losing candidate stays
    an unconsumed "trunk candidate" and inflates the remainder regardless
    of which title-twin actually won — proven separately in
    check_identical_resting_rects_leaves_both_out and
    check_bounds_cannot_settle_leaves_both_out). This proves the positive
    half: bounds genuinely close to two different rects, across two
    records, resolve to a full match rather than a refusal.

    Plant: refusing to disambiguate title-tied candidates at all -> `{}`,
    while the two "should refuse" checks above stay green."""
    storage = Storage("Proj")
    try:
        TRUNK, BA, BB = 0x30E, 0x30F, 0x310
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            BA: win("foo.py - Proj - Visual Studio Code", rect=(0, 0, 400, 300)),
            BB: win("foo.py - Proj - Visual Studio Code", rect=(500, 500, 900, 700)),
        })
        write_vscdb(storage.db(), auxiliary=[
            aux(("foo.py",), bounds={"x": 0, "y": 0,
                                       "width": 400, "height": 300}),
            aux(("foo.py",), bounds={"x": 500, "y": 500,
                                       "width": 900, "height": 700}),
        ])
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([TRUNK, BA, BB])
        return result == {BA: TRUNK, BB: TRUNK}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_bounds_tiebreak_reads_resting_rect_when_minimized():
    """THE OWNER'S OWN CASE (per the coordinator's note): a member of a
    non-focused layout sits MINIMIZED, and `window_manager._frame_rect`
    would report the same fixed off-screen placeholder for every minimized
    window — no information to break a tie with at all. The tie-break must
    read `lost_windows.resting_rect` (which answers `GetWindowPlacement`'s
    `rcNormalPosition` for an iconic window) instead. Two records / two
    minimized title-twins, the same symmetric shape as
    check_bounds_tiebreak_resolves_two_same_titled_windows and for the same
    reason (rule 4 forbids an unconsumed decoy riding along).

    Plant: tie-breaking off `wm._frame_rect` directly rather than
    `lost_windows.resting_rect` -> both minimized candidates report the
    IDENTICAL off-screen placeholder rect regardless of which is which, the
    tie can never be settled by either record, and the folder answers `{}`
    where the correct answer pairs both."""
    storage = Storage("Proj")
    try:
        TRUNK, BA, BB = 0x340, 0x341, 0x342
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            BA: win("foo.py - Proj - Visual Studio Code"),
            BB: win("foo.py - Proj - Visual Studio Code"),
        })
        # Both branches are MINIMIZED — their live frame is the identical
        # off-screen placeholder; only resting_rect tells them apart.
        minimize(BA, resting=(500, 500, 900, 700))
        minimize(BB, resting=(0, 0, 400, 300))
        write_vscdb(storage.db(), auxiliary=[
            aux(("foo.py",), bounds={"x": 500, "y": 500,
                                       "width": 900, "height": 700}),
            aux(("foo.py",), bounds={"x": 0, "y": 0,
                                       "width": 400, "height": 300}),
        ])
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([TRUNK, BA, BB])
        return result == {BA: TRUNK, BB: TRUNK}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_bounds_cannot_settle_leaves_both_out():
    """Two candidates and bounds that match NEITHER within tolerance — the
    tie cannot be broken, so both are left out rather than guessed at.

    NO third (trunk-eligible) window rides here (the coordinator's finding
    on the round-2 version — see check_identical_resting_rects_leaves_
    both_out's docstring for the full reasoning): with a third window
    present, both a correct refusal and a wrong pick leave two trunk
    candidates, so rule 4 answers `{}` either way and the check measures
    nothing. With ONLY the two candidates in the folder, a wrong pick
    resolves the OTHER as a false trunk — observably wrong.

    Plant: falling back to `matched[0]` when nothing is within
    `BOUNDS_TOLERANCE_PX` -> one of the two is wrongly paired instead of
    neither."""
    storage = Storage("Proj")
    try:
        B1, B2 = 0x312, 0x313
        install_windows({
            B1: win("foo.py - Proj - Visual Studio Code", rect=(10, 10, 300, 300)),
            B2: win("foo.py - Proj - Visual Studio Code", rect=(20, 20, 300, 300)),
        })
        # Bounds miss both live rects by far more than BOUNDS_TOLERANCE_PX.
        write_vscdb(storage.db(), auxiliary=[
            aux(("foo.py",), bounds={"x": 9999, "y": 9999,
                                       "width": 300, "height": 300})])
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([B1, B2])
        return result == {}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_identical_resting_rects_leaves_both_out():
    """THE OWNER'S REAL DESK (measured live by the coordinator): two of his
    VS Code windows, each minimized as the sole member of its own solo
    layout, report the EXACT SAME `resting_rect` — the tie-break cannot
    resolve who is closer when both are exactly as close, and rule 1 says
    refuse rather than pick arbitrarily. NO third window rides here — see
    the module docstring's ROUND 3 note on why (a masking hazard the
    coordinator found, and this file's own history of missing it).

    Plant: `scored[0]` on a stable sort instead of checking
    `scored[1][0] - best_dist < 1` -> one twin is arbitrarily declared the
    branch of the other."""
    storage = Storage("Proj")
    try:
        BA, BB = 0x346, 0x347
        install_windows({
            BA: win("foo.py - Proj - Visual Studio Code"),
            BB: win("foo.py - Proj - Visual Studio Code"),
        })
        # Both minimized under two DIFFERENT solo layouts that share one
        # region — his measured case exactly: identical resting rects.
        same_rect = (1148, 1, 775, 1678)
        minimize(BA, resting=same_rect)
        minimize(BB, resting=same_rect)
        write_vscdb(storage.db(), auxiliary=[
            aux(("foo.py",), bounds={"x": 1148, "y": 1,
                                       "width": 775, "height": 1678})])
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([BA, BB])
        return result == {}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_an_unreadable_record_never_forces_a_later_pick():
    """A record whose bounds are FAR from every candidate must be refused
    OUTRIGHT (rule 3) — and that refusal must not free up a "last one
    standing" for a LATER record to auto-accept without ever checking
    bounds. Two title-twin candidates (BA, BB) and two records: the first
    has bounds nowhere near either live window (refused); the second has
    bounds close to BA. A tie-break that skips the tolerance/ambiguity
    check and always takes `matched[0]` consumes SOME candidate for the
    unreadable first record regardless — freeing the second record's
    remaining candidate list down to exactly one, which is accepted
    unconditionally (a genuine single-candidate match, by design, needs no
    bounds check at all). That chain lets a defective tie-break slip a
    WRONG pair through even though every check that stages the tie-break
    directly (see above) happens to land on symmetric, order-independent
    output. The correct answer here is refusal: BB is never actually
    vouched for by any record, so it must remain unpaired and the whole
    folder answers `{}`.

    Plant: `return matched[0]` in place of the tolerance/closest-distance
    logic -> the first (unreadable) record wrongly consumes one candidate,
    the second record's single leftover is then accepted "for free", and
    the folder wrongly answers with BOTH candidates paired."""
    storage = Storage("Proj")
    try:
        TRUNK, BA, BB = 0x348, 0x349, 0x34A
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            BA: win("foo.py - Proj - Visual Studio Code", rect=(0, 0, 400, 300)),
            BB: win("foo.py - Proj - Visual Studio Code", rect=(500, 500, 900, 700)),
        })
        write_vscdb(storage.db(), auxiliary=[
            # Record 1: bounds nowhere near BA or BB — must be refused.
            aux(("foo.py",), bounds={"x": 9999, "y": 9999,
                                       "width": 300, "height": 300}),
            # Record 2: genuinely close to BA.
            aux(("foo.py",), bounds={"x": 0, "y": 0,
                                       "width": 400, "height": 300}),
        ])
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([TRUNK, BA, BB])
        return result == {}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


# ═══════════════════════════ 6: FAILURE MODES ═══════════════════════════
def check_missing_storage_dir_returns_empty():
    """A folder `agents.project_dir_of` cannot resolve at all (never
    touched by Claude Code) -> `{}`, never a raise.

    Plant: assume `agents._workspace_storage_dir` always returns a real
    Path and skip the `is None` guard -> a later `.is_file()` on `None`
    raises AttributeError instead of answering `{}`."""
    TRUNK, B1 = 0x320, 0x321
    # No Storage() registered for this folder at all — FOLDER_STORAGE stays
    # empty, so `_fake_project_dir_of` answers "" for it, exactly like a
    # folder Claude Code never opened.
    install_windows({
        TRUNK: win("readme.md - NeverOpened - Visual Studio Code"),
        B1: win("foo.py - NeverOpened - Visual Studio Code"),
    })
    try:
        result = vscode_windows.trunk_map([TRUNK, B1])
        return result == {}
    finally:
        restore_fakes()
        restore_appdata()


def check_missing_editor_parts_key_returns_empty():
    """The key is simply absent from `ItemTable` (a workspace whose windows
    were never torn apart).

    Plant: bare `memento["editorparts.state"]` indexing instead of `.get` ->
    KeyError propagates instead of `{}`."""
    storage = Storage("Proj")
    try:
        TRUNK, B1 = 0x322, 0x323
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            B1: win("foo.py - Proj - Visual Studio Code"),
        })
        write_vscdb(storage.db(), auxiliary=None)   # key never written
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([TRUNK, B1])
        return result == {}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_malformed_json_returns_empty():
    """The value column holds text that is not valid JSON at all.

    Plant: `json.loads` called with no try/except around it ->
    `json.JSONDecodeError` propagates instead of `{}`."""
    storage = Storage("Proj")
    try:
        TRUNK, B1 = 0x324, 0x325
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            B1: win("foo.py - Proj - Visual Studio Code"),
        })
        write_vscdb(storage.db(), malformed=True)
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([TRUNK, B1])
        return result == {}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_unreadable_db_returns_empty():
    """The file exists but is not a SQLite database at all (a truncated
    write, a disk hiccup mid-save).

    Plant: no `except Exception` around the copy+connect+query ->
    `sqlite3.DatabaseError` propagates instead of `{}`."""
    storage = Storage("Proj")
    try:
        TRUNK, B1 = 0x326, 0x327
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            B1: win("foo.py - Proj - Visual Studio Code"),
        })
        db = storage.db()
        db.parent.mkdir(parents=True, exist_ok=True)
        db.write_bytes(b"not a sqlite file at all")
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([TRUNK, B1])
        return result == {}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_no_state_vscdb_file_returns_empty():
    """A profile that opened this project but never tore a single window
    off it — the storage HASH DIR exists (matched by folder) but
    `state.vscdb` itself does not."""
    storage = Storage("Proj")
    try:
        TRUNK, B1 = 0x343, 0x344
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            B1: win("foo.py - Proj - Visual Studio Code"),
        })
        storage.dir.mkdir(parents=True, exist_ok=True)   # no state.vscdb written
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([TRUNK, B1])
        return result == {}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_nested_key_missing_from_valid_json_returns_empty():
    """The ROW exists and its value is perfectly valid JSON — just not the
    shape `memento/workbench.editorParts` should be (a VS Code version this
    module has never seen, or a value some OTHER key wrote by coincidence).
    Distinct from check_missing_editor_parts_key_returns_empty, which tests
    the row being absent ENTIRELY: that case returns before this nested
    lookup is ever reached, so it cannot prove the `.get`-not-`[]` guard on
    `memento["editorparts.state"]` / `state["auxiliary"]` at all.

    Plant: bare `memento["editorparts.state"]` / `state["auxiliary"]`
    indexing instead of `.get(...)` -> `KeyError` propagates instead of
    `{}` — a plant that check_missing_editor_parts_key_returns_empty alone
    cannot catch, because its row is never written."""
    storage = Storage("Proj")
    try:
        TRUNK, B1 = 0x34B, 0x34C
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            B1: win("foo.py - Proj - Visual Studio Code"),
        })
        write_vscdb(storage.db(), editor_parts_raw=json.dumps(
            {"some.other.shape": {}}))
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([TRUNK, B1])
        return result == {}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_malformed_auxiliary_shape_returns_empty():
    """`editorParts` parses as JSON but `auxiliary` is not a list at all (a
    shape VS Code itself would never write, but the file on disk is not
    ours to trust).

    Plant: assuming `auxiliary` is always a well-shaped list with no
    `isinstance` guard -> raises instead of `{}` for this one folder. A
    STRING value ("not-a-list") is deliberately NOT used here — removing
    the guard would still iterate its characters without crashing (each
    fails the inner `isinstance(entry, dict)` check and is skipped),
    landing on the SAME `{}` either way and proving nothing; an INT is not
    iterable at all and raises a real `TypeError` the instant the guard is
    gone."""
    storage = Storage("Proj")
    try:
        TRUNK, B1 = 0x328, 0x329
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            B1: win("foo.py - Proj - Visual Studio Code"),
        })
        write_vscdb(storage.db(), editor_parts_raw=json.dumps(
            {"editorparts.state": {"auxiliary": 12345}}))
        storage.install()
        assert_isolated()
        result = vscode_windows.trunk_map([TRUNK, B1])
        return result == {}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


# ═══════════════════════════ 5: THE READ POLICY ═══════════════════════════
def _wrap_readonly_copy():
    """Count real `agents._readonly_copy` invocations — the ONE place a DB
    is actually opened. Returns (counter, restore)."""
    counter = {"n": 0}
    real = agents._readonly_copy

    def _counting(db_path):
        counter["n"] += 1
        return real(db_path)

    agents._readonly_copy = _counting
    vscode_windows.agents._readonly_copy = _counting  # same object; explicit anyway

    def _restore():
        agents._readonly_copy = real

    return counter, _restore


def check_unchanged_file_is_not_reread():
    """Two calls, same file, same (mtime, size) in between -> the SECOND
    call must not open the database again.

    Plant: cache keyed by path alone (never checking mtime/size) still
    passes THIS check but fails check_changed_file_is_reread below — the
    two are a deliberate pair."""
    storage = Storage("Proj")
    try:
        TRUNK, B1 = 0x32A, 0x32B
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            B1: win("foo.py - Proj - Visual Studio Code"),
        })
        write_vscdb(storage.db(), auxiliary=[aux(("foo.py",))])
        storage.install()
        assert_isolated()
        counter, restore = _wrap_readonly_copy()
        try:
            vscode_windows.trunk_map([TRUNK, B1])
            first = counter["n"]
            vscode_windows.trunk_map([TRUNK, B1])
            second = counter["n"]
            return first >= 1 and second == first
        finally:
            restore()
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_changed_file_is_reread():
    """The SAME storage dir, but its `(mtime, size)` changed between calls
    (he tore off another window in between) -> the cache must not keep
    answering with stale data.

    Plant: caching forever with no invalidation at all -> this check
    reddens while check_unchanged_file_is_not_reread stays green."""
    storage = Storage("Proj")
    try:
        TRUNK, B1, B2 = 0x32C, 0x32D, 0x32E
        # B2's window does not exist yet — its record and its live window
        # both arrive only after the first read.
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            B1: win("foo.py - Proj - Visual Studio Code"),
        })
        db = storage.db()
        write_vscdb(db, auxiliary=[aux(("foo.py",))])
        storage.install()
        assert_isolated()
        counter, restore = _wrap_readonly_copy()
        try:
            r1 = vscode_windows.trunk_map([TRUNK, B1])
            first = counter["n"]
            time.sleep(0.05)   # keep (mtime, size) from coinciding
            write_vscdb(db, auxiliary=[aux(("foo.py",)), aux(("bar.py",))])
            install_windows({
                TRUNK: win("readme.md - Proj - Visual Studio Code"),
                B1: win("foo.py - Proj - Visual Studio Code"),
                B2: win("bar.py - Proj - Visual Studio Code"),
            })
            r2 = vscode_windows.trunk_map([TRUNK, B1, B2])
            second = counter["n"]
            return (r1 == {B1: TRUNK} and r2 == {B1: TRUNK, B2: TRUNK}
                    and second > first)
        finally:
            restore()
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


def check_hwnd_matching_is_never_cached():
    """Windows reuses handles: the SAME hwnd number must be re-matched
    fresh on every call, never answered from a memory of what that number
    used to be. The DB-read cache above is keyed by the storage DIRECTORY,
    never by an hwnd — this proves the hwnd side of the pipeline draws no
    such cache at all.

    Plant: memoizing the final `{branch: trunk}` dict keyed by the hwnd
    list -> the second call, with the SAME hwnd now meaning a completely
    different live window, still answers with the FIRST call's stale
    pairing."""
    storage = Storage("Proj")
    try:
        TRUNK, REUSED = 0x32F, 0x330
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            REUSED: win("foo.py - Proj - Visual Studio Code"),
        })
        write_vscdb(storage.db(), auxiliary=[aux(("foo.py",))])
        storage.install()
        assert_isolated()
        first = vscode_windows.trunk_map([TRUNK, REUSED])
        # The SAME numeric hwnd is now a totally different, unrelated
        # window — Windows recycling a handle. It must NOT still answer as
        # if it were the old branch.
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            REUSED: win("Google Chrome", process="chrome.exe"),
        })
        second = vscode_windows.trunk_map([TRUNK, REUSED])
        return first == {REUSED: TRUNK} and second == {}
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


# ═════════════════════ THE PAIR REACHES THE PHONE ═════════════════════
def check_pair_flows_into_layout_state_dependents_and_parent():
    """A pure `trunk_map` nobody calls is a feature that does not exist —
    the actions.json lesson, restated in CLAUDE.md's own words for this
    exact class of gap. `layout_state.state()` already turns a member's
    `Layout.sources` (member -> the window its content depends on) into the
    ⭐/`dependents` a layout carries, for a torn-out TAB (constraint 19's
    `resolve_slot`); a torn-off VS Code window found through `trunk_map` is
    the SAME relationship, `code.exe` is already the one app in
    `PARENT_CLOSE_APPS`, and `trunk_map`'s return shape (`{branch: trunk}`)
    is exactly what `Layout.sources` expects. This proves the SHAPE really
    fits the existing pipe, without touching `layout_state.py`/
    `layout_registry.py`'s own wiring, which another agent owns.

    Plant: swapping `trunk_map`'s dict the wrong way round
    (`{trunk: branch}` instead of `{branch: trunk}`) -> `Layout.sources`
    would key by the WRONG window, and this check catches it because
    `dependents`/`parent` come out empty instead of naming the branch
    layout."""
    storage = Storage("Proj")
    try:
        import layout_state
    except ImportError as e:
        print(f"  DETAIL cannot import server/layout_state.py: {e!r}")
        return False
    try:
        TRUNK, BRANCH = 0x333, 0x334
        install_windows({
            TRUNK: win("readme.md - Proj - Visual Studio Code"),
            BRANCH: win("foo.py - Proj - Visual Studio Code"),
        })
        write_vscdb(storage.db(), auxiliary=[aux(("foo.py",))])
        storage.install()
        assert_isolated()
        pairs = vscode_windows.trunk_map([TRUNK, BRANCH])
        if pairs != {BRANCH: TRUNK}:
            print(f"  DETAIL trunk_map itself did not pair as expected: "
                  f"{pairs}")
            return False

        class _Layout:
            def __init__(self, name, members):
                self.name = name
                self.members = members
                self.process = "code.exe"
                self.sources = {}
                self.template = None
                self.orient = "landscape"
                self.icon = None
                self.ratio = None
                self.pos = 0.5

            def project(self):
                return None

        trunk_layout = _Layout("Trunk", [TRUNK])
        branch_layout = _Layout("Branch", [BRANCH])
        # This is the wiring `trunk_map`'s CALLER is expected to do — feed
        # the pair into `sources` exactly as `resolve_slot` already does for
        # our own extractions (constraint 19).
        for branch, trunk in pairs.items():
            branch_layout.sources[branch] = trunk

        class _Reg:
            layouts = [trunk_layout, branch_layout]

            def prune(self):
                return list(range(len(self.layouts)))

        real_live, real_in = agents.live_agents, agents.agents_in
        agents.live_agents = lambda: {}
        agents.agents_in = lambda project, live: []
        try:
            frame = layout_state.state(_Reg(), None, None)
        finally:
            agents.live_agents, agents.agents_in = real_live, real_in

        by_name = {lay["name"]: lay for lay in frame["layouts"]}
        return (by_name["Trunk"]["parent"] is True
                and by_name["Trunk"]["dependents"] == ["Branch"]
                and by_name["Branch"]["parent"] is False)
    finally:
        storage.cleanup()
        restore_fakes()
        restore_appdata()


CHECKS = [
    ("assert_isolated() really fires on a non-temp path",
     check_isolation_assertion_really_fires),
    ("happy path: two branches pair to the one remainder",
     check_happy_path_pairs_both_branches_to_the_remainder),
    ("zero remainder yields no pairs",
     check_zero_remainder_yields_no_pairs),
    ("two remainders (same folder, two main windows) yields no pairs",
     check_two_remainders_yields_no_pairs),
    ("a non-code.exe window never appears in the answer",
     check_non_code_exe_window_never_appears),
    ("title-prefix matching works with the real … character",
     check_title_prefix_with_real_ellipsis),
    ("bounds tie-break resolves two same-titled live windows",
     check_bounds_tiebreak_resolves_two_same_titled_windows),
    ("the bounds tie-break reads the RESTING rect for a minimized window",
     check_bounds_tiebreak_reads_resting_rect_when_minimized),
    ("bounds that cannot settle it (outside tolerance) leaves both out",
     check_bounds_cannot_settle_leaves_both_out),
    ("identical resting rects (his real desk) leaves both out",
     check_identical_resting_rects_leaves_both_out),
    ("an unreadable record never forces a later single-candidate pick",
     check_an_unreadable_record_never_forces_a_later_pick),
    ("no workspace storage resolved for the folder -> {}",
     check_missing_storage_dir_returns_empty),
    ("missing memento/workbench.editorParts key -> {}",
     check_missing_editor_parts_key_returns_empty),
    ("malformed JSON in the value column -> {}",
     check_malformed_json_returns_empty),
    ("unreadable / non-SQLite state.vscdb -> {}",
     check_unreadable_db_returns_empty),
    ("storage dir exists but state.vscdb does not -> {}",
     check_no_state_vscdb_file_returns_empty),
    ("nested key missing from otherwise-valid JSON -> {}",
     check_nested_key_missing_from_valid_json_returns_empty),
    ("malformed auxiliary shape -> {} (never raises)",
     check_malformed_auxiliary_shape_returns_empty),
    ("an unchanged file is not re-read",
     check_unchanged_file_is_not_reread),
    ("a changed (mtime, size) file IS re-read",
     check_changed_file_is_reread),
    ("hwnd matching runs fresh every call — never cached against a handle",
     check_hwnd_matching_is_never_cached),
    ("a resolved pair reaches layout_state's dependents/parent",
     check_pair_flows_into_layout_state_dependents_and_parent),
]


def main() -> int:
    print("=== VSCODE TRUNK GATE ===")
    failed = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as e:
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"VSCODE TRUNK GATE FAILED — {failed} check(s).")
        return 1
    print("VSCODE TRUNK GATE PASSED — trunk_map pairs branches to trunks "
          "only when the DB and the live desktop agree, never guesses, and "
          "its answer really reaches layout_state's dependents/parent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
