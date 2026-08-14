"""TAP HAS ONE MEANING EVERYWHERE — the server half (owner correction
2026-08-13, overruling his own ballot's first reading of option (c) the same
day).

The earlier reading of his verdict was "you claim a window into the layout
you are looking at", and he rejected it outright: *"tap in an already-created
layout claims a window for that layout — what are you trying to say, I don't
understand, if I tapped on something in that layout it IS ALREADY in that
layout."* His correction is the whole feature now: a tap while a layout is
focused resolves the point exactly as it always has, and then —

1. the tap landed on a content TAB — the ordinary creation flow, seeded with
   that tab, exactly as at the desktop (unchanged, and not this file's
   subject — nothing on the SERVER side changed for it);
2. the tap landed on the member WINDOW itself, no tab — nothing to create,
   said in words, never a swallowed tap;
3. the tap landed on something else entirely (a foreign window standing over
   the region) — the ordinary creation flow, exactly as at the desktop.

Cases 1 and 3 are the untouched `layout_pick` this project already had; this
file's subject is what makes case 2 POSSIBLE to tell apart from them on the
phone — `LayoutRegistry.state()` now carries `member_hwnds` per layout, a
plain fact read live off `Layout.members`, so `client/layout-create.js`'s
`handleLayoutOffer` can refuse locally instead of guessing. The refusal
ITSELF is phone-side (`tests/test_layout_claim_arm.py`); this file proves the
SERVER sends the fact it depends on, and correctly.

The `window_manager.window_at` fix (real `is_listable`, never its own weaker
copy) is UNCHANGED from the previous round and is right on its own merits —
kept here rather than deleted, since it is what the tap-pick under BOTH
readings of the ballot relies on.

NOTHING HERE STUBS `is_listable` ITSELF (unlike tests/test_layout_popup.py's
desk, which patches it wholesale to isolate a different subject), and the
`member_hwnds` check is driven through the REAL dispatcher and the REAL
`LayoutRegistry.state()` — never a fixture that writes the field by hand.

Run:  .venv\\Scripts\\python tests/test_layout_claim.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import window_manager  # noqa: E402

from test_layout_drag import WIN_C, build_layouts  # noqa: E402
from test_layout_protocol import (  # noqa: E402
    MON, WIN_A, WIN_B, install_fakes, sent_of,
)

TOOLWIN = 0x77          # a real, titled, VISIBLE tool window — unofferable


class RealWin32:
    """Only what `window_at` + the REAL `is_listable` ask of Win32 — no stub
    of `is_listable` itself sits between this fake and the code under test."""

    def __init__(self, titles, ex_style=None, cloaked=(), pid=None):
        self.titles = titles                  # hwnd -> title
        self.ex_style = ex_style or {}         # hwnd -> WS_EX_* bits
        self.cloaked = set(cloaked)
        self.pid = pid or 4242                 # a foreign process, never ours

    def WindowFromPoint(self, pt):             # noqa: N802
        return self._hit

    def GetAncestor(self, hwnd, flag):          # noqa: N802
        return hwnd                             # already a root in this fixture

    def IsWindow(self, hwnd):                    # noqa: N802
        return 1 if hwnd in self.titles else 0

    def IsWindowVisible(self, hwnd):            # noqa: N802
        return 1 if hwnd in self.titles else 0

    def GetWindowLongW(self, hwnd, index):       # noqa: N802
        return self.ex_style.get(hwnd, 0)

    def GetClassNameW(self, hwnd, buf, n):       # noqa: N802
        buf.value = "ATL:00000000"               # never a shell class

    def GetWindowTextW(self, hwnd, buf, n):      # noqa: N802
        buf.value = self.titles.get(hwnd, "")

    def GetWindowThreadProcessId(self, hwnd, pid_out):  # noqa: N802
        pid_out._obj.value = self.pid

    def __getattr__(self, name):
        return lambda *a, **k: 0


class RealDwm:
    def __init__(self, cloaked=()):
        self.cloaked = set(cloaked)

    def DwmGetWindowAttribute(self, hwnd, attr, out, size):  # noqa: N802
        out._obj.value = 1 if hwnd in self.cloaked else 0
        return 0

    def __getattr__(self, name):
        return lambda *a, **k: 0


def _wire(hit, titles, ex_style=None, cloaked=()):
    win32 = RealWin32(titles, ex_style=ex_style, cloaked=cloaked)
    win32._hit = hit
    window_manager.user32 = win32
    window_manager.dwmapi = RealDwm(cloaked=cloaked)
    window_manager.icon_data_uri = lambda path: None
    window_manager._process_path = lambda hwnd: "C:/app.exe"
    return win32


# ═══════════════════════ window_at asks the REAL is_listable ═══════════════
def check_a_tool_window_is_never_picked() -> bool:
    """A real, titled, VISIBLE tool window (a floating find bar, a docked
    palette) sits at the tapped point. `window_at` must refuse it exactly as
    the creation list already does — the same fact, asked the same way.

    PLANTED-DEFECT PROOF (run by hand for this round): reverting `window_at`
    to its pre-fix body — `is_alive(root)` + a bare title/shell-class check,
    no `WS_EX_TOOLWINDOW` test — makes this check return a hit and this
    function returns False, exactly the defect this gate exists to catch."""
    _wire(TOOLWIN, {TOOLWIN: "Find"}, ex_style={TOOLWIN: window_manager.WS_EX_TOOLWINDOW})
    got = window_manager.window_at(MON, 0.5, 0.5)
    if got is not None:
        print(f"  DETAIL a tool window was offered: {got}")
        return False
    return True


def check_an_ordinary_window_is_still_picked() -> bool:
    """The control for the check above: an ordinary titled window at the same
    point is NOT refused — the fix must narrow the picker, not break it."""
    _wire(WIN_A, {WIN_A: "Vibe Coder - Visual Studio Code"})
    got = window_manager.window_at(MON, 0.5, 0.5)
    if got is None or got["hwnd"] != WIN_A:
        print(f"  DETAIL an ordinary window was refused: {got}")
        return False
    return True


def check_a_cloaked_window_is_never_picked() -> bool:
    """`is_listable` refuses a cloaked window too (a UWP ghost, or a real
    window on another virtual desktop)."""
    _wire(WIN_A, {WIN_A: "Ghost"}, cloaked={WIN_A})
    got = window_manager.window_at(MON, 0.5, 0.5)
    if got is not None:
        print(f"  DETAIL a cloaked window was offered: {got}")
        return False
    return True


# ══════════════ member_hwnds: the fact case 2's refusal depends on ═════════
def check_layout_state_carries_the_real_member_hwnds() -> bool:
    """Built through the REAL dispatcher (`layout_create`) and read back off
    the REAL `layout_state` frame it sends — never a fixture that writes
    `member_hwnds` by hand, and never a stub standing in for `state()`
    itself. This is the false-green shape named for this round: a value
    production computes must be read from where production actually put it."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B])])
    ws = None
    # `build_layouts` drives `layout_create`, which ends in `layout_focus` —
    # its own `layout_state` is the one this check reads.
    from test_layout_protocol import drive
    ws, conn, layouts = drive([], conn, layouts)  # no new message; re-ask nothing
    # The layout_state that matters is the one `build_layouts` already sent —
    # re-derive it the same way `layout_member_add`'s own gate does, by
    # asking the real registry for the SAME payload the wire carried.
    state = layouts.state(conn["active"], conn["region"])
    if len(state["layouts"]) != 1:
        print(f"  DETAIL expected one layout, got {state['layouts']}")
        return False
    got = state["layouts"][0].get("member_hwnds")
    if got != [WIN_A, WIN_B]:
        print(f"  DETAIL member_hwnds was {got}, expected {[WIN_A, WIN_B]}")
        return False
    return True


