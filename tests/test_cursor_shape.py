"""THE CURSOR SHOWS WHAT THE PIXEL UNDER IT DOES — the shape gate.

Owner request 2026-08-09 (task 142). The phone draws the PC pointer itself
(DXGI capture never contains it) and drew ONE fixed arrow, so from the tablet
a draggable window edge, a text box, a link and plain background all looked
identical. His words are the acceptance test:
# lang-ok: owner quote
"prikazi mi stvarni kursor kako izgleda, a ne da stalno bude strelica, tako da znam da tu mogu da kliknem i da promenim dimenzije prozora."

Three things have to be true, and a gate that proves only one of them is the
class of gate this project has been burned by:

1. **The PC names the right cursor.** `server/cursor_shape.py` matches the
   live `HCURSOR` against the system cursors it loaded once. Driven here with
   FAKED HANDLES through the REAL resolver — the resolver itself is never
   stubbed, or this would prove a mock to itself. What cannot be proven
   without a live desk is stated plainly at the bottom of this file.
2. **The name reaches the phone the way the protocol says.** The real
   `web._send_cursor` loop is driven over a fake socket: an OPTIONAL field on
   the EXISTING `cursor` message, sent when the NAME changes even though the
   pointer has not moved (hovering onto an edge is exactly that), and never
   more often than it already sent.
3. **The page draws a different, correctly ANCHORED shape per name.** The
   geometry is pure (`client/cursor-shapes.js`, the caret.js/view-anchor.js
   pattern) and is run WHOLE in node: every name a distinct silhouette, the
   hotspot landing on the commanded point under each shape's own rule, and
   anything unknown or missing drawing the EXACT arrow this page has always
   drawn — pinned below as a literal, because "unchanged" is a claim about
   yesterday's pixels and only a literal can hold it.

Run:  .venv\\Scripts\\python tests/test_cursor_shape.py
Requires: node on PATH — a HARD requirement (fail-closed in setup/build.py,
the test_view_anchor.py precedent). Never skip it silently.
"""

import asyncio
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
MODULE = PROJECT / "client" / "cursor-shapes.js"
RENDER = PROJECT / "client" / "render.js"
CONNECTION = PROJECT / "client" / "connection.js"
INDEX = PROJECT / "client" / "index.html"

sys.path.insert(0, str(PROJECT / "server"))

import cursor_shape  # noqa: E402
import web  # noqa: E402

# The arrow as it was drawn before this feature existed, held as a LITERAL.
# Every unknown name must still produce exactly this.
LEGACY_ARROW = [
    [0, 0], [0, 16.5], [3.6, 13.3], [6, 19], [8.7, 17.9], [6.3, 12.4],
    [11.2, 11.9],
]

# Which point of each shape is its hotspot — this gate's OWN expectation,
# written here rather than read from the module, so the module cannot mark
# its own homework. "tip" = the commanded point is a real vertex and the
# single highest point of the shape (an arrow points with its tip);
# "center" = the shape's bounding box is centred on it (Windows' own rule for
# the resize/move/wait/I-beam family, and what makes a resize arrow read as
# "this edge, right here").
TIP_ANCHORED = {"arrow", "hand", "up-arrow", "app-starting", "help"}
CENTER_ANCHORED = {"ibeam", "size-we", "size-ns", "size-nwse", "size-nesw",
                   "move", "wait", "cross", "no"}

# The system cursors the owner's request names, by their winuser.h ids. Held
# here independently of the server table: a cursor silently dropped from
# server/cursor_shape.py must fail, not pass by agreeing with itself.
REQUIRED_IDC = {
    32512: "arrow", 32513: "ibeam", 32514: "wait", 32515: "cross",
    32642: "size-nwse", 32643: "size-nesw", 32644: "size-we",
    32645: "size-ns", 32646: "move", 32648: "no", 32649: "hand",
    32650: "app-starting", 32651: "help",
}


