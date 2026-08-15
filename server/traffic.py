"""Traffic meter: every byte to and from the phone, over time.

An INSTRUMENT, not a feature (owner request 2026-08-05). He was convinced the
app keeps talking to a locked phone and eating its battery, and nothing in
this project could tell him whether it does — a suspicion neither side can
settle is the worst kind of bug report, because every "it stops, I checked"
is just another claim. So the question gets a measurement:

- Every byte crossing the WebSocket in either direction is counted at ONE
  place (`web._MeteredSocket` wraps the socket once, at accept — sprinkling
  counters over a dozen send call sites is how an instrument ends up
  measuring most of the traffic, and most is worthless here), plus the HTTP
  upload endpoints.
- Once a second that becomes a `Sample` in a ring buffer the desktop window
  draws, and a line in a CSV, so a night can be read back in the morning.
- The phone's own side rides along: the Android shell reports what OUR app
  has spent (TrafficStats for its UID) and what the WHOLE device has spent,
  in every heartbeat and in its parting word. The difference between the last
  reading before the phone went away and the first one after it came back is
  the only honest answer to "does it run while I sleep" — and it is measured
  by the phone itself, not inferred by us.

A locked phone must be a FLAT LINE with `clients == 0`. If it ever is not,
this module is what proves it.
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass

import traffic_devices
import traffic_stream
from config import SETTINGS

logger = logging.getLogger(__name__)


# ═══════════════════════════ SAMPLE ═══════════════════════════
@dataclass
class Sample:
    """One second of the graph. `clients` is part of the reading on purpose:
    a zero line means nothing until you can see whether anybody was connected
    to produce it. `device` (owner request 2026-08-13) is the identity of
    whoever was connected — empty when nobody was (see traffic_devices);
    exact for a live sample, since only one phone is ever connected at a
    time (the 4409 takeover rule)."""
    t: float          # unix time at the end of the second
    out_bytes: int    # PC -> phone during that second
    in_bytes: int     # phone -> PC during that second
    clients: int      # connected clients during that second
    device: str = ""  # the device KEY (traffic_devices.device_key) connected
                       # during this second, "" when nobody was (owner request
                       # 2026-08-13 — "which device sent these bytes"). Only
                       # one device is ever active at a time (the protocol's
                       # own "one device at a time" rule, 4409 on takeover),
                       # so a plain per-second tag is a complete attribution —
                       # no per-byte split is needed.
    stream: dict | None = None  # what the encoder was DOING this second —
                       # `traffic_stream.from_session` (fps / res / bitrate /
                       # crop / enc / zoom), owner request 2026-08-15 (T106);
                       # None while nobody streams. Read into the CSV as six
                       # appended columns; a number without its cause is
                       # half a measurement.


# ═══════════════════════════ METER ═══════════════════════════
class TrafficMeter:
    """Byte counters plus a one-second history. Every method is safe to call
    from the event loop, from the capture threads and from the Qt UI thread —
    the lock is held for a few integer operations at a time, and the busiest
    caller (one H.264 chunk) arrives a few dozen times a second."""

    def __init__(self):
        self._lock = threading.Lock()
        self._out = 0                 # bytes since the last sample
        self._in = 0
        self.total_out = 0            # since the counters were last reset
        self.total_in = 0
        self.since = time.time()
        self.clients = 0
        self.samples: deque = deque(maxlen=SETTINGS.traffic_history_samples)
        # What the phone says about itself (Android TrafficStats, cumulative
        # since the phone booted): the first reading of this connection, the
        # newest one, and the gap measured across its last absence.
        self.phone_first: dict | None = None
        self.phone_last: dict | None = None
        self.away_gap: dict | None = None
        self._gap_from: dict | None = None
        # WHAT THIS APP COSTS THE BATTERY WHILE IT RUNS (T80d, owner
        # 2026-08-14). The phone measures ITSELF and reports it on the
        # existing beat, so every device answers for its own hardware rather
        # than being predicted from his. Nothing here is ever computed when
        # the phone did not say: a missing property stays missing all the way
        # to the window, which then says so in words.
        self.battery_first: dict | None = None
        self.battery_last: dict | None = None
        self._drain_sum = 0.0     # sum of reported draw magnitudes, microamps
        self._drain_n = 0         # how many readings carried one
        self._thread: threading.Thread | None = None
        self._recording = True
        # Which device is the current session (see `traffic_devices.py`) —
        # set at `auth`, cleared when the client count drops back to 0. Read
        # into every `Sample` taken while it is set.
        self._device: str = ""
        # The live H.264 session's descriptor (see `traffic_stream.py`) —
        # set by web.py when a session opens, cleared when it closes.
        self._stream: dict | None = None

    # -- counting ----------------------------------------------------------

    def add_out(self, n: int) -> None:
        with self._lock:
            self._out += n
            self.total_out += n

    def add_in(self, n: int) -> None:
        with self._lock:
            self._in += n
            self.total_in += n

    def set_clients(self, n: int) -> None:
        """0 is the reading that matters most: it is what "nobody is watching"
        looks like, and it is what turns a flat line into proof."""
        n = max(0, n)
        with self._lock:
            was, self.clients = self.clients, n
            if n == 0 and was > 0:
                # The phone is gone. Remember its last self-report — whatever
                # it spends while we cannot see it shows up as the difference
                # against its first report when it returns.
                self._gap_from = self.phone_last
                self.phone_first = self.phone_last = None
                self._device = ""
                # The battery figures are about THIS session — "what did the
                # app cost while it was running" is the owner's own question
                # (T80d), and a level carried across a gap in which the phone
                # may have been charged would answer a different one. The
                # LAST reading survives so the window can still state the
                # closing level of the session that just ended.
                self.battery_first = None
                self._drain_sum, self._drain_n = 0.0, 0

    def set_device(self, key: str) -> None:
        """Called once at `auth`, after `traffic_devices.REGISTRY.note()` has
        resolved this connection's stable key. Left untouched by `reset()` —
        the Reset button clears COUNTERS, not who is holding the session."""
        with self._lock:
            self._device = key or ""

    def note_stream(self, info: dict | None) -> None:
        """web.py's two call sites: the descriptor of the H.264 session that
        just OPENED (`traffic_stream.from_session(session)`), or None when it
        closed. Every sample taken in between carries it (T106)."""
        with self._lock:
            self._stream = dict(info) if info else None

    def note_device(self, w, h, name: str | None) -> str:
        """`web.py`'s ONE call site: registers this connection's device with
        `traffic_devices.REGISTRY` (assigning it a stable, persisted colour
        slot the first time this resolution is ever seen) and arms
        `set_device` with the resulting key in the same call — the two used
        to be two call sites, which is exactly the kind of split that lets
        one of them go missing on the next edit."""
        entry = traffic_devices.REGISTRY.note(w, h, name)
        self.set_device(entry["key"])
        return entry["key"]

    def note_phone(self, reading: dict) -> None:
        """What the phone says IT has spent. `reading` carries app_rx/app_tx
        (our UID) and dev_rx/dev_tx (the whole device), all cumulative since
        the phone booted — deltas are computed here, never on the phone."""
        if not reading:
            return
        with self._lock:
            if self._gap_from is not None:
                self.away_gap = {
                    key: max(0, int(reading.get(key, 0)) - int(self._gap_from.get(key, 0)))
                    for key in ("app_rx", "app_tx", "dev_rx", "dev_tx")
                }
                self.away_gap["seconds"] = max(
                    0.0, time.time() - float(self._gap_from.get("t", time.time())))
                self._gap_from = None
            reading = dict(reading)
            reading["t"] = time.time()
            if self.phone_first is None:
                self.phone_first = reading
            self.phone_last = reading

    def note_battery(self, reading: dict) -> None:
        """What the phone says ITS OWN battery is doing (T80d, owner
        2026-08-14). `reading` may carry `level` (percent), `current_ua` (the
        MAGNITUDE of the instantaneous draw — the shell never sends a sign,
        because `BATTERY_PROPERTY_CURRENT_NOW`'s convention is inverted on a
        known share of OEMs and there is no way to tell which) and
        `charging`. Every one of them is independently optional: a device
        that will not answer sends nothing, and nothing is what must be
        stored — a zero here would become "this app costs nothing" on his
        screen, which is the one wrong answer that looks like a good one.

        No value is ever invented from another: a session with a level and no
        current reports a level and no current, and the window says which
        half is missing.
        """
        if not reading:
            return
        kept = {}
        level = reading.get("level")
        if isinstance(level, (int, float)) and 0 <= level <= 100:
            kept["level"] = int(level)
        current = reading.get("current_ua")
        if isinstance(current, (int, float)) and current > 0:
            kept["current_ua"] = float(current)
        if isinstance(reading.get("charging"), bool):
            kept["charging"] = reading["charging"]
        if not kept:
            return
        with self._lock:
            kept["t"] = time.time()
            if self.battery_first is None:
                self.battery_first = kept
            self.battery_last = kept
            if "current_ua" in kept:
                # An AVERAGE over the readings that carried one — a single
                # instantaneous sample swings with whatever the screen is
                # doing that second, and the number he asked for is what the
                # session costs, not what one heartbeat caught.
                self._drain_sum += kept["current_ua"]
                self._drain_n += 1

    def battery(self) -> dict | None:
        """The session's battery picture, or `None` when this phone has said
        nothing at all — the window renders that as plain words, never as a
        blank or a zero. Caller must hold no lock."""
        with self._lock:
            last, first = self.battery_last, self.battery_first
            drain_sum, drain_n = self._drain_sum, self._drain_n
        if not last:
            return None
        out: dict = {
            "level": last.get("level"),
            "charging": last.get("charging"),
            "current_ua": last.get("current_ua"),
            "avg_ua": (drain_sum / drain_n) if drain_n else None,
            "level_drop": None,
            "seconds": None,
        }
        if first and first.get("level") is not None and last.get("level") is not None:
            out["level_drop"] = first["level"] - last["level"]
            out["seconds"] = max(0.0, last["t"] - first["t"])
        return out

    def reset(self) -> None:
        """The window's Reset button: totals and history start over. The CSV
        is NOT touched — a recording the owner may still want to read is not
        something a stray click gets to delete."""
        with self._lock:
            self._out = self._in = 0
            self.total_out = self.total_in = 0
            self.since = time.time()
            self.samples.clear()
            self.phone_first = self.phone_last = None
            self.away_gap = self._gap_from = None
            self.battery_first = self.battery_last = None
            self._drain_sum, self._drain_n = 0.0, 0

    # -- sampling ----------------------------------------------------------

    def start(self) -> None:
        """Begin sampling. Called once when the server starts and never
        stopped: a stopped server has to read as a line of ZEROS, not as a
        hole in the graph where anything could have happened."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._sample_loop,
                                        name="traffic-meter", daemon=True)
        self._thread.start()

    def _sample_loop(self) -> None:
        period = max(0.2, SETTINGS.traffic_sample_s)
        next_at = time.monotonic()
        while True:
            next_at += period
            time.sleep(max(0.0, next_at - time.monotonic()))
            try:
                self._take_sample()
            except Exception as e:  # a measuring thread may never kill the app
                logger.warning("Traffic sample failed: %s", e)

    def _take_sample(self) -> None:
        with self._lock:
            sample = Sample(time.time(), self._out, self._in, self.clients,
                             self._device, self._stream)
            self._out = self._in = 0
            self.samples.append(sample)
        self._append_csv(sample)

    def history(self, seconds: float = 0.0) -> list:
        """The newest `seconds` of samples (0 = everything held)."""
        with self._lock:
            if seconds <= 0:
                return list(self.samples)
            cutoff = time.time() - seconds
            return [s for s in self.samples if s.t >= cutoff]

    def snapshot(self) -> dict:
        """Everything the desktop window's header shows, read under one lock
        so its numbers cannot disagree with each other."""
        with self._lock:
            last = self.samples[-1] if self.samples else None
            phone = None
            if self.phone_first and self.phone_last:
                phone = {
                    key: max(0, int(self.phone_last.get(key, 0))
                             - int(self.phone_first.get(key, 0)))
                    for key in ("app_rx", "app_tx", "dev_rx", "dev_tx")
                }
            return {
                "out_per_s": last.out_bytes if last else 0,
                "in_per_s": last.in_bytes if last else 0,
                "total_out": self.total_out,
                "total_in": self.total_in,
                "clients": self.clients,
                "since": self.since,
                "phone": phone,
                "away_gap": dict(self.away_gap) if self.away_gap else None,
                "recording": self._recording,
            }

    # -- recording ---------------------------------------------------------

    def _append_csv(self, sample: Sample) -> None:
        if not self._recording:
            return
        path = SETTINGS.traffic_csv_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.stat().st_size > SETTINGS.traffic_csv_max_bytes:
                self._rotate(path)
            header = not path.exists()
            with path.open("a", encoding="utf-8", newline="") as fh:
                if header:
                    # A 5th column, appended (never inserted) — an OLDER
                    # server still reads its own file's first 4 fields fine,
                    # and `traffic_history._parse_row` accepts either width so
                    # a file spanning the upgrade never breaks the reader
                    # (owner's own hard rule for this round).
                    # Six more, again APPENDED (T106, 2026-08-15): what the
                    # encoder was doing — see `traffic_stream.py`. Same rule:
                    # a reader accepts every width the file ever had.
                    fh.write("time,out_bytes,in_bytes,clients,device,"
                             + ",".join(traffic_stream.STREAM_COLUMNS) + "\n")
                fh.write("{},{},{},{},{},{}\n".format(
                    time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sample.t)),
                    sample.out_bytes, sample.in_bytes, sample.clients,
                    sample.device,
                    ",".join(traffic_stream.to_csv_fields(sample.stream))))
        except OSError as e:
            # Said once, then the graph keeps running from memory: a disk
            # problem must not cost the owner the live measurement too.
            self._recording = False
            logger.warning("Traffic recording stopped (%s) — the live graph continues", e)

    @staticmethod
    def _rotate(path) -> None:
        backup = path.with_name(path.name + ".1")
        try:
            if backup.exists():
                backup.unlink()
            path.rename(backup)
        except OSError:
            pass


