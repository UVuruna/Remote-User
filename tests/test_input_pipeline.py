"""End-to-end input regression gate: REAL client page + REAL server app,
driven by a REAL Chromium with touch emulation — only injection is faked.

Exists because "left click stopped working" shipped more than once while every
file looked correct in review (owner decree 2026-07-26: this must never need
re-debugging again). The whole pipeline is exercised: touch on the page →
Pointer Events → WebSocket protocol → FastAPI handler → injector call. A
FakeInjector records calls instead of SendInput, so the gate runs headless on
the build machine without touching the real screen.

Scenarios (all must pass, any failure exits 1 — build.py runs this fail-closed):
  1. steering    — a touch on the canvas sends pointer_move (cursor offset
     applied) and NEVER a click (the no-tap decree)
  2. click       — the Click button lands injector.click("left")
  3. right click — the Right button lands injector.click("right") (a BUTTON, not a tap)
  4. chord       — a chord button lands press_chord
  5. stolen tap  — pointerdown ended by a no-travel pointercancel STILL fires
     (Android steals edge touches; up-only buttons died on-device 2026-07-26)
  5b. system swipe — pointercancel after real travel must NOT fire (a home/back
     gesture crossing a button is not a press)
  6. edge reach  — a touch in the far bottom-right corner still drives the
     cursor to the PC screen's bottom-right edge (offset margin geometry)
  7. keyboard    — Keys focuses the capture field; typed text arrives as
     key_text; Enter arrives as the shift+enter chord (new row)

The control layout comes from tests/fixtures/actions.json — pinned, so the
owner's hand-edited repo actions.json can never break the build.

Run:  .venv\\Scripts\\python tests/test_input_pipeline.py
Requires: pip install playwright && playwright install chromium
"""

import asyncio
import socket
import sys
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import uvicorn

TOKEN = "gatetoken"
PORT = 8898
VIEW_W, VIEW_H = 412, 915  # portrait phone, dpr 1 → canvas px == CSS px
# The gate pins its OWN control layout — actions.json in the repo root is the
# owner's hand-edited file (ACTIONS.md: "yours to hand-edit"), and a layout
# edit there must never block a build.
ACTIONS_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "actions.json"

calls = []
calls_lock = threading.Lock()


class FakeInjector:
    """Records instead of SendInput. Interface-compatible with InputInjector."""

    def __init__(self):
        self._cursor = (0.5, 0.5)

    def _rec(self, *a):
        with calls_lock:
            calls.append(a)

    def cursor_norm(self):
        return self._cursor

    def set_monitor_rect(self, rect):
        self._rec("set_monitor_rect", rect)

    def move(self, x, y):
        self._cursor = (x, y)
        self._rec("move", round(x, 4), round(y, 4))

    def button_down(self, x, y, button):
        self._rec("button_down", round(x, 4), round(y, 4), button)

    def button_up(self, x, y, button):
        self._rec("button_up", round(x, 4), round(y, 4), button)

    def click(self, button):
        self._rec("click", button)

    def wheel(self, x, y, ticks):
        self._rec("wheel", round(x, 4), round(y, 4), ticks)

    def type_text(self, text):
        self._rec("type_text", text)

    def press_key(self, key):
        self._rec("press_key", key)

    def press_chord(self, chord):
        self._rec("press_chord", chord)


class FakeStream:
    """JPEG-mode duck interface — no capture, no frames (input needs none)."""
    mode = "jpeg"
    width = 1920
    height = 1080
    monitor_index = 0

    def output_count(self):
        return 1

    def set_viewport(self, x, y, w, h):
        pass

    def switch_to(self, index):
        return False

    def take_screenshot(self):
        return None


server_ready = threading.Event()
server_error = []


def run_server():
    async def main():
        import config
        import web
        config.apply(actions_path=ACTIONS_FIXTURE)
        loop = asyncio.get_running_loop()

        def quiet_reset(l, context):  # noqa: ANN001
            # The browser slams its sockets shut on close(); Windows proactor
            # then raises ConnectionResetError in a late callback. Harmless
            # teardown noise in THIS harness only — never silence it in the app.
            if isinstance(context.get("exception"), ConnectionResetError):
                return
            l.default_exception_handler(context)

        loop.set_exception_handler(quiet_reset)
        hub = web.FrameHub(loop)
        app = web.create_app(FakeStream(), hub, FakeInjector(), TOKEN)
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=PORT,
            log_level="warning", log_config=None, lifespan="off",
        ))
        server_ready.set()
        await server.serve()

    try:
        asyncio.run(main())
    except BaseException as e:  # noqa: BLE001 — uvicorn exits a taken port via SystemExit
        server_error.append(e)
        server_ready.set()


def snapshot():
    with calls_lock:
        return list(calls)


def clear_calls():
    with calls_lock:
        calls.clear()


def wait_for(pred, timeout=4.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred(snapshot()):
            return True
        time.sleep(0.05)
    return False


def tap_button(page, selector):
    """Tap the centre of one control button. Builtins are targeted by their
    data-action (labels are ambiguous — a category can share a button's name);
    chord buttons have no action and are found by label text."""
    box = page.locator(selector).first.bounding_box()
    page.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)


