"""WINDOW OFFER GATE — one window asks one question, and a chip never changes
its question under his finger.

His report (2026-08-12, with a screenshot): he clicked around on the PC
desktop, the phone offered to make a layout with the window that opened, he
tapped yes — and the window was RESIZED to the phone's aspect while NO LAYOUT
was created.

**His own server log settles it, to the millisecond**, and it is not a failure
in the creation path at all — `LayoutRegistry.create` never ran that evening
after that tap:

    20:29:58,356  New window python.exe "Controls …" offered as a layout (185)
    20:29:58,373  Popup     python.exe "Controls …" offered as 570a0a-3 (240)
    20:29:58,403  New window python.exe "Record a shortcut" offered … (185)
    20:29:58,569  New window python.exe "Wheel order" offered … (185)
    20:29:58,752  New window python.exe "Traffic …" offered … (185)
    20:30:03,565  POST /window_offer  200        <- his ONE tap

Two independent defects, and both are needed to produce what he saw:

1. **One window, two questions.** `scan` (task 185, "a layout with it?") and
   the popup sweep (tasks 202/240, "show it in this layout?") are two features
   that never knew about each other, and they fired on the SAME window inside
   one tick.
2. **One chip slot.** The phone has a single strip and a single live offer id,
   so every new `window_offer` silently replaced the last. Five arrived in
   400 ms; four questions vanished and the one his finger landed on was not
   the one he had read.

The yes he actually sent was therefore the SWEEP's — whose accept path runs
`_contain`, which PLACES the window into the focused layout's region. Window
resized to the phone's shape, no layout created. Exactly his sentence.

Both halves are gated here, each proven by planting its own defect. The phone
half runs the REAL `client/window-offer.js` in node against a DOM shim, since
a rule about which question a tap answers cannot be proven in Python.

Run:  .venv\\Scripts\\python tests/test_window_offer_queue.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _focus_fakes import run_checks  # noqa: E402

import test_layout_popup as popup_gate  # noqa: E402
import layout_popup  # noqa: E402

CLIENT = Path(__file__).resolve().parent.parent / "client" / "window-offer.js"


# ═══════════════════════ 1. THE SERVER: ONE QUESTION ═══════════════════════
def check_one_window_is_never_asked_about_twice():
    """HIS 20:29:58. A window the FOCUSED layout can claim is the sweep's
    question — "show it in this layout?", whose yes places it — and never also
    the birth question, whose yes opens the creation panel. Two chips for one
    window is a coin flip about which one his tap answers, and one side of
    that coin moves his window.

    Defect planted: deleting the `_attribute` guard in `scan` puts both chips
    out again, exactly as his log shows."""
    reg, conn = popup_gate.desk(
        fg=popup_gate.MEMBER_A,
        alive=(popup_gate.MEMBER_A, popup_gate.MEMBER_B, popup_gate.POPUP))
    # He double-clicked through the stream moments ago (the 185 correlation),
    # and the window that opened belongs to the focused layout's own work.
    conn["birth_seen"] = {popup_gate.MEMBER_A, popup_gate.MEMBER_B}
    # `desk()` leaves `wm.list_windows` REAL — planting the defect proved this
    # check was measuring nothing until this line existed, because `scan`
    # enumerated the owner's actual desktop and never saw POPUP at all. The
    # gate proving its own convenience to itself, caught by its own plant.
    layout_popup.wm.list_windows = lambda exclude=None: [
        {"hwnd": popup_gate.POPUP, "title": "Controls — sets on the phone",
         "process": "python.exe", "icon": None}]
    layout_popup.note_click(conn)
    layout_popup.note_click(conn)
    layout_popup.scan(reg, conn)
    layout_popup.sweep(reg, conn)
    for_popup = [m for m in popup_gate.offers(conn)
                 if f"{popup_gate.POPUP:x}" in m.get("id", "")]
    if len(for_popup) > 1:
        print(f"  DETAIL one window, {len(for_popup)} chips: "
              f"{[m.get('act', 'layout') for m in for_popup]}")
        return False
    # …and it must be the RIGHT one: inside a focused layout the question is
    # "show it here", not "make a second layout out of the layout's own work".
    if not for_popup:
        print("  DETAIL the window was never offered at all")
        return False
    return for_popup[0].get("act") != "layout_new"


def check_the_desktop_still_gets_the_birth_question():
    """The guard above may not cost task 185 its own commonest case — he
    double-clicks an .xlsx at the DESKTOP, where no layout can claim it."""
    reg, conn = popup_gate.desk(
        fg=popup_gate.MEMBER_A,
        alive=(popup_gate.MEMBER_A, popup_gate.MEMBER_B, popup_gate.STRANGER))
    conn["active"] = None                # the desktop: nothing is focused
    # The baseline task 185 keeps SEPARATELY from the attribution one, so a
    # look taken by one feature cannot make a window old for the other.
    conn["birth_seen"] = {popup_gate.MEMBER_A, popup_gate.MEMBER_B}
    # `scan` enumerates through `wm.list_windows`, which `desk()` leaves REAL —
    # and a gate that enumerated his actual desktop would be reading his work
    # instead of a fixture. Faked here, in the one check that needs it.
    layout_popup.wm.list_windows = lambda exclude=None: [
        {"hwnd": popup_gate.STRANGER, "title": "Budget.xlsx - Excel",
         "process": "excel.exe", "icon": None}]
    layout_popup.note_click(conn)
    layout_popup.note_click(conn)
    layout_popup.scan(reg, conn)
    return any(m.get("act") == "layout_new" for m in popup_gate.offers(conn))


# ═══════════════════════ 2. THE PHONE: ONE QUESTION AT A TIME ═══════════════
DRIVER = r"""
const fs = require("fs");
const vm = require("vm");

