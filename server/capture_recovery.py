"""Bringing a DEAD capture back — the responsibility `capture.py` does not own.

`capture.py` owns a LIVE camera's life: open it, grab from it, hand it on, put
it down. This module owns the case where that camera has stopped producing
pictures and cannot be talked to any more, which is a different job with
different rules: nothing here may block, nothing here may trust dxcam to let
go, and every rung of the ladder must SAY which rung brought the picture back.

THE FAILURE THIS EXISTS FOR (owner report 2026-08-16, measured in his own log
and reproduced on his own machine the same night).

He connected from the tablet at 19:19:24. Everything worked EXCEPT the
picture: his running applications were listed, he built a layout, the layout
really was created on the PC — and the canvas stayed our blue background
(`--canvas-bg`) the whole time. The control path never touches capture, which
is exactly why it looked healthy while the one thing he wanted was dead.

His log dates every step of it:

    19:19:24,309  dxcam: Frame buffer build(start): 3840x2160
    19:19:24,334  Desktop duplication access loss detected (HRESULT=0x887A0026)
    19:19:24,335  Output recovery attempt 1 failed (Output is not attached to
                  desktop.); retrying in 0.250s.
    19:19:41,353  Camera stop: Capture thread did not stop within timeout
    19:19:51,376  ERROR web: H.264 session failed to open: Capture is already
                  running. Call stop() first.
    ...          the same three lines every ~12 s, for 3.8 HOURS
    23:04:37,876  Output recovery attempt 2760 failed (Output is not attached
                  to desktop.); retrying in 5.000s.

FOUR separate mechanisms had to line up, and naming all four is the point —
fixing any one alone leaves the blue screen reachable by the other three:

1. `dxcam/core/display_recovery.py` retries in a bare `while True`. There is no
   give-up and no check of any stop flag, so the camera's own thread parks in
   there for as long as the process lives.
2. `dxcam/core/output_recovery.py::_refresh_output_desc` re-enumerates the
   adapter's outputs ONLY when `update_desc()` raises a transient COM error.
   When the descriptor reads back perfectly well and merely says
   `AttachedToDesktop == False`, it keeps the SAME `IDXGIOutput` and raises
   "Output is not attached to desktop." — forever, against an object that can
   never change its mind.
3. `dxcam.DXFactory` is a singleton built at IMPORT time, and its `Output`
   objects are enumerated once for the life of the process. So even our own
   task-193 eviction path (`close()` → `dxcam.create()`) hands the new camera
   the SAME stale output. Re-opening was never going to work.
4. `BaseCapture.start()`'s reset-and-retry (written 2026-07-29 for a different
   failure) assumes `stop()` can stop the camera. Against a parked recovery
   thread it cannot: dxcam's `stop()` joins for ten seconds, gives up, leaves
   the "capturing" flag standing, and the next `start()` raises the identical
   error. That is the 12-second cycle repeating in his log 3.8 hours long.

MEASURED, not reasoned (constraint 23's rule): while that loop was still
failing on his machine, a fresh `dxcam.create()` in a SEPARATE PROCESS grabbed
3840x2160 frames instantly. The display was attached the whole time he was
sitting at it — only the in-process DXGI objects were stale. That measurement
is what makes the ladder below a fix rather than a hope, and it is why rung 2
(re-enumerate) exists at all.

THE LADDER, and every rung is logged with its outcome so his next log answers
the question this one could not:

    rung 1  abandon  — give up on the parked camera WITHOUT waiting for it
    rung 2  reopen   — a fresh `dxcam.create()` on the existing enumeration
    rung 3  re-enumerate — rebuild dxcam's factory so brand-new `Output`
                       objects are made, then reopen

Rung 1 never blocks: `release()` joins dxcam's thread for ten seconds and
returns whether or not it died, so it is run on a THROWAWAY thread and the
parked thread is knowingly leaked. A leaked idle daemon thread is the price of
a picture coming back; it is bounded by the cooldown below and it is named in
the log rather than hidden.

AND THE PHONE IS TOLD. A blue screen that says nothing is the half of this
failure he actually lived through — he could not tell a dead capture from a
dead app, and there was nothing on the page to read. Every state change goes
out through `on_state`, so the page can say the PC lost its picture and say
when it came back.
"""

