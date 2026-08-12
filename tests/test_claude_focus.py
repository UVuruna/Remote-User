"""CLAUDE FOCUS GATE — the prompt is focused before the command is typed, and
a window that is not VS Code costs ZERO keystrokes.

His report (2026-08-11, task 200): a Claude command "fails when the prompt is
not selected". `paste_text` types into whatever the focus guard's target is,
and inside VS Code that is just as easily the editor, the terminal or the file
tree — so `/model` arrives as literal text in a source file. His instruction
was that the program must focus the prompt itself before typing.

This round's investigation found the one delivery that does not depend on any
current state: the Claude Code extension registers the command **"Claude Code:
Focus input"**, and the Command Palette runs it from anywhere —
`Ctrl+Shift+P`, paste the name, Enter. `Ctrl+Escape` was rejected because it
TOGGLES focus, which is a coin flip.

WHAT THIS GATE HOLDS, AND WHY EACH ONE CAN BREAK SILENTLY:

1. THE ORDER. The palette sequence must complete BEFORE the real text's
   Ctrl+V. Reversed, the command text lands in the palette and the palette
   runs whatever it filtered to — an arbitrary VS Code command, submitted.
2. THE OLD PATH IS UNTOUCHED. A `paste_text` with no `focus` field must still
   be exactly two injections. Every other typed button in the app rides this
   function, and a palette chord leaking into them would fire `Ctrl+Shift+P`
   into Chrome, Explorer and his editor.
3. A STRANGER COSTS NOTHING. `Ctrl+Shift+P` is a GLOBAL chord; fired at the
   wrong window it is the accident class constraint 11 exists to prevent. So a
   target that is not `Code.exe` must inject NOTHING and say so on the phone.
4. A LOST FENCE WITHHOLDS THE ENTER. The sequence has two real gaps in it, and
   120-180 ms is a whole window for the thief of constraint 11. An Enter that
   lands after focus moved does not lose a keystroke — it RUNS whatever the
   stranger's palette or box was holding.
5. THE CARET HAND-OFF IS WAITED OUT (his report 2026-08-12, task 272 — the
   Claude Tools commands "only work if text is SELECTED"). The palette's Enter
   focuses nothing; it asks two other processes to. With no editor selection
   the extension takes its `deliverAtMention` branch, never reveals, and the
   webview's single bare `focus()` races the palette's own focus restore — so
   the sequence was right and the CLOCK was wrong, and a gate that measures
   only the order of the injections cannot see that.
6. THE SERVER REALLY WIRES IT. A pure function nobody calls is a feature that
   does not exist (the actions.json lesson, 2026-08-07), and this one is only
   reachable through one `elif` in `web.py`.

Every check was proven by planting its own defect — the mapping is in
DEFECTS below.

Run:  .venv\\Scripts\\python tests/test_claude_focus.py
"""

import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import content  # noqa: E402

WEB = PROJECT / "server" / "web.py"
CLAUDE_API = PROJECT / "server" / "claude_api.py"

# Which planted defect each check catches — written down so a later round can
# re-plant them instead of trusting this paragraph.
DEFECTS = {
    "the palette runs before the command text":
        "swap the two calls in web.py's paste_text branch (focus AFTER the paste)",
    "a plain paste_text is still exactly two injections":
        "make focus_claude_prompt run unconditionally, ignoring the field",
    "a window that is not VS Code costs zero injections":
        "drop the process assertion in content.focus_claude_prompt",
    "a fence lost mid-sequence withholds the Enter":
        "make _settled() return True always (never re-check the guard)",
    "the clipboard is left holding the real text, not the command name":
        "reverse the two clipboard writes",
    "the server really wires the field": "delete the elif branch from web.py",
    "the caret hand-off is waited out with no selection":
        "restore the old tail of focus_claude_prompt — replace the "
        "_handed_off(guard) call after the Enter with "
        "`time.sleep(FOCUS_STEP_DELAY)`",
}

TARGET = 0x4321


