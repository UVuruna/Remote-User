"""Guard test - THE SPACE & LEGIBILITY LAW, static half (rules/GUI.md).

Installed from rules/templates/test_layout_law.py (MIGRATE-LAYOUT.md step 1,
owner go 2026-08-05). It is this project's fifth guard test.

What it fails on: GUI sources that cut content off, or that freeze an element
so it cannot take the window's free space - elide/trim APIs, forced
scrollbars, disabled wrapping, hard pixel sizes on text-bearing widgets. Both
GUI surfaces are in scope: the Qt desktop app (server/gui) and the phone
client's stylesheet (client).

A single line may opt out ONLY with a stated reason, written in that line's
comment as:  layout-law: exempt - <why>
An exemption with no reason does not count.

The runtime half of the law lives in tests/test_layout_audit_qt.py (the Qt
windows) and tests/test_layout_audit.py (the phone panels) - this test
catches the CAUSES by name, those catch the RESULT on screen.

Run:  .venv\\Scripts\\python tests/test_layout_law.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# --- CONFIGURATION (per project) -------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# directories that hold GUI sources; keep this narrow and honest
GUI_DIRS = ("server/gui", "client")

GUI_SUFFIXES = (".py", ".cs", ".xaml", ".axaml", ".ui", ".qml", ".qss", ".css")

SKIP_DIRS = {".git", "__pycache__", "node_modules", "build", "dist", "obj",
             "bin", "tests", ".venv", "venv"}

# Legacy violations that cannot be fixed in the session that installs the
# guard. Same discipline as the STRUCTURE LAW ratchet (rules/CODE.md): every
# entry names the file, WHY it is still here, and who owes the fix. The list
# may only SHRINK - adding an entry needs the owner's explicit approval.
RATCHET: dict[str, str] = {}

# --- THE BANNED PATTERNS (do not edit - shared wording with the hook) -------

EXEMPT_RE = re.compile(r"layout-law:\s*exempt\s*[-—:]\s*\S")

BANNED: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bElide(Right|Left|Middle)\b|setTextElideMode|setElideMode"),
     "Qt text elision - the user cannot read what the ellipsis ate"),
    (re.compile(r"TextTrimming\s*=\s*[\"'](?!None)"),
     "WPF TextTrimming - the same failure in XAML"),
    (re.compile(r"text-overflow\s*:\s*ellipsis"),
     "CSS text-overflow: ellipsis"),
    (re.compile(r"\bsetFixed(Size|Width|Height)\s*\("),
     "Qt hard size - the element can no longer take the free space"),
    (re.compile(r"\bsetWordWrap\s*\(\s*(False|false|0)\s*\)"),
     "word wrap disabled - reflow (ladder step 2) becomes impossible"),
    (re.compile(r"\bTextWrapping\s*=\s*[\"']NoWrap"),
     "WPF TextWrapping=NoWrap - reflow (ladder step 2) becomes impossible"),
    (re.compile(r"ScrollBarAlwaysOn"),
     "scrollbar forced ON - scrolling is ladder step 4, never a default"),
    (re.compile(r"ScrollBarVisibility\s*=\s*[\"']Visible"),
     "scrollbar forced Visible - scrolling is ladder step 4, never a default"),
    (re.compile(
        r"<(TextBlock|TextBox|Label|Button|ComboBox|CheckBox|RadioButton)\b"
        r"[^>]*\b(Width|Height)\s*=\s*[\"']\d"),
     "hard pixel size on a text-bearing XAML element"),
    (re.compile(r"-webkit-line-clamp"),
     "CSS line clamp - the rows past the clamp end in an ellipsis"),
)


def iter_gui_files() -> list[Path]:
    files: list[Path] = []
    for directory in GUI_DIRS:
        root = PROJECT_ROOT / directory
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in GUI_SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            files.append(path)
    return files


def violations_in(path: Path) -> list[str]:
    found: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for number, line in enumerate(text.splitlines(), start=1):
        if EXEMPT_RE.search(line):
            continue
        for pattern, why in BANNED:
            match = pattern.search(line)
            if match:
                found.append(f"{path.relative_to(PROJECT_ROOT)}:{number}: "
                             f"{match.group(0).strip()}  <- {why}")
                break
    return found


def test_no_banned_layout_patterns() -> None:
    offenders: list[str] = []
    for path in iter_gui_files():
        relative = path.relative_to(PROJECT_ROOT).as_posix()
        if relative in RATCHET:
            continue
        offenders.extend(violations_in(path))
    assert not offenders, (
        "THE SPACE & LEGIBILITY LAW (rules/GUI.md) - these lines cut content "
        "off or freeze it out of the free space:\n  "
        + "\n  ".join(offenders)
        + "\nFix in the ladder's order: (1) give the starving element the "
          "stretch, (2) reflow into more rows, (3) raise the window minimum, "
          "(4) scroll only when the window is genuinely full. A legitimate "
          "single line opts out with `layout-law: exempt - <reason>`."
    )


def test_ratchet_entries_still_exist() -> None:
    """A ratchet entry for a file that no longer exists is stale - the list may
    only shrink, and it shrinks honestly."""
    stale = [name for name in RATCHET if not (PROJECT_ROOT / name).is_file()]
    assert not stale, ("stale RATCHET entries (file gone) - remove them: "
                       + ", ".join(stale))


def main() -> int:
    failures = []
    for check in (test_no_banned_layout_patterns, test_ratchet_entries_still_exist):
        try:
            check()
        except AssertionError as e:
            failures.append(str(e))
    if failures:
        print("LAYOUT LAW (static) FAILED:\n", file=sys.stderr)
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    print(f"LAYOUT LAW (static) PASSED — {len(iter_gui_files())} GUI files clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
