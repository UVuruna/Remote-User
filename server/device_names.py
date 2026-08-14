"""Turn an Android MODEL CODE into the name a human calls that phone.

Owner decision 2026-08-13 (T74). The Traffic window printed `SM-S938B
(412x892)` and `23073RPBFG (686x1098)` and he asked why it does not say the
real model name. He REJECTED both a hand-written table and a bundled offline
database, with one reason — it works only until a new phone appears:
"funkcioniše samo dok se ne pojavi novi telefon" (lang-ok: owner quote) — a
snapshot only ever covers a percentage, and the percentage it covers is
exactly the phones that already existed on the day it was written. His
decision: an ONLINE lookup, at most ONCE per device code ever, cached
forever.

THE SOURCE, and why it survives "a new phone appears"
─────────────────────────────────────────────────────
`https://storage.googleapis.com/play_public/supported_devices.csv` — GOOGLE'S
OWN published list of every device supported by Google Play. Four columns:
Retail Branding, Marketing Name, Device, Model. `Model` is exactly the token
Android puts in `Build.MODEL`, which is exactly the token Chrome puts in its
User-Agent, which is exactly what `client/connection.js` already sends us on
`auth`. No transformation, no fuzzy matching, no near miss.

It was chosen against the hard constraints, and each was checked rather than
assumed:

  * NO PAYMENT for any required part (owner rule). It is a static object on
    Google's public CDN — no account, no quota, no billing relationship.
  * NO API KEY the user must obtain. A plain anonymous GET. Anything that
    needed the owner to register somewhere would fail this project's
    "the app installs/drives all dependencies — the user never side-installs
    anything" rule the moment the key expired.
  * IT ANSWERS FOR BOTH OF HIS REAL DEVICES — measured, not assumed, before
    a line of this module was written:
        SM-S938B   -> Samsung / Galaxy S25 Ultra   (row: pa3q)
        23073RPBFG -> Redmi   / Redmi Pad SE       (row: xun)
    53,383 rows, 4.7 MB, fetched in ~0.3 s.
  * IT ANSWERS HIS OBJECTION. This is not a snapshot we ship: it is fetched
    ON DEMAND, so the copy consulted for a phone bought next year is the copy
    Google publishes next year. A device enters this list when it enters
    Google Play, which is before the owner can buy it — the "new phone" case
    is the case it is best at, and it is the one case a bundled database can
    never win.

The alternative that was seriously considered and REJECTED:
`cdn.jsdelivr.net/gh/bsthen/device-models/devices.json` (3.0 MB, also
key-free, also answered both codes correctly in the same measurement). It is
a third party re-publishing this very CSV. It adds a middleman who can stop
updating, rename the file or delete the repo, in exchange for a slightly
smaller download — a bad trade for the one property the owner asked for,
which is that it keeps working for phones nobody has heard of yet.

HONEST LIMIT, stated rather than discovered later: the CSV is 4.7 MB, and a
lookup that needs it pays that once per SERVER RUN (the parsed table is held
in memory for the process; the answers are held on disk forever). A PC that
is offline resolves nothing and the Traffic window keeps printing exactly
what it prints today — the raw code and the resolution. That is deliberate,
and it is rule 4 of this task: a WRONG model name is worse than a code, so
there is no guessing, no prefix matching and no "closest row".

WHY A NETWORK FAILURE IS NOT A NEGATIVE ANSWER
──────────────────────────────────────────────
The registry caches a negative (`resolved` with no name) so an unknown code
is not re-queried on every connection forever. But a negative may ONLY be
recorded when the catalogue was really READ and really did not contain the
code. If a timeout or a dead link counted as "no such device", one offline
start would permanently blind this PC to a phone the CSV names perfectly —
a cache poisoned by weather. `resolve()` therefore returns a three-state
answer (`Answer.FOUND` / `Answer.ABSENT` / `Answer.UNDECIDED`) and only the
first two are ever written down.

NOTHING HERE RUNS ON A THREAD THAT MATTERS
──────────────────────────────────────────
`Resolver.request()` is called from `DeviceRegistry.note()`, which runs on
the asyncio event loop at `auth` time, and its answer is read by the Qt GUI
thread. So the request only ever ENQUEUES: a lazily-started daemon worker
does the fetch, and the answer arrives by callback. The Traffic window needs
no signal for it — it already rebuilds its device rows on its own 1 s
`QTimer` (`gui/traffic_window.py` `REFRESH_MS`), so a name that lands
mid-session simply appears on the next tick.
"""

import csv
import io
import logging
import queue
import threading
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

# Google's own published Play-supported-devices list. See the module
# docstring for why this source and not a third-party mirror.
CATALOGUE_URL = "https://storage.googleapis.com/play_public/supported_devices.csv"

# Generous: this runs on a background worker nobody is waiting for, and a
# 4.7 MB body on a slow line is a real case. Nothing user-facing blocks on it.
TIMEOUT_S = 30

# The file is published as UTF-16LE with a BOM (measured; the HTTP header
# says `text/csv; charset=utf-16le`). Decoding it as UTF-8 yields garbage
# rather than an exception, so the encoding is pinned here deliberately.
CATALOGUE_ENCODING = "utf-16"

_COL_BRAND, _COL_MARKETING, _COL_MODEL = "Retail Branding", "Marketing Name", "Model"


class Answer:
    """A resolution has THREE outcomes, not two — see the module docstring's
    "why a network failure is not a negative answer"."""

    FOUND = "found"          # the catalogue was read and names this code
    ABSENT = "absent"        # the catalogue was read and does NOT name it
    UNDECIDED = "undecided"  # we could not read the catalogue at all