# ═══════════════════════════ THE FAKES ═══════════════════════════
class FakeInjector:
    """Records every injection IN ORDER — the whole subject of this gate is a
    sequence, so nothing here summarises it into a set."""

    def __init__(self):
        self.ops: list[tuple[str, str]] = []
        # WHEN each injection happened, not only in what order. The defect of
        # 2026-08-12 was purely temporal — every op was in the right place and
        # the paste still arrived before VS Code had moved the caret — so a
        # gate that records only the sequence cannot see it.
        self.at: list[float] = []

    def _note(self, op: tuple[str, str]) -> None:
        self.ops.append(op)
        self.at.append(time.perf_counter())

    def press_chord(self, chord: str) -> None:
        self._note(("chord", chord))

    def press_key(self, name: str) -> None:
        self._note(("key", name))

    def type_text(self, text: str, guard=None) -> str:
        self._note(("type", text))
        return ""


class FakeClipboard:
    """`content.clipboard` — records what was written, and can be made busy."""

    def __init__(self, busy=False):
        self.writes: list[str] = []
        self.busy = busy

    def copy_text(self, text: str) -> bool:
        if self.busy:
            return False
        self.writes.append(text)
        return True


class FakeGuard:
    """The focus fence as `focus_guard.typist` hands it over: a zero-argument
    callable answering the target's hwnd, or 0 when focus could not be brought
    back. `fails_at` is the 1-based call that first answers 0."""

    def __init__(self, fails_at=None, target=TARGET):
        self.calls = 0
        self.fails_at = fails_at
        self.target = target

    def __call__(self) -> int:
        self.calls += 1
        if self.fails_at is not None and self.calls >= self.fails_at:
            return 0
        return self.target


class Stage:
    """One run of the real code with the desktop faked out. Restores every
    patched module attribute — these tests run on the owner's own PC."""

    def __init__(self, process="code.exe", busy=False, real_handoff=False):
        self.injector = FakeInjector()
        self.clipboard = FakeClipboard(busy)
        self.process = process
        # The hand-off wait is the SUBJECT of one check, so that check pays for
        # it in real seconds; every other check zeroes it, as they zero the
        # injection gaps.
        self.real_handoff = real_handoff

    def __enter__(self):
        self._saved = (content.clipboard, content.FOCUS_STEP_DELAY,
                       content.PASTE_ENTER_DELAY, content.CLAUDE_HANDOFF_DELAY)
        content.clipboard = self.clipboard
        content.FOCUS_STEP_DELAY = 0.0     # the gaps are real; the waiting is not
        content.PASTE_ENTER_DELAY = 0.0
        if not self.real_handoff:
            content.CLAUDE_HANDOFF_DELAY = 0.0
        return self

    def __exit__(self, *_exc):
        (content.clipboard, content.FOCUS_STEP_DELAY,
         content.PASTE_ENTER_DELAY, content.CLAUDE_HANDOFF_DELAY) = self._saved
        return False

    def process_of(self, _hwnd: int) -> str:
        return self.process

    def focus(self, guard):
        return content.focus_claude_prompt(self.injector, guard, self.process_of)

    def paste(self, text, enter=True, guard=None):
        return content.paste_text(self.injector, text, enter, guard)


PALETTE = [("chord", "ctrl+shift+p"), ("chord", "ctrl+v"), ("key", "enter")]


# ═══════════════════════════ THE CHECKS ═══════════════════════════
def check_the_palette_runs_before_the_command_text() -> bool:
    """The whole sequence, in the order `web.py` runs it: focus first, then the
    command. Both halves paste, so ORDER is the only thing that separates
    "the command reached the prompt" from "the command ran the palette"."""
    with Stage() as stage:
        problem = stage.focus(FakeGuard())
        if problem:
            print(f"    focus refused a legitimate VS Code target: {problem}")
            return False
        stage.paste("/model", True, FakeGuard())
    ops, writes = stage.injector.ops, stage.clipboard.writes
    if ops != PALETTE + [("chord", "ctrl+v"), ("key", "enter")]:
        print(f"    injections were {ops}")
        return False
    if writes != [content.CLAUDE_FOCUS_COMMAND, "/model"]:
        print(f"    clipboard writes were {writes}")
        return False
    # Said as the property, not as the literal list: the palette's Enter must
    # be behind us before the command's paste begins.
    return ops.index(("chord", "ctrl+shift+p")) < ops.index(("key", "enter")) \
        < len(ops) - 1


