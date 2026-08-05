"""End-to-end input regression gate: REAL client page + REAL server app,
driven by a REAL Chromium with touch emulation — only injection is faked.

Exists because "left click stopped working" shipped more than once while every
file looked correct in review (owner decree 2026-07-26: this must never need
re-debugging again). The whole pipeline is exercised: touch on the page →
Pointer Events → WebSocket protocol → FastAPI handler → injector call. A
FakeInjector records calls instead of SendInput, so the gate runs headless on
the build machine without touching the real screen.

Scenarios (all must pass, any failure exits 1 — build.py runs this fail-closed):
  1. steering    — a touch on the canvas sends pointer_move (pointer exactly
     under the finger — owner 2026-08-02) and NEVER a click (the no-tap decree)
  2. click       — Click/Right/Middle are CLICK/HOLD buttons (owner
     2026-08-04): finger lands -> press(button, down), lifts -> press(button,
     up); a tap is exactly one down+up pair in order
  4. keys + chord — the Esc builtin lands press_key("escape"); switching the
     wheel to Edit and tapping Copy lands press_chord("ctrl+c")
  5. stolen tap  — pointerdown ended by a pointercancel still completes the
     click: the down already fired, the cancel must RELEASE (Android steals
     edge touches; up-only buttons died on-device 2026-07-26)
  5b. system swipe — a pointercancel after real travel must also release: a
     hold button fires down on touch (that IS hold semantics), so the one
     guarantee is that no PC button ever stays STUCK down
  6. edge reach  — a touch in the far bottom-right corner drives the cursor
     to the PC screen's bottom-right edge (full-screen fit, no margins)
  7. keyboard    — Keys focuses the capture field; typed text arrives as
     key_text; Enter arrives as the shift+enter chord (new row)
  8. /ping contract — the reachability probe answers EXACTLY 204: the Android
     shell counts only 204 as "the PC answered" (captive portals on foreign
     Wi-Fi answer any request with a 2xx/redirect login page — live failure
     2026-07-27); a drift to 200 here would strand every phone
  9. injection tripwire — InjectionMonitor alarms on exactly the configured
     streak of eaten big moves, ignores small ones, re-arms after a success
     (UIPI live failure 2026-07-29: Windows silently discarded every injected
     event while an elevated window had focus — SendInput "succeeded", the
     phone showed a healthy session with a dead mouse)

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
import urllib.request
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

    def press(self, button, down):
        self._rec("press", button, down)

    def wheel(self, x, y, ticks):
        self._rec("wheel", round(x, 4), round(y, 4), ticks)

    def type_text(self, text):
        self._rec("type_text", text)

    def press_key(self, key):
        self._rec("press_key", key)

    def press_chord(self, chord):
        self._rec("press_chord", chord)

    def take_input_alarm(self):
        return False  # the gate fakes injection — nothing to verify


class FakeStream:
    """JPEG-mode duck interface — no capture, no frames (input needs none)."""
    mode = "jpeg"
    width = 1920
    height = 1080
    monitor_index = 0

    def __init__(self):
        self.running = 0

    def output_count(self):
        return 1

    def set_viewport(self, x, y, w, h):
        pass

    # JPEG capture is ON DEMAND since 2026-08-05 (nothing may be captured or
    # encoded while no phone is watching), so start/stop are part of the duck
    # interface the web layer calls — the gate caught their absence the moment
    # they were added, which is exactly what it is for.
    def start(self):
        self.running += 1

    def stop(self):
        self.running -= 1

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

    # 8. /ping contract — the Android shell's strict probe accepts ONLY the
    # exact 204 (anything else is a captive portal, not our server).
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/ping", timeout=5) as r:
        results["/ping contract: exactly 204 (phone probe)"] = r.status == 204

    # 9. injection tripwire — the pure decision logic of the real injector's
    # self-check (the Win32 side is faked in this gate, so the logic that
    # turns "moves do not land" into a visible alarm is pinned here).
    from input_injector import InjectionMonitor
    mon = InjectionMonitor(min_jump=24, tolerance=16, streak=3)
    tw = [
        mon.note((500, 500), (100, 100), 400) is False,   # miss 1 — quiet
        mon.note((900, 900), (100, 100), 400) is False,   # miss 2 — quiet
        mon.note((500, 500), (100, 100), 400) is True,    # miss 3 — ALARM
        mon.note((900, 900), (100, 100), 400) is False,   # alarmed once per streak
        mon.note((500, 500), (503, 497), 400) is False,   # landed — resets + re-arms
        mon.note((900, 900), (100, 100), 10) is False,    # small jump never judged
        mon.note((900, 900), (100, 100), 400) is False,   # miss 1 after reset
        mon.note((900, 900), None, 400) is False,         # miss 2 (no cursor read)
        mon.note((500, 500), (100, 100), 400) is True,    # miss 3 — ALARM again
    ]
    results["injection tripwire: alarms on eaten moves"] = all(tw)

    # 9b. the WIRING: the real InputInjector.move() must feed the monitor and
    # raise the alarm the web layer forwards to the phone. SendInput itself is
    # stubbed out — this gate never touches the build machine's real cursor.
    from input_injector import InputInjector
    real = InputInjector((0, 0, 1920, 1080))
    real._send = lambda *a, **k: None            # never inject on the build machine
    real._cursor_px = lambda: (10, 10)           # cursor never follows = eaten input
    for _ in range(5):
        real.move(0.9, 0.9)                      # big jumps, none of them land
    results["injection tripwire: move() raises the client alarm"] = real.take_input_alarm()
    results["injection tripwire: alarm clears after reading"] = not real.take_input_alarm()

    # 9c. the SIDE buttons (owner 2026-08-05 — "Button 4 i Button 5"): both
    # share ONE flag pair and name themselves in mouseData, so a wrong
    # mouseData presses the other side button (or none) with no error at all.
    # The client path is the proven hold path; this pins the Win32 mapping.
    sent: list[tuple[int, int]] = []
    side = InputInjector((0, 0, 1920, 1080))
    side._send = lambda flags, ax=0, ay=0, mouse_data=0: sent.append((flags, mouse_data))
    side.press("x1", True)
    side.press("x1", False)
    side.press("x2", True)
    side.press("x2", False)
    results["side buttons: x1/x2 -> XDOWN/XUP with the right mouseData"] = sent == [
        (0x0080, 0x0001), (0x0100, 0x0001), (0x0080, 0x0002), (0x0100, 0x0002)]

    # 9d. TYPED command buttons (owner 2026-08-05 — the Claude set's /usage,
    # /model, /effort). ORDER is the whole contract: the text reaches the
    # clipboard, THEN Ctrl+V, THEN Enter. An Enter that overtakes the paste
    # sends an empty prompt, which is exactly the kind of silent wrong that
    # only shows up on the owner's screen.
    import clipboard as clip
    import web as web_mod
    steps: list[tuple] = []
    real_copy = clip.copy_text
    clip.copy_text = lambda t: (steps.append(("clipboard", t)), True)[1]
    typed = InputInjector((0, 0, 1920, 1080))
    typed.press_chord = lambda c: steps.append(("chord", c))
    typed.press_key = lambda k: steps.append(("key", k))
    typed.type_text = lambda t: steps.append(("typed", t))
    web_mod._paste_text(typed, "/usage", True)
    web_mod._paste_text(typed, "/", False)          # the Menu button: no Enter
    clip.copy_text = lambda t: False                # clipboard held by another app
    web_mod._paste_text(typed, "/model", True)
    clip.copy_text = real_copy
    results["typed command: clipboard -> ctrl+v -> enter, in that order"] = steps == [
        ("clipboard", "/usage"), ("chord", "ctrl+v"), ("key", "enter"),
        ("clipboard", "/"), ("chord", "ctrl+v"),
        ("typed", "/model"), ("key", "enter"),      # fallback still delivers
    ]

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

        # 2. CLICK/HOLD buttons (owner 2026-08-04): a tap on Click/Right/
        # Middle is one press-down + press-up pair, in that order — the same
        # wiring that holds the PC button while the finger stays down.
        def press_pair(c, button):
            downs = [i for i, x in enumerate(c) if x == ("press", button, True)]
            ups = [i for i, x in enumerate(c) if x == ("press", button, False)]
            return bool(downs and ups) and downs[0] < ups[-1]

        for name, action in (("left", "click"), ("right", "right"), ("middle", "middle")):
            clear_calls()
            tap_button(page, f'#group-left [data-action="{action}"]')
            results[f"{action} button -> press({name}) down+up"] = \
                wait_for(lambda c, b=name: press_pair(c, b))

        # 4. Esc is a builtin now (it also switches keyboard/mic OFF) and
        # lands as the real key; a chord button still lands press_chord —
        # reached through the category wheel (Edit is not on screen), which
        # pins the wheel's tap-to-switch path too.
        clear_calls()
        tap_button(page, '#group-right [data-action="esc"]')
        results["Esc button -> press_key(escape)"] = \
            wait_for(lambda c: ("press_key", "escape") in c)
        clear_calls()
        tap_button(page, '#group-right .ctl.cat')
        page.wait_for_selector('#wheel .wheel-item', timeout=3000)
        tap_button(page, '#wheel .wheel-item:has-text("Edit")')
        tap_button(page, '#group-right .ctl:has-text("Copy")')
        results["wheel -> Edit -> Copy -> chord(ctrl+c)"] = \
            wait_for(lambda c: ("press_chord", "ctrl+c") in c)
        # put Input back — the keyboard scenario below needs it on screen
        tap_button(page, '#group-right .ctl.cat')
        page.wait_for_selector('#wheel .wheel-item', timeout=3000)
        tap_button(page, '#wheel .wheel-item:has-text("Input")')

        # 5. stolen-tap rescue on a HOLD button: Android ends edge-zone
        # touches with a pointercancel — the down already fired on touch, so
        # the cancel must RELEASE and the click still completes (the
        # 2026-07-26 all-buttons-dead failure, hold-semantics edition)...
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
        results["stolen tap (cancel) still completes the click"] = \
            wait_for(lambda c: press_pair(c, "left"))

        # 5b. ...and a SYSTEM SWIPE crossing the button must never leave the
        # PC button STUCK down: with real hold semantics the down fires on
        # touch (that is the feature), so the pinned guarantee is the release.
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
        swipe_calls = snapshot()
        results["system swipe never leaves the button stuck down"] = \
            ("press", "left", True) not in swipe_calls or press_pair(swipe_calls, "left")

        # keepFocus buttons (chords, toggles) still ignore a travelled cancel:
        # the same swipe over Esc must not press the key.
        clear_calls()
        page.evaluate("""() => {
            const btn = document.querySelector('#group-right [data-action="esc"]');
            const r = btn.getBoundingClientRect();
            const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
            const opts = (x, y) => ({bubbles: true, cancelable: true, isPrimary: true,
                                     pointerId: 97, pointerType: 'touch',
                                     clientX: x, clientY: y});
            btn.dispatchEvent(new PointerEvent('pointerdown', opts(cx, cy)));
            btn.dispatchEvent(new PointerEvent('pointermove', opts(cx, cy - 80)));
            btn.dispatchEvent(new PointerEvent('pointercancel', opts(cx, cy - 80)));
        }""")
        time.sleep(0.4)
        results["system swipe over a tap button does NOT fire"] = \
            ("press_key", "escape") not in snapshot()

        # 6. edge reach: the image fills the canvas with no reserved margins
        # (owner 2026-08-02) — a corner touch maps straight to the corner.
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