# ═══════════════════════════ THE MEASURING POINT ═══════════════════════════
class MeteredSocket:
    """A WebSocket that counts what passes through it.

    ONE wrapper at accept time, not counters at each of a dozen send call
    sites: the socket is what every handler in web.py is handed, so this is
    the only place that can be COMPLETE — and an instrument built to settle
    an argument is worth nothing if it measures most of the traffic.

    Everything it does not override (accept, close, client, receive_bytes…)
    passes straight through, so the rest of the server cannot tell the
    difference — including the `is` comparisons that decide which device owns
    the session, because the wrapper is what every one of them sees.
    """

    __slots__ = ("_ws", "_meter")

    def __init__(self, ws, meter: TrafficMeter):
        self._ws = ws
        self._meter = meter

    def __getattr__(self, name):
        return getattr(self._ws, name)

    async def send_text(self, text: str) -> None:
        self._meter.add_out(len(text.encode("utf-8")))
        await self._ws.send_text(text)

    async def send_bytes(self, data: bytes) -> None:
        self._meter.add_out(len(data))
        await self._ws.send_bytes(data)

    async def receive_text(self) -> str:
        text = await self._ws.receive_text()
        self._meter.add_in(len(text.encode("utf-8")))
        return text


# ═══════════════════════════ SHARED INSTANCE ═══════════════════════════
# One meter per process, deliberately outliving any single server run: the
# owner restarts the server from the window (Apply & restart) and the graph
# must keep its history across that, or an overnight measurement is lost to
# one settings change.
METER = TrafficMeter()

# When THIS PROCESS started — distinct from `METER.since`, which the Reset
# button rewinds. The Traffic window's "Od starta" span names the process's
# own lifetime (BUILD ROUND R4, owner-approved 2026-08-07), and a stray click
# on Reset must never touch that answer.
PROCESS_START = time.time()
