"""Presence gate: the phone leaving work mode must free the owner's desk.

Regression proof for the 2026-08-05 live complaint ("kada sednem za desktop
ostane topmost na svima"). Layout members are always-on-top while the phone
shows them, and the server only ever learned they should stop from a CLEAN
socket close — which a locked phone rarely manages (its Wi-Fi sleeps and the
connection simply goes quiet). Nothing ever ended the session, so the windows
hovered over everything at the desk.

What is proven here, without Windows and without a browser (the registry's
window calls are stubbed):

1. Silence IS the leave — `hb` keeps the session, and the watchdog ends it
   (minimizing every layout member) once the beats stop.
2. An announced EXCURSION (image picker, camera, voice) is NOT a leave: the
   layout stands while the owner picks, guarded only by the long backstop.
3. An announced leave (`away` without `excursion`) frees the desk at once.
4. The resume pointer: coming back lands in the layout last used, a
   deliberate Desktop choice resumes on the desktop, and rename/remove keep
   the pointer honest.

Run:  .venv\\Scripts\\python tests/test_presence.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import presence  # noqa: E402
import web  # noqa: E402
import window_manager  # noqa: E402


class FakeWs:
    """Feeds queued client messages to `_receive_input`, records what the
    server sent back, and raises the real disconnect when the script ends."""

    def __init__(self, messages):
        self._messages = list(messages)
        self.sent: list = []
        self.closed_code = None

    async def receive_text(self) -> str:
        if not self._messages:
            raise web.WebSocketDisconnect(1000)
        return json.dumps(self._messages.pop(0))

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))

    async def close(self, code: int = 1000) -> None:
        self.closed_code = code


class FakeRegistry:
    """Only what the presence path touches."""

    def __init__(self):
        self.minimized = 0
        self.cleared = 0

    def minimize_members(self) -> None:
        self.minimized += 1

    def clear_topmost(self) -> None:
        self.cleared += 1


class FakeWin32:
    """window_manager talks to user32 directly; these tests run without a
    single real window, so the handful of calls the pruning/ledger paths make
    are answered here. `alive` is the set of hwnds that still exist."""

    def __init__(self, alive=()):
        self.alive = set(alive)
        self.dropped: list = []
        self.ex_style = 0   # what GetWindowLongW reports back after a drop

    def IsWindow(self, hwnd):            # noqa: N802 — mirrors the Win32 name
        return 1 if hwnd in self.alive else 0

    def SetWindowPos(self, hwnd, after, *_args):  # noqa: N802
        self.dropped.append(hwnd)
        return 1

    def GetWindowLongW(self, hwnd, index):        # noqa: N802
        return self.ex_style

    def __getattr__(self, name):
        return lambda *a, **k: 0   # ShowWindow, IsIconic, DwmSet… — all no-ops


def with_win32(alive=()):
    """Install the fake and hand it back; every check that touches windows
    uses this so the result never depends on the machine it runs on."""
    fake = FakeWin32(alive)
    window_manager.user32 = fake
    window_manager.dwmapi = fake
    window_manager._topmost.clear()
    window_manager._ledger_save = lambda: None   # no disk in a unit test
    return fake


def no_local_input() -> None:
    """The desk rule reads Windows' real last-input clock, which moves while
    these tests run on a machine somebody is using. Pin it."""
    presence.last_input_tick = lambda: 0


def fresh_conn() -> dict:
    return {"ratio": 9 / 16, "active": 0, "region": {"x": 0, "y": 0, "w": 1, "h": 1},
            "quality": None, "seen": 0.0, "away": None, "left": False}


async def drive(messages, conn, layouts):
    ws = FakeWs(messages)
    try:
        await web._receive_input(ws, injector=None, stream=None, token="t",
                                 layouts=layouts, conn=conn)
    except web.WebSocketDisconnect:
        pass
    return ws


def check_heartbeat_holds_the_session() -> bool:
    """A beating phone is a present phone — nothing is packed away."""
    conn, layouts = fresh_conn(), FakeRegistry()
    asyncio.run(drive([{"type": "hb"}, {"type": "hb"}], conn, layouts))
    return layouts.minimized == 0 and conn["away"] is None and conn["seen"] > 0


def check_silence_ends_the_session() -> bool:
    """The watchdog is the whole point: no beats for HEARTBEAT_TIMEOUT_S and
    the desk gets its windows back, socket alive or not."""
    conn, layouts = fresh_conn(), FakeRegistry()
    conn["seen"] = time.monotonic() - presence.HEARTBEAT_TIMEOUT_S * 2  # long silent

    async def run():
        ws = FakeWs([])
        # One poll is enough — the timeout is already exceeded.
        await asyncio.wait_for(presence.watchdog(ws, layouts, conn),
                               timeout=presence.WATCHDOG_POLL_S * 3)
        return ws

    ws = asyncio.run(run())
    return (layouts.minimized == 1 and conn["left"] is True
            and conn["active"] is None and ws.closed_code == 4408)


def check_excursion_is_not_a_leave() -> bool:
    no_local_input()
    """Picking an image hides the page for as long as it takes — the layout
    must still be standing when the owner comes back (owner 2026-08-05)."""
    conn, layouts = fresh_conn(), FakeRegistry()
    asyncio.run(drive([{"type": "away", "reason": "excursion"}], conn, layouts))
    if layouts.minimized != 0 or conn["away"] is not True:
        return False
    # ...and the watchdog is patient for it: the same silence that would end a
    # normal session must NOT end this one.
    conn["seen"] = time.monotonic() - presence.HEARTBEAT_TIMEOUT_S * 2

    async def run():
        try:
            await asyncio.wait_for(
                presence.watchdog(FakeWs([]), layouts, conn),
                timeout=presence.WATCHDOG_POLL_S * 2)
        except asyncio.TimeoutError:
            pass  # still watching — exactly right

    asyncio.run(run())
    return layouts.minimized == 0


def check_announced_leave_frees_the_desk() -> bool:
    """Lock / app closed: the client says so and the PC acts immediately."""
    conn, layouts = fresh_conn(), FakeRegistry()
    asyncio.run(drive([{"type": "away", "reason": ""}], conn, layouts))
    return layouts.minimized == 1 and conn["left"] is True


def check_leave_is_idempotent() -> bool:
    """The watchdog and the socket teardown both call it — once is once."""
    conn, layouts = fresh_conn(), FakeRegistry()
    asyncio.run(presence.leave_session(layouts, conn))
    asyncio.run(presence.leave_session(layouts, conn))
    return layouts.minimized == 1


def _registry_with(names) -> window_manager.LayoutRegistry:
    reg = window_manager.LayoutRegistry()
    for i, name in enumerate(names):
        reg.layouts.append(window_manager.Layout(
            name, "app.exe", [1000 + i], None, "portrait", 0.5))
    return reg


def check_resume_pointer() -> bool:
    """Coming back lands where the owner left off — and never on the wrong
    window when the list changed while the phone was away."""
    with_win32(alive=(1000, 1001))
    window_manager.is_alive = lambda hwnd: True  # no real windows in this test
    reg = _registry_with(["Editor", "Browser"])
    reg.last_focus = (1, "Browser")
    if reg.resume_index() != 1:
        return False
    # A deliberate Desktop choice resumes on the desktop.
    reg.forget_focus()
    if reg.resume_index() is not None:
        return False
    # Renaming keeps the pointer valid (name is half of its identity).
    reg.last_focus = (1, "Browser")
    reg.rename(1, "Reading")
    if reg.layouts[1].name != "Reading" or reg.resume_index() != 1:
        return False
    # Removing a layout below it shifts the pointer down with the list.
    reg.remove(0)
    if reg.resume_index() != 0 or reg.layouts[0].name != "Reading":
        return False
    # Removing the remembered layout leaves nothing to come back to.
    reg.remove(0)
    if reg.resume_index() is not None:
        return False
    # A name that no longer matches is a changed list — desktop, not a guess.
    with_win32(alive=(1000,))
    reg = _registry_with(["Editor"])
    reg.last_focus = (0, "Browser")
    return reg.resume_index() is None


def check_rename_rejects_empty() -> bool:
    """An empty name would leave a nameless row in the layout bar."""
    with_win32(alive=(1000,))
    window_manager.is_alive = lambda hwnd: True
    reg = _registry_with(["Editor"])
    return (not reg.rename(0, "   ") and not reg.rename(5, "Nope")
            and reg.rename(0, " Notes ") and reg.layouts[0].name == "Notes")


# ── Round 6 (owner report 2026-08-05, the SECOND time): "napravio sam GRID,
# zaključao tablet, došao na desktop — Chrome i VSCode su opet TOPMOST".
# The live server log dated the cause to the second: an excursion announced at
# 18:41:56 released at 18:46:56, exactly EXCURSION_MAX_S=300 s later, because
# LOCKING the tablet within 90 s of a Mic tap was reported as an excursion.
# Everything below is that failure, nailed down.

def check_lock_is_never_an_excursion() -> bool:
    """The reason the phone gives decides, and a lock is ALWAYS a leave — even
    when a legacy `excursion: true` rides along in the same message (an older
    page inside a newer server: the phone updates from the PC, so the two
    versions really do meet)."""
    if presence.is_excursion({"reason": "lock", "excursion": True}):
        return False
    if presence.is_excursion({"reason": ""}):
        return False
    if not presence.is_excursion({"reason": "excursion"}):
        return False
    if not presence.is_excursion({"excursion": True}):   # pre-reason page
        return False
    no_local_input()
    conn, layouts = fresh_conn(), FakeRegistry()
    asyncio.run(drive([{"type": "away", "reason": "lock", "excursion": True}],
                      conn, layouts))
    # Minimized AND out of the topmost band, at once — not in five minutes.
    return (layouts.minimized == 1 and layouts.cleared == 1
            and conn["left"] is True and conn["away"] is None)


def check_the_desk_wins() -> bool:
    """Whatever the phone claimed on its way out, the owner sitting down at
    this PC ends the hold immediately (owner decree 2026-08-05)."""
    conn, layouts = fresh_conn(), FakeRegistry()
    conn["away"] = True
    conn["seen"] = time.monotonic()          # not silent — only the desk acts
    presence.last_input_tick = lambda: 2 ** 31   # a hand on the keyboard, now

    async def run():
        ws = FakeWs([])
        await asyncio.wait_for(presence.watchdog(ws, layouts, conn),
                               timeout=presence.WATCHDOG_POLL_S * 3)
        return ws

    ws = asyncio.run(run())
    no_local_input()
    return layouts.minimized == 1 and conn["left"] is True and ws.closed_code == 4408


def check_a_leave_releases_the_topmost_band() -> bool:
    """Minimizing the members is not enough: a window that fell out of its
    layout (closed, cloaked, extracted as a tab) is exactly the one no member
    list can still name — the ledger is what covers it."""
    conn, layouts = fresh_conn(), FakeRegistry()
    asyncio.run(presence.leave_session(layouts, conn))
    return layouts.minimized == 1 and layouts.cleared == 1


def check_the_ledger_releases_everything() -> bool:
    """Every window we raise is written down, and release_all empties the
    book — this is what runs on tray Quit, on stop, on atexit."""
    fake = with_win32(alive=(4001, 4002))
    window_manager.mark_topmost(4001)
    window_manager.mark_topmost(4002)
    if len(window_manager._topmost) != 2:
        return False
    window_manager.release_all()
    return (not window_manager._topmost
            and set(fake.dropped) == {4001, 4002})


def check_a_refused_drop_stays_in_the_book() -> bool:
    """SetWindowPos can be refused (a window at a higher integrity level).
    Forgetting such a window because we asked once is how "solved" becomes
    "still topmost" — it must survive for the next start's repair."""
    fake = with_win32(alive=(4003,))
    fake.ex_style = window_manager.WS_EX_TOPMOST   # it stayed up there
    window_manager.mark_topmost(4003)
    dropped = window_manager.drop_topmost(4003)
    return dropped is False and 4003 in window_manager._topmost


