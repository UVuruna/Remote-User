"""Gate: the update flow gives HONEST, LIVE feedback — never a frozen ellipsis.

The owner's report, 2026-08-10:

    *"downloading 3 tačke koji nema nikakav response ... ne znam ... da li je
    blokirao ili radi ... napravi bar koji se učitava dok se ne završi
    loading i onda isto tako napravi Bar installing ili ako moraš da zatvoriš
    aplikaciju obavesti korisnika šta se dešava"*                # lang-ok: owner quote

Translated: a filling progress bar for the download — real % where the HTTP
response gives a length, an indeterminate animated bar where it does not,
never a frozen ellipsis — the same for the install step, and an EXPLICIT
"closing to finish updating" message before the app goes, never a silent
disappearance.

Three things must hold, and this file proves each with a defect it would
catch if the fix regressed:

  1. `updates.download()` reports a REAL, ADVANCING percentage when the
     response carries a Content-Length. A download that forgot to call
     `on_progress` at all — the shape of the original bug, just moved one
     layer down — leaves the report list too short or non-advancing, and
     this check goes red on either.
  2. `updates.download()` never FABRICATES a total when the response gives
     none. Inventing one from `len(body)` (the obvious, wrong shortcut) would
     make the phone/desktop show a percentage that is tracking nothing —
     `total` must stay `None` end to end, which is the caller's own signal to
     fall back to the indeterminate bar.
  3. `MainWindow` drives its `QProgressBar` off exactly that contract
     (determinate with `total`, indeterminate without), and the explicit
     closing message plus an indeterminate bar are on screen BEFORE the
     process quits — proven by capturing the button's text and the bar's
     visibility from INSIDE the stubbed `_quit()`, so a regression that
     re-ordered "quit" ahead of "say so" (exactly the silent-disappearance
     bug this task exists to end) is caught by what the button says the
     instant this app goes down, not by what it says a tick later that never
     comes.

Run:  .venv\\Scripts\\python tests/test_update_progress.py
"""

import os
import sys
import tempfile
import urllib.request
from pathlib import Path
from types import SimpleNamespace

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import updates  # noqa: E402


# ═══════════════════ 1 & 2: updates.download() — the byte contract ═════════
class _FakeResponse:
    """Just enough of what `urllib.request.urlopen` hands back — `headers`,
    `read`, the context-manager protocol — for `updates.download` to run
    completely unmodified, in small chunks so more than one progress report
    is guaranteed."""

    def __init__(self, body: bytes, content_length: str | None, chunk: int = 6):
        self._body = body
        self._pos = 0
        self._chunk = chunk
        self.headers = {"Content-Length": content_length} if content_length else {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, n: int) -> bytes:
        n = min(n, self._chunk)
        out = self._body[self._pos:self._pos + n]
        self._pos += len(out)
        return out


def _run_download(work: Path, body: bytes, content_length: str | None):
    calls: list[tuple[int, int | None]] = []
    real_urlopen = urllib.request.urlopen
    urllib.request.urlopen = lambda *a, **k: _FakeResponse(body, content_length)
    try:
        dest = work / "asset.bin"
        updates.download("http://fake/asset", dest,
                         on_progress=lambda r, t: calls.append((r, t)))
        return dest, calls
    finally:
        urllib.request.urlopen = real_urlopen


def check_percent_advances_with_content_length() -> tuple[bool, str]:
    body = b"X" * 41   # not a multiple of the chunk size — an uneven tail
    with tempfile.TemporaryDirectory() as d:
        dest, calls = _run_download(Path(d), body, str(len(body)))
        landed = dest.read_bytes()
    if len(calls) < 3:
        return False, f"too few progress reports to call this 'advancing': {calls}"
    totals = {t for _, t in calls}
    if totals != {len(body)}:
        return False, f"the reported total drifted or was lost: {totals}"
    received = [r for r, _ in calls]
    if received != sorted(received):
        return False, f"received bytes went BACKWARDS: {received}"
    if received[0] != 0 or received[-1] != len(body):
        return False, f"progress did not span 0..total: {received}"
    if len(set(received)) < 3:
        return False, f"the number never actually ADVANCES — a frozen bar: {received}"
    if landed != body:
        return False, "the downloaded bytes do not match the source"
    return True, ""


def check_indeterminate_fallback_with_no_content_length() -> tuple[bool, str]:
    body = b"Y" * 41
    with tempfile.TemporaryDirectory() as d:
        dest, calls = _run_download(Path(d), body, None)
        landed = dest.read_bytes()
    if not calls:
        return False, "no progress reports at all — a frozen bar either way"
    totals = {t for _, t in calls}
    if totals != {None}:
        return False, (f"a total was FABRICATED with no Content-Length in the "
                       f"response: {totals} — this is a percentage tracking nothing")
    if landed != body:
        return False, "the downloaded bytes do not match the source"
    return True, ""