import asyncio
import logging
import threading
import time

import dxcam

import session_log

logger = logging.getLogger(__name__)

# No frame for this long, while capture is RUNNING and someone is watching,
# means the camera is not coming back on its own. dxcam's own recovery backs
# off to a 5 s retry, so anything under ~6 s would fire during a legitimate
# transient (a mode switch, a fullscreen game taking the output) that dxcam
# does heal by itself. This is the give-up point dxcam does not have.
STALL_SECONDS = 8.0

# Never run the ladder faster than this. A rebuild leaks a parked thread when
# dxcam refuses to die (see rung 1), so a tight loop would trade a blue screen
# for a thread leak — the cooldown is what keeps the cure bounded.
REBUILD_COOLDOWN_S = 20.0

# How often the guard looks. It only reads a float, so this is free.
POLL_S = 1.0


# How long rung 1 waits for a real release before walking away from it. A
# HEALTHY camera releases in milliseconds; the parked one cannot release at
# all, because dxcam's `stop()` joins its own thread for ten seconds and that
# thread is inside the infinite retry loop. So this is not an estimate of how
# long anything takes (constraint 15) — it is the line between "it answered"
# and "it is never going to", and both sides are handled.
RELEASE_WAIT_S = 2.5


def abandon_camera(camera, wait_s: float = RELEASE_WAIT_S) -> bool:
    """Rung 1 — stop owning the camera, and FREE ITS DUPLICATION if it will.

    Freeing matters more than it looks: DXGI allows one desktop duplication
    per output, so a camera that is merely dropped keeps the very handle the
    replacement needs, and the fresh `DuplicateOutput` fails with
    "The parameter is incorrect" (E_INVALIDARG). That is not a theory — it is
    what this module's own smoke test did on the first attempt, against a
    HEALTHY camera, and it would have made the whole ladder a no-op on every
    case except the one it was written for.

    So the release is attempted for real, on a throwaway thread, and waited on
    briefly. A healthy camera lets go at once. A parked one never will —
    dxcam's `stop()` joins a thread that is inside its infinite retry loop —
    and there the wait is abandoned, the instance is marked released so
    dxcam's factory drops it from its registry (`DXFactory.create` deletes any
    entry whose `is_released` is true), and the parked thread is knowingly
    leaked. A leaked idle daemon thread is the price of a picture coming back;
    it is bounded by the guard's cooldown and it is named in the log rather
    than hidden.

    Returns True when the camera really let go. Never raises: this runs on the
    path that exists because something already went wrong."""
    if camera is None:
        return True
    done = threading.Event()
    thread = threading.Thread(
        target=_release_quietly, args=(camera, done),
        name="capture-abandon", daemon=True,
    )
    thread.start()
    if done.wait(wait_s):
        logger.info("Capture recovery: the old camera released its duplication")
        return True
    logger.warning(
        "Capture recovery: the old camera did not let go within %.1fs — its thread "
        "is parked inside dxcam's retry loop. Marking it released and leaking that "
        "thread deliberately; the replacement is worth more than the corpse.", wait_s)
    try:
        camera._is_released = True  # what the factory's registry actually reads
    except Exception as e:  # a camera object dxcam has already torn down
        logger.warning("Capture recovery: could not mark the camera released: %s", e)
    return False


def _release_quietly(camera, done: threading.Event) -> None:
    try:
        camera.release()
        done.set()
    except Exception as e:
        # Expected on a camera whose thread is parked — the release path is a
        # courtesy here, not the mechanism. The mechanism is the flag above.
        logger.info("Capture recovery: abandoned camera did not release cleanly (%s) "
                    "— its thread is parked inside dxcam's retry loop and is leaked "
                    "deliberately", e)