# ═══════════════════════ 1. THE PC NAMES THE CURSOR ═══════════════════════
class FakeCursorTable:
    """Windows as far as the resolver is concerned: every system cursor has a
    handle, and the handles CHANGE when the user switches cursor scheme (they
    really do — that is why the resolver may reload at all)."""

    def __init__(self, base: int = 0x7FF000) -> None:
        self.base = base
        self.calls: list[int] = []

    def handle(self, idc: int) -> int:
        return self.base + idc

    def load(self, idc: int) -> int:
        self.calls.append(idc)
        return self.handle(idc)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def check_every_system_cursor_resolves_to_its_name() -> None:
    table = FakeCursorTable()
    namer = cursor_shape.CursorNamer(load=table.load, clock=FakeClock())
    for idc, name in cursor_shape.SYSTEM_CURSORS:
        got = namer.name_for(table.handle(idc))
        if got != name:
            raise AssertionError(
                f"IDC {idc} resolved to {got!r}, expected {name!r}")


def check_the_owners_whole_list_is_covered() -> None:
    table = dict(cursor_shape.SYSTEM_CURSORS)
    for idc, name in REQUIRED_IDC.items():
        if table.get(idc) != name:
            raise AssertionError(
                f"IDC {idc} is {table.get(idc)!r} in server/cursor_shape.py, "
                f"expected {name!r} — the owner's list lost a cursor")


def check_an_unknown_handle_is_custom_never_a_guess() -> None:
    """An application's own cursor matches nothing. The honest answer is
    `custom` (the phone then draws the plain arrow); a near-miss would tell
    him an edge is grabbable when it is not."""
    table = FakeCursorTable()
    namer = cursor_shape.CursorNamer(load=table.load, clock=FakeClock())
    for handle in (0x123456, 1, 0xFFFFFFFF):
        got = namer.name_for(handle)
        if got != cursor_shape.CUSTOM:
            raise AssertionError(
                f"an unknown handle {handle:#x} resolved to {got!r} — a shape "
                "we do not know must never be dressed up as one we do")
    if namer.name_for(None) != cursor_shape.CUSTOM:
        raise AssertionError("a null handle did not fall back to custom")


def check_the_table_is_loaded_once_not_per_frame() -> None:
    """This runs inside the ~30 Hz cursor loop. A LoadCursorW sweep per frame
    would be a syscall storm for an answer that changes only when the user
    changes their cursor scheme."""
    table = FakeCursorTable()
    clock = FakeClock()
    namer = cursor_shape.CursorNamer(load=table.load, clock=clock)
    for _ in range(200):
        namer.name_for(table.handle(cursor_shape.IDC_SIZEWE))
        clock.now += 1.0  # even a minute of hovering may not reload
    if len(table.calls) != len(cursor_shape.SYSTEM_CURSORS):
        raise AssertionError(
            f"the system table was loaded {len(table.calls)} times for "
            f"{len(cursor_shape.SYSTEM_CURSORS)} cursors — it must be "
            "resolved ONCE and cached")


def check_a_changed_cursor_scheme_heals_itself() -> None:
    """Windows hands out NEW handles for every system cursor when the scheme
    changes. Cached forever, the table would call every cursor on the machine
    `custom` for the rest of the session — so an UNMATCHED handle may reload,
    at most once per RELOAD_SECONDS."""
    table = FakeCursorTable()
    clock = FakeClock()
    namer = cursor_shape.CursorNamer(load=table.load, clock=clock)
    namer.name_for(table.handle(cursor_shape.IDC_ARROW))
    sweep = len(table.calls)
    table.base = 0x900000  # the user picked another cursor style
    if namer.name_for(table.handle(cursor_shape.IDC_IBEAM)) != cursor_shape.CUSTOM:
        raise AssertionError("a stale handle was matched to a name")
    if len(table.calls) != sweep:
        raise AssertionError(
            "an unmatched handle reloaded the table immediately — that is the "
            "per-frame syscall storm the cache exists to avoid")
    clock.now += cursor_shape.RELOAD_SECONDS
    if namer.name_for(table.handle(cursor_shape.IDC_IBEAM)) != "ibeam":
        raise AssertionError(
            "the table never reloaded — a cursor-scheme change would make "
            "every cursor on the PC report as 'custom' forever")


