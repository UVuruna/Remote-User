"""Gate: the category wheel's circles never touch, and never leave the screen.

TWO OWNER REPORTS OF 2026-08-13, one root each, both in `wheelLayout`.

1. THE RING DID NOT FOLLOW THE SCREEN. With a set open he rotated the desktop
   from portrait to landscape and the wheel slid half off the edge — "a little
   of it left visible". `wheelPoints` returns ABSOLUTE pixels measured against
   the viewport of the moment, and `openWheel` wrote them into each item once;
   nothing recomputed them, so after a rotation every circle still sat around
   where the OLD screen's centre had been. The fix is that the layout is a
   function that can be re-run (`layoutWheel`, client/wheel.js) — and what THIS
   gate can prove about it is the part that is pure: for every screen shape the
   app supports, in either orientation, the layout puts every circle wholly
   inside the screen.

2. THE CIRCLES TOUCHED. "Shrink them a few pixels so a little space is left
   between them — not much, but some." The radius was a flat 118 px that knew
   nothing about how many items it was arranging: neighbouring centres sit
   2*r*sin(pi/n) apart, which at 8 items and 90 px circles is 90.3 px (touching
   exactly) and at TEN — task 181 raised the cap to 10 — is 72.9 px, a 17 px
   OVERLAP. The mini radial had always derived its radius from its own face and
   gap; the wheel never did.

The RULE the fix follows, and the one this gate really pins, is the project's
own ladder rather than the shrink he asked for: **open the ring out until the
gap fits, and only when the screen will not allow that radius do the circles
give up pixels.** A gate that only checked "the circles got smaller" would pass
an implementation that shrinks them on a tablet with room to spare.

Run standalone or from build.py (fail-closed). node runs the pure module whole
— chrome.js is loaded with a tiny DOM shim, the same discipline
tests/test_grid_icons.py and tests/test_loading_settle.py use.

Each check is proven by planting its own defect:
  * WHEEL_GAP = 0                     -> "8 items ... gap -0.3px"
  * a flat `radius = WHEEL_RADIUS`    -> "10 items ... gap -17.1px"
  * drop the room() clamp             -> "a circle leaves the screen"
  * shrink first instead of last      -> "shrank to 70px with room to spare"
"""

import json
import math
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CLIENT = PROJECT / "client"

# Every screen the audits sweep, in BOTH orientations — the rotation is the
# whole point of the first report.
SCREENS = [
    (412, 915, "phone portrait"),
    (915, 412, "phone landscape"),
    (800, 1280, "tablet portrait"),
    (1280, 800, "tablet landscape"),
]
# 1 is a wheel with one set; 10 is task 181's raised cap.
COUNTS = list(range(1, 11))

DRIVER = r"""
const fs = require("fs");
const vm = require("vm");

// chrome.js reads CSS tokens at load for the MINI radial's own geometry and
// appends its element; a shim is enough — nothing below touches the DOM.
const el = () => ({
  style: { setProperty() {} }, classList: { add() {}, remove() {}, toggle() {} },
  appendChild() {}, addEventListener() {}, querySelectorAll: () => [],
  hidden: true, innerHTML: "",
});
const sandbox = {
  document: {
    createElement: el, getElementById: el, body: el(),
    documentElement: el(), addEventListener() {},
  },
  getComputedStyle: () => ({ getPropertyValue: () => "" }),
  window: { addEventListener() {}, innerWidth: 412, innerHeight: 915 },
  console,
  // chrome.js wires the real page at load (keepFocus from controls.js, the
  // auto-hide tick, the toast). Stubbed rather than loading controls.js too:
  // this gate is about the ring's ARITHMETIC, and pulling in the whole page
  // would make a failure here ambiguous between the two files.
  keepFocus() {}, svg: () => "", showToast() {}, setTimeout() {},
  setInterval() {}, clearTimeout() {}, clearInterval() {},
  requestAnimationFrame() {}, performance: { now: () => 0 },
  wheelCats: () => [], allCats: () => [], placedCat: () => null,
};
sandbox.window.document = sandbox.document;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), sandbox, {filename: "chrome.js"});

const cases = JSON.parse(process.argv[3]);
const out = cases.map((c) => {
  const r = sandbox.wheelLayout(c.count, {width: c.width, height: c.height}, c.size);
  // `size` stays the size ASKED FOR; `face` is what the ladder settled on.
  // Spreading the case last would lose the request, and a check comparing the
  // result with itself can never fail — which is what this line first did.
  return {...c, radius: r.radius, face: r.size, points: r.points};
});
process.stdout.write(JSON.stringify(out));
"""


