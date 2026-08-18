"""LAYOUT POPUP GATE — a window the layout's work opens stays reachable.

Owner report 2026-08-10, and again on 2026-08-11 (task 202, escalated — the
third time this class reached him): he was watching a LAYOUT on the phone when
an agent on the PC opened its HTML report. The window appeared OUTSIDE the
layout's region, below the members' always-on-top band, and the only way to
"reach" it — choosing Desktop — MINIMIZES every member and takes his place of
work with it. He could see the thing he wanted and could not touch it.

His rule, which this gate holds: nothing belonging to the layout's work may
live outside the layout's dimensions. If it FITS the region it is placed
INSIDE it; if it cannot fit, it opens separate, over the FULL screen.

AND HE IS ASKED FIRST (his amendment the same day): a new window is OFFERED to
the phone — one chip, two buttons, "Show in layout" / "Leave on desktop" — and
nothing on the PC moves until he taps. Ignoring the chip is a real answer and
the answer is the desktop; a window he left on the desktop is never asked about
again, and the chip is sent once per window, not four times a second.

The hard half is NOT the placement — it is knowing WHOSE window it is. This PC
is never quiet: other agents launch GUI apps all day, and constraint 11 exists
because they take the foreground mid-dictation. So the checks below are as much
about what must NOT be adopted (a stranger, and the owner's OTHER VS Code
window, which shares its process with a member) as about what must.

NOTHING HERE TOUCHES THE OWNER'S DESKTOP: every Win32 call is answered by a
fake — the desk model is local to this file, the guard/registry/fence machinery
is the real code, and the ledger is a dict this file can read.

Run:  .venv\\Scripts\\python tests/test_layout_popup.py
"""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _focus_fakes import (  # noqa: E402
    MEMBER_A, MEMBER_B, FakeWs, Raises, fake_listen, focus_guard, fresh_conn,
    layout_with, run_checks, window_manager, with_win32,
)

import desk_facts  # noqa: E402

import popup_contain  # noqa: E402
import popup_offers  # noqa: E402

import layout_popup  # noqa: E402
import window_claim  # noqa: E402

# The desk: two members side by side, and the windows that appear on top of it.
DIALOG = 0x30          # "Open this link?" — owned by MEMBER_A
POPUP = 0x40           # the agent's HTML report: fits the region
BIG = 0x41             # a window whose MINIMUM size is larger than the region
STRANGER = 0x50        # another agent's window — a different process, no kin
OLD_TWIN = 0x51        # his OTHER VS Code window: same process, already open
CHILD = 0x52           # the viewer a member started
CLICKED = 0x53         # an already-running third-party app, opened by HIS click
TOOLWIN = 0x54         # a member's own TOOL window — real, new, and unofferable
OURS = 0x55            # a window WE made (a torn-off tab) — never his question

MEMBER_PID, OTHER_PID, CHILD_PID = 1000, 2000, 3000
PIDS = {MEMBER_A: MEMBER_PID, MEMBER_B: MEMBER_PID, DIALOG: MEMBER_PID,
        POPUP: MEMBER_PID, BIG: MEMBER_PID, OLD_TWIN: MEMBER_PID,
        STRANGER: OTHER_PID, CHILD: CHILD_PID, CLICKED: OTHER_PID,
        TOOLWIN: MEMBER_PID, OURS: MEMBER_PID}
PARENTS = {CHILD_PID: MEMBER_PID, OTHER_PID: 4, MEMBER_PID: 4}

MONITOR = (0, 0, 2560, 1400)
REGION = (100, 100, 1200, 800)          # the union of the two members' frames
HOME = {MEMBER_A: (100, 100, 600, 800), MEMBER_B: (700, 100, 600, 800),
        DIALOG: (1900, 1000, 500, 300),
        POPUP: (1800, 900, 400, 300),   # outside the region, and small
        BIG: (1700, 40, 1600, 1000),    # outside the region, and too big
        STRANGER: (1500, 500, 800, 600), OLD_TWIN: (1500, 500, 800, 600),
        CHILD: (2000, 200, 300, 200), CLICKED: (1600, 700, 700, 500),
        TOOLWIN: (1900, 300, 200, 120), OURS: (1750, 350, 500, 400)}
# What `window_manager.is_listable` refuses: a window no layout could hold, so
# no chip may name it (owner report 2026-08-13, his point 3). A TOOL window is
# the honest case — Windows really does hand these a title and real geometry.
NOT_LISTABLE = {TOOLWIN}
# The exe each fake window belongs to. `window_claim.expect()` claims by
# PROCESS — a claim cannot name a handle that does not exist yet — so a fake
# desk without these could not drive that rule at all.
PROCESS_OF_STRANGER = "agent.exe"
PROCESS_OF_MEMBER = "code.exe"
PROCESS_NAMES = {MEMBER_A: PROCESS_OF_MEMBER, MEMBER_B: PROCESS_OF_MEMBER,
                 DIALOG: PROCESS_OF_MEMBER, POPUP: PROCESS_OF_MEMBER,
                 BIG: PROCESS_OF_MEMBER, OLD_TWIN: PROCESS_OF_MEMBER,
                 TOOLWIN: PROCESS_OF_MEMBER, OURS: PROCESS_OF_MEMBER,
                 STRANGER: PROCESS_OF_STRANGER, CLICKED: PROCESS_OF_STRANGER,
                 CHILD: "child.exe"}
# What a window REFUSES to shrink below — how a minimum size looks from here.
MINSIZE = {BIG: (1400, 900)}

