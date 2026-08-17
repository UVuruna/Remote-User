"""THE WINDOW-OFFER GATE — who gets asked about a new window, and who does not.

OWNER REPORT 2026-08-17, and his sentence is the specification: *the app asks
me only where it has nothing to ask me — where I make the window myself — and
not where somebody else made it, where I DO want a layout from it.*

Exactly inverted, and two independent agents found the two mechanisms:

  * **It asks where it must not.** `layout_popup.mine()` — "we made this
    window" — was always called AFTER the window already existed, while the
    popup sweep runs every second on its own thread with no grace at all for a
    window it can tie to a member. Measured: the tear-off leaves its window
    standing 6-8 s before the claim, and the VS Code act cannot begin watching
    until the Command Palette sequence returns, though VS Code can raise the
    window the instant Enter lands. Whoever looks first wins. A second, wholly
    separate hole: `sweep_lost` never consulted `_is_ours` at all.
  * **It is silent where he wants it.** `_attribute` has four rules and every
    one of them asks *does this window belong to this layout* — mostly by
    PROCESS. An agent's report window is its own exe, with no ancestry and no
    click of his anywhere near it, so it falls through all four and is filed as
    a stranger to ignore. And `baseline()` enumerated the LIVE desk on every
    connection, so a window born while no phone was connected — which is when
    an agent's report is born, every time — was filed as already known by the
    very connection that came looking for it, and could never be new again.

His decisions, off a ballot: ask about **every new window that is not ours and
is not already in a layout**, including the ones born while he was away.

What is held here, each proven by planting its own defect:

  1. A claim ARMED BEFORE the act silences the chip — the race, closed
     structurally rather than by winning it.
  2. A claim is bounded: a window of that process much later is not ours.
  3. `mine()` still works on its own, for the makers that know the handle.
  4. A NEW listable window nobody has placed IS offered inside a layout, with
     no process tie, no ancestry and no click — his agent-report case.
  5. A window ANOTHER layout already holds is never offered.
  6. A window no layout could hold (not listable) is still never offered.
  7. The rescue pass skips a window we made — the hole that had no guard.
  8. The baseline is the desk as the phone LAST LEFT IT, so a window born
     while nobody was connected is NEW on the next connection.
  9. With no memory at all (a fresh server) the live desk is the baseline —
     his standing desk is not news.

It reuses tests/test_layout_popup.py's fake desk WHOLE rather than building a
second one: a second copy of a Win32 fake is precisely how two gates come to
disagree about what a desk is. Its own FILE because that one stands at THE
STRUCTURE LAW's wall and asks a different question (what happens to a window
the layout can claim) than this one (WHO is asked at all).

NOTHING HERE TOUCHES THE OWNER'S DESKTOP.

Run:  .venv\\Scripts\\python tests/test_window_offer.py
"""

import sys
import time
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import layout_popup  # noqa: E402
import window_claim  # noqa: E402
import window_rescue  # noqa: E402

from _focus_fakes import fresh_conn, run_checks  # noqa: E402

import test_layout_popup as base  # noqa: E402


STRANGER = base.STRANGER
POPUP = base.POPUP
MEMBER_A = base.MEMBER_A
TOOLWIN = base.TOOLWIN


def _fresh():
    """One desk holding NOTHING but the two members, with both claim records
    emptied — they are module-level and would otherwise leak from one check
    into the next.

    The bare desk is deliberate. `test_layout_popup`'s default alive-set is
    every window that file ever needs, and under this round's rule EVERY one of
    them is a window nobody has placed — so a check written on the default desk
    would be counting six chips and could not say which rule produced which."""
    window_claim._OURS.clear()
    window_claim._EXPECT.clear()
    layout_popup._DESK = None
    reg, conn = base.desk(fg=MEMBER_A,
                          alive=(base.MEMBER_A, base.MEMBER_B, base.OLD_TWIN))
    return reg, conn


def _sweep(reg, conn):
    """One enumeration pass — the sweep is where the catch-all rule lives, and
    it is also the only pass that sees a window which never takes the
    foreground (task 239). `focus_guard.guard` drives the FOREGROUND path and
    would answer a different question."""
    conn["popup_swept"] = 0.0
    layout_popup.sweep(reg, conn)
    return base.offers(conn)