def reenumerate_dxgi() -> bool:
    """Rung 3 — make dxcam enumerate the adapters and outputs AGAIN.

    This is the rung that answers mechanism 3 above: `DXFactory` is a
    process-lifetime singleton whose `Output` objects were built at import, so
    a display that detached and came back is described by objects that will
    say "not attached" for as long as the app runs. Rebuilding the factory is
    the only way to get new ones without restarting the server.

    It reaches into dxcam's privates, which is why it is written HERE, alone,
    behind one name: a dxcam release that changes its factory shape breaks
    exactly this function, and it returns False with a warning instead of
    taking the capture down with it. Verified on this machine: a rebuilt
    factory produces a camera that grabs at full resolution.

    Returns True when the enumeration really was rebuilt."""
    try:
        factory_cls = dxcam.DXFactory
        singleton = type(factory_cls)
        previous = getattr(dxcam, "__factory", None)
        singleton._instances.pop(factory_cls, None)
        fresh = factory_cls()
        setattr(dxcam, "__factory", fresh)
    except Exception as e:
        logger.warning(
            "Capture recovery: DXGI could not be re-enumerated (%s) — dxcam's "
            "factory is not the shape this was written against; the reopen rung "
            "still stands", e)
        return False
    if fresh is previous:
        logger.warning("Capture recovery: the DXGI factory rebuilt to the same "
                       "object — nothing was re-enumerated")
        return False
    logger.info("Capture recovery: DXGI re-enumerated — %d adapter(s), fresh output "
                "objects", len(getattr(fresh, "devices", ())))
    return True


def phone_notice(ws, loop, toast):
    """Bridges the guard (a plain thread) to one phone's status pill.

    It lives HERE and not in the web layer for the reason the structure law
    asks: telling the owner that the picture died is part of recovering from
    it, not part of serving a socket — and web.py stood at the 1,000-line wall
    when this was written, which is the law noticing the same thing.

    `toast` is passed IN rather than imported so this module keeps no opinion
    about the protocol; the guard cannot await and does not know what a socket
    is, so the callable it gets hops onto the event loop by itself. A send
    that fails is DROPPED and logged, never raised: this runs on the recovery
    path, and a guard that dies of a broken pipe takes the only way back with
    it."""
    async def _send(text: str) -> None:
        try:
            await toast(ws, text)
        except Exception as e:
            logger.info("Capture notice could not reach the phone: %s", e)

    def notice(ok: bool, detail: str) -> None:
        text = detail or ("The PC's picture is back" if ok else "The PC lost its picture")
        try:
            asyncio.run_coroutine_threadsafe(_send(text), loop)
        except Exception as e:
            logger.info("Capture notice could not be scheduled: %s", e)

    return notice


class CaptureGuard:
    """Watches ONE capture's frame clock and runs the ladder when it stops.

    It judges by the only fact that matters to the owner — did a picture
    arrive — and never by whether dxcam reported an error, because the failure
    it exists for reports its errors at INFO level to its own logger and
    otherwise looks exactly like a healthy idle camera.

    `is_wanted` is asked before every verdict so an idle server (nobody
    connected, capture deliberately stopped) is never "stalled"; `rebuild`
    performs the actual reopen and is the capture's own business."""

    def __init__(self, capture, *, is_wanted, on_state=None,
                 stall_seconds: float = STALL_SECONDS,
                 cooldown_s: float = REBUILD_COOLDOWN_S,
                 poll_s: float = POLL_S, clock=time.monotonic):
        self._capture = capture
        self._is_wanted = is_wanted
        self._on_state = on_state
        self._stall = stall_seconds
        self._cooldown = cooldown_s
        self._poll = poll_s
        self._clock = clock
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._last_attempt = 0.0
        self._down = False

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="capture-guard", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.wait(self._poll):
            try:
                self.tick()
            except Exception:
                # A guard that dies takes the only way back with it.
                logger.exception("Capture guard tick failed")

    def tick(self) -> None:
        """One judgement. Split out from the thread so a gate can drive it with
        its own clock instead of sleeping through real seconds."""
        if not self._is_wanted():
            self._last_attempt = 0.0  # an idle stretch is not a used-up cooldown
            return
        age = self._capture.frame_age()
        if age < self._stall:
            if self._down:
                self._down = False
                logger.info("Capture recovered — frames are arriving again")
                self._announce(True, "")
            return
        if not self._down:
            self._down = True
            logger.error(
                "CAPTURE STALLED — no frame for %.1fs while a client is watching. "
                "This is the blue-screen failure: the phone keeps its controls and "
                "gets no picture at all. Running the recovery ladder.", age)
            self._announce(False, "The PC lost its picture — putting it back")
        now = self._clock()
        if self._last_attempt and now - self._last_attempt < self._cooldown:
            return
        self._last_attempt = now
        self._capture.rebuild_camera()

    def _announce(self, ok: bool, detail: str) -> None:
        # The use log's own evidence for a bug (owner ruling 2026-08-16): the
        # ONE place capture's health flips, so a dead-then-recovered picture
        # is exactly two lines in his file, never zero and never four.
        try:
            session_log.LOG.record("fault.capture", ok=ok, detail=detail)
        except Exception:
            logger.exception("Capture guard could not log its own state")
        if self._on_state is None:
            return
        try:
            self._on_state(ok, detail)
        except Exception:
            logger.exception("Capture guard could not announce its state")


