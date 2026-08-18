"""Guard runner — the project's own guards, wired into `.claude/settings.json`.

    PostToolUse -> python tests/run_guards.py --fast
    Stop        -> python tests/run_guards.py

`--fast` runs only the cheap guards (structure law, config sections, the
static half of the layout law) — the PostToolUse speed budget.

The FULL pass runs ONLY when `rules/hooks/changed_files.touched_anything()`
says this session changed something; "cannot tell" (no git, no upstream, an
import failure) always means RUN, never skip — a broken helper never
silently disables a law. Inside the FULL pass the RUNTIME window audit is
gated a second time, on `touched_gui()`: GUI PROVERE SAMO AKO SU MENJANI GUI
FAJLOVI (owner decree 2026-08-14; lang-ok: owner decree, quoted). The FULL
pass also runs the monorepo's clone guard against this project's ratchet
(`tests/clone_ratchet.json`, ONE KIND ONE CLASS) and the rules-size guard
over `CLAUDE.md`.

Exit 2 on any guard failure — that is what makes the hook BLOCK. This runner
never runs the application's own test suite; guards only, kept fast and
deterministic (rules/CODE.md -> Guards).
"""

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
REPO_ROOT = PROJECT_ROOT.parents[1]      # <Category>/<Project> -> monorepo root

sys.path.insert(0, str(TESTS_DIR))

import test_structure_law as structure_law  # noqa: E402
import test_config_sections as config_sections  # noqa: E402
import test_docs_coverage as docs_coverage  # noqa: E402
import test_doc_links as doc_links  # noqa: E402
import test_layout_law as layout_law  # noqa: E402

FAST_CHECKS = [
    ("structure law", structure_law.test_no_file_exceeds_structure_law_threshold),
    ("structure law (ratchet)", structure_law.test_ratchet_entries_reference_existing_files),
    ("config sections", config_sections.test_config_sections_law),
    # The static half of the layout law is a grep — it costs nothing and
    # belongs where the damage is done (rules/GUI.md → Law — Space &
    # Legibility; rules/briefs/MIGRATE-LAYOUT.md step 5).
    ("layout law (static)", layout_law.test_no_banned_layout_patterns),
    ("layout law (ratchet)", layout_law.test_ratchet_entries_still_exist),
]

def _control_sets() -> None:
    """Imported lazily for the same reason as the Qt audit below: it builds
    the real Controls dialog offscreen. Guards the owner's actions.json
    against being silently rewritten (both failures of 2026-08-05)."""
    import test_controls_sets
    for _, check in test_controls_sets.CHECKS:
        check()


def _actions_migration() -> None:
    """That a NEW VERSION'S FIELDS reach the owner's own actions.json — his
    copy is seeded once and never replaced, so this merge is the only path.
    The Claude set's `agent` switch never arrived through four releases while
    every guard was green, because every guard built its "user file" out of
    the SHIPPED file. This one starts from an older shape."""
    import test_actions_migration
    for _, check in test_actions_migration.CHECKS:
        check()


def _app_set_wheel() -> None:
    """The owner's two app-set rules of 2026-08-06: only the Claude
    conversation wears the Claude set (never a document that merely carries
    the word), and an app set costs a wheel slot like every other set. Runs
    the pure client functions in node — skipped when node is absent."""
    import test_app_set_wheel
    if not test_app_set_wheel.shutil.which("node"):
        return
    for _, check in test_app_set_wheel.TESTS:
        check()


def _wheel_dropout() -> None:
    """THE WHEEL THAT SHEDS ITS ACTIVE SETS (task 181, 2026-08-11): a set
    placed on either D-pad group drops off the wheel while it is placed,
    no set ever rides both sides at once, and the cap rises to 10. The two
    server-side cases (wheel_mode survives merge_shipped, reaches the phone
    through _load_actions) run without node and are never skipped; the
    client-side cases follow the app-set-wheel guard's own skip rule."""
    import test_wheel_dropout
    for _, check in test_wheel_dropout.TESTS:
        if not test_wheel_dropout.shutil.which("node") and check not in (
            test_wheel_dropout.test_wheel_mode_is_owner_owned,
            test_wheel_dropout.test_wheel_mode_reaches_the_phone_through_load_actions,
        ):
            continue
        check()


