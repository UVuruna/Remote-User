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
  7b. mic survives the tap — a canvas tap closes only the KEYBOARD; a
     listening mic keeps listening (owner 2026-08-09, amending the 2026-08-04
     both-off rule: steering the cursor while dictating killed the mic
     mid-sentence); Esc and the keyboard going ON still switch the mic off
  8. /ping contract — the reachability probe answers EXACTLY 204: the Android
     shell counts only 204 as "the PC answered" (captive portals on foreign
     Wi-Fi answer any request with a 2xx/redirect login page — live failure
     2026-07-27); a drift to 200 here would strand every phone
  10. gamepad     — synthetic pad events driven through the page's REAL
     mapping (build rounds G1/G2, owner spec 2026-08-07): a D-pad arrow presses
     the LEFT group's button in that direction and HOLDS the PC button while
     it is held; a face button presses the RIGHT group's, on release; L2/R2 are
     Layout (+) / Hide; the left stick steers on the tuned curve at three
     deflections (deadzone included); the right stick scrolls; L1 held + stick
     + release picks a wheel category and fires NO button; a short shoulder tap
     steps the layout bar instead. The pad is only ever allowed in through
     `buttonPress()` — the same activator a finger's pointerup runs — so this
     block also pins that there is no second button path to drift (constraint 9)
  9. injection tripwire — InjectionMonitor alarms on exactly the configured
     streak of eaten big moves, ignores small ones, re-arms after a success
     (UIPI live failure 2026-07-29: Windows silently discarded every injected
     event while an elevated window had focus — SendInput "succeeded", the
     phone showed a healthy session with a dead mouse)
  11. horizontal scroll (owner spec — "scroll vertikalni i horizontalni"):
     InputInjector.wheel's new `hticks` is optional at the Win32 mapping
     itself — an OLD-STYLE call with no `hticks` argument at all (every
     caller before this round) still scrolls vertically only, with NOTHING
     horizontal ever sent; the right stick's other axis drives it at the same
     tuned rate, positive = tilted right (Windows documents MOUSEEVENTF_HWHEEL's
     positive value as "the wheel was tilted to the right" — the SAME sense as
     the stick's own un-inverted +x, so unlike the vertical mapping no
     negation belongs here); and the finger's Scroll mode is proven
     byte-for-byte unchanged — it never sends an `hticks` field at all

The control layout comes from tests/fixtures/actions.json — pinned, so the
owner's hand-edited repo actions.json can never break the build.

