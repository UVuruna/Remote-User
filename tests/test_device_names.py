"""DEVICE NAME GATE (T74) — the raw model CODE becomes the name he calls the
phone, exactly once per code, and NEVER becomes a guess.

Owner decision 2026-08-13. The Traffic window printed `SM-S938B (412x892)`
and `23073RPBFG (686x1098)`. He rejected a hand-written table and a bundled
offline database with one reason — it works only until a new phone appears —
and chose an ONLINE lookup, once per device, cached forever.

WHAT THIS GATE EXISTS TO PREVENT, and it is not "a name prints".

  * A GUESS. Rule 4 of the task and the whole reason the resolver has three
    outcomes instead of two: a wrong model name is worse than a code. An
    unknown code must keep the label it had before this feature existed.
  * A CACHE POISONED BY WEATHER. If a timeout, a dead link or a changed file
    were written down as "no such device", one offline evening would blind
    this PC to that phone forever — and the owner would never find out,
    because the failure looks exactly like the honest fallback.
  * A LOOKUP THAT RUNS AGAIN AND AGAIN. "At most ONCE per device code ever"
    is his decision verbatim; a phone reconnecting every few seconds must
    not fetch 4.7 MB every time, and a NEGATIVE answer must be remembered
    just as firmly as a positive one.
  * SOMETHING BLOCKING. `note()` runs on the asyncio event loop at `auth`
    time and the Qt GUI thread reads the answer. Neither may ever wait on
    a network fetch. Measured here against a deliberately slow fake.
  * A SECOND STORE. The answers live in the SAME registry file every other
    device fact lives in (`config.USER_DIR`), never a second hand-rolled
    LOCALAPPDATA lookup that could drift from it.

THE NETWORK IS FAKED THROUGHOUT. A gate that reached Google would be a gate
that fails when the line is down — which is precisely the condition this
module is written to survive, so testing it that way would be backwards. The
PARSER, however, is driven over REAL published bytes: `tests/fixtures/
supported_devices_slice.csv` is a genuine slice of Google's own file, kept
in its published UTF-16 encoding with its real header row, so a renamed
column or a changed encoding fails here rather than on his PC. Both of his
real devices are in that slice.

Every check below is proven by planting its own defect (project gate
methodology).

Run:  .venv\\Scripts\\python tests/test_device_names.py
"""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import device_names  # noqa: E402
import traffic_devices  # noqa: E402

FIXTURE = PROJECT / "tests" / "fixtures" / "supported_devices_slice.csv"

# His two real devices, and what Google's own list says they are.
HIS_PHONE, HIS_PHONE_NAME = "SM-S938B", "Samsung Galaxy S25 Ultra"
HIS_TABLET, HIS_TABLET_NAME = "23073RPBFG", "Redmi Pad SE"


def run_checks(title: str, checks) -> int:
    print(f"=== {title} ===")
    failed = 0
    for name, fn in checks:
        try:
            ok = fn()
        except Exception as e:
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"{title} FAILED — {failed} check(s).")
        return 1
    print(f"{title} PASSED")
    return 0


def _real_bytes() -> bytes:
    return FIXTURE.read_bytes()


# ═══════════════════════════ 1. THE PARSER, ON REAL BYTES ═══════════════════

def test_parses_real_published_bytes() -> bool:
    """PLANTED DEFECT: changing `CATALOGUE_ENCODING` to "utf-8" (the obvious
    "fix" someone makes when the file looks like mojibake) — the UTF-16 body
    then decodes to replacement noise, no column matches, and the table
    comes back EMPTY. Also caught: renaming `_COL_MODEL`."""
    table = device_names.parse_catalogue(_real_bytes())
    return len(table) > 10 and HIS_PHONE in table


def test_his_phone_resolves() -> bool:
    """His Samsung. The brand is NOT already in the marketing name, so the
    display rule must prefix it."""
    table = device_names.parse_catalogue(_real_bytes())
    return table.get(HIS_PHONE) == HIS_PHONE_NAME


def test_his_tablet_resolves() -> bool:
    """His Xiaomi/Redmi. PLANTED DEFECT: prefixing the brand
    unconditionally in `display_name` gives "Redmi Redmi Pad SE" — the exact
    reason that rule is conditional, and it is one of his two real
    devices."""
    table = device_names.parse_catalogue(_real_bytes())
    return table.get(HIS_TABLET) == HIS_TABLET_NAME