def display_name(brand: str, marketing: str) -> str:
    """How the two catalogue columns become the one string he reads.

    `Samsung` + `Galaxy S25 Ultra` must read "Samsung Galaxy S25 Ultra", but
    `Redmi` + `Redmi Pad SE` must NOT read "Redmi Redmi Pad SE" — Xiaomi's
    sub-brand repeats itself in the marketing name and one of his two real
    devices is exactly that case. So the brand is prefixed only when the
    marketing name does not already begin with it.
    """
    brand, marketing = (brand or "").strip(), (marketing or "").strip()
    if not marketing:
        return ""
    if not brand or marketing.lower().startswith(brand.lower()):
        return marketing
    return f"{brand} {marketing}"


def _fetch_catalogue_bytes() -> bytes:
    with urllib.request.urlopen(CATALOGUE_URL, timeout=TIMEOUT_S) as response:
        return response.read()


def parse_catalogue(raw: bytes) -> dict[str, str]:
    """`{model code -> display name}` from the published CSV bytes.

    Kept separate from the fetch so the gate can drive the REAL parser over
    REAL catalogue bytes without a network call — the parser is where a
    silent breakage would live (a renamed column, a changed encoding), and a
    gate that faked the parse too would prove nothing about it.
    """
    text = raw.decode(CATALOGUE_ENCODING, errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    table: dict[str, str] = {}
    for row in reader:
        code = (row.get(_COL_MODEL) or "").strip()
        if not code:
            continue
        name = display_name(row.get(_COL_BRAND, ""), row.get(_COL_MARKETING, ""))
        if name:
            # First row wins: the same Model can appear under several Device
            # rows (regional variants), and they carry the same marketing
            # name — taking the first avoids depending on file order for a
            # value that does not differ.
            table.setdefault(code, name)
    return table


class Resolver:
    """One background worker that turns model codes into names.

    `request()` never blocks and never touches the network — it is called on
    the asyncio event loop. The worker thread is started lazily on the first
    request, so a PC where no phone ever connects never spawns it, and it is
    a daemon so it can never hold the app open at quit (constraint 23's
    spirit: nothing of ours outlives the session).

    `fetch` is injectable for the gate. The network is NEVER called from a
    test — that would make the suite depend on Google being reachable, which
    is precisely the failure mode this module is written to tolerate.
    """

    def __init__(self, fetch=_fetch_catalogue_bytes) -> None:
        self._fetch = fetch
        self._queue: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._table: dict[str, str] | None = None   # per-process memo
        self._inflight: set[str] = set()

    # ── called on the event loop ────────────────────────────────────────
    def request(self, code: str, on_resolved) -> bool:
        """Ask for `code`'s name. Returns whether the request was accepted
        (False = nothing to do: no code, or one already being looked up).

        `on_resolved(code, name, outcome)` is called ON THE WORKER THREAD.
        Its implementation must therefore take its own lock — which
        `DeviceRegistry` does, the same lock its GUI-thread readers take.
        """
        code = (code or "").strip()
        if not code:
            return False
        with self._lock:
            if code in self._inflight:
                # A phone reconnecting every few seconds must not queue the
                # same lookup a hundred times behind one 4.7 MB fetch.
                return False
            self._inflight.add(code)
            self._ensure_worker()
        self._queue.put((code, on_resolved))
        return True

    def _ensure_worker(self) -> None:
        """Caller holds `self._lock`."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run, name="device-names", daemon=True)
        self._thread.start()

    # ── the worker thread ───────────────────────────────────────────────
    def _run(self) -> None:
        while True:
            code, on_resolved = self._queue.get()
            try:
                name, outcome = self.resolve(code)
                on_resolved(code, name, outcome)
            except Exception:
                # A diagnostic nicety may never take the app down, and it may
                # never kill its own worker either — the next phone deserves
                # its lookup.
                logger.exception("device_names: resolving %r failed", code)
            finally:
                with self._lock:
                    self._inflight.discard(code)
                self._queue.task_done()

    def resolve(self, code: str) -> tuple[str | None, str]:
        """`(name, Answer.*)`. Blocking — worker thread only."""
        table = self._catalogue()
        if table is None:
            return None, Answer.UNDECIDED
        name = table.get(code)
        if name:
            logger.info("device_names: %s is %s", code, name)
            return name, Answer.FOUND
        logger.info("device_names: %s is not in Google's device list", code)
        return None, Answer.ABSENT

    def _catalogue(self) -> dict[str, str] | None:
        """The parsed table, fetched at most once per process. `None` means
        we could not read it — NEVER an empty table, because an empty table
        would make every code look ABSENT and poison the disk cache with
        negatives for phones the real list names (see the module docstring)."""
        if self._table is not None:
            return self._table
        try:
            raw = self._fetch()
        except (urllib.error.URLError, OSError, ValueError) as e:
            logger.info("device_names: device list unreachable (%s) — the "
                        "code stands as its own label", e)
            return None
        try:
            table = parse_catalogue(raw)
        except Exception:
            logger.exception("device_names: could not parse the device list")
            return None
        if not table:
            # A 200 that parsed to nothing is a CHANGED FILE, not an answer.
            logger.warning("device_names: the device list parsed to zero rows "
                           "— treating it as unreadable, never as 'unknown'")
            return None
        self._table = table
        return table


# One resolver per process, like `traffic_devices.REGISTRY` itself: the
# per-process catalogue memo is the whole point, and a second instance would
# pay the 4.7 MB again.
RESOLVER = Resolver()