# ═══════════════════ 2. THE NAME REACHES THE PHONE ═══════════════════
class FakeWs:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))


class ScriptedInjector:
    """Plays a scripted (position, shape) tape and then ends the loop the way
    a dead socket does."""

    def __init__(self, script) -> None:
        self._script = list(script)
        self.shape = None

    def take_input_alarm(self) -> bool:
        return False

    def cursor_norm(self):
        if not self._script:
            raise RuntimeError("tape finished")  # _send_cursor's normal exit
        pos, self.shape = self._script.pop(0)
        return pos


def _run_cursor_loop(script) -> list[dict]:
    injector = ScriptedInjector(script)
    ws = FakeWs()
    original = cursor_shape.current_cursor_name
    cursor_shape.current_cursor_name = lambda: injector.shape
    try:
        asyncio.run(web._send_cursor(ws, injector))
    finally:
        cursor_shape.current_cursor_name = original
    return ws.sent


P1 = (0.25, 0.5)
P2 = (0.75, 0.5)


def check_the_shape_rides_the_existing_cursor_message() -> None:
    sent = _run_cursor_loop([(P1, "arrow")])
    if len(sent) != 1:
        raise AssertionError(f"expected one frame, got {sent}")
    frame = sent[0]
    if frame.get("type") != "cursor":
        raise AssertionError(
            f"the shape arrived as {frame.get('type')!r} — it must ride the "
            "EXISTING cursor message, never a new message type")
    if frame.get("shape") != "arrow":
        raise AssertionError(f"no shape on the cursor frame: {frame}")
    if frame["x"] != P1[0] or frame["y"] != P1[1]:
        raise AssertionError(f"the position stopped being sent: {frame}")


def check_a_shape_change_alone_reaches_the_phone() -> None:
    """Hovering onto a window edge moves nothing — and is the entire feature."""
    sent = _run_cursor_loop([(P1, "arrow"), (P1, "size-we")])
    shapes = [f.get("shape") for f in sent]
    if shapes != ["arrow", "size-we"]:
        raise AssertionError(
            f"a shape change without movement was swallowed: {shapes} — the "
            "owner would hover the edge and still see an arrow")


def check_nothing_unchanged_is_ever_resent() -> None:
    """The cadence must stay exactly what it was: on change, nothing else."""
    sent = _run_cursor_loop([
        (P1, "arrow"), (P1, "arrow"), (P1, "arrow"),
        (P1, "ibeam"), (P1, "ibeam"),
        (P2, "ibeam"), (P2, "ibeam"),
    ])
    got = [(f["x"], f.get("shape")) for f in sent]
    want = [(P1[0], "arrow"), (P1[0], "ibeam"), (P2[0], "ibeam")]
    if got != want:
        raise AssertionError(
            f"the cursor stream changed cadence: {got}, expected {want}")


def check_an_unreadable_shape_leaves_the_field_off_the_wire() -> None:
    """A secure desktop / lock screen: the PC cannot read the cursor. The
    field is OPTIONAL, so it is simply absent — an older page ignores it and
    a newer one falls back to the arrow. Neither is ever fed a guess."""
    sent = _run_cursor_loop([(P1, "arrow"), (P2, None)])
    if len(sent) != 2:
        raise AssertionError(f"expected two frames, got {sent}")
    if "shape" in sent[1]:
        raise AssertionError(
            f"an unreadable cursor still put a shape on the wire: {sent[1]}")
    if sent[1]["x"] != P2[0]:
        raise AssertionError("the position stopped flowing without a shape")


