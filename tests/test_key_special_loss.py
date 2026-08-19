"""Key Special Loss Gate — HALF 2 of the 2026-08-13 MEASURED typing-loss
defect (the other half, the client's outbound queue, is gated by
`tests/test_type_queue.py`).

`key_text` and `paste_text` both toast `focus_guard.loss_notice` when the
fence could not be held — a phone that dictates a sentence into the wrong
window at least LEARNS about it. `key_special` (Backspace, arrows, Tab, Esc,
Delete, Home, End — every structural key `client/controls.js` sends) had NO
loss check at all: `server/web.py`'s `key_special` branch called
`injector.press_key` unconditionally, with no return value to check and
nothing for `injector.press_key` itself to report. A Backspace that landed
nowhere was invisible to the owner — exactly the "buttons randomly stopped
working" experience constraint 8 already names, and priority D of the
constitution (every app carries SOME error visibility).

THE FIX: `server/web.py`'s `key_special` branch now runs
`focus_guard.typist(layouts, conn)` — the SAME verified checkpoint
`InputInjector.type_text`'s chunk loop already calls between characters — once,
before injecting. A held fence presses the key and costs nothing extra (a
bare foreground read, matching the happy-path cost documented on `typist`);
a fence that could not be recovered presses NOTHING and toasts
`focus_guard.loss_notice(key, unit="key press")` on the SAME toast machinery
`key_text`/`paste_text` already use.

Driven through the REAL dispatcher (`web._receive_input`) with the SAME fakes
`test_focus_guard.py` uses — nothing here touches the owner's desktop.

Run:  .venv\\Scripts\\python tests/test_key_special_loss.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _focus_fakes import (  # noqa: E402
    FakeInjector, FakeWs, MEMBER_A, Raises, THIEF, focus_guard, fresh_conn,
    layout_with, run_checks, web, with_win32,
)


# ═══════════ 1. a held fence presses the key and toasts nothing ═══════════
def check_a_held_fence_presses_the_key_and_stays_silent() -> bool:
    with_win32(fg=MEMBER_A, alive=(MEMBER_A,))
    Raises().install()
    reg, conn = layout_with([MEMBER_A]), fresh_conn(active=0)
    injector = FakeInjector()

    async def run():
        ws = FakeWs([{"type": "key_special", "key": "backspace"}])
        try:
            await web._receive_input(ws, injector=injector, stream=None,
                                     token="t", layouts=reg, conn=conn)
        except web.WebSocketDisconnect:
            pass
        return ws

    ws = asyncio.run(run())
    toasts = [m for m in ws.sent if m.get("type") == "toast"]
    return (("press_key", "backspace") in injector.ops and toasts == [])


# ═══════════ 2. a fence that cannot be recovered presses nothing and says so ═══════════
def check_a_lost_fence_injects_nothing_and_toasts_the_loss() -> bool:
    """The thief holds the foreground and CANNOT be evicted (`Raises().install()`
    with no fake, so the hand-back never lands) — the case the owner actually
    lives with: an elevated or stubborn window. What must be true is both at
    once: zero injections, and a toast naming the key that never arrived."""
    with_win32(fg=THIEF, alive=(MEMBER_A, THIEF))
    Raises().install()                # the raise is refused: focus stays gone
    reg, conn = layout_with([MEMBER_A]), fresh_conn(active=0)
    injector = FakeInjector()

    async def run():
        ws = FakeWs([{"type": "key_special", "key": "backspace"}])
        try:
            await web._receive_input(ws, injector=injector, stream=None,
                                     token="t", layouts=reg, conn=conn)
        except web.WebSocketDisconnect:
            pass
        return ws

    ws = asyncio.run(run())
    toasts = [m for m in ws.sent if m.get("type") == "toast"]
    return (injector.ops == [] and len(toasts) == 1
            and "backspace" in toasts[0]["text"]
            and "key press" in toasts[0]["text"]
            and "characters" not in toasts[0]["text"])


# ═══════════ 3. the toast wording never claims a character count ═══════════
def check_loss_notice_names_a_key_press_not_a_character_count() -> bool:
    """`loss_notice`'s default sentence counts characters ("9 characters did
    NOT reach the PC") — wired straight through for a key name it would read
    "9 characters ... 'backspace'", naming the wrong thing entirely. The
    `unit="key press"` branch must produce a sentence about ONE key, not a
    length that happens to match how many letters spell its name."""
    text = focus_guard.loss_notice("backspace", unit="key press")
    return "backspace" in text and "9 characters" not in text and "A key press" in text


# ═══════════ 4. key_text's own wording is untouched by the new branch ═══════════
def check_key_text_loss_wording_is_unchanged() -> bool:
    """The default call (no `unit=`) must still read exactly as it did before
    this round — the new branch is additive, never a rewording of the
    sibling it was modelled on."""
    text = focus_guard.loss_notice("hello world")
    return text == ('11 characters did NOT reach the PC — another window '
                     'took the keyboard: “hello world”')


CHECKS = [
    ("a held fence presses the key and toasts nothing",
     check_a_held_fence_presses_the_key_and_stays_silent),
    ("a fence that cannot be recovered injects nothing and toasts the loss",
     check_a_lost_fence_injects_nothing_and_toasts_the_loss),
    ("the toast names a key press, never a character count",
     check_loss_notice_names_a_key_press_not_a_character_count),
    ("key_text's own loss wording is unchanged by the new branch",
     check_key_text_loss_wording_is_unchanged),
]


def test_gate():
    assert run_checks(
        "KEY SPECIAL LOSS GATE", CHECKS,
        "a Backspace/arrow/Tab/Esc that lands nowhere is now TOLD to the "
        "phone, on the same toast machinery key_text and paste_text use") == 0


if __name__ == "__main__":
    sys.exit(run_checks(
        "KEY SPECIAL LOSS GATE", CHECKS,
        "a Backspace/arrow/Tab/Esc that lands nowhere is now TOLD to the "
        "phone, on the same toast machinery key_text and paste_text use"))
