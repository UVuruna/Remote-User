"""The ONE-TIME 4K@60 freeze offer (task 226, owner ballot verdict).

Split out of main_window.py the same day it was written (THE STRUCTURE LAW —
the file crossed 1000 lines the moment this banner landed in it): a
self-contained widget builder belongs in its own module the way `switch.py`
and `traffic_window.py` already do, not folded into the window that happens
to host it.

The freeze recipe (task 151, `config.h264_max_width`'s own docstring): a
saved capture width of 3840 (native) at 60 fps floods the pipeline with
0.75 GB/s of raw pixels per client — the log's own frozen, negative `behind`
counter. Offered exactly once, at start, only when BOTH halves of the recipe
are true right now; either answer — Switch or Keep 4K — is remembered in
`SETTINGS.offered_2560` and the offer never returns, because a banner that
keeps asking after "no" is the nagging the owner has banned everywhere else
in this product.

NEVER a modal dialog (his standing rule for in-app guidance): a bar in the
window's own column, dismissed by an answer — his values are never changed
without a choice he made.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from config import SETTINGS, save_user_settings


def build_freeze_offer_banner(window) -> QWidget | None:
    """`window` needs one method: `restart_server()` — the same worker the
    Settings window's own Apply & restart uses, so Switch reaches the
    encoder through the identical path a manual change would.
    """
    if SETTINGS.offered_2560:
        return None
    if not (SETTINGS.h264_max_width >= 3840 and SETTINGS.target_fps >= 60):
        return None

    frame = QFrame()
    frame.setObjectName("freezeOffer")
    row = QHBoxLayout(frame)
    row.setContentsMargins(12, 10, 12, 10)
    row.setSpacing(10)

    label = QLabel("4K at 60 fps can freeze the stream — switch to 2560?")
    label.setWordWrap(True)
    row.addWidget(label, 1)

    switch_btn = QPushButton("Switch")
    switch_btn.setObjectName("primary")
    keep_btn = QPushButton("Keep 4K")
    row.addWidget(switch_btn)
    row.addWidget(keep_btn)

    def answer(switch: bool) -> None:
        changes = {"offered_2560": True}
        if switch:
            # THE SAME PATH Settings Apply uses — never a hand-edited json,
            # and a restart because h264_max_width reshapes the encoder
            # exactly like the Stream card's own Apply & restart.
            changes["h264_max_width"] = 2560
        save_user_settings(changes)
        frame.setParent(None)
        frame.deleteLater()
        if switch:
            window.restart_server()

    switch_btn.clicked.connect(lambda: answer(True))
    keep_btn.clicked.connect(lambda: answer(False))
    return frame
