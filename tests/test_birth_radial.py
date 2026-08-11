"""BIRTH RADIAL GATE — how a layout is born, on the phone (tasks 186, 184, 185).

Three owner rulings land on one component and they are only worth anything
together:

* **186+228** — the Layout button's radial holds FOUR options now (New / List
  / Tap / Recent) and stands CENTERED, the category wheel's own rule ("najbolje da se
  držimo istog pravila" — lang-ok: owner quote). On the pad it is L2: a TAP
  arms the tap-pick, a HOLD opens this same radial with the stick pointing at
  it and the release confirming — the grammar L1/R1 already speak.
* **184** — the third option, New, asks the PC what it can open.
* **185** — a window he just opened arrives as a chip, and his yes lands in the
  creation panel he already knows, pre-seeded.

WHY A LIVE PAGE. Every claim here is about laid-out pixels or about a listener
that only exists once the page is running: where three options sit on a ring,
whether a veil paints over the buttons it is meant to sit behind, and whether
the pad's release really runs the very handler a finger's tap runs. The
`test_phone_chrome.py` pattern is reused wholesale — same server, same
Chromium, same three sizes.

THE ONE THING THAT IS FAKED is `fetch`: the gate server builds the app through
`create_app`, and `/recents` is registered at the composition root beside the
other routes (server/server_core.py), so it does not exist here. The check
therefore proves what this side owns — that the New option really ASKS the PC
(the URL it calls) and really draws what comes back. What the PC answers is
`tests/test_layout_birth.py`'s subject, on the real module.

Run:  .venv\\Scripts\\python tests/test_birth_radial.py
Requires the same toolchain as the input gate (playwright + chromium).
"""

import socket
import sys
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(PROJECT / "server"))

SIZES = [("portrait 412x915", 412, 915), ("landscape 915x412", 915, 412),
         ("tablet landscape 1280x800", 1280, 800)]

# What the PC would answer /recents with. Two apps, one of them carrying
# recents and one carrying only what it can honestly do — the shape
# server/recents.py really produces.
FAKE_RECENTS = """() => {
  window.__asked = [];
  window.fetch = async (url, opts) => {
    window.__asked.push(url);
    if (url.indexOf('/recents/open') === 0) {
      return {json: async () => ({ok: true, window: {
        hwnd: 4660, title: 'Vibe Coder - Visual Studio Code',
        process: 'Code.exe', icon: null}})};
    }
    return {json: async () => ({ok: true, entries: [
      {app: 'vscode', kind: 'new', label: 'New window', sub: '',
       id: 'vscode|new|'},
      {app: 'vscode', kind: 'recent', label: 'Vibe Coder',
       sub: 'U:\\\\Coding\\\\Vibe Coder', id: 'vscode|recent|U:\\\\Coding'},
      {app: 'chrome', kind: 'new', label: 'New window', sub: '',
       id: 'chrome|new|'},
      {app: 'chrome', kind: 'private', label: 'Incognito', sub: '',
       id: 'chrome|private|'}]})};
  };
}"""


