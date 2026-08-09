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
import pathlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import agents  # noqa: E402
import layout_api  # noqa: E402
import uia  # noqa: E402
import web  # noqa: E402
import window_manager  # noqa: E402

WIN_A, WIN_B, WIN_C = 0x10, 0x20, 0x30
MON = (0, 0, 3840, 2160)

# THE DESK THE CREATION LIST IS READ OFF (owner 2026-08-09, task 167). Three
# windows, chosen so that every branch of the tab rule is exercised by the
# SAME fixture: WIN_A holds three tabs (tabs are legitimately offered and can
# fill a grid of three), WIN_C holds exactly one (its lone tab must NOT be
# offered — a window and its only tab are one thing on screen), and WIN_B is
# not tab-capable at all. Until this fixture existed the whole file faked one
# VS Code with ONE tab and asserted three entries — a check that REQUIRED the
# bug, and that turned red the moment his rule was enforced.
FAKE_TABS: dict[int, list[str]] = {
    WIN_A: ["prompt.txt", "layout_api.py", "CLAUDE.md"],
    WIN_C: ["Inbox"],
}


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
    """Three open windows: a tab-capable one holding THREE tabs, a plain one,
    and a tab-capable one holding exactly ONE (see FAKE_TABS)."""
    return [
        {"hwnd": WIN_A, "title": "Remote User - Visual Studio Code",
         "process": "code.exe", "icon": None},
        {"hwnd": WIN_B, "title": "Downloads", "process": "explorer.exe",
         "icon": None},
        {"hwnd": WIN_C, "title": "Mail - Google Chrome",
         "process": "chrome.exe", "icon": None},
    ]


PLACED: list[tuple[int, tuple[int, int, int, int]]] = []
FRAME: dict[int, tuple[int, int, int, int]] = {}


def install_fakes(track_placement: bool = False) -> None:
    """`track_placement` swaps the do-nothing `place_window` for a MODEL of the
    desk: every commanded rect is recorded AND becomes the window's real frame,
    so `_frame_rect` afterwards answers where the window actually stands. That
    is what lets a check assert on the RECT instead of on a stored number —
    see `check_the_move_handle_reaches_the_windows`."""
    fake = FakeWin32([WIN_A, WIN_B, WIN_C])
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
    uia.has_tabs = lambda process: process in ("code.exe", "chrome.exe")
    # `list_tabs` is the RAW read and is faked; `uia.offerable_tabs` — the rule
    # under test (a lone tab is never offered, a minimized window is never
    # asked) — runs for real on top of it.
    uia.list_tabs = lambda rect, hwnd: [
        {"name": name, "x": 0.1 + 0.1 * i, "y": 0.02}
        for i, name in enumerate(FAKE_TABS.get(hwnd, []))]
    uia.is_minimized = lambda hwnd: False
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
def list_entries():
    """One `layout_list` through the real dispatcher → its entries."""
    ws, _, _ = drive([{"type": "layout_list"}])
    offers = sent_of(ws, "layout_offer")
    return offers[0]["entries"] if len(offers) == 1 else None


def check_create_from_a_list_answers() -> bool:
    """THE bug: `layout_list` raised UnboundLocalError, so the phone's cube
    spun forever. The list must come back, with the windows AND the tabs of
    the tab-capable ones."""
    install_fakes()
    entries = list_entries()
    if entries is None:
        return False
    kinds = [e["kind"] for e in entries]
    return "window" in kinds and "tab" in kinds


