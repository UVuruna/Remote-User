"""The Settings window's STREAM card — what this PC sends.

SPLIT OUT OF settings_window.py on 2026-08-12 (THE STRUCTURE LAW). The window
was 854 lines and this round grows the card rather than shrinks it: four
quality steps, a Custom disclosure and the numbers behind both. The seam is a
real responsibility and not a size trick — this module answers "what does the
PC encode", the window answers "which cards are in the column and how big must
it be"; nothing here knows about notifications, focus or startup, and the
window no longer knows a bitrate from a frame rate.

── WHY THE CARD LOOKS LIKE THIS (owner ballot 2026-08-12, option A) ─────────

It used to be four combos — Monitor, Resolution, Bitrate, Frame rate — three of
which asked him to compose a stream out of parts. His verdict picked the
DESCRIPTIVE shape: one Quality dropdown of named steps, each carrying its own
numbers in its label, so the thing he reads is the thing he gets.

  Monitor    — unchanged; it is a different question and it always was.
  Quality    — Max / High / Balanced / Data saver, each a fixed
               (frame rate, bitrate) pair with the real numbers written into
               the label. Not a slider and not three dials: the point of the
               shape is that "High — 60 fps, 12 Mbps" cannot be misread.
  Custom…    — the exact numbers, hidden until asked for. The capability was
               never removed, only the requirement to use it.

RESOLUTION LEFT THE FRONT OF THE CARD, NOT THE PRODUCT. The PC now scales to
the device's own panel, so a resolution the owner picks here is a ceiling he
should not have to think about — but `h264_max_width` is still a real setting,
still on the wire, still what the phone's own quality panel measures its steps
against (`config.stream_base`), and still editable behind Custom…. Removing the
dial and removing the capability are different acts, and only the first was
asked for.

DATA SAVER IS NOT A FOURTH SET OF NUMBERS. It is `config.DATA_SAVER`, the same
profile the phone's "save data on mobile networks" tick applies automatically
over cellular and the same one a legacy `quality {reduced:true}` maps to. His
instruction was exactly this — "just make sure you connect Data saver to mobile
data, the mechanic we already have" — so this module IMPORTS the profile rather
than restating it, and tests/test_stream_card.py asserts the step against that
one definition so the manual pick and the automatic switch can never drift.
"""

from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QPushButton, QWidget

from config import DATA_SAVER, DATA_SAVER_BITRATE, SETTINGS, bitrate_bps, save_user_settings

# The exact-number choices, behind Custom…. They are the ones this card has
# always offered; what changed is that reaching them is now deliberate.
RESOLUTIONS = [("Native (up to 4K)", 3840), ("2560 — QHD", 2560),
               ("1920 — Full HD", 1920), ("1600 — light", 1600)]
# EVERY VALUE A NAMED STEP SETS MUST BE OFFERED HERE. The step writes its
# numbers INTO these combos (`_pick_step`), and `_select` falls back to index
# 0 for a value it cannot find — so a step whose bitrate were missing from
# this list would silently set a DIFFERENT one, which is the worst kind of
# defect this card can have: the dropdown would say one thing and the encoder
# do another. Gated (`check_every_step_is_selectable`), because the two lists
# are edited in different rounds for different reasons.
BITRATES = [("1.2 Mbps — data saver", "1200k"), ("3 Mbps — light", "3M"),
            ("6 Mbps — default", "6M"), ("12 Mbps — sharp", "12M"),
            ("20 Mbps — max quality", "20M")]
FPS_CHOICES = [("10 fps — light", 10), ("20 fps", 20), ("30 fps", 30),
               ("60 fps", 60)]


def mbps_label(text: str) -> str:
    """"12M" → "12 Mbps", "1200k" → "1.2 Mbps" — the same words the phone's
    quality panel uses for the same number (client/quality.js → `mbpsLabel`).
    Computed from the stored string, never tabled: a step's label must be a
    reading of its own value, or the two go out of step the first time one
    of them is retuned."""
    mbps = bitrate_bps(text) / 1_000_000
    shown = round(mbps) if mbps >= 10 else round(mbps * 10) / 10
    return f"{shown:g} Mbps"


