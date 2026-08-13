"""Which PHONE was on the other end of the traffic — attribution and colour.

Owner request 2026-08-13: the Traffic window's "this session X MB" line
should say how LONG the session lasted, its rate in MB/h, and the RESOLUTION
of every Android device that connected — with a NAME when one can be found,
e.g. "Samsung Galaxy S5 Ultra" — and the chart should colour its line
differently per device, since that is what lets him SEE a smaller-resolution
phone costing fewer bytes.

Split out as its own module (THE STRUCTURE LAW): `traffic.py` counts bytes
and knows nothing about WHO is on the other end; `traffic_window.py` paints;
this module is the one place that turns "a screen size arrived on `auth`"
into a stable identity, a colour and a human label — the same
one-responsibility split `layout_history.py` already uses for a persisted,
capped, cross-restart record.

STABLE IDENTITY, and why it is what it is (the task's own instruction to
document this choice): a device is keyed by its **CSS-pixel screen
resolution alone** — `"{w}x{h}"`, both rounded to whole pixels — never by
name. A name can arrive late (the `userAgentData` promise resolves after the
first paint, `client/dictation-card.js`'s own pattern, reused verbatim here)
or never at all, and keying by something that can change mid-session would
split ONE phone into two colours the moment its better name lands. Two
different physical devices that happen to share an exact resolution collide
into one slot — an accepted, named limit (`DeviceRegistry.note`'s docstring)
rather than a guess at a richer key (resolution+model) that would instead
split ONE phone into two slots the day its `userAgent` model token differs
from what `userAgentData` later resolves.

PERSISTED ACROSS RESTARTS, same shape as `layout_history.py`:
`%LOCALAPPDATA%/VibeCoder/traffic_devices.json` maps device key -> the index
it was assigned the FIRST time it was ever seen on this PC (plus the best
name found so far). Re-connecting the same tablet next week must land it on
the same colour, not a new one appended at the end — a colour that keeps
sliding is exactly as useless as no colour at all.

COLOUR: `gui.theme.DEVICE_COLORS`, not invented here — see that module's own
docstring for why it is the existing `SET_COLORS` palette, already proven
(by `tests/test_layout_audit.py`) to read on both the dark and the light
desktop palette.
"""

import json
import logging
import threading
from pathlib import Path

from config import USER_DIR

logger = logging.getLogger(__name__)

UNKNOWN_LABEL = "unknown device"


def _path() -> Path:
    """Same user-data folder every other persisted file in this project
    uses (`config.USER_DIR`) — never a second hand-rolled LOCALAPPDATA
    lookup that could silently drift from it."""
    return USER_DIR / "traffic_devices.json"


def device_key(w, h) -> str:
    """The stable identity: whole-pixel CSS resolution, ORIENTATION-INVARIANT
    (coordinator defect report 2026-08-13, correcting this module's own
    earlier claim that normalising was unnecessary). A real device rotates
    mid-session — `window.screen.width`/`height` swap the moment Android
    reports landscape instead of portrait — and the FIRST version of this
    key was a plain `f"{w}x{h}"`, order-sensitive: one physical tablet held
    both ways during one session produced TWO registry entries, two colours,
    two rows in the "devices seen" list, for one phone. The key is now the
    two dimensions SORTED (smaller first) so a rotation can never change
    identity; the human-facing LABEL is built separately, from whichever
    orientation was actually seen most recently (`DeviceRegistry.note`'s
    `last_wh`), so the display never shows a nonsensical "sorted" size the
    device itself never reported."""
    try:
        wi, hi = int(round(float(w))), int(round(float(h)))
    except (TypeError, ValueError):
        return ""
    if wi <= 0 or hi <= 0:
        return ""
    lo, hi_ = sorted((wi, hi))
    return f"{lo}x{hi_}"


def label_for(key: str, name: str | None, wh: tuple[int, int] | None = None) -> str:
    """What the phone list shows for one device: the name when we have one,
    else an honest admission we don't (the task's hard rule — never guess a
    model name), always paired with a resolution. `wh` — the device's own
    LAST-SEEN orientation, `DeviceRegistry`'s `last_wh` — is used when given;
    only the identity KEY is orientation-sorted, never what he reads."""
    if not key:
        return "unknown device"
    if wh is not None:
        w, h = wh
    else:
        w, h = key.split("x")
    if name:
        return f"{name} ({w}×{h})"
    return f"{UNKNOWN_LABEL} ({w}×{h})"