def main():
    threading.Thread(target=run_server, daemon=True).start()
    server_ready.wait(15)
    # Readiness = the port actually accepts, not "the thread started".
    deadline = time.time() + 10
    while time.time() < deadline:
        if server_error:
            raise server_error[0]
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.25):
                break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError(f"test server never started listening on port {PORT}")

    from playwright.sync_api import sync_playwright

    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": VIEW_W, "height": VIEW_H},
            has_touch=True,
            is_mobile=True,
            # The APK WebView's marker — Android UAs without it get the
            # install funnel instead of the client page.
            user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36 RemoteUserApp"),
        )
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{PORT}/?token={TOKEN}")
        page.wait_for_selector("#group-left button", timeout=8000)
        page.wait_for_function(
            "document.getElementById('status').textContent.includes('Connected')",
            timeout=8000)

        # 1. steering — and the no-tap decree: a canvas touch may ONLY move,
        # it must never click (nothing on the canvas acts on a tap).
        clear_calls()
        page.touchscreen.tap(VIEW_W / 2, VIEW_H / 2)
        moved = wait_for(lambda c: any(x[0] == "move" for x in c))
        time.sleep(0.3)  # give a stray click time to surface before asserting absence
        clicked = any(x[0] in ("click", "button_down", "button_up") for x in snapshot())
        results["steering: canvas touch -> pointer_move"] = moved
        results["no-tap rule: canvas touch never clicks"] = not clicked

        # 2. left click
        clear_calls()
        tap_button(page, '#group-left [data-action="click"]')
        results["Click button -> click(left)"] = \
            wait_for(lambda c: ("click", "left") in c)

        # 3. right click — a BUTTON now, never a canvas tap
        clear_calls()
        tap_button(page, '#group-left [data-action="right"]')
        results["Right button -> click(right)"] = \
            wait_for(lambda c: ("click", "right") in c)

        # 4. chord (Esc lives in the default right group)
        clear_calls()
        tap_button(page, '#group-right .ctl.text:has-text("Esc")')
        results["Esc button -> chord(escape)"] = \
            wait_for(lambda c: ("press_chord", "escape") in c)

        # 5. stolen-tap rescue: Android ends edge-zone touches with a
        # pointercancel — a cancel with (near) zero travel IS the tap and must
        # still fire (the 2026-07-26 all-buttons-dead failure)...
        clear_calls()
        page.evaluate("""() => {
            const btn = document.querySelector('#group-left [data-action="click"]');
            const r = btn.getBoundingClientRect();
            const opts = {bubbles: true, cancelable: true, isPrimary: true,
                          pointerId: 99, pointerType: 'touch',
                          clientX: r.x + r.width / 2, clientY: r.y + r.height / 2};
            btn.dispatchEvent(new PointerEvent('pointerdown', opts));
            btn.dispatchEvent(new PointerEvent('pointercancel', opts));
        }""")
        results["stolen tap (cancel, no travel) still fires"] = \
            wait_for(lambda c: ("click", "left") in c)

        # 5b. ...but a SYSTEM SWIPE crossing the button (real travel, then
        # cancel) must NOT act on the PC — a home/back gesture is not a press.
        clear_calls()
        page.evaluate("""() => {
            const btn = document.querySelector('#group-left [data-action="click"]');
            const r = btn.getBoundingClientRect();
            const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
            const opts = (x, y) => ({bubbles: true, cancelable: true, isPrimary: true,
                                     pointerId: 98, pointerType: 'touch',
                                     clientX: x, clientY: y});
            btn.dispatchEvent(new PointerEvent('pointerdown', opts(cx, cy)));
            btn.dispatchEvent(new PointerEvent('pointermove', opts(cx, cy - 80)));
            btn.dispatchEvent(new PointerEvent('pointercancel', opts(cx, cy - 80)));
        }""")
        time.sleep(0.4)
        results["system swipe over a button does NOT fire"] = \
            ("click", "left") not in snapshot()

        # 6. edge reach: with the up-left offset (right-handed default), the
        # margin must let a bottom-right-corner touch reach the screen corner.
        clear_calls()
        page.touchscreen.tap(VIEW_W - 2, VIEW_H - 2)
        results["edge reach: corner touch -> cursor at ~(1,1)"] = \
            wait_for(lambda c: any(x[0] == "move" and x[1] > 0.98 and x[2] > 0.98 for x in c))

        # 7. keyboard: Keys focuses the invisible field, typing lands as
        # key_text, Enter is the shift+enter new-row chord.
        clear_calls()
        tap_button(page, '#group-right [data-action="keyboard"]')
        page.wait_for_function("document.activeElement === document.getElementById('kb')",
                               timeout=3000)
        page.keyboard.type("hi")
        results["keyboard: typed text -> key_text"] = \
            wait_for(lambda c: any(x[0] == "type_text" for x in c))
        clear_calls()
        page.keyboard.press("Enter")
        results["keyboard: Enter -> chord(shift+enter)"] = \
            wait_for(lambda c: ("press_chord", "shift+enter") in c)

        browser.close()

    if errors:
        print("PAGE ERRORS:")
        for e in errors:
            print(f"  {e}")

    print("\n=== INPUT PIPELINE GATE ===")
    failed = False
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed |= not ok
    if failed or errors:
        print("\nGATE FAILED — the input pipeline is broken; do not ship.")
        sys.exit(1)
    print("\nGATE PASSED — touch -> protocol -> injection verified end-to-end.")


if __name__ == "__main__":
    main()