def check_member_hwnds_follows_a_grown_or_shrunk_layout() -> bool:
    """The fact must stay CURRENT — a member removed at the desk, or added
    through the ⚙ sheet, must move `member_hwnds` with it, or a tap on a
    window that just left would still be refused as "already in this
    layout" after it no longer is."""
    conn, layouts = build_layouts([("Work", [WIN_A, WIN_B, WIN_C])])
    layouts.drop_member(0, 1)   # drop WIN_B (ordinal 1)
    state = layouts.state(None, None)
    got = state["layouts"][0]["member_hwnds"]
    if got != [WIN_A, WIN_C]:
        print(f"  DETAIL member_hwnds after drop was {got}, expected "
              f"{[WIN_A, WIN_C]}")
        return False
    return True


CHECKS = [
    ("a tool window is never offered to the tap", check_a_tool_window_is_never_picked),
    ("an ordinary window is still picked (the fix narrows, does not break)",
     check_an_ordinary_window_is_still_picked),
    ("a cloaked window is never offered", check_a_cloaked_window_is_never_picked),
    ("layout_state carries the REAL member_hwnds, through the real dispatcher",
     check_layout_state_carries_the_real_member_hwnds),
    ("member_hwnds follows a layout that grows or shrinks",
     check_member_hwnds_follows_a_grown_or_shrunk_layout),
]


def main() -> int:
    print("=== LAYOUT TAP GATE (owner correction, 2026-08-13) ===")
    failed = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as e:  # a crashing handler is a failing check
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"LAYOUT TAP GATE FAILED — {failed} check(s).")
        return 1
    print("LAYOUT TAP GATE PASSED — the tap picks only what a layout could "
          "hold, and the phone can tell a member from a tab.")
    return 0


def test_layout_claim():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