def check_a_lone_tab_is_not_offered_beside_its_own_window() -> bool:
    """HIS RULE (owner 2026-08-09, task 167): a tab can be pulled out into its
    own window only when the window has MORE THAN ONE tab. A window holding a
    single tab and that tab are the same picture on screen, so offering both
    counted one window twice — his VS Code with three tabs was offered as FOUR
    members, and the panel then let him build a grid of four out of three.

    THE CHECK THAT STOOD HERE REQUIRED THE DEFECT, which is the finding worth
    more than the fix: it faked ONE VS Code window with exactly ONE tab and
    asserted `len(entries) == 3` — window, its lone tab, and the plain window.
    Enforcing his rule turned it red. A gate written around a fixture that
    cannot tell the two behaviours apart proves whichever one it was written
    against, so the fixture is the fix: three tabs on one window, one tab on
    another, and both answers asserted in the same run."""
    install_fakes()
    entries = list_entries()
    if entries is None:
        print("  DETAIL the list never answered")
        return False
    ok = True
    windows = [e["hwnd"] for e in entries if e["kind"] == "window"]
    if sorted(windows) != sorted([WIN_A, WIN_B, WIN_C]):
        print(f"  DETAIL the windows offered were {windows}, expected all three")
        ok = False
    tabs = [(e["hwnd"], e["title"]) for e in entries if e["kind"] == "tab"]
    if [h for h, _ in tabs] != [WIN_A] * 3:
        print(f"  DETAIL the tabs offered were {tabs}, expected WIN_A's three")
        ok = False
    if any(h == WIN_C for h, _ in tabs):
        print("  DETAIL the ONE-tab window's lone tab was offered — the "
              "defect: it is the window, counted a second time")
        ok = False
    # …and the emission order is window-then-ITS-tabs, which is the whole
    # basis of the phone's indented list (owner 2026-08-09, task 168): the
    # panel indents a tab under the row above it and never re-groups.
    order = [(e["kind"], e["hwnd"]) for e in entries]
    if order != [("window", WIN_A), ("tab", WIN_A), ("tab", WIN_A),
                 ("tab", WIN_A), ("window", WIN_B), ("window", WIN_C)]:
        print(f"  DETAIL the emission order was {order} — the phone indents "
              "by it")
        ok = False
    return ok


def check_a_minimized_window_says_so_instead_of_hiding_its_tabs() -> bool:
    """MEASURED on the owner's own PC, 2026-08-09: a minimized window
    enumerates ZERO tabs — Win32 reports the classic (-32000, -32000) rect and
    UIA reports a bounding height of 0, so `uia._real_tabs` returns []. The
    creation list therefore offered the SAME window without its tabs from the
    taskbar and with them once restored, with nothing on screen to explain the
    difference: a list that silently depends on window state.

    The honest behaviour, and the one implemented: a minimized window is not
    asked at all, and its entry carries `tabs_hidden` so the phone can say
    why. Restoring it brings the tabs back — proven in the same check, because
    a flag nobody ever clears would be a second way to be wrong."""
    install_fakes()
    uia.is_minimized = lambda hwnd: hwnd == WIN_A
    entries = list_entries()
    if entries is None:
        return False
    ok = True
    if any(e["kind"] == "tab" for e in entries):
        print("  DETAIL a minimized window still offered tabs")
        ok = False
    by_hwnd = {e["hwnd"]: e for e in entries if e["kind"] == "window"}
    if not by_hwnd[WIN_A].get("tabs_hidden"):
        print("  DETAIL the minimized window did not say WHY it shows no tabs")
        ok = False
    for hwnd in (WIN_B, WIN_C):
        if by_hwnd[hwnd].get("tabs_hidden"):
            print(f"  DETAIL {hwnd:#x} claims hidden tabs while it is not "
                  "minimized")
            ok = False
    # Restored: the three tabs are back and nothing still claims otherwise.
    uia.is_minimized = lambda hwnd: False
    entries = list_entries()
    if len([e for e in entries if e["kind"] == "tab"]) != 3:
        print("  DETAIL restoring the window did not bring its tabs back")
        ok = False
    if any(e.get("tabs_hidden") for e in entries):
        print("  DETAIL `tabs_hidden` outlived the minimize that caused it")
        ok = False
    return ok


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


