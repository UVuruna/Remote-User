"""Focus gate: what the phone types lands where the owner is looking.

Regression proof for the 2026-08-06 live complaint, reported three times in
one evening and once by accident — a sentence he dictated for another project
arrived in THIS project's session, because mid-dictation the PC's focus moved
and every following keystroke followed it.

`SendInput` has no target: it types into whatever window Windows calls the
foreground at that instant. So anything on the PC that takes focus while he
speaks — an app starting, a dialog, another agent's editor window — takes the
rest of his sentence too, silently, with the stream still showing the PC.

What is proven here, without Windows and without a browser (every user32 call
window_manager makes is answered by a fake):

1. IN A LAYOUT the fence is the layout: a foreground outside its members is
   refused, focus is handed back to the member that was being typed into, and
   only then do the keys go out.
2. A legitimate move inside the layout is followed, not fought — and a DIALOG
   of a member (Save As…) counts as that member.
3. AT THE DESKTOP the target is the window the typing burst started in, and it
   is re-armed by what the owner does on purpose (an injected click,
   `next_input`, a layout switch) — never by a thief, which sends no message.
4. Re-focusing a layout leaves the KEYBOARD member in front. Raising members
   in plain list order is the second half of the same bug: one excursion (a
   picker, a permission dialog) closes the socket, the page re-focuses the
   layout, and dictation resumed in whichever window sat last in the grid.
5. The thief is NAMED in the log every time — the app being the last to know
   is what cost three trips back to the phone.

Run:  .venv\\Scripts\\python tests/test_focus_guard.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

import focus_guard  # noqa: E402
import web  # noqa: E402
import window_manager  # noqa: E402

MEMBER_A, MEMBER_B, DIALOG, THIEF = 0x10, 0x20, 0x30, 0x99


class FakeWin32:
    """The handful of user32 calls the guard makes. `fg` is the foreground,
    `owner` maps a window to the one that raised it (GW_OWNER)."""

    def __init__(self, fg=0, alive=(), owner=None):
        self.fg = fg
        self.alive = set(alive)
        self.owner = dict(owner or {})

    def GetForegroundWindow(self):        # noqa: N802 — mirrors the Win32 name
        return self.fg

    def GetWindow(self, hwnd, cmd):       # noqa: N802
        return self.owner.get(hwnd, 0) if cmd == focus_guard.GW_OWNER else 0

    def IsWindow(self, hwnd):             # noqa: N802
        return 1 if hwnd in self.alive else 0

    def __getattr__(self, name):
        return lambda *a, **k: 0          # ShowWindow, SetWindowPos, … no-ops


class Raises(list):
    """Records (hwnd, topmost) of every raise the guard asks for."""

    def install(self):
        window_manager.raise_window = lambda hwnd, topmost=True: \
            self.append((hwnd, topmost))
        return self


def with_win32(fg, alive=(), owner=None) -> FakeWin32:
    fake = FakeWin32(fg, alive, owner)
    window_manager.user32 = fake
    window_manager.dwmapi = fake
    window_manager._process_name = lambda hwnd: f"app{hwnd:x}.exe"
    window_manager._title = lambda hwnd: f"window {hwnd:#x}"
    return fake


def layout_with(members, last_member=None) -> window_manager.LayoutRegistry:
    reg = window_manager.LayoutRegistry()
    lay = window_manager.Layout("Work", "code.exe", list(members),
                                "2x1" if len(members) > 1 else None,
                                "portrait", 0.5)
    lay.last_member = last_member or members[0]
    reg.layouts.append(lay)
    return reg


def fresh_conn(active=None) -> dict:
    return {"ratio": 9 / 16, "active": active, "region": None, "quality": None,
            "seen": 0.0, "away": None, "left": False,
            "pin": None, "pin_stale": True}


# ═══════════════════ 1. the layout is a fence ═══════════════════
def check_a_thief_never_gets_the_keystroke() -> bool:
    """The report itself: focus moved to another agent's window mid-sentence.
    The keys must go back to the member he was typing into, first."""
    with_win32(fg=THIEF, alive=(MEMBER_A, MEMBER_B, THIEF))
    raises = Raises().install()
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_B)
    conn = fresh_conn(active=0)
    target = focus_guard.guard(reg, conn)
    return (target == MEMBER_B and raises == [(MEMBER_B, True)]
            and conn["pin"] == MEMBER_B)


def check_the_fence_holds_without_a_pin() -> bool:
    """A fresh connection after an excursion has no pin — the layout's own
    memory of which member held the keyboard is what answers."""
    with_win32(fg=THIEF, alive=(MEMBER_A, MEMBER_B, THIEF))
    raises = Raises().install()
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_B)
    return (focus_guard.guard(reg, fresh_conn(active=0)) == MEMBER_B
            and raises == [(MEMBER_B, True)])


def check_a_move_inside_the_layout_is_followed() -> bool:
    """He clicked into the other pane himself — that is not a theft, and the
    layout remembers the new target for the next reconnect."""
    with_win32(fg=MEMBER_B, alive=(MEMBER_A, MEMBER_B))
    raises = Raises().install()
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_A)
    conn = fresh_conn(active=0)
    return (focus_guard.guard(reg, conn) == MEMBER_B and not raises
            and reg.layouts[0].last_member == MEMBER_B and conn["pin"] == MEMBER_B)


def check_a_dialog_of_a_member_is_the_member() -> bool:
    """Save As… is a window of its own and belongs to no layout — yanking
    focus out of it would make typing a file name impossible."""
    with_win32(fg=DIALOG, alive=(MEMBER_A, DIALOG), owner={DIALOG: MEMBER_A})
    raises = Raises().install()
    reg = layout_with([MEMBER_A])
    return focus_guard.guard(reg, fresh_conn(active=0)) == DIALOG and not raises


# ═══════════════════ 2. the desktop has no fence, so build one ═══════════════════
def check_the_desktop_arms_on_the_first_key() -> bool:
    """No layout: the window the burst starts in IS the target."""
    fake = with_win32(fg=MEMBER_A, alive=(MEMBER_A, THIEF))
    raises = Raises().install()
    conn = fresh_conn()
    if focus_guard.guard(None, conn) != MEMBER_A or conn["pin"] != MEMBER_A:
        return False
    # ...and the next utterance goes back there when something steals focus.
    fake.fg = THIEF
    return (focus_guard.guard(None, conn) == MEMBER_A
            # NOT topmost: this window is nobody's layout member (owner
            # decree 2026-08-05 — a raise there stranded windows above the desk)
            and raises == [(MEMBER_A, False)])


def check_the_owners_own_click_re_arms_it() -> bool:
    """He moved to another window through the phone — the target follows him,
    because a click is a message and a thief is not."""
    fake = with_win32(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B))
    raises = Raises().install()
    conn = fresh_conn()
    focus_guard.guard(None, conn)          # armed on A
    focus_guard.retarget(conn)             # ...he clicked
    fake.fg = MEMBER_B
    return focus_guard.guard(None, conn) == MEMBER_B and not raises


def check_the_thief_is_named_in_the_log() -> bool:
    """A restored keystroke that logs nothing would only hide the next cause."""
    with_win32(fg=THIEF, alive=(MEMBER_A, THIEF))
    Raises().install()
    records: list[str] = []

    class Catch(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    handler = Catch()
    focus_guard.logger.addHandler(handler)
    try:
        focus_guard.guard(layout_with([MEMBER_A]), fresh_conn(active=0))
    finally:
        focus_guard.logger.removeHandler(handler)
    return any(f"{THIEF:#x}" in line and "app99.exe" in line for line in records)


# ═══════════════════ 3. the other half: the re-focus order ═══════════════════
def check_refocus_leaves_the_keyboard_member_in_front() -> bool:
    """One excursion closes the socket, the page re-focuses the layout — and
    raising members in list order handed the keyboard to the wrong window."""
    with_win32(fg=MEMBER_A, alive=(MEMBER_A, MEMBER_B))
    raises = Raises().install()
    window_manager.place_window = lambda hwnd, rect: True
    window_manager._frame_rect = lambda hwnd: (0, 0, 100, 100)
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_A)
    reg.focus(0, 0.5, (0, 0, 1000, 1000))
    # Last raised = the one left holding the keyboard.
    return [hwnd for hwnd, _ in raises][-1] == MEMBER_A


def check_prune_moves_the_target_off_a_closed_window() -> bool:
    """The member he was typing into was closed at the desk — the target may
    not stay pointing at a dead handle."""
    with_win32(fg=MEMBER_A, alive=(MEMBER_A,))
    Raises().install()
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_B)
    reg.prune()
    return reg.layouts[0].last_member == MEMBER_A


# ═══════════════════ 4. end to end, through the real dispatcher ═══════════════════
class FakeInjector:
    def __init__(self):
        self.typed: list[str] = []

    def type_text(self, text):
        self.typed.append(text)

    def __getattr__(self, name):
        return lambda *a, **k: None


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


def check_dictation_through_the_dispatcher() -> bool:
    """The whole path the owner's voice takes: `key_text` from the phone while
    a thief holds the foreground. The text must still arrive — in the layout."""
    with_win32(fg=THIEF, alive=(MEMBER_A, MEMBER_B, THIEF))
    raises = Raises().install()
    reg = layout_with([MEMBER_A, MEMBER_B], last_member=MEMBER_B)
    conn = fresh_conn(active=0)
    injector = FakeInjector()

    async def run():
        ws = FakeWs([{"type": "key_text", "text": "zdravo"}])
        try:
            await web._receive_input(ws, injector=injector, stream=None,
                                     token="t", layouts=reg, conn=conn)
        except web.WebSocketDisconnect:
            pass

    asyncio.run(run())
    return injector.typed == ["zdravo"] and raises == [(MEMBER_B, True)]


def check_a_click_message_re_arms_through_the_dispatcher() -> bool:
    """`press` / `click` / `next_input` are the owner choosing a window; the
    dispatcher must mark the target stale for the next keystroke."""
    with_win32(fg=MEMBER_A, alive=(MEMBER_A,))
    Raises().install()
    conn = fresh_conn()
    conn["pin"], conn["pin_stale"] = MEMBER_B, False

    async def run():
        ws = FakeWs([{"type": "press", "button": "left", "down": True}])
        try:
            await web._receive_input(ws, injector=FakeInjector(), stream=None,
                                     token="t", layouts=None, conn=conn)
        except web.WebSocketDisconnect:
            pass

    asyncio.run(run())
    return conn["pin_stale"] is True


CHECKS = [
    ("a focus thief never gets the keystroke", check_a_thief_never_gets_the_keystroke),
    ("the fence holds on a fresh connection (no pin yet)",
     check_the_fence_holds_without_a_pin),
    ("a move inside the layout is followed, not fought",
     check_a_move_inside_the_layout_is_followed),
    ("a dialog of a member counts as that member",
     check_a_dialog_of_a_member_is_the_member),
    ("at the desktop the burst's first window is the target",
     check_the_desktop_arms_on_the_first_key),
    ("the owner's own click re-arms the target", check_the_owners_own_click_re_arms_it),
    ("the thief is named in the log", check_the_thief_is_named_in_the_log),
    ("re-focus leaves the keyboard member in front",
     check_refocus_leaves_the_keyboard_member_in_front),
    ("prune moves the target off a closed window",
     check_prune_moves_the_target_off_a_closed_window),
    ("dictation survives a thief through the real dispatcher",
     check_dictation_through_the_dispatcher),
    ("a click message re-arms the target through the dispatcher",
     check_a_click_message_re_arms_through_the_dispatcher),
]


def main() -> int:
    print("=== FOCUS GATE ===")
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
        print(f"FOCUS GATE FAILED — {failed} check(s).")
        return 1
    print("FOCUS GATE PASSED — typed input lands where the owner is looking.")
    return 0


def test_focus_guard():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
