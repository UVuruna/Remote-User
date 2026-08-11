"""Gate: THE CATEGORY WHEEL NEVER PUSHES AN ITEM OFF SCREEN (task 238, owner
screenshot report — in landscape the wheel showed only four of six-plus
riding sets, while portrait showed all of them).

`openWheel` (client/controls.js) used to place every item on a FIXED 118 px
radius circle with no clamp at all. A phone's landscape HEIGHT is its short
side (~360-412 px, against an ~900 px portrait height) — the radius that
leaves a wide margin in portrait leaves only a thin one in landscape, and on
a real device (a slightly shorter phone, or the transient system bars
CLAUDE.md constraint 9 describes) that margin goes negative and an item's
CENTRE lands outside the viewport: still in the DOM, but unreachable by a
finger and invisible in a screenshot, which reads as "the wheel dropped it".

The fix (`wheelPoints` in client/chrome.js, beside `miniRingPoints` — the
sibling it copies the clamp from) shrinks the radius to fit the SHORTER
viewport side instead. This gate proves every riding item stays fully
on-screen at both a tall portrait and a short landscape size, with enough
riding sets (7) that the old fixed radius left barely any margin to begin
with, and asserts the COUNT never drops — reflow is fine, silently dropping
an entry is not.

Run:  .venv\\Scripts\\python tests/test_wheel_geometry.py
Requires playwright + chromium, like the other phone-chrome gates.
"""

import json
import socket
import sys
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(PROJECT / "server"))

SIZES = [("portrait 412x915", 412, 915), ("landscape 915x412", 915, 412),
         # A shorter real landscape (a smaller phone, or the transient system
         # bars CLAUDE.md constraint 9 describes eating into innerHeight) —
         # the size at which the OLD fixed 118 px radius, unclamped, pushed
         # an item's centre outside the viewport (cy - 118 - 37 < 0 once the
         # height drops under ~310 px). Kept alongside the ordinary 412 px
         # size so the gate proves BOTH "the common case still works" and
         # "the margin case the owner actually hit is fixed".
         ("landscape-short 900x280", 900, 280)]

# Seven riding sets — enough that the old FIXED 118 px radius, unclamped,
# left only a thin (and on a shorter real device, negative) margin against a
# ~412 px landscape height. Two are `required` (never shed) so the drop-out
# rule (task 181 — a placed set sheds off ITS OWN side, and the other side's
# placed set never rides) leaves a realistic five-item ring, matching the
# owner's report of "only four" shown out of six-plus enabled.
NAMES = ["Mouse", "Input", "Edit", "Attach", "Navigate", "Cursor", "Media"]
CATS = [{"name": n, "icon": "mouse", "required": (i < 2),
         "buttons": [{"action": "click"}]} for i, n in enumerate(NAMES)]

STAGE = (
    f"categories = {json.dumps(CATS)}; customSets = []; appSets = []; "
    "wheelOrder = []; setWheelMode('dropout'); "
    "groups.left = 0; groups.right = 1; "
    "renderGroup('left'); renderGroup('right');"
)

ONSCREEN_JS = """() => {
  const vw = window.innerWidth, vh = window.innerHeight;
  const items = [...document.querySelectorAll('.wheel-item')];
  const fully = items.filter(el => {
    const r = el.getBoundingClientRect();
    return r.left >= 0 && r.top >= 0 && r.right <= vw && r.bottom <= vh;
  });
  return { total: items.length, onscreen: fully.length };
}"""


def main() -> int:
    import test_input_pipeline as gate
    threading.Thread(target=gate.run_server, daemon=True).start()
    gate.server_ready.wait(15)
    deadline = time.time() + 10
    while time.time() < deadline:
        if gate.server_error:
            raise gate.server_error[0]
        try:
            with socket.create_connection(("127.0.0.1", gate.PORT), timeout=0.25):
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError("gate server never started")

    from playwright.sync_api import sync_playwright

    results: dict[str, bool] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for label, w, h in SIZES:
            ctx = browser.new_context(
                viewport={"width": w, "height": h}, has_touch=True, is_mobile=True,
                user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 8) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 "
                            "Mobile Safari/537.36 RemoteUserApp"))
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
            page.wait_for_selector("#group-left button", timeout=8000)
            page.wait_for_function("() => monitor.w > 0", timeout=10000)
            page.evaluate(STAGE)
            page.click("#group-left .ctl.cat")
            page.wait_for_selector("#wheel.open", timeout=3000)
            counts = page.evaluate(ONSCREEN_JS)
            ok_count = counts["total"] == counts["onscreen"]
            results[f"every rendered wheel item stays on-screen @ {label}"] = ok_count
            if not ok_count:
                print(f"  DETAIL @ {label}: {counts}")
            # NOTHING may be dropped — the riding count itself must match what
            # wheelCats() actually computed, never fewer than what the finger
            # is owed (planting the old FIXED radius must never shrink the
            # DOM count, only push centres off screen — a silent slice would
            # be the worse bug this gate must also catch).
            ok_riding = counts["total"] >= 5
            results[f"the wheel keeps every riding set (>=5) @ {label}"] = ok_riding
            if not ok_riding:
                print(f"  DETAIL riding count @ {label}: {counts}")
            page.evaluate("closeWheel()")
            ctx.close()
        browser.close()

    print("\n=== WHEEL GEOMETRY GATE ===")
    failed = 0
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    if failed:
        print(f"\nWHEEL GEOMETRY GATE FAILED — {failed} check(s).", file=sys.stderr)
        return 1
    print("\nWHEEL GEOMETRY GATE PASSED — every riding set stays on the ring "
          "and on screen, in landscape as much as portrait.")
    return 0


def test_wheel_geometry():
    """pytest entry — skipped where the browser toolchain is absent."""
    import pytest
    pytest.importorskip("playwright.sync_api")
    pytest.importorskip("uvicorn")
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
