"""LOST WINDOW GATE — there is ALWAYS a way back, whoever opened the window.

The owner reported one failure FIVE times: a window that opened while his
phone was locked stands off every screen, and no phone can ever show it again.
Four rounds "fixed" it and none of them could even SEE it, because every rule
in [Layout Popup](../server/layout_popup.py) is built on a baseline taken when
the phone connects — and a window born while nothing was connected is filed as
already-known by that very baseline. The whole point of
[Lost Windows](../server/lost_windows.py) is that it asks GEOMETRY (can he
reach it) instead of HISTORY (who opened it), so this gate's first duty is to
prove that the answer really is independent of history.

What is held here, each proven by planting its own defect:

  1. A window off every screen is found — with NO baseline, NO connection
     history and no attribution of any kind. This is his exact case.
  2. A sliver at the screen edge is still LOST. "Some pixels are technically
     visible" is not a way out, and treating it as one is the disease.
  3. A minimized window is judged by where it would RESTORE to. His report
     window went down with the layout that owned it, so a check that skipped
     minimized windows would have found nothing wrong.
  4. A layout's own windows are never offered — the layout can move them.
  5. The rescue RESTORES BEFORE it places. The other order looks like it works
     and moves nothing he can see.
  6. The rescue never raises topmost (constraint 10) — nothing we raise may
     outlive us in the always-on-top band.
  7. An act the server does not recognise LEAVES THE WINDOW ALONE.
  8. The monitor is read at his TAP, through the callable, never remembered
     from when the chip went out (constraint 13).

NOTHING HERE TOUCHES THE OWNER'S DESKTOP. No window is enumerated, moved,
restored or raised: `window_manager`'s Win32 is a fake, `list_windows` is a
list this file writes, and every placement is recorded rather than performed.

Run:  .venv\\Scripts\\python tests/test_lost_windows.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _focus_fakes import fresh_conn, run_checks, window_manager  # noqa: E402

import layout_popup  # noqa: E402
import lost_windows  # noqa: E402

# One 1920x1080 screen with a 40 px taskbar — the work area every rect below
# is judged against.
SCREEN = [(0, 0, 1920, 1040)]

STRANDED = 0x70        # the HTML report, off the right edge entirely
SLIVER = 0x71          # 30 px of it peeking in at the left edge
HOME = 0x72            # an ordinary window, sitting where it should
SLEEPING = 0x73        # minimized, and its restore rect is off-screen
MEMBER = 0x74          # a layout member — and OFF-SCREEN, deliberately
HEADLESS = 0x75        # body on screen, title bar above the top edge

RECTS = {
    STRANDED: (3000, 200, 900, 700),
    SLIVER: (-870, 300, 900, 700),      # only its rightmost 30 px are on
    HOME: (300, 200, 900, 700),
    SLEEPING: (2400, 400, 800, 600),
    # OFF-SCREEN ON PURPOSE. A member sitting comfortably on the desk would be
    # excluded by geometry alone, and the exclusion rule would go untested —
    # the check would pass with the rule deleted.
    MEMBER: (2600, 0, 960, 1040),
    # THE CASE THAT SEPARATES "grabbable" FROM "visible". Most of this window
    # is on the screen and a whole-window overlap test calls it reachable, but
    # its title bar is 400 px above the top edge: there is nothing to grab, so
    # it is exactly as lost as the one off the right edge.
    HEADLESS: (300, -400, 900, 700),
}


class FakeWin32:
    """The user32 calls `lost_windows` makes. Placements and shows are
    RECORDED in order — the order is what check 5 is about."""

    def __init__(self, iconic=()):
        self.iconic = set(iconic)
        self.acts: list[tuple] = []

    def IsWindow(self, hwnd):             # noqa: N802 — mirrors the Win32 name
        return 1 if hwnd in RECTS else 0

    def IsIconic(self, hwnd):             # noqa: N802
        return 1 if hwnd in self.iconic else 0

    def IsWindowVisible(self, hwnd):      # noqa: N802
        return 0 if hwnd in self.iconic else 1

    def GetWindowPlacement(self, hwnd, ptr):     # noqa: N802
        # The real call fills rcNormalPosition; the module reads it straight
        # after, so the fake fills the same struct the same way.
        x, y, w, h = RECTS[hwnd]
        wp = ptr._obj
        wp.rcNormalPosition.left, wp.rcNormalPosition.top = x, y
        wp.rcNormalPosition.right, wp.rcNormalPosition.bottom = x + w, y + h
        self.acts.append(("placement", hwnd))
        return 1

    def ShowWindow(self, hwnd, cmd):      # noqa: N802
        self.acts.append(("show", hwnd, cmd))
        if cmd == lost_windows.SW_RESTORE:
            self.iconic.discard(hwnd)
        return 1

    def __getattr__(self, name):
        return lambda *a, **k: 0


def install(iconic=(), placed_ok=True):
    """Point both modules at the fake desk. Returns (fake, placements, raises)
    — placements and raises are lists, so nothing is performed anywhere."""
    fake = FakeWin32(iconic)
    placements: list[tuple] = []
    raises: list[tuple] = []
    lost_windows.user32 = fake
    window_manager.user32 = fake
    lost_windows.work_areas = lambda: list(SCREEN)
    # WHAT WINDOWS REALLY REPORTS FOR A MINIMIZED WINDOW, and the gate is
    # worthless without it: an iconic window's frame is the off-screen
    # placeholder (~-32000), NOT where it will come back to. A fake that
    # returned the same rect either way would let `resting_rect` ignore
    # `GetWindowPlacement` entirely and still pass check 3 — the gate proving
    # its own convenience to itself, which is this project's oldest lesson.
    lost_windows.wm._frame_rect = lambda hwnd: (
        (-32000, -32000, 160, 28) if hwnd in fake.iconic else RECTS.get(hwnd))
    lost_windows.wm._work_area = lambda rect: SCREEN[0]
    lost_windows.wm._title = lambda hwnd: f"window {hwnd:#x}"
    lost_windows.wm.freeze_transitions = lambda hwnd, disabled=True: None

    def _place(hwnd, rect):
        placements.append((hwnd, rect))
        # ALSO into the act log, in ORDER, beside the restore — the whole
        # defect check 6 exists for is the two happening the wrong way round,
        # and a separate list can only say THAT they happened.
        fake.acts.append(("place", hwnd, rect))
        return placed_ok

    def _raise(hwnd, topmost=True):
        raises.append((hwnd, topmost))

    lost_windows.wm.place_window = _place
    lost_windows.wm.raise_window = _raise
    lost_windows.wm.list_windows = lambda exclude=None: [
        {"hwnd": h, "title": f"window {h:#x}",
         "process": f"app{h:x}.exe", "icon": None} for h in RECTS
    ]
    return fake, placements, raises


# ═══════════════════════════ 1-3: WHAT IS LOST ═══════════════════════════
def check_stranded_is_found():
    """HIS CASE. A window off every screen is on the list — and the list is
    reached with no baseline, no connection and no attribution, which is the
    whole reason this module exists.

    Defect planted: making `reachable` answer True for anything drops it."""
    install()
    found = {w["hwnd"] for w in lost_windows.lost()}
    return STRANDED in found and HOME not in found


def check_a_sliver_is_not_a_way_out():
    """30 px showing at the screen edge is not a handle. He cannot grab a
    title bar he cannot see, and calling that reachable is exactly how this
    survived four rounds.

    And the case that really separates GRABBABLE from VISIBLE: `HEADLESS` has
    most of its body on the screen and only its title bar above the top edge.
    A whole-window overlap test calls that reachable; a hand cannot reach it
    at all.

    Defect planted: testing the whole window's overlap instead of the title
    strip's `GRAB_WIDTH_PX` fails on HEADLESS."""
    install()
    found = {w["hwnd"] for w in lost_windows.lost()}
    return SLIVER in found and HEADLESS in found