RECTS: dict = {}
# Windows a MODAL dialog has disabled. A modal disables its owner until it is
# answered — that IS what modal means to Windows — and it is the one fact our
# leave sequence never used to ask about (owner report 2026-08-13).
DISABLED: set = set()
# Every DWM transition freeze, in order: hwnd -> is it frozen right now.
FROZEN: dict = {}
# Raw SetWindowPos moves — how a window is put BACK where Windows had it.
MOVED: list = []
# The invisible resize border every real window carries: the gap between
# GetWindowRect (what SetWindowPos speaks) and the DWM visible frame (what
# `_frame_rect` answers). Non-zero on purpose — with zeroes the two coordinate
# spaces collapse into one and a missing compensation is invisible.
BORDER = (7, 0, 7, 7)
# What EnumWindows would return — the sweep's whole eye (task 239). Mutable
# during a check on purpose: a window that opens WHILE the layout stays
# focused is the entire subject, and a set fixed at setup time could only ever
# describe a desk that never changes.
DESK_WINDOWS: set = set()
PLACED: list = []
LEDGER: dict = {}
MINIMIZED: list = []


def desk(fg, alive=None, owner=None):
    """One fake desktop, one fake ledger, one fake process table. Returns the
    (registry, connection) the guard is driven with."""
    RECTS.clear()
    RECTS.update(HOME)
    PLACED.clear()
    LEDGER.clear()
    MINIMIZED.clear()

    DISABLED.clear()
    FROZEN.clear()
    MOVED.clear()

    alive = alive if alive is not None else tuple(HOME)
    fake = with_win32(fg=fg, alive=alive, owner=owner or {DIALOG: MEMBER_A})
    fake.ShowWindow = lambda hwnd, cmd: MINIMIZED.append((hwnd, cmd))
    fake.IsWindowEnabled = lambda hwnd: 0 if hwnd in DISABLED else 1

    def _setwindowpos(hwnd, after, x, y, w, h, flags):
        # Windows' own two coordinate spaces, modelled rather than flattened:
        # SetWindowPos speaks GetWindowRect (invisible resize border included)
        # while `_frame_rect` answers the VISIBLE frame. A fake that treats
        # them as one cannot see a caller that forgot to compensate — which is
        # exactly the defect an independent review found in the first version
        # of this fix, after the gate had passed.
        MOVED.append((hwnd, (x, y, w, h)))
        bl, bt, br, bb = BORDER
        RECTS[hwnd] = (x + bl, y + bt, w - bl - br, h - bt - bb)
        return 1

    fake.SetWindowPos = _setwindowpos
    window_manager._border_offsets = lambda hwnd: BORDER
    window_manager.freeze_transitions = \
        lambda hwnd, disabled=True: FROZEN.__setitem__(hwnd, disabled)
    Raises().install()

    window_manager._frame_rect = lambda hwnd: RECTS.get(hwnd)
    window_manager._work_area = lambda rect: MONITOR
    window_manager.place_window = _place
    window_manager._topmost = LEDGER
    window_manager.mark_topmost = lambda hwnd: LEDGER.setdefault(hwnd, "exe")
    window_manager.drop_topmost = lambda hwnd: (LEDGER.pop(hwnd, None), True)[1]
    window_manager._ledger_save = lambda: None
    window_manager.wait_minimized = lambda hwnds, timeout_s=0: None

    desk_facts.pid_of = lambda hwnd: PIDS.get(hwnd, 0)
    desk_facts.parent_pids = lambda: dict(PARENTS)
    DESK_WINDOWS.clear()
    DESK_WINDOWS.update(alive)
    desk_facts.top_level_hwnds = lambda: set(DESK_WINDOWS)
    window_manager.is_listable = lambda hwnd: hwnd not in NOT_LISTABLE
    # THE MAKER'S CLAIM lives in its own module since 2026-08-17
    # (server/window_claim.py). Both records are cleared, and the process
    # NAME is faked too — `expect()` claims by process, so a fake desk whose
    # windows have no process name could not exercise that rule at all.
    window_claim._OURS.clear()
    window_claim._EXPECT.clear()
    # The remembered desk is module-level BY DESIGN — its whole job is to
    # outlive a connection (server/layout_popup.py → `remember_desk`) — so a
    # fake desk that did not reset it would carry one check's windows into the
    # next one's baseline and quietly make them old. Found by this file's own
    # watcher check going silent.
    layout_popup._DESK = None
    window_manager._process_name = lambda hwnd: PROCESS_NAMES.get(hwnd, "")

    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_A)
    conn = fresh_conn(active=0)
    # The baseline `focus_guard.watch` takes when the phone connects: what was
    # already standing. POPUP/BIG/STRANGER/CHILD open AFTER it, OLD_TWIN did not.
    conn["popup_known"] = {MEMBER_A, MEMBER_B, OLD_TWIN}
    return reg, conn


def _place(hwnd, rect):
    """The real `place_window`'s contract, faked: the ledger is marked BEFORE
    the landing is verified (that ordering is a live property — a window that
    refused its rect is still in the always-on-top band), an app never shrinks
    below its minimum, and the return value says whether it really landed."""
    PLACED.append((hwnd, tuple(rect)))
    LEDGER[hwnd] = "exe"
    x, y, w, h = rect
    mw, mh = MINSIZE.get(hwnd, (0, 0))
    RECTS[hwnd] = (x, y, max(w, mw), max(h, mh))
    return w >= mw and h >= mh


