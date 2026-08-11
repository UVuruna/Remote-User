"""ON MUST BE A LUMINANCE EVENT — the switched-on state gate.

Owner report 2026-08-09 (task 179), with a screenshot of the Mic switched ON
in the COLOURED look, and it is round TWO of the same complaint:

  "onaj button koji je svičovan, oni koji su on/off u svakom modu — bilo da je
   kolor, dark, light — mora da bude jasno upečatljivo vidljiv, kao što je to
   jasno vidljivo u modu transparent light: plavi okvir umesto belog. Ovde
   uopšte ti nije jasno, meni kao korisniku, da li i šta je uključeno."
   # lang-ok: owner quote

Round one (0.0.371, released in v0.0.103) answered it with an accent ring, an
accent wash and a scale — and every one of those is a HUE. What his one
working example describes is not a hue at all: a BLUE frame where a WHITE one
was is a LUMINANCE flip, and that is why he can see it at a glance.

WHY ROUND ONE COULD SHIP GREEN — the process half, which is the more valuable
one (THE REPEAT LAW). Its gate lived in the phone audit and asked three
questions about COMPUTED STYLE: is the border wider, is it solid, is there an
extra background image. All three are true in the PLAIN look, which is the
look the audit happened to be in when it asked — and in the coloured look the
per-set rules OUTRANK `.ctl.active` (`body[data-colored="true"] .ctl` is one
attribute + one class + one type = more specific than `.ctl.active`), so the
accent border and the accent ink never even applied; with `data-fill="full"`
the `background:` shorthand at higher specificity also erased the wash. A
check on a property the user cannot see, asked in one of eight looks, proves
nothing about a state he judges by looking at it.

So this gate measures what a CAMERA sees, in ALL EIGHT looks: it screenshots
the real page and compares the ON button against its own OFF sibling as a
CONTRAST RATIO — over the button's face and over its ring — and demands a
real luminance event in every combination. It also holds the press state
(`.ctl.held`) apart from the latched ON state, because a button that looks
switched on while a finger is merely resting on it says the wrong thing.

Run:  .venv\\Scripts\\python tests/test_on_state.py
Requires the same toolchain as the phone audit (playwright + chromium) plus
Pillow, which the project already uses for image work.
"""

import socket
import sys
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(PROJECT / "server"))

# EVERY LOOK THE PRODUCT SHIPS — two themes x coloured/plain x
# transparent/full. His screenshot is one of the eight, and a state that is
# only unmistakable in the other seven is exactly the bug being fixed.
LOOKS = [("dark", False, "transparent"), ("dark", False, "full"),
         ("dark", True, "transparent"), ("dark", True, "full"),
         ("light", False, "transparent"), ("light", False, "full"),
         ("light", True, "transparent"), ("light", True, "full")]

VIEWPORT = (412, 915)
DPR = 2

# This gate's own port (see `start_server`) — never the input gate's 8898.
PORT = 8897

# THE FLOOR. 3.0:1 is WCAG's bar for a GRAPHIC OBJECT — the level at which a
# shape is reliably distinguishable — and "is this switched on?" is exactly
# that question about a shape. It is deliberately the same number the border
# and the icon of these buttons already owe, and it is set here so that the
# rule SHIPPED before this round fails it: the accent halo it relied on
# measured 1.1-1.6:1 against a saturated set colour, which is what the owner
# was looking at when he said he could not tell.
FLOOR = 3.0
# The press state has to be TELLABLE from the latched one, but it is a
# momentary thing under a finger, so it owes a difference rather than a bar.
HELD_FLOOR = 1.6

SHOT_DIR = PROJECT / ".claude" / "shots" / "round32-on-state"


def _look_word(colored: bool) -> str:
    return "colored" if colored else "plain"


# ═════════════════════ measuring what a camera sees ═════════════════════
def luminance(rgb) -> float:
    def ch(v):
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    la, lb = luminance(a), luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def mean(img, box):
    """Mean colour of a rectangle, in device pixels."""
    crop = img.crop(box)
    px = list(crop.getdata())
    n = max(1, len(px))
    return tuple(sum(p[i] for p in px) / n for i in range(3))