def _stranger_appears(conn):
    """A window with NO tie of any kind: its own process, no ancestry to a
    member, and deliberately no injected click anywhere near it. Under the
    four old rules this is the window the module called a stranger and
    ignored — it is the shape of an agent's report."""
    base.DESK_WINDOWS.add(STRANGER)
    conn["click_times"] = []


# ═══════════ 1-3. THE CLAIM, ARMED BEFORE THE WINDOW EXISTS ═══════════
def check_a_claim_armed_before_the_act_silences_the_chip() -> bool:
    """The race, and the whole reason `expect()` exists. The maker arms its
    claim BEFORE it acts; the window then appears; the sweep must say nothing,
    even though `mine()` has not run and cannot yet — the handle did not exist
    when the maker spoke."""
    reg, conn = _fresh()
    layout_popup.expect(base.PROCESS_OF_STRANGER)
    _stranger_appears(conn)
    return _sweep(reg, conn) == []


def check_the_claim_does_not_last_forever() -> bool:
    """It is a promise about the next few seconds, not a licence. A window of
    the same process appearing long afterwards is an ordinary window again —
    without this, one act would silence that exe for the session."""
    reg, conn = _fresh()
    layout_popup.expect(base.PROCESS_OF_STRANGER)
    window_claim._EXPECT[:] = [
        (p, t - window_claim.EXPECT_TTL_S - 1) for p, t in window_claim._EXPECT]
    _stranger_appears(conn)
    return len(_sweep(reg, conn)) == 1


def check_naming_the_handle_still_silences_it() -> bool:
    """`expect()` does not replace `mine()`: the claim covers the gap, and the
    exact handle is what survives past the claim's short life."""
    reg, conn = _fresh()
    _stranger_appears(conn)
    layout_popup.mine(STRANGER)
    return _sweep(reg, conn) == []


# ═══════════ 4-6. THE QUESTION HE ACTUALLY WANTS ASKED ═══════════
def check_a_window_nobody_placed_is_offered() -> bool:
    """HIS AGENT-REPORT CASE. No process tie, no ancestry, no click — every
    one of the four old attribution rules refuses it, and it must still earn a
    chip, because the question is now "have I put this anywhere" and not "does
    this belong to the layout"."""
    reg, conn = _fresh()
    _stranger_appears(conn)
    queued = _sweep(reg, conn)
    return len(queued) == 1 and queued[0].get("process") == base.PROCESS_OF_STRANGER


def check_a_window_another_layout_holds_is_never_offered() -> bool:
    """A window a layout is already responsible for HAS been placed — by him.
    Offering it is the half of his report about being asked pointless
    questions, and the catch-all must not reintroduce it.

    IT IS PUT IN A SECOND LAYOUT, NOT THE FOCUSED ONE, and planting is what
    forced that. The first version appended it to `reg.layouts[0]` — the very
    layout being swept — so the loop's own `hwnd in lay.members` line answered
    it several rules earlier, and deleting `hwnd not in held` from the
    catch-all left this check GREEN. It was measuring a rule that has been
    there since the module was written, not the one this round added."""
    reg, conn = _fresh()
    base.DESK_WINDOWS.add(STRANGER)
    conn["click_times"] = []
    elsewhere = base.layout_with([STRANGER])
    reg.layouts.append(elsewhere.layouts[0])
    return _sweep(reg, conn) == []


def check_a_window_no_layout_could_hold_is_still_never_offered() -> bool:
    """The catch-all may not widen this: a tool window would not appear in the
    creation list, so a chip about it is a question the app cannot honour (his
    point 3, 2026-08-13).

    THE TOOL WINDOW IS GIVEN A STRANGER'S PROCESS, and planting is what forced
    that too. With its shipped fixture PID — a member's — `_attribute` ties it
    to the layout, so it is answered by the `if reason:` branch and never
    reaches the catch-all at all; bypassing the catch-all's own `is_listable`
    left this check GREEN, because it was measuring the OTHER branch's gate."""
    reg, conn = _fresh()
    base.DESK_WINDOWS.add(TOOLWIN)
    conn["click_times"] = []
    base.PIDS[TOOLWIN] = base.OTHER_PID
    try:
        return _sweep(reg, conn) == []
    finally:
        base.PIDS[TOOLWIN] = base.MEMBER_PID


