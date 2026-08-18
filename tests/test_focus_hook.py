"""Focus gate, part two: the machinery that makes the defence INSTANT — and
that has to disappear without a trace when the app ends.

`test_focus_guard.py` proves the POLICY (where typed input may land). This
file proves the plumbing underneath it, split out on 2026-08-07 when the two
subjects together crossed THE STRUCTURE LAW's 1,000 lines:

1. Windows ANNOUNCES a foreground change (`SetWinEventHook`), so the layout is
   defended in milliseconds instead of up to one 250 ms poll — and the poll
   still defends when Windows refuses the hook.
2. **A listener may only SIGNAL.** A WinEventProc runs inside Windows' own
   event dispatch: the first version called `guard` straight from there and
   was measured stalling a second caller for 2.99 s, because `guard` waits on
   a lock held across a window raise that waits for a frame to settle. The
   owner felt exactly this as a juddering mouse. If that contract is broken
   again, the log says so — Windows detaches a slow hook without a word, and
   we would go on believing we had millisecond reaction.
3. **Nothing of ours outlives us** (owner decree 2026-08-05, the topmost
   ledger's rule applied to a thread and a hook handle): every documented exit
   path stops the listener, and a `stop()` whose join times out keeps the
   thread's identity instead of orphaning it with the hook still installed.
4. One decision at a time: three callers can now reach `guard` at once.

NO REAL HOOK IS INSTALLED AND NO REAL WINDOW IS TOUCHED — see
[_focus_fakes.py](_focus_fakes.py). The owner works on this machine.

Run:  .venv\Scripts\python tests/test_focus_hook.py
"""

import ast
import asyncio
import sys
import threading
import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))

from _focus_fakes import (  # noqa: E402
    MEMBER_A, PROJECT_DIR, THIEF, Catch, Raises, fake_listen, focus_guard,
    focus_hook, fresh_conn, install_fake_hook_win32, layout_with, run_checks,
    with_win32,
)


def check_the_hook_defends_without_waiting_for_the_poll() -> bool:
    """A quarter of a second is not "instant" when the thing being defended is
    a dictated sentence: the recognizer hands over the whole utterance at the
    END of a round, so a window that holds the keyboard for 250 ms can still
    take all of it. Windows announces the change — the defence must land on
    that announcement, measurably before the poll tick would have come."""
    fake = with_win32(fg=MEMBER_A, alive=(MEMBER_A, THIEF))
    raises = Raises().install(fake)
    reg = layout_with([MEMBER_A])
    registered: list = []
    released, restore = fake_listen(lambda cb: (registered.append(cb), True)[1])

    async def run() -> bool:
        started = time.perf_counter()
        task = asyncio.ensure_future(focus_guard.watch(reg, fresh_conn(active=0)))
        await asyncio.sleep(0.02)          # far below one poll interval
        if not registered:
            task.cancel()
            return False
        fake.fg = THIEF                    # something grabs the keyboard...
        registered[0]()                    # ...and Windows says so at once
        for _ in range(20):                # give the worker a moment, not a poll
            await asyncio.sleep(0.005)
            if raises:
                break
        spent = time.perf_counter() - started
        ok = (raises == [(MEMBER_A, True)] and fake.fg == MEMBER_A
              # the poll could not have done this yet — that is the whole point
              and spent < focus_guard.WATCH_POLL_S)
        task.cancel()
        await asyncio.sleep(0)             # let the task's finally run
        return ok

    try:
        answered = asyncio.run(run())
    finally:
        restore()
    # ...and the listener is handed back when the connection ends: nothing of
    # ours may outlive the phone (the topmost-ledger discipline). Note HOW the
    # task is ended above — cancelled and never awaited, exactly as the web
    # layer's `finally` does it. A release that needed one more turn of the
    # event loop would never happen at all, and the hook would stay installed
    # for the life of the process.
    return answered and released == registered