def check_prune_keeps_hidden_windows_and_frees_dead_ones() -> bool:
    """A window on ANOTHER VIRTUAL DESKTOP is cloaked, not closed. Pruning it
    deleted the owner's layout and abandoned its members — still on screen,
    still always-on-top — in a list nothing could reach (audit 2026-08-05)."""
    fake = with_win32(alive=(5001,))
    window_manager.is_alive = lambda hwnd: False   # everything looks "cloaked"
    reg = window_manager.LayoutRegistry()
    reg.layouts.append(window_manager.Layout("Kept", "app.exe", [5001], None,
                                             "portrait", 0.5))
    reg.layouts.append(window_manager.Layout("Gone", "app.exe", [5002], None,
                                             "portrait", 0.5))
    window_manager.mark_topmost(5001)
    window_manager.mark_topmost(5002)
    kept = reg.prune()
    return (kept == [0] and len(reg.layouts) == 1
            and reg.layouts[0].name == "Kept"
            # The dead one is off the books (a window that no longer exists
            # needs no SetWindowPos — it needs to stop being owed one)...
            and 5002 not in window_manager._topmost
            # ...and the merely hidden one keeps BOTH its layout membership
            # and its ledger entry, so it is still released later.
            and 5001 in window_manager._topmost
            and 5001 not in fake.dropped)


