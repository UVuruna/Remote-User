"""Open a file with ITS OWN default application — the double-click in Explorer,
not another tab in the editor.

THE OWNER ASKED FOR EXACTLY THIS and the distinction is the whole point: when
he clicks a file inside VS Code it opens as a TAB, which is one process and no
new window, and nothing this project does can be tested by it. Through the
SHELL the same file opens in whatever app Windows has registered — Notepad for
text, Photos for an image, a browser for SVG, Excel for CSV — which is a NEW
TOP-LEVEL WINDOW of a DIFFERENT PROCESS, and that is the case the layout rules
are actually about.

Every file type in `assets/` is here for a measured reason, not for variety:

  sample.txt   Notepad          starts instantly — the fast end of the 15 s
                                window in which a new window may still be
                                counted as one HE opened
  sample.png   Photos           a genuinely different process from the editor;
                                the cleanest case there is
  sample.csv   Excel            a slow cold start — the OTHER end of that
                                window, and the one a fixed sleep would get
                                wrong (constraint 15)
  sample.svg   your browser     a browser may serve it from a window that
                                already exists instead of making one
  sample.html  your browser     the case measured on 2026-08-13 that opens a
                                TAB and creates NO WINDOW AT ALL, sometimes in
                                a window that is not in the layout — the one
                                nothing here can currently see

USAGE

    .venv\\Scripts\\python.exe tests\\manual\\open_default.py           # menu
    .venv\\Scripts\\python.exe tests\\manual\\open_default.py png       # one
    .venv\\Scripts\\python.exe tests\\manual\\open_default.py all       # all,
                                                                     # spaced

It prints what Windows will use for each extension BEFORE opening anything, so
a case that behaves oddly can be read against the handler that produced it
rather than guessed at afterwards.

It is an INSTRUMENT, not a gate: nothing here is wired into run_guards.py or
build.py, and nothing it shows may be cited as proof that something works.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"

# Order matters: fastest handler first, so a run of "all" starts with the case
# that settles immediately and ends with the ones that need patience.
FILES = [
    ("txt", "sample.txt", "a tiny app that opens instantly"),
    ("png", "sample.png", "a different process from the editor"),
    ("svg", "sample.svg", "a browser may reuse a window instead of making one"),
    ("csv", "sample.csv", "a slow cold start"),
    ("html", "sample.html", "opens a TAB, often no new window at all"),
]

# Between two opens in "all" mode. NOT an estimate of how long an app needs —
# constraint 15 forbids that, and nothing here waits on a condition. It is the
# spacing that keeps the runs legible to a PERSON watching the phone: two
# windows appearing in the same second cannot be told apart by eye, and this
# script's only output is what he sees.
SPACING_S = 6.0


def handler_for(ext: str) -> str:
    """What Windows says it will use for this extension. Read from the shell's
    own association database (`assoc` + `ftype`), never guessed from a table of
    ours that would drift from his machine the day he changes a default."""
    try:
        assoc = subprocess.run(["cmd", "/c", "assoc", f".{ext}"],
                               capture_output=True, text=True, timeout=10)
        if assoc.returncode != 0 or "=" not in assoc.stdout:
            return "no association registered"
        kind = assoc.stdout.strip().split("=", 1)[1]
        ftype = subprocess.run(["cmd", "/c", "ftype", kind],
                               capture_output=True, text=True, timeout=10)
        if ftype.returncode != 0 or "=" not in ftype.stdout:
            return kind
        return ftype.stdout.strip().split("=", 1)[1]
    except (OSError, subprocess.SubprocessError):
        return "could not be read"


def show_table() -> None:
    print("What THIS machine will open each file with:\n")
    for ext, name, why in FILES:
        path = ASSETS / name
        mark = " " if path.exists() else "!"
        print(f" {mark} .{ext:<5} {name:<14} {why}")
        print(f"        -> {handler_for(ext)[:96]}")
    print()


def open_one(name: str) -> bool:
    path = ASSETS / name
    if not path.exists():
        print(f"MISSING: {path}")
        return False
    print(f"opening {name} ...")
    # `os.startfile` IS the double click: it asks the shell to run the file's
    # default verb, which is the same path Explorer takes. Deliberately not
    # `subprocess` with an app name — naming an app would make this a test of
    # that app instead of a test of HIS machine's own association.
    os.startfile(str(path))          # noqa: S606 - the shell verb is the point
    return True


def main() -> int:
    if not ASSETS.exists():
        print(f"No assets folder at {ASSETS}")
        return 1
    arg = (sys.argv[1] if len(sys.argv) > 1 else "").lower().strip()

    show_table()

    if arg == "all":
        print(f"Opening all {len(FILES)}, {SPACING_S:g}s apart so each one can "
              "be watched on its own.\n")
        for i, (_ext, name, _why) in enumerate(FILES):
            open_one(name)
            if i < len(FILES) - 1:
                time.sleep(SPACING_S)
        return 0

    if arg:
        for ext, name, _why in FILES:
            if arg in (ext, name):
                return 0 if open_one(name) else 1
        print(f"Unknown: {arg!r}")
        return 1

    print("Pick one:")
    for i, (ext, name, _why) in enumerate(FILES, 1):
        print(f"  {i}. {name}   (.{ext})")
    print(f"  {len(FILES) + 1}. all of them, {SPACING_S:g}s apart")
    try:
        choice = input("\nnumber (or Enter to quit): ").strip()
    except EOFError:
        return 0
    if not choice:
        return 0
    if choice.isdigit():
        n = int(choice)
        if 1 <= n <= len(FILES):
            return 0 if open_one(FILES[n - 1][1]) else 1
        if n == len(FILES) + 1:
            for i, (_ext, name, _why) in enumerate(FILES):
                open_one(name)
                if i < len(FILES) - 1:
                    time.sleep(SPACING_S)
            return 0
    print("Nothing opened.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
