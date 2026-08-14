# Traffic Devices

**Module:** [traffic_devices.py](../traffic_devices.py) ·
**Folder:** [server](../___server.md)

## Purpose

Turns "a screen resolution arrived on `auth`" into a stable device identity,
a persisted colour slot and a human label — the one thing `traffic.py` (byte
counting), `traffic_history.py` (CSV attribution) and
[Traffic Window](../gui/__about/traffic_window.md) (painting) would
otherwise each have to decide separately, and disagree about.

## Why it exists (owner request 2026-08-13)

Beside "this session 152.4 MB" he wants the session's LENGTH, its rate in
MB/h, and — since more than one phone can use this app — WHICH device sent
what: named where possible ("a device with this resolution was used, a
device with that resolution … even better with a name like Samsung Galaxy
S5 Ultra"), and coloured differently on the chart per device, "so we can see
the difference in how much is sent to a device with a smaller resolution".

## Key Functions

- `device_key(w, h)` — the stable identity: whole-pixel CSS resolution,
  `"{w}x{h}"`. Never keyed by name (see Design Decisions).
- `DeviceRegistry.note(w, h, name)` — one call per `auth`
  ([Web Layer](web.md)'s only call site, via `traffic.TrafficMeter.note_device`)
  — assigns a fresh, PERSISTED colour slot the first time a resolution is
  ever seen on this PC, records/updates the raw model CODE the phone
  reported, and REQUESTS the one online name lookup if that code has never
  had one (T74). The request only enqueues — `note()` runs on the asyncio
  event loop and never waits for it.
- `DeviceRegistry._on_resolved(code, model, outcome)` — the answer, arriving
  later on [Device Names](device_names.md)' worker thread. Writes `model` +
  `resolved` against every entry carrying that code and persists them.
  An `UNDECIDED` outcome is deliberately NOT written down.
- `DeviceRegistry.index_for(key)` / `.label_for_key(key)` / `.all()` — what
  [Traffic Window](../gui/__about/traffic_window.md) reads to colour the
  chart and to print the device list.
- `duration_and_rate(total_bytes, since, now)` — the session-length + MB/h
  header line's arithmetic, held here rather than in the paint file so the
  gate can run it without Qt.
- `REGISTRY` — the one process-wide instance, same "outlives any single
  connection" reasoning as `traffic.METER`.

## Design Decisions

- **Identity is the RESOLUTION alone, never the name.** A name can arrive
  late (`navigator.userAgentData`'s promise resolves after first paint,
  `client/dictation-card.js`'s own pattern, reused verbatim in
  `client/connection.js`) or never at all. Keying by something that can
  change mid-session would split ONE phone into two colours the moment its
  better name lands. A NAME, once learned, only ever REPLACES a blank one —
  it never overwrites an earlier name, and it never changes the KEY.
- **Two different physical devices sharing an exact resolution collide into
  one slot.** Accepted, not fixed — nothing here can tell them apart
  without a name, and a richer key (resolution+model) would instead split
  ONE phone into two slots the day its `userAgent` model token differs from
  what `userAgentData` later resolves.
- **Persisted across restarts**, same shape as `layout_history.py`
  (`%LOCALAPPDATA%/VibeCoder/traffic_devices.json`, via `config.USER_DIR`):
  a colour that keeps sliding on every server restart is exactly as useless
  as no colour at all.
- **The human model name is CACHED HERE, looked up ONCE, and never
  guessed** (T74, owner decision 2026-08-13). He rejected a hand-written
  table and a bundled database alike — a snapshot works only until a new
  phone appears — so the name comes from an online lookup
  ([Device Names](device_names.md)) performed at most once per code ever.
  Two new fields in the SAME persisted file, never a second store: `model`
  (the resolved name, or `None`) and `resolved` (the lookup has been
  ANSWERED — including the negative answer for a code Google's list does not
  carry, so an unknown phone is asked about once and not on every
  connection). A lookup that could not reach the list writes NEITHER: that
  is not an answer, and recording it as one would blind this PC to that
  phone forever because it was offline on the wrong evening.
- **The label has a strict order of honesty and no fourth case:** resolved
  `model` → the raw `name` code → `unknown device`, always with the
  resolution. An unresolved device keeps EXACTLY the label it had before
  T74 — a wrong model name is worse than a code.
- **A different code arriving on the same slot drops the resolved name.**
  Two physical devices sharing a CSS resolution is the accepted collision
  this module has always named; what may not happen is the second phone
  inheriting the first one's model name.
- **The GUI needs no signal.** [Traffic Window](../gui/__about/traffic_window.md)
  rebuilds its device rows on its own 1 s `QTimer`, reading `all()` under the
  same lock the worker writes under, so a name that lands mid-session
  appears on the next tick.
- **Colour comes from `gui.theme.DEVICE_COLORS`** — the existing
  `config.SET_COLORS` palette, not a new table; see that module's own
  docstring for why it is already proven legible on both palettes.

## Used by

- [Traffic](traffic.md) — `TrafficMeter.note_device()` is the one call site
- [Traffic History](traffic_history.md) — the CSV `device` column this
  module's keys populate
- [Traffic Window](../gui/__about/traffic_window.md) — per-device chart
  colour and the header's device list
- `tests/test_traffic_devices.py` — the gate, fail-closed in `setup/gates.py`
- `tests/test_device_names.py` — the T74 name-lookup + cache gate,
  fail-closed in `setup/gates.py` (0b12/6)

## Uses

- [Device Names](device_names.md) — the one online lookup, off every thread
  that matters