# ═══════════ a grid is built from the windows that ARRIVED ═══════════
# Owner report 2026-08-09, task 166: the panel offered a grid of FOUR while
# the desktop held three, and the server built it without a word. Every link
# in that chain behaved: `create` truncates its members to the template's
# cells, `zip` stops at the shorter side, `placed` stays True because every
# window it did place landed, and the region is the union of the cells — so a
# 2x2 filled by three windows frames four quadrants and streams bare desktop
# in the fourth. What was missing is anyone DECIDING that a four cannot be
# built out of three, and saying so to the phone.


def create_run(grid: str | None, hwnds: list[int], mode: str = "grid",
               track: bool = False):
    """One `layout_create` of `hwnds` asking for `grid`. Returns (ws, layouts)."""
    install_fakes(track_placement=track)
    ws, conn, layouts = drive([
        {"type": "layout_create", "mode": mode, "grid": grid,
         "orient": "landscape", "name": "Work",
         "slots": [{"hwnd": h, "tab": None, "x": 0.5, "y": 0.5}
                   for h in hwnds]}])
    return ws, layouts


def check_a_grid_is_built_from_the_windows_that_arrived() -> bool:
    """A four asked for with three windows becomes a THREE — and the phone is
    TOLD, because a layout that silently came out a different shape is exactly
    what he reported. The shape is not decided here either: this path asks
    `LayoutRegistry._template_for`, the same function `merge` and
    `drop_member` ask, so the three ways a layout's size can change cannot
    disagree about what a three is."""
    ok = True
    for grid, hwnds, want_cells in (
        ("4", [WIN_A, WIN_B, WIN_C], 3),   # the reported case
        ("4", [WIN_A, WIN_B], 2),
        ("3-left", [WIN_A, WIN_B], 2),
        ("2", [WIN_A], 1),                 # one window: not a grid at all
    ):
        ws, layouts = create_run(grid, hwnds)
        if len(layouts.layouts) != 1:
            print(f"  DETAIL {grid} from {len(hwnds)}: no layout was made")
            ok = False
            continue
        lay = layouts.layouts[0]
        cells = window_manager.GRID_CELLS.get(lay.template or "", 1)
        if cells != want_cells or len(lay.members) != want_cells:
            print(f"  DETAIL {grid} from {len(hwnds)} windows became "
                  f"{lay.template!r} with {len(lay.members)} member(s), "
                  f"expected a {want_cells}")
            ok = False
        if not sent_of(ws, "toast"):
            print(f"  DETAIL {grid} from {len(hwnds)} windows was downgraded "
                  "in SILENCE — the phone was told nothing")
            ok = False
    # …and a grid that DOES fit is left alone, toast and all: a notice on
    # every create would be noise, and noise is how a real one gets ignored.
    ws, layouts = create_run("3-left", [WIN_A, WIN_B, WIN_C])
    if layouts.layouts[0].template != "3-left":
        print(f"  DETAIL a fitting grid was changed to "
              f"{layouts.layouts[0].template!r}")
        ok = False
    if sent_of(ws, "toast"):
        print(f"  DETAIL a grid that fitted still toasted: {sent_of(ws, 'toast')}")
        ok = False
    return ok


def check_the_framed_region_has_no_empty_cell() -> bool:
    """THE GEOMETRY HE JUDGES, not the number we stored. The phone frames the
    UNION of the member rects, so under the old behaviour three windows in a
    2x2 covered three quarters of the picture and the fourth quadrant streamed
    his bare desktop — while the union rect, the member list and `placed` all
    looked perfectly correct. Coverage is what tells the two apart: the placed
    cells must fill the region they are framed in."""
    ok = True
    for grid, hwnds in (("4", [WIN_A, WIN_B, WIN_C]), ("4", [WIN_A, WIN_B]),
                        ("3-top", [WIN_A, WIN_B, WIN_C])):
        create_run(grid, hwnds, track=True)
        rects = [r for _, r in PLACED]
        if len(rects) != len(hwnds):
            print(f"  DETAIL {grid} from {len(hwnds)}: placed {len(rects)} "
                  f"window(s) of {len(hwnds)} — one was dropped")
            ok = False
            continue
        frame = union(rects)
        covered = sum(w * h for _, _, w, h in rects)
        framed = frame[2] * frame[3]
        if covered < framed * 0.99:
            print(f"  DETAIL {grid} from {len(hwnds)} windows covers "
                  f"{covered * 100 // framed}% of the region it frames — the "
                  "rest is bare desktop on his phone")
            ok = False
    return ok


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