def check_the_hook_callback_only_signals() -> bool:
    """D1, and the owner felt this one: a WinEventProc runs INSIDE Windows'
    own event dispatch. The first version called `guard` straight from there,
    which waits on a lock held across a window raise that waits for a frame to
    settle — measured stalling a second caller for 2.99 s. Everything the
    desktop does with the foreground queues behind that.

    So the callback must return at once and the work must happen elsewhere."""
    with_win32(fg=MEMBER_A, alive=(MEMBER_A, THIEF))
    reg = layout_with([MEMBER_A])
    registered: list = []
    _, restore_hook = fake_listen(lambda cb: (registered.append(cb), True)[1])
    ran_on: list[str] = []
    real_guard = focus_guard.guard

    def slow_guard(layouts, conn, typing=True):
        ran_on.append(threading.current_thread().name)
        time.sleep(0.30)                   # the 3-second stall, in miniature
        return MEMBER_A

    async def run() -> bool:
        task = asyncio.ensure_future(focus_guard.watch(reg, fresh_conn(active=0)))
        await asyncio.sleep(0.02)
        if not registered:
            task.cancel()
            return False
        caller = threading.Thread(target=registered[0], name="pretend-hook-thread")
        began = time.perf_counter()
        caller.start()
        caller.join(2.0)
        spent = time.perf_counter() - began
        await asyncio.sleep(0.10)          # the work happens meanwhile...
        task.cancel()
        await asyncio.sleep(0)
        return (not caller.is_alive() and spent < 0.05      # returned at once
                and ran_on                                   # ...and it DID run
                and "pretend-hook-thread" not in ran_on)     # ...just not there

    focus_guard.guard = slow_guard
    try:
        return asyncio.run(run())
    finally:
        focus_guard.guard = real_guard
        restore_hook()


def check_a_listener_that_works_instead_of_signalling_is_logged() -> bool:
    """If that contract is ever broken again, the log must say so — Windows
    detaches a slow hook without a word, and we would go on believing we had
    millisecond reaction while running on the poll alone."""
    fake, restore = install_fake_hook_win32()
    try:
        focus_hook.listen(lambda: time.sleep(focus_hook.CALLBACK_BUDGET_S * 4))
        with Catch(focus_hook.logger) as caught:
            focus_hook._dispatch(0, focus_hook.EVENT_SYSTEM_FOREGROUND, MEMBER_A,
                                 focus_hook.OBJID_WINDOW, 0, 0, 0)
        return any("may only signal" in line for line in caught.records)
    finally:
        restore()


def check_a_hook_that_went_quiet_is_reported() -> bool:
    """Windows never says it detached a hook. The evidence available to us is
    exactly this: the POLL had to undo a steal that the hook, which Windows
    still claims to hold, never announced. Said once, not every poll."""
    with_win32(fg=THIEF, alive=(MEMBER_A, THIEF))
    Raises().install()
    fake, restore = install_fake_hook_win32()
    try:
        focus_hook.listen(lambda: None)          # a hook Windows "holds"
        reg, conn = layout_with([MEMBER_A]), fresh_conn(active=0)
        conn["hook_events"] = focus_hook.event_count()
        with Catch(focus_guard.logger) as caught:
            focus_guard._defend(reg, conn, False)     # the poll found it
            focus_guard._defend(reg, conn, False)     # ...and says so ONCE
        return sum("DETACHED" in line for line in caught.records) == 1
    finally:
        restore()


def check_the_poll_still_defends_when_the_hook_is_refused() -> bool:
    """Belt AND braces: `SetWinEventHook` can be refused, and Windows drops a
    hook whose thread stops pumping. The 0.25 s poll is what makes that a
    slower defence instead of no defence."""
    fake = with_win32(fg=THIEF, alive=(MEMBER_A, THIEF))
    raises = Raises().install(fake)
    reg = layout_with([MEMBER_A])
    _, restore = fake_listen(lambda cb: False)      # Windows said no

    async def run():
        task = asyncio.ensure_future(focus_guard.watch(reg, fresh_conn(active=0)))
        await asyncio.sleep(focus_guard.WATCH_POLL_S * 3)
        task.cancel()

    try:
        asyncio.run(run())
    finally:
        restore()
    return bool(raises) and raises[0] == (MEMBER_A, True)