def _step(name: str, fps: int, bitrate: str) -> tuple[str, int, str]:
    """One quality step, with its own numbers written into its label. The
    label is BUILT from the values rather than typed beside them, so a step
    can never advertise a number it does not set — which is the entire reason
    the owner chose the descriptive shape."""
    return (f"{name} — {fps} fps, {mbps_label(bitrate)}", fps, bitrate)


# THE FIVE STEPS — A LADDER, not a list of presets (owner rejection
# 2026-08-12, and he was right about both defects in the four-step draft).
#
# DEFECT 1, AN INVERTED LADDER. The draft had High at 60 fps / 12 Mbps and
# Balanced at 30 fps / 12 Mbps — the same bitrate at half the frame rate,
# which is TWICE the bits per frame. "Balanced" would have rendered a SHARPER
# picture than "High", so the ladder contradicted its own naming. The rule
# that comes out of it, and the one the gate now enforces: going DOWN the
# list, neither axis may rise AND bits per frame may not rise either. A step
# below another must be worse in every way a person can perceive, or its name
# is a lie.
#
# DEFECT 2, A CLIFF. 12 Mbps straight to 1.2 Mbps is a factor of ten with
# nothing in between, so a link that could not hold Balanced had only the
# saving profile left. **Light** fills it, and no adjacent bitrate step is now
# more than a 2.5x drop (gated at 3x).
#
#   Step        fps   bitrate    bits/frame
#   Max          60   20 Mbps        333k
#   High         60   12 Mbps        200k
#   Balanced     30    6 Mbps        200k     <- the shipped default
#   Light        20    3 Mbps        150k
#   Data saver   10   1.2 Mbps       120k
#
# Balanced now means something that is actually TRUE of it: half the data and
# half the frames of High, at the same sharpness per frame.
#
# Frame rates and bitrates are the ones this PC really has — the same values
# the Custom combos offer, so a step is a shortcut through the exact numbers
# and never a second vocabulary. Data saver is `config.DATA_SAVER` read out,
# never a copy of it (see the module docstring).
QUALITY_STEPS = [
    _step("Max", 60, "20M"),
    _step("High", 60, "12M"),
    # Balanced is the SHIPPED DEFAULT read out (target_fps 30, h264_bitrate
    # 6M) — deliberately, so a PC nobody has configured opens this window on a
    # NAMED step instead of on the Custom entry. A step's numbers must be
    # true; a fresh install reading "Custom" would have been true and useless.
    _step("Balanced", 30, "6M"),
    _step("Light", 20, "3M"),
    _step("Data saver", DATA_SAVER["fps"], DATA_SAVER_BITRATE),
]

# The ladder's own rules, stated as numbers so the gate reads them from here
# rather than restating them (tests/test_stream_card.py). MAX_BITRATE_JUMP is
# 3.0 and the real ladder's worst step is 2.5x — the ceiling is what stops a
# future retune re-opening the cliff, not a description of today's table.
MAX_BITRATE_JUMP = 3.0

STREAM_TEXT = ("These are the PC's own limits — the phone's quality panel goes "
               "below them freely and may raise only where it says so. Data "
               "saver is the same profile a phone switches to by itself on "
               "mobile data.")
CUSTOM_TEXT = ("The exact numbers behind the steps above. Resolution is a "
               "ceiling — the PC already scales down to whatever screen is "
               "watching, so there is normally nothing to set here.")

# The label of the entry that appears when this PC's saved values match no
# step — a hand-edited settings.json, or an older release's numbers. It states
# what IS set instead of lighting a step that would be a lie.
CUSTOM_STEP = "Custom"


