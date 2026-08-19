"""THE DEVELOPER DOOR — what a stranger's fresh install shows, and the five
clicks that change it.

Owner request 2026-08-19: Traffic is his own instrument, not something the
person who installed this app ten seconds ago needs, and it is the FIRST of a
class ("i jos neke naknadne opcije"). <!-- lang-ok: owner request -->
It is therefore hidden behind DEVELOPER TOOLS, opened by clicking the window's
title five times.

Four things are held here, and every one of them is a way this kind of feature
usually goes wrong:

  1. A FRESH INSTALL SHOWS NO TRAFFIC. The default is off, and the row built
     from that default has exactly the doors a stranger needs. This is the
     whole request, and it is the check that fails if anyone adds a developer
     door without marking it one.
  2. FIVE, AND FIVE AGAIN. The gesture toggles, it needs all five inside the
     window, and clicks spread over a longer time never accumulate — a person
     who happens to click the header twice a day must never wake this.
  3. IT SURVIVES A RESTART, THROUGH THE ONE DOOR. `developer_tools` is a
     user-adjustable key like every other, so the five taps and a hand-edited
     settings.json are the same answer written the same way.
  4. THE ROW IS STILL MEASURED AGAINST ALL THREE. THE SPACE & LEGIBILITY LAW
     measures the fullest real content, not the state that happens to be on
     screen: a minimum taken from two buttons is a minimum the window outgrows
     the moment he opens the door.

Run:  .venv\\Scripts\\python -m pytest tests/test_developer_tools.py
"""

