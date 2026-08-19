"""Gate: THE DESIGN LAB TELLS THE TRUTH ABOUT THE FILES (tools/).

A tuner is only worth having if three things hold, and each of them is a way
this kind of tool usually fails:

  1. EVERY KNOB IS REAL. A row offered in the page must be readable from the
     source it names and writable back into it. A knob whose token was renamed
     in client/style.css would otherwise sit there looking tunable and do
     nothing — the actions.json lesson in a new place.
  2. A SAVE TOUCHES ONLY THE VALUE. The prose around these declarations is the
     project's memory: the owner's verdicts, the graders' findings, the dates.
     A writer that reflowed, reformatted or dropped a comment would destroy
     more than it tuned, so a round trip is proven byte-for-byte.
  3. IT IS NOT PART OF THE PRODUCT. `tools/` is a workshop on the PC. The
     phone product must never lean on it (CLAUDE.md — the monorepo rule this
     project already carries for hooks and rules), so nothing under client/,
     server/ or android/ may import it.

Run:  .venv\\Scripts\\python -m pytest tests/test_design_lab.py
"""

import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "tools"))

import design_tokens as tokens  # noqa: E402


# ═══════════════════ 1. EVERY KNOB IS REAL ═══════════════════
def _rows(kinds):
    for group in tokens.GROUPS:
        for row in group["rows"]:
            if row["kind"] in kinds:
                yield group["id"], row


def test_every_offered_token_exists_in_its_source():
    values = {sid: tokens.read_source(sid) for sid in tokens.SOURCES}
    missing = []
    for group_id, row in _rows({"theme", "alpha"}):
        for theme in ("dark", "light"):
            if row["token"] not in values[theme]:
                missing.append(f"{group_id}: {row['token']} not in the {theme} block")
    for group_id, row in _rows({"shape"}):
        if row["token"] not in values["shape"]:
            missing.append(f"{group_id}: {row['token']} not in client/style.css :root")
    assert not missing, (
        "the design lab offers knobs that no longer exist — a renamed token is "
        "a knob that silently does nothing:\n  " + "\n  ".join(missing))


def test_a_derived_value_is_never_offered_as_a_knob():
    """`--on-gap` follows the page floor and `--topbar` is computed from the
    spacing. Pinning either would turn a rule back into a constant, which is
    exactly the drift these tokens were written to prevent."""
    for _, row in _rows({"derived"}):
        for source in tokens.SOURCES:
            assert row["token"] not in tokens._known(source), (
                row["token"] + " is derived and must not be writable")


def test_every_shape_knob_is_really_read_by_a_rule():
    """A token declared and never used is a knob that moves nothing. Every
    shape tunable must appear as `var(--name)` somewhere in the client."""
    css = "\n".join((PROJECT / "client" / name).read_text(encoding="utf-8")
                    for name in ("style.css", "theme.css", "panels.css",
                                 "layouts.css", "ledger-panel.css"))
    unused = [row["token"] for _, row in _rows({"shape"})
              if ("var(" + row["token"] + ")") not in css
              and ("var(" + row["token"] + ",") not in css]
    assert not unused, (
        "declared but never drawn with — these knobs would move nothing:\n  "
        + "\n  ".join(unused))


# ═══════════════════ 2. A SAVE TOUCHES ONLY THE VALUE ═══════════════════
def test_a_round_trip_leaves_the_file_byte_identical():
    """Write a new value into every source, then write the old one back. What
    comes out must equal what went in — every comment, every blank line, every
    spelling of an alpha."""
    cases = [
        ("dark", "--accent", "#123456"),
        ("light", "--accent", "#654321"),
        ("shape", "--ctl-radius", "19px"),
        ("sets", "Mouse", "#123456"),
    ]
    before = {}
    for source_id, _, _ in cases:
        path = PROJECT / tokens.SOURCES[source_id]["file"]
        before[path] = path.read_bytes()
    try:
        for source_id, name, value in cases:
            was = tokens.read_source(source_id)[name]
            assert tokens.write_source(source_id, {name: value}), \
                f"{source_id}/{name}: the writer reported no change"
            assert tokens.read_source(source_id)[name] == value
            tokens.write_source(source_id, {name: was})
    finally:
        for path, raw in before.items():
            if path.read_bytes() != raw:
                path.write_bytes(raw)          # never leave the tree dirty
                raise AssertionError(f"{path.name}: a round trip changed the file")


