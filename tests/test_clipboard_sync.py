"""Gate: THE CLIPBOARD LIVES ON BOTH DEVICES (task 182).

Three promises, each proven by planting the defect that would break it:

1. An injected Copy/Cut reads the PC clipboard back and pushes it to the
   phone (`after_copy_chord`).
2. A push that arrives while the phone cannot see it (no connection, or an
   announced excursion) is held — never dropped — and the LATEST one wins if
   more than one arrives before the phone returns (`flush_pending`).
3. No echo loop: text written to the PC clipboard ON THE PHONE'S BEHALF
   (`note_written`, what `content.paste_text` calls) is never read back and
   pushed to the phone as if it were a fresh PC-side copy — and two paths
   that see the SAME clipboard change (the immediate push after Copy, and
   what the live listener would see) never both send it.

NO REAL WIN32 CLIPBOARD OR WINDOW IS TOUCHED: `clipboard_sync.read_text` is
monkeypatched everywhere below, and the message-only-window listener thread
(`watch`'s Win32 half) is never started — its OS plumbing is exercised only
by hand on a machine, same as `focus_hook.py`'s hook. What IS proven here is
the logic every one of `watch`'s iterations runs: dedup, echo-guard and the
hidden/pending path — by driving them directly, the same shape `_defend` gets
driven in test_focus_hook.py.

Run:  .venv\\Scripts\\python tests/test_clipboard_sync.py
"""

import asyncio
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import clipboard_sync  # noqa: E402


class FakeWS:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))


def _reset() -> None:
    """Every check starts from a clean slate — the module's dedup/pending
    state is process-wide, exactly like focus_hook's single hook."""
    clipboard_sync._last_text = None
    clipboard_sync._pending = None


def _run(coro):
    return asyncio.run(coro)


def test_injected_copy_pushes_to_the_phone() -> None:
    _reset()
    clipboard_sync.read_text = lambda: "hello from the PC"
    ws = FakeWS()
    conn = {"away": None}
    _run(clipboard_sync.after_copy_chord(ws, conn, "ctrl+c"))
    assert ws.sent == [{"type": "clipboard", "text": "hello from the PC"}], (
        f"Copy did not push the clipboard text — got {ws.sent!r}. PLANTED "
        f"DEFECT: without after_copy_chord actually reading and pushing, "
        f"ws.sent stays empty.")


def test_a_non_copy_chord_pushes_nothing() -> None:
    _reset()
    clipboard_sync.read_text = lambda: "should never be read"
    ws = FakeWS()
    _run(clipboard_sync.after_copy_chord(ws, {"away": None}, "ctrl+v"))
    assert ws.sent == [], (
        "A Paste chord pushed clipboard text to the phone — only Copy/Cut "
        "may. PLANTED DEFECT: a chord filter that matches everything.")


def test_a_push_while_hidden_is_held_not_dropped() -> None:
    _reset()
    clipboard_sync.read_text = lambda: "copied while the phone was away"
    ws = FakeWS()
    conn = {"away": True}   # an announced excursion — the page cannot see this
    _run(clipboard_sync.after_copy_chord(ws, conn, "ctrl+c"))
    assert ws.sent == [], (
        "A push reached a hidden page directly instead of being held. "
        "PLANTED DEFECT: _push ignoring conn['away'].")
    assert clipboard_sync._pending == "copied while the phone was away", (
        "The text was neither sent nor held — it was silently DROPPED, "
        "exactly what task 182's honest limit forbids.")


