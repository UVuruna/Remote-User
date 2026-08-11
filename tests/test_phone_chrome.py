"""Gate: the phone's TOP ROW and the two-job buttons — tasks 155, 158, 159, 160.

Four owner rulings of 2026-08-09 land on the same strip of screen, and none of
them could be proven by the panel audit next door: that sweep opens CARDS and
measures their insides, while everything here is about the chrome itself — where
a button's options appear, whether a hidden control comes back, and whether the
bar between the two corners is built like them or unlike them.

Driven against the REAL page in a REAL headless Chromium, like the audit and the
input gate, because every one of these is a claim about laid-out pixels or about
a listener that only exists on a live page. Each check below is written so that
removing the line of product code it guards makes it FAIL — the planted-defect
discipline; the defect each one catches is named in its own docstring.

Run:  .venv\\Scripts\\python tests/test_phone_chrome.py
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

# The panel CATALOGUE the layout audit stages from — reused, never re-typed:
# the dictation card's long language list is what makes task 217's scroll
# question answerable at all, and a second copy of it here would go stale.
from _audit_panels import DICT_STAGE_JS, LAYOUT_LIST_STAGE_JS  # noqa: E402

# Both orientations, and a tablet: task 160's bottom position has to clear a
# D-pad group whose HEIGHT differs between the cross and the column, and those
# two shapes are what the orientations render by default.
SIZES = [("portrait 412x915", 412, 915), ("landscape 915x412", 915, 412),
         ("tablet landscape 1280x800", 1280, 800)]

# Two layouts, so the bar is not hidden (`updateLayoutBar` hides it when there
# are none) and the list has rows to draw.
STAGE_LAYOUTS = (
    "layouts = ["
    " {name:'Claude', process:'code', orient:'landscape', icon:null,"
    "  ratio:null, pos:0.5, members:1, grid:null},"
    " {name:'Mail', process:'chrome', orient:'landscape', icon:null,"
    "  ratio:null, pos:0.5, members:1, grid:null}];"
    "layoutActive = 0; updateLayoutBar()"
)

# TWO monitors of different sizes — task 155's rows exist only above one, and a
# fixture with two identical monitors could not tell "it printed the resolution"
# from "it printed the same string twice".
STAGE_MONITORS = (
    "monitorList = [{index:0, width:3840, height:2160, primary:true},"
    "               {index:1, width:1920, height:1080, primary:false}];"
    "monitorIndex = 0"
)


# Every panel that REFLOWS in landscape, opened in a state long enough to need
# scrolling. `openLayoutSettings` / `openMemberPanel` / `openCloseChooser` need
# a staged list, so they carry it.
REFLOWING_PANELS = [
    ("Dictation card", "#dictation-panel .sets-card", "closeDictationPanel()"),
    ("Sets picker", "#sets-panel .sets-card", "closeSetsPanel()"),
    ("Quality panel", "#quality-panel .sets-card", "closeQualityPanel()"),
    ("Layout list", "#layout-panel .lay-card", "closeLayoutPanel()"),
    ("Creation card", "#layout-panel .lay-card", "cancelCreation(true)"),
    ("Layout settings sheet", "#layout-panel .lay-card", "closeLayoutPanel()"),
    ("Member chooser", "#layout-panel .lay-card", "closeLayoutPanel()"),
    ("Close chooser", "#layout-panel .lay-card", "closeLayoutPanel()"),
]

# THE BOTTOM BUTTON IS REACHABLE, AFTER SCROLLING WHATEVER CAN SCROLL.
# Catches (proven by removing the two lines it guards in client/panels.css —
# the dictation card then overflowed SIDEWAYS by 742 px at 915x412 and its Done
# button could not be reached by any vertical gesture, which is his report of
# task 217 exactly): a `column-count` card with a definite height is a
# FRAGMENTAINER — it answers "out of room" by making another COLUMN, so
# `scrollHeight` never exceeds `clientHeight`, `overflow-y: auto` has nothing to
# do, and the rest of the card sits off to the right.
REACH_JS = """(sel) => {
  const card = document.querySelector(sel);
  const btns = [...card.querySelectorAll('button')];
  if (!btns.length) return ['the card has no buttons at all'];
  const t = btns[btns.length - 1];
  for (let n = t; n && n !== document.body; n = n.parentElement) {
    const s = getComputedStyle(n);
    if (/(auto|scroll)/.test(s.overflowY) && n.scrollHeight > n.clientHeight + 1) {
      n.scrollTop = n.scrollHeight;
    }
  }
  const r = t.getBoundingClientRect();
  const bad = [];
  const sideways = card.scrollWidth - card.clientWidth;
  if (sideways > 1) {
    bad.push('the card overflows SIDEWAYS by ' + sideways + 'px — a capped ' +
             'multicol makes another COLUMN instead of a taller box, and no ' +
             'vertical gesture can ever reach it');
  }
  if (r.bottom > innerHeight + 1 || r.top < -1 ||
      r.right > innerWidth + 1 || r.left < -1) {
    bad.push('"' + t.textContent.trim().slice(0, 16) + '" is still off the ' +
             'screen after scrolling everything that scrolls: ' +
             JSON.stringify({top: Math.round(r.top), bottom: Math.round(r.bottom),
                             right: Math.round(r.right), w: innerWidth,
                             h: innerHeight}));
  }
  return bad;
}"""


def _reflow_checks(page, label, out, stage_layouts, stage_dict):
    """Task 217 (owner 2026-08-10) — and task 215's standing order with it: the
    content is staged long enough to REQUIRE scrolling, because a panel that
    never scrolls proves nothing about scrolling."""
    openers = {
        "Dictation card": stage_dict,
        "Sets picker": "openSetsPanel()",
        "Quality panel": ("setStreamBase({fps:10, width:3840, height:2160,"
                          " bitrate:'6M', bitrate_mid:'2400k',"
                          " bitrate_low:'600k'}); openQualityPanel()"),
        "Layout list": stage_layouts,
        "Creation card": None,     # staged by the caller's own creation fixture
        "Layout settings sheet": stage_layouts + "; openLayoutSettings(0)",
        "Member chooser": stage_layouts + "; openMemberPanel(2)",
        "Close chooser": stage_layouts + "; openCloseChooser(0)",
    }
    for name, sel, close_js in REFLOWING_PANELS:
        open_js = openers.get(name)
        if open_js is None:
            continue
        page.evaluate(open_js)
        page.wait_for_selector(sel, state="visible", timeout=4000)
        page.wait_for_timeout(120)
        bad = page.evaluate(REACH_JS, sel)
        out[f"{name}: its bottom button is reachable @ {label}"] = not bad
        if bad:
            print(f"  DETAIL {name} @ {label}: {bad}")
        page.evaluate(close_js)
        page.wait_for_timeout(60)


def _checks(page, label, out):
    # ── 160: THE BAR IS BUILT LIKE THE CORNERS ───────────────────────────────
    # Catches: reverting #lay-frame / .lay-arrow to their old 34px, 14px-radius,
    # background-less shape — the exact "it has a different style, different
    # height" he reported.
    page.evaluate(STAGE_LAYOUTS)
    page.wait_for_timeout(80)
    same = page.evaluate("""() => {
      const bad = [];
      const corner = document.getElementById('btn-hide');
      const cr = corner.getBoundingClientRect();
      const cs = getComputedStyle(corner);
      const rad = (el) => parseFloat(getComputedStyle(el).borderTopLeftRadius);
      for (const sel of ['#lay-frame', '#lay-prev', '#lay-next']) {
        const el = document.querySelector(sel);
        const r = el.getBoundingClientRect();
        if (Math.abs(r.height - cr.height) > 1) {
          bad.push(sel + ' is ' + Math.round(r.height) + 'px tall beside a ' +
                   Math.round(cr.height) + 'px corner button');
        }
        if (Math.abs(rad(el) - rad(corner)) > 0.5) {
          bad.push(sel + ' carries a ' + rad(el) + 'px radius beside the ' +
                   'corner button\\'s ' + rad(corner) + 'px');
        }
        const bg = getComputedStyle(el).backgroundColor;
        if (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent') {
          bad.push(sel + ' has no fill of its own — it stands on the bare ' +
                   'stream while the buttons beside it are surfaces');
        }
        if (getComputedStyle(el).borderTopWidth !== cs.borderTopWidth) {
          bad.push(sel + ' does not wear the corner button\\'s border');
        }
      }
      return bad;
    }""")
    out[f"the layout bar wears the top row's own style @ {label}"] = not same
    if same:
        print(f"  DETAIL bar style @ {label}: {same}")

    # ── 160: AT THE BOTTOM IT STANDS CLEAR OF THE D-PAD ──────────────────────
    # Catches: pinning the bottom position to the screen edge (or dropping
    # --group-h from the calc) — the bar would then be drawn straight across the
    # two control groups, which on a 412px phone meet in the middle.
    clear = page.evaluate("""() => {
      setLayBarPos('bottom');
      const bar = document.getElementById('layout-bar').getBoundingClientRect();
      const bad = [];
      if (bar.bottom > innerHeight + 1 || bar.top < 0) {
        bad.push('the bar left the screen: ' + JSON.stringify(
          {top: Math.round(bar.top), bottom: Math.round(bar.bottom),
           h: innerHeight}));
      }
      // It must really have MOVED — a pref nothing reads would pass a pure
      // overlap test forever.
      const topPos = document.getElementById('layout-bar');
      for (const g of document.querySelectorAll('.group')) {
        const r = g.getBoundingClientRect();
        if (bar.left < r.right && r.left < bar.right &&
            bar.top < r.bottom && r.top < bar.bottom) {
          bad.push('the bar overlaps a D-pad group');
        }
      }
      setLayBarPos('top');
      const back = topPos.getBoundingClientRect();
      if (back.top >= bar.top - 1) {
        bad.push('the position setting does nothing — bottom sat at ' +
                 Math.round(bar.top) + ', top at ' + Math.round(back.top));
      }
      return bad;
    }""")
    out[f"the bar at the bottom clears the D-pad @ {label}"] = not clear
    if clear:
        print(f"  DETAIL bar bottom @ {label}: {clear}")

    # ── 158: THE RADIAL IS SOUTH AND SOUTH-EAST, DRAWN AND LABELLED ──────────
    # Catches: spreading the options around a ring (his geometry is for the
    # analog stick), dropping the icon or the label (his "with a picture and
    # with text"), or letting an option open off the screen.
    radial = page.evaluate("""() => {
      const bad = [];
      const btn = document.getElementById('btn-newlay');
      const b = btn.getBoundingClientRect();
      openSourceChooser();
      const items = [...document.querySelectorAll('#mini-radial .mini-item')];
      if (items.length !== 2) {
        closeMiniRadial();
        return ['the Layout button offered ' + items.length + ' options, not 2'];
      }
      const c = items.map((el) => {
        const r = el.getBoundingClientRect();
        return {x: r.left + r.width / 2, y: r.top + r.height / 2, r};
      });
      const bx = b.left + b.width / 2, by = b.top + b.height / 2;
      if (!(c[0].y > by + 40)) bad.push('the first option is not SOUTH of the button');
      if (Math.abs(c[0].x - bx) > 2) bad.push('the first option is not straight below it');
      if (!(c[1].y > by + 20)) bad.push('the second option is not below the button');
      if (!(Math.abs(c[1].x - bx) > 20)) {
        bad.push('the second option is not DIAGONAL — the two directions a ' +
                 'stick has to tell apart are the same direction');
      }
      for (const item of items) {
        const r = item.getBoundingClientRect();
        if (r.left < 0 || r.top < 0 || r.right > innerWidth || r.bottom > innerHeight) {
          bad.push('an option opened off the screen');
        }
        if (!item.querySelector('svg')) bad.push('an option carries no drawing');
        const lbl = item.querySelector('.lbl');
        if (!lbl || !lbl.textContent.trim()) bad.push('an option carries no words');
      }
      // Kin: the two options are the same kind in one container.
      if (Math.abs(c[0].r.width - c[1].r.width) > 1 ||
          Math.abs(c[0].r.height - c[1].r.height) > 1) {
        bad.push('the two options are different sizes');
      }
      closeMiniRadial();
      return bad;
    }""")
    out[f"the Layout radial drops south and south-east @ {label}"] = not radial
    if radial:
        print(f"  DETAIL layout radial @ {label}: {radial}")

    # ── 158: ON THE RIGHT HALF IT LEANS THE OTHER WAY ────────────────────────
    # Catches: a fixed south-east — Hide sits in the top-RIGHT corner, so the
    # diagonal option would be clamped onto its sibling or off the screen.
    lean = page.evaluate("""() => {
      const btn = document.getElementById('btn-hide');
      const b = btn.getBoundingClientRect();
      openHideModes();
      const items = [...document.querySelectorAll('#mini-radial .mini-item')];
      const bad = [];
      if (items.length !== 2) bad.push('Hide offered ' + items.length + ' modes');
      else {
        const bx = b.left + b.width / 2;
        const x1 = items[1].getBoundingClientRect();
        if (x1.left + x1.width / 2 > bx - 20) {
          bad.push('the diagonal option did not lean AWAY from the right edge');
        }
        if (x1.right > innerWidth) bad.push('the diagonal option is off the screen');
        // The mode he is already in has to be readable, or the radial only
        // offers and never says.
        if (![...items].some((el) => el.classList.contains('active'))) {
          bad.push('neither mode is shown as the current one');
        }
      }
      closeMiniRadial();
      return bad;
    }""")
    out[f"the Hide radial leans away from the edge @ {label}"] = not lean
    if lean:
        print(f"  DETAIL hide radial @ {label}: {lean}")

    # ── 159: THE TWO HIDE MODES REALLY DIFFER ────────────────────────────────
    # Catches: `sticky` not being read by wakeControls (a touch would bring the
    # controls back and the mode would be a stored word that does nothing —
    # exactly the class of bug the wheel_order field was), or `auto` being
    # broken by the change (the mode that has always shipped).
    modes = page.evaluate("""() => {
      const bad = [];
      const hidden = () => document.body.classList.contains('hidden-controls');
      setHideMode('auto');
      setControlsHidden(true);
      wakeControls();
      if (hidden()) bad.push('in AUTO mode a touch did not bring the controls back');
      setHideMode('sticky');
      setControlsHidden(true);
      wakeControls();
      if (!hidden()) bad.push('in STICKY mode a touch unhid the controls');
      // …and the Hide button is still the way out of sticky.
      const btn = document.getElementById('btn-hide');
      buttonPress(btn, true); buttonPress(btn, false);
      if (hidden()) bad.push('in STICKY mode the Hide button could not unhide');
      // …and sticky never hides by itself either.
      setHideMode('sticky');
      setControlsHidden(false);
      lastWake = performance.now() - AUTO_HIDE_MS - 500;
      setHideMode('auto');
      setControlsHidden(false);
      return bad;
    }""")
    page.wait_for_timeout(60)
    out[f"the two Hide modes differ @ {label}"] = not modes
    if modes:
        print(f"  DETAIL hide modes @ {label}: {modes}")

    sticky = page.evaluate("""() => {
      setHideMode('sticky');
      setControlsHidden(false);
      lastWake = performance.now() - AUTO_HIDE_MS - 500;
      return true;
    }""")
    page.wait_for_timeout(400)     # comfortably past one auto-hide tick
    out[f"STICKY never hides by itself @ {label}"] = sticky and not page.evaluate(
        "document.body.classList.contains('hidden-controls')")
    page.evaluate("setHideMode('auto'); setControlsHidden(false); wakeControls()")

    # ── 155: ONE ROW PER MONITOR, EACH NAMING ITS RESOLUTION ─────────────────
    # Catches: the single Desktop row surviving above one monitor, a row that
    # names no size (the whole point — "Monitor 1 and that resolution"), or the
    # row for the monitor already on screen not being the selected one.
    page.evaluate(STAGE_MONITORS + "; layoutActive = null; openLayoutPicker()")
    page.wait_for_selector("#layout-panel .lay-card", state="visible", timeout=4000)
    mons = page.evaluate("""() => {
      const bad = [];
      const rows = [...document.querySelectorAll('#layout-panel .lay-item')];
      const text = rows.map((r) => r.textContent.trim());
      const named = text.filter((t) => /^Monitor \\d/.test(t));
      if (named.length !== 2) {
        bad.push('the list drew ' + named.length + ' monitor rows for 2 monitors: ' +
                 JSON.stringify(text));
      }
      if (!named.some((t) => t.includes('3840') && t.includes('2160'))) {
        bad.push('no row names the 4K monitor\\'s resolution: ' + JSON.stringify(named));
      }
      if (!named.some((t) => t.includes('1920') && t.includes('1080'))) {
        bad.push('no row names the second monitor\\'s resolution');
      }
      if (text.some((t) => t.startsWith('Desktop'))) {
        bad.push('the old single Desktop row is still there beside the monitors');
      }
      const sel = rows.filter((r) => r.querySelector('.lay-item-main.sel'))
                      .map((r) => r.textContent.trim());
      if (sel.length !== 1 || !sel[0].includes('3840')) {
        bad.push('the monitor being streamed is not the selected row: ' +
                 JSON.stringify(sel));
      }
      return bad;
    }""")
    out[f"one row per monitor, each with its resolution @ {label}"] = not mons
    if mons:
        print(f"  DETAIL monitor rows @ {label}: {mons}")

    # …and tapping ANOTHER one asks for THAT index, not for "the next".
    # Catches: sending a bare `monitor_switch` again (the cycler), which on a
    # three-monitor PC would open the wrong screen.
    sent = page.evaluate("""() => {
      const seen = [];
      const real = window.send;
      window.send = (m) => seen.push(m);
      const rows = [...document.querySelectorAll('#layout-panel .lay-item')];
      const other = rows.find((r) => r.textContent.includes('1920'));
      buttonPress(other.querySelector('.lay-item-main'), true);
      buttonPress(other.querySelector('.lay-item-main'), false);
      window.send = real;
      return seen;
    }""")
    ok = (len(sent) == 1 and sent[0].get("type") == "monitor_switch"
          and sent[0].get("index") == 1)
    out[f"tapping a monitor row asks for THAT monitor @ {label}"] = ok
    if not ok:
        print(f"  DETAIL monitor tap @ {label}: {sent}")
    page.evaluate("closeLayoutPanel(); monitorList = []; layouts = [];"
                  " layoutActive = null; updateLayoutBar()")


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
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
            page.wait_for_selector("#group-left button", timeout=8000)
            page.wait_for_function("() => monitor.w > 0", timeout=10000)
            _checks(page, label, results)
            _reflow_checks(page, label, results, LAYOUT_LIST_STAGE_JS,
                           DICT_STAGE_JS)
            results[f"no page errors @ {label}"] = not errors
            if errors:
                print(f"  DETAIL page errors @ {label}: {errors}")
            ctx.close()
        browser.close()

    print("\n=== PHONE CHROME GATE ===")
    failed = 0
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    if failed:
        print(f"\nPHONE CHROME GATE FAILED — {failed} check(s).", file=sys.stderr)
        return 1
    print("\nPHONE CHROME GATE PASSED — the top row is one row, a two-job button "
          "drops its options where the stick will reach them, Hide has two real "
          "modes, and the desktop is a list of monitors.")
    return 0


def test_phone_chrome():
    """pytest entry — skipped where the browser toolchain is absent."""
    import pytest
    pytest.importorskip("playwright.sync_api")
    pytest.importorskip("uvicorn")
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