class DeviceRegistry:
    """First-seen-order slot assignment, persisted so a reconnecting device
    keeps its colour across a server restart. Every method is lock-safe —
    `note()` runs on the event loop at `auth` time; the GUI thread only ever
    reads via `all()`/`label_for_key()`, which take the same lock."""

    def __init__(self, path: Path | None = None) -> None:
        self._lock = threading.Lock()
        self._path = path or _path()
        self._entries: dict[str, dict] = {}   # key -> {"index", "name"}
        self._load()

    def _load(self) -> None:
        """Reads the persisted file, then MIGRATES it: a file written before
        `device_key` was made orientation-invariant (2026-08-13) may hold two
        entries — `"1080x2400"` and `"2400x1080"` — for what is now one
        identity. Both are folded into whichever normalised key they share,
        so an existing colour assignment is never orphaned or duplicated by
        the fix that stopped it happening again. Approach: MERGE-on-load,
        immediately followed by a REWRITE of the file if anything changed —
        migration runs at most once per machine; every load after that finds
        an already-normalised file and does nothing extra."""
        try:
            if not self._path.exists():
                return
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            raw = {k: v for k, v in data.items()
                   if isinstance(v, dict) and "index" in v}
        except (OSError, ValueError) as e:
            logger.warning("traffic_devices: could not read %s (%s)", self._path, e)
            return

        migrated: dict[str, dict] = {}
        changed = False
        # Oldest slot (smallest index) FIRST, so when two raw keys collide
        # into one normalised key, the earlier-seen entry is kept as the
        # canonical one — "prefer the earliest-seen slot index" — and only
        # loses to the later one for fields it does not itself have (a name
        # the earlier connection never learned).
        for raw_key, entry in sorted(raw.items(), key=lambda kv: kv[1].get("index", 0)):
            try:
                w_str, h_str = raw_key.split("x")
                w, h = int(w_str), int(h_str)
            except (ValueError, IndexError):
                continue
            norm = device_key(w, h)
            if not norm:
                continue
            if norm != raw_key:
                changed = True
            existing = migrated.get(norm)
            if existing is None:
                migrated[norm] = {
                    "index": entry["index"],
                    "name": entry.get("name"),
                    "last_wh": entry.get("last_wh", [w, h]),
                }
            else:
                changed = True   # a real collision — two raw keys, one device
                if not existing.get("name") and entry.get("name"):
                    existing["name"] = entry["name"]
        self._entries = migrated
        if changed:
            self._save()
            logger.info("traffic_devices: migrated %s to orientation-invariant "
                       "keys (%d slot(s))", self._path, len(migrated))

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._entries, indent=2), encoding="utf-8")
        except OSError as e:
            logger.warning("traffic_devices: could not write %s (%s)", self._path, e)

    def note(self, w, h, name: str | None) -> dict:
        """Called once per `auth`. Returns the entry for this connection —
        `{"key", "index", "name"}` — assigning a fresh slot only the FIRST
        time this NORMALISED resolution is ever seen on this PC (a rotation
        mid-session lands on the SAME slot, never a new one). A NAME, once
        learned, is never overwritten by a blank one — the late
        `userAgentData` promise (or a plain reconnect that skipped the model
        field) must not erase a name an earlier connection already found.
        `last_wh` — the actual orientation THIS call reported — is always
        updated, so the device list shows the phone the way it is being
        held right now, not the sorted identity key."""
        key = device_key(w, h)
        if not key:
            return {"key": "", "index": -1, "name": None}
        try:
            wh = (int(round(float(w))), int(round(float(h))))
        except (TypeError, ValueError):
            wh = None
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = {"index": len(self._entries), "name": name or None,
                         "last_wh": list(wh) if wh else None}
                self._entries[key] = entry
                self._save()
            else:
                dirty = False
                if name and entry.get("name") != name:
                    entry["name"] = name
                    dirty = True
                if wh is not None and entry.get("last_wh") != list(wh):
                    entry["last_wh"] = list(wh)
                    dirty = True
                if dirty:
                    self._save()
            return {"key": key, "index": entry["index"], "name": entry.get("name")}

    def index_for(self, key: str) -> int:
        with self._lock:
            entry = self._entries.get(key)
            return entry["index"] if entry else -1

    def label_for_key(self, key: str) -> str:
        with self._lock:
            entry = self._entries.get(key)
            name = entry.get("name") if entry else None
            wh = tuple(entry["last_wh"]) if entry and entry.get("last_wh") else None
        return label_for(key, name, wh)

    def all(self) -> list[dict]:
        """Every device ever seen on this PC, oldest slot first — what the
        Traffic window's device list reads."""
        with self._lock:
            items = [(k, v["index"], v.get("name"),
                      tuple(v["last_wh"]) if v.get("last_wh") else None)
                     for k, v in self._entries.items()]
        items.sort(key=lambda t: t[1])
        return [{"key": k, "index": i, "name": n, "label": label_for(k, n, wh)}
                for k, i, n, wh in items]


# One registry per process, same "outlives any single server run" reasoning
# as `traffic.METER` — a colour assignment must survive an Apply & restart.
REGISTRY = DeviceRegistry()


# ═══════════════════════════ SESSION DURATION / RATE ═══════════════════════════
MIN_RATE_WINDOW_S = 5.0   # below this a rate is noise, not a measurement


def duration_and_rate(total_bytes: int, since: float, now: float) -> tuple[float, float | None]:
    """`(duration_s, mb_per_hour)` for the header line. `mb_per_hour` is
    `None` — never a wildly inflated number — for a session younger than
    `MIN_RATE_WINDOW_S`, where dividing by a near-zero duration would print
    something like "40000 MB/h" for three bytes sent in the first tick."""
    duration_s = max(0.0, now - since)
    if duration_s < MIN_RATE_WINDOW_S:
        return duration_s, None
    hours = duration_s / 3600.0
    mb = total_bytes / (1 << 20)
    return duration_s, mb / hours


def human_duration(seconds: float) -> str:
    """"2h 14m" / "14m" / "37s" — never more than two units, matching
    `traffic_window.py`'s own "X min Y s" away-gap style."""
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"