def check_the_listener_thread_starts_stops_and_repeats() -> bool:
    """A real thread with a real message loop and a real join — over a faked
    Windows. It must install, deliver, unhook, and be gone after `stop()`,
    twice over, because `stop()` is reached from several exit paths at once."""
    fake, restore = install_fake_hook_win32()
    try:
        fired: list[int] = []
        started = focus_hook.listen(lambda: fired.append(1))
        thread = focus_hook._thread
        if not started or thread is None or not thread.is_alive():
            return False
        # Only OUR event, and only for the window itself (not a child part).
        focus_hook._dispatch(0, focus_hook.EVENT_SYSTEM_FOREGROUND, MEMBER_A,
                             focus_hook.OBJID_WINDOW, 0, 0, 0)
        focus_hook._dispatch(0, 0x800C, MEMBER_A, focus_hook.OBJID_WINDOW, 0, 0, 0)
        focus_hook.stop()
        focus_hook.stop()                 # idempotent — the second is a no-op
        stopped = (not thread.is_alive() and focus_hook._thread is None
                   and fake.unhooked == 1)   # the handle went back to Windows
        # ...and it can be started again afterwards (Apply & restart).
        fake.quit.clear()
        again = focus_hook.listen(lambda: None)
        alive_again = focus_hook._thread is not None and focus_hook._thread.is_alive()
        return fired == [1] and stopped and again and alive_again
    finally:
        restore()


def check_a_timed_out_stop_never_orphans_silently() -> bool:
    """D2, and it is the topmost leak in another costume: `stop()` used to
    clear the thread identity BEFORE knowing the join had worked. Measured —
    the thread stayed alive, `UnhookWinEvent` was never called, and the next
    `listen()` installed a SECOND hook over the first, whose tid was now
    unreachable forever.

    A join that misses must keep the identity, say so loudly, install nothing
    over it, and stay quick: this runs on the Qt UI thread at tray Quit."""
    fake, restore = install_fake_hook_win32(deaf=True)    # WM_QUIT goes nowhere
    try:
        focus_hook.listen(lambda: None)
        thread = focus_hook._thread
        with Catch(focus_hook.logger) as caught:
            began = time.perf_counter()
            focus_hook.stop()
            spent = time.perf_counter() - began
        kept = focus_hook._thread is thread and focus_hook._tid != 0
        loud = any("did not stop within" in line for line in caught.records)
        quick = spent < 0.5               # the owner's Quit may not hang on this
        focus_hook.listen(lambda: None)   # ...and nothing is installed over it
        one_hook = fake.hooks == 1 and focus_hook._thread is thread
        # Now let it go, and the book empties properly.
        fake.deaf = False
        focus_hook.stop()
        gone = (focus_hook._thread is None and not thread.is_alive()
                and fake.unhooked == 1)
        return kept and loud and quick and one_hook and gone
    finally:
        restore()


def _calls_inside(rel: str, func: str, needle: str) -> bool:
    """Does `func` in that file really CALL `needle`? Parsed, not grepped: a
    file-wide substring search would stay green if tray Quit stopped calling
    `release_windows` while any other line in the file still named it."""
    tree = ast.parse((PROJECT_DIR / rel).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == func):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Call) and needle in ast.unparse(inner):
                    return True
    return False