def _run(cases: list[dict]) -> list[dict]:
    driver = PROJECT / "tests" / "_tmp_wheel_driver.js"
    driver.write_text(DRIVER, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["node", str(driver), str(CLIENT / "chrome.js"), json.dumps(cases)],
            capture_output=True, text=True)
    finally:
        driver.unlink(missing_ok=True)
    if proc.returncode != 0:
        raise RuntimeError(f"node failed: {proc.stderr.strip()[:400]}")
    return json.loads(proc.stdout)


def _all_cases(size: int = 86) -> list[dict]:
    return [{"count": n, "width": w, "height": h, "label": label, "size": size}
            for n in COUNTS for (w, h, label) in SCREENS]


def check_no_two_circles_ever_touch(problems: list[str], results) -> None:
    for r in results:
        n = r["count"]
        if n < 2:
            continue
        gap = 2 * r["radius"] * math.sin(math.pi / n) - r["face"]
        if gap < 0:
            problems.append(
                f"{n} items @ {r['label']}: gap {gap:.1f}px — the circles "
                f"overlap (radius {r['radius']:.1f}, face {r['face']:.1f})")


def check_no_circle_ever_leaves_the_screen(problems: list[str], results) -> None:
    """The rotation report, in the only form a pure function can carry it."""
    for r in results:
        half = r["face"] / 2
        for i, p in enumerate(r["points"]):
            if (p["x"] - half < 0 or p["y"] - half < 0
                    or p["x"] + half > r["width"] or p["y"] + half > r["height"]):
                problems.append(
                    f"{r['count']} items @ {r['label']}: a circle leaves the "
                    f"screen — item {i} centre ({p['x']:.0f},{p['y']:.0f}), "
                    f"face {r['face']:.0f}px in {r['width']}x{r['height']}")
                break


def check_the_ring_is_centred(problems: list[str], results) -> None:
    """A rotation that is handled puts the ring back in the MIDDLE. This is
    what the bug looked like from the outside: the centre stayed where the old
    screen's centre was."""
    for r in results:
        if r["count"] < 2:
            continue
        cx = sum(p["x"] for p in r["points"]) / len(r["points"])
        cy = sum(p["y"] for p in r["points"]) / len(r["points"])
        if abs(cx - r["width"] / 2) > 1 or abs(cy - r["height"] / 2) > 1:
            problems.append(
                f"{r['count']} items @ {r['label']}: the ring's centre is "
                f"({cx:.0f},{cy:.0f}), the screen's is "
                f"({r['width'] / 2:.0f},{r['height'] / 2:.0f})")


def check_the_shrink_is_the_last_resort(problems: list[str], results) -> None:
    """THE LADDER, and the reason this check exists at all: he asked for
    smaller circles, and an implementation that simply made them smaller would
    satisfy the request while breaking the rule. Circles may only give up
    pixels when the RADIUS cannot grow any further — never while the screen
    still has room."""
    for r in results:
        asked = r["size"]
        got = r["face"]
        n = r["count"]
        if n < 2:
            continue
        # Would the asked-for face have fitted at some radius the screen allows?
        room = min(r["width"], r["height"]) / 2 - asked / 2 - 8
        needed = (asked + 8) / (2 * math.sin(math.pi / n))
        if got < asked - 0.01 and needed <= room + 0.01:
            problems.append(
                f"{n} items @ {r['label']}: shrank to {got:.0f}px with room to "
                f"spare (needed radius {needed:.0f}, screen allows {room:.0f})")