def centered(rect, region=REGION):
    x, y, w, h = rect
    rx, ry, rw, rh = region
    return (rx + (rw - w) // 2, ry + (rh - h) // 2, w, h)


def offers(conn):
    """The chips the watcher wants to send the phone."""
    return list(conn.get("popup_send") or [])


def ask(reg, conn, act=None):
    """One guard pass — the watcher noticing the window — and, when `act` is
    given, his TAP coming back through the real `pick()` (which is what the
    HTTP route calls). Returns the offers that were queued."""
    focus_guard.guard(reg, conn)
    queued = offers(conn)
    if act is not None and queued:
        popup_offers.pick(queued[-1]["id"], act)
    return queued


# ═══════════════ 1. he is ASKED, and nothing moves before he answers ═══════════
def check_a_new_window_is_offered_and_not_grabbed() -> bool:
    """HIS AMENDMENT (2026-08-11): when something new opens, the program ASKS
    whether to show it in the layout or leave it on the desktop. So the watcher
    noticing the window must move NOTHING — it must produce one chip, naming
    the window he is being asked about."""
    reg, conn = desk(fg=POPUP)
    queued = ask(reg, conn)
    if PLACED or LEDGER or reg.layouts[0].adopted:
        print(f"  DETAIL the window was grabbed without asking: {PLACED}")
        return False
    if len(queued) != 1 or queued[0]["type"] != "window_offer":
        print(f"  DETAIL he was not asked: {queued}")
        return False
    offer = queued[0]
    if not offer.get("id") or offer.get("title") != f"window {POPUP:#x}":
        print(f"  DETAIL the chip does not name the window: {offer}")
        return False
    return offer.get("layout") == "Work"


def check_the_chip_is_sent_once_per_window() -> bool:
    """The watcher runs four times a second. A chip that came back on every
    tick would be worse than the bug it answers — and it must really reach the
    phone, over the page's own socket."""
    # POPUP and not DIALOG: since 2026-08-13 a member's OWN dialog is placed
    # without a chip (his rule), so the window that still ASKS is the one whose
    # attribution is a guess — a new window of the member's process.
    reg, conn = desk(fg=POPUP)
    for _ in range(5):
        focus_guard.guard(reg, conn)
    if len(offers(conn)) != 1:
        print(f"  DETAIL {len(offers(conn))} chips for one window")
        return False

    sent: list = []
    real = popup_offers.notice_channel.page_socket

    class Sock:
        async def send_text(self, text):
            sent.append(text)

    popup_offers.notice_channel.page_socket = lambda: Sock()
    try:
        asyncio.run(popup_offers.flush_offers(conn))
    finally:
        popup_offers.notice_channel.page_socket = real
    if len(sent) != 1 or "window_offer" not in sent[0]:
        print(f"  DETAIL the chip never reached the phone: {sent}")
        return False
    # …and nothing is left queued to be sent a second time on the next poll.
    return not offers(conn)


def check_leaving_it_on_the_desktop_moves_nothing_ever() -> bool:
    """His other answer, and the DEFAULT one. Nothing on the PC moves, and the
    window is never asked about again — a chip that reappeared after he had
    already answered it would be the same nagging in a new place."""
    reg, conn = desk(fg=POPUP)
    ask(reg, conn, act="desktop")
    if PLACED or LEDGER or reg.layouts[0].adopted:
        print(f"  DETAIL a declined window was still moved: {PLACED}")
        return False
    conn["popup_send"].clear()
    for _ in range(5):
        focus_guard.guard(reg, conn)
    if offers(conn) or PLACED:
        print(f"  DETAIL he was asked again: {offers(conn)} / {PLACED}")
        return False
    return True


# ═══════════════ 2. and when he says YES, the placement rules run ═══════════════
def check_a_member_dialog_is_placed_on_its_parent_without_asking() -> bool:
    """HIS RULE OF 2026-08-13, and the correction of a whole round that fixed
    the wrong thing: "when a popup opens, WINDOWS throws it OUTSIDE the bounds
    of our window … the solution is that the POPUP of the PARENT APPLICATION is
    SHOWN IN ITS MIDDLE".

    Three separate promises, and each one is planted against below:

    * NO CHIP. The owner chain is Windows' own statement that this member
      raised this window — not a guess like every other rule here — so asking
      him to confirm his app's own dialog is asking him to confirm nothing.
    * ON THE PARENT, not on the region. A four-grid dialog belongs on the
      window that raised it, and the two rects are deliberately different here
      so a check cannot pass by measuring the wrong one.
    * The LEDGER still owes it a way back down (constraint 10) — it is in the
      always-on-top band now, and nothing we raise may outlive us there.
    """
    reg, conn = desk(fg=DIALOG)
    target = focus_guard.guard(reg, conn)
    if target != DIALOG:
        print(f"  DETAIL focus was yanked to {target:#x} instead of the dialog")
        return False
    if offers(conn):
        print(f"  DETAIL his app's own dialog still asked him: {offers(conn)}")
        return False
    want = centered(HOME[DIALOG], HOME[MEMBER_A])
    if PLACED != [(DIALOG, want)]:
        print(f"  DETAIL the dialog was placed {PLACED}, expected it centered "
              f"on its PARENT at {want} (the region would be "
              f"{centered(HOME[DIALOG])})")
        return False
    if DIALOG not in LEDGER or DIALOG not in reg.layouts[0].adopted:
        print("  DETAIL the dialog is in the picture but nothing owes it a way "
              f"back down (ledger={list(LEDGER)}, adopted="
              f"{reg.layouts[0].adopted})")
        return False
    # …and the MEMBER stays the remembered keyboard target, as before.
    return reg.layouts[0].last_member == MEMBER_A


def check_a_new_window_of_a_members_process_is_adopted() -> bool:
    """The agent's report window: same process as the member (it IS the
    member's app), opened while he watched. Nothing owns it, so the owner
    chain says nothing — it is attributed because it is NEW and shares the
    member's process, and his tap puts it in the picture."""
    reg, conn = desk(fg=POPUP)
    ask(reg, conn, act="layout")
    if PLACED != [(POPUP, centered(HOME[POPUP]))]:
        print(f"  DETAIL placed={PLACED}")
        return False
    # …and from now on the keyboard may sit on it: it is the layout's window.
    return (POPUP in reg.layouts[0].adopted
            and focus_guard.guard(reg, conn) == POPUP)


def check_a_window_a_member_started_is_adopted() -> bool:
    """A viewer the member launched: a different process, but its parent is
    the member's. That link is the only thing tying a third-party window to
    the layout, and it is read from the process table."""
    reg, conn = desk(fg=CHILD)
    ask(reg, conn, act="layout")
    if not PLACED:
        print("  DETAIL nothing was placed — it was never attributed")
        return False
    return PLACED[0] == (CHILD, centered(HOME[CHILD]))


def check_a_popup_too_big_to_fit_goes_full_screen() -> bool:
    """The second half of his sentence: a window that cannot fit the layout's
    dimensions opens separate, over the whole screen. Which branch applies is
    MEASURED — it is ASKED to take the region first, and only its refusal
    (a minimum size larger than the region) sends it full screen."""
    reg, conn = desk(fg=BIG)
    ask(reg, conn, act="layout")
    if [rect for _, rect in PLACED] != [REGION, MONITOR]:
        print(f"  DETAIL the big window was placed {PLACED}, expected the "
              f"region {REGION} first and then the full screen {MONITOR}")
        return False
    if RECTS[BIG][:2] != MONITOR[:2]:
        print(f"  DETAIL it ended up at {RECTS[BIG]}, not on the monitor")
        return False
    return BIG in LEDGER and BIG in reg.layouts[0].adopted


# ═══════════════ 2. and NOTHING else is touched ═══════════════
def check_a_foreign_window_is_still_refused_exactly_as_before() -> bool:
    """THE SAFETY PROPERTY. Another agent's window taking the foreground is
    the failure constraint 11 exists for: focus goes straight back to the
    member the phone was typing into, the thief is named, and NOTHING of his
    is moved, resized or nailed above everything by a session it has nothing
    to do with."""
    reg, conn = desk(fg=STRANGER)
    raises = Raises().install()
    target = focus_guard.guard(reg, conn)
    if target != MEMBER_A or raises != [(MEMBER_A, True)]:
        print(f"  DETAIL target={target:#x} raises={raises} — the fence did "
              "not hand the keyboard back")
        return False
    if PLACED or LEDGER or reg.layouts[0].adopted:
        print(f"  DETAIL a stranger's window was adopted: placed={PLACED} "
              f"ledger={list(LEDGER)}")
        return False
    if offers(conn):
        print(f"  DETAIL he was asked about a stranger's window: {offers(conn)}")
        return False
    return True


def check_the_other_window_of_the_same_app_is_never_adopted() -> bool:
    """Every VS Code window shares ONE process (constraint 11), and one of
    them is exactly the thief — his other project's session. Process identity
    may therefore never decide on its own: a window that was already standing
    when the phone connected is refused however well its process matches."""
    reg, conn = desk(fg=OLD_TWIN)
    raises = Raises().install()
    target = focus_guard.guard(reg, conn)
    if target != MEMBER_A or raises != [(MEMBER_A, True)]:
        print(f"  DETAIL target={target:#x} raises={raises}")
        return False
    if PLACED or offers(conn):
        print(f"  DETAIL his other window was moved or asked about: {PLACED} "
              f"{offers(conn)}")
        return False
    return True


def check_nothing_happens_without_a_layout_or_a_watching_phone() -> bool:
    """Two conditions, both already the fence's: at the DESKTOP there is no
    region to contain anything in, and while the phone is away those windows
    belong to the desk again. Neither may move a window."""
    reg, conn = desk(fg=POPUP)
    conn["active"] = None
    focus_guard.guard(reg, conn)              # the desktop: no layout at all
    if PLACED or offers(conn):
        print(f"  DETAIL something happened with no layout focused: {PLACED} "
              f"{offers(conn)}")
        return False

    reg, conn = desk(fg=POPUP)
    conn["away"] = True
    # The raises are the watcher's own footprint: a pass that ran at all would
    # hand the keyboard back to the member. Read here rather than assumed,
    # because the offer queue alone cannot tell (the watcher drains it).
    raises = Raises().install()

    async def run():
        task = asyncio.ensure_future(focus_guard.watch(reg, conn))
        await asyncio.sleep(focus_guard.WATCH_POLL_S * 3)
        task.cancel()

    asyncio.run(run())
    if PLACED or offers(conn) or raises:
        print(f"  DETAIL the watcher acted while the phone was away: "
              f"{PLACED} {offers(conn)} {raises}")
        return False
    return True


# ═══════════════ 3. the way back down (constraint 10) ═══════════════
def check_the_ledger_lets_it_go_on_desktop_focus() -> bool:
    """Nothing we raise may outlive the showing of the layout it belongs to.
    Desktop is the path he takes when he wants the popup itself — so it leaves
    the always-on-top band and is NOT minimized with the members, which would
    be his original complaint in a new place.

    NOT forgotten either (defect 1, owner report 2026-08-13, the SAME evening
    as the rest of this file — "another layout OR the desktop, and come back"):
    a plain Desktop tap keeps the session running, so `lay.adopted` stands and
    the next `focus()` of this layout re-contains the popup — see the fuller
    lifecycle proof in `tests/test_layout_adoption.py`. Only a TRUE session end
    (`minimize_members(session_end=True)`, wired to `presence.leave_session`)
    actually forgets it."""
    reg, conn = desk(fg=POPUP)
    ask(reg, conn, act="layout")
    if POPUP not in LEDGER:
        print("  DETAIL nothing to release — the popup never reached the ledger")
        return False
    reg.minimize_members()
    if POPUP in LEDGER:
        print(f"  DETAIL still in the always-on-top band after Desktop: "
              f"{list(LEDGER)}")
        return False
    if POPUP not in reg.layouts[0].adopted:
        print("  DETAIL Desktop forgot the adoption outright — the layout it "
              "belongs to will never re-contain it again")
        return False
    if any(hwnd == POPUP for hwnd, _ in MINIMIZED):
        print("  DETAIL the popup was minimized away with the members")
        return False
    return [hwnd for hwnd, _ in MINIMIZED] == [MEMBER_A, MEMBER_B]


def check_the_ledger_lets_it_go_on_disconnect_and_removal() -> bool:
    """The other two ways the layout stops being shown: the phone hangs up
    (`clear_topmost`, which walks the LEDGER and not the member lists) and the
    layout is removed. A popup must survive neither — and must never be closed
    by either: only the ✕ chooser closes windows, and only what he chose."""
    reg, conn = desk(fg=POPUP)
    ask(reg, conn, act="layout")
    reg.clear_topmost()
    if POPUP in LEDGER:
        print(f"  DETAIL the phone hung up and {POPUP:#x} stayed on top")
        return False

    reg, conn = desk(fg=POPUP)
    ask(reg, conn, act="layout")
    reg.remove(0)
    if POPUP in LEDGER or not window_manager.user32.IsWindow(POPUP):
        print("  DETAIL removal left the popup topmost, or closed it")
        return False
    return True


def check_a_dead_popup_leaves_the_list_by_itself() -> bool:
    """He closed the report at the desk. The layout must stop naming it — and
    hand its ledger entry back on the way out, because a handle nobody names
    is exactly the one that used to stay stranded up there."""
    reg, conn = desk(fg=POPUP)
    ask(reg, conn, act="layout")
    window_manager.user32.alive.discard(POPUP)
    reg.prune()
    return POPUP not in reg.layouts[0].adopted and POPUP not in LEDGER


# ═══════════════ 4. it is MEASURED, not remembered ═══════════════
def check_a_contained_popup_is_not_re_placed_four_times_a_second() -> bool:
    """The watcher runs every 0.25 s. A window already inside the picture must
    cost nothing — and one that walks back OUT (an app re-laying itself out)
    must be brought back, because a note of a placement is not a placement
    (constraint 13, the lesson the Move handle cost four rounds)."""
    reg, conn = desk(fg=POPUP)
    ask(reg, conn, act="layout")
    for _ in range(5):
        focus_guard.guard(reg, conn)
    if len(PLACED) != 1:
        print(f"  DETAIL {len(PLACED)} placements for one popup: {PLACED}")
        return False
    RECTS[POPUP] = (2000, 1100, 400, 300)     # it wandered off on its own
    focus_guard.guard(reg, conn)
    if len(PLACED) != 2 or PLACED[-1][1] != centered((2000, 1100, 400, 300)):
        print(f"  DETAIL a popup that left the region was not brought back: "
              f"{PLACED}")
        return False
    return True


def check_one_window_is_never_fought_forever() -> bool:
    """A window that refuses every rect we command must not be pushed four
    times a second for the rest of the session — the desk would be unusable
    and the log would be written by one app."""
    reg, conn = desk(fg=POPUP)
    focus_guard.guard(reg, conn)                  # the chip
    window_manager.place_window = lambda hwnd, rect: (
        PLACED.append((hwnd, tuple(rect))), False)[1]
    popup_offers.pick(offers(conn)[-1]["id"], "layout")   # he said yes
    for _ in range(10):
        focus_guard.guard(reg, conn)
    # Three tries, each of which asks for the region and then the full screen.
    if len(PLACED) > popup_contain.MAX_CONTAIN_TRIES * 3:
        print(f"  DETAIL {len(PLACED)} placement attempts — it is being fought")
        return False
    return len(PLACED) > 0


# ═══ 5. IT IS SEEN WHILE HE STAYS IN THE LAYOUT (task 239) ═══
# HIS FOURTH REPORT of one bug, and his own observation carried the mechanism:
# the chip appeared only after he LEFT the layout and came back. The checks
# above are exactly why nobody caught it — every one of them hands the popup
# the FOREGROUND, and the window this module was written about never gets it:
# it opens under the members' always-on-top band, Windows refuses the
# foreground to a process with no input of its own, and the guard one line
# above hands focus back into the layout anyway.
def check_a_window_opened_under_a_focused_layout_is_offered_at_once() -> bool:
    """A member has the foreground the whole time — which is the NORMAL state
    of a focused, defended layout — and the report window opens beneath it.
    The foreground eye sees nothing (that is the bug, asserted here so this
    check cannot quietly stop measuring it); the sweep sees it."""
    reg, conn = desk(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B, OLD_TWIN))
    focus_guard.guard(reg, conn)              # the layout is standing, defended
    DESK_WINDOWS.add(POPUP)                   # the agent opens its HTML report
    RECTS[POPUP] = HOME[POPUP]
    focus_guard.guard(reg, conn)              # the foreground eye, task 202
    if offers(conn):
        print("  DETAIL the foreground path saw it — this check no longer "
              "measures the reported failure")
        return False

    layout_popup.sweep(reg, conn)
    queued = offers(conn)
    if len(queued) != 1 or not queued[0]["id"].startswith(f"{POPUP:x}-"):
        print(f"  DETAIL no chip while the layout stayed focused: {queued}")
        return False
    if PLACED or LEDGER:
        print(f"  DETAIL the sweep MOVED something: {PLACED} {LEDGER}")
        return False
    return True


