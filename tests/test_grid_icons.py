"""THE LIST SAYS WHICH SHAPE EACH LAYOUT IS — the grid icon gate.

Owner request 2026-08-09 (task 164). A row in the layout list carried a name
and nothing about its SHAPE, so a solo window, a two-split and a four-grid
read identically until he opened one. The catalogue is not derived here or
anywhere else: it is his own sheet, `UV/grid_variations.png` (2026-08-07) —
two columns LANDSCAPE and PORTRAIT, three rows 2 / 3 / 4, with the THREE row
holding four arrangements in each column and the 2 and 4 rows holding one
each. Six shapes per orientation, plus solo, is 7; with the orientations, 14.

Three things have to be true, and this project has been burned by gates that
proved only one:

1. **Every variant draws its OWN picture.** That is the entire feature — two
   shapes that draw the same thing tell him nothing, and the failure is
   silent. The sheet is the source: a grid choice is a DRAWING, never a word
   (owner 2026-08-07: "GRID kada korisnik bira budu skice ... a ne tekstovi
   tipa 'GRID 2x1'"). # lang-ok: owner quote
2. **The picture is the TRUTH about the PC screen.** The partitions are
   compared, number for number, against the REAL `server/grids.py` `_cells` —
   the arithmetic that actually places his windows. `client/grids.js` has
   carried a note since it was split off ("it mirrors server/grids.py shape
   for shape; if one changes, the other must") and nothing has ever checked
   it. A drawing that disagrees with the placement is worse than no drawing.
3. **Something CALLS it.** A pure function nobody runs is a feature that does
   not exist — the actions.json lesson of 2026-08-07, where a field was
   shipped through four releases without ever reaching the owner's own file.

The geometry is pure (`client/grid-icons.js`, the view-anchor.js /
cursor-shapes.js pattern) and is run WHOLE in node.

Run:  .venv\\Scripts\\python tests/test_grid_icons.py
Requires: node on PATH — a HARD requirement (fail-closed in setup/build.py,
the test_view_anchor.py precedent). Never skip it silently.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MODULE = PROJECT / "client" / "grid-icons.js"
GRIDS_JS = PROJECT / "client" / "grids.js"
LAYOUTS_JS = PROJECT / "client" / "layouts.js"
INDEX = PROJECT / "client" / "index.html"
LOAD_TEST = PROJECT / "client" / "load_test.js"
REGISTRY = PROJECT / "server" / "layout_registry.py"
FRAME = REGISTRY.with_name("layout_state.py")

sys.path.insert(0, str(PROJECT / "server"))

import grids  # noqa: E402

# HIS SHEET, held here as this gate's OWN expectation rather than read from
# the module — a catalogue that marks its own homework proves nothing. Per
# orientation: 2 in one arrangement, 3 in four, 4 in one.
SHEET = {2: ["2"], 3: ["3-top", "3-bottom", "3-left", "3-right"], 4: ["4"]}
ORIENTS = ["landscape", "portrait"]
# Solo is the seventh, and the one he most needs told apart from a grid.
CATALOGUE = [(1, None, o) for o in ORIENTS] + [
    (count, grid, o) for o in ORIENTS for count in (2, 3, 4)
    for grid in SHEET[count]]


# ═════════════════════════ running the real module ═════════════════════════
def node_run(body: str):
    """Evaluate an expression against the REAL client/grid-icons.js."""
    if not shutil.which("node"):
        raise AssertionError(
            "node is required for the grid icon gate (it runs the REAL "
            "client/grid-icons.js geometry) — install Node.js. Never skip a "
            "gate silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_gridicon_gate_"))
    script = work / "run.js"
    script.write_text(
        f"const M = require({json.dumps(str(MODULE))});\n"
        "const {gridIconBox, gridIconRects, gridIconPath, gridIconSvg,\n"
        "       gridIconShape, gridIconChoices, gridIconName} = M;\n"
        f"console.log(JSON.stringify((() => {{ {body} }})()));\n",
        encoding="utf-8")
    try:
        out = subprocess.run([shutil.which("node"), str(script)],
                             capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            raise AssertionError(f"node failed: {out.stderr.strip()}")
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def drawings(entries):
    """One {box, path, rects} per (count, grid, orient) — the drawn geometry,
    which is the only thing the owner can actually tell apart."""
    calls = [{"count": c, "grid": g, "orient": o} for c, g, o in entries]
    return node_run(
        f"const calls = {json.dumps(calls)};\n"
        "return calls.map(c => ({box: gridIconBox(c.orient),\n"
        "  path: gridIconPath(c.count, c.grid, c.orient),\n"
        "  rects: gridIconRects(c.count, c.grid, c.orient)}));")


def signature(d) -> str:
    """What the eye sees: the box it is drawn on AND the shapes on it. The box
    is part of it on purpose — every three has the same partition in both
    orientations, and it is the LEANING BOX that tells a portrait three from a
    landscape one (owner round 3, 2026-08-07)."""
    return f"{d['box']}|{d['path']}"


def label(entry) -> str:
    count, grid, orient = entry
    return f"{grid or 'solo'} x{count} {orient}"


# ═══════════════════════ 1. EVERY VARIANT ITS OWN PICTURE ═══════════════════
def check_the_catalogue_is_his_sheet() -> None:
    """The module's own catalogue must be exactly the sheet — 7 shapes, 14
    with the orientations. A shape quietly dropped (or an extra one invented)
    is a row of the list that can never be drawn right."""
    got = node_run("return M.GRID_ICON_CATALOGUE.map("
                   "e => [e.count, e.grid, e.orient]);")
    want = sorted(f"{c}|{g}|{o}" for c, g, o in CATALOGUE)
    have = sorted(f"{c}|{g}|{o}" for c, g, o in got)
    if have != want:
        raise AssertionError(
            f"the catalogue is not his sheet ({len(got)} entries, expected "
            f"{len(CATALOGUE)}):\n  missing {sorted(set(want) - set(have))}\n"
            f"  extra   {sorted(set(have) - set(want))}")


def check_every_catalogue_entry_has_its_own_silhouette() -> None:
    """THE FEATURE. Fourteen variants, fourteen different pictures — if two
    draw the same thing the row is lying about at least one of them, and he
    would only find out by opening it."""
    seen: dict[str, str] = {}
    for entry, d in zip(CATALOGUE, drawings(CATALOGUE)):
        sig = signature(d)
        if sig in seen:
            raise AssertionError(
                f"{label(entry)} draws exactly what {seen[sig]} draws — "
                "two shapes, one picture")
        seen[sig] = label(entry)


def check_portrait_and_landscape_differ_for_every_shape() -> None:
    """Only "2" changes its PARTITION with orientation; the other six keep it
    and lean their BOX instead. Both are ways of being different, and the
    check is the same: the two columns of his sheet must never draw one
    picture. (A fixed square box was the real bug once — a landscape three and
    a portrait three came out pixel-for-pixel identical.)"""
    for count, shapes in list(SHEET.items()) + [(1, [None])]:
        for grid in shapes:
            land, port = drawings([(count, grid, "landscape"),
                                   (count, grid, "portrait")])
            if signature(land) == signature(port):
                raise AssertionError(
                    f"{grid or 'solo'} draws the same picture in landscape and "
                    "in portrait — his sheet has two columns for a reason")


# ═════════════ 2. THE PICTURE IS THE TRUTH ABOUT THE PC SCREEN ═════════════
SPAN = 1000   # even halves, so the server's integer division is exact


def server_fractions(grid: str, orient: str):
    """Where server/grids.py REALLY puts the windows, as fractions of the
    region — the arithmetic that runs on his PC."""
    return [(x / SPAN, y / SPAN, w / SPAN, h / SPAN)
            for x, y, w, h in grids._cells((0, 0, SPAN, SPAN), grid, orient)]


def check_the_cells_are_the_servers_own_partition() -> None:
    """The drawing must be the PLACEMENT. Compared number for number against
    the real `grids._cells` — including MEMBER ORDER, because cell k of the
    picture is member k of the layout and a chooser points at a window by
    pointing at its square."""
    table = node_run("return M.GRID_ICON_CELLS;")
    for orient in ORIENTS:
        for count, shapes in SHEET.items():
            for grid in shapes:
                key = f"2:{orient}" if grid == "2" else grid
                if key not in table:
                    raise AssertionError(f"the module draws no {key!r}")
                drawn = [(x / 2, y / 2, w / 2, h / 2) for x, y, w, h in table[key]]
                real = server_fractions(grid, orient)
                if len(drawn) != count:
                    raise AssertionError(
                        f"{grid} {orient}: drawn as {len(drawn)} cells, "
                        f"the server places {count} windows")
                for i, (a, b) in enumerate(zip(drawn, real)):
                    if max(abs(p - q) for p, q in zip(a, b)) > 1e-9:
                        raise AssertionError(
                            f"{grid} {orient}: cell {i} is drawn at {a} but the "
                            f"server places that member at {b} — the picture "
                            "disagrees with the desk")


def check_the_cells_partition_the_box_without_overlapping() -> None:
    """Geometry sanity on the DRAWN rects: inside the box, no cell on top of
    another, and together covering it. A drawing with a hole or an overlap
    reads as a different arrangement than the one it is."""
    for entry, d in zip(CATALOGUE, drawings(CATALOGUE)):
        bw, bh = d["box"]
        rects = d["rects"]
        area = 0.0
        for r in rects:
            if r["x"] < 0 or r["y"] < 0 or r["x"] + r["w"] > bw or r["y"] + r["h"] > bh:
                raise AssertionError(f"{label(entry)}: a cell leaves the box: {r}")
            if r["w"] <= 0 or r["h"] <= 0:
                raise AssertionError(f"{label(entry)}: an empty cell: {r}")
            area += r["w"] * r["h"]
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                if (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                        and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]):
                    raise AssertionError(
                        f"{label(entry)}: two cells overlap: {a} and {b}")
        # The gaps between cells are the 1-unit insets, nothing more.
        if area < bw * bh * 0.6:
            raise AssertionError(
                f"{label(entry)}: the cells cover only {area:.0f} of "
                f"{bw * bh} — the drawing is mostly empty space")


# ═══════════ 3. THE ASYMMETRY: ONLY A THREE HAS AN ARRANGEMENT ═══════════
def check_only_a_three_may_change_its_arrangement() -> None:
    """Owner 2026-08-07, read straight off the sheet: the 3 row holds four
    drawings per column, the 2 and 4 rows hold one. So a two and a four may
    flip portrait/landscape and NOTHING else. Held in the module, pure, so no
    panel can re-derive it and offer him a choice that does not exist."""
    asked = [(1, None), (2, "2"), (3, "3-top"), (3, "3-right"), (4, "4"),
             (2, "2x1"), (4, "2x2")]
    got = node_run(
        f"const a = {json.dumps(asked)};\n"
        "return a.map(([c, g]) => gridIconChoices(c, g));")
    for (count, grid), choices in zip(asked, got):
        want = SHEET[3] if count == 3 else []
        if sorted(choices) != sorted(want):
            raise AssertionError(
                f"a {grid or 'solo'} of {count} offers {choices}, expected "
                f"{want} — only a three has arrangements")


# ═══════════════════ 4. NOTHING UNKNOWN MAY EVER THROW ═══════════════════
def check_an_unknown_key_falls_back_to_a_safe_generic() -> None:
    """A row must always draw something. A grid name from a NEWER server, a
    field that never arrived, a nonsense count — none of them may throw (one
    exception while building the list kills the whole panel) and none may draw
    a lie. The rule: a known name wins; an unknown name with a real count
    falls back to the default shape for THAT COUNT, which is the server's own
    default; anything else is the solo rectangle."""
    cases = [
        # (count, grid) -> how many cells the drawing must have
        [3, "3-diagonal", 3],     # a shape from a newer server
        [4, "5-star", 4],
        [2, None, 2],             # the grid field never arrived
        [3, "", 3],
        [2, "2x1", 2],            # the legacy names still read
        [4, "2x2", 4],
        [1, "4", 1],              # a name far too big for one window
        [3, "2", 3],              # a name too SMALL for the members: count wins
        [0, "3-top", 3],          # no count at all: draw the whole shape
        [None, "4", 4],
        [1, None, 1],
        [0, None, 1],
        [-2, None, 1],
        [99, "nonsense", 4],      # never more cells than a layout can hold
        [2.7, "4", 2],            # a fractional count still draws something
    ]
    got = node_run(
        f"const cases = {json.dumps(cases)};\n"
        "return cases.map(([c, g]) => {\n"
        "  try { return gridIconRects(c, g, 'landscape').length; }\n"
        "  catch (e) { return 'THREW: ' + e.message; }\n"
        "});")
    for (count, grid, want), cells in zip(cases, got):
        if cells != want:
            raise AssertionError(
                f"count={count!r} grid={grid!r} drew {cells!r} cells, "
                f"expected {want}")


def check_fewer_live_members_than_cells_draws_only_what_is_there() -> None:
    """A window closed at the desk is pruned and the TEMPLATE is left alone
    (`LayoutRegistry.prune`), and `focus` then places the survivors into the
    FIRST cells of that template. So a four holding three windows really does
    show three quadrants and one gap — and the picture must say so, not
    pretend to be a tidy three."""
    four_of_three, three_shape = drawings([(3, "4", "landscape"),
                                           (3, "3-top", "landscape")])
    if len(four_of_three["rects"]) != 3:
        raise AssertionError(
            f"a four holding three drew {len(four_of_three['rects'])} cells")
    if signature(four_of_three) == signature(three_shape):
        raise AssertionError(
            "a four holding three draws exactly what a real three draws — "
            "the screen does not look like that")
    full_four, = drawings([(4, "4", "landscape")])
    if four_of_three["rects"] != full_four["rects"][:3]:
        raise AssertionError(
            "the surviving members are not drawn in the cells focus() really "
            "places them into")


def check_one_lit_cell_names_the_cell_it_lights() -> None:
    """`gridIconSvg(..., {cell: k})` is how a chooser says "this window is THIS
    square" without a word. The lit path must be cell k's own geometry, and
    the others must still be drawn (faint) — a picture with the rest missing
    would read as the layout already having been cut down."""
    got = node_run(
        "const svgs = [0, 1, 2, 3].map(k => gridIconSvg(4, '4', 'landscape',"
        " {cell: k}));\n"
        "const paths = [0, 1, 2, 3].map(k => gridIconPath(4, '4', 'landscape',"
        " [k]));\n"
        "return {svgs, paths};")
    for k, (svg, path) in enumerate(zip(got["svgs"], got["paths"])):
        if svg.count("<path") != 2:
            raise AssertionError(
                f"cell {k} lit drew {svg.count('<path')} paths, expected 2 "
                "(the rest faint, then the lit one)")
        if f'<path d="{path}"/>' not in svg:
            raise AssertionError(f"cell {k} lit does not draw cell {k}")
        if "opacity" not in svg:
            raise AssertionError(
                f"cell {k} lit drew the other cells at full strength — "
                "nothing is lit if everything is")


# ═══════════════════════ 5. THE WIRING, BOTH ENDS ═══════════════════════
def check_the_page_loads_the_module_before_its_users() -> None:
    html = INDEX.read_text(encoding="utf-8")
    order = [html.find(f"/static/{f}") for f in
             ("grid-icons.js", "grids.js", "layouts.js")]
    if order[0] == -1:
        raise AssertionError("index.html never loads grid-icons.js")
    if not (order[0] < order[1] < order[2]):
        raise AssertionError(
            "grid-icons.js must load BEFORE grids.js (which reads it at LOAD "
            f"for GRID_THREE) and before layouts.js — offsets {order}")
    files = LOAD_TEST.read_text(encoding="utf-8")
    if '"grid-icons.js"' not in files:
        raise AssertionError(
            "client/load_test.js does not run grid-icons.js — a load-time "
            "reference between these two files is exactly what it exists to "
            "catch")


def check_grids_js_delegates_instead_of_keeping_a_second_copy() -> None:
    """The partitions were about to have a THIRD copy (server/grids.py, this
    module, and the list). grids.js must draw through the module, not beside
    it — a second table is how the picture and the desk drift apart."""
    src = GRIDS_JS.read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("//"))
    # A PARTITION table maps a shape name to an ARRAY of cells. `GRID_CELLS`
    # in grids.js maps the same names to a COUNT — a different thing, and it
    # stays there: how many windows fit is the wheel-cap's question, not the
    # drawing's. So the bracket is what this looks for, not the name.
    for shape in ("2", "3-top", "3-bottom", "3-left", "3-right", "4"):
        if re.search(rf'"{re.escape(shape)}"\s*:\s*\[', code):
            raise AssertionError(
                f"client/grids.js defines the CELLS of {shape!r} again — the "
                "shapes live in grid-icons.js now, or they will drift")
    if "gridIconSvg(" not in code:
        raise AssertionError(
            "client/grids.js no longer draws through grid-icons.js — the "
            "creation panel and the list would draw from two tables")


def check_the_layout_list_draws_the_shape_of_every_row() -> None:
    """THE POINT OF THE ROUND, and the check that makes it real. A pure module
    nobody calls is a feature that does not exist (the actions.json lesson,
    2026-08-07 — a field shipped through four releases without reaching his
    file). The list's row builder must draw the layout's OWN shape, from the
    three fields `layout_state` already carries."""
    src = LAYOUTS_JS.read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("//"))
    if "gridIconSvg(" not in code:
        raise AssertionError(
            "client/layouts.js draws no shape on its rows. Wire it in "
            "openLayoutPicker's `layouts.forEach`, beside the rename and "
            "aspect buttons:\n"
            "        const shape = document.createElement('button');\n"
            "        shape.type = 'button';\n"
            "        shape.className = 'lay-ratio lay-shape';\n"
            "        shape.innerHTML = gridIconSvg(lay.members, lay.grid, "
            "lay.orient);\n"
            "        keepFocus(shape, () => openMemberPanel(i));\n"
            "    …then pass `shape` to layRow() before `ren`.")
    m = re.search(r"gridIconSvg\(([^)]*)\)", code)
    args = m.group(1) if m else ""
    for field in ("members", "grid", "orient"):
        if f".{field}" not in args:
            raise AssertionError(
                f"layouts.js calls gridIconSvg without the layout's {field!r} "
                f"— got `gridIconSvg({args})`. All three fields are on the "
                "wire already; a drawing keyed by fewer of them is a drawing "
                "that is wrong for some rows.")


def check_the_server_still_sends_the_shape() -> None:
    """The other end of the chain, pinned here so one gate tells the whole
    story: `layout_state` must keep carrying the three fields the drawing is
    keyed by. Losing one silently un-fixes this round."""
    # The frame moved to server/layout_state.py on 2026-08-14 (THE STRUCTURE
    # LAW split: the registry owns the windows, that module owns what the
    # phone is told). This FOLLOWS the code rather than being weakened —
    # whichever file builds the frame, it must carry all three fields.
    reg = REGISTRY.read_text(encoding="utf-8") + FRAME.read_text(encoding="utf-8")
    m = re.search(r'"type": "layout_state"(.*?)\n(?:        |    )\}', reg, re.S)
    if not m:
        raise AssertionError("nothing builds the layout_state frame any more")
    body = m.group(1)
    for field, why in (('"grid"', "which arrangement"),
                       ('"members"', "how many windows are really in it"),
                       ('"orient"', "which column of his sheet it is drawn in")):
        if field not in body:
            raise AssertionError(
                f"layout_state no longer carries {field} — the phone could not "
                f"know {why}")


def check_the_module_stays_pure() -> None:
    """This gate runs the module WHOLE in node — possible only while it
    touches no DOM, no socket, no bridge (the caret.js / view-anchor.js rule).
    It BUILDS markup, which is a string; it must never go near a document."""
    code = "\n".join(ln for ln in MODULE.read_text(encoding="utf-8").splitlines()
                     if not ln.lstrip().startswith(("//", "*", "/*")))
    for banned in ("document", "window.", "send(", "Android", "fetch(",
                   "localStorage"):
        if banned in code:
            raise AssertionError(
                f"client/grid-icons.js reaches for {banned!r} — it is no "
                "longer pure and this gate can no longer run it whole")


def check_nothing_here_says_wide() -> None:
    """ONE NAME PER THING (owner 2026-08-07): a shape is "landscape" or
    "portrait", everywhere. The banned word was the same thing under a second
    name. Checked on the files this round owns, so the ban cannot creep back
    in through the newest module. (Lines that name the ban itself are
    exempt — this docstring would otherwise fail its own check.)"""
    for path in (MODULE, PROJECT / "tests" / "test_grid_icons.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r'\bwide\b', line, re.I) and "banned" not in line.lower():
                raise AssertionError(
                    f"{path.name}:{i} says \"wide\" — the word is banned in "
                    f"favour of portrait/landscape: {line.strip()!r}")


CHECKS = [
    ("the catalogue is HIS SHEET — 6 shapes + solo, 14 with orientations",
     check_the_catalogue_is_his_sheet),
    ("every variant draws its OWN silhouette",
     check_every_catalogue_entry_has_its_own_silhouette),
    ("portrait and landscape never draw one picture",
     check_portrait_and_landscape_differ_for_every_shape),
    ("the cells ARE server/grids.py's partition, in member order",
     check_the_cells_are_the_servers_own_partition),
    ("the cells partition the box — inside it, no overlaps, no holes",
     check_the_cells_partition_the_box_without_overlapping),
    ("only a THREE may change its arrangement",
     check_only_a_three_may_change_its_arrangement),
    ("an unknown key falls back to a safe generic, never throws",
     check_an_unknown_key_falls_back_to_a_safe_generic),
    ("fewer live members than cells draws only what is there",
     check_fewer_live_members_than_cells_draws_only_what_is_there),
    ("one lit cell names the cell it lights",
     check_one_lit_cell_names_the_cell_it_lights),
    ("the page loads the module before grids.js and layouts.js",
     check_the_page_loads_the_module_before_its_users),
    ("grids.js delegates — no second copy of the shapes",
     check_grids_js_delegates_instead_of_keeping_a_second_copy),
    ("the layout LIST draws the shape of every row",
     check_the_layout_list_draws_the_shape_of_every_row),
    ("the server still sends grid + members + orient",
     check_the_server_still_sends_the_shape),
    ("the module stays pure, so this gate can run it whole",
     check_the_module_stays_pure),
    ("one name per thing — no banned second name for landscape",
     check_nothing_here_says_wide),
]


def main() -> int:
    print("\n=== GRID ICON GATE ===")
    if shutil.which("node") is None:
        print("GRID ICON GATE FAILED — node is required (it runs the REAL "
              "client/grid-icons.js geometry) and is not on PATH. Never skip "
              "a gate silently.")
        return 1
    failed = 0
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nGRID ICON GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nGRID ICON GATE PASSED — every row can say which shape it is, and "
          "the drawing is the desk.")
    return 0


def test_grid_icons():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
