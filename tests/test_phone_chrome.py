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
# HIDE_HOLD_MS is 380 in client/chrome.js; the wait gives the timer headroom.
HIDE_HOLD_WAIT_MS = 550

SIZES = [("portrait 412x915", 412, 915), ("landscape 915x412", 915, 412),
         ("tablet landscape 1280x800", 1280, 800),
         # Task 237, his sizing rule: a SECOND real device class — a 1280x800
         # tablet rotated upright — is the other half of the min-width proof.
         # His phone (412-class) must OVERFLOW the row; his tablet (800-class)
         # must FIT it between the D-pad columns. Neither claim is provable at
         # only one width.
         ("tablet portrait 800x1280", 800, 1280)]

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
      // THE ARROWS ARE DELIBERATELY *NOT* CORNER BUTTONS ANY MORE (owner
      // 2026-08-11, superseding his own task-160 ruling after seeing it): two
      // 58 px squares left the name nothing, and "not one letter" of it showed
      // on his phone. The FRAME still wears the top row's style — that half of
      // 160 was right and is what keeps the row reading as one row.
      for (const sel of ['#lay-frame']) {
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

    # ── 2026-08-11: THE NAME TAKES THE ROW, THE ARROWS TAKE ALMOST NONE ──────
    # His report on v0.0.107, with the screenshot: the bar showed not one
    # letter of the layout name. Catches (proven by restoring either half of
    # the shipped rule): arrows sized `var(--corner)` with a border and a fill,
    # or `#lay-frame` back to `flex: 0 1 auto` — with a long name, both put the
    # frame under 60% of the bar and the name under a readable width.
    page.evaluate("layouts[0].name = 'Vibe Coder — Applications — UVuruna';"
                  " updateLayoutBar()")
    page.wait_for_timeout(80)
    room = page.evaluate("""() => {
      const bad = [];
      const bar = document.getElementById('layout-bar').getBoundingClientRect();
      const frame = document.getElementById('lay-frame').getBoundingClientRect();
      const share = frame.width / bar.width;
      if (share < 0.6) {
        bad.push('the name frame is ' + Math.round(share * 100) + '% of the ' +
                 'bar — the arrows are eating the row he reads');
      }
      for (const sel of ['#lay-prev', '#lay-next']) {
        const a = document.querySelector(sel).getBoundingClientRect();
        if (a.width > 40) {
          bad.push(sel + ' is ' + Math.round(a.width) + 'px wide — his rule ' +
                   'is a big glyph in a very small footprint, not a button');
        }
        // …and the glyph itself stays big: shrinking the BOX is the fix, not
        // shrinking the arrow he has to hit.
        const svg = document.querySelector(sel + ' svg').getBoundingClientRect();
        if (svg.width < 24) {
          bad.push(sel + ' shrank its glyph to ' + Math.round(svg.width) + 'px');
        }
      }
      // The logo sits near the LEFT edge of the frame and the ✕ near the RIGHT
      // one — his words, and what the small inner padding buys.
      const pick = document.getElementById('lay-pick').getBoundingClientRect();
      const close = document.getElementById('lay-close').getBoundingClientRect();
      if (pick.left - frame.left > 12) {
        bad.push('the name starts ' + Math.round(pick.left - frame.left) +
                 'px inside the frame');
      }
      if (frame.right - close.right > 12) {
        bad.push('the ✕ stands ' + Math.round(frame.right - close.right) +
                 'px from the frame\\'s right edge');
      }
      // And something of the name is actually READ — the whole complaint.
      const name = document.getElementById('lay-name').getBoundingClientRect();
      if (name.width < 100) {
        bad.push('the name has ' + Math.round(name.width) + 'px to live in');
      }
      return bad;
    }""")
    out[f"the bar gives the row to the name @ {label}"] = not room
    if room:
        print(f"  DETAIL bar room @ {label}: {room}")

    # …AND IT SWITCHES BY SWIPE (owner 2026-08-11, the same report).
    # Catches: no swipe handler at all, or one that fires on a tap / on a
    # mostly-vertical drag, or one that lets the drag ALSO open the layout list
    # under its own finger.
    swipe = page.evaluate("""() => {
      const bad = [];
      const bar = document.getElementById('layout-bar');
      const r = bar.getBoundingClientRect();
      const y = r.top + r.height / 2;
      // Dispatched on the framed NAME, the one inner control a swipe is
      // likely to end on — so the last check below is a real question.
      const on = document.getElementById('lay-pick');
      const drag = (dx, dy) => {
        const at = (x, yy, type) => on.dispatchEvent(new PointerEvent(type, {
          clientX: x, clientY: yy, pointerId: 1, isPrimary: true,
          bubbles: true, cancelable: true}));
        const x0 = r.left + r.width / 2;
        at(x0, y, 'pointerdown');
        at(x0 + dx, y + dy, 'pointerup');
      };
      // The step is ASKED OF THE PC (`layout_focus`) — `layoutActive` only
      // moves when the server's own state frame comes back, so what is read
      // here is what really went out.
      layoutActive = 0;
      const seen = [];
      const real = window.send;
      window.send = (m) => seen.push(m);
      try {
        drag(-120, 0);
        if (seen.length !== 1 || seen[0].type !== 'layout_focus' ||
            seen[0].index !== 1) {
          bad.push('a swipe left did not step forward: ' + JSON.stringify(seen));
        }
        seen.length = 0;
        drag(120, 0);
        if (seen.length !== 1 || seen[0].index !== -1) {
          bad.push('a swipe right did not step back: ' + JSON.stringify(seen));
        }
        seen.length = 0;
        drag(10, 0);
        if (seen.length) bad.push('a tap-sized wobble stepped the layout');
        drag(60, 200);
        if (seen.length) bad.push('a mostly-vertical drag stepped it');
        // A real swipe must not ALSO open the list under the finger. (The
        // tap-sized wobble above legitimately DID open it — that is what a tap
        // on the framed name means — so the panel is closed first, or this
        // would be measuring the tap.)
        closeLayoutPanel();
        seen.length = 0;
        drag(-120, 0);
        if (!document.getElementById('layout-panel').hidden) {
          bad.push('the swipe opened the layout list as well');
        }
      } finally {
        window.send = real;
      }
      layoutActive = 0; updateLayoutBar();
      return bad;
    }""")
    out[f"a swipe on the bar switches layouts @ {label}"] = not swipe
    if swipe:
        print(f"  DETAIL bar swipe @ {label}: {swipe}")
    page.evaluate(STAGE_LAYOUTS)

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

    # ── 158 GOVERNS THE LAYOUT BUTTON AGAIN: AN ANCHORED FAN OF THREE ────────
    # The history matters, because this button has now worn three shapes and
    # only the last one may ship. Task 158 gave it two anchored options; task
    # 186 (with 228's fourth) moved it to a CENTERED ring behind the category
    # wheel's veil, four faces around a ✕; and on 2026-08-12 the owner reversed
    # that after living with it — the options belong BESIDE the button, like
    # Hide's two modes, and Recent leaves the radial altogether. So the
    # centered ring may now leave NO TRACE on this button, and the distinction
    # this check used to draw against Hide is inverted: BOTH radials are
    # anchored now, and what separates them is the COUNT and the directions
    # (Hide: two, S + SE-leaning-away; Layout: three, E / SE / S).
    # Catches: the centered ring coming back, a fourth option returning, and a
    # fan that is not really tied to the button it came out of.
    # The fan's exact angles, its no-overlap rule and the pad's grammar are
    # proven in full by tests/test_birth_radial.py; what is held HERE is that
    # this button's radial is the anchored one at all.
    radial = page.evaluate("""() => {
      const bad = [];
      const btn = document.getElementById('btn-newlay');
      const b = btn.getBoundingClientRect();
      openSourceChooser();
      const items = [...document.querySelectorAll('#mini-radial .mini-item')];
      if (items.length !== 3) {
        closeMiniRadial();
        return ['the Layout button offered ' + items.length + ' sources, not ' +
                'the three of 2026-08-12 (New / Tap / List)'];
      }
      const words = items.map((el) => el.querySelector('.lbl').textContent.trim());
      for (const want of ['New', 'Tap', 'List']) {
        if (words.indexOf(want) < 0) bad.push('no "' + want + '" option: ' + words);
      }
      if (words.indexOf('Recent') >= 0) {
        bad.push('Recent is back on the radial — he took it off on 2026-08-12');
      }
      const c = items.map((el) => {
        const r = el.getBoundingClientRect();
        return {x: r.left + r.width / 2, y: r.top + r.height / 2, r};
      });
      // ANCHORED: every option is in the button's own quadrant — right of it
      // and no higher than it — and none of them is on a ring around the
      // SCREEN's centre, which is the superseded task-186 shape.
      const bx = b.left + b.width / 2, by = b.top + b.height / 2;
      if (!c.every((p) => p.x >= bx - 1 && p.y >= by - 1)) {
        bad.push('an option opened outside the Layout button\\'s own quadrant: ' +
                 JSON.stringify(c.map((p) => [Math.round(p.x), Math.round(p.y)])));
      }
      const sx = innerWidth / 2, sy = innerHeight / 2;
      const ringR = c.map((p) => Math.hypot(p.x - sx, p.y - sy));
      if (Math.max(...ringR) - Math.min(...ringR) < 2) {
        bad.push('the options sit on one ring around the SCREEN centre — the ' +
                 'superseded task-186 shape');
      }
      if (document.querySelector('#mini-radial .wheel-x') ||
          document.body.classList.contains('mini-open')) {
        bad.push('the wheel\\'s ✕ / veil came back with it');
      }
      for (const item of items) {
        const r = item.getBoundingClientRect();
        if (r.left < 0 || r.top < 0 || r.right > innerWidth || r.bottom > innerHeight) {
          bad.push('an option opened off the screen');
        }
        if (!item.querySelector('svg')) bad.push('an option carries no drawing');
      }
      if (Math.abs(c[0].r.width - c[1].r.width) > 1 ||
          Math.abs(c[0].r.height - c[1].r.height) > 1) {
        bad.push('the options are different sizes');
      }
      closeMiniRadial();
      return bad;
    }""")
    out[f"the Layout radial is an anchored fan of three @ {label}"] = not radial
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

    # ── 229: THE HOLD SURVIVES A REAL FINGER'S JITTER ────────────────────────
    # Catches: cancelling the hold timer on ANY pointermove. A fingertip on
    # glass moves a pixel within milliseconds, so a move-cancels hold can only
    # ever fire under a perfectly still mouse — which is exactly how this
    # shipped broken (owner repeat report 2026-08-11). The gesture is driven
    # here WITH jitter injected; real travel past the slop must still cancel.
    page.evaluate("""() => {
      const btn = document.getElementById('btn-hide');
      const b = btn.getBoundingClientRect();
      const cx = b.left + b.width / 2, cy = b.top + b.height / 2;
      const ev = (type, x, y) => btn.dispatchEvent(new PointerEvent(type, {
        bubbles: true, isPrimary: true, pointerId: 7, clientX: x, clientY: y}));
      ev('pointerdown', cx, cy);
      ev('pointermove', cx + 3, cy + 2);   // the jitter every finger has
      ev('pointermove', cx + 1, cy + 4);
    }""")
    page.wait_for_timeout(HIDE_HOLD_WAIT_MS)
    jitter = page.evaluate("""() => {
      const bad = [];
      const open = document.querySelectorAll('#mini-radial .mini-item').length === 2;
      if (!open) bad.push('a hold with sub-slop jitter never opened the mode radial');
      closeMiniRadial();
      const btn = document.getElementById('btn-hide');
      btn.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, isPrimary: true, pointerId: 7}));
      hideHeld = false;
      // Real travel — a swipe across the button — must still cancel the hold.
      const b = btn.getBoundingClientRect();
      const cx = b.left + b.width / 2, cy = b.top + b.height / 2;
      const ev = (type, x, y) => btn.dispatchEvent(new PointerEvent(type, {
        bubbles: true, isPrimary: true, pointerId: 8, clientX: x, clientY: y}));
      ev('pointerdown', cx, cy);
      ev('pointermove', cx + 40, cy);
      return bad;
    }""")
    page.wait_for_timeout(HIDE_HOLD_WAIT_MS)
    jitter += page.evaluate("""() => {
      const bad = [];
      if (document.querySelectorAll('#mini-radial .mini-item').length) {
        bad.push('a swipe across Hide opened the mode radial — the slop is not a slop');
        closeMiniRadial();
      }
      const btn = document.getElementById('btn-hide');
      btn.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, isPrimary: true, pointerId: 8}));
      hideHeld = false;
      return bad;
    }""")
    out[f"the Hide hold survives finger jitter @ {label}"] = not jitter
    if jitter:
        print(f"  DETAIL hide hold jitter @ {label}: {jitter}")

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

    # ── 2026-08-12: STICKY LEAVES ITS OWN DOOR ON SCREEN ─────────────────────
    # His report: pressing Hide made everything vanish for good. In `sticky`
    # nothing brings the controls back by itself — that is the mode — so hiding
    # the Hide button with the rest left the page unrecoverable, and his own
    # spec for the mode had already excepted it. `auto` is unchanged: any touch
    # brings everything back, so there the corner may go with the rest.
    # Catches (each half proven by planting): dropping the `hide-sticky` class
    # in `setControlsHidden` (the CSS `:not()` then hides the button in both
    # modes — the bug), and letting the LAYOUT corner ride out with it (hidden
    # means hidden; the one exception is the way out, not a second button).
    door = page.evaluate("""() => {
      const bad = [];
      const gone = (id) => {
        const el = document.getElementById(id);
        const r = el.getBoundingClientRect();
        return getComputedStyle(el).display === 'none' || !r.width || !r.height;
      };
      setHideMode('sticky');
      setControlsHidden(true);
      if (gone('btn-hide')) {
        bad.push('in STICKY the Hide button went with the rest — there is no ' +
                 'way back at all');
      }
      if (!gone('btn-newlay')) {
        bad.push('in STICKY the Layout corner stayed on screen too — hidden ' +
                 'means hidden apart from the one door out');
      }
      setHideMode('auto');
      setControlsHidden(true);
      if (!gone('btn-hide') || !gone('btn-newlay')) {
        bad.push('in AUTO the corners no longer hide — any touch brings them ' +
                 'back there, so nothing may be left standing over the picture');
      }
      setHideMode('auto');
      setControlsHidden(false);
      wakeControls();
      return bad;
    }""")
    out[f"STICKY keeps the Hide button, and only that @ {label}"] = not door
    if door:
        print(f"  DETAIL sticky door @ {label}: {door}")

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


# ── TASK 237: HIS FULL SPEC ON THE BAR'S GEOMETRY (verdict ~21:4x) ──────────
# Three claims, each provable at exactly one of the three sizes this function
# is called at: his PHONE (412-class portrait) must OVERFLOW the row and drop
# into its own full-width strip; his TABLET (800-class portrait) must FIT the
# bar IN the row, sandwiched between the D-pad columns, at the SAME size as
# the top bar; LANDSCAPE must honor the Bottom setting (the bug being fixed)
# and stay centered under the ~560px cap. Each check is proven RED by
# reverting the one CSS/JS rule it guards — see the session report for the
# planted-defect transcript.
def _bar_geometry_checks(page, label, out):
    page.evaluate(STAGE_LAYOUTS)
    page.wait_for_timeout(80)

    if label.startswith("tablet portrait"):
        # Catches: dropping `--group-w` (or the whole in-row rule) — the bar
        # would either overflow on a device with plenty of room, or draw at
        # some width that does not match the bottom row's own reservation.
        #
        # THE BASELINE CLAIM IS NEW (owner report 2026-08-12, his tablet): the
        # in-row bar used to be centred on the groups' HEIGHT BAND
        # (`(--group-h - --corner) / 2`), which floated it ABOVE their bottom
        # edge — a third of the way up the screen once the pads were a column.
        # Riding IN the row means sharing the row's baseline, so the two bottom
        # edges are measured against each other here.
        # THE SIZE CLAIM CHANGED WITH THE CAP (owner 2026-08-12, task P10): the
        # old assertion was "the same WIDTH as the top bar", which was only
        # ever true while both were stretched to their own reservations. There
        # is ONE cap now (`--laybar-max`, 420 px) and the D-pad columns reserve
        # more of the row than the corner buttons do, so on an 800-class tablet
        # the top bar reaches the cap and the bottom bar is bounded by the
        # columns instead. What must still hold is the HEIGHT (the row's own
        # style), the CAP (neither may exceed it) and the CENTRING.
        bad = page.evaluate("""() => {
          const out = [];
          setLayBarPos('bottom');
          if (document.body.classList.contains('laybar-overflow')) {
            out.push('his tablet (800-class portrait) overflowed the row — ' +
                     'there is room, it must fit');
          }
          const bar = document.getElementById('layout-bar').getBoundingClientRect();
          const groups = [...document.querySelectorAll('.group')]
            .map((g) => g.getBoundingClientRect())
            .sort((a, b) => a.left - b.left);
          const [gl, gr] = groups;
          if (bar.left < gl.right - 1 || bar.right > gr.left + 1) {
            out.push('the bar is not sandwiched between the D-pad columns: ' +
              JSON.stringify({barLeft: Math.round(bar.left), barRight: Math.round(bar.right),
                               leftColRight: Math.round(gl.right), rightColLeft: Math.round(gr.left)}));
          }
          if (Math.abs(bar.bottom - gl.bottom) > 1) {
            out.push('the in-row bar does not share the bottom row\\'s baseline: ' +
              JSON.stringify({bar: Math.round(bar.bottom), group: Math.round(gl.bottom)}));
          }
          if (bar.width > 421) {
            out.push('the bottom bar is ' + Math.round(bar.width) +
                     'px wide — over the 420px cap');
          }
          const bcx = (bar.left + bar.right) / 2;
          if (Math.abs(bcx - innerWidth / 2) > 2) {
            out.push('the bottom bar is not centered: ' + Math.round(bcx) +
                     ' vs ' + Math.round(innerWidth / 2));
          }
          setLayBarPos('top');
          const barTop = document.getElementById('layout-bar').getBoundingClientRect();
          if (barTop.width > 421) {
            out.push('the top bar is ' + Math.round(barTop.width) +
                     'px wide — over the 420px cap');
          }
          const tcx = (barTop.left + barTop.right) / 2;
          if (Math.abs(tcx - innerWidth / 2) > 2) {
            out.push('the top bar is not centered: ' + Math.round(tcx));
          }
          if (Math.abs(bar.height - barTop.height) > 1) {
            out.push('the in-row bottom bar is not the same HEIGHT as the top ' +
              'bar: ' + JSON.stringify({bottom: Math.round(bar.height),
                                        top: Math.round(barTop.height)}));
          }
          return out;
        }""")
        out[f"tablet (800-class): the bottom bar rides IN the row, capped and centered @ {label}"] = not bad
        if bad:
            print(f"  DETAIL tablet in-row @ {label}: {bad}")

    if label.startswith("portrait"):
        # Catches: raising LAY_BAR_MIN_GAP so low his own phone never
        # overflows (the whole point of the rule), or dropping the corner-drop
        # / own-strip fallback CSS so an overflowed bar just gets squeezed.
        bad = page.evaluate("""() => {
          const out = [];
          setLayBarPos('bottom');
          if (!document.body.classList.contains('laybar-overflow')) {
            out.push('his phone (412-class portrait) did NOT overflow at the ' +
                     'bottom — the row has no room for it there');
          }
          const barBottom = document.getElementById('layout-bar').getBoundingClientRect();
          if (barBottom.width < 300) {
            out.push('the overflowed bottom bar is only ' + Math.round(barBottom.width) +
                     'px wide — it should spend its own full row, not be squeezed');
          }
          setLayBarPos('top');
          if (!document.body.classList.contains('laybar-overflow')) {
            out.push('his phone did NOT overflow at the top either');
          }
          const corner = document.getElementById('btn-newlay').getBoundingClientRect();
          const barTop = document.getElementById('layout-bar').getBoundingClientRect();
          if (corner.top <= barTop.bottom - 1) {
            out.push('the Layout corner button did not drop BELOW the ' +
                     'overflowed top bar\\'s own row');
          }
          return out;
        }""")
        out[f"phone (412-class): the bar overflows into its own row @ {label}"] = not bad
        if bad:
            print(f"  DETAIL phone overflow @ {label}: {bad}")

    if label.startswith("landscape"):
        # Catches: the pre-237 bug (Bottom ignored in landscape, bar always at
        # the same top y) coming back, or the cap / centering breaking.
        # UPDATED 2026-08-12: the cap is 420 px everywhere (his "the maximum
        # width is too large"), and landscape no longer has a geometry of its
        # own — the bottom position rides IN the bottom row here too, sharing
        # the D-pad's baseline, which is the half of his report that named
        # BOTH orientations. Clearing the whole group height is now the
        # overflow shape alone, and overflow never happens in landscape.
        bad = page.evaluate("""() => {
          const out = [];
          setLayBarPos('top');
          const barTopPos = document.getElementById('layout-bar').getBoundingClientRect();
          setLayBarPos('bottom');
          const barBottomPos = document.getElementById('layout-bar').getBoundingClientRect();
          if (Math.abs(barBottomPos.top - barTopPos.top) < 5) {
            out.push('the Bottom setting did nothing in landscape — the bar ' +
                     'stayed at the same y: ' + JSON.stringify(
                     {top: Math.round(barTopPos.top), bottom: Math.round(barBottomPos.top)}));
          }
          if (barBottomPos.top <= barTopPos.top) {
            out.push('the "bottom" bar is not below the "top" bar in landscape');
          }
          if (barBottomPos.width > 421 || barTopPos.width > 421) {
            out.push('the landscape bar exceeds the 420px max width: ' +
                     JSON.stringify({top: Math.round(barTopPos.width),
                                     bottom: Math.round(barBottomPos.width)}));
          }
          for (const [name, r] of [['top', barTopPos], ['bottom', barBottomPos]]) {
            const cx = (r.left + r.right) / 2;
            if (Math.abs(cx - innerWidth / 2) > 2) {
              out.push('the landscape ' + name + ' bar is not centered: ' +
                       Math.round(cx) + ' vs ' + Math.round(innerWidth / 2));
            }
          }
          // IN the bottom row, not above it: same baseline as the D-pad, and
          // between the two columns rather than across them.
          const groups = [...document.querySelectorAll('.group')]
            .map((g) => g.getBoundingClientRect())
            .sort((a, b) => a.left - b.left);
          const [gl, gr] = groups;
          if (Math.abs(barBottomPos.bottom - gl.bottom) > 1) {
            out.push('the landscape bottom bar does not share the row\\'s ' +
              'baseline: ' + JSON.stringify({bar: Math.round(barBottomPos.bottom),
                                             group: Math.round(gl.bottom)}));
          }
          if (barBottomPos.left < gl.right - 1 || barBottomPos.right > gr.left + 1) {
            out.push('the landscape bottom bar is not between the D-pad ' +
              'columns: ' + JSON.stringify(
                {barLeft: Math.round(barBottomPos.left),
                 barRight: Math.round(barBottomPos.right),
                 leftColRight: Math.round(gl.right),
                 rightColLeft: Math.round(gr.left)}));
          }
          setLayBarPos('top');
          return out;
        }""")
        out[f"landscape: Bottom is honored, bar in the row, capped and centered @ {label}"] = not bad
        if bad:
            print(f"  DETAIL landscape bar @ {label}: {bad}")

    page.evaluate("closeLayoutPanel(); layouts = []; layoutActive = null; updateLayoutBar()")
    page.wait_for_timeout(60)

    # ── NO BAR, NO INSET ROW (owner report 2026-08-12) ───────────────────────
    # With no layout created there IS no bar — and the corner buttons were
    # still being pushed a whole row down on any phone-width screen, over an
    # empty strip, because `layBarFit()` measured the corner-to-corner gap
    # whatever stood between them and set `laybar-overflow` from it alone.
    # Catches: exactly that — the `layoutBar.hidden` bail being removed. It is
    # driven at BOTH bar positions, because the bottom position measures the
    # D-pad columns instead and on a phone that gap is zero, which would set
    # the class just as certainly.
    bad = page.evaluate("""() => {
      const out = [];
      const top0 = calcTop();
      for (const pos of ['top', 'bottom']) {
        setLayBarPos(pos);
        if (document.body.classList.contains('laybar-overflow')) {
          out.push('with NO layouts and the bar at ' + pos + ', the page still ' +
                   'reserved the overflow row');
        }
        const c = document.getElementById('btn-newlay').getBoundingClientRect();
        const h = document.getElementById('btn-hide').getBoundingClientRect();
        if (c.top > top0 + 1 || h.top > top0 + 1) {
          out.push('with NO layouts the corner buttons sit ' +
                   Math.round(Math.max(c.top, h.top) - top0) + 'px below the ' +
                   'top row (bar at ' + pos + ')');
        }
      }
      setLayBarPos('top');
      return out;
      function calcTop() {
        // The undisturbed top row: --space-m + --vtop, the `.corner` rule's own.
        const s = getComputedStyle(document.documentElement);
        return parseFloat(s.getPropertyValue('--space-m')) +
               parseFloat(s.getPropertyValue('--vtop'));
      }
    }""")
    out[f"with no layouts the corners keep the top row @ {label}"] = not bad
    if bad:
        print(f"  DETAIL empty top row @ {label}: {bad}")


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
            _bar_geometry_checks(page, label, results)
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