def step_for(fps: int, bitrate: str):
    """Which named step these numbers ARE, or None. Compared on the bitrate's
    VALUE, not its spelling: "12M" and "12000k" are the same stream, and a
    settings file written by an older build may hold either."""
    for label, step_fps, step_bitrate in QUALITY_STEPS:
        if step_fps == fps and bitrate_bps(step_bitrate) == bitrate_bps(bitrate):
            return label
    return None


class StreamCard:
    """Builds the card and owns its widgets. A small object rather than loose
    functions because the card has state — which step is showing, whether
    Custom is open — and the window should not have to hold it."""

    def __init__(self, window, populate_monitors, restart):
        self.window = window
        self._populate_monitors = populate_monitors
        self._restart = restart

    def build(self):
        window = self.window
        frame, box = window.card()
        window.section(box, "STREAM")

        form = window.form()
        self.monitor_combo = QComboBox()
        self._populate_monitors(self.monitor_combo)
        window.row(form, "Monitor", self.monitor_combo)

        self.quality_combo = QComboBox()
        self.quality_combo.currentIndexChanged.connect(self._pick_step)
        window.row(form, "Quality", self.quality_combo)
        box.addLayout(form)
        window.caption(box, STREAM_TEXT)

        # CUSTOM — a disclosure, not a second card. The tick is the door and
        # the fields below it are the room; both live in this card because
        # they are the same setting seen at two levels of detail, and a
        # separate card would have implied a separate decision.
        self.custom_check = QCheckBox("Custom…")
        self.custom_check.toggled.connect(self._show_custom)
        box.addWidget(self.custom_check)

        # THE THREE EXACT COMBOS SHARE ONE ROW, and that is ladder step 2
        # (REFLOW), not decoration: this window's scarce axis is HEIGHT — it
        # already spends most of the 1000 px the project's layout frame allows
        # — while it has width to spare, so a disclosure that added three
        # labelled rows would have bought its detail out of the only budget
        # that binds. It is also the pattern this very card's neighbour used
        # for the same reason until 2026-08-12 (the phone's theme trio).
        #
        # No sub-labels are needed and none are invented: every entry names its
        # own unit — "2560 — QHD", "12 Mbps — default", "30 fps" — so the row
        # reads without a legend. A combo whose entries were bare numbers would
        # have needed the three rows and been worth them.
        self.custom_box = QWidget()
        # Furniture, not a surface — see gui/theme.py `QWidget#group`.
        self.custom_box.setObjectName("group")
        custom_form = window.form()
        custom_form.setContentsMargins(0, 0, 0, 0)
        self.resolution_combo = QComboBox()
        for label, value in RESOLUTIONS:
            self.resolution_combo.addItem(label, value)
        self.bitrate_combo = QComboBox()
        for label, value in BITRATES:
            self.bitrate_combo.addItem(label, value)
        self.fps_combo = QComboBox()
        for label, value in FPS_CHOICES:
            self.fps_combo.addItem(label, value)
        for combo in (self.bitrate_combo, self.fps_combo):
            combo.currentIndexChanged.connect(self._exact_changed)
        trio = QWidget()
        trio.setObjectName("group")
        trio_row = QHBoxLayout(trio)
        trio_row.setContentsMargins(0, 0, 0, 0)
        trio_row.setSpacing(8)
        trio_row.addWidget(self.resolution_combo, 1)
        trio_row.addWidget(self.bitrate_combo, 1)
        trio_row.addWidget(self.fps_combo, 1)
        window.row(custom_form, "Exact", trio)
        self.custom_box.setLayout(custom_form)
        box.addWidget(self.custom_box)
        self.custom_caption = window.caption(box, CUSTOM_TEXT)

        self.select_current()
        self._show_custom(False)

        apply_row = QHBoxLayout()
        apply_row.addStretch()
        self.apply_btn = QPushButton("Apply && restart")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.clicked.connect(self.apply)
        apply_row.addWidget(self.apply_btn)
        box.addLayout(apply_row)
        return frame

    def settle(self) -> None:
        """Pin the three Exact combos to the width their own entries need —
        ON FIRST SHOW, never in `build`.

        Two reasons, and the second is the one that bites. A QComboBox's
        MINIMUM size hint is far smaller than its size hint, so three of them
        sharing a row are squeezed to a third of whatever the row happens to
        have and the longest entry is clipped — the audit measured exactly
        that the first time this row was written ("has 175x34, needs at least
        181x34"). And the hint is only correct once Qt has POLISHED the widget:
        the theme reaches this dialog through its parent's stylesheet, so a
        width read in the constructor is read in the wrong font and comes out
        roughly a tenth short — the lesson `_align_label_column` already
        carries in this window, and the reason both run from the same show.

        They are pinned to the WIDEST of the three, because the row gives all
        three the same width anyway; a per-combo floor would just be the same
        number written three times, arrived at by a longer route.
        """
        combos = (self.resolution_combo, self.bitrate_combo, self.fps_combo)
        width = max(combo.sizeHint().width() for combo in combos)
        for combo in combos:
            combo.setMinimumWidth(width)

    # -- state -------------------------------------------------------------

    def _select(self, combo: QComboBox, value) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def select_current(self) -> None:
        """Read the live settings into every widget. The exact combos are the
        model — the Quality dropdown is a VIEW of them — so they are filled
        first and the step is derived, never the other way round."""
        self._select(self.monitor_combo, SETTINGS.monitor_index)
        self._select(self.resolution_combo, SETTINGS.h264_max_width)
        self._select(self.bitrate_combo, SETTINGS.h264_bitrate)
        self._select(self.fps_combo, SETTINGS.target_fps)
        self._refresh_steps()

    def _refresh_steps(self) -> None:
        """Rebuild the dropdown so the entry it shows is always true of the
        numbers underneath. A PC whose values match no step gets a Custom
        entry that SAYS those numbers — a step lit under different numbers
        would be the exact lie this shape was chosen to prevent."""
        fps = self.fps_combo.currentData()
        bitrate = self.bitrate_combo.currentData()
        match = step_for(fps, bitrate)
        self.quality_combo.blockSignals(True)
        self.quality_combo.clear()
        for label, step_fps, step_bitrate in QUALITY_STEPS:
            self.quality_combo.addItem(label, (step_fps, step_bitrate))
        if match is None:
            self.quality_combo.addItem(
                f"{CUSTOM_STEP} — {fps} fps, {mbps_label(bitrate)}", None)
        index = self.quality_combo.findText(match) if match else \
            self.quality_combo.count() - 1
        self.quality_combo.setCurrentIndex(max(0, index))
        self.quality_combo.blockSignals(False)

    def _pick_step(self) -> None:
        """A named step writes its numbers into the exact combos, so Custom…
        opens onto what the step actually chose rather than onto whatever was
        there before it."""
        data = self.quality_combo.currentData()
        if not data:
            return   # the Custom entry describes the fields; it does not set them
        fps, bitrate = data
        for combo, value in ((self.fps_combo, fps), (self.bitrate_combo, bitrate)):
            combo.blockSignals(True)
            self._select(combo, value)
            combo.blockSignals(False)

    def _exact_changed(self) -> None:
        self._refresh_steps()

    def _show_custom(self, on: bool) -> None:
        self.custom_box.setVisible(bool(on))
        self.custom_caption.setVisible(bool(on))
        self.window.resettle()

    # -- saving -------------------------------------------------------------

    def apply(self) -> None:
        """ONE save path, exactly as before. The step and the Custom fields are
        two views of the same four values, so there is nothing here to branch
        on — which is why picking a step writes the fields instead of writing
        settings of its own."""
        save_user_settings({
            "monitor_index": self.monitor_combo.currentData(),
            "h264_max_width": self.resolution_combo.currentData(),
            "h264_bitrate": self.bitrate_combo.currentData(),
            "target_fps": self.fps_combo.currentData(),
        })
        self._restart()