# ═══════════ 7. THE PASS THAT NEVER LEARNED THE RULE ═══════════
def check_the_rescue_skips_a_window_we_made() -> bool:
    """`sweep_lost` consulted every other defence and never `_is_ours` — so a
    window we opened on his tap that landed off-screen, which is what a fresh
    window does before anything places it, could be handed back to him as
    "this is lost, shall I rescue it?". Not a variant of the race above: here
    the guard was not late, it was absent."""
    reg, conn = _fresh()
    lost = [{"hwnd": STRANGER, "title": "report", "process": "agent.exe",
             "rect": (-4000, 0, 800, 600), "minimized": False, "icon": None}]
    real = window_rescue.lost_windows.lost
    window_rescue.lost_windows.lost = lambda held: list(lost)
    try:
        layout_popup.mine(STRANGER)
        conn["lost_swept"] = 0.0
        window_rescue.sweep_lost(reg, conn)
        ours = base.offers(conn)
        # …and the same pass must still rescue a window that is NOT ours, or
        # the check above proves only that the function stopped working.
        window_claim._OURS.clear()
        conn["lost_swept"] = 0.0
        window_rescue.sweep_lost(reg, conn)
        stranger = base.offers(conn)
    finally:
        window_rescue.lost_windows.lost = real
    return ours == [] and len(stranger) == 1


# ═══════════ 8-9. THE DESK AS HE LEFT IT ═══════════
def check_a_window_born_while_he_was_gone_is_new_on_his_return() -> bool:
    """THE SILENCE HE REPORTED, and the mechanism named. `baseline()` used to
    enumerate the LIVE desk on every connection, so a window born while no
    phone was connected was filed as already known by the very connection that
    came looking for it. An agent's report is born exactly then."""
    _fresh()
    layout_popup.remember_desk()          # the desk as the phone left it
    base.DESK_WINDOWS.add(STRANGER)       # …and then, with nobody watching:
    later = fresh_conn(active=0)
    layout_popup.baseline(later)
    return layout_popup._is_new(later, STRANGER)


def check_a_server_that_has_never_been_watched_treats_the_desk_as_his() -> bool:
    """The other half, and the one a too-eager memory breaks: on the FIRST
    connection after the server starts there is no memory, and everything
    standing there really is his desk rather than news. Without this, the first
    connection after every restart would ask about every window he owns."""
    _fresh()
    layout_popup._DESK = None
    base.DESK_WINDOWS.add(STRANGER)
    first = fresh_conn(active=0)
    layout_popup.baseline(first)
    return not layout_popup._is_new(first, STRANGER)


# ═══════════ 10-12. THE ANSWER HE ASKED FOR IS ON THE CHIP ═══════════
# OWNER REPORT 2026-08-17, the one he has made more often than any other: an
# agent's HTML report opened in Chrome while he was watching a layout, and the
# phone offered to MOVE IT IN — never to make a layout of it. It was structural
# and not a slip: inside a focused layout this sweep is the only question a new
# window can raise (`layout_birth.scan` stands down for anything this module
# can claim — constraint 18), and its chip had exactly two answers, neither of
# them the one he wants. Three checks, each proven by planting its own defect.
def check_the_chip_offers_a_layout_of_its_own() -> bool:
    """His agent-report window, inside a focused layout: the chip must carry
    the create answer AND the window's identity, because "Make a layout" seeds
    the ordinary creation panel with that exact window."""
    reg, conn = _fresh()
    _stranger_appears(conn)
    queued = _sweep(reg, conn)
    if len(queued) != 1:
        return False
    chip = queued[0]
    return chip.get("new_ok") is True and chip.get("hwnd") == STRANGER


def check_his_create_tap_moves_nothing_and_is_not_a_refusal() -> bool:
    """The tap comes back through the REAL `pick()` — the one the HTTP route
    calls. Two promises: the PC moves nothing (the creation flow does every
    later step, exactly as task 185's chip does), and the window is NOT filed
    as left on the desktop, since he has not left it anywhere."""
    reg, conn = _fresh()
    _stranger_appears(conn)
    # The fake's ENUMERATION and its IsWindow are two different sets, exactly
    # as Windows' own EnumWindows and IsWindow are: this is the only check here
    # that reaches `pick`, which refuses a window that has closed meanwhile.
    layout_popup.wm.user32.alive.add(STRANGER)
    queued = _sweep(reg, conn)
    if len(queued) != 1:
        return False
    lay = reg.layouts[0]
    before = list(base.PLACED)
    ok = layout_popup.pick(queued[0]["id"], "layout_new")
    return (ok and list(base.PLACED) == before
            and STRANGER not in lay.adopted
            and STRANGER not in conn.get("popup_declined", set()))


