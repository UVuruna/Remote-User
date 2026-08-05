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

    def minimize_members(self) -> None:
        self.minimized += 1


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
    conn["seen"] = time.monotonic() - web.HEARTBEAT_TIMEOUT_S * 2  # long silent

    async def run():
        ws = FakeWs([])
        # One poll is enough — the timeout is already exceeded.
        await asyncio.wait_for(web._presence_watchdog(ws, layouts, conn),
                               timeout=web.WATCHDOG_POLL_S * 3)
        return ws

    ws = asyncio.run(run())
    return (layouts.minimized == 1 and conn["left"] is True
            and conn["active"] is None and ws.closed_code == 4408)


def check_excursion_is_not_a_leave() -> bool:
    """Picking an image hides the page for as long as it takes — the layout
    must still be standing when the owner comes back (owner 2026-08-05)."""
    conn, layouts = fresh_conn(), FakeRegistry()
    asyncio.run(drive([{"type": "away", "excursion": True}], conn, layouts))
    if layouts.minimized != 0 or conn["away"] is not True:
        return False
    # ...and the watchdog is patient for it: the same silence that would end a
    # normal session must NOT end this one.
    conn["seen"] = time.monotonic() - web.HEARTBEAT_TIMEOUT_S * 2

    async def run():
        try:
            await asyncio.wait_for(
                web._presence_watchdog(FakeWs([]), layouts, conn),
                timeout=web.WATCHDOG_POLL_S * 2)
        except asyncio.TimeoutError:
            pass  # still watching — exactly right

    asyncio.run(run())
    return layouts.minimized == 0


def check_announced_leave_frees_the_desk() -> bool:
    """Lock / app closed: the client says so and the PC acts immediately."""
    conn, layouts = fresh_conn(), FakeRegistry()
    asyncio.run(drive([{"type": "away", "excursion": False}], conn, layouts))
    return layouts.minimized == 1 and conn["left"] is True


def check_leave_is_idempotent() -> bool:
    """The watchdog and the socket teardown both call it — once is once."""
    conn, layouts = fresh_conn(), FakeRegistry()
    asyncio.run(web._leave_session(layouts, conn))
    asyncio.run(web._leave_session(layouts, conn))
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
    reg = _registry_with(["Editor"])
    reg.last_focus = (0, "Browser")
    return reg.resume_index() is None


def check_rename_rejects_empty() -> bool:
    """An empty name would leave a nameless row in the layout bar."""
    window_manager.is_alive = lambda hwnd: True
    reg = _registry_with(["Editor"])
    return (not reg.rename(0, "   ") and not reg.rename(5, "Nope")
            and reg.rename(0, " Notes ") and reg.layouts[0].name == "Notes")


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
