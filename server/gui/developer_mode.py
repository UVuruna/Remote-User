"""DEVELOPER TOOLS — the doors that are not for the person who just wants to
use the app, and the five taps that open them.

Owner request 2026-08-19: *"Kada se ukljuci Developer Tools ova, Traffic i jos
neke naknadne opcije ce se pojaviti. Kao button u osnovnom meniju gde je
controls, settings, traffic (sada uvek vidljiv). developer tools se otvara tako
sto se 5 puta klikne na Vibe Coder Title."*  <!-- lang-ok: owner request -->

WHY THIS IS ITS OWN FILE AND NOT A FLAG IN THE WINDOW. He said "and some other
later options" — so this is not one button, it is a CLASS of button, and the
first one of a class gets a registry rather than an `if` (THE ONE KIND, ONE
CLASS law). `main_window.DOORS` names which of the row's buttons are ordinary
and which are developer's; everything else about the mechanism lives here.

WHY FIVE TAPS ON THE TITLE, and not a checkbox in Settings. The thing being
hidden is hidden from the person who does not know it exists, which is exactly
who a checkbox would show it to. The gesture is Android's own (tap the build
number seven times) and it is the one convention a user of this app already
has. It TOGGLES: five taps again, and the row is back to what a stranger sees.

WHAT IT IS NOT. It is not a lock and it is not a secret — the value sits in
plain text in the user's settings.json, and anyone who edits that file gets the
same result. It hides clutter; it does not guard anything, and nothing behind
it may ever be something that would be unsafe in a stranger's hands.
"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QEvent, QObject, Qt

from config import SETTINGS, apply as apply_settings, save_user_settings

logger = logging.getLogger(__name__)

# Five, because that is what he asked for. The window is what makes five
# DELIBERATE taps different from five clicks spread over a working day: a
# person who lands on the title now and then must never wake this by accident.
TAPS_TO_TOGGLE = 5
TAP_WINDOW_S = 3.0

ON_TEXT = ("Developer tools are ON — Traffic is back on the row. "
           "Click the title five times again to hide it.")
OFF_TEXT = ("Developer tools are OFF — the row is what a new user sees. "
            "Click the title five times to bring them back.")


def is_on() -> bool:
    """Whether the developer doors are shown. Read from the live settings, so
    a hand-edited settings.json and a five-tap answer are the same answer."""
    return bool(getattr(SETTINGS, "developer_tools", False))


class TitleTap(QObject):
    """Counts clicks on whatever widget it is installed over, and calls back
    when the count reaches five inside the window.

    An event FILTER and not a QPushButton: the header is a logo and two lines
    of text, and turning it into a button would tell every user there is
    something here to press — which is the one thing this must not do. Nothing
    about the widget changes; it simply also counts.

    INSTALL IT ON ONE WIDGET — THE CONTAINER — AND NOTHING ELSE. This was
    wrong for the first hour of its life and a grader measured it: with the
    filter also on the logo and the two labels, a QLabel (which ignores a
    press) let the SAME press propagate up to the container, where the same
    filter counted it a second time. Every click on text or logo counted two,
    THREE clicks opened the door, and a click landing on the 10 px gap between
    the logo and the text counted one — so the gesture had no stable "five" at
    all. Propagation is exactly why one install is enough: a press anywhere on
    the header arrives here, once.

    A DOUBLE-CLICK IS TWO CLICKS. Qt turns the second press of a fast pair
    into `MouseButtonDblClick`, so counting presses alone made a person tapping
    in a double-click rhythm count fewer than one tapping evenly — the same
    "five that is not five" in its other direction.
    """

    TAPPED = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick)

    def __init__(self, on_toggle) -> None:
        super().__init__()
        self._on_toggle = on_toggle
        self._taps = 0
        self._last = 0.0

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt's name)
        if event.type() not in self.TAPPED:
            return False
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        now = time.monotonic()
        self._taps = self._taps + 1 if (now - self._last) <= TAP_WINDOW_S else 1
        self._last = now
        if self._taps >= TAPS_TO_TOGGLE:
            self._taps = 0
            self._toggle()
        return False        # never swallow the click — the header still works

    def _toggle(self) -> None:
        wanted = not is_on()
        try:
            save_user_settings({"developer_tools": wanted})
        except OSError as error:
            # A settings file that cannot be written is not a reason to lie
            # about what the row is showing: the row still follows the live
            # value, and the log says the choice did not survive the restart.
            #
            # OSError ONLY. `save_user_settings` also raises ValueError for a
            # key that is not user-adjustable, and that is a programming
            # mistake — a future developer door whose flag nobody registered in
            # config.USER_ADJUSTABLE. Swallowing it would hide the bug and
            # leave a switch that silently forgets.
            logger.error("developer_tools could not be saved: %s", error)
            apply_settings(developer_tools=wanted)   # the frozen instance's own door
        logger.info("Developer tools %s", "ON" if wanted else "OFF")
        self._on_toggle(wanted)
