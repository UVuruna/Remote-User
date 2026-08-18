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
import layout_birth  # noqa: E402
import layout_popup  # noqa: E402
import offer_withdraw  # noqa: E402

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
    layout_birth.note_click(conn)
    layout_birth.note_click(conn)
    layout_birth.scan(reg, conn)
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
    layout_birth.note_click(conn)
    layout_birth.note_click(conn)
    layout_birth.scan(reg, conn)
    return any(m.get("act") == "layout_new" for m in popup_gate.offers(conn))


# ═══════════════════ 1b. THE SERVER: A QUESTION ABOUT NOTHING ═══════════════
# His report, 2026-08-18, with a screenshot of the phone: "the agents open and
# close a heap of windows, and then I have to press No a thousand times". The
# chip in the shot asks for a layout out of a window that had closed long
# before he picked the phone up — and the yes could not have worked either,
# because there is no window behind that handle any more.
def _desk_with_one_new_window():
    """The desktop, one window an agent just opened, and the birth chip for
    it queued — the state every check below starts from."""
    reg, conn = popup_gate.desk(
        fg=popup_gate.MEMBER_A,
        alive=(popup_gate.MEMBER_A, popup_gate.MEMBER_B, popup_gate.STRANGER))
    conn["active"] = None                # the desktop: nothing is focused
    conn["birth_seen"] = {popup_gate.MEMBER_A, popup_gate.MEMBER_B}
    fake = layout_popup.wm.user32
    # `is_alive` asks three questions and the fake desk only answers one of
    # them (`FakeWin32.__getattr__` returns 0 for everything else, which would
    # make EVERY window here look dead and let this gate pass on a lie). The
    # visibility answer is wired to the same `alive` set the fake already owns.
    fake.IsWindowVisible = lambda hwnd: 1 if hwnd in fake.alive else 0
    layout_popup.wm.list_windows = lambda exclude=None: [
        {"hwnd": popup_gate.STRANGER, "title": "Agent report",
         "process": "chrome.exe", "icon": None}]
    layout_birth.scan(reg, conn)
    sent = [m["id"] for m in popup_gate.offers(conn)
            if m.get("type") == "window_offer"]
    return conn, fake, sent


def check_a_chip_whose_window_closed_is_withdrawn():
    """The PC must take the question back — the phone cannot know the window
    is gone, and a question he cannot answer is one he still has to tap away.

    Defect planted: dropping the `withdraw_dead` call leaves the offer in
    `_OFFERS` and nothing at all on the wire for the phone."""
    conn, fake, sent = _desk_with_one_new_window()
    conn["popup_send"].clear()           # the flush: the chip is on the phone
    fake.alive.discard(popup_gate.STRANGER)   # …and the agent closed it
    withdrawn = offer_withdraw.withdraw_dead(conn)
    if len(sent) != 1 or withdrawn != sent:
        print(f"  DETAIL asked {sent}, withdrew {withdrawn}")
        return False
    cancels = [m["id"] for m in popup_gate.offers(conn)
               if m.get("type") == "window_offer_cancel"]
    if cancels != sent:
        print(f"  DETAIL cancel frames {cancels}, expected {sent}")
        return False
    # …and the offer itself is gone, so a stale tap on a dead handle can never
    # be honoured either.
    return layout_popup.pick(sent[0], "layout_new") is False


def check_a_chip_that_never_went_out_is_simply_dropped():
    """A window that opened and closed between two ticks must not be SENT and
    then cancelled — the phone would show it for a frame. The queued offer is
    dropped where it stands, and no cancel is owed for a chip nobody saw."""
    conn, fake, sent = _desk_with_one_new_window()
    fake.alive.discard(popup_gate.STRANGER)   # closed before the flush
    offer_withdraw.withdraw_dead(conn)
    if not sent:
        print("  DETAIL nothing was ever offered")
        return False
    return popup_gate.offers(conn) == []


def check_a_living_window_keeps_its_question():
    """The withdrawal may not eat the feature. A chip about a window that is
    still standing survives every tick until he answers it or it fades."""
    conn, _fake, sent = _desk_with_one_new_window()
    conn["popup_send"].clear()
    for _ in range(4):                   # a second of the watcher's poll
        if offer_withdraw.withdraw_dead(conn):
            print("  DETAIL a standing window's chip was withdrawn")
            return False
    return bool(sent) and popup_gate.offers(conn) == []


