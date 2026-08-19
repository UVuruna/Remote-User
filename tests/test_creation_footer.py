"""THE FOOTER IS ALWAYS VISIBLE — the New-layout creation panel, task 227a.

Owner report 2026-08-11, with his screenshot: when the window list is long,
Cancel/Create scrolled off-screen with it — `.lay-card` was ONE block that
scrolled as a whole (`max-height: 92vh; overflow-y: auto`), so a chosen row,
the name field, the shape rows and a twenty-row list together pushed the
footer below the fold with no hint that scrolling further would ever reach
it.

The fix (client/layout-create.js `renderCreationPanel`/`renderRecentsPanel` +
client/layout-create.css `.lc-panel`/`.lc-scrollwrap`) makes the card a fixed
-height flex COLUMN: everything except Cancel/Create lives in
`.lc-scrollwrap`, the one child that scrolls; `.lay-actions` is a sibling
appended after it and can never be scrolled past.

This is a REAL page in a REAL headless Chromium (the test_input_pipeline.py
harness, reused rather than re-built) staged with a TWENTY-row window list —
long enough that the old bug's card genuinely overflowed 92vh — at BOTH sizes
the owner's report and task spec name: portrait 412x915 and landscape
915x412. The assertion is the one that matters to him: Cancel/Create sit
INSIDE the viewport the INSTANT the panel opens, with no scroll performed.

Run:  .venv\\Scripts\\python tests/test_creation_footer.py
Requires: playwright + chromium (the test_input_pipeline.py precedent).
"""

import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import test_input_pipeline as gate  # noqa: E402

SIZES = [("portrait 412x915", 412, 915), ("landscape 915x412", 915, 412)]

# Twenty windows — long enough that the OLD single-scroll card genuinely
# overflowed its 92vh cap (measured: header + name field + shape rows alone
# already spend ~260px of a 412px-tall screen before a single row is drawn).
LONG_LIST_JS = (
    "creating = newCreation('list');"
    "creating.entries = Array.from({length: 20}, (_, i) => ("
    "  {kind: 'window', hwnd: i + 1, "
    "   title: 'Window number ' + (i + 1) + ' of a very long session', "
    "   process: 'code.exe', icon: null, x: 0.5, y: 0.5}));"
    "renderCreationPanel()"
)


def _wait_ready(page) -> None:
    page.wait_for_selector("#group-left button", timeout=8000)
    page.wait_for_function("() => monitor.w > 0", timeout=10000)


def _footer_check(page) -> dict:
    """Cancel/Create's own bounding rects, measured the instant the panel
    renders — before any scroll. `.lc-panel .lay-actions` is the pinned
    footer; querying `.lay-chip` inside it gets both buttons regardless of
    which one is disabled."""
    return page.evaluate(
        """() => {
          const actions = document.querySelector('#layout-panel .lay-actions');
          if (!actions) return { found: false };
          const chips = [...actions.querySelectorAll('.lay-chip')];
          const rects = chips.map((c) => c.getBoundingClientRect());
          const allVisible = rects.length > 0 && rects.every(
            (r) => r.top >= 0 && r.bottom <= innerHeight + 1 &&
                   r.left >= 0 && r.right <= innerWidth + 1);
          return {
            found: true, count: rects.length, allVisible,
            rects: rects.map((r) => ({top: r.top, bottom: r.bottom})),
          };
        }""")


def run() -> int:
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

    failures = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for label, w, h in SIZES:
            ctx = browser.new_context(
                viewport={"width": w, "height": h}, has_touch=True, is_mobile=True,
                # WITHOUT the app's own UA marker the server serves the
                # install funnel, not the client — NO browser ever sees the
                # client page (CLAUDE.md constraint), and this gate's
                # selectors would simply never appear.
                user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 8) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 "
                            "Mobile Safari/537.36 VibeCoderApp"))
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
            _wait_ready(page)
            page.evaluate(LONG_LIST_JS)
            page.wait_for_selector("#layout-panel .lay-card", state="visible",
                                   timeout=4000)
            result = _footer_check(page)
            ok = result.get("found") and result.get("count", 0) >= 2 and \
                result.get("allVisible")
            print(f"{'PASS' if ok else 'FAIL'} — footer visible with 20 "
                 f"entries @ {label}: {result}")
            if not ok:
                failures.append(label)
            ctx.close()
        browser.close()

    if failures:
        print(f"FAIL — footer scrolled off-screen at: {', '.join(failures)}")
        return 1
    print("PASS — test_creation_footer")
    return 0


def test_gate():
    assert run() == 0


if __name__ == "__main__":
    sys.exit(run())