def test_display_name_rules() -> bool:
    return (device_names.display_name("Samsung", "Galaxy S25 Ultra")
            == "Samsung Galaxy S25 Ultra"
            and device_names.display_name("Redmi", "Redmi Pad SE") == "Redmi Pad SE"
            and device_names.display_name("Samsung", "") == ""
            and device_names.display_name("", "Some Pad") == "Some Pad")


def test_no_fuzzy_match() -> bool:
    """A near-miss code must resolve to NOTHING — rule 4, the most important
    promise in this round.

    THIS CHECK WAS REWRITTEN AFTER PLANTING PROVED IT MEASURED NOTHING. Its
    first version asked the parsed TABLE whether it contained `"SM-S938"`,
    which is trivially true of a dict and says nothing about the LOOKUP: a
    `startswith` fallback planted inside `resolve()` left all 24 checks
    green. It now drives the real `resolve()` — the function that would
    actually hand a phone the wrong name — over a code one character short
    of his Samsung and a code one suffix past it."""
    r = device_names.Resolver(fetch=FakeFetch(_real_bytes()))
    for near_miss in ("SM-S938", "SM-S938B-XYZ", "23073RPBF"):
        name, outcome = r.resolve(near_miss)
        if name is not None or outcome != device_names.Answer.ABSENT:
            return False
    return True


PARSER_CHECKS = [
    ("the REAL published bytes parse (UTF-16, real header)",
     test_parses_real_published_bytes),
    (f"his phone {HIS_PHONE} resolves to {HIS_PHONE_NAME}", test_his_phone_resolves),
    (f"his tablet {HIS_TABLET} resolves to {HIS_TABLET_NAME} (brand not doubled)",
     test_his_tablet_resolves),
    ("display_name prefixes the brand only when it is missing",
     test_display_name_rules),
    ("a near-miss code matches NOTHING — never a fuzzy name", test_no_fuzzy_match),
]


# ═══════════════════════════ 2. THE THREE-STATE ANSWER ══════════════════════

class FakeFetch:
    """A stand-in for the network. Counts calls, so "once per process" is a
    measurement rather than a claim."""

    def __init__(self, payload=None, error=None, delay=0.0):
        self.payload, self.error, self.delay = payload, error, delay
        self.calls = 0
        self._lock = threading.Lock()

    def __call__(self) -> bytes:
        with self._lock:
            self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return self.payload


def test_found_is_found() -> bool:
    r = device_names.Resolver(fetch=FakeFetch(_real_bytes()))
    name, outcome = r.resolve(HIS_PHONE)
    return name == HIS_PHONE_NAME and outcome == device_names.Answer.FOUND


def test_absent_when_the_list_was_read() -> bool:
    """A code the list genuinely does not carry: a real, recordable answer."""
    r = device_names.Resolver(fetch=FakeFetch(_real_bytes()))
    name, outcome = r.resolve("NO-SUCH-PHONE-9000")
    return name is None and outcome == device_names.Answer.ABSENT


def test_network_failure_is_undecided_never_absent() -> bool:
    """THE central check of this gate. PLANTED DEFECT: making `_catalogue()`
    return `{}` instead of `None` on a fetch error — every code then reads as
    ABSENT, the registry writes that down as a permanent negative, and one
    offline evening blinds this PC to that phone forever."""
    r = device_names.Resolver(fetch=FakeFetch(error=OSError("no route")))
    name, outcome = r.resolve(HIS_PHONE)
    return name is None and outcome == device_names.Answer.UNDECIDED


def test_empty_or_changed_file_is_undecided() -> bool:
    """A 200 that parses to zero rows is a CHANGED FILE, not an answer about
    his phone. PLANTED DEFECT: dropping the `if not table` guard makes this
    ABSENT, i.e. the same permanent poisoning by a different door — and this
    door opens by itself the day Google renames a column."""
    r = device_names.Resolver(fetch=FakeFetch(b"\xff\xfe"))   # valid UTF-16, no rows
    _, outcome = r.resolve(HIS_PHONE)
    return outcome == device_names.Answer.UNDECIDED


def test_catalogue_fetched_once_per_process() -> bool:
    """PLANTED DEFECT: removing the `self._table` memo re-downloads 4.7 MB
    for every single code."""
    fetch = FakeFetch(_real_bytes())
    r = device_names.Resolver(fetch=fetch)
    r.resolve(HIS_PHONE)
    r.resolve(HIS_TABLET)
    r.resolve("NO-SUCH-PHONE-9000")
    return fetch.calls == 1


def test_a_failed_fetch_is_not_memoized() -> bool:
    """The mirror of the check above: a FAILED read must NOT be remembered
    as the catalogue, or the first lookup after a boot with no network would
    disable the feature for the rest of the run."""
    fetch = FakeFetch(error=OSError("down"))
    r = device_names.Resolver(fetch=fetch)
    r.resolve(HIS_PHONE)
    r.resolve(HIS_TABLET)
    return fetch.calls == 2