def check_a_plain_paste_text_is_still_two_injections() -> bool:
    """No `focus` field = exactly the behaviour every other typed button has
    had since 2026-08-05. Enter is still separable."""
    with Stage() as stage:
        stage.paste("/usage", True, FakeGuard())
        if stage.injector.ops != [("chord", "ctrl+v"), ("key", "enter")]:
            print(f"    injections were {stage.injector.ops}")
            return False
    with Stage() as stage:
        stage.paste("/", False, FakeGuard())
        if stage.injector.ops != [("chord", "ctrl+v")]:
            print(f"    enter:false still pressed something: {stage.injector.ops}")
            return False
    return True


def check_a_window_that_is_not_vscode_costs_zero_injections() -> bool:
    """A global chord fired into a stranger is the accident this prevents. The
    refusal is total: no chord, no clipboard write, and a sentence for the
    phone (never a silent return — silence is the original bug in a coat)."""
    for process in ("chrome.exe", "explorer.exe", ""):
        with Stage(process=process) as stage:
            problem = stage.focus(FakeGuard())
            if not problem:
                print(f"    {process!r} was accepted as the Claude host")
                return False
            if stage.injector.ops or stage.clipboard.writes:
                print(f"    {process!r}: {stage.injector.ops} / "
                      f"{stage.clipboard.writes}")
                return False
    # And a fence that could not be restored at all is the same refusal.
    with Stage() as stage:
        if not stage.focus(FakeGuard(fails_at=1)):
            print("    a dead fence was treated as a focused prompt")
            return False
        if stage.injector.ops:
            print(f"    a dead fence still injected {stage.injector.ops}")
            return False
    # A busy clipboard must not fall back to TYPING the command name: the
    # palette re-filters on every character and the Enter would run whatever
    # it had filtered to.
    with Stage(busy=True) as stage:
        if not stage.focus(FakeGuard()) or stage.injector.ops:
            print(f"    busy clipboard: {stage.injector.ops}")
            return False
    return True


def check_a_fence_lost_mid_sequence_withholds_the_enter() -> bool:
    """The gaps are re-checked, not assumed. Whatever was already injected
    stands (the palette is visible on the PC and the owner can close it); what
    must never happen is the ENTER that submits."""
    # Lost after the palette opened, before the name could be pasted.
    with Stage() as stage:
        problem = stage.focus(FakeGuard(fails_at=2))
        if not problem or stage.injector.ops != [("chord", "ctrl+shift+p")]:
            print(f"    early loss: {problem!r} / {stage.injector.ops}")
            return False
    # Lost after the name was pasted — the dangerous one: the palette is
    # standing with text in it and an Enter would run the filtered entry.
    with Stage() as stage:
        problem = stage.focus(FakeGuard(fails_at=3))
        if not problem:
            print("    a lost fence before the Enter was reported as success")
            return False
        if ("key", "enter") in stage.injector.ops:
            print(f"    the Enter was still submitted: {stage.injector.ops}")
            return False
        if stage.injector.ops != [("chord", "ctrl+shift+p"), ("chord", "ctrl+v")]:
            print(f"    injections were {stage.injector.ops}")
            return False
    return True


