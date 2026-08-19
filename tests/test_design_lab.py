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
    for group_id, row in _rows({"theme", "shadow"}):
        for theme in ("dark", "light"):
            if row["token"] not in values[theme]:
                missing.append(f"{group_id}: {row['token']} not in the {theme} block")
    for group_id, row in _rows({"shape"}):
        if row["token"] not in values["shape"]:
            missing.append(f"{group_id}: {row['token']} not in client/style.css :root")
    for group_id, row in _rows({"jscolor"}):
        if row["token"] not in values["js"]:
            missing.append(f"{group_id}: {row['token']} is not a const in client/theme.js")
    assert not missing, (
        "the design lab offers knobs that no longer exist — a renamed token is "
        "a knob that silently does nothing:\n  " + "\n  ".join(missing))


def test_the_shadow_colours_are_offered_at_all():
    """THE ROUND-2 DEFECT, as a check. He went looking for the white shadow
    drawn under black letters, and it was not in the list at ANY quality of
    grouping: the round that made the shadow colour a rule left the rule
    itself untunable, so the page could only offer the strength of a colour
    nobody could choose. The two constants `client/theme.js` decides between
    are rows now, and this is what stops the next rule from disappearing the
    same way."""
    offered = {row["token"] for _, row in _rows({"jscolor"})}
    assert offered == {"SHADOW_DARK", "SHADOW_LIGHT"}, offered


def test_every_row_says_what_it_does_and_shows_a_picture():
    """His round-2 sentence, as a gate: a knob with no sentence is a knob
    nobody turns. Every row carries `help` (or, for the two computed ones,
    `why`) and names a diagram that `tools/design_pics.js` really draws — a
    `pic` naming a picture that does not exist is a row with a blank space
    where its explanation should be."""
    drawn = set(re.findall(r"^\s*'?([a-z-]+)'?:\s*'",
                           (PROJECT / "tools" / "design_pics.js")
                           .read_text(encoding="utf-8"), re.M))
    dumb, unpainted = [], []
    for group in tokens.GROUPS:
        for row in group["rows"]:
            where = group["id"] + "/" + row.get("token", row["kind"])
            if not (row.get("help") or row.get("why")):
                dumb.append(where)
            if row.get("pic") not in drawn:
                unpainted.append(where + " -> " + str(row.get("pic")))
    assert not dumb, "rows with no sentence:\n  " + "\n  ".join(dumb)
    assert not unpainted, ("rows naming a diagram design_pics.js does not "
                           "draw:\n  " + "\n  ".join(unpainted))


def test_every_group_and_row_is_pointed_somewhere():
    """`demo` is what lets the page POINT at what a value touches instead of
    describing it. Two of the selectors are the board's own — `:dark-ink` and
    `:light-ink` are answered from what `paintSet` really produced — and the
    rest are plain CSS. A row with no `demo` is allowed; a row with a `demo`
    the board cannot possibly answer is not."""
    board = (PROJECT / "tools" / "preview.html").read_text(encoding="utf-8")
    unknown = []
    for group in tokens.GROUPS:
        for row in group["rows"]:
            for part in [p.strip() for p in (row.get("demo") or "").split(",")]:
                if not part or part in (":dark-ink", ":light-ink"):
                    continue
                # The class or id the selector is built on has to be a word the
                # board actually writes; the shapes themselves are checked in
                # the browser below.
                head = re.split(r"[ >]", part)[-1]
                token = re.sub(r"^[.#]", "", head).split(".")[0].split(":")[0]
                if token and token not in ("body", "svg") and token not in board:
                    unknown.append(group["id"] + ": " + part)
    assert not unknown, ("rows pointing at something the specimen board never "
                         "draws:\n  " + "\n  ".join(unknown))


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
        ("js", "SHADOW_LIGHT", "254 253 252"),
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
        # A shadow colour is interpolated straight into `rgb(… / a)` by
        # client/theme.js, so anything that is not an `r g b` triple would be
        # a stylesheet that silently draws nothing.
        ("js", "SHADOW_DARK", "#000000"),
        ("js", "SHADOW_DARK", '0 0 0"; alert(1); //'),
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