# ═══════════════════ 3: MainWindow drives the bar + says so first ══════════
def _make_window():
    from gui.main_window import MainWindow
    updates.check = lambda force=False: None   # no real GitHub call from __init__
    stopped = SimpleNamespace(state="stopped", info=None, error=None,
                              start=lambda: None, stop=lambda: None,
                              release_windows=lambda: None)
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    if QApplication.instance() is None:
        QApplication([])
    window = MainWindow(stopped)
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()
    return window


def check_download_bar_is_determinate_with_a_total() -> tuple[bool, str]:
    """PLANTS: a `_show_progress` that always calls `setRange(0, 0)` (the
    original indeterminate-only shape) would leave `maximum()` at 0 here —
    exactly the "no real % ever shown" defect."""
    window = _make_window()
    try:
        window._update = SimpleNamespace(version="9.9.999",
                                         installer_url="http://x/y.exe", page_url="http://x")
        window._update_state = "downloading"
        window._update_progress = (50, 200)
        window._refresh_update_button()
        if window.update_progress.isHidden():
            return False, "the bar is hidden while a download with a known size runs"
        if window.update_progress.maximum() != 100:
            return False, f"not determinate: range is 0..{window.update_progress.maximum()}"
        if window.update_progress.value() != 25:
            return False, f"the % is wrong: got {window.update_progress.value()}, want 25"
        return True, ""
    finally:
        window.close()


def check_download_bar_is_indeterminate_without_a_total() -> tuple[bool, str]:
    """PLANTS: a `_show_progress` that fabricates a total (e.g. from bytes
    received so far) would show a determinate, moving-target bar here instead
    of the honest indeterminate animation — caught by `maximum() != 0`."""
    window = _make_window()
    try:
        window._update = SimpleNamespace(version="9.9.999",
                                         installer_url="http://x/y.exe", page_url="http://x")
        window._update_state = "downloading"
        window._update_progress = (50, None)
        window._refresh_update_button()
        if window.update_progress.isHidden():
            return False, "the bar is hidden while a download with no length runs"
        if window.update_progress.maximum() != 0 or window.update_progress.minimum() != 0:
            return False, (f"not indeterminate: range is "
                           f"{window.update_progress.minimum()}.."
                           f"{window.update_progress.maximum()}")
        return True, ""
    finally:
        window.close()


def check_closing_message_and_bar_are_shown_before_quit() -> tuple[bool, str]:
    """The gate for the owner's actual complaint: a window that vanishes with
    no explanation reads as a crash. Captures the button's text and the bar's
    visibility from INSIDE the stubbed `_quit()` — the one place that proves
    the ORDER, not just that both eventually happened."""
    import update_handover
    from gui.main_window import UPDATE_HANDOVER_TEXT
    window = _make_window()
    real_begin = update_handover.begin
    captured: dict = {}
    try:
        update_handover.begin = lambda *a, **k: ("quit", "")
        window._update = SimpleNamespace(version="9.9.999",
                                         installer_url="http://x/y.exe", page_url="http://x",
                                         size=12345)
        window._update_path = Path("does-not-matter.exe")
        window._update_state = "ready"

        def fake_quit():
            captured["text"] = window.update_btn.text()
            captured["progress_shown"] = not window.update_progress.isHidden()
            captured["indeterminate"] = window.update_progress.maximum() == 0
            captured["quit_called"] = True

        window._quit = fake_quit
        window._refresh_update_button()   # routes "ready" -> _begin_handover()

        if not captured.get("quit_called"):
            return False, "the app never reached the quit step at all"
        if captured.get("text") != UPDATE_HANDOVER_TEXT:
            return (False, f"the closing message was not on screen before quit: "
                           f"{captured.get('text')!r}")
        if not captured.get("progress_shown"):
            return False, "no bar was visible before quit — a silent disappearance"
        if not captured.get("indeterminate"):
            return False, "the install step claimed a % it cannot possibly know"
        return True, ""
    finally:
        update_handover.begin = real_begin
        window.close()


CHECKS = [
    ("download % advances with a real Content-Length",
     check_percent_advances_with_content_length),
    ("no total is fabricated without a Content-Length",
     check_indeterminate_fallback_with_no_content_length),
    ("the desktop bar is determinate once a total is known",
     check_download_bar_is_determinate_with_a_total),
    ("the desktop bar falls back to indeterminate without one",
     check_download_bar_is_indeterminate_without_a_total),
    ("the closing message + bar are shown BEFORE the app quits",
     check_closing_message_and_bar_are_shown_before_quit),
]


def main() -> int:
    print("\n=== UPDATE PROGRESS GATE (task 207) ===")
    failed = []
    for name, check in CHECKS:
        ok, reason = check()
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f" — {reason}" if not ok else ""))
        if not ok:
            failed.append(name)
    if failed:
        print(f"\nUPDATE PROGRESS GATE FAILED — {len(failed)} check(s).",
              file=sys.stderr)
        return 1
    print("\nUPDATE PROGRESS GATE PASSED — a real % while it can be known, an "
          "honest indeterminate bar while it cannot, and the app says it is "
          "closing before it ever does.")
    return 0


def test_update_progress():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
