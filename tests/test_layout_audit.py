"""Layout audit for the GUI surfaces this project ships on the PHONE — the
overlay panels (Sets picker, Quality panel, Aspect panel + Move handle).
Proof source for .claude/layout-proof.md (THE SPACE & LEGIBILITY LAW,
rules/GUI.md): the REAL page is opened in a REAL headless Chromium at phone
sizes, each panel is opened, and geometry is checked — nothing clipped, no
horizontal overflow anywhere, every panel card fully inside the viewport.

Also audits the server-side region placement math (`_fit_rect` with the
2026-08-05 `pos` fraction): the placed rect must stay inside its box for
every position, or the phone would frame pixels outside the monitor.

Run:  .venv\\Scripts\\python tests/test_layout_audit.py
Requires the same toolchain as the input gate (playwright + chromium).
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

SIZES = [("portrait 412x915", 412, 915), ("landscape 915x412", 915, 412)]


def _fit_rect_audit() -> bool:
    """Pure-math check: the region never leaves its box, at any pos/aspect."""
    from window_manager import _fit_rect
    box = (100, 50, 1000, 600)
    for aspect in (0.4, 1.0, 16 / 9, 3.2):
        for pos in (0.0, 0.25, 0.5, 0.75, 1.0):
            x, y, w, h = _fit_rect(box, aspect, pos)
            if not (box[0] <= x and box[1] <= y and
                    x + w <= box[0] + box[2] and y + h <= box[1] + box[3]):
                return False
            if w <= 0 or h <= 0:
                return False
    return True


def _check_panel(page, name, open_js, close_js, card_sel):
    """Opens one overlay panel and verifies: the card sits fully inside the
    viewport, the page gained no horizontal overflow, and no element inside
    the card is clipped horizontally."""
    page.evaluate(open_js)
    page.wait_for_selector(card_sel, state="visible", timeout=4000)
    ok = page.evaluate(
        """(sel) => {
          const card = document.querySelector(sel);
          const r = card.getBoundingClientRect();
          const inView = r.left >= 0 && r.top >= 0 &&
                         r.right <= innerWidth + 1 && r.bottom <= innerHeight + 1;
          const noPageScroll =
            document.scrollingElement.scrollWidth <= innerWidth + 1;
          let noClip = card.scrollWidth <= card.clientWidth + 1;
          for (const el of card.querySelectorAll('button, .q-row, .sets-row')) {
            if (el.scrollWidth > el.clientWidth + 2) noClip = false;
          }
          return { inView, noPageScroll, noClip };
        }""",
        card_sel,
    )
    page.evaluate(close_js)
    passed = ok["inView"] and ok["noPageScroll"] and ok["noClip"]
    return passed, ok


def main() -> int:
    import test_input_pipeline as gate

    threading.Thread(target=gate.run_server, daemon=True).start()
    gate.server_ready.wait(15)
    deadline = time.time() + 10
    import socket
    while time.time() < deadline:
        if gate.server_error:
            raise gate.server_error[0]
        try:
            with socket.create_connection(("127.0.0.1", gate.PORT), timeout=0.25):
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError("audit server never started")

    from playwright.sync_api import sync_playwright

    results = {"region math: _fit_rect stays inside its box for every pos":
               _fit_rect_audit()}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for label, w, h in SIZES:
            ctx = browser.new_context(
                viewport={"width": w, "height": h}, has_touch=True, is_mobile=True,
                user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 8) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 "
                            "Mobile Safari/537.36 RemoteUserApp"),
            )
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
            page.wait_for_selector("#group-left button", timeout=8000)

            for name, open_js, close_js, sel in (
                ("Quality panel", "openQualityPanel()", "closeQualityPanel()",
                 "#quality-panel .sets-card"),
                ("Sets picker", "openSetsPanel()", "closeSetsPanel()",
                 "#sets-panel .sets-card"),
                ("Aspect panel + Move handle",
                 "layouts = [{name:'Audit', process:'x', orient:'portrait',"
                 " icon:null, ratio:[600,1000], pos:0.5}]; openAspectPanel(0)",
                 "closeLayoutPanel()", "#layout-panel .lay-card"),
            ):
                passed, detail = _check_panel(page, name, open_js, close_js, sel)
                results[f"{name} @ {label}"] = passed
                if not passed:
                    print(f"  DETAIL {name} @ {label}: {detail}")

            # The Move handle must be visible and inside the panel card.
            page.evaluate(
                "layouts = [{name:'Audit', process:'x', orient:'portrait',"
                " icon:null, ratio:[600,1000], pos:0.5}]; openAspectPanel(0)")
            page.wait_for_selector(".asp-move", state="visible", timeout=4000)
            results[f"Move handle visible inside the card @ {label}"] = page.evaluate(
                """() => {
                  const m = document.querySelector('.asp-move').getBoundingClientRect();
                  const c = document.querySelector('.lay-card').getBoundingClientRect();
                  return m.width >= 40 && m.left >= c.left && m.right <= c.right &&
                         m.top >= c.top && m.bottom <= c.bottom;
                }""")
            page.evaluate("closeLayoutPanel()")
            results[f"no page errors @ {label}"] = not errors
            ctx.close()
        browser.close()

    print("\n=== LAYOUT AUDIT ===")
    failed = 0
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"LAYOUT AUDIT FAILED — {failed} check(s).")
        return 1
    print("LAYOUT AUDIT PASSED — panels fit, nothing clipped, region math bounded.")
    return 0


def test_layout_audit():
    """pytest entry — skipped where the browser toolchain is absent."""
    import pytest
    pytest.importorskip("playwright.sync_api")
    pytest.importorskip("uvicorn")
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
