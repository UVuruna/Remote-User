"""Layout gate: EVERY layout message the phone can send must answer it.

Regression proof for the 2026-08-06 live failure — "layout, kreiraj iz liste,
ništa se ne dešava": the loading cube spun and no list ever came. The cause was
one line in `layout_api.layout_list`:

    mon_rect = mon_rect(stream)

`mon_rect` is this module's own function, so assigning to that name made it a
LOCAL for the whole function and the call on the right-hand side raised
UnboundLocalError before anything was sent. The socket died, the phone
reconnected, and the owner saw a spinner forever. His server log carried the
traceback three times; nothing in the build did, because NO TEST WALKED THIS
PATH. Four guard tests, an input gate, a presence gate, a notify gate and a
focus gate, and the phone's whole layout protocol had none — that is the real
finding, and this file is it.

Every message is driven through the REAL `web._receive_input` dispatcher and
the REAL `layout_api` + `LayoutRegistry`; only Windows itself is faked (user32,
the window list, UIA, the process table). A handler that raises, or that
answers the phone with nothing, fails here.

Run:  .venv\\Scripts\\python tests/test_layout_protocol.py
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import agents  # noqa: E402
import layout_api  # noqa: E402
import uia  # noqa: E402
import web  # noqa: E402
import window_manager  # noqa: E402

WIN_A, WIN_B = 0x10, 0x20
MON = (0, 0, 3840, 2160)


class FakeWs:
    def __init__(self, messages):
        self._messages = list(messages)
        self.sent: list = []

    async def receive_text(self) -> str:
        if not self._messages:
            raise web.WebSocketDisconnect(1000)
        return json.dumps(self._messages.pop(0))

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def close(self, code: int = 1000) -> None:
        pass


class FakeStream:
    mode = "h264"
    width, height, monitor_index = 3840, 2160, 0


class FakeWin32:
    """Only what the layout path asks of user32/dwmapi."""

    def __init__(self, alive):
        self.alive = set(alive)

    def IsWindow(self, hwnd):             # noqa: N802
        return 1 if hwnd in self.alive else 0

    def IsWindowVisible(self, hwnd):      # noqa: N802
        return 1 if hwnd in self.alive else 0

    def GetForegroundWindow(self):        # noqa: N802
        return WIN_A

    def __getattr__(self, name):
        return lambda *a, **k: 0


def fake_windows():
    """Two open windows, one of them tab-capable."""
    return [
        {"hwnd": WIN_A, "title": "Remote User - Visual Studio Code",
         "process": "code.exe", "icon": None},
        {"hwnd": WIN_B, "title": "Downloads", "process": "explorer.exe",
         "icon": None},
    ]


PLACED: list[tuple[int, tuple[int, int, int, int]]] = []
FRAME: dict[int, tuple[int, int, int, int]] = {}


def install_fakes(track_placement: bool = False) -> None:
    """`track_placement` swaps the do-nothing `place_window` for a MODEL of the
    desk: every commanded rect is recorded AND becomes the window's real frame,
    so `_frame_rect` afterwards answers where the window actually stands. That
    is what lets a check assert on the RECT instead of on a stored number —
    see `check_the_move_handle_reaches_the_windows`."""
    fake = FakeWin32([WIN_A, WIN_B])
    window_manager.user32 = fake
    window_manager.dwmapi = fake
    window_manager._topmost.clear()
    window_manager._ledger_save = lambda: None
    window_manager.is_alive = lambda hwnd: True
    window_manager.list_windows = lambda exclude=None: [
        w for w in fake_windows() if not exclude or w["hwnd"] not in exclude]
    window_manager.window_at = lambda rect, x, y: dict(fake_windows()[0])
    window_manager.place_window = lambda hwnd, rect: True
    window_manager.raise_window = lambda hwnd, topmost=True: None
    window_manager.drop_topmost = lambda hwnd: True
    window_manager.freeze_transitions = lambda hwnd, disabled=True: None
    window_manager.wait_minimized = lambda hwnds, timeout_s=0: None
    window_manager._frame_rect = lambda hwnd: (0, 0, 1000, 1000)
    if track_placement:
        PLACED.clear()
        FRAME.clear()

        def place(hwnd, rect):
            PLACED.append((hwnd, tuple(rect)))
            FRAME[hwnd] = tuple(rect)
            return True

        window_manager.place_window = place
        window_manager._frame_rect = lambda hwnd: FRAME.get(hwnd, (0, 0, 1000, 1000))
    window_manager._title = lambda hwnd: "Remote User - Visual Studio Code"
    window_manager._process_name = lambda hwnd: "code.exe"
    window_manager._process_path = lambda hwnd: "C:/code.exe"
    window_manager.icon_data_uri = lambda path: None
    layout_api.rect_for_size = lambda w, h, i: MON
    uia.has_tabs = lambda process: process == "code.exe"
    uia.list_tabs = lambda rect, hwnd: [{"name": "prompt.txt", "x": 0.1, "y": 0.02}]
    uia.tab_at = lambda rect, x, y: None
    # The snapshot argument is the fix of 2026-08-07: the real function is a
    # 1.85 s PowerShell probe, and the handlers used to reach it once per
    # entry, bare, on the event loop. `live` is what they pass now.
    agents.agents_for = lambda title, live=None: ["claude"] if "Remote User" in title else []
    agents.live_agents = lambda: {"claude": {"remote user"}}


def fresh_conn() -> dict:
    return {"ratio": 9 / 16, "active": None, "region": None, "quality": None,
            "seen": 0.0, "away": None, "left": False,
            "pin": None, "pin_stale": True}


def drive(messages, conn=None, layouts=None):
    """Run the messages through the real dispatcher; return (ws, conn, layouts).
    An exception inside a handler is NOT swallowed — that is the point."""
    conn = conn if conn is not None else fresh_conn()
    layouts = layouts if layouts is not None else window_manager.LayoutRegistry()
    ws = FakeWs(messages)

    async def run():
        try:
            await web._receive_input(ws, injector=None, stream=FakeStream(),
                                     token="t", layouts=layouts, conn=conn)
        except web.WebSocketDisconnect:
            pass

    asyncio.run(run())
    return ws, conn, layouts


def sent_of(ws, kind):
    return [m for m in ws.sent if m.get("type") == kind]


# ═══════════════════ the failure that got here ═══════════════════
def check_create_from_a_list_answers() -> bool:
    """THE bug: `layout_list` raised UnboundLocalError, so the phone's cube
    spun forever. The list must come back, with the windows AND the tabs of
    the tab-capable ones."""
    install_fakes()
    ws, _, _ = drive([{"type": "layout_list"}])
    offers = sent_of(ws, "layout_offer")
    if len(offers) != 1:
        return False
    entries = offers[0]["entries"]
    kinds = [e["kind"] for e in entries]
    return ("window" in kinds and "tab" in kinds and len(entries) == 3
            and offers[0]["grids"])


def check_the_list_probes_the_process_table_once() -> bool:
    """The list may cost ONE process-table probe, never one per entry (owner
    2026-08-07: "treba mu jako dugo da učita").

    `agents.live_agents()` is a PowerShell subprocess — 1.85 s measured on the
    owner's own PC. `layout_list` used to call `agents_for()` bare, once per
    window and once per tab, from the coroutine itself: every lapse of the two
    second cache bought another 1.85 s with the WHOLE event loop stopped — no
    stream, no heartbeats, no answer — while a slow `uia.list_tabs` between
    two windows guaranteed the lapse. One snapshot, taken in a thread, is the
    fix; this counts it."""
    install_fakes()
    calls = []
    agents.live_agents = lambda: (calls.append(1), {"claude": {"remote user"}})[1]
    agents.agents_for = lambda title, live=None: (
        [] if live is None else ["claude"] if "Remote User" in title else [])
    ws, _, _ = drive([{"type": "layout_list"}])
    entries = sent_of(ws, "layout_offer")[0]["entries"]
    if len(calls) != 1:
        return False
    # …and every entry still carries a real answer, so "once" did not become
    # "not at all".
    return any(e["agents"] == ["claude"] for e in entries)


def check_tap_a_window_answers() -> bool:
    """The other creation source — one armed tap."""
    install_fakes()
    ws, _, _ = drive([{"type": "layout_pick", "x": 0.5, "y": 0.5}])
    offers = sent_of(ws, "layout_offer")
    return len(offers) == 1 and offers[0]["target"]["hwnd"] == WIN_A


# ═══════════════════ and the whole protocol behind it ═══════════════════
def check_create_focus_and_desktop() -> bool:
    """Create → the layout is focused and framed; Desktop → back out."""
    install_fakes()
    conn, layouts = fresh_conn(), window_manager.LayoutRegistry()
    ws, conn, layouts = drive([
        {"type": "layout_create", "mode": "solo", "orient": "portrait",
         "slots": [{"hwnd": WIN_A, "tab": None, "x": 0.5, "y": 0.5}],
         # `app_sets` is what an OLD client still sends (the ticks, removed
         # 2026-08-07). It must be accepted and ignored — a phone that has not
         # reloaded the page may not break creation.
         "name": "Work", "app_sets": ["claude"]},
    ], conn, layouts)
    states = sent_of(ws, "layout_state")
    if not states or len(layouts.layouts) != 1:
        return False
    if states[-1]["active"] != 0 or conn["active"] != 0:
        return False
    if layouts.layouts[0].name != "Work":
        return False
    if "app_sets" in states[-1]["layouts"][0]:
        return False  # nothing may carry a frozen copy of the app-set answer
    ws, conn, layouts = drive([{"type": "layout_focus", "index": -1}], conn, layouts)
    states = sent_of(ws, "layout_state")
    return bool(states) and states[-1]["active"] is None and conn["active"] is None


def check_rename_apps_aspect_remove_all_answer() -> bool:
    """Every later message about an existing layout answers with the state —
    a silent handler is how the phone ends up showing a stale list."""
    install_fakes()
    conn, layouts = fresh_conn(), window_manager.LayoutRegistry()
    ws, conn, layouts = drive([
        {"type": "layout_create", "mode": "solo", "orient": "portrait",
         "slots": [{"hwnd": WIN_A, "tab": None, "x": 0.5, "y": 0.5}]},
    ], conn, layouts)
    for msg, check in (
        ({"type": "layout_rename", "index": 0, "name": "Reading"},
         lambda: layouts.layouts[0].name == "Reading"),
        ({"type": "layout_aspect", "index": 0, "w": 4, "h": 3, "pos": 250},
         lambda: layouts.layouts[0].ratio == (4, 3)
         and abs(layouts.layouts[0].pos - 0.25) < 1e-6),
    ):
        ws, conn, layouts = drive([msg], conn, layouts)
        if not sent_of(ws, "layout_state") or not check():
            return False
    ws, conn, layouts = drive([{"type": "layout_remove", "index": 0}], conn, layouts)
    return bool(sent_of(ws, "layout_state")) and not layouts.layouts


def check_a_grid_from_the_list_answers() -> bool:
    """Two slots, the source the owner actually used when it broke."""
    install_fakes()
    ws, conn, layouts = drive([
        {"type": "layout_list"},
        {"type": "layout_create", "mode": "grid", "grid": "2x1",
         "orient": "landscape",
         "slots": [{"hwnd": WIN_A, "tab": None, "x": 0.25, "y": 0.5},
                   {"hwnd": WIN_B, "tab": None, "x": 0.75, "y": 0.5}]},
    ])
    progress = sent_of(ws, "layout_progress")
    return (len(sent_of(ws, "layout_offer")) == 1 and len(progress) == 2
            and len(layouts.layouts) == 1
            and layouts.layouts[0].members == [WIN_A, WIN_B])


# ═══════════════ the Move handle, followed to the WINDOWS ═══════════════
# Owner report 2026-08-07, the SECOND round of the same bug: he sets 10:13
# portrait, drags the Move handle to the TOP, presses Apply — and the window
# comes out vertically centred. "uvek ostavi centrirano."
#
# The round before it measured `_fit_rect(box, aspect, pos)` and `Layout.pos`,
# found both correct, and called the feature verified. Both WERE correct. The
# value died between them and the desk, and no check in this file could see it
# because the one that touched `layout_aspect` asserted on a stored NUMBER
# (`layouts[0].pos == 0.25`) while `place_window` was a fake that threw its
# rect away. So these checks assert on the RECT — where the window is told to
# stand — for a solo layout AND a grid, portrait AND landscape.

RATIO_W, RATIO_H = 10, 13     # the owner's own pair


def union(rects) -> tuple[int, int, int, int]:
    x = min(r[0] for r in rects)
    y = min(r[1] for r in rects)
    return (x, y, max(r[0] + r[2] for r in rects) - x,
            max(r[1] + r[3] for r in rects) - y)


def aspect_run(mode: str, orient: str, positions: list, drift: bool = False):
    """Create a layout, then apply `layout_aspect` at each position through the
    REAL dispatcher. Returns one union rect per position (None = nothing was
    placed). `drift` moves the window off its rect between positions — an app
    re-laying itself out, a restore, a snap: the desk the server must re-read."""
    install_fakes(track_placement=True)
    conn, layouts = fresh_conn(), window_manager.LayoutRegistry()
    slots = [{"hwnd": WIN_A, "tab": None, "x": 0.5, "y": 0.5}]
    if mode == "grid":
        slots.append({"hwnd": WIN_B, "tab": None, "x": 0.5, "y": 0.5})
    ws, conn, layouts = drive([
        {"type": "layout_create", "mode": mode, "grid": "2" if mode == "grid" else None,
         "orient": orient, "slots": slots, "name": "Work"}], conn, layouts)
    out = []
    for pos in positions:
        if drift:
            for hwnd in list(FRAME):
                x, y, w, h = FRAME[hwnd]
                FRAME[hwnd] = (x, y + 400, w, h)   # the window wandered
        PLACED.clear()
        ws, conn, layouts = drive([
            {"type": "layout_aspect", "index": 0,
             "w": RATIO_W, "h": RATIO_H, "pos": pos}], conn, layouts)
        out.append(union([r for _, r in PLACED]) if PLACED else None)
    return out


def check_the_move_handle_reaches_the_windows() -> bool:
    """0 = the free axis's near edge, 1000 = its far edge, 500 = centred — read
    off the rect the server commands, not off anything it stored."""
    ml, mt, mw, mh = MON
    ok = True
    for mode in ("solo", "grid"):
        for orient in ("portrait", "landscape"):
            top, mid, bottom = aspect_run(mode, orient, [0, 500, 1000])
            if not (top and mid and bottom):
                print(f"  DETAIL {mode}/{orient}: a position placed NOTHING")
                ok = False
                continue
            # Only the position may differ — the shape must not.
            if not (top[2] == mid[2] == bottom[2] and top[3] == mid[3] == bottom[3]):
                print(f"  DETAIL {mode}/{orient}: the region changed SIZE: "
                      f"{top} {mid} {bottom}")
                ok = False
            if orient == "portrait":
                near, far, size, span, origin = top[1], bottom[1], top[3], mh, mt
                centre = mid[1]
            else:
                near, far, size, span, origin = top[0], bottom[0], top[2], mw, ml
                centre = mid[0]
            slack = span - size
            good = (abs(near - origin) <= 2                     # pinned near
                    and abs(far - (origin + slack)) <= 2        # pinned far
                    and abs(centre - (origin + slack // 2)) <= 2)  # centred
            if not good or slack < 100:
                print(f"  DETAIL {mode}/{orient}: near={near} centre={centre} "
                      f"far={far} slack={slack} (origin {origin})")
                ok = False
    return ok


def check_the_same_position_applied_again_still_moves_the_windows() -> bool:
    """THE REPEAT, gated. `Layout.arranged_pos` records what was COMMANDED, so
    once a member left its rect (an app re-laying itself out, a restore out of
    the taskbar, a Windows snap) the guard matched on every later Apply of the
    SAME position and placed NOTHING — the phone's panel moved, the PC never
    did again, "uvek ostavi centrirano". The desk is re-read now."""
    ml, mt, mw, mh = MON
    ok = True
    for mode in ("solo", "grid"):
        runs = aspect_run(mode, "portrait", [0, 0, 0], drift=True)
        for i, rect in enumerate(runs):
            if rect is None:
                print(f"  DETAIL {mode}: apply #{i + 1} of pos=0 placed NOTHING")
                ok = False
            elif abs(rect[1] - mt) > 2:
                print(f"  DETAIL {mode}: apply #{i + 1} landed at y={rect[1]}, "
                      f"not on the top edge {mt}")
                ok = False
    return ok


# ═══════════════ the ✕ means two things, and only one is fatal ═══════════════
# Owner 2026-08-08, task 116: "brisanje layouta ga samo obrise iz nase liste
# ali ostavlja prozor na desktopu. Nekad hocemo to, a nekad hocemo bas da
# zatvorimo sve tu."
#
# The first check below is the one that matters. Everything else here proves a
# feature works; that one proves the feature CANNOT reach his windows unless
# he said so — and it is the only half of this that cannot be undone from the
# phone. It is written against the real `close_windows`, not a fake, because
# a fake would prove nothing about which branch the dispatcher takes.

CLOSED: list[int] = []


def install_close_model(refuses: set[int] | None = None) -> None:
    """A DESK where windows really close. `PostMessageW(WM_CLOSE)` marks the
    window dead unless it is one of `refuses` — an app with unsaved work that
    put up its own dialog and is waiting for the owner, which is a normal
    outcome and must reach the phone as words, not as a silent success."""
    refuses = refuses or set()
    CLOSED.clear()
    real = window_manager.user32

    class Desk:
        def PostMessageW(self, hwnd, msg, w, l):  # noqa: N802, E741
            if msg == window_manager.WM_CLOSE:
                CLOSED.append(hwnd)
                if hwnd not in refuses:
                    real.alive.discard(hwnd)
            return 1

        def __getattr__(self, name):
            return getattr(real, name)

    window_manager.user32 = Desk()
    window_manager.is_alive = lambda hwnd: hwnd in real.alive
    window_manager.CLOSE_TIMEOUT_S = 0.2   # the refusal path must not stall


def remove_run(message: dict, refuses: set[int] | None = None):
    """One 2x1 layout, then one `layout_remove`. Returns (ws, layouts)."""
    install_fakes()
    install_close_model(refuses)
    ws, conn, layouts = drive([
        {"type": "layout_create", "mode": "grid", "grid": "2x1",
         "orient": "landscape",
         "slots": [{"hwnd": WIN_A, "tab": None, "x": 0.25, "y": 0.5},
                   {"hwnd": WIN_B, "tab": None, "x": 0.75, "y": 0.5}]},
    ])
    ws, conn, layouts = drive([message], conn, layouts)
    return ws, layouts


def check_a_plain_remove_closes_nothing() -> bool:
    """THE SAFETY PROPERTY. The button that has always only removed the layout
    must still only remove the layout — including for a page from before this
    round, which sends no `close` field at all."""
    ok = True
    for label, msg in (
        ("no field at all", {"type": "layout_remove", "index": 0}),
        ("close: false", {"type": "layout_remove", "index": 0, "close": False}),
        # `is True`, not truthiness: a stray "0"/"no"/1 must not be a licence
        # to close his windows.
        ("close: 1 (truthy, not True)",
         {"type": "layout_remove", "index": 0, "close": 1}),
        ("close: 'yes' (a string)",
         {"type": "layout_remove", "index": 0, "close": "yes"}),
    ):
        ws, layouts = remove_run(msg)
        if CLOSED:
            print(f"  DETAIL {label}: WM_CLOSE went to {CLOSED} — his windows")
            ok = False
        if layouts.layouts:
            print(f"  DETAIL {label}: the layout survived the removal")
            ok = False
    return ok


def check_close_reaches_every_member() -> bool:
    """The new act: both windows of the grid are asked to close, and the phone
    is not told anything went wrong."""
    ws, layouts = remove_run({"type": "layout_remove", "index": 0, "close": True})
    if sorted(CLOSED) != sorted([WIN_A, WIN_B]):
        print(f"  DETAIL WM_CLOSE reached {CLOSED}, expected both members")
        return False
    if layouts.layouts:
        print("  DETAIL the layout survived a close")
        return False
    toasts = sent_of(ws, "toast")
    if toasts:
        print(f"  DETAIL a clean close still toasted: {toasts}")
        return False
    return bool(sent_of(ws, "layout_state"))


def check_a_window_that_refuses_is_reported() -> bool:
    """An app with unsaved work puts up its own dialog and stays. The layout
    is gone either way — he chose that — but the phone must SAY the window is
    still there, or the close silently half-happened."""
    ws, layouts = remove_run({"type": "layout_remove", "index": 0, "close": True},
                             refuses={WIN_B})
    if layouts.layouts:
        print("  DETAIL the layout survived a partly refused close")
        return False
    toasts = sent_of(ws, "toast")
    if not toasts:
        print("  DETAIL a window refused to close and the phone was told nothing")
        return False
    return "1 window" in toasts[0].get("text", "")


def check_the_members_leave_the_topmost_band_before_closing() -> bool:
    """A member is always-on-top while the phone shows it. Its save dialog is a
    SEPARATE window, so the parent must come down first — otherwise the thing
    asking him a question sits underneath the thing that asked it."""
    install_fakes()
    install_close_model(refuses={WIN_A, WIN_B})
    order: list[tuple[str, int]] = []
    window_manager.drop_topmost = lambda hwnd: order.append(("drop", hwnd)) or True
    real_post = window_manager.user32.PostMessageW
    win = window_manager.user32

    class Watch:
        def PostMessageW(self, hwnd, msg, w, l):  # noqa: N802, E741
            if msg == window_manager.WM_CLOSE:
                order.append(("close", hwnd))
            return real_post(hwnd, msg, w, l)

        def __getattr__(self, name):
            return getattr(win, name)

    window_manager.user32 = Watch()
    ws, conn, layouts = drive([
        {"type": "layout_create", "mode": "solo", "orient": "portrait",
         "slots": [{"hwnd": WIN_A, "tab": None, "x": 0.5, "y": 0.5}]},
    ])
    drive([{"type": "layout_remove", "index": 0, "close": True}], conn, layouts)
    steps = [k for k, h in order if h == WIN_A]
    if steps[:2] != ["drop", "close"]:
        print(f"  DETAIL the order was {steps}, expected drop then close")
        return False
    return True


CHECKS = [
    ("create from a LIST answers the phone", check_create_from_a_list_answers),
    ("the list probes the process table ONCE, not per entry",
     check_the_list_probes_the_process_table_once),
    ("create by TAPPING a window answers the phone", check_tap_a_window_answers),
    ("create → focus → desktop", check_create_focus_and_desktop),
    ("rename / aspect / remove all answer",
     check_rename_apps_aspect_remove_all_answer),
    ("a 2x1 grid built from the list", check_a_grid_from_the_list_answers),
    ("the Move handle reaches the WINDOWS (solo/grid, portrait/landscape)",
     check_the_move_handle_reaches_the_windows),
    ("the same position applied again still moves the windows",
     check_the_same_position_applied_again_still_moves_the_windows),
    ("a plain ✕ closes NOTHING, whatever the field looks like",
     check_a_plain_remove_closes_nothing),
    ("close: true reaches every member", check_close_reaches_every_member),
    ("a window that refuses to close is REPORTED, not shrugged off",
     check_a_window_that_refuses_is_reported),
    ("members leave the topmost band BEFORE they are closed",
     check_the_members_leave_the_topmost_band_before_closing),
]


def main() -> int:
    print("=== LAYOUT GATE ===")
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
        print(f"LAYOUT GATE FAILED — {failed} check(s).")
        return 1
    print("LAYOUT GATE PASSED — every layout message answers the phone.")
    return 0


def test_layout_protocol():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