def check_his_create_tap_is_not_asked_again_a_second_later() -> bool:
    """AN INDEPENDENT ADVERSARIAL AGENT REPORTED THIS AS A CONFIRMED DEFECT and
    it is NOT one — the check stays because the question it asks is real and
    nothing in this file had ever asked it.

    Its reasoning was sound as far as it went: `pick` discards `popup_asked`,
    which only ever means "a chip is out right now", and the sweep runs every
    second — so the same window would be offered again while he stands in the
    creation panel, four more copies of a question he has answered. What it
    missed is that `_offer` is preceded by `_judged`, which files the window as
    no longer NEW, and the catch-all rule requires newness. Measured, not
    argued: with the proposed fix (a `popup_creating` record consulted by the
    sweep) REMOVED ENTIRELY, this check still passes — so the fix would have
    been dead code, and dead code that looks like a defence is worse than none.

    The defence this really pins is `_judged`, which is what planting breaks."""
    reg, conn = _fresh()
    _stranger_appears(conn)
    layout_popup.wm.user32.alive.add(STRANGER)
    first = _sweep(reg, conn)
    if len(first) != 1:
        return False
    conn["popup_send"].clear()
    layout_popup.pick(first[0]["id"], "layout_new")
    return _sweep(reg, conn) == []


def check_the_page_really_wires_the_create_answer() -> bool:
    """A SERVER FIELD NO PAGE READS IS NOT A FEATURE (the actions.json lesson
    of 2026-08-07, and the `wheel_order` one after it). This reads the shipped
    client: the button must exist, it must post the act the server is waiting
    for, and it must seed the creation panel through `startFromWindow` — the
    same function Tap, List and New already end in, which is his whole point.

    The CSS row is checked too: a third answer squeezed into the pair's grid
    would shrink all three below a thumb (THE SPACE & LEGIBILITY LAW)."""
    client = PROJECT_DIR / "client"
    html = (client / "index.html").read_text(encoding="utf-8")
    js = (client / "window-offer.js").read_text(encoding="utf-8")
    css = (client / "window-offer.css").read_text(encoding="utf-8")
    return ('id="window-offer-new"' in html
            and "window-offer-new" in js
            and 'answerWindowOffer("layout_new")' in js
            and "new_ok" in js
            and "startFromWindow" in js
            and "grid-column: 1 / -1" in css)


CHECKS = [
    ("a claim armed before the act silences the chip",
     check_a_claim_armed_before_the_act_silences_the_chip),
    ("the claim does not last forever",
     check_the_claim_does_not_last_forever),
    ("naming the handle still silences it",
     check_naming_the_handle_still_silences_it),
    ("a window nobody has placed is offered",
     check_a_window_nobody_placed_is_offered),
    ("a window another layout holds is never offered",
     check_a_window_another_layout_holds_is_never_offered),
    ("a window no layout could hold is still never offered",
     check_a_window_no_layout_could_hold_is_still_never_offered),
    ("the rescue skips a window we made, and still rescues a stranger's",
     check_the_rescue_skips_a_window_we_made),
    ("a window born while he was gone is NEW on his return",
     check_a_window_born_while_he_was_gone_is_new_on_his_return),
    ("a server that has never been watched treats the desk as his",
     check_a_server_that_has_never_been_watched_treats_the_desk_as_his),
    ("the chip offers a layout of its own",
     check_the_chip_offers_a_layout_of_its_own),
    ("his create tap moves nothing and is not a refusal",
     check_his_create_tap_moves_nothing_and_is_not_a_refusal),
    ("his create tap is not asked again a second later",
     check_his_create_tap_is_not_asked_again_a_second_later),
    ("the page really wires the create answer",
     check_the_page_really_wires_the_create_answer),
]


def main() -> int:
    return run_checks("WINDOW OFFER GATE", CHECKS,
                      "he is asked about what he has not placed, and never "
                      "about what he just asked for")


def test_window_offer():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())