Run:  .venv\\Scripts\\python tests/test_input_pipeline.py
Requires: pip install playwright && playwright install chromium
"""

import asyncio
import math
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

    def wheel(self, x, y, ticks, hticks=0.0):
        self._rec("wheel", round(x, 4), round(y, 4), ticks, hticks)

    def type_text(self, text, guard=None):
        # `guard` is the mid-sentence focus checkpoint (focus_guard.typist) —
        # the real injector re-checks the foreground between chunks; nothing
        # here to fence, so it is only accepted.
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


def isolate_desktop() -> None:
    """THE BROWSER GATES MUST NOT SEE THE OWNER'S REAL DESKTOP (T83, owner
    decision 2026-08-14 after `tests/test_birth_radial.py` failed once inside
    `build.py` and passed every time it was run alone).

    These gates start the REAL `web.create_app`, and a connecting page makes
    `focus_guard.watch` run `layout_birth.scan` and `layout_popup.sweep_lost`
    — both of which call `EnumWindows` and read WHATEVER IS OPEN ON THIS PC AT
    THAT MOMENT. His own failing run has the evidence in its log:
    "PromptPainter ... is off every screen", a rescue chip raised about a real
    window of his that had nothing to do with the test. A page that gets an
    unexpected chip renders something the checks did not stage, so the result
    depended on what he happened to have open.

    THE COST OF LEAVING IT IS NOT A RED BUILD, IT IS THE HABIT. A gate that
    sometimes reddens for no reason teaches everyone — the owner included — to
    RE-RUN a red build instead of reading it, and that habit is the only way a
    broken guard can let a real defect through. This is the one hazard
    constraint 18 names, met for real.

    Three seams, all of them the enumeration itself and none of them a
    behaviour these gates are about: the creation list, the popup sweep's own
    eye, and the lost-window sweep. Everything else in `window_manager` stays
    real, so nothing that DOES belong to a browser gate is faked away.

    Deliberately in the shared harness rather than in one gate's own `main()`:
    every browser gate here starts this same server, so every one of them had
    the same exposure, and a fix in only the file that happened to fail first
    is how the next one gets found the same way in three weeks.
    """
    import desk_facts
    import layout_popup
    import lost_windows
    import window_manager

    window_manager.list_windows = lambda: []
    desk_facts.top_level_hwnds = lambda: set()
    lost_windows.sweep = lambda *a, **k: []


def run_server():
    async def main():
        import config
        import web
        config.apply(actions_path=ACTIONS_FIXTURE)
        isolate_desktop()
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
    chord buttons have no action and are found by label text.

    The button is WAITED for, never merely asked about: the pad's own tests
    change the group's category through the wheel, and that re-render is
    asynchronous — a bare `bounding_box()` returned None often enough to fail
    a build at random, with a TypeError that named nothing.
    """
    button = page.locator(selector).first
    button.wait_for(state="visible", timeout=5000)
    box = button.bounding_box()
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
    # `paste_text` moved out of web.py into content.py on 2026-08-08 (THE
    # STRUCTURE LAW): turning what the phone sent into keystrokes the PC
    # receives never belonged to the transport layer.
    import content as content_mod
    steps: list[tuple] = []
    real_copy = clip.copy_text
    clip.copy_text = lambda t: (steps.append(("clipboard", t)), True)[1]
    typed = InputInjector((0, 0, 1920, 1080))
    typed.press_chord = lambda c: steps.append(("chord", c))
    typed.press_key = lambda k: steps.append(("key", k))
    typed.type_text = lambda t, guard=None: steps.append(("typed", t))
    content_mod.paste_text(typed, "/usage", True)
    content_mod.paste_text(typed, "/", False)          # the Menu button: no Enter
    clip.copy_text = lambda t: False                # clipboard held by another app
    content_mod.paste_text(typed, "/model", True)
    clip.copy_text = real_copy
    results["typed command: clipboard -> ctrl+v -> enter, in that order"] = steps == [
        ("clipboard", "/usage"), ("chord", "ctrl+v"), ("key", "enter"),
        ("clipboard", "/"), ("chord", "ctrl+v"),
        ("typed", "/model"), ("key", "enter"),      # fallback still delivers
    ]

    # 9e. HORIZONTAL wheel (closing the gamepad round's reported gap: the
    # protocol carried one `ticks` and the injector knew only
    # `MOUSEEVENTF_WHEEL`). Pins the Win32 mapping the way 9c pins the side
    # buttons: MOUSEEVENTF_HWHEEL (0x1000), mouseData = hticks * WHEEL_DELTA,
    # positive = right — and, in the SAME assertion, that the legacy call
    # shape (no `hticks` argument at all — every caller before this round)
    # still injects EXACTLY one WHEEL event and nothing else.
    sent_wheel: list[tuple[int, int]] = []
    wh = InputInjector((0, 0, 1920, 1080))
    wh._send = lambda flags, ax=0, ay=0, mouse_data=0: sent_wheel.append((flags, mouse_data))
    wh._cursor_px = lambda: (10, 10)
    wh.wheel(0.5, 0.5, 3)          # legacy call — positional, no hticks at all
    wh.wheel(0.5, 0.5, -2, 1)      # vertical + rightward horizontal together
    wh.wheel(0.5, 0.5, 0, -1)      # horizontal-only, leftward
    # wheel() also calls move() first (the gesture point) — MOVE events use a
    # different flag, so filtering to the two wheel flags isolates the part
    # this case is about.
    wheel_only = [(f, d) for f, d in sent_wheel if f in (0x0800, 0x1000)]
    results["wheel: legacy call (no hticks) injects only WHEEL, unchanged"] = \
        wheel_only[:1] == [(0x0800, 360)]
    results["wheel: HWHEEL fires with the right flag and signed mouseData"] = \
        wheel_only[1:] == [(0x0800, -240), (0x1000, 120), (0x0800, 0), (0x1000, -120)]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": VIEW_W, "height": VIEW_H},
            has_touch=True,
            is_mobile=True,
            # The APK WebView's marker — Android UAs without it get the
            # install funnel instead of the client page.
            user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36 VibeCoderApp"),
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

        # 7b. the mic SURVIVES a canvas tap while the KEYBOARD still closes
        # (owner 2026-08-09, amending the 2026-08-04 both-off rule: he steers
        # the cursor WHILE dictating, and every steer killed the mic
        # mid-sentence). No Android bridge exists in this harness, so the
        # mic's ON state is planted directly — micOn/setMicActive are the
        # page's own top-level bindings, and micStop() (exactly what a
        # regression would call from the tap path) runs fine without the
        # bridge (micSupported() guards the stopVoice call).
        # The keyboard is still focused from scenario 7 — first prove the
        # tap closes IT...
        page.touchscreen.tap(VIEW_W / 2, VIEW_H / 2)
        try:
            page.wait_for_function(
                "document.activeElement !== document.getElementById('kb')",
                timeout=3000)
            kb_closed = True
        except Exception:
            kb_closed = False
        results["canvas tap still closes the keyboard"] = kb_closed
        # ...then that the SAME tap path leaves a listening mic alone.
        page.evaluate("() => { micOn = true; setMicActive(true); }")
        page.touchscreen.tap(VIEW_W / 2, VIEW_H / 2)
        time.sleep(0.3)  # the tap's handler is synchronous; generous margin
        results["canvas tap leaves the mic listening (owner 2026-08-09)"] = \
            page.evaluate("""() => micOn === true &&
                document.querySelector('[data-action="mic"]')
                    .classList.contains('active')""")
        # ...while every OTHER mic-off path is unweakened: Esc (inputOff)...
        clear_calls()
        tap_button(page, '#group-right [data-action="esc"]')
        wait_for(lambda c: ("press_key", "escape") in c)
        results["Esc still switches the mic off (inputOff unweakened)"] = \
            not page.evaluate("() => micOn")
        # ...and the one-of-two invariant: switching the KEYBOARD on still
        # switches the mic off (the capture field's focus handler).
        page.evaluate("() => { micOn = true; setMicActive(true); }")
        tap_button(page, '#group-right [data-action="keyboard"]')
        page.wait_for_function(
            "document.activeElement === document.getElementById('kb')",
            timeout=3000)
        results["keyboard ON still switches the mic off (one-of-two rule)"] = \
            not page.evaluate("() => micOn")

        # 10. GAMEPAD (build rounds G1/G2, owner spec 2026-08-07). The pad
        # pairs with the PHONE, so the Android shell captures its keys and
        # sticks and calls the page's `__padButton` / `__padAxis` — where the
        # WHOLE mapping lives. Everything below drives those two entry points
        # exactly as the shell does: synthetic pad events through the real
        # mapping, asserting the exact protocol that must come out of it.
        #
        # The pinned fixture layout is what makes the expectations readable:
        #   left group  = Mouse (up Click · left Right · right Middle · down Scroll)
        #   right group = Input (up Keys  · left Enter · right Esc  · down Mic)
        def pad(js):
            page.evaluate(f"() => {{ {js} }}")

        # 10a. A D-pad arrow presses the LEFT group's button in that direction,
        # and HOLDING it holds the PC button down — the same CLICK/HOLD the
        # finger gets, because it is literally the same activator.
        clear_calls()
        pad("__padButton('d_up', true)")
        pad_down = wait_for(lambda c: ("press", "left", True) in c)
        time.sleep(0.25)
        pad_still_held = ("press", "left", False) not in snapshot()
        pad("__padButton('d_up', false)")
        results["pad: D-pad -> left group's button, held while the key is held"] = (
            pad_down and pad_still_held and wait_for(lambda c: press_pair(c, "left")))

        # 10b. A face button presses the RIGHT group's — and on the RELEASE,
        # exactly where a finger's pointerup acts.
        clear_calls()
        pad("__padButton('f_right', true)")
        time.sleep(0.25)
        fired_early = ("press_key", "escape") in snapshot()
        pad("__padButton('f_right', false)")
        results["pad: face button -> right group's command, on release"] = (
            not fired_early and wait_for(lambda c: ("press_key", "escape") in c))

        # 10c. The triggers are the two corner buttons.
        # L2 IS STILL LAYOUT (+) — WHAT THE BUTTON OPENS CHANGED (owner
        # 2026-08-09, task 158). Its two jobs used to be a full-screen card in
        # `#layout-panel`; they are now the mini radial beside the button, so
        # asserting `#layout-panel` opened would be asserting the old product.
        # The INVARIANT this check exists for is untouched and is what is
        # measured: L2 reaches Layout (+)'s own activator, the same object a
        # finger's pointerup runs (CLAUDE.md constraint 12) — proven by
        # requiring the pad's press to produce exactly what the finger's own
        # `openSourceChooser` produces, two drawn and labelled options.
        #
        # AND IT CLOSES AGAIN ON A SECOND PRESS. That half is why this check
        # went red rather than merely stale: the pad has no backdrop to tap, so
        # a radial that only ever opened would leave a controller-only session
        # under a full-screen overlay with no way out — and it left one standing
        # over every later check in this file, which is what killed 10e4's tap
        # on the Scroll button downstream.
        # THE LAST VERSION of the grammar (the 221 lesson — this button has now
        # worn three shapes and only the newest may ship): task 186 superseded
        # 158's two-option S/SE shape with a CENTERED ring, task 228 grew that
        # ring to four, and on 2026-08-12 the owner reversed both — the radial
        # is an ANCHORED FAN of THREE beside the button again (New / Tap /
        # List; Recent left the radial, its panel and protocol untouched).
        # Pressing L2 DOWN opens it with the full source set, each drawn AND
        # labelled; a quick release pointing at nothing is the TAP (arms
        # tap-pick, today's act); a long release at nothing only closes. The
        # radial must never linger over later checks.
        results["pad: L2 -> Layout (+)"] = page.evaluate("""() => {
            closeLayoutPanel();
            closeMiniRadial();
            __padButton('l2', true);
            const items = [...document.querySelectorAll('#mini-radial .mini-item')];
            const opened = !document.getElementById('mini-radial').hidden &&
                           items.length === 3 &&
                           items.every((el) => el.querySelector('svg') &&
                                               el.querySelector('.lbl').textContent.trim());
            __padButton('l2', false);   // quick release at nothing = the tap
            const closed = document.getElementById('mini-radial').hidden;
            const armed = !!(typeof creating !== 'undefined' && creating) ||
                          !!(typeof layoutArm !== 'undefined' && layoutArm);
            cancelCreation();
            closeMiniRadial();
            closeLayoutPanel();
            return opened && closed && armed;
        }""")
        results["pad: R2 -> Hide"] = page.evaluate("""() => {
            const hidden = () => document.body.classList.contains('hidden-controls');
            const before = hidden();
            __padButton('r2', true);
            __padButton('r2', false);
            const during = hidden();
            __padButton('r2', true);
            __padButton('r2', false);   // put the controls back
            return before === false && during === true && hidden() === false;
        }""")

        # 10d. The left stick STEERS, on the curve the owner will tune. The
        # gate pins the SHAPE (deadzone, then a power curve, then speed × time),
        # never the numbers — it reads the page's own constants and recomputes
        # the expected coordinate independently, so retuning the feel on the
        # real controller can never turn a build red, while changing the
        # FORMULA must.
        pad_cfg = page.evaluate(
            "() => ({dz: PAD_DEADZONE, cv: PAD_CURVE, sp: PAD_CURSOR_SPEED,"
            "        tk: PAD_SCROLL_TICKS})")

        def pad_expected_x(deflection, dt_ms):
            magnitude = abs(deflection)
            if magnitude <= pad_cfg["dz"]:
                return None  # inside the deadzone: nothing may move at all
            unit = (magnitude - pad_cfg["dz"]) / (1 - pad_cfg["dz"])
            travel = math.copysign(unit ** pad_cfg["cv"], deflection)
            return 0.5 + travel * pad_cfg["sp"] * dt_ms / 1000

        for deflection in (0.10, 0.55, 1.0):
            clear_calls()
            # padCursorStep() is the very function the rAF loop calls — driving
            # it with an exact dt is what makes a frame-clock race untestable
            # into an exact assertion. Zeroing the axes afterwards stops the
            # loop before it can fire a frame of its own.
            page.evaluate(f"""() => {{
                __padAxis(0, 0, 0, 0);
                cursorPos = {{x: 0.5, y: 0.5}};
                __padAxis({deflection}, 0, 0, 0);
                padCursorStep(100);
                __padAxis(0, 0, 0, 0);
            }}""")
            want = pad_expected_x(deflection, 100)
            if want is None:
                time.sleep(0.3)
                ok = not any(x[0] == "move" for x in snapshot())
                label = f"pad: left stick at {deflection:.2f} is inside the deadzone"
            else:
                ok = wait_for(lambda c, w=want: any(
                    x[0] == "move" and abs(x[1] - w) < 0.002 and abs(x[2] - 0.5) < 0.002
                    for x in c))
                label = f"pad: left stick at {deflection:.2f} -> pointer_move on the curve"
            results[label] = ok

        # 10e. The right stick SCROLLS, and pushing it up scrolls up. Also
        # pins that a pure-vertical push leaves the NEW horizontal field at
        # zero (x[4] — FakeInjector.wheel records (x, y, ticks, hticks)) —
        # the "vertical is unchanged" half of closing the gamepad round's gap.
        clear_calls()
        page.evaluate("""() => {
            __padAxis(0, 0, 0, 0);
            cursorPos = {x: 0.4, y: 0.6};
            __padAxis(0, 0, 0, -1);   // pushed fully UP
            padScrollStep(1000);       // one second at full tilt
            __padAxis(0, 0, 0, 0);
        }""")
        results["pad: right stick -> scroll (up is up, at the tuned rate)"] = wait_for(
            lambda c: any(x[0] == "wheel" and x[3] == pad_cfg["tk"] and x[4] == 0.0
                          for x in c))

        # 10e2. The right stick's HORIZONTAL axis (`rx`) scrolls sideways —
        # the gap this round closes: `rx` used to be spent only on pointing
        # the category wheel while a shoulder was held (10f below); with no
        # wheel open it now drives `hticks` on the same curve as `ry`.
        # Pushing RIGHT must scroll right (positive hticks, matching
        # InputInjector.wheel's contract pinned in 9e), and the vertical
        # field must stay untouched by a horizontal-only push.
        clear_calls()
        page.evaluate("""() => {
            __padAxis(0, 0, 0, 0);
            cursorPos = {x: 0.4, y: 0.6};
            __padAxis(0, 0, 1, 0);   // pushed fully RIGHT
            padScrollStep(1000);      // one second at full tilt
            __padAxis(0, 0, 0, 0);
        }""")
        results["pad: right stick horizontal -> scroll right (positive hticks)"] = wait_for(
            lambda c: any(x[0] == "wheel" and x[3] == 0.0 and x[4] == pad_cfg["tk"]
                          for x in c))
        clear_calls()
        page.evaluate("""() => {
            __padAxis(0, 0, 0, 0);
            cursorPos = {x: 0.4, y: 0.6};
            __padAxis(0, 0, -1, 0);  // pushed fully LEFT
            padScrollStep(1000);
            __padAxis(0, 0, 0, 0);
        }""")
        results["pad: right stick horizontal -> scroll left (negative hticks)"] = wait_for(
            lambda c: any(x[0] == "wheel" and x[4] == -pad_cfg["tk"] for x in c))

        # 10e3. Backward compatibility: a `scroll` message with NO `hticks`
        # field at all — every client before this round, and still what an
        # unmodified page sends off-canvas — must reach the injector exactly
        # as it always did: `hticks` defaults to 0.0, nothing about the
        # vertical path changes. Bypasses the pad entirely (raw `send()`, the
        # same call gestures.js has always made) to pin the PROTOCOL contract
        # rather than the pad's own mapping.
        clear_calls()
        page.evaluate("""() => {
            send({ type: "scroll", x: 0.4, y: 0.6, ticks: 3 });
        }""")
        results["scroll backward-compat: message without hticks injects unchanged"] = \
            wait_for(lambda c: ("wheel", 0.4, 0.6, 3.0, 0.0) in c)

        # 10e4. The FINGER'S own Scroll mode must be byte-for-byte unchanged
        # by this round — not just the protocol contract 10e3 pins, but the
        # actual gestures.js code path: the Scroll mode button (Mouse set's
        # "down" slot, data-action="scroll") plus a real one-finger drag on
        # the canvas. That code never learned about `hticks` (untouched this
        # round), so the message it sends carries no such key at all, and it
        # must still land at the injector with `hticks` defaulted to 0.0.
        clear_calls()
        tap_button(page, '#group-left [data-action="scroll"]')
        page.evaluate("""() => {
            // A raw dispatchEvent-built PointerEvent is untrusted — real
            // Chromium refuses setPointerCapture() for a pointerId that never
            // came from an actual touch, throwing out of gestures.js's own
            // pointerdown handler mid-gesture (killing the rest of the drag,
            // and the socket with it). client/load_test.js hits the exact
            // same wall for its synthetic load-test pointers and stubs the
            // same way — this is that established pattern, test-only, and
            // restored right after so no later test's real touchscreen.tap()
            // is affected.
            canvas.__realCapture = canvas.setPointerCapture;
            canvas.setPointerCapture = () => {};
            const r = canvas.getBoundingClientRect();
            const cx = r.x + r.width / 2, cy = r.y + r.height / 2;
            const opts = (y) => ({bubbles: true, cancelable: true, isPrimary: true,
                                  pointerId: 66, pointerType: 'touch',
                                  clientX: cx, clientY: y});
            canvas.dispatchEvent(new PointerEvent('pointerdown', opts(cy)));
            canvas.dispatchEvent(new PointerEvent('pointermove', opts(cy + 200)));
            canvas.dispatchEvent(new PointerEvent('pointerup', opts(cy + 200)));
            canvas.setPointerCapture = canvas.__realCapture;
            // The synthetic down->move->up above lands in one JS turn (0ms
            // elapsed), so gestures.js computes an enormous fling velocity
            // and arms scroll INERTIA on pointerup — left alone it keeps
            // sending `scroll` messages on its own rAF loop long after this
            // block returns, polluting every later test's clear_calls()
            // window (confirmed: it broke 10f's "fires no button" assertion
            // downstream before this line was added). Cancel it before the
            // browser gets a chance to run that first frame.
            cancelScrollInertia();
        }""")
        finger_scrolled = wait_for(lambda c: any(x[0] == "wheel" for x in c))
        results["finger scroll (real drag): unchanged — hticks still defaults to 0.0"] = (
            finger_scrolled and all(x[4] == 0.0 for x in snapshot() if x[0] == "wheel"))
        tap_button(page, '#group-left [data-action="scroll"]')  # restore Move mode

        # 10f. A HELD shoulder opens that side's wheel, the stick POINTS (the
        # ring's own frame follows it) and the release confirms — while not a
        # single button may fire on the way.
        clear_calls()
        wheel_state = page.evaluate("""() => {
            // This check pins the POINTING grammar, not the wheel's
            // composition — task 181's drop-out default sheds the placed
            // sets and would leave one item to point at, so the grammar is
            // proven under the fixed mode (test_app_set_wheel's own choice;
            // composition under drop-out is test_wheel_dropout.py's job).
            // The no-duplicate rule ships in BOTH modes, so the expected
            // ring is wheelCats(side), read from the page itself rather
            // than assumed — the 181 change must move THIS arithmetic too.
            setWheelMode('fixed');
            groups.left = 0;
            renderGroup('left');
            const ring = wheelCats('left');
            __padButton('l1', true);
            const open = document.getElementById('wheel').classList.contains('open');
            const items = () => [...document.querySelectorAll('#wheel .wheel-item')];
            const n = items().length;
            // Item 1 sits one step clockwise from 12 o'clock — at n items the
            // step is 2PI/n, so point the stick at that exact angle.
            const ang = -Math.PI / 2 + (2 * Math.PI / n) * 1;
            __padAxis(Math.cos(ang), Math.sin(ang), 0, 0);
            const framed = items().findIndex((el) => el.classList.contains('current'));
            __padButton('l1', false);   // released while still pointing — that IS the pick
            __padAxis(0, 0, 0, 0);      // ...and only then does the thumb come back
            return {open, n, ringN: ring.length, framed, picked: groups.left,
                    expected: allCats().indexOf(ring[1]), expectedName: ring[1].name,
                    closed: !document.getElementById('wheel').classList.contains('open'),
                    shown: document.querySelector('#group-left .ctl.cat .lbl').textContent};
        }""")
        time.sleep(0.3)
        results["pad: L1 held + stick + release picks a set, and fires no button"] = (
            wheel_state["open"] and wheel_state["n"] == wheel_state["ringN"] and
            wheel_state["n"] >= 2 and wheel_state["framed"] == 1 and
            wheel_state["picked"] == wheel_state["expected"] and
            wheel_state["shown"] == wheel_state["expectedName"] and
            wheel_state["closed"] and not snapshot())
        page.evaluate("() => { setWheelMode('dropout'); groups.left = 0; renderGroup('left'); }")

        # 10g. ...and the SAME shoulder, merely tapped, is the layout bar's
        # ‹ › step. `send` is captured here rather than followed to the server:
        # what this pins is that a short press produces the layout message and
        # NOT a category change (the server side of layout_focus is
        # tests/test_layout_protocol.py's job).
        stepped = page.evaluate("""() => {
            const real = window.send;
            const sent = [];
            window.send = (m) => sent.push(m);
            layouts = [{name: 'A'}, {name: 'B'}];
            layoutActive = null;
            const before = groups.right;
            __padButton('r1', true);
            __padButton('r1', false);   // a tap: no stick, no waiting
            window.send = real;
            layouts = [];
            layoutActive = null;
            hideLayLoading();
            return {sent, before, after: groups.right};
        }""")
        results["pad: a short shoulder tap steps the layout bar"] = (
            len(stepped["sent"]) == 1 and
            stepped["sent"][0]["type"] == "layout_focus" and
            stepped["sent"][0]["index"] == 0 and
            stepped["before"] == stepped["after"])

        # 10h. A pad press holds the SCREEN awake. It is neither a touch nor a
        # keydown — the shell claims it at dispatchKeyEvent and hands it to the
        # page through evaluateJavascript — so the two listeners in
        # connection.js never hear it, and a session driven entirely from the
        # controller would go dark after KEEP_AWAKE_MS, hide the page, and have
        # the PC correctly pack the layout away mid-work.
        results["pad: activity holds the screen awake"] = page.evaluate("""() => {
            awakeUntil = 0;
            padAwakeAt = -Infinity;     // open the throttle, whatever it just did
            __padButton('l1', true);    // no layouts exist: this only opens the wheel
            __padButton('l1', false);
            return awakeUntil > 0;
        }""")

        browser.close()

    # ── PHONE → PC CONTENT: a picture missing its tail is still a picture ──
    # Owner report 2026-08-09: he sent an image from the tablet, the loading
    # animation ran, and nothing arrived. His own log named it — Pillow refused
    # 717,894 bytes of ordinary JPEG over "image file is truncated (5 bytes not
    # processed)", and the OpenCV fallback (which is only there for formats
    # Pillow does not KNOW) refused it too. Three uploads died that way.
    #
    # This belongs in the INPUT gate: an upload is phone → PC → Ctrl+V, the
    # same pipeline by a different door.
    import io as _io
    sys.path.insert(0, str(PROJECT / "server"))
    import content as _content
    from PIL import Image as _Image

    _buf = _io.BytesIO()
    _Image.new("RGB", (640, 480), (200, 60, 40)).save(_buf, "JPEG", quality=92)
    _whole = _buf.getvalue()
    results["upload: a whole JPEG decodes"] = _content.decode_upload(_whole) is not None
    # EXACTLY his failure: five bytes short.
    results["upload: a JPEG five bytes short still decodes"] = (
        _content.decode_upload(_whole[:-5]) is not None)
    # …and it must still be a picture, not anything at all.
    results["upload: something that is not an image is still refused"] = (
        _content.decode_upload(b"this is not an image") is None)

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
