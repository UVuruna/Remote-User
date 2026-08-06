"""Guard: MD-First 2.0 tier coverage (rules/DOCS.md -> Tiers). Every source
file must have the docs its tier requires:

  Trivial     -> no own doc (a one-line mention in the folder's ___folder.md)
  Standard    -> __about/{name}.md
  Algorithmic -> __about/{name}.md AND __flow/{name}.md
  tests/      -> no own doc (___tests.md folder doc covers the whole folder)

`{name}` is the source file's basename without extension, e.g.
`server/config.py` -> `server/__about/config.md`.

The tier lists below are the single source of truth for tier assignment
(DOCS.md: "changing a file's tier means updating this test in the same
commit"). Any project source file not listed in exactly one tier is a build
failure — an unclassified file is exactly the drift this guard exists to
catch.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _guards_common import PROJECT_ROOT, iter_source_files  # noqa: E402

# Trivial: glue/__init__/re-exports/<~60 lines of plain wiring. One line in
# the parent ___folder.md only — no __about/__flow doc of their own.
TRIVIAL = {
    "server/main.py",
    "server/gui/__init__.py",
    "android/app/src/main/java/com/uvuruna/remoteuser/Prefs.kt",
}

# Standard: ordinary module. Needs __about/{name}.md only.
STANDARD = {
    "server/gui_main.py",
    "server/bootstrap.py",
    "server/pairing.py",
    "server/monitors.py",
    "server/window_manager.py",
    "server/clipboard.py",
    "server/updates.py",
    "server/traffic.py",
    "client/index.html",
    "client/install.html",
    "client/load_test.js",
    "client/state.js",
    "client/panels.js",
    "client/icons.js",
    "client/region.js",
    "client/notify.js",
    "client/quality.js",
    "setup/create_cert.py",
    "setup/agent_hook.py",
    "android/app/src/main/java/com/uvuruna/remoteuser/Notifier.kt",
    "android/app/src/main/java/com/uvuruna/remoteuser/OnboardingActivity.kt",
    "android/app/src/main/java/com/uvuruna/remoteuser/VoiceInput.kt",
}

# Algorithmic: real algorithm, GUI window/widget, config/data table, or
# protocol. Needs __about/{name}.md AND __flow/{name}.md.
ALGORITHMIC = {
    "server/server_core.py",
    "server/uia.py",
    "server/config.py",
    "server/capture.py",
    "server/h264_streamer.py",
    "server/encoders.py",
    "server/input_injector.py",
    "server/web.py",
    # Split out of controls.js on 2026-08-06 (THE STRUCTURE LAW): which sets
    # ride the wheel is a rule set of its own — the cap of 8, the per-process
    # reserve, and the owner's per-layout app ticks.
    "client/sets.js",
    # Split out of web.py on 2026-08-05 (THE STRUCTURE LAW): presence is a
    # state machine with its own rules and its own gate, layout_api is the
    # phone's layout protocol. Both are algorithmic — they carry a flow.
    "server/presence.py",
    "server/layout_api.py",
    # Split out of web.py on 2026-08-06 (THE STRUCTURE LAW): WHERE typed input
    # lands is a decision with its own rules (the layout fence, the desktop
    # pin, dialogs, what re-arms it) and its own gate — algorithmic.
    "server/focus_guard.py",
    "server/notify.py",
    # New 2026-08-06: which agent tools are LIVE on this PC and in which
    # project. Algorithmic — a process table read, a session-id -> transcript
    # -> project mapping, and a cache, all of which have to be explained.
    "server/agents.py",
    "server/gui/theme.py",
    # Split out of the three windows on 2026-08-06 (THE STRUCTURE LAW): the
    # same settle loop was copied three times and carried the same lie in
    # every copy — how a window declares its true minimum is one rule, and it
    # is algorithmic (a circular measurement that has to converge).
    "server/gui/sizing.py",
    "server/gui/traffic_window.py",
    "server/gui/main_window.py",
    "server/gui/controls_editor.py",
    "server/gui/controls_widgets.py",
    "client/style.css",
    # layouts.css is the layout feature's own styling, split out of style.css
    # on 2026-08-05. It shares __about/__flow/layouts.md with layouts.js —
    # one feature, one doc, two files (the doc names both).
    "client/layouts.css",
    "client/render.js",
    "client/input-geometry.js",
    "client/controls.js",
    "client/layouts.js",
    "client/gestures.js",
    "client/connection.js",
    "setup/svg_to_ico.py",
    "setup/build_apk.py",
    "setup/build.py",
    "android/app/src/main/java/com/uvuruna/remoteuser/MainActivity.kt",
}

ALL_CLASSIFIED = TRIVIAL | STANDARD | ALGORITHMIC


def _is_tests_tier(rel_posix: str) -> bool:
    # Every source file under tests/ (guard modules included) needs no own
    # doc — the folder's ___tests.md covers it (DOCS.md tier table).
    return rel_posix == "tests" or rel_posix.startswith("tests/")


def _about_flow_paths(rel: Path) -> tuple[Path, Path]:
    """Where a source file's __about/__flow docs live. Normally beside the
    file's own folder; android/'s Kotlin sources are nested deep under a Java
    package path (android/app/src/main/java/com/...) with no ___folder.md of
    their own down there, so their docs live at the android/ top level next
    to android/___android.md instead (the migration session's deliberate
    choice — docs mirror the doc-folder tree, not the Java package tree)."""
    basename = rel.stem
    if rel.parts[0] == "android":
        folder = PROJECT_ROOT / "android"
    else:
        folder = PROJECT_ROOT / rel.parent
    return folder / "__about" / f"{basename}.md", folder / "__flow" / f"{basename}.md"


def test_every_source_file_is_classified():
    unclassified = []
    for path in iter_source_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if _is_tests_tier(rel) or rel in ALL_CLASSIFIED:
            continue
        unclassified.append(rel)
    assert not unclassified, (
        "Source files with no tier assignment in test_docs_coverage.py "
        "(classify them: Trivial/Standard/Algorithmic — DOCS.md -> Tiers):\n"
        + "\n".join(unclassified)
    )


def test_standard_and_algorithmic_files_have_required_docs():
    missing = []
    for path in iter_source_files():
        rel_str = path.relative_to(PROJECT_ROOT).as_posix()
        if rel_str not in STANDARD and rel_str not in ALGORITHMIC:
            continue
        rel = path.relative_to(PROJECT_ROOT)
        about_path, flow_path = _about_flow_paths(rel)
        if not about_path.exists():
            missing.append(f"{rel_str}: missing {about_path.relative_to(PROJECT_ROOT).as_posix()}")
        if rel_str in ALGORITHMIC and not flow_path.exists():
            missing.append(f"{rel_str}: missing {flow_path.relative_to(PROJECT_ROOT).as_posix()} (Algorithmic tier)")
    assert not missing, "Docs coverage gaps:\n" + "\n".join(missing)


def test_trivial_and_tests_tier_files_have_no_stray_doc():
    # Not a hard requirement of DOCS.md, but a useful drift check: a Trivial
    # or tests-tier file that somehow grew its own __about/__flow doc means
    # either the tier is stale (promote it) or the doc is a leftover
    # (delete it) — either way this test should be updated in the same
    # commit as whichever fix applies.
    stray = []
    for path in iter_source_files():
        rel_str = path.relative_to(PROJECT_ROOT).as_posix()
        if rel_str not in TRIVIAL and not _is_tests_tier(rel_str):
            continue
        rel = path.relative_to(PROJECT_ROOT)
        about_path, flow_path = _about_flow_paths(rel)
        if about_path.exists():
            stray.append(str(about_path.relative_to(PROJECT_ROOT).as_posix()))
        if flow_path.exists():
            stray.append(str(flow_path.relative_to(PROJECT_ROOT).as_posix()))
    assert not stray, (
        "Trivial/tests-tier files with a stray __about/__flow doc "
        "(promote the tier or delete the doc):\n" + "\n".join(stray)
    )


def test_every_code_folder_has_a_folder_doc():
    # Every folder that contains at least one classified source file must
    # have its own ___{folder}.md entry point (DOCS.md -> Structure). android/
    # is the one exception: its Kotlin sources nest deep under a Java package
    # path with no folder doc of their own down there — android/___android.md
    # at the top level is their entry point instead (see _about_flow_paths).
    folders_with_code = set()
    for path in iter_source_files():
        rel = path.relative_to(PROJECT_ROOT)
        folders_with_code.add(PROJECT_ROOT / "android" if rel.parts[0] == "android" else path.parent)
    missing = []
    for folder in folders_with_code:
        expected = folder / f"___{folder.name}.md"
        if not expected.exists():
            missing.append(str(expected.relative_to(PROJECT_ROOT).as_posix()))
    assert not missing, "Code folders missing their ___folder.md entry point:\n" + "\n".join(missing)


if __name__ == "__main__":
    test_every_source_file_is_classified()
    test_standard_and_algorithmic_files_have_required_docs()
    test_trivial_and_tests_tier_files_have_no_stray_doc()
    test_every_code_folder_has_a_folder_doc()
    print("PASS — test_docs_coverage")