def check_the_caret_hand_off_is_waited_out_with_no_selection() -> bool:
    """HIS REPORT OF 2026-08-12, AND THE PATH THAT SHIPPED UNGATED.

    Everything above this check measures a SEQUENCE, and the sequence was
    already right — which is exactly why the defect shipped. What was wrong was
    the clock. The palette's Enter does not focus anything; it asks another
    process to. `claude-vscode.focus` with no editor selection hands the empty
    string to `deliverAtMention`, which posts it to the webview and returns
    without ever calling `reveal()`, and the webview's handler then does its
    one bare `a.current?.focus()` — in the same tick the Command Palette is
    restoring focus to whatever it took it from. With a selection the same
    handler focuses a SECOND time, after the insert's DOM write, which is why
    only the no-selection case ever failed on his PC.

    So the promise this check holds is temporal: after the Enter, and BEFORE
    the command's own Ctrl+V, the code waits out a hand-off budget of its own —
    not the injection gap the other steps use — and that wait is fence-checked
    like every other gap in this file."""
    handoff = content.CLAUDE_HANDOFF_DELAY
    step = content.FOCUS_STEP_DELAY
    # A budget that is merely the injection gap under another name is the bug
    # with a new constant on it.
    if handoff < 3 * step:
        print(f"    the hand-off budget ({handoff}s) is not meaningfully "
              f"longer than an injection gap ({step}s)")
        return False

    # NO SELECTION is the whole case, and there is nothing to fake about it:
    # the editor's selection lives in VS Code, so what this measures is that we
    # never depend on it — the wait happens on every run, unconditionally.
    with Stage(real_handoff=True) as stage:
        problem = stage.focus(FakeGuard())
        if problem:
            print(f"    focus refused a legitimate target: {problem}")
            return False
        stage.paste("/code-review", True, FakeGuard())
    ops, at = stage.injector.ops, stage.injector.at
    if ops != PALETTE + [("chord", "ctrl+v"), ("key", "enter")]:
        print(f"    injections were {ops}")
        return False
    gap = at[ops.index(("chord", "ctrl+v"), 2)] - at[2]   # command paste − Enter
    # 0.9 rather than 1.0 only because a sliced sleep may finish a hair early
    # on a coarse clock; the point is the order of magnitude, never the digits.
    if gap < handoff * 0.9:
        print(f"    the command was pasted {gap * 1000:.0f} ms after the "
              f"palette Enter — VS Code was given no time to move the caret")
        return False

    # And the wait is not a blind sleep: a thief taking the foreground while VS
    # Code is still handing over must cost the command, not misplace it.
    with Stage(real_handoff=True) as stage:
        # 1 = the entry read of the target, 2 and 3 = the two palette gaps, so
        # 4 is the first re-read inside the hand-off.
        problem = stage.focus(FakeGuard(fails_at=4))
        if not problem:
            print("    a fence lost during the hand-off was reported as a "
                  "focused prompt")
            return False
        if stage.injector.ops != PALETTE:
            print(f"    the hand-off injected something extra: "
                  f"{stage.injector.ops}")
            return False
    return True


def check_the_server_really_wires_the_field() -> bool:
    """The feature is reachable only through `web.py`'s `paste_text` branch,
    and only for `focus == "claude"`. Read as source because the alternative —
    trusting that a handler calls a helper — is exactly how `wheel_order`
    shipped as a no-op for every user."""
    web = WEB.read_text(encoding="utf-8")
    api = CLAUDE_API.read_text(encoding="utf-8")
    if 'msg.get("focus") == "claude"' not in web:
        print("    web.py never reads the focus field")
        return False
    if "claude_api.focus_prompt" not in web:
        print("    web.py never asks for the prompt to be focused")
        return False
    # The refusal must SKIP the paste, not merely report it.
    branch = web.split('msg.get("focus") == "claude"', 1)[1][:400]
    if "continue" not in branch:
        print("    a refused focus still falls through to the paste")
        return False
    if "content.focus_claude_prompt" not in api or "toast" not in api:
        print("    claude_api does not run the sequence or does not toast")
        return False
    return True


CHECKS = [
    ("the palette runs before the command text",
     check_the_palette_runs_before_the_command_text),
    ("a plain paste_text is still exactly two injections",
     check_a_plain_paste_text_is_still_two_injections),
    ("a window that is not VS Code costs zero injections",
     check_a_window_that_is_not_vscode_costs_zero_injections),
    ("a fence lost mid-sequence withholds the Enter",
     check_a_fence_lost_mid_sequence_withholds_the_enter),
    ("the caret hand-off is waited out with no selection",
     check_the_caret_hand_off_is_waited_out_with_no_selection),
    ("the server really wires the field",
     check_the_server_really_wires_the_field),
]


def main() -> int:
    print("=== CLAUDE FOCUS GATE ===")
    failed = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as e:                 # a crashing check is a failing one
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"CLAUDE FOCUS GATE FAILED — {failed} check(s).")
        return 1
    print("CLAUDE FOCUS GATE PASSED — the prompt is focused first, and a "
          "stranger's window costs nothing.")
    return 0


def test_claude_focus():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