def band_mean(img, rect, grow=8, inset=0.30):
    """The two regions a person actually reads a button by.

    `face` — the middle of the button, where its fill lives.
    `ring` — the frame: everything between a box GROWN past the element (so an
    outer glow or a gap ring counts, exactly as the eye counts it) and the
    inner face. Both are means, because a mean is what a glance is.
    """
    x0, y0, x1, y1 = [v * DPR for v in rect]
    g = grow * DPR
    out = (max(0, x0 - g), max(0, y0 - g), x1 + g, y1 + g)
    w, h = x1 - x0, y1 - y0
    face = (x0 + w * inset, y0 + h * inset, x1 - w * inset, y1 - h * inset)
    outer = mean(img, out)
    inner = mean(img, face)
    # The ring is the outer box with the face's contribution removed, so a
    # bright face cannot pass for a bright frame.
    area_out = (out[2] - out[0]) * (out[3] - out[1])
    area_in = (face[2] - face[0]) * (face[3] - face[1])
    if area_out <= area_in:
        return inner, outer
    ring = tuple((outer[i] * area_out - inner[i] * area_in) / (area_out - area_in)
                 for i in range(3))
    return inner, ring


# ═════════════════════════ the harness ═════════════════════════
def start_server():
    """The audit server, on a PORT OF ITS OWN — the gates run back to back in
    `setup/build.py`, and a uvicorn still shutting down holds the shared 8898
    long enough for the next process to connect to a dying server and wait
    forever for its first `config` (seen once while these gates were being
    written)."""
    import test_input_pipeline as gate
    gate.PORT = PORT
    threading.Thread(target=gate.run_server, daemon=True).start()
    gate.server_ready.wait(15)
    deadline = time.time() + 10
    while time.time() < deadline:
        if gate.server_error:
            raise gate.server_error[0]
        try:
            with socket.create_connection(("127.0.0.1", gate.PORT), timeout=0.25):
                return gate
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("the ON state gate's server never started")


# The two buttons this gate compares, and the state it puts them in. The RIGHT
# group is the Input set, so the ON button really is the Mic — the button in
# his screenshot — and its sibling is the one beside it in the same set,
# wearing the same colour. Comparing a button with its OWN sibling is what
# makes the measurement about the STATE and not about the palette.
STAGE_JS = """
(held) => {
  const g = document.getElementById('group-right');
  const btns = [...g.querySelectorAll('button.ctl:not(.cat)')];
  const on = btns.find((b) => b.dataset.action === 'mic') || btns[0];
  const off = btns.find((b) => b !== on);
  for (const b of btns) b.classList.remove('active', 'held');
  on.classList.add(held ? 'held' : 'active');
  const r = (el) => { const q = el.getBoundingClientRect();
                      return [q.left, q.top, q.right, q.bottom]; };
  return {on: r(on), off: r(off),
          onLabel: on.textContent.trim(), offLabel: off.textContent.trim()};
}
"""


def measure(page, img_path, held=False):
    from PIL import Image
    # THE CONTROLS AUTO-HIDE WHEN NOBODY TOUCHES THEM (client/chrome.js), and
    # a sweep of eight looks is minutes of not touching anything: the first
    # run of this gate photographed a bare page for the last two looks and
    # scored them a perfect 1.00:1 — a measurement of nothing at all. Waking
    # them is the product's own entry point, the same one a finger uses.
    page.evaluate("() => { if (controlsHidden()) setControlsHidden(false);"
                  " wakeControls(); }")
    # …and the status pill goes back to its resting state. A gate that opens a
    # second connection to the same server earns the real "another device took
    # over" notice (owner rule 2026-08-02, one device at a time) — a true
    # message about the HARNESS, painted across a picture whose whole subject
    # is one button. Through the product's own setter, never by hiding an
    # element: the pill stays exactly as visible as it always is.
    page.evaluate("() => setStatus('connected', 'Connected')")
    stage = page.evaluate(STAGE_JS, held)
    page.wait_for_timeout(350)          # the scale/box-shadow transition
    page.screenshot(path=str(img_path))
    img = Image.open(img_path).convert("RGB")
    on_face, on_ring = band_mean(img, stage["on"])
    off_face, off_ring = band_mean(img, stage["off"])
    return {"face": contrast(on_face, off_face),
            "ring": contrast(on_ring, off_ring),
            "on_face": on_face, "off_face": off_face,
            "on_ring": on_ring, "off_ring": off_ring,
            "labels": (stage["onLabel"], stage["offLabel"])}