# ═══════════════════════ 2. THE PHONE: ONE QUESTION AT A TIME ═══════════════
DRIVER = r"""
const fs = require("fs");
const vm = require("vm");

const shown = [];
const text = { set textContent(v) { shown.push(v); }, get textContent() {
  return shown[shown.length - 1] || ""; }, title: "" };
const btn = () => ({ textContent: "", hidden: false, addEventListener: () => {} });
// `classList` is modelled rather than stubbed away (owner report 2026-08-17):
// the chip now wears `has-new` when its create answer is up, and a fake that
// merely swallowed the call would let a page that never set it pass here.
const classes = new Set();
const chip = { hidden: true,
               getBoundingClientRect: () => ({ bottom: 200, height: 136 }),
               classList: { toggle: (c, on) => on ? classes.add(c) : classes.delete(c),
                            contains: (c) => classes.has(c) } };
const els = { "window-offer": chip, "window-offer-text": text,
              "window-offer-in": btn(), "window-offer-out": btn(),
              "window-offer-new": btn() };

const rootVars = {};
const rootStyle = { setProperty: (k, v) => { rootVars[k] = v; },
                    removeProperty: (k) => { delete rootVars[k]; } };
const posted = [];
const ctx = {
  console, setTimeout, clearTimeout, Date,
  // `documentElement.style` is MODELLED, not stubbed away (owner decree
  // 2026-08-17): the chip pushes the status pill below itself through
  // `--status-top`, and the shift is measured off the chip's real box. Here
  // the box is a fake with a known height, so the arithmetic is checkable —
  // a fake that swallowed the call would let a page that never moves the pill
  // pass this gate.
  document: { getElementById: (id) => els[id] || btn(),
              documentElement: { style: rootStyle } },
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
  // NOTHING MAY OVERLAP ANYTHING (owner decree 2026-08-17): while a chip
  // stands, the status pill is pushed BELOW its measured bottom edge, and
  // the shift is dropped the moment the chip goes.
  out.shiftedWhileUp = rootVars["--status-top"] || null;
  ctx.hideWindowOffer();
  out.shiftedWhenGone = rootVars["--status-top"] || null;
  // THE PC TAKES A QUESTION BACK (owner report 2026-08-18). Two chips up —
  // one showing, one queued behind it — and both their windows close.
  // The five-offer burst above left c/d/e still waiting behind the strip;
  // their windows are gone too, and clearing them here is the same withdrawal
  // this block is about — not a convenience.
  ["c", "d", "e"].forEach(ctx.cancelWindowOffer);
  const before = shown.length;
  offer("f", "layout_new", "Report one");
  offer("g", "layout_new", "Report two");
  ctx.cancelWindowOffer("g");            // the one WAITING dies first
  ctx.cancelWindowOffer("f");            // …and then the one on screen
  out.afterCancel = shown.length - before;   // "Report two" must never go up
  out.chipGone = chip.hidden;
  posted.length = 0;
  // A LIVE ONE IS UNTOUCHED: the next question still goes up and still posts
  // its own id, so the withdrawal cannot have eaten the queue itself.
  offer("h", "layout_new", "Report three");
  out.afterLive = shown[shown.length - 1];
  await ctx.answerWindowOffer("desktop");
  out.livePosted = posted.map(p => p.id);
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


def check_the_chip_pushes_the_status_pill_out_of_its_way():
    """NOTHING MAY OVERLAP ANYTHING (owner decree 2026-08-17, after the audit
    shots showed the amber status pill sitting over the chip's own title — the
    sentence naming WHICH window he is being asked about).

    Two halves, and the second is the one that rots quietly: while the chip
    stands the pill is pushed below its MEASURED bottom edge (the fake box's
    bottom is 200, plus the 10 px gap), and the moment the chip goes the shift
    goes with it — a pill left pinned halfway down the screen for the rest of
    the session would be this fix's own bug."""
    r = _drive()
    return r["shiftedWhileUp"] == "210px" and r["shiftedWhenGone"] is None


def check_the_page_really_reads_the_shift():
    """A CSS VARIABLE NOBODY READS IS NOT A FEATURE. The pill's own rule must
    take `--status-top`, or the JS above writes a value into a page that goes
    on drawing the pill exactly where it always did."""
    css = (CLIENT.parent / "style.css").read_text(encoding="utf-8")
    return "var(--status-top" in css


def check_a_withdrawn_chip_leaves_the_phone():
    """His thousand taps. When the PC says the window is gone, the chip goes
    by itself — and the queued question about a window that also closed never
    goes up at all, or it is the same tap arriving one beat later.

    Defect planted: removing the queue sweep in `cancelWindowOffer` puts
    'Report two' on screen the moment 'Report one' is withdrawn."""
    r = _drive()
    return r["afterCancel"] == 1 and r["chipGone"] is True


def check_the_withdrawal_does_not_eat_the_next_question():
    """A chip about a window that is still there must still be asked, and his
    tap must still answer it — the cure may not become the disease."""
    r = _drive()
    return "Report three" in (r["afterLive"] or "") and r["livePosted"] == ["h"]


CHECKS = [
    ("one window is never asked about twice",
     check_one_window_is_never_asked_about_twice),
    ("the desktop still gets the birth question",
     check_the_desktop_still_gets_the_birth_question),
    ("a standing chip is not replaced under his finger",
     check_a_standing_chip_is_not_replaced),
    ("his tap answers the question he read, and the next one follows",
     check_his_tap_answers_the_question_he_read),
    ("the chip pushes the status pill out of its way",
     check_the_chip_pushes_the_status_pill_out_of_its_way),
    ("the page really reads the shift",
     check_the_page_really_reads_the_shift),
    ("a chip whose window closed is withdrawn by the PC",
     check_a_chip_whose_window_closed_is_withdrawn),
    ("a chip that never went out is simply dropped",
     check_a_chip_that_never_went_out_is_simply_dropped),
    ("a living window keeps its question",
     check_a_living_window_keeps_its_question),
    ("a withdrawn chip leaves the phone, queue included",
     check_a_withdrawn_chip_leaves_the_phone),
    ("the withdrawal does not eat the next question",
     check_the_withdrawal_does_not_eat_the_next_question),
]


def main() -> int:
    return run_checks("WINDOW OFFER GATE", CHECKS,
                      "one window asks one question, and it waits for his tap")


if __name__ == "__main__":
    sys.exit(main())