def recover_for_open(capture, error: Exception) -> bool:
    """Run the ladder because a session FAILED TO OPEN, and say whether a
    camera that really produces frames is back.

    WHY THIS ENTRY POINT EXISTS (owner report 2026-08-17, T135). His report:
    he lifted the laptop and the tablet "just span connected, disconnected,
    connected, disconnected"; it only came back after he installed an update
    on the PC. Read out of his own `server.log` rather than asked about — six
    cycles, one every six seconds, 09:24:02 to 09:24:26:

        dxcam: AttributeError: 'NoneType' object has no 'AcquireNextFrame'
        web:   H.264 session failed to open: ffmpeg produced no init segment
        web:   Client disconnected
        web:   Client authenticated          <- one second later, and again

    The camera was dead (the DXGI duplicator's COM object gone), so ffmpeg was
    fed nothing, so the FIRST session could not open — and `web.py` closed the
    socket for it. The phone reconnects a second later, meets the same dead
    camera, and the loop cannot break itself: a new CONNECTION has never fixed
    DXGI. What finally "fixed" it was installing an update, which RESTARTED
    the process — the only thing in that whole sequence that was clearing the
    stale COM objects. The new version had nothing to do with it, and that is
    worth writing down, because "it started working after the update" is
    exactly the evidence that would send the next round looking at the wrong
    release.

    WHY THE LADDER COULD NOT ALREADY REACH HIM, which is the structural half:
    `CaptureGuard` judges by the FRAME CLOCK while a client is watching — did
    a picture arrive — and that is the right question for the blue-screen
    failure it was built for (constraint 30), where the session opens fine and
    then goes quiet. Here no session ever opens, so there is no stream to
    measure, no frame age to compare, and the guard's whole premise is absent.
    A dead camera at open time is the SAME dead camera; it simply has no
    stream for the guard to watch it through. So the ladder needs a second
    door, and this is it.

    Bounded on purpose: `web.py` calls this at most once per connection. It is
    a real rebuild of the camera — abandon, reopen, re-enumerate — not a retry
    knob, and running it per failed attempt would be its own storm.

    The capture is passed IN rather than looked up, for the same reason
    `phone_notice` takes its toast: this module owns the LADDER and holds no
    opinion about who owns the camera. `H264Manager` does, and it is the one
    that calls in here.

    Returns True when a camera that PROVED itself (it produced a frame) is
    installed, so the caller may retry the session; False when it could not,
    in which case the caller closes the socket and the phone is told the PC
    lost its picture — the honest end, and one the owner can act on, instead
    of a flap with no message.
    """
    logger.error("H.264 session failed to open (%s) — running the capture "
                 "recovery ladder before giving up", error)
    try:
        healed = bool(capture is not None and capture.rebuild_camera())
    except Exception:
        logger.exception("The capture recovery ladder raised while answering a "
                         "failed session open")
        healed = False
    if healed:
        logger.info("Capture rebuilt after a failed session open — retrying")
    else:
        logger.error("The capture could not be rebuilt — the PC has no picture "
                     "to send, and the phone is being told so instead of being "
                     "left to reconnect into the same failure")
    try:
        session_log.LOG.record("fault.capture", ok=healed,
                               detail="session open failed; ladder "
                                      + ("recovered" if healed else "could not recover"))
    except Exception:
        logger.exception("Capture recovery could not log the open-failure ladder")
    return healed