def check_it_is_not_asked_twice_when_he_then_switches_layout() -> bool:
    """His timeline continued: he changed layout, the window finally reached
    the foreground and the old path looked at it. TWO EYES, ONE ACT.

    The check used to drive a member's DIALOG here, deliberately: a dialog is
    attributed by its OWNER chain, so unlike every other case it stays
    attributable after the sweep has judged it, and only that made the "asked
    twice" defect visible at all. Since 2026-08-13 a dialog is PLACED and never
    asked — so the two eyes now have two different promises to keep, and both
    are checked, each with the fixture that can actually show it failing:

    * the dialog: seen by both eyes, it must never produce a chip from either;
    * the report window: chipped by the first eye, answered, and then never
      raised again by the second.
    """
    reg, conn = desk(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B, OLD_TWIN, DIALOG))
    layout_popup.sweep(reg, conn)
    window_manager.user32.fg = DIALOG
    focus_guard.guard(reg, conn)
    conn["popup_swept"] = 0.0                 # and the next sweep, unthrottled
    layout_popup.sweep(reg, conn)
    if offers(conn):
        print(f"  DETAIL the dialog asked after all: {offers(conn)}")
        return False
    if DIALOG not in reg.layouts[0].adopted:
        print("  DETAIL neither eye placed the dialog")
        return False

    reg, conn = desk(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B, OLD_TWIN, POPUP))
    layout_popup.sweep(reg, conn)
    first = len(offers(conn))
    window_manager.user32.fg = POPUP
    focus_guard.guard(reg, conn)
    conn["popup_swept"] = 0.0
    layout_popup.sweep(reg, conn)
    if first != 1 or len(offers(conn)) != 1:
        print(f"  DETAIL asked {len(offers(conn))} times, first pass {first}")
        return False
    # And once he has answered, neither eye asks again.
    popup_offers.pick(offers(conn)[-1]["id"], "desktop")
    conn["popup_swept"] = 0.0
    layout_popup.sweep(reg, conn)
    focus_guard.guard(reg, conn)
    if len(offers(conn)) != 1:
        print(f"  DETAIL re-asked after his answer: {offers(conn)}")
        return False
    return True


