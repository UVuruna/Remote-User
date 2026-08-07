"""A fake Windows, shared by the two focus gates.

Split out of `test_focus_guard.py` on 2026-08-07 (THE STRUCTURE LAW): that
file crossed 1,000 lines, and it had grown two subjects — WHERE typed input
lands (policy, `test_focus_guard.py`) and HOW we hear about a foreground
change and shut it down again (machinery, `test_focus_hook.py`). The fakes
they share live here rather than in either of them, and certainly not twice.

NOTHING HERE TOUCHES THE OWNER'S DESKTOP, and that is a rule, not an
optimisation: he works on this machine while these run. No real
`SetWinEventHook` is installed, no real window is raised, no real key or mouse
event is injected — a hook or a thread a FAILING test forgot to release is his
mouse juddering, not a red line in a terminal. What stays real is everything
the defects were ever in: the threads, the joins, the identity book, the
injector's own chunking logic.
"""

import json
import logging
import sys
import threading
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "server"))

import focus_guard  # noqa: E402
import focus_hook  # noqa: E402
import input_injector  # noqa: E402
import web  # noqa: E402
import window_manager  # noqa: E402

MEMBER_A, MEMBER_B, DIALOG, THIEF = 0x10, 0x20, 0x30, 0x99


# ═══════════════════════════ THE FAKE DESKTOP ═══════════════════════════
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
    """Records (hwnd, topmost) of every raise the guard asks for — and raises
    NOTHING: `window_manager.raise_window` is replaced, so no window on this
    machine is ever moved.

    Given `fake`, the recorded raise also WORKS — the fake foreground follows
    it. That is what lets a test watch a mid-sentence steal actually being
    undone; without it the raise is only recorded and focus stays with the
    thief, which is the other case worth proving (the typing must stop)."""

    def install(self, fake=None):
        def _raise(hwnd, topmost=True):
            self.append((hwnd, topmost))
            if fake is not None:
                fake.fg = hwnd
        window_manager.raise_window = _raise
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


class Catch(logging.Handler):
    """Every line the named loggers write inside the `with` block. The thief's
    name is half of what these gates prove, so it is read, not assumed."""

    def __init__(self, *loggers):
        super().__init__()
        self.loggers = loggers
        self.records: list[str] = []

    def emit(self, record):
        self.records.append(record.getMessage())

    def __enter__(self):
        for log in self.loggers:
            log.addHandler(self)
        return self

    def __exit__(self, *exc):
        for log in self.loggers:
            log.removeHandler(self)

    def naming(self, hwnd: int) -> bool:
        return any(f"{hwnd:#x}" in line and f"app{hwnd:x}.exe" in line
                   for line in self.records)


# ═══════════════════════════ THE FAKE HOOK ═══════════════════════════
class FakeHookWin32:
    """`focus_hook`'s Win32 — the four calls it makes into Windows, faked, so
    the thread and its whole lifecycle can be driven without installing a
    single real hook on the owner's PC.

    `refuse` = Windows says no to the hook. `deaf` = WM_QUIT is accepted and
    goes nowhere, which is the only way to make a `stop()` time out on
    purpose."""

    def __init__(self, refuse=False, deaf=False):
        self.refuse = refuse
        self.deaf = deaf
        self.quit = threading.Event()
        self.hooks = 0
        self.unhooked = 0

    def SetWinEventHook(self, *a):        # noqa: N802 — mirrors the Win32 name
        if self.refuse:
            return 0
        self.hooks += 1
        return 0x1234

    def GetMessageW(self, *a):            # noqa: N802
        self.quit.wait()                  # blocks exactly like the real loop
        return 0                          # 0 = WM_QUIT was retrieved

    def DispatchMessageW(self, *a):       # noqa: N802
        return 0

    def UnhookWinEvent(self, _handle):    # noqa: N802
        self.unhooked += 1
        return 1

    def PostThreadMessageW(self, _tid, _msg, _w, _l):   # noqa: N802
        if self.deaf:
            return 1                      # "delivered" — but nothing wakes up
        self.quit.set()
        return 1

    def GetCurrentThreadId(self):         # noqa: N802
        return 4242


def install_fake_hook_win32(**kwargs) -> tuple[FakeHookWin32, callable]:
    """Returns (fake, restore). `restore()` is unconditional cleanup: it wakes
    the message loop whatever the test did, stops the thread and puts the real
    Win32 back — so a check that FAILS still leaves no thread behind."""
    fake = FakeHookWin32(**kwargs)
    real = (focus_hook.user32, focus_hook.kernel32)

    def restore():
        fake.deaf = False
        fake.quit.set()                   # never leave the thread parked
        focus_hook.stop()
        focus_hook.user32, focus_hook.kernel32 = real

    focus_hook.user32 = focus_hook.kernel32 = fake
    return fake, restore


def fake_listen(listen):
    """Swap `focus_hook`'s two entry points; returns (released, restore). Used
    where what matters is that `watch` USES the hook and gives it back, not
    what the hook itself does."""
    real = (focus_hook.listen, focus_hook.release)
    released: list = []
    focus_hook.listen = listen
    focus_hook.release = released.append

    def restore():
        focus_hook.listen, focus_hook.release = real
    return released, restore


# ═══════════════════════════ THE SPIES ═══════════════════════════
class TypeSpy(input_injector.InputInjector):
    """The REAL injector with only `SendInput` replaced: every UTF-16 unit is
    recorded together with the window that would have received it. Nothing is
    typed on this machine.

    `__init__` is deliberately not the parent's — nothing here needs a monitor
    rect or the injection monitor, and this must never touch a real cursor.
    `steal_at` flips the fake foreground to the thief after that many units,
    which is the owner's report reproduced exactly: focus moved WHILE the
    sentence was going out."""

    def __init__(self, fake, steal_at=None):
        self.fake = fake
        self.steal_at = steal_at
        self.units: list[tuple[int, int]] = []   # (UTF-16 unit, foreground)

    def _send_key(self, vk, scan, flags):
        if flags & input_injector.KEYEVENTF_KEYUP:
            return                                # one record per unit, on the way down
        self.units.append((scan, self.fake.fg))
        if self.steal_at is not None and len(self.units) == self.steal_at:
            self.fake.fg = THIEF

    @property
    def text(self) -> str:
        return b"".join(unit.to_bytes(2, "little")
                        for unit, _ in self.units).decode("utf-16-le")

    def landed_only_in(self, hwnd: int) -> bool:
        return all(fg == hwnd for _, fg in self.units)


class FakeInjector:
    """`lost` is what `type_text` reports as never having reached the PC —
    the phone has to be TOLD about that, and this is how the dispatcher's
    half of it gets tested."""

    def __init__(self, lost=""):
        self.lost = lost
        self.typed: list[str] = []
        self.guards: list = []      # the mid-sentence fence the dispatcher hands over

    def type_text(self, text, guard=None):
        self.typed.append(text)
        self.guards.append(guard)
        return self.lost

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


def run_checks(title: str, checks, subject: str) -> int:
    """The shared runner both gates print through — same shape, same exit
    code, and a crashing check is a FAILING check (never a silent skip)."""
    print(f"=== {title} ===")
    failed = 0
    for name, fn in checks:
        try:
            ok = fn()
        except Exception as e:
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"{title} FAILED — {failed} check(s).")
        return 1
    print(f"{title} PASSED — {subject}")
    return 0