# ═══════════════ the Move handle: the WINDOWS stay centred ═══════════════
# Owner decree 2026-08-09, the FOURTH round of the same feature. Round two
# (2026-08-07) taught this file to follow the handle to the WINDOWS — and that
# was still the wrong screen: the server crops the layout's region and streams
# the SAME picture wherever the windows sit inside the monitor, so three
# rounds of moving windows moved nothing he could see and his tablet stayed
# centred every time. The position that exists FOR HIM is where the
# letterboxed picture lands on the phone; `pos` acts THERE now
# (client/view-anchor.js, gated by tests/test_view_anchor.py) and the server
# ALWAYS centres the windows. What this file still owns is the server half of
# that contract: placement ignores `pos`, a pos-only Apply re-places nothing,
# and `layout_state` carries `pos` to the phone on every answer — the hop the
# picture is anchored by.

RATIO_W, RATIO_H = 10, 13     # the owner's own pair


def union(rects) -> tuple[int, int, int, int]:
    x = min(r[0] for r in rects)
    y = min(r[1] for r in rects)
    return (x, y, max(r[0] + r[2] for r in rects) - x,
            max(r[1] + r[3] for r in rects) - y)


def aspect_run(mode: str, orient: str, positions: list, drift: bool = False):
    """Create a layout, then apply `layout_aspect` at each position through the
    REAL dispatcher. Returns one (union rect or None, pos echoed by the last
    `layout_state`) pair per position — None = nothing was placed, which since
    2026-08-09 is the CORRECT outcome for a pos-only change. `drift` moves the
    window off its rect between positions — an app re-laying itself out, a
    restore out of the taskbar, a Windows snap: the desk the server must
    re-read."""
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
        states = sent_of(ws, "layout_state")
        echoed = (states[-1]["layouts"][0]["pos"]
                  if states and states[-1]["layouts"] else None)
        out.append((union([r for _, r in PLACED]) if PLACED else None, echoed))
    return out