def check_the_watcher_itself_runs_the_sweep_and_the_chip_reaches_him() -> bool:
    """The wiring, end to end, with no layout change anywhere in it: the real
    `focus_guard.watch` loop, a window appearing MID-RUN, and the chip arriving
    on the page's own socket. A pure function nobody calls is a feature that
    does not exist — this project has paid for that lesson twice."""
    import notice_channel

    reg, conn = desk(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B, OLD_TWIN))
    released, restore = fake_listen(lambda _cb: True)
    ws = FakeWs([])
    was_page = notice_channel._page["ws"]
    notice_channel._page["ws"] = ws

    async def run():
        task = asyncio.ensure_future(focus_guard.watch(reg, conn))
        await asyncio.sleep(focus_guard.WATCH_POLL_S)
        DESK_WINDOWS.add(POPUP)               # it opens while he works
        RECTS[POPUP] = HOME[POPUP]
        # Long enough for the sweep's own cadence — "a few seconds", his
        # requirement — and no longer.
        await asyncio.sleep(layout_popup.SWEEP_EVERY_S + focus_guard.WATCH_POLL_S * 2)
        task.cancel()

    try:
        asyncio.run(run())
    finally:
        restore()
        notice_channel._page["ws"] = was_page

    chips = [m for m in ws.sent if m.get("type") == "window_offer"]
    if len(chips) != 1 or not chips[0]["id"].startswith(f"{POPUP:x}-"):
        print(f"  DETAIL the watcher sent {chips}")
        return False
    if PLACED:
        print(f"  DETAIL the watcher moved something: {PLACED}")
        return False
    return bool(released)