def _voice_dedup() -> None:
    """Dictation never retypes across a ROUND BOUNDARY (task 75 REPEAT,
    2026-08-08 — 0.0.293 fixed a round re-typing its own growing partial on
    retry; his log then showed 177 ERROR_CLIENTs and a smaller shred at the
    boundary between two independent rounds). Runs the real page function in
    node — skipped when node is absent, like the app-set wheel guard above."""
    import test_voice_dedup
    if not test_voice_dedup.shutil.which("node"):
        return
    for _, check in test_voice_dedup.CHECKS:
        check()


def _hold_gesture() -> None:
    """A HOLD IS A CONTACT THAT STAYED PUT (owner report 2026-08-09, task 162 —
    he held a layout row and the layout opened). The row used to drop its hold
    timer on ANY movement, and a finger resting on a capacitive digitizer never
    stands still. Runs the real page rule in node against a realistic jitter
    sequence — skipped when node is absent, like the guards above."""
    import test_hold_gesture
    if not test_hold_gesture.shutil.which("node"):
        return
    for _, check in test_hold_gesture.CHECKS:
        check()


def _layout_drag() -> None:
    """The list's own two gestures, which had no gate at all until the same
    report: a row dropped ON another makes a grid, a row dropped in a GAP only
    moves. Imported lazily — it pulls in the real web layer."""
    import test_layout_drag
    assert test_layout_drag.main() == 0, "the layout drag gate failed (see output)"


def _user_settings() -> None:
    """A setting WE retired leaves his file quietly; a setting HE mistyped is
    still reported (owner evidence 2026-08-08 — `hand` warned on every start,
    months after the offset system was deleted). Pure Python over a temp file:
    it never reads or writes the real %LOCALAPPDATA% settings."""
    import test_user_settings
    for _, check in test_user_settings.CHECKS:
        check()


def _caret_lift() -> None:
    """The soft keyboard raises the PICTURE only when the caret would be
    covered, and only by the shortfall (owner 2026-08-07). Runs the real page
    rule in node — skipped when node is absent, like the guards above."""
    import test_caret_lift
    if not test_caret_lift.shutil.which("node"):
        return
    for _, check in test_caret_lift.CHECKS:
        check()


def _caret_server() -> None:
    """The PC's half of the caret keyboard: WHERE the typing caret is, in
    monitor-normalized coordinates, or an honest "cannot say". Nothing on this
    machine is touched — no window is raised, read, or moved; the Win32/UIA
    layer is faked."""
    import test_caret
    for _, check in test_caret.CHECKS:
        check()


def _focus_gate() -> None:
    """WHERE typed input lands, and the machinery that gets it there (owner
    2026-08-06 + build round R1). Imported lazily like the others: they pull
    in the real web layer. Fast, no browser — and nothing on this machine is
    touched: no hook is installed, no window raised, no key injected."""
    import test_focus_guard
    import test_focus_hook
    assert test_focus_guard.main() == 0, "the focus gate failed (see its output)"
    assert test_focus_hook.main() == 0, "the focus HOOK gate failed (see its output)"


def _layout_audit_qt() -> None:
    """Imported lazily: it pulls in PySide6 and builds an offscreen
    QApplication, which the --fast path must never pay for."""
    import test_layout_audit_qt
    test_layout_audit_qt.test_layout_audit()


def _load(rel_path: str):
    """Load a monorepo-root helper by path; None when it cannot be reached.

    An unreachable helper never silently disables a law: every caller treats
    None as "assume the worst" and runs the guard anyway."""
    path = REPO_ROOT / rel_path
    try:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except (OSError, AttributeError, ImportError, SyntaxError):
        return None


def _clone_guard() -> None:
    """ONE KIND, ONE CLASS — the AST clone detector against this project's
    ratchet. The ratchet was written for the clones that existed on
    2026-08-18 (0 groups) and may only shrink."""
    module = _load("rules/tools/clone_guard.py")
    if module is None:
        return
    ratchet = TESTS_DIR / "clone_ratchet.json"
    rc = module.run([str(PROJECT_ROOT), "--ratchet", str(ratchet)])
    assert rc == 0, ("clone_guard found an un-ratcheted duplicate (output "
                     "above) — extract the shared kind, or extend "
                     "tests/clone_ratchet.json with the owner's word")


