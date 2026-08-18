"""THE IN-APP UPDATE: from the periodic check to handing this PC over.

Split out of `gui/main_window.py` on 2026-08-18 (THE STRUCTURE LAW, VC-R3) as
a MIXIN for the same reason as its sibling: every method reaches the window's
own update button, its progress bar and its controller.

One responsibility, and it is a STATE MACHINE — `None -> found -> downloading
-> ready -> launched`, with `failed` beside it — which is exactly why it is
worth a file of its own: the button's text, its enabled state and the progress
bar are all functions of that one field, and the round that put them in three
places is why the owner spent a day testing a build published before the fix
he was testing for.
"""

import logging
import os
import tempfile
import webbrowser
from pathlib import Path

from PySide6.QtWidgets import QApplication

import update_handover
import updates
from gui import offthread

logger = logging.getLogger(__name__)

# The Update button's failure caption when nothing more specific is known —
# i.e. the download itself never finished. Named because the window's computed
# minimum has to MEASURE it (THE SPACE & LEGIBILITY LAW), alongside the three
# the handover can hand back.
UPDATE_FAILED_TEXT = "Update download failed — retry"

# What the button says in the moments between "downloaded" and the process
# actually going down (owner decree 2026-08-10, task 207): a window that
# vanishes with no explanation reads as a crash to whoever is watching it —
# plain and complete: what is happening, that we are closing, and that we
# come back. Module-level (not a class attribute) so `_computed_minimum`
# can measure it like every other caption this button can wear.
UPDATE_HANDOVER_TEXT = "Vibe Coder will close to finish updating — it comes back on its own"



