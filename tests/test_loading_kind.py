"""Gate: every loading animation declares WHICH OF THE TWO KINDS it is.

THE RULE (owner decree 2026-08-12, and he named both kinds himself):

    "1. vrsta je loading full screen
     2. vrsta je loading samo CUBE bez background"          lang-ok: owner quote

and the reason the second kind exists, in his own example: while Chrome is
loading, the cube should spin over a TRANSPARENT page — "na taj način će
korisnik znati da se dešava učitavanje ali će i vidjeti da se u pozadini
otvara to jest da nije još gotovo" (lang-ok: owner quote). Covering that
would be hiding the only progress there is to see.

The split is decided by WHAT IS BEHIND, and by nothing else:

  FULL — the PC's own picture is about to change in a way he must not watch
         (windows climbing out of the taskbar, a grid being built).
  CUBE — we are only waiting for an answer, or watching something open that
         is worth seeing open.

WHY THIS IS A GATE AND NOT A CONVENTION. He asked for the classification to
be written into the code as a comment at every site, so the eventual move to
the shared Loading Cube gadget has its inventory in one place. A comment
nothing checks goes stale on the first new call site — this repo has met that
exact failure more than once (a pure module nobody called; a whitelist that
never carried the new field). So the comment and the ARGUMENT are both
required, and they must AGREE: a site whose comment says CUBE while the code
passes FULL is a lie in the inventory, which is worse than no inventory.

Run standalone or from build.py (fail-closed).

Each check is proven by planting its own defect:
  * drop the `, LOADING_FULL` from any call      -> "declares no kind"
  * change one comment's word to the other kind  -> "comment says X, code passes Y"
  * delete the `.cube-only` background rule      -> "the second kind is not built"
"""

import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CLIENT = PROJECT / "client"

# The definition and its own doc comments live here; this file declares the
# kinds rather than choosing one.
DEFINITION = "loading.js"

CALL = re.compile(r"\bshowLayLoading\s*\(")
KIND_ARG = re.compile(r"\bLOADING_(FULL|CUBE)\s*\)")
MARKER = re.compile(r"//\s*LOADING:\s*(FULL|CUBE)\s*—\s*(\S.*)")


def _call_sites() -> list[tuple[str, int, str, str]]:
    """(file, 1-based line, source, previous source) for every real call."""
    sites = []
    for path in sorted(CLIENT.glob("*.js")):
        if path.name == DEFINITION:
            continue
        lines = path.read_text(encoding="utf-8").split("\n")
        for number, line in enumerate(lines, 1):
            if not CALL.search(line):
                continue
            if line.lstrip().startswith("//"):
                continue                      # prose about the call, not a call
            sites.append((path.name, number, line,
                          lines[number - 2] if number >= 2 else ""))
    return sites


def check_every_call_declares_its_kind(problems: list[str]) -> None:
    for name, number, line, _ in _call_sites():
        if not KIND_ARG.search(line):
            problems.append(
                f"client/{name}:{number}: declares no kind — every call must "
                f"pass LOADING_FULL or LOADING_CUBE explicitly: {line.strip()[:90]}")


def check_every_call_carries_its_marker(problems: list[str]) -> None:
    for name, number, line, previous in _call_sites():
        marker = MARKER.search(previous)
        if marker is None:
            problems.append(
                f"client/{name}:{number}: no '// LOADING: FULL|CUBE — why' "
                f"comment on the line above: {line.strip()[:90]}")
            continue
        argument = KIND_ARG.search(line)
        if argument and marker.group(1) != argument.group(1):
            problems.append(
                f"client/{name}:{number}: comment says {marker.group(1)}, "
                f"code passes LOADING_{argument.group(1)} — the inventory and "
                f"the behaviour disagree")


def check_both_kinds_are_really_built(problems: list[str]) -> None:
    """A classification is worth nothing if only one kind renders."""
    js = (CLIENT / DEFINITION).read_text(encoding="utf-8")
    for name in ("LOADING_FULL", "LOADING_CUBE"):
        if f"const {name} =" not in js:
            problems.append(f"client/{DEFINITION}: {name} is not defined")
    if 'classList.toggle("cube-only"' not in js:
        problems.append(
            f"client/{DEFINITION}: nothing puts the `cube-only` class on the "
            f"overlay — the second kind cannot render")

    css = "\n".join(p.read_text(encoding="utf-8")
                    for p in sorted(CLIENT.glob("*.css")))
    rule = re.search(r"#lay-loading\.cube-only\s*\{([^}]*)\}", css)
    if rule is None:
        problems.append(
            "client/*.css: no `#lay-loading.cube-only` rule — the second kind "
            "is not built, so every CUBE site would still veil the screen")
    elif "background: transparent" not in rule.group(1):
        problems.append(
            "client/*.css: `#lay-loading.cube-only` does not clear the "
            "background — 'samo CUBE bez background' is the whole kind")


def check_at_least_one_of_each_is_used(problems: list[str]) -> None:
    """Guards against the classification quietly collapsing to one value."""
    used = {m.group(1) for _, _, line, _ in _call_sites()
            for m in [KIND_ARG.search(line)] if m}
    for name in ("FULL", "CUBE"):
        if name not in used:
            problems.append(
                f"no call site uses LOADING_{name} — the two kinds exist "
                f"because two things really happen; one of them has been lost")


def main() -> int:
    print("=== LOADING KIND GATE ===")
    sites = _call_sites()
    problems: list[str] = []
    check_every_call_declares_its_kind(problems)
    check_every_call_carries_its_marker(problems)
    check_both_kinds_are_really_built(problems)
    check_at_least_one_of_each_is_used(problems)
    if problems:
        print(f"  FAIL  {len(problems)} problem(s):")
        for problem in problems:
            print(f"        {problem}")
        print("\nLOADING KIND GATE FAILED — a loading animation whose kind is "
              "undeclared is one that covers something the owner asked to see, "
              "or shows something he asked to have covered.")
        return 1
    full = sum(1 for _, _, line, _ in sites
               if (m := KIND_ARG.search(line)) and m.group(1) == "FULL")
    print(f"  PASS  {len(sites)} loading site(s) classified "
          f"({full} full screen, {len(sites) - full} cube only)")
    print("\nLOADING KIND GATE PASSED — every animation declares its kind, in "
          "the code and in a comment that agrees with it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
