"""Fast guard runner — THE STRUCTURE LAW, THE CONFIG SECTION LAW, docs
coverage, and doc-links, wired into Claude Code hooks (.claude/settings.json).

Exit 2 on any guard failure (what makes a PostToolUse/Stop hook BLOCKING);
exit 0 when every guard is green. Never runs the project's own app/test
suite (tests/test_input_pipeline.py) — guards only, kept fast and
deterministic per rules/CODE.md -> Enforcement.

Usage:
    python tests/run_guards.py           # all four guards
    python tests/run_guards.py --fast    # structure + config-sections only
                                          # (the PostToolUse hook's speed budget)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

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
    # Legibility; MIGRATE-LAYOUT.md step 5).
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
    # windows measure roughly twice as wide inside run_guards" note in
    # .claude/layout-proof.md came from. Ordering is the whole fix: the audit
    # builds the QApplication first, on the real platform, and the offscreen
    # default that comes later is a no-op because an application already
    # exists.
    ("layout audit (Qt windows)", _layout_audit_qt),
    ("control sets (never silently rewritten)", _control_sets),
    ("actions migration (a new version's fields reach HIS file)", _actions_migration),
    ("app sets (right window, and they pay for their seat)", _app_set_wheel),
    ("voice dedup (dictation never retypes across a round boundary)", _voice_dedup),
    ("user settings (a key we retired leaves his file quietly)", _user_settings),
    ("caret lift (only if needed, only by the shortfall)", _caret_lift),
    ("focus gate (typed input lands where he is looking)", _focus_gate),
]


def main() -> int:
    fast_only = "--fast" in sys.argv
    checks = FAST_CHECKS if fast_only else FAST_CHECKS + FULL_ONLY_CHECKS

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