def test_the_writer_refuses_what_it_does_not_know():
    """Three refusals, each one a way a page bug could become a broken
    stylesheet: a token nobody offered, a value carrying its own `;`, and a
    name the block does not declare."""
    for source_id, name, value in (
        ("shape", "--not-a-token", "4px"),
        ("dark", "--accent", "#fff; } body { display: none"),
        ("sets", "No Such Set", "#ffffff"),
    ):
        try:
            tokens.write_source(source_id, {name: value})
        except ValueError:
            continue
        raise AssertionError(f"{source_id}/{name} was NOT refused")


def test_an_unchanged_alpha_is_left_exactly_as_it_is_written():
    """`0.80` and `0.8` are one strength and two lines. A save that rewrote
    every alpha it merely read would bury the one value he moved — and
    tests/test_ink_shadow.py reads the file's own spelling of his answer."""
    assert tokens.with_alpha("rgb(0 0 0 / 0.80)", 0.8) == "rgb(0 0 0 / 0.80)"
    assert tokens.with_alpha("rgb(0 0 0 / 0.80)", 0.5) == "rgb(0 0 0 / 0.5)"


# ═══════════════════ 3. IT IS NOT PART OF THE PRODUCT ═══════════════════
def test_nothing_shipped_imports_the_lab():
    offenders = []
    for folder in ("client", "server", "android", "setup"):
        root = PROJECT / folder
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in {".py", ".js", ".kt", ".html"}:
                continue
            if "__pycache__" in path.parts or "build" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"\b(import|from)\s+design_(lab|tokens)\b", text) \
                    or "tools/design_lab" in text:
                offenders.append(path.relative_to(PROJECT).as_posix())
    assert not offenders, (
        "the phone product must never lean on the workshop:\n  "
        + "\n  ".join(offenders))


def test_the_lab_serves_only_its_own_two_folders():
    """The allowlist is the whole of the tool's answer to "what may a browser
    on this machine read through it". A third folder here would want a
    sentence explaining itself first."""
    import design_lab
    assert design_lab.SERVE_DIRS == ("tools", "client")


# ═══════════════════ 4. A KNOB REALLY MOVES THE FRAMES ═══════════════════
# The three checks above prove the WRITER. This one proves the other half —
# that a turn of a knob reaches the specimen — and it proves it the only way
# that means anything: in a real browser, reading the computed style off a
# real button inside the preview frame. Artefact evidence is not behaviour
# evidence; a page that built its sidebar and pushed nothing would pass every
# check above.
def test_a_knob_moves_the_real_button():
    import pytest
    pytest.importorskip("playwright.sync_api")
    import threading
    from http.server import ThreadingHTTPServer
    from playwright.sync_api import sync_playwright

    import design_lab

    server = ThreadingHTTPServer(("127.0.0.1", 0), design_lab.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = "http://127.0.0.1:%d/" % server.server_address[1]
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch()
            page = browser.new_page(viewport={"width": 1500, "height": 900})
            page.goto(url)
            page.wait_for_selector(".look iframe")
            frame = page.frames[1]
            frame.wait_for_selector(".ctl")
            before = frame.eval_on_selector(
                ".ctl", "el => getComputedStyle(el).borderTopLeftRadius")

            # The knob for --ctl-radius, driven the way a finger drives it.
            page.click("summary:text('Control shape')")
            row = page.locator(".row[data-token='--ctl-radius']")
            row.locator("input[type=number]").fill("31")
            row.locator("input[type=number]").dispatch_event("input")
            page.wait_for_timeout(250)

            after = frame.eval_on_selector(
                ".ctl", "el => getComputedStyle(el).borderTopLeftRadius")
            browser.close()
    finally:
        server.shutdown()

    assert after == "31px", (
        "the knob did not reach the specimen: the button's radius read "
        + after + " (it was " + before + ")")
    assert before != after


if __name__ == "__main__":
    for name, check in sorted(globals().items()):
        if name.startswith("test_"):
            check()
            print("PASS ", name)
    print("DESIGN LAB GATE PASSED")