def _checks(page, label, out):
    # ── 186: THREE OPTIONS, ON A RING, IN THE MIDDLE OF THE SCREEN ───────────
    # Catches (proven by planting): dropping the `{centered: true}` flag (the
    # options fall back beside the corner button, where a third one is clamped
    # onto its sibling), spreading them at any angles but the wheel's (the pad
    # would then point at the wrong one), or losing the ✕.
    ring = page.evaluate("""() => {
      const bad = [];
      openSourceChooser();
      const items = [...document.querySelectorAll('#mini-radial .mini-item')];
      if (items.length !== 4) {
        closeMiniRadial();
        return ['the Layout button offered ' + items.length + ' sources, not 4'];
      }
      const cx = innerWidth / 2, cy = innerHeight / 2;
      const c = items.map((el) => {
        const r = el.getBoundingClientRect();
        return {x: r.left + r.width / 2, y: r.top + r.height / 2, r};
      });
      // Item 0 is straight UP and the rest sweep clockwise — the wheel's own
      // placement, which is what makes the pad's pointing arithmetic reusable.
      const ang = c.map((p) => Math.atan2(p.y - cy, p.x - cx));
      const want = [0, 1, 2, 3].map((i) => -Math.PI / 2 + i * 2 * Math.PI / 4);
      ang.forEach((a, i) => {
        // Signed shortest angle between the two, wrapped into (-PI, PI].
        const d = ((a - want[i] + Math.PI * 3) % (Math.PI * 2)) - Math.PI;
        if (Math.abs(d) > 0.08) {
          bad.push('option ' + i + ' sits at ' + a.toFixed(2) +
                   ' rad, not the wheel\\'s ' + want[i].toFixed(2));
        }
      });
      // Equidistant from the centre, and really centred on the SCREEN.
      const radii = c.map((p) => Math.hypot(p.x - cx, p.y - cy));
      if (Math.max(...radii) - Math.min(...radii) > 2) {
        bad.push('the four are not on one ring: ' + radii.map(Math.round));
      }
      if (radii[0] < 40) bad.push('the ring has collapsed onto the centre');
      for (const item of items) {
        const r = item.getBoundingClientRect();
        if (r.left < 0 || r.top < 0 || r.right > innerWidth || r.bottom > innerHeight) {
          bad.push('an option opened off the screen at ' + JSON.stringify(
            {l: Math.round(r.left), t: Math.round(r.top),
             r: Math.round(r.right), b: Math.round(r.bottom)}));
        }
        if (!item.querySelector('svg')) bad.push('an option carries no drawing');
        const lbl = item.querySelector('.lbl');
        const word = lbl ? lbl.textContent.trim() : '';
        if (!word) bad.push('an option carries no word');
        // HIS RULING: ONE WORD each (task 184, ~20:25).
        if (word.split(/\\s+/).length !== 1) {
          bad.push('"' + word + '" is not one word');
        }
      }
      if (!document.querySelector('#mini-radial .wheel-x')) {
        bad.push('there is no ✕ in the middle — the radial cannot be cancelled ' +
                 'by anything but the backdrop');
      }
      closeMiniRadial();
      return bad;
    }""")
    out[f"the birth radial is four options on the wheel's ring @ {label}"] = not ring
    if ring:
        print(f"  DETAIL birth radial @ {label}: {ring}")

    # ── 186: THE VEIL SITS *UNDER* THE CONTROLS ──────────────────────────────
    # Catches: painting the dim on `#mini-radial` itself. That element is
    # z-index 36 and the options are its children, so the veil would go BEHIND
    # the very buttons it must not touch — the measured contrast failure that
    # moved the wheel's own veil to its own layer (client/style.css).
    veil = page.evaluate("""() => {
      const bad = [];
      openSourceChooser();
      if (!document.body.classList.contains('mini-open')) {
        bad.push('the centered radial raises no veil at all');
      }
      const own = getComputedStyle(document.getElementById('mini-radial'))
        .backgroundColor;
      if (own !== 'rgba(0, 0, 0, 0)' && own !== 'transparent') {
        bad.push('the radial paints its own background (' + own + '), which ' +
                 'lands UNDER the options and takes their contrast with it');
      }
      const layer = getComputedStyle(document.body, '::before');
      const bg = layer.backgroundColor;
      if (layer.content === 'none' || bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') {
        bad.push('the veil layer paints nothing (content=' + layer.content +
                 ', background=' + bg + ')');
      }
      if (!(parseInt(layer.zIndex, 10) < 20)) {
        bad.push('the veil is at z-index ' + layer.zIndex + ', at or above ' +
                 'the controls (20)');
      }
      closeMiniRadial();
      if (document.body.classList.contains('mini-open')) {
        bad.push('the veil outlived the radial');
      }
      return bad;
    }""")
    out[f"the veil sits under the controls, not over them @ {label}"] = not veil
    if veil:
        print(f"  DETAIL veil @ {label}: {veil}")

    # ── 186: L2 HELD, POINTED, RELEASED — THE L1/R1 GRAMMAR ──────────────────
    # Catches: mapping L2 back to a plain corner press (no radial at all),
    # confirming on the press instead of the release, or picking something when
    # the stick was never moved. The pick is observed through the REAL option
    # element, so a controller-only option list could not pass this.
    pad = page.evaluate("""() => {
      const bad = [];
      const open = () => document.querySelectorAll('#mini-radial .mini-item').length;
      // 1. HOLD opens it.
      window.__padButton('l2', true);
      if (open() !== 4) bad.push('holding L2 did not open the radial');
      // 2. The stick POINTS: straight up is option 0, and it lights.
      window.__padAxis(0, -1, 0, 0);
      const lit = [...document.querySelectorAll('#mini-radial .mini-item')]
        .findIndex((el) => el.classList.contains('current'));
      if (lit !== 0) bad.push('pointing up lit option ' + lit + ', not 0');
      // 3. RELEASE confirms — the option's own handler runs.
      let ran = null;
      const items = [...document.querySelectorAll('#mini-radial .mini-item')];
      const real = items[0].__miniPick;
      items[0].__miniPick = () => { ran = 'yes'; closeMiniRadial(); };
      window.__padButton('l2', false);
      items[0].__miniPick = real;
      if (ran !== 'yes') bad.push('releasing on an option did not run it');
      if (open()) bad.push('the radial stayed open after the release');
      window.__padAxis(0, 0, 0, 0);

      // 4. RELEASING AT NOTHING CHANGES NOTHING — his rule, verbatim.
      creating = null; layoutArm = false;
      window.__padButton('l2', true);
      const before = performance.now();
      while (performance.now() - before < 400) { /* past PAD_TAP_MS */ }
      window.__padButton('l2', false);
      if (open()) bad.push('a long hold released at nothing left the radial up');
      if (creating || layoutArm) {
        bad.push('a long hold released at nothing started a creation anyway');
      }

      // 5. A TAP is the tap-pick, exactly as the button did before the radial.
      window.__padButton('l2', true);
      window.__padButton('l2', false);
      if (open()) bad.push('a tap opened the radial instead of arming the pick');
      if (!layoutArm) bad.push('a tap did not arm the tap-pick');
      // …and a second tap cancels, which is the only way out on a pad.
      window.__padButton('l2', true);
      window.__padButton('l2', false);
      if (layoutArm || creating) bad.push('a second tap did not cancel');
      return bad;
    }""")
    out[f"L2 taps, holds, points and releases @ {label}"] = not pad
    if pad:
        print(f"  DETAIL L2 grammar @ {label}: {pad}")
    page.evaluate("cancelCreation(true)")

    # ── 184: NEW ASKS THE PC, AND DRAWS WHAT COMES BACK ──────────────────────
    # Catches: a New option that opens nothing, one that never calls the PC
    # (the whole feature), or a list that drops the app grouping — a flat list
    # of "New window" rows names neither app.
    page.evaluate(FAKE_RECENTS)
    page.evaluate("openSourceChooser()")
    # A MISSING OPTION IS A FAILING CHECK, NOT A CRASHING GATE. Reaching
    # straight into `.find(...)` threw a TypeError out of `page.evaluate` when
    # the New option was removed, which killed the whole run and printed no
    # verdict at all — a gate whose failure mode is a traceback cannot be read
    # by whoever comes next.
    picked = page.evaluate("""() => {
      const items = [...document.querySelectorAll('#mini-radial .mini-item')];
      const el = items.find((i) => i.querySelector('.lbl').textContent.trim() === 'New');
      if (!el) return false;
      el.__miniPick();
      return true;
    }""")
    out[f"the radial carries a New option at all @ {label}"] = picked
    if not picked:
        print(f"  DETAIL New source @ {label}: the radial has no New option")
        page.evaluate("closeMiniRadial()")
        out[f"New asks the PC and draws its answer @ {label}"] = False
        out[f"the window it opened becomes the slot @ {label}"] = False
        return
    page.wait_for_selector("#layout-panel .lay-card", state="visible", timeout=4000)
    page.wait_for_timeout(120)
    new = page.evaluate("""() => {
      const bad = [];
      if (!window.__asked.some((u) => u.indexOf('/recents?token=') === 0)) {
        bad.push('New never asked the PC what it can open: ' +
                 JSON.stringify(window.__asked));
      }
      const rows = [...document.querySelectorAll('#layout-panel .lay-item')];
      if (rows.length !== 4) bad.push('the list drew ' + rows.length + ' rows, not 4');
      const text = document.querySelector('#layout-panel .lay-card').textContent;
      for (const app of ['VS Code', 'Chrome']) {
        if (text.indexOf(app) < 0) bad.push('the list never names ' + app);
      }
      if (!rows.every((r) => r.querySelector('.lay-item-main svg'))) {
        bad.push('a row carries no drawn app face');
      }
      // A recent row is indented under its app's heading, a new-window row is
      // not — the same column a tab takes under its window (task 168).
      const kid = rows.filter((r) => r.classList.contains('lc-kid'));
      if (kid.length !== 1) bad.push(kid.length + ' rows are indented, expected 1');
      return bad;
    }""")
    out[f"New asks the PC and draws its answer @ {label}"] = not new
    if new:
        print(f"  DETAIL New source @ {label}: {new}")

    # …and tapping a row opens it and lands in the creation panel with a slot.
    # Catches: an opened window that never becomes a member (the whole point of
    # task 184 — "the chosen thing OPENS and becomes the member").
    page.evaluate("""() => {
      const row = [...document.querySelectorAll('#layout-panel .lay-item-main')]
        .find((r) => r.textContent.indexOf('Vibe Coder') >= 0);
      // Task 227b moved row selection to RELEASE under a travel slop, driven
      // by real pointer events — so the gate presses the way a finger does,
      // not through the button activator.
      const b = row.getBoundingClientRect();
      const ev = (type, x, y) => row.dispatchEvent(new PointerEvent(type, {
        bubbles: true, isPrimary: true, pointerId: 5, clientX: x, clientY: y}));
      ev('pointerdown', b.left + 10, b.top + 10);
      ev('pointerup', b.left + 11, b.top + 10);
    }""")
    page.wait_for_timeout(250)
    seeded = page.evaluate("""() => {
      const bad = [];
      if (!window.__asked.some((u) => u.indexOf('/recents/open') === 0)) {
        bad.push('tapping a recent never asked the PC to open it');
      }
      if (!creating || creating.slots.length !== 1) {
        bad.push('the opened window did not become a slot: ' +
                 JSON.stringify(creating && creating.slots));
      } else if (creating.slots[0].hwnd !== 4660) {
        bad.push('the slot is not the window the PC opened');
      }
      const card = document.querySelector('#layout-panel .lay-card');
      if (!card || card.textContent.indexOf('New layout') < 0) {
        bad.push('it did not land in the creation panel');
      }
      return bad;
    }""")
    out[f"the window it opened becomes the slot @ {label}"] = not seeded
    if seeded:
        print(f"  DETAIL New slot @ {label}: {seeded}")
    page.evaluate("cancelCreation(true)")

    # ── 185: THE CHIP ASKS THE OTHER QUESTION, AND YES SEEDS THE PANEL ───────
    # Catches: one set of words for both questions ("Show in layout" about a
    # window that is in no layout), or a yes that answers the PC without ever
    # opening the panel — the half that makes it a feature.
    birth = page.evaluate("""() => {
      const bad = [];
      showWindowOffer({id: 'b1', act: 'layout_new', hwnd: 4661,
                       title: 'Budget.xlsx - Excel', process: 'EXCEL.EXE'});
      const chip = document.getElementById('window-offer');
      if (chip.hidden) return ['the chip never appeared'];
      const text = document.getElementById('window-offer-text').textContent;
      if (text.indexOf('Budget.xlsx') < 0) bad.push('the chip does not name it');
      if (text.indexOf('layout') < 0) bad.push('the chip does not ask the question');
      const yes = document.getElementById('window-offer-in').textContent;
      if (/Show in layout/.test(yes)) {
        bad.push('it still asks task 202\\'s question: "' + yes + '"');
      }
      document.getElementById('window-offer-in').click();
      if (!chip.hidden) bad.push('the chip stayed up after the answer');
      if (!creating || creating.slots.length !== 1 ||
          creating.slots[0].hwnd !== 4661) {
        bad.push('yes did not seed the creation panel: ' +
                 JSON.stringify(creating && creating.slots));
      }
      const card = document.querySelector('#layout-panel .lay-card');
      if (!card || card.textContent.indexOf('New layout') < 0) {
        bad.push('the creation panel never opened');
      }
      return bad;
    }""")
    out[f"an app that opened asks its own question @ {label}"] = not birth
    if birth:
        print(f"  DETAIL birth chip @ {label}: {birth}")
    page.evaluate("cancelCreation(true); hideWindowOffer()")


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
                            "Mobile Safari/537.36 VibeCoderApp"))
            page = ctx.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
            page.wait_for_selector("#group-left button", timeout=8000)
            page.wait_for_function("() => monitor.w > 0", timeout=10000)
            _checks(page, label, results)
            results[f"no page errors @ {label}"] = not errors
            if errors:
                print(f"  DETAIL page errors @ {label}: {errors}")
            ctx.close()
        browser.close()

    print("\n=== BIRTH RADIAL GATE ===")
    failed = 0
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    if failed:
        print(f"\nBIRTH RADIAL GATE FAILED — {failed} check(s).", file=sys.stderr)
        return 1
    print("\nBIRTH RADIAL GATE PASSED — four sources on one ring, the pad "
          "speaks the grammar it already knows, and a window that opens can "
          "become a layout.")
    return 0


def test_birth_radial():
    """pytest entry — skipped where the browser toolchain is absent."""
    import pytest
    pytest.importorskip("playwright.sync_api")
    pytest.importorskip("uvicorn")
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
