"""The server as a component: build once, start/stop from any thread.

Shared by both entry points — `main.py` (CLI, blocking on the main thread) and
the desktop GUI (background thread, controlled by buttons). Owns everything
`main.py` used to wire inline: stream-mode decision (H.264 vs JPEG), injector,
pairing info, uvicorn lifecycle, teardown.

The process must already be per-monitor DPI aware BEFORE this module is
imported (both entry points declare it first) — capture and injection break
silently otherwise.
"""

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field

import uvicorn

import config
import display_watch
import encoders
import focus_hook
import foreground_lock
import layout_popup
import log_shipper
import log_summary
import notify
import recents
import monitors
import pairing
import session_log
import traffic
import update_handover
import window_manager
from config import SETTINGS
from session_log import LOG
from input_injector import InputInjector
from web import FrameHub, ServerStats, create_app

logger = logging.getLogger(__name__)


@dataclass
class ServerInfo:
    """Everything the GUI shows about a running server."""
    mode: str                 # "h264" | "jpeg"
    encoder: str | None       # e.g. "h264_nvenc"; None in JPEG mode
    monitor_width: int
    monitor_height: int
    port: int
    token: str
    qr_url: str               # preferred address (Tailscale when present)
    lan_url: str
    tailscale_ip: str | None
    stats: ServerStats = field(default_factory=ServerStats)


