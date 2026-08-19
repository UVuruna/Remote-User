"""THE PICTURE IS DRAWN WHEN THERE IS A NEW PICTURE, NOT WHEN THE PANEL BLINKS.

Owner order 2026-08-14, in his own words: *"ako korisnik odabere 10 fps onda je
to dovoljno, nema potrebe 120 puta u sekundi da telefon iscrtava sliku kada se
ona menja samo 10 puta u sekundi"* (lang-ok: owner quote).

`client/render.js`'s loop used to call `redraw()` on EVERY animation frame,
unconditionally. On his S25 Ultra that is 120 Hz against a stream he may have
set to 10 fps — eleven of every twelve full-canvas composites of a 4K-ish video
redrew the picture that was already on the screen. The screen is the biggest
battery cost on a phone and the GPU work behind it is the biggest one this app
controls.

HIS OWN FRAMING DECIDED THE DESIGN, and it is better than the obvious one: we
never ask the device what it can do (`screen.refreshRate` is a claim, and a
claim about the PANEL rather than about our stream). We draw when a frame
ACTUALLY ARRIVES, so the rate follows the encoder by construction and keeps
following it when he changes fps, when the network sags, and when a layout crop
makes the stream cheaper. Nothing has to be kept in step with anything.

WHY THIS FILE RUNS A REAL BROWSER AND NOT A SOURCE READ. The whole claim is
about a RATE — how many times a second something happens — and a rate cannot be
read off a diff. A source check would have passed just as happily on the old
loop with a comment about frames added above it. So this counts real `redraw()`
calls in real Chromium over a real second of wall clock.

It runs its OWN static server on its OWN port, deliberately: `test_phone_chrome
.py` binds 8898, and while both were running the two collided — one of them got
ERR_CONNECTION_REFUSED and the other a page that never received `config`, which
for half an hour looked exactly like a defect in this change. A gate that fails
when a sibling is running is not a gate, it is a coin flip.

Run:  .venv\\Scripts\\python tests/test_redraw_rate.py
"""

import functools
import http.server
import sys
import threading
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
CLIENT = PROJECT / "client"
RENDER = CLIENT / "render.js"
CONNECTION = CLIENT / "connection.js"
PORT = 8917          # NOT 8898 — see the module docstring
IDLE_MS = 1000       # one second of wall clock with nothing arriving


# ═══════════════════════════ THE STATIC SERVER ═══════════════════════════
class _Handler(http.server.SimpleHTTPRequestHandler):
    """Serves client/ the way the real server does — `/static/x.js` is
    `client/x.js` — and nothing else. There is deliberately no `/ws`: this
    file's subject is what the page does when NO frames are arriving, which
    is precisely the state the old loop kept painting through."""

    def translate_path(self, path: str) -> str:
        p = path.split("?")[0]
        if p.startswith("/static/"):
            p = p[len("/static"):]
        if p in ("/", ""):
            p = "/index.html"
        return str(CLIENT / p.lstrip("/"))

    def log_message(self, *args) -> None:
        pass


def _serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


# ═══════════════════════════ THE MEASUREMENT ═══════════════════════════
COUNT_JS = """
() => {
  // Wrap the page's own redraw() — a classic-script function declaration is a
  // property of window, so this counts the REAL calls the page makes, never a
  // copy of the loop reimplemented in the test.
  window.__redraws = 0;
  const real = window.redraw;
  window.redraw = function () { window.__redraws += 1; return real.apply(this, arguments); };
  // The loop only starts with an MSE session, which needs a server. Start it
  // by hand: the subject is the loop's own idling behaviour, not how it was
  // reached.
  window.renderLoop();
}
"""


def _measure(page) -> int:
    page.evaluate(COUNT_JS)
    page.wait_for_timeout(IDLE_MS)
    return page.evaluate("() => window.__redraws")


def _with_page(fn):
    from playwright.sync_api import sync_playwright
    srv = _serve()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 412, "height": 915})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"http://127.0.0.1:{PORT}/?token=gatetoken",
                          wait_until="load")
                page.wait_for_timeout(400)
                return fn(page, errors)
            finally:
                browser.close()
    finally:
        srv.shutdown()


def check_an_idle_page_stops_drawing() -> bool:
    """THE WHOLE POINT. With no frames arriving and nothing moving, the page
    must not repaint at all. The old loop repainted at the panel's refresh
    rate forever — at 412x915 in headless Chromium that is ~60/s, and on his
    120 Hz phone twice that.

    The allowance is 3 rather than 0 on purpose: the first paint after
    `renderLoop()` is legitimate (there IS a new picture — the first one), and
    a theme/anchor pass may add one. Anything that keeps drawing shows up as
    tens, not as three, so the threshold cannot pass a regression by luck.

    PLANTED DEFECT: restore the unconditional `rafId = requestAnimationFrame
    (step); redraw();` loop and this check reports ~60 and goes red."""
    def run(page, errors):
        n = _measure(page)
        if errors:
            print(f"  DETAIL the page threw: {errors[0]}")
            return False
        print(f"  DETAIL {n} redraw(s) in {IDLE_MS} ms of an idle page")
        return n <= 3
    return _with_page(run)