def check_minimized_is_judged_by_its_restore_rect():
    """His report window went DOWN with the layout that owned it. Judged as
    it stands, a minimized window has no meaningful rect at all; judged by
    `rcNormalPosition`, it is exactly as lost as it will be the moment anyone
    restores it.

    Both directions, because only the pair is the rule: SLEEPING restores
    off-screen and must be listed, HOME minimized restores on-screen and must
    NOT be — the taskbar reaches that one, and so does he."""
    install(iconic=[SLEEPING, HOME])
    found = {w["hwnd"] for w in lost_windows.lost()}
    return SLEEPING in found and HOME not in found


def check_layout_members_are_never_offered():
    """The layout put them there and the layout can move them; a rescue chip
    over a member would fight the arrangement he asked for."""
    install()
    found = {w["hwnd"] for w in lost_windows.lost({MEMBER})}
    return MEMBER not in found and STRANDED in found


def check_the_target_lands_inside_the_work_area():
    """Pure arithmetic, checked without a screen: a rescued window keeps its
    own size where that fits and is centered, and a window bigger than the
    screen is cut down to the work area minus its margin — never left larger
    than the place it is being rescued to."""
    area = SCREEN[0]
    x, y, w, h = lost_windows._target((3000, 200, 900, 700), area)
    small_ok = (w, h) == (900, 700) and x >= 0 and y >= 0 \
        and x + w <= area[2] and y + h <= area[3]
    _, _, bw, bh = lost_windows._target((3000, 200, 5000, 4000), area)
    m = lost_windows.RESCUE_MARGIN_PX
    return small_ok and bw == area[2] - 2 * m and bh == area[3] - 2 * m