ANSWER_CHECKS = [
    ("a known code answers FOUND with its name", test_found_is_found),
    ("a code the list really lacks answers ABSENT", test_absent_when_the_list_was_read),
    ("a NETWORK FAILURE answers UNDECIDED, never ABSENT",
     test_network_failure_is_undecided_never_absent),
    ("a changed/empty file answers UNDECIDED, never ABSENT",
     test_empty_or_changed_file_is_undecided),
    ("the 4.7 MB list is fetched at most ONCE per process",
     test_catalogue_fetched_once_per_process),
    ("a FAILED fetch is never memoized as the catalogue",
     test_a_failed_fetch_is_not_memoized),
]


# ═══════════════════════════ 3. NOTHING BLOCKS ══════════════════════════════

class CountingResolver(device_names.Resolver):
    """Counts ACCEPTED requests as well as fetches.

    Added after planting showed `test_resolved_once_never_again` measuring
    the wrong number: it counted FETCHES, and the per-process catalogue memo
    means a hundred repeat lookups still fetch once — so removing the
    `resolved` check from `note()` (the literal defect that check names) left
    it green. "Once per device code ever" is a statement about REQUESTS."""

    def __init__(self, fetch):
        super().__init__(fetch=fetch)
        self.requests = 0

    def request(self, code, on_resolved):
        accepted = super().request(code, on_resolved)
        if accepted:
            self.requests += 1
        return accepted


def _registry(path: Path, fetch) -> tuple:
    resolver = CountingResolver(fetch)
    reg = traffic_devices.DeviceRegistry(path=path, resolver=resolver)
    return reg, resolver