def check_the_page_still_loads_without_throwing() -> bool:
    """Held separately from the count above, because a page that DIED would
    also score zero redraws — and would pass a rate check that only looked at
    the number. The two together are what make the count mean anything."""
    def run(page, errors):
        if errors:
            print(f"  DETAIL the page threw: {errors[0]}")
            return False
        ok = page.evaluate("() => typeof window.renderLoop === 'function'"
                           " && typeof window.scheduleRedraw === 'function'")
        if not ok:
            print("  DETAIL renderLoop/scheduleRedraw are not on the page")
        return bool(ok)
    return _with_page(run)


def check_a_moved_cursor_still_repaints() -> bool:
    """THE OTHER HALF, and the reason this is a dirty flag and not a bare
    frame callback. The PC's pointer, a pinch, a pan and a theme flip are all
    reasons to repaint that have nothing to do with a video frame. If only
    frames drew, the cursor would step at the stream's fps — ten times a
    second on a 10 fps stream, which is worse than what he has today.

    PLANTED DEFECT: make `scheduleRedraw()` a no-op and this check reports 0
    while the idle check above still passes — the exact regression the count
    alone cannot see."""
    def run(page, errors):
        page.evaluate(COUNT_JS)
        page.wait_for_timeout(200)
        before = page.evaluate("() => window.__redraws")
        page.evaluate("() => { for (let i = 0; i < 5; i++) window.scheduleRedraw(); }")
        page.wait_for_timeout(200)
        after = page.evaluate("() => window.__redraws")
        if errors:
            print(f"  DETAIL the page threw: {errors[0]}")
            return False
        print(f"  DETAIL {after - before} redraw(s) after five scheduleRedraw() calls")
        # Five requests inside one animation frame must COALESCE — at least one
        # paint (it is not ignored) and never five (it is not per-call).
        return 1 <= (after - before) <= 3
    return _with_page(run)


def check_the_cursor_handler_schedules_instead_of_leaning_on_the_loop() -> bool:
    """`connection.js` used to skip its redraw in h264 with the comment "h264
    redraws every rAF anyway" — true of the old loop and false the moment the
    loop began drawing on frame arrival. A source check, and honestly so: the
    live cursor needs a server, and what must never come back is that literal
    conditional.

    PLANTED DEFECT: restore `if (streamMode !== "h264") redraw();` and this
    check goes red."""
    src = CONNECTION.read_text(encoding="utf-8")
    if 'cursorShapeName = msg.shape' not in src:
        print("  DETAIL connection.js no longer handles the cursor shape")
        return False
    tail = src[src.index('cursorShapeName = msg.shape'):][:900]
    if 'streamMode !== "h264"' in tail:
        print('  DETAIL the cursor redraw is conditional on the stream mode '
              'again — h264 no longer redraws every rAF')
        return False
    return "scheduleRedraw()" in tail


def check_the_rate_is_never_read_off_the_device() -> bool:
    """His own instruction, and it is a design rule rather than a detail: the
    rate follows the STREAM, never a number the panel reports about itself.
    `screen.refreshRate` (and Android's `Display.getRefreshRate` reached
    through the bridge) would be a claim about the hardware, and it would have
    to be kept in step with fps, with the network and with the layout crop —
    three things the frame callback already tracks for free."""
    src = RENDER.read_text(encoding="utf-8")
    for banned in ("refreshRate", "getRefreshRate", "displayRate"):
        # in a comment is fine — this looks for a real read
        for line in src.splitlines():
            stripped = line.strip()
            if banned in stripped and not stripped.startswith(("//", "*", "/*")):
                print(f"  DETAIL render.js reads the panel's own rate: {stripped!r}")
                return False
    return "requestVideoFrameCallback" in src


CHECKS = [
    ("an idle page stops drawing entirely", check_an_idle_page_stops_drawing),
    ("the page still loads and both entry points exist",
     check_the_page_still_loads_without_throwing),
    ("a moved cursor still repaints, coalesced to one paint a frame",
     check_a_moved_cursor_still_repaints),
    ("the cursor handler schedules instead of leaning on the loop",
     check_the_cursor_handler_schedules_instead_of_leaning_on_the_loop),
    ("the rate follows the stream, never the panel's own claim",
     check_the_rate_is_never_read_off_the_device),
]


def main() -> int:
    print("=== REDRAW RATE GATE ===")
    failed = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as exc:  # a gate may not die silently
            print(f"  ERROR {name}: {exc!r}")
            ok = False
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    if failed:
        print(f"\nREDRAW RATE GATE FAILED — {failed} check(s).")
        return 1
    print("\nREDRAW RATE GATE PASSED — the phone draws when there is a new "
          "picture, not when the panel blinks.")
    return 0


def test_gate():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