def check_every_exit_path_stops_the_listener() -> bool:
    """No zombie thread, no leaked hook handle — the same discipline as the
    topmost ledger. There is ONE funnel, `ServerController.release_windows`;
    it is EXECUTED here, and every documented way out is checked to really
    call it, inside the function that handles that way out."""
    fake, restore = install_fake_hook_win32()
    try:
        focus_hook.listen(lambda: None)
        thread = focus_hook._thread
        import server_core                    # the real funnel, called unbound
        server_core.ServerController.release_windows(None)
        if thread is None or thread.is_alive() or focus_hook._thread is not None:
            return False
        if fake.unhooked != 1:
            return False
    finally:
        restore()
    exits = [
        # the funnel itself
        ("server/server_core.py", "release_windows", "focus_hook.stop()"),
        # server stop / Apply & restart, and the serve() teardown
        ("server/server_core.py", "stop", "self.release_windows()"),
        ("server/server_core.py", "_serve", "self.release_windows()"),
        # Ctrl+C / console close / logoff, and the interpreter's own exit
        ("server/main.py", "main", "atexit.register(controller.release_windows)"),
        ("server/main.py", "main", "SetConsoleCtrlHandler"),
        ("server/main.py", "_console_event", "controller.release_windows()"),
        # the desktop app: Qt's own quit, and atexit behind it
        ("server/gui_main.py", "main",
         "app.aboutToQuit.connect(controller.release_windows)"),
        ("server/gui_main.py", "main", "atexit.register(controller.release_windows)"),
        # tray Quit — in the ServerControl mixin since 2026-08-18 (VC-R3);
        # the exit path is the same one, it simply lives with the rest of this
        # window's power over the server it wraps
        ("server/gui/main_window_server.py", "_quit",
         "self.controller.release_windows()"),
    ]
    return all(_calls_inside(rel, func, needle) for rel, func, needle in exits)




def check_two_threads_cannot_decide_at_once() -> bool:
    """There are three callers now — the message that types, the poll, and
    (through the loop) the hook. Two of them deciding at the same time would
    race over the pin and could raise two different windows, so `guard` holds
    a lock. Nothing tested that lock until it was asked for."""
    with_win32(fg=THIEF, alive=(MEMBER_A, THIEF))
    Raises().install()
    reg, conn = layout_with([MEMBER_A]), fresh_conn(active=0)
    inside, overlap = threading.Event(), []
    real_refocus = focus_guard._refocus

    def slow_refocus(hwnd):
        if inside.is_set():
            overlap.append(hwnd)      # two threads inside the decision at once
        inside.set()
        time.sleep(0.05)
        inside.clear()

    focus_guard._refocus = slow_refocus
    try:
        threads = [threading.Thread(target=focus_guard.guard, args=(reg, conn, False))
                   for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(2.0)
        return not overlap and not any(t.is_alive() for t in threads)
    finally:
        focus_guard._refocus = real_refocus




CHECKS = [
    ("the hook defends in milliseconds, without waiting for the poll",
     check_the_hook_defends_without_waiting_for_the_poll),
    ("the hook callback only SIGNALS — it never works on Windows' thread",
     check_the_hook_callback_only_signals),
    ("a listener that works instead of signalling is logged",
     check_a_listener_that_works_instead_of_signalling_is_logged),
    ("a hook that went quiet is reported, once",
     check_a_hook_that_went_quiet_is_reported),
    ("the poll still defends when the hook is refused",
     check_the_poll_still_defends_when_the_hook_is_refused),
    ("the listener thread starts, stops, unhooks, and starts again",
     check_the_listener_thread_starts_stops_and_repeats),
    ("a timed-out stop never orphans the thread silently",
     check_a_timed_out_stop_never_orphans_silently),
    ("every documented exit path really calls the funnel that stops it",
     check_every_exit_path_stops_the_listener),
    ("two threads cannot decide the target at once",
     check_two_threads_cannot_decide_at_once),
]


def main() -> int:
    return run_checks("FOCUS HOOK GATE", CHECKS,
                      "the defence is instant, and it leaves nothing behind.")


def test_focus_hook():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
