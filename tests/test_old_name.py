"""Gate: no shipped file still calls this product Remote User.

Born from the rename of 2026-08-11/12, and specifically from how it FAILED
the first time. The sweep tool does not know `.nsi`, so `installer.nsi` was
patched by hand — and the hand searched only for `RemoteUser`, one spelling.
`!define APP_DISPLAY "Remote User"` survived, the verification grep repeated
the same incomplete pattern, and the owner met the old name in the title bar
of the very installer that was supposed to carry the new one.

The second half was worse and nobody saw it at all: `client/install.html`
still built its `intent://` with `scheme=remoteuser;package=com.uvuruna.remoteuser`.
That is the ONE tap the whole install funnel exists for, and it pointed at an
application id that no longer exists — the funnel would have opened nothing.

So the check is not "grep for the string I just fixed". It is: every spelling
of the old name (spaced, hyphenated, joined, any case), across every text file
we ship, is a failure unless it is on the short list of places the name is
deliberately, permanently correct.

Run standalone or from build.py (fail-closed, before anything is packaged).
"""

import os
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent

# Directories that hold no shipped source: build output, dependencies, the
# agent harness's own scratch, and the dev log (a real historical record of
# runs that really happened under the old path).
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".pytest_cache", ".gradle", "bin", "obj", ".claude", "keystore", "logs",
    "UV",
}

OLD_NAME = re.compile(r"remote[ _\-]?user", re.IGNORECASE)

# The name is CORRECT in exactly these places, and each says why. A line is
# allowed only when its file is listed AND the line matches the reason —
# a blanket file exemption would have hidden the APP_DISPLAY bug, since
# installer.nsi legitimately quotes the owner further down.
ALLOWED: dict[str, tuple[str, ...]] = {
    # The README's own name story CONTRASTS the two names; that is the point
    # of the section the naming gate requires.
    "README.md": ('"Remote User" described the',),
    # The key's slot inside a keystore that already exists and cannot be
    # renamed in place — renaming it means a new signing identity.
    "android/app/build.gradle.kts": ('"remoteuser" is the key', 'RU_KEY_ALIAS'),
    "setup/build_apk.py": ('rename deliberately left reading', 'KEY_ALIAS = "remoteuser"'),
    # The migration must NAME the folder it is carrying data out of.
    "server/config.py": ("%LOCALAPPDATA%/RemoteUser", "was called Remote User until then",
                         '"RemoteUser"'),
    # The owner's own sentence, quoted. A quotation is not a reference.
    "setup/installer.nsi": ("cim udjem u instalaciju",),
    "tests/test_update_handover.py": ("čim uđem u instalaciju",),
}


def _allowed(rel: str, line: str) -> bool:
    return any(fragment in line for fragment in ALLOWED.get(rel, ()))


def find_survivors() -> list[str]:
    survivors = []
    for current, directories, files in os.walk(PROJECT):
        directories[:] = [d for d in directories if d not in SKIP_DIRS]
        for name in files:
            path = Path(current) / name
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue                     # binary or unreadable: not text we ship
            rel = path.relative_to(PROJECT).as_posix()
            if path.resolve() == Path(__file__).resolve():
                continue                     # this gate's whole job is to spell it
            for number, line in enumerate(text.splitlines(), 1):
                if OLD_NAME.search(line) and not _allowed(rel, line):
                    survivors.append(f"{rel}:{number}: {line.strip()[:120]}")
    return survivors


def main() -> int:
    print("=== OLD NAME GATE ===")
    survivors = find_survivors()
    if survivors:
        print(f"  FAIL  {len(survivors)} line(s) still call this product Remote User:")
        for hit in survivors:
            print(f"        {hit}")
        print("\nOLD NAME GATE FAILED — a user would meet the old name. Fix the "
              "line, or add it to ALLOWED with the reason it is permanently "
              "correct. Never widen ALLOWED to a whole file.")
        return 1
    print("  PASS  no shipped file calls this product Remote User")
    print("\nOLD NAME GATE PASSED — every surviving mention is a quotation, a "
          "migration source, or the README's own name story.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