def check_focus_follows_its_layout_through_a_prune() -> bool:
    """Closing a window at the desk used to slide the list down under the
    focus, so the phone was suddenly focused on — and one ✕ away from
    removing — a layout it never chose."""
    with_win32(alive=(6002, 6003))
    reg = window_manager.LayoutRegistry()
    for name, hwnd in (("A", 6001), ("B", 6002), ("C", 6003)):
        reg.layouts.append(window_manager.Layout(name, "app.exe", [hwnd], None,
                                                 "portrait", 0.5))
    state = reg.state(1, {"x": 0, "y": 0, "w": 1, "h": 1})   # focused on B
    return (state["active"] == 0
            and state["layouts"][0]["name"] == "B"
            and state["region"] is not None)


CHECKS = [
    ("heartbeat holds the session", check_heartbeat_holds_the_session),
    ("silence ends it — members minimized, socket closed 4408",
     check_silence_ends_the_session),
    ("an excursion is not a leave", check_excursion_is_not_a_leave),
    ("an announced leave frees the desk at once",
     check_announced_leave_frees_the_desk),
    ("leaving twice minimizes once", check_leave_is_idempotent),
    ("resume pointer survives rename/remove, forgets on Desktop",
     check_resume_pointer),
    ("rename rejects an empty or missing layout", check_rename_rejects_empty),
    ("a LOCK is never an excursion — released at once, not in 5 minutes",
     check_lock_is_never_an_excursion),
    ("the owner's own keyboard at this PC ends the hold", check_the_desk_wins),
    ("a leave releases the topmost band, not just the members",
     check_a_leave_releases_the_topmost_band),
    ("the ledger releases every window we ever raised",
     check_the_ledger_releases_everything),
    ("a REFUSED drop stays in the book for the next repair",
     check_a_refused_drop_stays_in_the_book),
    ("prune keeps hidden windows and frees dead ones",
     check_prune_keeps_hidden_windows_and_frees_dead_ones),
    ("the focus follows its layout through a prune",
     check_focus_follows_its_layout_through_a_prune),
]


def main() -> int:
    print("=== PRESENCE GATE ===")
    failed = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as e:  # a crashing check is a failing check
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"PRESENCE GATE FAILED — {failed} check(s).")
        return 1
    print("PRESENCE GATE PASSED — the phone leaving work mode frees the desk.")
    return 0


def test_presence():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