class UpdateFlow:
    """The update state machine, mixed into `MainWindow`.

    `_update`, `_update_state`, `_update_error`, `_update_progress` and
    `_update_path` are the window's own attributes; they are declared in its
    `__init__` beside everything else it owns, because a mixin that quietly
    invented state on `self` would be the hardest kind of coupling to read."""

    def _check_updates(self) -> None:
        """Worker: ask GitHub whether a newer release exists. Only sets the
        attribute — the refresh timer shows the button on the UI thread.

        THIS RAN ONCE PER START UNTIL 2026-08-07, and that one word cost the
        owner more than any bug in this repo. Proven from his own machine the
        morning he lost his temper:

            installed exe 0.0.089, running since 2026-08-06 19:49:58
            v0.0.090 published                   2026-08-06 20:06

        He had been testing — and reporting as broken — a build published
        BEFORE the fix he was testing for, for a full day, because the app he
        leaves running for days had asked GitHub exactly once, seventeen
        minutes too early. Every round after that re-diagnosed a bug that was
        already fixed and released. A desktop app that only looks for its own
        update at startup is, for this owner, an app that never updates.
        """
        self._update = updates.check()
        if self._update:
            self._update_state = "found"

    def _recheck_updates(self) -> None:
        """The periodic re-check. Never disturbs an update already in flight
        (found / downloading / ready / launched) — only a state of None can
        still learn something new, and re-arming a button he is mid-way
        through installing would be its own bug."""
        if self._update_state is not None:
            return
        offthread.run(self._check_updates)

    def _install_update(self) -> None:
        upd = self._update
        if not upd or self._update_state not in ("found", "failed"):
            return
        if not upd.installer_url:
            webbrowser.open(upd.page_url)  # release without an exe asset
            return
        self._update_state = "downloading"
        self._update_error = None    # a retry re-downloads; last time's reason goes
        self._update_progress = None  # a retry starts its bar from empty, not the last try's %
        self._refresh_update_button()
        offthread.run(self._download_update, upd)

    def _download_update(self, upd) -> None:
        """Worker: fetch the installer to %TEMP%; the refresh timer launches
        it (Qt work stays on the UI thread). `updates.download` owns the
        transfer itself — chunked, socket timeout, its own four retries with
        Range resume, and (received, total) after every chunk, `total` being
        None when the response gave no Content-Length, which `_show_progress`
        reads as the indeterminate bar (task 207)."""
        def report(received: int, total: int | None) -> None:
            self._update_progress = (received, total)

        try:
            path = Path(tempfile.gettempdir()) / f"VibeCoder_Setup_v{upd.version}.exe"
            updates.download(upd.installer_url, path, on_progress=report)
        except Exception as e:
            logger.error("Update download failed: %s", e)
            # THE REASON GOES ON THE BUTTON (owner 2026-08-12): by the time
            # this runs, updates.download has already retried four times by
            # itself, so a surviving failure is worth naming. `_update_error`
            # is the handover path's own field; download simply never set it.
            self._update_error = updates.failure_reason(e)
            self._update_state = "failed"
            self._update_progress = None
            return
        self._update_path = path
        self._update_state = "ready"
        self._update_progress = None

    def _begin_handover(self) -> None:
        """The downloaded installer is on disk — hand this PC over to it.

        THE WHOLE POINT (owner report 2026-08-07): he installs from the PHONE,
        through the very session the install is about to end. *"čim uđem u
        instalaciju on će meni ugasiti Vibe Coder i više neću moći da
        komandujem odavde."* So from the tap on this button there is nothing
        left for anyone to click — [update_handover] verifies the file, tells
        the phone, arms the script that will install and restart us, and only
        then do we go. This window keeps its manual path exactly as it was
        for the case the handover cannot run unattended (a dev checkout with
        no elevation): the installer is launched visibly instead.
        """
        action, text = update_handover.begin(
            self.controller, self._update_path, self._update.version,
            self._update.size)
        if action == "stop":
            # The REASON goes on the button, and it survives the next refresh
            # tick — `_update_error`, not a setText the 1 s timer overwrites
            # one second later with "Update download failed" (which would be a
            # lie: the download finished, it was the FILE that was wrong).
            self._update_error = text
            self._update_state = "failed"
            self._refresh_update_button()
            return
        if action == "manual":
            # os.startfile = ShellExecute, which raises the UAC prompt the
            # installer's admin manifest requires — Popen/CreateProcess from
            # an unelevated app fails with WinError 740 and would wedge the
            # whole flow. "launched" only after the call succeeds.
            try:
                os.startfile(str(self._update_path))
            except OSError as e:
                logger.error("Installer launch failed: %s", e)
                self._update_error = "Update launch failed — retry"
                self._update_state = "failed"
                self._refresh_update_button()
                return
        # THE LATCH CLOSES FIRST (owner 2026-08-09, the handover fork): this
        # line used to sit BELOW processEvents(), so a pending 1 s refresh
        # tick re-entered _refresh_update_button while the state still said
        # "ready" and armed ANOTHER handover — the arming lock now refuses
        # that second arm, but the late latch was the re-entrancy ROOT, and
        # a root left standing invites the next variant.
        self._update_state = "launched"
        # SAY IT BEFORE WE GO (owner 2026-08-09: "aplikacija je pukla kad sam
        # stisnuo download — krenuo je da radi downloading a onda je izašao i
        # podigao ponovo aplikaciju; je l' to zamisao?"). It IS the intention,
        # and that is exactly why it must be announced: from his side a window
        # that vanishes mid-action is a crash, and being right about the design
        # does not make the experience honest.
        #
        # Painted with processEvents BEFORE the quit — a setText alone would
        # never reach the screen, because the very next line ends the app.
        self.update_btn.setText(UPDATE_HANDOVER_TEXT)
        self.update_btn.setEnabled(False)
        # THE BAR (owner decree 2026-08-10, task 207 — replacing the
        # 2026-08-09 placeholder marker): the actual install runs in the
        # handover SCRIPT, after this process is gone (update_handover.py) —
        # there is nothing left here to measure, so `_show_progress(None)`
        # is the honest indeterminate animation, never a frozen ellipsis
        # claiming to know a progress this window cannot see.
        self._show_progress(None)
        QApplication.processEvents()
        self._quit()  # free our files; the handover takes over from here

    def _show_progress(self, progress: tuple[int, int | None] | None) -> None:
        """Drive the bar under the update button (owner decree 2026-08-10,
        task 207 — "ne znam da li je blokirao ili radi"). `progress` is
        (received, total) with `total` possibly None, or None outright (the
        install hand-over step, which has no bytes to count at all).

        DETERMINATE — a real, advancing % — whenever a total is known;
        INDETERMINATE (Qt's own scrolling-chunk animation, engaged by
        `setRange(0, 0)`) whenever it is not. Never a value frozen mid-way
        and never a percent text pretending to know a number it does not
        have — that is exactly the "three static dots" bug this replaces.
        """
        received, total = progress if progress else (0, None)
        if total:
            self.update_progress.setRange(0, 100)
            self.update_progress.setValue(min(100, int(received * 100 / total)))
            self.update_progress.setTextVisible(True)
        else:
            self.update_progress.setRange(0, 0)
            self.update_progress.setTextVisible(False)
        self.update_progress.show()

    def _refresh_update_button(self) -> None:
        state = self._update_state
        if state in (None, "launched") or self._update is None:
            return
        if state == "ready":
            self._begin_handover()
            return
        if state == "found":
            self.update_btn.setText(f"Update to v{self._update.version} — download && install")
            self.update_btn.setEnabled(True)
            self.update_progress.hide()
        elif state == "downloading":
            self.update_btn.setText("Downloading update…")
            self.update_btn.setEnabled(False)
            self._show_progress(self._update_progress)
        elif state == "failed":
            self.update_btn.setText(self._update_error or UPDATE_FAILED_TEXT)
            self.update_btn.setEnabled(True)
            self.update_progress.hide()
        self.update_btn.show()