def check_the_sweep_is_silent_at_the_desktop_and_while_he_is_away() -> bool:
    """Same two conditions the foreground path already honours. A sweep that
    offered at the desktop would ask about a window with no region to put it
    in; one that offered while the phone is away would ask nobody."""
    reg, conn = desk(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B, OLD_TWIN, POPUP))
    conn["active"] = None
    layout_popup.sweep(reg, conn)
    if offers(conn):
        print(f"  DETAIL offered at the desktop: {offers(conn)}")
        return False

    reg, conn = desk(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B, OLD_TWIN, POPUP))
    conn["away"] = True
    layout_popup.sweep(reg, conn)
    if offers(conn):
        print(f"  DETAIL offered while the phone was away: {offers(conn)}")
        return False

    # And with no baseline yet, nothing is new — the rule `handle` already has.
    reg, conn = desk(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B, OLD_TWIN, POPUP))
    conn.pop("popup_known")
    layout_popup.sweep(reg, conn)
    return not offers(conn)


def check_the_sweep_offers_a_stranger_but_still_moves_nothing() -> bool:
    """A STRANGER IS NOW OFFERED, AND THAT IS THE OWNER'S OWN DECISION
    (2026-08-17, off a ballot) — this check used to assert the opposite and is
    rewritten rather than deleted, because the reversal is the point.

    His report: the app asked him only about windows HE had just made and was
    silent about the ones somebody else made, "and there I DO want a layout
    from it". A stranger — its own process, no ancestry, no click — is exactly
    an agent's report window, and refusing it was the silence he reported. The
    catch-all that offers it lives in `sweep` and has its own gate
    (tests/test_window_offer.py).

    WHAT MUST NOT CHANGE is the half this file has always been about, and it is
    what is asserted here: an offer is a QUESTION. Nothing is placed, raised,
    resized or moved before his tap — a wrong guess must cost him a chip he can
    decline and never a window that has been taken."""
    reg, conn = desk(fg=MEMBER_A,
                     alive=(MEMBER_A, MEMBER_B, OLD_TWIN, STRANGER))
    layout_popup.sweep(reg, conn)
    queued = offers(conn)
    if len(queued) != 1 or queued[0].get("process") != PROCESS_OF_STRANGER:
        print(f"  DETAIL the stranger was not offered: {queued}")
        return False
    if PLACED or LEDGER or MOVED:
        print(f"  DETAIL the chip MOVED something: {PLACED} {LEDGER} {MOVED}")
        return False
    # And he is asked ONCE. A window that keeps failing to be attributed must
    # not be re-offered on every pass — the rule the old grace protected.
    conn["popup_swept"] = 0.0
    layout_popup.sweep(reg, conn)
    if len(offers(conn)) != 1:
        print(f"  DETAIL re-asked on the next pass: {offers(conn)}")
        return False
    return True