# ═══════════════════ 3. THE PAGE DRAWS THE NAMED SHAPE ═══════════════════
def node_shapes(names: list, x: float = 0, y: float = 0) -> list:
    """cursorPolys() for each name, evaluated in ONE node process by the REAL
    client module. `None` in `names` means "no name at all" (undefined)."""
    if not shutil.which("node"):
        raise AssertionError(
            "node is required for the cursor shape gate (it runs the REAL "
            "client/cursor-shapes.js geometry) — install Node.js. Never skip "
            "a gate silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_cursor_gate_"))
    script = work / "run.js"
    script.write_text(
        f"const {{ cursorPolys }} = require({json.dumps(str(MODULE))});\n"
        f"const names = {json.dumps(names)};\n"
        f"console.log(JSON.stringify(names.map(n => cursorPolys("
        f"n === null ? undefined : n, {x}, {y}))));\n",
        encoding="utf-8")
    try:
        out = subprocess.run([shutil.which("node"), str(script)],
                             capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def node_shape_names() -> list:
    if not shutil.which("node"):
        raise AssertionError("node is required for the cursor shape gate")
    work = Path(tempfile.mkdtemp(prefix="ru_cursor_gate_"))
    script = work / "names.js"
    script.write_text(
        f"const m = require({json.dumps(str(MODULE))});\n"
        "console.log(JSON.stringify(Object.keys(m.CURSOR_SHAPES)));\n",
        encoding="utf-8")
    try:
        out = subprocess.run([shutil.which("node"), str(script)],
                             capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, f"node failed: {out.stderr.strip()}"
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _bbox(polys):
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def check_an_unknown_or_missing_name_draws_the_old_arrow() -> None:
    """The fallback is the promise that nothing regressed: a page that gets a
    name it has never heard of — `custom`, or a shape from a newer server —
    looks EXACTLY like the page did before this feature existed."""
    got = node_shapes([None, "custom", "no-such-cursor", "", "arrow"])
    for label, polys in zip(("missing", "custom", "unknown", "empty", "arrow"),
                            got):
        if polys != [LEGACY_ARROW]:
            raise AssertionError(
                f"a {label} cursor name did not draw the original arrow: "
                f"{polys}")


def check_every_name_draws_its_own_shape() -> None:
    names = node_shape_names()
    drawn = node_shapes(names)
    seen: dict[str, str] = {}
    for name, polys in zip(names, drawn):
        key = json.dumps(polys, sort_keys=True)
        if key in seen:
            raise AssertionError(
                f"{name!r} draws exactly what {seen[key]!r} draws — at a "
                "glance on a shrunken 4K stream they would be one shape")
        seen[key] = name
    if len(names) < 10:
        raise AssertionError(
            f"only {len(names)} shapes are drawn — the owner's minimum is "
            "arrow, ibeam, hand, the four resize arrows, move and wait")


def check_the_hotspot_lands_on_the_commanded_point() -> None:
    """The drawn shape must point at the same pixel the old arrow pointed at.
    Getting this wrong is invisible on a still screenshot and lethal in the
    hand: he would aim at an edge and grab 10 px away from it."""
    names = node_shape_names()
    x, y = 137.0, 411.0
    for name, polys in zip(names, node_shapes(names, x, y)):
        pts = [tuple(p) for poly in polys for p in poly]
        if name in TIP_ANCHORED:
            if (x, y) not in pts:
                raise AssertionError(
                    f"{name!r}: the commanded point {(x, y)} is not even a "
                    "vertex of the drawn shape — its tip points elsewhere")
            highest = min(p[1] for p in pts)
            if abs(highest - y) > 1e-6:
                raise AssertionError(
                    f"{name!r}: the tip is not the topmost point "
                    f"(top={highest}, commanded y={y})")
        elif name in CENTER_ANCHORED:
            x0, y0, x1, y1 = _bbox(polys)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if abs(cx - x) > 0.6 or abs(cy - y) > 0.6:
                raise AssertionError(
                    f"{name!r}: centred on {(cx, cy)}, commanded {(x, y)} — "
                    "a resize cursor that is not centred on the edge points "
                    "at the wrong pixel")
        else:
            raise AssertionError(
                f"{name!r} is drawn but this gate does not know where its "
                "hotspot belongs — add it to TIP_ANCHORED or CENTER_ANCHORED "
                "in the same commit that draws it")


def check_the_shape_only_translates() -> None:
    """Whatever the commanded point, the shape itself is identical — the only
    thing (x, y) may do is move it."""
    names = node_shape_names()
    at_origin = node_shapes(names)
    moved = node_shapes(names, 137.0, 411.0)
    for name, a, b in zip(names, at_origin, moved):
        want = [[[px + 137.0, py + 411.0] for px, py in poly] for poly in a]
        if b != want:
            raise AssertionError(
                f"{name!r} is not a pure translation of itself — the geometry "
                "changes with the point it is drawn at")


def check_every_shape_is_legible_at_a_glance() -> None:
    """Nothing microscopic, nothing that swallows the screen: he reads these
    on a tablet showing a whole 4K desktop."""
    names = node_shape_names()
    for name, polys in zip(names, node_shapes(names)):
        x0, y0, x1, y1 = _bbox(polys)
        w, h = x1 - x0, y1 - y0
        if max(w, h) < 12 or max(w, h) > 32:
            raise AssertionError(
                f"{name!r} is {w}x{h} CSS px — outside the readable band")
        if min(w, h) < 5:
            raise AssertionError(f"{name!r} is {w}x{h} CSS px — too thin to see")


# ═══════════════════════ the wiring, both ends ═══════════════════════
def check_the_page_actually_draws_the_named_shape() -> None:
    """A pure module nobody calls is a feature that does not exist (the
    actions.json lesson, 2026-08-07)."""
    src = RENDER.read_text(encoding="utf-8")
    m = re.search(r"function drawCursor\(D\)\s*\{(.*?)\n\}", src, re.S)
    if not m:
        raise AssertionError("drawCursor() left client/render.js")
    body = m.group(1)
    if "cursorPolys(" not in body:
        raise AssertionError(
            "drawCursor no longer calls cursorPolys — the page draws one "
            "fixed shape again, which is the whole bug of task 142")
    if "cursorShapeName" not in body:
        raise AssertionError(
            "drawCursor does not read cursorShapeName — the shape would be a "
            "constant, not the cursor the PC is showing")
    # The legibility treatment is inherited by every new shape, not re-decided
    # per shape: white body, black outline, soft shadow — what keeps the
    # pointer visible over a white document AND a dark editor.
    for token in ('fillStyle = "#fff"', 'strokeStyle = "#000"', "shadowColor"):
        if token not in body:
            raise AssertionError(
                f"drawCursor lost {token!r} — the cursor stops being legible "
                "over one of the two backgrounds")
    if re.search(r"const CURSOR_PATH\b", src):
        raise AssertionError(
            "render.js still carries its own hardcoded cursor path — two "
            "copies of the arrow is exactly how one of them goes stale")


def check_the_socket_hands_the_name_over() -> None:
    src = CONNECTION.read_text(encoding="utf-8")
    m = re.search(r'msg\.type === "cursor"\)\s*\{(.*?)\}\s*else', src, re.S)
    if not m:
        raise AssertionError("the cursor message handler left connection.js")
    body = m.group(1)
    if "msg.shape" not in body or "cursorShapeName" not in body:
        raise AssertionError(
            "the cursor handler does not carry msg.shape into cursorShapeName "
            "— the server would name the shape and the page would ignore it")


def check_the_page_loads_the_module_before_render() -> None:
    html = INDEX.read_text(encoding="utf-8")
    shapes = html.find("/static/cursor-shapes.js")
    render = html.find("/static/render.js")
    if shapes == -1:
        raise AssertionError("index.html never loads cursor-shapes.js")
    if not -1 < shapes < render:
        raise AssertionError(
            "cursor-shapes.js must load BEFORE render.js — drawCursor calls "
            "into it")


def check_the_module_stays_pure() -> None:
    """This gate runs the module WHOLE in node — possible only while it
    touches no DOM, no canvas, no socket (the caret.js rule)."""
    code = "\n".join(ln for ln in MODULE.read_text(encoding="utf-8").splitlines()
                     if not ln.lstrip().startswith(("//", "*", "/*")))
    for banned in ("document", "window.", "canvas", "ctx.", "send(", "Android",
                   "fetch("):
        if banned in code:
            raise AssertionError(
                f"client/cursor-shapes.js reaches for {banned!r} — it is no "
                "longer pure and this gate can no longer prove it")


def check_the_two_name_tables_agree() -> None:
    """The name is the whole protocol surface of this feature. A name the PC
    can send with no shape behind it is a silent fallback to the arrow; a
    shape keyed by a name the PC never sends is dead code that looks alive."""
    server_names = {name for _, name in cursor_shape.SYSTEM_CURSORS}
    drawn = set(node_shape_names())
    dead = drawn - server_names
    if dead:
        raise AssertionError(
            f"the page draws {sorted(dead)} but the PC can never send those "
            "names — dead shapes that look like a working feature")
    undrawn = server_names - drawn
    if undrawn:
        raise AssertionError(
            f"the PC can send {sorted(undrawn)} and the page has no shape for "
            "it — it would silently draw an arrow for a cursor we DO know")
    if cursor_shape.CUSTOM in drawn:
        raise AssertionError(
            "'custom' has a drawn shape — an application's own cursor must "
            "fall back to the plain arrow, never to an invented silhouette")


CHECKS = [
    ("every system cursor resolves to its name",
     check_every_system_cursor_resolves_to_its_name),
    ("the owner's whole list is covered",
     check_the_owners_whole_list_is_covered),
    ("an unknown handle is 'custom', never a guess",
     check_an_unknown_handle_is_custom_never_a_guess),
    ("the system table is loaded once, not per frame",
     check_the_table_is_loaded_once_not_per_frame),
    ("a changed cursor scheme heals itself",
     check_a_changed_cursor_scheme_heals_itself),
    ("the shape rides the EXISTING cursor message",
     check_the_shape_rides_the_existing_cursor_message),
    ("a shape change alone reaches the phone (hovering an edge)",
     check_a_shape_change_alone_reaches_the_phone),
    ("nothing unchanged is ever resent (the cadence is unchanged)",
     check_nothing_unchanged_is_ever_resent),
    ("an unreadable shape leaves the field off the wire",
     check_an_unreadable_shape_leaves_the_field_off_the_wire),
    ("an unknown or missing name draws the ORIGINAL arrow",
     check_an_unknown_or_missing_name_draws_the_old_arrow),
    ("every name draws its own shape",
     check_every_name_draws_its_own_shape),
    ("the hotspot lands on the commanded point, per shape",
     check_the_hotspot_lands_on_the_commanded_point),
    ("the point only translates the shape, never changes it",
     check_the_shape_only_translates),
    ("every shape is legible at a glance",
     check_every_shape_is_legible_at_a_glance),
    ("the page actually draws the named shape",
     check_the_page_actually_draws_the_named_shape),
    ("the socket hands the name over",
     check_the_socket_hands_the_name_over),
    ("the page loads the module before render.js",
     check_the_page_loads_the_module_before_render),
    ("the module stays pure, so this gate can run it whole",
     check_the_module_stays_pure),
    ("the PC's names and the page's shapes are the same set",
     check_the_two_name_tables_agree),
]


def main() -> int:
    print("\n=== CURSOR SHAPE GATE ===")
    if shutil.which("node") is None:
        print("CURSOR SHAPE GATE FAILED — node is required (it runs the REAL "
              "client/cursor-shapes.js geometry) and is not on PATH. Never "
              "skip a gate silently.")
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
        print(f"\nCURSOR SHAPE GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nCURSOR SHAPE GATE PASSED — the phone draws the cursor the PC is "
          "really showing, pointing at the pixel it names.")
    return 0


def test_cursor_shape():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