def _rules_size() -> None:
    """CLAUDE.md stays under its 6,000-byte limit."""
    module = _load("rules/tools/rules_size_guard.py")
    if module is None:
        return
    rows = [r for r in module.check(project=PROJECT_ROOT) if not r[3]]
    assert not rows, ("over the byte limit: "
                      + ", ".join(f"{r[0]} {r[1]}B > {r[2]}B" for r in rows))


FULL_ONLY_CHECKS = [
    ("docs coverage (classified)", docs_coverage.test_every_source_file_is_classified),
    ("docs coverage (required docs)", docs_coverage.test_standard_and_algorithmic_files_have_required_docs),
    ("docs coverage (no stray docs)", docs_coverage.test_trivial_and_tests_tier_files_have_no_stray_doc),
    ("docs coverage (folder docs)", docs_coverage.test_every_code_folder_has_a_folder_doc),
    ("doc links (no broken links)", doc_links.test_every_relative_link_resolves_to_a_real_file),
    ("doc links (reachable from README)", doc_links.test_every_doc_reachable_from_readme),
    # The runtime half: opens every Qt window and measures it. Full run only
    # — it builds a QApplication (~1 s), too slow for the PostToolUse budget.
    #
    # AND IT GOES FIRST OF THE QT GUARDS (build round R3). `test_controls_sets`
    # sets `QT_QPA_PLATFORM=offscreen` at import time and builds a
    # QApplication with it; every Qt guard after that inherits a platform with
    # NO SYSTEM FONTS. The audit still measured — but every SCREENSHOT it
    # wrote came out as rows of tofu boxes, and those screenshots are the
    # DESIGN REVIEW's whole evidence (rules/GUI.md: the agent opens the image
    # and grades what it sees). A run of the full guards therefore overwrote
    # good proof with unreadable pictures, which is also where the "the same
    # windows measure roughly twice as wide inside run_guards" note that
    # tests/___tests.md still carries. Ordering is the whole fix: the audit
    # builds the QApplication first, on the real platform, and the offscreen
    # default that comes later is a no-op because an application already
    # exists.
    ("layout audit (Qt windows)", _layout_audit_qt),
    ("control sets (never silently rewritten)", _control_sets),
    ("actions migration (a new version's fields reach HIS file)", _actions_migration),
    ("app sets (right window, and they pay for their seat)", _app_set_wheel),
    ("wheel drop-out (a placed set sheds, never on both sides)", _wheel_dropout),
    ("voice dedup (dictation never retypes across a round boundary)", _voice_dedup),
    ("hold gesture (a resting finger picks a layout row up)", _hold_gesture),
    ("layout drag (a row dropped on another makes a grid)", _layout_drag),
    ("user settings (a key we retired leaves his file quietly)", _user_settings),
    ("caret lift (only if needed, only by the shortfall)", _caret_lift),
    ("caret (the PC says where the typing lands)", _caret_server),
    ("focus gate (typed input lands where he is looking)", _focus_gate),
    ("clones (one kind, one class)", _clone_guard),
    ("rules size (CLAUDE.md under its limit)", _rules_size),
]


def main() -> int:
    fast_only = "--fast" in sys.argv
    if fast_only:
        checks = FAST_CHECKS
    else:
        changed = _load("rules/hooks/changed_files.py")
        if changed is not None and not changed.touched_anything(PROJECT_ROOT):
            print("GUARDS SKIPPED — this session changed no file")
            return 0
        checks = FAST_CHECKS + FULL_ONLY_CHECKS
        # The runtime window audit costs a QApplication and real windows; it
        # runs only for a session that touched a GUI file (owner decree
        # 2026-08-14). "Cannot tell" reports touched, so it runs.
        if changed is not None and not changed.touched_gui(PROJECT_ROOT):
            checks = [c for c in checks if c[1] is not _layout_audit_qt]
            print("guards: no GUI file touched — the Qt window audit is skipped")

    failures = []
    for name, check in checks:
        try:
            check()
        except AssertionError as e:
            failures.append(f"[{name}] {e}")

    if failures:
        print("GUARDS FAILED:\n", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
            print(file=sys.stderr)
        return 2

    scope = "fast (structure + config-sections)" if fast_only else "full (all guards)"
    print(f"GUARDS PASSED — {scope}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