def _centred_on_free_axis(rect, orient) -> tuple[bool, str]:
    """Is the union rect centred along the axis the ratio freed — with real
    slack, so a fixture where nothing could move cannot pass by accident?"""
    ml, mt, mw, mh = MON
    if orient == "portrait":
        near, size, span, origin = rect[1], rect[3], mh, mt
    else:
        near, size, span, origin = rect[0], rect[2], mw, ml
    slack = span - size
    detail = f"near={near} slack={slack} (origin {origin})"
    return slack >= 100 and abs(near - (origin + slack // 2)) <= 2, detail


def check_placement_is_centred_whatever_the_pos() -> bool:
    """The server half of the 2026-08-09 decree, read off the rect the server
    commands: a FRESH arrangement lands centred for pos 0, 500 and 1000 alike,
    at the same size — and each answer's `layout_state` still carries the pos
    the phone will anchor the picture by."""
    ok = True
    for mode in ("solo", "grid"):
        for orient in ("portrait", "landscape"):
            rects = []
            for pos, want in ((0, 0.0), (500, 0.5), (1000, 1.0)):
                (rect, echoed), = aspect_run(mode, orient, [pos])
                if rect is None:
                    print(f"  DETAIL {mode}/{orient}: pos={pos} placed NOTHING "
                          "on a fresh ratio change")
                    ok = False
                    continue
                if echoed is None or abs(echoed - want) > 1e-6:
                    print(f"  DETAIL {mode}/{orient}: pos={pos} echoed "
                          f"{echoed!r} to the phone, expected {want}")
                    ok = False
                rects.append(rect)
            if len(rects) == 3 and any(r != rects[0] for r in rects):
                print(f"  DETAIL {mode}/{orient}: placement FOLLOWED pos: {rects}")
                ok = False
            for rect in rects:
                centred, detail = _centred_on_free_axis(rect, orient)
                if not centred:
                    print(f"  DETAIL {mode}/{orient}: not centred — {detail}")
                    ok = False
    return ok


def check_a_pos_change_moves_the_phone_and_not_the_windows() -> bool:
    """The untangled trigger, both halves. Apply a ratio at pos 0, then the
    SAME ratio at pos 1000 with every window still standing: the second Apply
    must place NOTHING (a pos change re-places no PC window — three rounds
    proved moving them changes nothing he sees) while its `layout_state` must
    carry the new pos, because that answer is what re-anchors the picture on
    the phone. A second Apply that still moved windows, or a pos that never
    reached the phone, are both this feature broken."""
    ok = True
    for mode in ("solo", "grid"):
        (first, first_pos), (second, second_pos) = aspect_run(
            mode, "portrait", [0, 1000])
        if first is None:
            print(f"  DETAIL {mode}: the ratio change itself placed NOTHING")
            ok = False
        if second is not None:
            print(f"  DETAIL {mode}: a pos-only change re-placed windows: {second}")
            ok = False
        if second_pos is None or abs(second_pos - 1.0) > 1e-6:
            print(f"  DETAIL {mode}: the new pos never reached the phone "
                  f"(echoed {second_pos!r})")
            ok = False
    return ok


def check_a_wandered_window_is_put_back_centred() -> bool:
    """THE REPEAT of round three, still gated. The desk is re-read on every
    Apply: a member that left its rect (an app re-laying itself out, a restore
    out of the taskbar, a Windows snap) is put BACK — and back to the CENTRE,
    wherever the handle sits, because the centre is the only place the server
    puts windows now."""
    ok = True
    for mode in ("solo", "grid"):
        runs = aspect_run(mode, "portrait", [0, 500, 1000], drift=True)
        for i, (rect, _) in enumerate(runs):
            if rect is None:
                print(f"  DETAIL {mode}: apply #{i + 1} placed NOTHING after "
                      "the window wandered")
                ok = False
                continue
            centred, detail = _centred_on_free_axis(rect, "portrait")
            if not centred:
                print(f"  DETAIL {mode}: apply #{i + 1} not centred — {detail}")
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


# ═══════════════ a Store app's icon is in its PACKAGE ═══════════════
# Owner report 2026-08-08, with his screenshot of a generic glyph on a Photos
# layout. MEASURED before it was answered: SHGetFileInfoW on the packaged exe
# returns a 516-byte generic document icon (1,188 for Code.exe, 2,080 for
# chrome.exe), and the manifest names assets that DO NOT EXIST under the name
# it gives — 55 files on his PC, none of them `PhotosAppList.png`. So the
# choice among the siblings is the whole algorithm, and it is what these check.


def check_a_packaged_app_uses_its_manifest_icon() -> bool:
    """The stem in the manifest is not a file. The right sibling is."""
    import shutil
    import tempfile

    from PIL import Image

    import window_icons
    ok = True
    root = pathlib.Path(tempfile.mkdtemp())
    try:
        pkg = root / "WindowsApps" / "Contoso.Viewer_1.0_x64__abc"
        assets = pkg / "Assets"
        assets.mkdir(parents=True)
        (pkg / "AppxManifest.xml").write_text(
            '<Package><Applications><Application><uap:VisualElements '
            'Square44x44Logo="Assets\\Logo.png" /></Application>'
            '</Applications></Package>', encoding="utf-8")
        # Every scale EXCEPT the bare name, exactly as a real package ships,
        # plus the altform variants that must never be preferred.
        for name in ("Logo.scale-200.png", "Logo.scale-100.png",
                     "Logo.targetsize-32.png",
                     "Logo.targetsize-32_altform-unplated.png"):
            Image.new("RGBA", (44, 44), (10, 20, 30, 255)).save(assets / name)
        exe = pkg / "Viewer.exe"
        chosen = window_icons._appx_asset(str(exe))
        if chosen is None or chosen.name != "Logo.targetsize-32.png":
            print(f"  DETAIL picked {chosen and chosen.name!r}, "
                  f"expected 'Logo.targetsize-32.png'")
            ok = False
        uri = window_icons._packaged_icon(str(exe))
        if not (uri or "").startswith("data:image/png;base64,"):
            print("  DETAIL the packaged icon did not become a data URI")
            ok = False
        # A window that is NOT packaged must not pay for any of this, and must
        # never be answered from a manifest that does not exist.
        if window_icons._appx_asset(r"C:\Program Files\App\app.exe") is not None:
            print("  DETAIL an ordinary exe was treated as a package")
            ok = False
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return ok


def check_a_package_with_no_assets_falls_through() -> bool:
    """A manifest naming assets nobody shipped must return None, so the shell
    route still runs — a generic icon beats no layout."""
    import shutil
    import tempfile

    import window_icons
    root = pathlib.Path(tempfile.mkdtemp())
    try:
        pkg = root / "WindowsApps" / "Broken_1.0_x64__abc"
        (pkg / "Assets").mkdir(parents=True)
        (pkg / "AppxManifest.xml").write_text(
            '<Package Square44x44Logo="Assets\\Gone.png" />', encoding="utf-8")
        return (window_icons._appx_asset(str(pkg / "App.exe")) is None
                and window_icons._packaged_icon(str(pkg / "App.exe")) is None)
    finally:
        shutil.rmtree(root, ignore_errors=True)


CHECKS = [
    ("create from a LIST answers the phone", check_create_from_a_list_answers),
    ("a window's lone tab is NOT offered beside it",
     check_a_lone_tab_is_not_offered_beside_its_own_window),
    ("a minimized window SAYS why it shows no tabs",
     check_a_minimized_window_says_so_instead_of_hiding_its_tabs),
    ("a grid is built from the windows that ARRIVED, and a downgrade is said",
     check_a_grid_is_built_from_the_windows_that_arrived),
    ("the framed region is FULLY covered by its members",
     check_the_framed_region_has_no_empty_cell),
    ("the list probes the process table ONCE, not per entry",
     check_the_list_probes_the_process_table_once),
    ("create by TAPPING a window answers the phone", check_tap_a_window_answers),
    ("create → focus → desktop", check_create_focus_and_desktop),
    ("rename / aspect / remove all answer",
     check_rename_apps_aspect_remove_all_answer),
    ("a 2x1 grid built from the list", check_a_grid_from_the_list_answers),
    ("placement is CENTRED whatever the pos, and the pos reaches the phone",
     check_placement_is_centred_whatever_the_pos),
    ("a pos change moves the phone's picture, never the windows",
     check_a_pos_change_moves_the_phone_and_not_the_windows),
    ("a wandered window is put back — centred",
     check_a_wandered_window_is_put_back_centred),
    ("a plain ✕ closes NOTHING, whatever the field looks like",
     check_a_plain_remove_closes_nothing),
    ("close: true reaches every member", check_close_reaches_every_member),
    ("a window that refuses to close is REPORTED, not shrugged off",
     check_a_window_that_refuses_is_reported),
    ("members leave the topmost band BEFORE they are closed",
     check_the_members_leave_the_topmost_band_before_closing),
    ("a Store app's icon comes from its PACKAGE, not its exe",
     check_a_packaged_app_uses_its_manifest_icon),
    ("a package with no assets falls through to the shell route",
     check_a_package_with_no_assets_falls_through),
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