# ═══════════════════ 4. IN A REAL BROWSER ═══════════════════
# The checks above prove the WRITER. These prove the other half — that the page
# does on screen what it says — and they prove it the only way that means
# anything: a real browser, reading computed style off a real button inside a
# real preview frame. Artefact evidence is not behaviour evidence; a page that
# built its sidebar and pushed nothing would pass every check above.
#
# ONE browser for all of it: launching chromium is most of the cost, and a
# gate that takes two minutes is a gate that gets skipped.
def test_the_pressed_look_has_a_knob_in_every_one_of_the_eight():
    """THE PRESSED RING AND HALO REACH ALL EIGHT LOOKS (owner 2026-08-19).

    A coloured control's press is drawn by `body[data-colored="true"]
    .ctl.held` in client/theme.css — one attribute and two classes, which
    outranks `.ctl.held` in style.css — and it used to carry its two sizes as
    LITERALS. So the lab's two sliders moved four of the eight frames and
    stopped dead, with nothing on the page saying so. His ruling was NOT to
    make them share: the coloured press may want different numbers, so it has
    its OWN pair. What must stay true is that neither rule holds a number a
    knob cannot reach.

    Source-level on purpose, and cheap: the browser check below drives the
    coloured knob and reads the computed shadow back off a real button, which
    is where "the value is really used" is proven. This one is the other half
    — that no LITERAL crept back into either rule — and it is the half that
    catches a revert in a diff rather than in a screenshot."""
    css = (PROJECT / "client" / "theme.css").read_text(encoding="utf-8")
    rule = re.search(r'body\[data-colored="true"\] \.ctl\.held \{(.*?)\}',
                     css, re.S)
    assert rule, "client/theme.css no longer has a coloured `.ctl.held` rule"
    body = rule.group(1)
    for token in ("--held-ring-colored", "--held-glow-colored"):
        assert token in body, (
            "the coloured pressed rule does not read %s — a slider that "
            "cannot reach four of the eight looks is a slider that lies "
            "about its reach" % token)
    assert not re.search(r"\b\d+px\b", body), (
        "a hard-coded size is back in the coloured pressed rule: %r" % body)

    plain = re.search(r"^\.ctl\.held \{(.*?)^\}",
                      (PROJECT / "client" / "style.css").read_text(encoding="utf-8"),
                      re.S | re.M)
    assert plain and not re.search(r"\b\d+px\b", plain.group(1)), (
        "the plain pressed rule grew a hard-coded size")

    # And all four are really offered, each with its own sentence, so nobody
    # has to guess which pair reaches which half of the wall.
    offered = {row.get("token") for group in tokens.GROUPS
               for row in group["rows"]}
    for token in ("--held-ring", "--held-glow",
                  "--held-ring-colored", "--held-glow-colored"):
        assert token in offered, "%s is not on the bench" % token