def test_only_the_latest_pending_survives_and_flushes_on_return() -> None:
    _reset()
    ws = FakeWS()
    conn = {"away": True}
    for text in ("first copy", "second copy", "third and last copy"):
        clipboard_sync.read_text = lambda t=text: t
        clipboard_sync._last_text = None   # each is a genuinely fresh PC copy
        _run(clipboard_sync.after_copy_chord(ws, conn, "ctrl+c"))
    assert ws.sent == [], "Nothing should have reached the hidden page yet."
    assert clipboard_sync._pending == "third and last copy", (
        "Pending held an earlier copy instead of the latest one — a second "
        "copy while away must never queue behind the first.")
    # The phone returns: a fresh connection's first act is flush_pending.
    _run(clipboard_sync.flush_pending(ws))
    assert ws.sent == [{"type": "clipboard", "text": "third and last copy"}], (
        f"The return did not deliver exactly the latest held copy — got "
        f"{ws.sent!r}. PLANTED DEFECT: flush_pending sending the first text "
        f"instead of the last, or sending nothing at all.")
    assert clipboard_sync._pending is None, (
        "Pending was not cleared after flushing — the next connection would "
        "replay a copy the owner already received.")


def test_a_repeat_read_of_the_same_text_is_not_pushed_twice() -> None:
    _reset()
    clipboard_sync.read_text = lambda: "same text both times"
    ws = FakeWS()
    conn = {"away": None}
    _run(clipboard_sync.after_copy_chord(ws, conn, "ctrl+c"))
    _run(clipboard_sync.after_copy_chord(ws, conn, "ctrl+x"))
    assert ws.sent == [{"type": "clipboard", "text": "same text both times"}], (
        f"The unchanged clipboard was pushed twice — got {ws.sent!r}. This "
        f"is the same dedup that stops the immediate push and the live "
        f"listener from both sending one real PC-side copy.")


def test_text_written_on_the_phones_behalf_is_never_echoed_back() -> None:
    """Mirrors what content.paste_text does: clipboard.copy_text(text) then
    clipboard_sync.note_written(text). The live listener (simulated here by
    calling read_text + the same dedup after_copy_chord uses) must treat
    that text as already known, not as a fresh PC-side copy to push."""
    _reset()
    written = "a Claude slash command the phone sent"
    clipboard_sync.note_written(written)
    # The listener's read sees exactly what we just wrote (the natural case —
    # our own SetClipboardData is what fired WM_CLIPBOARDUPDATE).
    clipboard_sync.read_text = lambda: written
    ws = FakeWS()
    conn = {"away": None}
    # Simulate one iteration of watch()'s body without starting the real
    # Win32 listener thread — the same three calls it makes per wake-up.
    text = clipboard_sync.read_text()
    if clipboard_sync._fresh(text):
        clipboard_sync._remember(text)
        _run(clipboard_sync._push(ws, conn, text))
    assert ws.sent == [], (
        "Text written on the phone's behalf echoed straight back to it. "
        "PLANTED DEFECT: note_written not updating the shared dedup value, "
        "so the listener treats its own echo as a brand-new PC-side copy.")


CHECKS = [
    ("an injected Copy/Cut pushes the PC clipboard to the phone",
     test_injected_copy_pushes_to_the_phone),
    ("a non-Copy/Cut chord pushes nothing",
     test_a_non_copy_chord_pushes_nothing),
    ("a push while the phone is hidden is held, never dropped",
     test_a_push_while_hidden_is_held_not_dropped),
    ("only the latest pending copy survives and flushes on return",
     test_only_the_latest_pending_survives_and_flushes_on_return),
    ("the same clipboard text is never pushed twice",
     test_a_repeat_read_of_the_same_text_is_not_pushed_twice),
    ("text written on the phone's behalf is never echoed back to it",
     test_text_written_on_the_phones_behalf_is_never_echoed_back),
]


def main() -> int:
    failed = []
    print("\n=== CLIPBOARD SYNC GATE ===")
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed.append(f"{name}: {e}")
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nCLIPBOARD SYNC GATE FAILED — {len(failed)} check(s).",
              file=sys.stderr)
        return 1
    print("\nCLIPBOARD SYNC GATE PASSED — Copy/Cut reaches the phone, a "
          "hidden phone never loses a copy, and neither direction echoes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