const shown = [];
const text = { set textContent(v) { shown.push(v); }, get textContent() {
  return shown[shown.length - 1] || ""; }, title: "" };
const btn = () => ({ textContent: "", addEventListener: () => {} });
const chip = { hidden: true };
const els = { "window-offer": chip, "window-offer-text": text,
              "window-offer-in": btn(), "window-offer-out": btn() };

const posted = [];
const ctx = {
  console, setTimeout, clearTimeout, Date,
  document: { getElementById: (id) => els[id] || btn() },
  fetch: (url, opt) => { posted.push(JSON.parse(opt.body)); return Promise.resolve({}); },
  token: "t",
  showToast: () => {},
  startFromWindow: () => {},
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), ctx,
                { filename: "window-offer.js" });

const offer = (id, act, title) =>
  ctx.showWindowOffer({ id, act, title, process: "p.exe", hwnd: 1 });

async function main() {
  const out = {};
  // HIS 400 ms: five offers in a row, the way his log recorded them.
  offer("a", "layout_new", "Controls");
  offer("b", "layout", "Controls");
  offer("c", "layout_new", "Record a shortcut");
  offer("d", "layout_new", "Wheel order");
  offer("e", "layout_new", "Traffic");
  // What he is LOOKING at must still be the first question asked.
  out.showing = shown.length;
  out.first = shown[0];
  out.stillFirst = shown[shown.length - 1] === shown[0];
  // …and his tap answers THAT one, not one that overwrote it unseen.
  await ctx.answerWindowOffer("desktop");
  out.answered = posted.map(p => p.id);
  // Only then does the next question get its turn.
  out.next = shown[shown.length - 1];
  out.queued = posted.length;
  console.log(JSON.stringify(out));
  // The chip's own 30 s auto-dismiss timer would otherwise hold node
  // open long past the answer — and a driver that hangs is a gate that
  // reports a timeout instead of a verdict.
  process.exit(0);
}
main();
"""


def _drive():
    node = shutil.which("node")
    if not node:
        raise AssertionError(
            "node is required for the window-offer gate (it runs the REAL "
            "client/window-offer.js) — install Node.js. Never skip a gate "
            "silently.")
    work = Path(tempfile.mkdtemp(prefix="ru_winoffer_gate_"))
    try:
        script = work / "run.js"
        script.write_text(DRIVER, encoding="utf-8")
        out = subprocess.run([node, str(script), str(CLIENT)],
                             capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            raise AssertionError(f"node failed: {out.stderr.strip()}")
        return json.loads(out.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(work, ignore_errors=True)


def check_a_standing_chip_is_not_replaced():
    """FIVE OFFERS IN 400 MS, his own log. The strip must still be asking the
    FIRST question when his finger arrives — a chip that swapped its subject
    unseen is how a tap moved a window he had not agreed to move.

    Defect planted: removing the settle window makes the strip show 'Traffic'
    while he reads 'Controls'."""
    r = _drive()
    return r["stillFirst"] and r["showing"] == 1


def check_his_tap_answers_the_question_he_read():
    """The id posted must be the one that was on screen, and only after that
    does the next question get its turn — a queue, never a second strip."""
    r = _drive()
    return r["answered"] == ["a"] and r["next"] != r["first"]


CHECKS = [
    ("one window is never asked about twice",
     check_one_window_is_never_asked_about_twice),
    ("the desktop still gets the birth question",
     check_the_desktop_still_gets_the_birth_question),
    ("a standing chip is not replaced under his finger",
     check_a_standing_chip_is_not_replaced),
    ("his tap answers the question he read, and the next one follows",
     check_his_tap_answers_the_question_he_read),
]


def main() -> int:
    return run_checks("WINDOW OFFER GATE", CHECKS,
                      "one window asks one question, and it waits for his tap")


if __name__ == "__main__":
    sys.exit(main())