def check_a_members_dialog_is_swept_however_old_it_is() -> bool:
    """THE OWNER'S OWN REASONING, 2026-08-12: "if the desktop minimizes it WITH
    the layout, does it know that window belongs to it?" It does — Windows
    takes an OWNED window down with its owner, and `minimize_members` touches
    only real members.

    So the owner chain is evidence that does not need the baseline, and
    `_attribute` has always agreed: its FIRST rule is the owner root,
    deliberately ahead of the newness test. But `sweep` threw such a window
    away one line earlier, so that rule could never run for a dialog raised
    while the phone was away — which is precisely the window he reported.

    Both halves are checked, because only the pair is the rule: an OLD dialog
    of a member is ACTED ON, and his OLD second window of the same app — same
    process, no owner chain — is still refused. Losing the second half would
    be the fence gone.

    What "acted on" means changed on 2026-08-13 and the age rule did not: a
    dialog is now placed on its parent instead of chipped (his rule). So the
    outcome measured here is the PLACEMENT, and OLD_TWIN must reach neither
    the placement nor the chip — a fence that only held one of the two would
    still be a way to move his window.

    Defect planted: restoring the bare `if not _is_new(...): continue` fails
    this and nothing else."""
    reg, conn = desk(fg=MEMBER_A,
                     alive=(MEMBER_A, MEMBER_B, DIALOG, OLD_TWIN))
    # It was ALREADY STANDING when the phone connected — the locked-phone
    # shape, where nothing was watching at the moment it opened.
    conn["popup_known"] = {MEMBER_A, MEMBER_B, DIALOG, OLD_TWIN}
    layout_popup.sweep(reg, conn)
    got = {m.get("id", "").split("-")[0] for m in offers(conn)}
    offered = {int(h, 16) for h in got if h}
    placed = {h for h, _ in PLACED}
    if DIALOG not in placed:
        print("  DETAIL a member's own dialog was skipped for being old")
        return False
    if OLD_TWIN in offered or OLD_TWIN in placed:
        print("  DETAIL his OTHER window of the same app was adopted — the "
              "fence is gone")
        return False
    return True


# ═══ 6. THE CLICK CORRELATION (task 240) ═══
# His shape: an ALREADY-RUNNING third-party app (old Chrome, parent long dead)
# opens a new window because he clicked something through the stream. Rules 2
# and 3 both need the PROCESS to say something, and this window's process says
# nothing — the click he just made is the only evidence left.
def check_a_window_after_his_click_is_offered_with_no_process_tie() -> bool:
    """No owner chain, no shared process, no ancestry — CLICKED is exactly the
    stranger rule 2/3 could never reach. A click he injected moments earlier
    is what task 240 adds: it is offered through the ordinary chip, and
    nothing moves before his tap, same as every other case above."""
    reg, conn = desk(fg=CLICKED)
    conn["click_times"] = [time.monotonic() - 1.0]   # he clicked a second ago
    queued = ask(reg, conn)
    if PLACED or LEDGER or reg.layouts[0].adopted:
        print(f"  DETAIL grabbed without asking: {PLACED}")
        return False
    if len(queued) != 1 or queued[0]["title"] != f"window {CLICKED:#x}":
        print(f"  DETAIL not offered: {queued}")
        return False
    # …and his tap adopts it exactly as any other "Show in layout" answer.
    popup_offers.pick(queued[0]["id"], "layout")
    return CLICKED in reg.layouts[0].adopted and PLACED == [
        (CLICKED, centered(HOME[CLICKED]))]


def check_the_same_window_with_no_recent_click_is_still_refused() -> bool:
    """THE SAFETY PROPERTY for this rule: without a click in the grace window
    the old refusal must survive unwidened — an unattributable stranger stays
    a stranger just because a window happened to appear."""
    reg, conn = desk(fg=CLICKED)
    conn["click_times"] = [time.monotonic() - (layout_popup.CLICK_GRACE_S + 5)]
    queued = ask(reg, conn)
    if queued or PLACED:
        print(f"  DETAIL offered with a stale click: {queued} {PLACED}")
        return False
    # …and with no click at all.
    reg, conn = desk(fg=CLICKED)
    queued = ask(reg, conn)
    if queued or PLACED:
        print(f"  DETAIL offered with no click ever: {queued} {PLACED}")
        return False
    return True


def check_a_click_correlated_window_is_never_asked_twice() -> bool:
    """The one-chip-per-window rule must hold for this attribution path too —
    the watcher polls four times a second and the click stays 'recent' for
    the whole grace window."""
    reg, conn = desk(fg=CLICKED)
    conn["click_times"] = [time.monotonic() - 1.0]
    for _ in range(5):
        focus_guard.guard(reg, conn)
    if len(offers(conn)) != 1:
        print(f"  DETAIL {len(offers(conn))} chips for one click-correlated window")
        return False
    return True


# ═══ 7. WHAT MAY NEVER WEAR A CHIP AT ALL (owner report 2026-08-13) ═══
def check_a_window_no_layout_could_hold_is_never_offered() -> bool:
    """HIS POINT 3: the phone kept asking him about things that are not windows
    he can do anything with — and when he tapped, the creation list did not
    even carry them.

    The two lists were built by different code. `wm.list_windows` (the creation
    list) drops tool windows, cloaked surfaces and untitled windows; the popup
    sweep's own eye was `IsWindowVisible` and nothing else. So a member's TOOL
    window is attributable by every rule here, and it is exactly what a chip
    may not name: a question the app cannot honour is worse than no question.

    TOOLWIN is a member's own process and NEW, so it passes attribution — the
    only thing standing between it and a chip is the listability test."""
    reg, conn = desk(fg=MEMBER_A,
                     alive=(MEMBER_A, MEMBER_B, TOOLWIN, POPUP))
    layout_popup.sweep(reg, conn)
    named = {int(m.get("id", "").split("-")[0], 16) for m in offers(conn)
             if m.get("id")}
    if TOOLWIN in named:
        print("  DETAIL a tool window was offered as a layout member")
        return False
    # …and the real window beside it still is, so this is a filter and not a
    # switch that turned the feature off.
    if POPUP not in named:
        print(f"  DETAIL the filter ate the real window too: {named}")
        return False
    return True