class ServerController:
    """start()/stop() the whole server stack. One instance per process.

    States: "stopped" → "starting" → "running" → "stopped", or "failed"
    (with .error set). The GUI polls state/info; the CLI uses run_blocking().
    """

    def __init__(self, console_pairing: bool = False):
        self._console_pairing = console_pairing
        self._thread: threading.Thread | None = None
        self._uvicorn: uvicorn.Server | None = None
        # The server's own event loop, published so code on OTHER threads can
        # reach a connected phone. Exactly one caller today: the update
        # handover's last message before this process exits (the Qt thread has
        # no other way to speak to a WebSocket).
        self.loop: asyncio.AbstractEventLoop | None = None
        self.state = "stopped"
        self.error: str | None = None
        # Bumped by every start(); see start() for why a run must be able to
        # recognise that it is no longer the live one.
        self._generation = 0
        self.info: ServerInfo | None = None
        # THE USE LOG (owner request 2026-08-16). Its file belongs to the
        # PROCESS, not to a server run — `session_log.py`'s own ruling — so the
        # controller owns it here rather than any one `_serve`. `_log_lock`
        # makes closing IDEMPOTENT across the four ways out (tray Quit, Qt
        # aboutToQuit, atexit, the console handler): all four reach
        # `release_windows()`, and four exits must not footer one file four
        # times.
        self._log_lock = threading.Lock()
        self._display_watch: display_watch.DisplayWatch | None = None
        # One registry for the PROCESS, not per server run: "Apply & restart"
        # used to build a fresh empty one, which threw away the owner's
        # layouts and the only list of windows still standing always-on-top.
        self.layouts = window_manager.LayoutRegistry()
        # Whatever a previous run was killed holding, put right before we can
        # possibly raise anything of our own — the always-on-top band, and
        # (round R2) Windows' foreground lock, which is the same discipline
        # applied to a machine-wide setting.
        window_manager.repair_stranded()
        foreground_lock.repair_stranded()
        # …and the same discipline for the one thing a previous run may have
        # ended ON PURPOSE: an update handover. If this process is the app the
        # installer put here, the phone is told so on its next connection —
        # and if the install did NOT take, it is told that instead, because a
        # man testing a build he never installed is the most expensive silence
        # this project has had (owner 2026-08-07).
        update_handover.announce()
        # …and only THEN take it, if the owner's switch says so. Applied here
        # rather than in the window, because both entry points build a
        # controller and the headless CLI is entitled to the same setting.
        # Releasing it is NOT part of release_windows(): that runs on every
        # server stop (Apply & restart), and this lock belongs to the PROCESS
        # — the entry points release it on the way out (gui_main.py, main.py).
        if SETTINGS.foreground_lock:
            foreground_lock.apply(True)

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Non-blocking: spawns the server thread. No-op when already up."""
        if self._thread and self._thread.is_alive():
            return
        self.state = "starting"
        self.error = None
        # Every run carries its own number, and only the CURRENT run may
        # touch shared state. stop() gives up after `timeout` and clears
        # `_thread`, so a run that outlives its own stop is not merely
        # possible — his log has it: a stop at 19:15:04 whose thread only
        # unwound at 19:15:52, 38 seconds AFTER the next run was already
        # serving. Unguarded, that ghost's own teardown wrote
        # state="stopped" over a running server (the GUI's STOPPED pill
        # under a live phone), released the live layout's topmost windows
        # and shut the live encoder down. A generation is the only thing
        # that can tell the two runs apart from inside the thread.
        self._generation += 1
        gen = self._generation
        self._thread = threading.Thread(target=self._run, args=(gen,),
                                        name=f"server-core-{gen}", daemon=True)
        self._thread.start()

    # -- the displays ------------------------------------------------------

    @property
    def display_watch(self) -> display_watch.DisplayWatch:
        """The process's ONE display watch, created on first ask.

        A property and not a `_serve` local because two of its consumers are
        not the server: the Settings window subscribes while it is open (its
        monitor list is otherwise filled once, from an enumeration dxcam made
        at import — constraint 30), and capture re-enumerates DXGI on it. It
        is created before the server runs so a Settings window opened against
        a STOPPED server still has something to subscribe to; `start()` and
        `stop()` are both idempotent, so asking for it costs nothing.
        """
        if self._display_watch is None:
            self._display_watch = display_watch.DisplayWatch()
        return self._display_watch

    # -- the use log -------------------------------------------------------

    def _start_use_log(self, info: "ServerInfo") -> None:
        """Repair, sweep, THEN open — and the order is load-bearing.

        A run that ended without us leaves a file with no footer, and that
        missing footer is the ONLY way the next start can recognise it
        (`session_log.is_unclosed`). Both the repair and the shipper's sweep
        therefore have to finish BEFORE a new file exists, or the sweep would
        pick up the file we just opened and ship a log that is still being
        written. `skip=` is belt and braces on top of the ordering: at this
        point `LOG.path` is None anyway, so nothing can match it — but a later
        edit that moved `LOG.start()` up would otherwise fail SILENTLY, and
        this feature exists precisely for failures nothing reports.

        The header carries ONLY what cannot change while this process lives.
        No monitors, no encoder, no quality — those are facts WITH A DURATION
        and go through `LOG.state()`, which writes them again whenever they
        move. A header claiming "the PC is X" is `Layout.arranged_ratio`
        (constraint 13) in a new place: a note of what was once true, read
        forever after as if it still were.
        """
        try:
            session_log.repair_unclosed(SETTINGS, log_shipper.SHIPPER,
                                        skip=LOG.path)
            log_shipper.SHIPPER.sweep(SETTINGS)
        except Exception:  # a use log may never break the app it observes
            logger.exception("Use log: the start-up repair/sweep failed")
        try:
            LOG.start(
                app_version=config.app_version(),
                install_id=log_shipper.install_id(),
                process_start=time.time(),
            )
            # The first observable facts, as STATE and never as header: what
            # this PC's displays are right now, and what this run decided to
            # be. `display_watch.snapshot()` is read fresh (constraint 13) and
            # every later change re-writes it through `_on_display_change`.
            LOG.state("pc", monitors=[
                {"index": d.index, "w": d.width, "h": d.height,
                 "primary": d.primary, "scale_pct": d.scale_pct}
                for d in display_watch.snapshot()])
            # Elevation and the bundled ffmpeg's version are deliberately NOT
            # here: neither is readable at this point without inventing a
            # probe, and a guessed value in an evidence log is worse than a
            # missing one.
            LOG.state("app", mode=info.mode, encoder=info.encoder,
                      monitor_w=info.monitor_width,
                      monitor_h=info.monitor_height)
        except Exception:
            logger.exception("Use log: could not be opened")

    def _on_display_change(self, diff) -> None:
        """The displays moved: write the new truth, never a delta. `state()`
        dedupes by itself, so an event that changed nothing observable costs
        the file nothing."""
        try:
            LOG.state("pc", monitors=[
                {"index": d.index, "w": d.width, "h": d.height,
                 "primary": d.primary, "scale_pct": d.scale_pct}
                for d in diff.snapshot])
        except Exception:
            logger.exception("Use log: recording a display change failed")

    def close_use_log(self, reason: str = "stop") -> None:
        """Footer the file, summarise it, and hand BOTH to the shipper.

        IDEMPOTENT by construction and by lock: `LOG.close()` returns None
        when nothing is open, so the four exit paths that all reach
        `release_windows()` cannot footer one file four times."""
        with self._log_lock:
            try:
                path = LOG.close(reason)
            except Exception:
                logger.exception("Use log: closing failed")
                return
            if path is None:
                return
            try:
                summary = log_summary.write_summary(path)
            except Exception:
                logger.exception("Use log: could not summarise %s", path)
                summary = None
            # `LOG.close` already offered the log itself to its own shipper;
            # offering both here is what makes the SUMMARY travel with it, and
            # `offer()` on an already-shipped file is a no-op by design.
            for item in (path, summary):
                if item is not None:
                    try:
                        log_shipper.SHIPPER.offer(item)
                    except Exception:
                        logger.exception("Use log: could not ship %s", item)

    def release_windows(self) -> None:
        """THE exit call: hand every window we raised back to the normal
        z-band and stop the foreground-hook thread, NOW, on the calling
        thread. Deliberately not part of the async teardown: dropping the
        topmost band is a handful of SetWindowPos calls that need no event
        loop, and the event loop is exactly what may be busy placing a 2x2
        layout when the owner hits Quit. Called before every stop, and again
        from the process-exit hooks — it is idempotent.

        Every documented way out of this process funnels here: tray Quit,
        server stop, Apply & restart, Ctrl+C, a console close, Qt's
        aboutToQuit, `atexit`. Which is why the Win32 resources that must not
        outlive us are released HERE and nowhere else."""
        try:
            window_manager.release_all()
        except Exception:  # nothing on the way out may raise
            logger.exception("Releasing the always-on-top windows failed")
        try:
            focus_hook.stop()
        except Exception:
            logger.exception("Stopping the foreground-hook listener failed")
        # The endless /notices responses end here too (task 234): force_exit
        # stops the loop from accepting work, but a generator parked on its
        # queue is an open connection the shutdown drain still waits on — it
        # cost every Apply & restart the full join timeout and abandoned the
        # old thread. Sits in this funnel because every documented way out
        # already runs it, idempotently.
        try:
            notify.close_channels()
        except Exception:
            logger.exception("Ending the notice channels failed")
        # The display watch is a thread (or a set of Qt connections) of ours,
        # so it goes out the same funnel every other Win32 resource does. The
        # OBJECT is kept (the Settings window may still be holding it, and a
        # next start re-subscribes to the same one); only its event source is
        # released. Honest limit, stated where it bites: `stop()` clears EVERY
        # subscriber by its own contract, so a Settings window open across a
        # server stop stops being repopulated until it is reopened — which is
        # exactly the behaviour it had before this wiring existed.
        # Defensive: this funnel runs on paths where self may be incomplete
        # (e.g. called unbound during tests, or from process-exit handlers where
        # __init__ may not have finished). Use getattr to tolerate a missing
        # attribute.
        watch = getattr(self, "_display_watch", None)
        if watch is not None:
            try:
                watch.unsubscribe(self._on_display_change)
                watch.stop()
            except Exception:
                logger.exception("Stopping the display watch failed")
        # LAST of the funnel: the footer is the file's own record that we got
        # to run code on the way out, so everything above has already happened
        # by the time it is written. Idempotent — see close_use_log.
        # Defensive: self may be incomplete on some exit paths (constraint 10
        # names them). Only call if self is not None and has _log_lock.
        if self is not None and hasattr(self, "_log_lock"):
            self.close_use_log("stop")

    def stop(self, timeout: float = 10.0) -> None:
        """Stops uvicorn and waits for the thread to unwind.

        force_exit, not just should_exit: graceful shutdown DRAINS open
        connections, and a phone watching the stream keeps its WebSocket
        open — the drain then waits forever, the old thread got abandoned
        still bound to the port, and the next start() failed with
        port-in-use. That was the live "Apply & restart does nothing"
        failure; a client must never be able to hold the server hostage."""
        # BEFORE anything can block: the join below may wait out its full
        # timeout while the server thread is mid-placement, and the owner must
        # never be left with windows nailed above his desk because a stop took
        # too long (audit 2026-08-05).
        self.release_windows()
        thread = self._thread
        if thread and thread.is_alive() and self._uvicorn is None:
            # stop() during startup — wait for the uvicorn instance to exist
            # so the exit flags have something to land on.
            deadline = time.monotonic() + timeout
            while self._uvicorn is None and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.05)
        if self._uvicorn:
            self._uvicorn.force_exit = True
            self._uvicorn.should_exit = True
        if thread:
            thread.join(timeout)
            if thread.is_alive():
                logger.error("Server thread did not stop within %.0fs", timeout)
                # We just gave up on it, so we must give up its uvicorn with
                # it: that instance belongs to a run nobody controls any more.
                # Left in place it is the next stop()'s target — the branch
                # above would skip its "wait for the instance" wait (the name
                # is not None), the exit flags would land on the abandoned
                # object, and the join would time out against a LIVE thread
                # that was never asked to stop, ending on state="stopped"
                # over a serving server. The same pill, one press later.
                self._uvicorn = None
            self._thread = None
        if self.state != "failed":
            self.state = "stopped"

    def run_blocking(self) -> None:
        """CLI mode: run on the calling thread until Ctrl+C/exit."""
        self._generation += 1
        gen = self._generation
        try:
            asyncio.run(self._serve(gen))
        finally:
            # Same guard as `_run`: nothing may end on a state it no longer
            # owns. Narrow on the CLI path, but an asymmetry here is exactly
            # how the guarded half gets copied wrong later.
            if gen == self._generation and self.state != "failed":
                self.state = "stopped"

    def _run(self, gen: int) -> None:
        try:
            asyncio.run(self._serve(gen))
            if gen == self._generation and self.state != "failed":
                self.state = "stopped"
        except Exception as e:  # visible in log AND in the GUI status
            logger.exception("Server crashed")
            if gen != self._generation:
                # A crash on the way out of a superseded run says nothing
                # about the server the owner is using right now.
                return
            self.state = "failed"
            self.error = str(e)

    # -- the stack ---------------------------------------------------------

    async def _serve(self, gen: int) -> None:
        loop = asyncio.get_running_loop()
        live = lambda: gen == self._generation  # noqa: E731 — one predicate, read many times
        if not live():
            return
        self.loop = loop

        # Stream mode is decided per start: H.264 when a verified encoder
        # exists (capture then runs on demand, per client), JPEG otherwise.
        encoder = encoders.detect_encoder() if SETTINGS.use_h264 else None
        hub = None
        if encoder:
            from h264_streamer import H264Manager
            stream = H264Manager(encoder)
        else:
            from capture import JpegStreamer
            if SETTINGS.use_h264:
                logger.warning("No working H.264 encoder/ffmpeg — falling back to JPEG streaming")
            hub = FrameHub(loop)
            stream = JpegStreamer(on_frame=hub.push_threadsafe)

        injector = InputInjector(
            monitor_rect=monitors.rect_for_size(stream.width, stream.height, stream.monitor_index)
        )

        token = pairing.generate_token()
        urls = pairing.pairing_urls(token)
        stats = ServerStats()
        info = ServerInfo(
            mode=stream.mode,
            encoder=encoder,
            monitor_width=stream.width,
            monitor_height=stream.height,
            port=SETTINGS.port,
            token=token,
            qr_url=urls["qr"],
            lan_url=urls["lan"],
            tailscale_ip=urls["tailscale_ip"],
            stats=stats,
        )
        app = create_app(stream, hub, injector, token, stats=stats,
                         layouts=self.layouts)
        # HIS ANSWER TO THE WINDOW CHIP comes back over HTTP (task 202, his
        # amendment 2026-08-11: a new window is OFFERED, never auto-grabbed).
        # Registered here, at the composition root, beside the app it belongs
        # to — the route itself lives with the rest of that feature in
        # server/layout_popup.py.
        layout_popup.register(app, token)
        # THE NEW SOURCE of a layout (task 184): the phone asks what the PC can
        # open — VS Code / Chrome / Explorer recents — and asks it to open one.
        # Two plain request/response routes, same reason as the line above.
        recents.register(app, token)
        # The traffic meter samples for the life of the PROCESS once started:
        # a stopped server has to read as a line of zeros on the owner's
        # graph, never as a hole where anything could have happened.
        traffic.METER.start()
        # The use log, beside the traffic meter and for the same reason: both
        # are records of what this installation did, and both belong to the
        # process rather than to one phone.
        self._start_use_log(info)
        # ONE display watch for the process (constraint 30: dxcam enumerates
        # its outputs once at import, so nothing notices a monitor arriving).
        # Owned here because every consumer of it — the use log, the Settings
        # window's monitor list, capture's re-enumeration — is downstream of
        # this controller, and `release_windows()` stops it.
        watch = self.display_watch
        watch.subscribe(self._on_display_change)
        try:
            from capture import on_display_change as capture_on_display_change
            watch.subscribe(capture_on_display_change)
        except Exception:
            logger.exception("Capture could not subscribe to the display watch")
        watch.start()
        if self._console_pairing:
            pairing.show_pairing(token)

        # Capture is ON DEMAND in both modes now: H.264 starts it with the
        # first session, and the JPEG fallback starts it with the first
        # subscriber (web.FrameHub.subscribers). Nothing is captured, encoded
        # or sent while no phone is watching — which is the flat line the
        # owner's traffic graph has to be able to show.
        try:
            # Setting up takes real time (encoder detection, pairing, a UIA
            # probe on a busy PC), and a run can be superseded DURING it — the
            # ghost would then publish its own info/loop/uvicorn over the live
            # run's and bind the port a second time. A superseded run never
            # reaches the socket at all; its `finally` still shuts its own
            # stream down.
            if not live():
                logger.warning(
                    "Server run #%d was superseded while starting up — it never serves",
                    gen)
                return
            self.info = info
            # log_level info so every HTTP/WS access is visible — with "warning" a
            # failing client is invisible in the log, which already cost us a debug
            # session (the phone WAS reaching the server while the log showed nothing).
            # log_config=None: uvicorn's own dictConfig calls sys.stdout.isatty(),
            # which crashes in a windowed (no-console) PyInstaller app where stdout
            # is None; without it uvicorn's loggers propagate to our root handlers.
            # lifespan="off": we use no startup/shutdown hooks, and force_exit
            # cancels the lifespan task mid-wait — every stop would log a
            # scary (but harmless) CancelledError traceback.
            server = uvicorn.Server(uvicorn.Config(
                app, host=SETTINGS.host, port=SETTINGS.port,
                log_level="info", log_config=None, lifespan="off",
            ))
            self._uvicorn = server
            self.state = "running"
            await server.serve()
        finally:
            # A superseded run owns NOTHING that is shared: the names below
            # already point at the live run, and its layout windows and
            # encoder are in use. It tears down only what is its own — the
            # uvicorn instance it created and its own stream.
            if live():
                self._uvicorn = None
                self.loop = None
                # FIRST, ahead of the encoder teardown: a hanging ffmpeg
                # terminate must not be able to eat the one thing the owner
                # notices.
                self.release_windows()
            else:
                logger.warning(
                    "Superseded server run #%d finished after run #%d took over "
                    "— leaving the live server's state, windows and encoder alone",
                    gen, self._generation)
            if stream.mode == "jpeg":
                stream.stop()
            else:
                stream.shutdown()