def test_the_page_does_on_screen_what_it_says():
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
    found = {}
    try:
        with sync_playwright() as play:
            browser = play.chromium.launch()
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.goto(url)
            page.wait_for_selector(".look iframe")
            page.wait_for_timeout(1500)          # eight frames, each fitting itself
            frame = page.frames[1]
            frame.wait_for_selector(".ctl")
            found["before"] = frame.eval_on_selector(
                ".ctl", "el => getComputedStyle(el).borderTopLeftRadius")

            # (a) HIS SECOND COMPLAINT: no card scrolls, and no cell is empty.
            found["wall"] = page.evaluate(WALL_JS)

            # (b) HIS THIRD: the value he could not find is findable, and every
            #     row is pointed at something the board really draws.
            page.fill("#find", "shadow")
            page.wait_for_timeout(200)
            found["shadow_visible"] = page.locator(
                ".row[data-token='SHADOW_LIGHT']").is_visible()
            page.fill("#find", "")

            # (c) THE POINTER really outlines something, in the look where the
            #     question is asked. `#colored` and `#fill` only decide
            #     anything once ONE look is shown — with all eight up they are
            #     the axes themselves — so the wall is narrowed first, to the
            #     one rendering where black ink exists at all.
            page.select_option("#which", "one")
            page.select_option("#theme", "dark")
            page.select_option("#colored", "true")
            page.select_option("#fill", "full")
            page.wait_for_timeout(1500)
            found["pointed"] = page.evaluate(POINT_JS)

            # (d) A knob still reaches the specimen, driven the way a finger
            #     drives it.
            page.fill("#find", "corner radius")
            page.wait_for_timeout(200)
            knob = page.locator(".row[data-token='--ctl-radius'] input[type=number]")
            knob.fill("31")
            knob.dispatch_event("input")
            page.wait_for_timeout(300)
            found["after"] = page.frames[1].eval_on_selector(
                ".ctl", "el => getComputedStyle(el).borderTopLeftRadius")
            browser.close()
    finally:
        server.shutdown()

    wall = found["wall"]
    assert wall["cells"] == wall["cards"], (
        "the wall left empty cells — eight looks must divide into full rows: "
        + str(wall))
    assert not wall["scrolling"], (
        "cards still scroll inside themselves: " + str(wall["scrolling"]))
    assert found["shadow_visible"], (
        "typing `shadow` does not surface the colour he went looking for")
    assert found["pointed"]["checked"] >= 40, (
        "almost every row names what it points at, so a page that stopped "
        "writing `data-demo` would make the next check pass by having nothing "
        "to check — only " + str(found["pointed"]["checked"]) + " rows carried one")
    assert found["pointed"]["missed"] == [], (
        "rows pointing at nothing the board draws: "
        + str(found["pointed"]["missed"]))
    assert found["pointed"]["darkInk"] > 0, (
        "no specimen came out with black ink in the coloured filled look, so "
        "the white-shadow row is pointing at an empty set — the palette or the "
        "board changed under this check")
    assert found["after"] == "31px", (
        "the knob did not reach the specimen: the button's radius read "
        + found["after"] + " (it was " + found["before"] + ")")
    assert found["before"] != found["after"]


# Every card measured against ITS OWN frame. `documentElement.scrollHeight`
# is not the question: `#screen` is `position: fixed; inset: 0` and is
# therefore always exactly one viewport tall, and under `zoom` that height and
# the board's own live in different coordinate spaces. The board's bottom edge
# against `innerWidth/innerHeight` is the one honest comparison — the same
# lesson tools/preview.html carries in `boardBottom`.
WALL_JS = """
() => {
  const host = document.getElementById("frames");
  const cs = getComputedStyle(host);
  const cards = [...host.querySelectorAll(".look iframe")];
  const scrolling = [];
  cards.forEach((f, i) => {
    const board = f.contentDocument.getElementById("board");
    if (!board) { scrolling.push("frame " + i + ": no board"); return; }
    const over = board.getBoundingClientRect().bottom - f.contentWindow.innerHeight;
    if (over > 2) scrolling.push("frame " + i + " overflows by " + Math.round(over));
  });
  return {
    cells: cs.gridTemplateColumns.split(" ").length *
           cs.gridTemplateRows.split(" ").length,
    cards: cards.length,
    scrolling,
  };
}
"""

# The `demo` selector of every row, run inside a real frame. `:dark-ink` and
# `:light-ink` are the board's own (answered from what `paintSet` produced), so
# they are asked as the board answers them.
POINT_JS = """
() => {
  const doc = document.querySelector(".look iframe").contentDocument;
  const missed = [];
  let darkInk = doc.querySelectorAll('[data-ink="dark"]').length;
  let checked = 0;
  document.querySelectorAll(".row").forEach((row) => {
    const token = row.dataset.token || "(row)";
    const demo = row.dataset.demo;
    if (!demo) return;
    checked++;
    let hit = 0;
    demo.split(",").map((s) => s.trim()).filter(Boolean).forEach((part) => {
      if (part === ":dark-ink") hit += doc.querySelectorAll('[data-ink="dark"]').length;
      else if (part === ":light-ink") hit += doc.querySelectorAll('[data-ink="light"]').length;
      else { try { hit += doc.querySelectorAll(part).length; } catch (e) { /* below */ } }
    });
    if (!hit) missed.push(token + " -> " + demo);
  });
  return { missed, darkInk, checked };
}
"""


if __name__ == "__main__":
    for name, check in sorted(globals().items()):
        if name.startswith("test_"):
            check()
            print("PASS ", name)
    print("DESIGN LAB GATE PASSED")