def _settle(resolver, timeout=5.0) -> None:
    """Wait for the worker to drain — TESTS may wait; production never does."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if resolver._queue.unfinished_tasks == 0:
            return
        time.sleep(0.01)


def test_note_never_blocks_on_the_network() -> bool:
    """`note()` runs on the asyncio event loop. PLANTED DEFECT: resolving
    INLINE in `note()` (the obvious simple implementation) makes this call
    take the fetch's full 2 s — every `auth` would stall the whole server
    loop for as long as Google takes to answer."""
    with tempfile.TemporaryDirectory() as d:
        fetch = FakeFetch(_real_bytes(), delay=2.0)
        reg, resolver = _registry(Path(d) / "devices.json", fetch)
        t0 = time.time()
        reg.note(412, 892, HIS_PHONE)
        elapsed = time.time() - t0
        _settle(resolver, timeout=6.0)
        return elapsed < 0.25


def test_readers_never_block_while_a_lookup_runs() -> bool:
    """The GUI thread's own promise: `all()` / `label_for_key()` must return
    at once even while a 2 s fetch is in flight — i.e. NOBODY may hold the
    registry lock across a network call.

    `note()` is driven from ANOTHER THREAD here, which is the only way this
    check can see the defect it names: called on this thread, a lock held
    across the fetch merely serialises with the reader and the timing looks
    innocent. Planting proved exactly that — the first version of this check
    stayed green while `note()` resolved inline under the lock."""
    with tempfile.TemporaryDirectory() as d:
        fetch = FakeFetch(_real_bytes(), delay=2.0)
        reg, resolver = _registry(Path(d) / "devices.json", fetch)
        noter = threading.Thread(
            target=lambda: reg.note(412, 892, HIS_PHONE), daemon=True)
        noter.start()
        time.sleep(0.3)          # the lookup is now inside the fetch
        t0 = time.time()
        reg.all()
        reg.label_for_key("412x892")
        elapsed = time.time() - t0
        noter.join(timeout=6.0)
        _settle(resolver, timeout=6.0)
        return elapsed < 0.25


THREAD_CHECKS = [
    ("note() returns instantly — the lookup never rides the event loop",
     test_note_never_blocks_on_the_network),
    ("the GUI's readers never wait on an in-flight fetch",
     test_readers_never_block_while_a_lookup_runs),
]


# ═══════════════════════════ 4. THE CACHE, IN HIS REGISTRY FILE ═════════════

def test_the_name_lands_in_the_label() -> bool:
    """End to end on his own phone: a code arrives on `auth`, and the label
    the Traffic window reads becomes the real model name."""
    with tempfile.TemporaryDirectory() as d:
        reg, resolver = _registry(Path(d) / "devices.json", FakeFetch(_real_bytes()))
        reg.note(412, 892, HIS_PHONE)
        _settle(resolver)
        return reg.label_for_key("412x892") == f"{HIS_PHONE_NAME} (412×892)"


def test_his_tablet_lands_too() -> bool:
    with tempfile.TemporaryDirectory() as d:
        reg, resolver = _registry(Path(d) / "devices.json", FakeFetch(_real_bytes()))
        reg.note(686, 1098, HIS_TABLET)
        _settle(resolver)
        return reg.label_for_key("686x1098") == f"{HIS_TABLET_NAME} (686×1098)"


def test_unresolved_keeps_todays_exact_label() -> bool:
    """RULE 4, measured: with no network the line must read EXACTLY what it
    read before this feature existed — the raw code and the resolution.
    PLANTED DEFECT: any fallback that invents or abbreviates a name here."""
    with tempfile.TemporaryDirectory() as d:
        reg, resolver = _registry(Path(d) / "devices.json",
                                  FakeFetch(error=OSError("down")))
        reg.note(412, 892, HIS_PHONE)
        _settle(resolver)
        return reg.label_for_key("412x892") == f"{HIS_PHONE} (412×892)"


def test_no_code_at_all_still_says_unknown() -> bool:
    with tempfile.TemporaryDirectory() as d:
        reg, resolver = _registry(Path(d) / "devices.json", FakeFetch(_real_bytes()))
        reg.note(412, 892, None)
        _settle(resolver)
        return reg.label_for_key("412x892") == "unknown device (412×892)"


def test_resolved_once_never_again() -> bool:
    """His decision verbatim — ONCE per device code ever. PLANTED DEFECT:
    dropping the `resolved` flag from the request condition in `note()`; a
    phone that reconnects ten times then queues ten lookups.
    Measured on the RESOLVER's REQUEST count, not the fetch's — the
    per-process catalogue memo hides repeats from the fetch counter, which
    is how the first version of this check stayed green under exactly the
    defect it names (found by planting, and the reason `CountingResolver`
    exists)."""
    with tempfile.TemporaryDirectory() as d:
        fetch = FakeFetch(_real_bytes())
        reg, resolver = _registry(Path(d) / "devices.json", fetch)
        for _ in range(6):
            reg.note(412, 892, HIS_PHONE)
            _settle(resolver)
        return resolver.requests == 1 and fetch.calls == 1


def test_a_negative_answer_is_cached_too() -> bool:
    """A code Google's list does not carry must be asked about ONCE. PLANTED
    DEFECT: recording only successful lookups (`if model:` around the write
    in `_on_resolved`) makes an unknown phone re-fetch on every connection
    for the life of the machine."""
    with tempfile.TemporaryDirectory() as d:
        fetch = FakeFetch(_real_bytes())
        reg, resolver = _registry(Path(d) / "devices.json", fetch)
        for _ in range(4):
            reg.note(412, 892, "NO-SUCH-PHONE-9000")
            _settle(resolver)
        entries = json.loads((Path(d) / "devices.json").read_text(encoding="utf-8"))
        entry = entries["412x892"]
        return (resolver.requests == 1 and entry["resolved"] is True
                and entry["model"] is None)


def test_an_undecided_answer_is_NOT_cached() -> bool:
    """The other half, and the one that protects him: a lookup that could
    not reach the list must be RETRIED on the next connection. PLANTED
    DEFECT: removing the UNDECIDED early-return from `_on_resolved` — the
    device is then marked resolved-with-no-name and can never be named
    again, on any later evening, with the network back."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "devices.json"
        broken = FakeFetch(error=OSError("down"))
        reg, resolver = _registry(path, broken)
        reg.note(412, 892, HIS_PHONE)
        _settle(resolver)
        stored = json.loads(path.read_text(encoding="utf-8"))["412x892"]
        if stored.get("resolved"):
            return False
        # The network comes back — a fresh run, same file.
        good = FakeFetch(_real_bytes())
        reg2 = traffic_devices.DeviceRegistry(
            path=path, resolver=device_names.Resolver(fetch=good))
        reg2.note(412, 892, HIS_PHONE)
        _settle(reg2._resolver)
        return reg2.label_for_key("412x892") == f"{HIS_PHONE_NAME} (412×892)"