def main() -> int:
    print("\n=== ON STATE GATE ===")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ON STATE GATE FAILED — playwright is required (it photographs "
              "the REAL page). Never skip a gate silently.")
        return 1
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("ON STATE GATE FAILED — Pillow is required (it reads the "
              "photograph). Never skip a gate silently.")
        return 1

    import config as server_config
    gate = start_server()
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]},
            has_touch=True, is_mobile=True, device_scale_factor=DPR,
            user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 8) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 "
                        "Mobile Safari/537.36 VibeCoderApp"))
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
        page.wait_for_selector("#group-left button", timeout=8000)
        page.wait_for_function("() => monitor.w > 0", timeout=10000)
        try:
            for theme, colored, fill in LOOKS:
                name = f"{theme}/{_look_word(colored)}/{fill}"
                # Through the DESKTOP and the page's own entry point, like the
                # phone audit: a look the product cannot really reach is not a
                # look worth measuring.
                server_config.apply(phone_theme=theme, phone_colored=colored,
                                    phone_fill=fill)
                page.evaluate("(ui) => applyUi(ui)", server_config.ui_config())
                page.wait_for_timeout(200)
                got = page.evaluate(
                    "() => [document.body.dataset.theme,"
                    " document.body.dataset.colored, document.body.dataset.fill]")
                ok_look = (got[0], got[1] == "true", got[2]) == (theme, colored, fill)
                results[f"the shot shows the look it is named for @ {name}"] = ok_look
                if not ok_look:
                    print(f"  DETAIL look drift @ {name}: page was showing {got}")

                stem = f"ON__{theme}__{_look_word(colored)}__{fill}"
                m = measure(page, SHOT_DIR / f"{stem}.png")
                best = max(m["face"], m["ring"])
                ok = best >= FLOOR
                results[f"ON is a luminance event @ {name}"] = ok
                print(f"  {'OK  ' if ok else 'BAD '} {name}: face "
                      f"{m['face']:.2f}:1  ring {m['ring']:.2f}:1  "
                      f"(best {best:.2f}, floor {FLOOR}) — {m['labels'][0]} ON "
                      f"vs {m['labels'][1]} OFF")

                # …and the PRESS is not the LATCH. Measured against the ON
                # state itself, not against OFF: the question is whether a
                # finger resting on a button can be mistaken for a switch.
                h = measure(page, SHOT_DIR / f"HELD__{stem[4:]}.png", held=True)
                held_vs_on = max(contrast(h["on_face"], m["on_face"]),
                                 contrast(h["on_ring"], m["on_ring"]))
                ok_held = held_vs_on >= HELD_FLOOR
                results[f"held stays distinct from ON @ {name}"] = ok_held
                if not ok_held:
                    print(f"  DETAIL held @ {name}: {held_vs_on:.2f}:1 against "
                          "the latched state — a press reads as a switch")
            results["the page never errored"] = not errors
            if errors:
                print(f"  DETAIL page errors: {errors}")
        finally:
            ctx.close()
            browser.close()

    failed = [k for k, ok in results.items() if not ok]
    if failed:
        print(f"\nON STATE GATE FAILED — {len(failed)} check(s) broken:")
        for name in failed:
            print(f"  FAIL  {name}")
        return 1
    print(f"\nON STATE GATE PASSED — ON is unmistakable in all {len(LOOKS)} "
          "looks, and a press still reads as a press.")
    return 0


def test_on_state():
    """pytest entry."""
    import pytest
    pytest.importorskip("playwright.sync_api")
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