# ═══════════════════════════ 5-6: THE RESCUE ═══════════════════════════
def check_restore_comes_before_the_placement():
    """A minimized window takes `SetWindowPos` geometry into its stored
    placement WITHOUT coming back, so placing first looks like a success and
    changes nothing he can see. The order is the fix, so the order is checked.

    Defect planted: swapping the two statements in `rescue` fails here while
    every other check in this file still passes."""
    fake, placements, _ = install(iconic=[SLEEPING])
    lost_windows.rescue(SLEEPING, (0, 0, 1920, 1080))
    order = [a[0] for a in fake.acts if a[0] in ("show", "place")]
    return order[:2] == ["show", "place"] and len(placements) == 1


def check_the_rescue_never_raises_topmost():
    """CONSTRAINT 10. A rescued window is a normal window on his desk, not a
    member of anything — and a topmost raise here would strand it above
    everything for the rest of the Windows session, which is the ledger's
    whole reason for existing."""
    _, _, raises = install()
    lost_windows.rescue(STRANDED, (0, 0, 1920, 1080))
    return bool(raises) and all(topmost is False for _, topmost in raises)


def check_a_refused_placement_still_raises_and_reports():
    """Half a rescue is still worth performing — a window that would not take
    the rect may still have come out of the taskbar — but it must be REPORTED
    as a failure, never as a success, so the sweep asks again."""
    _, _, raises = install(placed_ok=False)
    ok = lost_windows.rescue(STRANDED, (0, 0, 1920, 1080))
    return ok is False and bool(raises)


# ═══════════════════════════ 7-8: THE CHIP ═══════════════════════════
def _armed_conn():
    """A connection with one rescue chip out for the stranded window."""
    conn = fresh_conn()
    conn["mon_rect"] = lambda: (0, 0, 1920, 1080)
    layout_popup.sweep_lost(None, conn)
    sent = conn.get("popup_send") or []
    return conn, sent


def check_the_chip_is_offered_at_the_desktop_too():
    """The case he reported happened with NO layout focused, so a sweep that
    only ran inside a layout would be the same blindness in a new place."""
    install()
    conn, sent = _armed_conn()
    return any(m.get("act") == "rescue" and m.get("hwnd") == STRANDED
               for m in sent)


def check_an_unknown_act_leaves_the_window_alone():
    """The safe answer must be the DEFAULT one: of the two outcomes only one
    moves his window, so a message that lost its field on the way must land on
    the one that does nothing."""
    install()
    conn, sent = _armed_conn()
    offer = next(m for m in sent if m.get("hwnd") == STRANDED)
    _, placements, raises = install()
    layout_popup.pick(offer["id"], "wat")
    return not placements and not raises \
        and STRANDED in conn.get("lost_left", set())


def check_the_monitor_is_read_at_the_tap():
    """CONSTRAINT 13, in its smallest form. The chip may sit on his screen for
    half a minute, and he may switch monitors in that time — so the rescue
    must ask WHERE THE PHONE IS LOOKING when he taps, not when the chip was
    queued.

    Defect planted: reading `mon_rect()` inside `_offer_lost` and storing the
    value makes the rescue land on the monitor he walked away from."""
    install()
    conn, sent = _armed_conn()
    offer = next(m for m in sent if m.get("hwnd") == STRANDED)
    # He switches monitors AFTER the chip went out.
    seen: list = []
    conn["mon_rect"] = lambda: seen.append("asked") or (1920, 0, 1920, 1080)
    install()
    lost_windows.wm._work_area = lambda rect: (rect[0], rect[1], 1920, 1040)
    _, placements, _ = install()
    lost_windows.wm._work_area = lambda rect: (rect[0], rect[1], 1920, 1040)
    layout_popup.pick(offer["id"], "rescue")
    if not seen or not placements:
        return False
    x = placements[0][1][0]
    return x >= 1920          # landed on the SECOND monitor, where he now is


CHECKS = [
    ("a window off every screen is found, with no history at all",
     check_stranded_is_found),
    ("a sliver at the screen edge is still lost", check_a_sliver_is_not_a_way_out),
    ("a minimized window is judged by its restore rect",
     check_minimized_is_judged_by_its_restore_rect),
    ("a layout's own windows are never offered",
     check_layout_members_are_never_offered),
    ("the rescue target lands inside the work area",
     check_the_target_lands_inside_the_work_area),
    ("restore comes before the placement", check_restore_comes_before_the_placement),
    ("the rescue never raises topmost", check_the_rescue_never_raises_topmost),
    ("a refused placement still raises, and reports failure",
     check_a_refused_placement_still_raises_and_reports),
    ("the chip is offered at the desktop too",
     check_the_chip_is_offered_at_the_desktop_too),
    ("an act we do not recognise leaves the window alone",
     check_an_unknown_act_leaves_the_window_alone),
    ("the monitor is read at his tap, never remembered",
     check_the_monitor_is_read_at_the_tap),
]


def main() -> int:
    return run_checks("LOST WINDOW GATE", CHECKS,
                      "an unreachable window always has a way back")


if __name__ == "__main__":
    sys.exit(main())