def check_a_screen_too_small_shrinks_rather_than_overlapping(problems) -> None:
    """And the other end of the same ladder: when the room really is gone, the
    circles MUST give way — an implementation that only ever grew the radius
    would push them off the edge instead."""
    tiny = [{"count": 10, "width": 320, "height": 480, "label": "tiny", "size": 86}]
    r = _run(tiny)[0]
    gap = 2 * r["radius"] * math.sin(math.pi / 10) - r["face"]
    if gap < 0:
        problems.append(f"on a 320x480 screen ten circles still overlap by {-gap:.0f}px")
    if r["face"] >= 86:
        problems.append(
            f"on a 320x480 screen the face stayed {r['face']:.0f}px — nothing "
            f"gave way, so either the ring or the circles must be off-screen")
    half = r["face"] / 2
    if any(p["x"] - half < 0 or p["y"] - half < 0 for p in r["points"]):
        problems.append("on a 320x480 screen a circle still leaves the edge")


def check_the_page_really_uses_the_returned_size(problems: list[str]) -> None:
    """A pure function nobody calls correctly is a feature that does not exist
    (the actions.json lesson of 2026-08-07). `wheelLayout` returns the face the
    ladder settled on; writing `wheelItemSize` instead would put an 86px circle
    on a 70px plan."""
    for name in ("wheel.js",):
        src = (CLIENT / name).read_text(encoding="utf-8")
        if "wheelLayout(" not in src:
            problems.append(f"client/{name} never calls wheelLayout")
            continue
        if "--wheel-item-size" not in src:
            problems.append(f"client/{name} never writes --wheel-item-size")
        for caller in ("openWheel", "layoutWheel"):
            if caller not in src:
                problems.append(f"client/{name} has no {caller}")
    chrome = (CLIENT / "chrome.js").read_text(encoding="utf-8")
    if "function wheelLayout" not in chrome:
        problems.append("client/chrome.js no longer defines wheelLayout")
    wheel = (CLIENT / "wheel.js").read_text(encoding="utf-8")
    for event in ('"resize"', '"orientationchange"'):
        if event not in chrome and event not in wheel:
            problems.append(
                f"nothing listens for {event} — an open ring would not follow "
                f"a rotation, which is the bug this gate is named for")


def main() -> int:
    print("=== WHEEL GEOMETRY GATE ===")
    try:
        results = _run(_all_cases())
    except Exception as e:  # noqa: BLE001
        print(f"  FAIL  could not run the pure module: {e}")
        return 1
    checks = [
        ("no two circles ever touch", check_no_two_circles_ever_touch),
        ("no circle ever leaves the screen", check_no_circle_ever_leaves_the_screen),
        ("the ring is centred on the screen it is drawn for", check_the_ring_is_centred),
        ("the shrink is the last resort, never the first move",
         check_the_shrink_is_the_last_resort),
    ]
    failed = 0
    for name, fn in checks:
        problems: list[str] = []
        try:
            fn(problems, results)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{type(e).__name__}: {e}")
        print(f"  {'PASS' if not problems else 'FAIL'}  {name}")
        for problem in problems[:6]:
            print(f"        {problem}")
        failed += bool(problems)
    for name, fn in (("a screen too small shrinks rather than overlapping",
                      check_a_screen_too_small_shrinks_rather_than_overlapping),
                     ("the page really uses the size the ladder settled on",
                      check_the_page_really_uses_the_returned_size)):
        problems = []
        try:
            fn(problems)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{type(e).__name__}: {e}")
        print(f"  {'PASS' if not problems else 'FAIL'}  {name}")
        for problem in problems[:6]:
            print(f"        {problem}")
        failed += bool(problems)
    print()
    if failed:
        print(f"WHEEL GEOMETRY GATE FAILED — {failed} check(s).")
        return 1
    print(f"WHEEL GEOMETRY GATE PASSED — {len(results)} layouts across "
          f"{len(COUNTS)} counts and {len(SCREENS)} screens: every circle whole "
          f"on screen, none touching, and the shrink kept for last.")
    return 0


def test_wheel_geometry():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