import sys
import time
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
for entry in (PROJECT / "server", PROJECT / "tests"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import config  # noqa: E402


@pytest.fixture
def dev_off(monkeypatch):
    """The default, restored afterwards whatever the test did — and HIS OWN
    settings.json never touched.

    Two process-wide things are borrowed here and both are put back, which is
    the lesson of tests/conftest.py (the day forty tests failed on a fake
    nobody restored): `SETTINGS` is ONE object every module holds, and
    `save_user_settings` writes a real file in the real %LOCALAPPDATA%. A guard
    that flipped the owner's own installation into developer mode and left it
    there would be a guard that changed the thing it was measuring.
    """
    import gui.developer_mode as developer_mode
    written = []

    def record(changes):
        written.append(dict(changes))
        config.apply(**changes)       # the live effect, none of the file I/O

    monkeypatch.setattr(developer_mode, "save_user_settings", record)
    was = config.SETTINGS.developer_tools
    config.apply(developer_tools=False)
    yield written
    config.apply(developer_tools=was)


# ═══════════════════ 1. A FRESH INSTALL ═══════════════════
def test_the_default_is_off():
    field = {f.name: f for f in __import__("dataclasses").fields(config.Settings)}
    assert field["developer_tools"].default is False, (
        "a fresh install must show the row a stranger needs — anything else "
        "makes the owner's instrument the first thing a new user meets")


def test_traffic_is_the_only_door_behind_it():
    """If a second developer door is added tomorrow this check simply names it
    too; what it refuses is a door marked developer's that everyone needs, or
    an ordinary door quietly moved behind the switch."""
    from gui.main_window import DOORS
    behind = {label for label, _, _, dev in DOORS if dev}
    open_to_all = {label for label, _, _, dev in DOORS if not dev}
    assert behind == {"Traffic"}, behind
    assert open_to_all == {"Controls", "Settings"}, open_to_all


def test_the_row_a_stranger_sees_has_no_traffic(dev_off):
    window, app = _main_window()
    try:
        assert _door_labels(window) == ["Controls", "Settings"]
    finally:
        _close(window, app)


def test_five_clicks_put_traffic_back(dev_off):
    window, app = _main_window()
    try:
        _tap_title(window, 5)
        assert config.SETTINGS.developer_tools is True
        assert dev_off == [{"developer_tools": True}], (
            "the answer must go through save_user_settings, or it dies with "
            "the process and he has to click five times again every morning")
        assert _door_labels(window) == ["Controls", "Traffic", "Settings"], (
            "Traffic must come back IN ITS OWN PLACE — a door that reappears "
            "at the end of the row is a row that moves under his finger")
        _tap_title(window, 5)
        assert config.SETTINGS.developer_tools is False
        assert _door_labels(window) == ["Controls", "Settings"]
    finally:
        _close(window, app)


# ═══════════════════ 2. THE GESTURE ═══════════════════
def test_four_clicks_are_not_five(dev_off):
    window, app = _main_window()
    try:
        _tap_title(window, 4)
        assert config.SETTINGS.developer_tools is False
    finally:
        _close(window, app)


def test_a_click_counts_once_however_it_lands(dev_off):
    """The defect a grader measured by hand on 2026-08-19: the filter was
    installed on the container AND on its three children, a QLabel propagates
    the press it ignores, and the same click was counted twice — three clicks
    opened the door, and a click on the 10 px gap between the logo and the text
    counted one while a click on the text counted two. The gesture had no
    stable "five". Every place a finger can land must count the SAME."""
    window, app = _main_window()
    try:
        from PySide6.QtWidgets import QApplication, QLabel
        targets = [window.title_area] + window.title_area.findChildren(QLabel)
        for target in targets:
            window._title_tap._taps = 0
            for _ in range(4):
                QApplication.sendEvent(target, _press())
            assert config.SETTINGS.developer_tools is False, (
                "four clicks on " + target.__class__.__name__ + " already "
                "toggled it — that click is being counted more than once")
            assert window._title_tap._taps == 4, (
                "four clicks on " + target.__class__.__name__ + " counted "
                + str(window._title_tap._taps))
    finally:
        _close(window, app)


def test_a_double_click_rhythm_counts_the_same_as_an_even_one(dev_off):
    """Qt turns the second press of a fast pair into `MouseButtonDblClick`. A
    filter that only counted presses made a person tapping in a double-click
    rhythm count fewer than one tapping evenly — the same "five that is not
    five", in its other direction."""
    window, app = _main_window()
    try:
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QApplication
        label = _title_label(window)
        for kind in (QMouseEvent.Type.MouseButtonPress,
                     QMouseEvent.Type.MouseButtonDblClick):
            window._title_tap._taps = 0
            QApplication.sendEvent(label, QMouseEvent(
                kind, QPointF(4, 4), QPointF(4, 4), Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
            assert window._title_tap._taps == 1, kind
    finally:
        _close(window, app)


def test_the_window_itself_says_how_to_turn_it_off(dev_off):
    """A tray balloon is not a promise — Focus assist, Do-not-disturb, or
    notifications turned off for this app all swallow it, and then an
    accidental ON is a mystery button with no way back. The row carries the
    sentence for as long as the state lasts, and it is the only place in the
    product the gesture is written down."""
    from gui.main_window import DEV_NOTE_TEXT
    assert "five" in DEV_NOTE_TEXT.lower() and "title" in DEV_NOTE_TEXT.lower()
    window, app = _main_window()
    try:
        assert window.dev_note.isHidden()
        _tap_title(window, 5)
        assert not window.dev_note.isHidden(), (
            "nothing in the window says how to close the door that just opened")
        _tap_title(window, 5)
        assert window.dev_note.isHidden()
    finally:
        _close(window, app)


def test_closing_the_door_closes_the_room(dev_off):
    """He turns the tools off before handing the machine to somebody else.
    Leaving the Traffic chart standing on the desktop with no door to it is
    the same defect as a chip about a window that has already closed."""
    window, app = _main_window()
    try:
        _tap_title(window, 5)
        shown = []
        window._traffic = type("FakeTraffic", (), {
            "isVisible": lambda self: True,
            "hide": lambda self: shown.append("hidden"),
        })()
        _tap_title(window, 5)
        assert shown == ["hidden"], "the Traffic window outlived its own door"
    finally:
        _close(window, app)


def test_clicks_spread_over_time_never_add_up(dev_off):
    """The window is what makes five DELIBERATE clicks different from five
    clicks over a working day. Proven by moving the counter's own clock back
    between real presses rather than by sleeping: a guard that took twenty
    seconds to say this is a guard nobody runs."""
    pytest.importorskip("PySide6.QtWidgets")
    from _audit_windows import make_app
    from gui.developer_mode import TAP_WINDOW_S, TitleTap
    make_app()
    seen = []
    tap = TitleTap(seen.append)
    for _ in range(8):
        tap._last = time.monotonic() - (TAP_WINDOW_S + 1)   # the last one was long ago
        tap.eventFilter(None, _press())
    assert not seen, "clicks separated by more than the window must not count"
    assert tap._taps == 1, "each late click must restart the count, not extend it"


def test_the_gesture_never_swallows_the_click():
    """`eventFilter` returns False always: the header is still a header, its
    text still selectable, and nothing else that watches those clicks stops
    seeing them."""
    source = (PROJECT / "server" / "gui" / "developer_mode.py").read_text(
        encoding="utf-8")
    body = source[source.index("def eventFilter"):source.index("def _toggle")]
    assert "return True" not in body, (
        "the tap counter must never consume the event it counted")


# ═══════════════════ 3. IT SURVIVES A RESTART ═══════════════════
def test_it_is_a_user_setting_like_any_other():
    assert "developer_tools" in config.USER_ADJUSTABLE
    assert config._coerced("developer_tools", True) is True
    assert config._coerced("developer_tools", "yes") is None, (
        "a settings.json with a string here must be ignored, not truthy")


# ═══════════════════ 4. THE MEASURED MINIMUM ═══════════════════
def test_the_minimum_is_measured_against_the_fullest_row(dev_off):
    """Off and on, the declared minimum is the same number — because it was
    taken from all three captions either way. If this ever differs, the window
    grew a floor that depends on a state, and the state it does not measure is
    the one that overlaps."""
    window, app = _main_window()
    try:
        closed = window._computed_minimum()
        _tap_title(window, 5)
        opened = window._computed_minimum()
        assert closed == opened, (closed, opened)
    finally:
        _close(window, app)


# ═══════════════════ the harness ═══════════════════
def _main_window():
    """The real window, offscreen and never shown on his desk (the 2026-08-06
    report: guard runs flashing windows and stealing focus)."""
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import Qt
    from _audit_windows import make_app
    import updates
    updates.check = lambda force=False: None
    from gui.main_window import MainWindow
    from types import SimpleNamespace

    app = make_app()
    controller = SimpleNamespace(state="stopped", info=None, error=None,
                                 start=lambda: None, stop=lambda: None)
    window = MainWindow(controller)
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()
    return window, app


def _close(window, app) -> None:
    window.hide()
    window.deleteLater()
    app.processEvents()


def _door_labels(window) -> list:
    box = window.window_row.layout()
    return [box.itemAt(i).widget().text().strip() for i in range(box.count())
            if box.itemAt(i).widget() is not None]


def _press():
    """One left-button press, the object Qt itself would deliver."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    return QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(4, 4),
                       QPointF(4, 4), Qt.MouseButton.LeftButton,
                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)


def _tap_title(window, times: int) -> None:
    """Real mouse presses ON THE TITLE LABEL, sent through Qt.

    The label and not the container, and that is the whole point: a QLabel
    ignores a press, so Qt propagates it up — which is how a finger reaches
    the filter, and it is the path the first version of this guard did not
    take. Sending straight to the container hid a defect a grader found by
    hand: with the filter also installed on the children, every real click
    counted TWICE and three clicks opened the door while this file said four
    were not five.
    """
    from PySide6.QtWidgets import QApplication
    for _ in range(times):
        QApplication.sendEvent(_title_label(window), _press())


def _title_label(window):
    """The words a finger actually lands on."""
    from PySide6.QtWidgets import QLabel
    for label in window.title_area.findChildren(QLabel):
        if label.text() == "Vibe Coder":
            return label
    raise AssertionError("the header no longer carries the title label")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