def test_survives_a_restart_without_re_querying() -> bool:
    """"Cached forever" means across an Apply & restart, and it means the
    new process asks NOTHING. PLANTED DEFECT: not persisting `model` /
    `resolved` in `_save`'s entries — the name would come back only by
    re-downloading, every single start."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "devices.json"
        reg, resolver = _registry(path, FakeFetch(_real_bytes()))
        reg.note(412, 892, HIS_PHONE)
        _settle(resolver)
        fetch2 = FakeFetch(_real_bytes())
        reg2 = traffic_devices.DeviceRegistry(
            path=path, resolver=device_names.Resolver(fetch=fetch2))
        label = reg2.label_for_key("412x892")
        entry = reg2.note(412, 892, HIS_PHONE)
        _settle(reg2._resolver)
        return (label == f"{HIS_PHONE_NAME} (412×892)"
                and entry["model"] == HIS_PHONE_NAME
                and fetch2.calls == 0)


def test_one_file_only() -> bool:
    """No second store (the task's rule 1): after a full resolve, the
    registry's own file is the ONLY file in the user dir, and it carries the
    new fields itself."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "devices.json"
        reg, resolver = _registry(path, FakeFetch(_real_bytes()))
        reg.note(412, 892, HIS_PHONE)
        _settle(resolver)
        files = sorted(p.name for p in Path(d).iterdir())
        entry = json.loads(path.read_text(encoding="utf-8"))["412x892"]
        return (files == ["devices.json"]
                and entry["model"] == HIS_PHONE_NAME and entry["resolved"] is True)


def test_a_pre_T74_file_still_loads_and_resolves() -> bool:
    """A registry file written before this round has neither field. It must
    load (never crash), read as "never looked up", and resolve on the next
    connection — the same forward-compatibility promise
    `test_actions_migration.py` exists for, written as LITERAL old text
    rather than as a copy of what today's code produces."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "devices.json"
        path.write_text(json.dumps({
            "412x892": {"index": 0, "name": HIS_PHONE, "last_wh": [412, 892]},
        }), encoding="utf-8")
        reg, resolver = _registry(path, FakeFetch(_real_bytes()))
        reg.note(412, 892, HIS_PHONE)
        _settle(resolver)
        return (reg.label_for_key("412x892") == f"{HIS_PHONE_NAME} (412×892)"
                and reg.all()[0]["index"] == 0)


def test_a_new_code_on_the_same_slot_drops_the_old_name() -> bool:
    """The accepted resolution-collision, made safe: a DIFFERENT phone with
    the same CSS resolution must not inherit the first one's model name.
    PLANTED DEFECT: keeping `model`/`resolved` when the code changes in
    `note()` — his tablet would then be labelled as his phone, which is the
    exact "wrong name" rule 4 forbids."""
    with tempfile.TemporaryDirectory() as d:
        reg, resolver = _registry(Path(d) / "devices.json", FakeFetch(_real_bytes()))
        reg.note(412, 892, HIS_PHONE)
        _settle(resolver)
        reg.note(412, 892, HIS_TABLET)     # a different phone, same resolution
        _settle(resolver)
        return reg.label_for_key("412x892") == f"{HIS_TABLET_NAME} (412×892)"


CACHE_CHECKS = [
    (f"his phone's label becomes {HIS_PHONE_NAME!r}", test_the_name_lands_in_the_label),
    (f"his tablet's label becomes {HIS_TABLET_NAME!r}", test_his_tablet_lands_too),
    ("with no network the label is EXACTLY today's code + resolution",
     test_unresolved_keeps_todays_exact_label),
    ("no code at all still reads 'unknown device'", test_no_code_at_all_still_says_unknown),
    ("a resolved code is never looked up again", test_resolved_once_never_again),
    ("a NEGATIVE answer is cached just as firmly", test_a_negative_answer_is_cached_too),
    ("an UNDECIDED answer is NOT cached — it retries later",
     test_an_undecided_answer_is_NOT_cached),
    ("the answer survives a restart, and the new process asks nothing",
     test_survives_a_restart_without_re_querying),
    ("one file only — the existing registry, with new fields", test_one_file_only),
    ("a pre-T74 registry file still loads and resolves",
     test_a_pre_T74_file_still_loads_and_resolves),
    ("a different code on the same slot never inherits the old name",
     test_a_new_code_on_the_same_slot_drops_the_old_name),
]


if __name__ == "__main__":
    failed = 0
    failed += run_checks("PARSER (real published bytes)", PARSER_CHECKS)
    failed += run_checks("THE THREE-STATE ANSWER", ANSWER_CHECKS)
    failed += run_checks("NOTHING BLOCKS", THREAD_CHECKS)
    failed += run_checks("THE CACHE, IN HIS REGISTRY FILE", CACHE_CHECKS)
    if failed:
        sys.exit(1)
    print("DEVICE NAME GATE PASSED — his phone and his tablet resolve, once "
          "each, cached forever; a failure stays an honest code.")