def check_a_window_we_made_ourselves_is_never_offered() -> bool:
    """HIS POINT 4A: he taps "create a layout from a tap" inside a layout,
    picks a TAB of that layout, and the moment the layout is built the phone
    asks whether to show the brand-new window in it.

    Every rule is RIGHT about that window — new, a member's process, moments
    after an injected click — which is why no attribution rule could ever fix
    it. Only the maker knows, and `layout_popup.mine()` is the maker saying so.

    Also checked: the record EXPIRES. A window handle is a number Windows
    re-uses, and a permanent record would one day silence a chip about a
    stranger's window that inherited it."""
    reg, conn = desk(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B, OURS))
    layout_popup.mine(OURS)
    layout_popup.sweep(reg, conn)
    if offers(conn):
        print(f"  DETAIL the tab we tore off was offered back to him: "
              f"{offers(conn)}")
        return False
    reg, conn = desk(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B, OURS))
    window_claim._OURS[OURS] = time.monotonic() - window_claim.OURS_TTL_S - 1
    layout_popup.sweep(reg, conn)
    if not offers(conn):
        print("  DETAIL a long-expired record still silences the chip — a "
              "recycled handle would be muted forever")
        return False
    return True


def check_a_dialog_too_big_for_its_parent_still_lands_in_the_picture() -> bool:
    """The anchor is a PREFERENCE, never a promise. A dialog larger than the
    one cell its parent occupies cannot be centered on it — and the guarantee
    it must not lose is the one he actually cares about: it is inside the
    picture the phone is streaming. So it falls through to the region, exactly
    as it did before there was an anchor at all."""
    reg, conn = desk(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B, DIALOG))
    # Wider than MEMBER_A's cell, still inside the region.
    RECTS[DIALOG] = (1900, 1000, 900, 400)
    layout_popup.sweep(reg, conn)
    want = centered(RECTS[DIALOG])
    if PLACED != [(DIALOG, want)]:
        print(f"  DETAIL placed {PLACED}, expected the region fallback {want}")
        return False
    return True


CHECKS = [
    ("a new window is OFFERED to the phone, never grabbed",
     check_a_new_window_is_offered_and_not_grabbed),
    ("the chip is sent once per window, and really reaches the phone",
     check_the_chip_is_sent_once_per_window),
    ("'Leave on desktop' moves nothing, ever, and is not asked twice",
     check_leaving_it_on_the_desktop_moves_nothing_ever),
    ("a member's dialog that FITS is placed inside the region",
     check_a_member_dialog_is_placed_on_its_parent_without_asking),
    ("a NEW window of a member's own process is adopted",
     check_a_new_window_of_a_members_process_is_adopted),
    ("a window a member STARTED is adopted",
     check_a_window_a_member_started_is_adopted),
    ("one that cannot fit opens full screen on the streamed monitor",
     check_a_popup_too_big_to_fit_goes_full_screen),
    ("a foreign window is still refused EXACTLY as before",
     check_a_foreign_window_is_still_refused_exactly_as_before),
    ("his other window of the same app is never adopted",
     check_the_other_window_of_the_same_app_is_never_adopted),
    ("nothing happens with no layout focused / the phone away",
     check_nothing_happens_without_a_layout_or_a_watching_phone),
    ("Desktop releases it from the topmost band, and does not minimize it",
     check_the_ledger_lets_it_go_on_desktop_focus),
    ("a disconnect and a removal release it too, and never close it",
     check_the_ledger_lets_it_go_on_disconnect_and_removal),
    ("a popup closed at the desk leaves the layout by itself",
     check_a_dead_popup_leaves_the_list_by_itself),
    ("a contained popup is not re-placed on every poll, but a wandering one is",
     check_a_contained_popup_is_not_re_placed_four_times_a_second),
    ("one window is never fought forever",
     check_one_window_is_never_fought_forever),
    ("it is offered WHILE the layout stays focused, with no foreground",
     check_a_window_opened_under_a_focused_layout_is_offered_at_once),
    ("and never asked twice when he then switches layout",
     check_it_is_not_asked_twice_when_he_then_switches_layout),
    ("the watcher itself sweeps, and the chip reaches the page's socket",
     check_the_watcher_itself_runs_the_sweep_and_the_chip_reaches_him),
    ("the sweep is silent at the desktop, while away, and with no baseline",
     check_the_sweep_is_silent_at_the_desktop_and_while_he_is_away),
    ("the sweep offers a stranger, but still moves nothing",
     check_the_sweep_offers_a_stranger_but_still_moves_nothing),
    ("a member's own dialog is swept however old it is, his twin still is not",
     check_a_members_dialog_is_swept_however_old_it_is),
    ("a window after his click is offered with no process tie (task 240)",
     check_a_window_after_his_click_is_offered_with_no_process_tie),
    ("the same window with no recent click is still refused",
     check_the_same_window_with_no_recent_click_is_still_refused),
    ("a click-correlated window is never asked twice",
     check_a_click_correlated_window_is_never_asked_twice),
    ("a window no layout could hold is never offered (his point 3)",
     check_a_window_no_layout_could_hold_is_never_offered),
    ("a window WE made is never offered back to him (his point 4A)",
     check_a_window_we_made_ourselves_is_never_offered),
    ("a dialog too big for its parent still lands in the picture",
     check_a_dialog_too_big_for_its_parent_still_lands_in_the_picture),
]


def main() -> int:
    return run_checks("LAYOUT POPUP GATE", CHECKS,
                      "a window the layout's work opens stays reachable.")


def test_layout_popup():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
