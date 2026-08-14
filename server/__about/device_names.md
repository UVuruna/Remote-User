# Device Names

**Module:** [device_names.py](../device_names.py) ·
**Folder:** [server](../___server.md)

## Purpose

Turns an Android **model code** — the raw `Build.MODEL` token the phone sends
on `auth` (`SM-S938B`, `23073RPBFG`) — into the name a human calls that phone
("Samsung Galaxy S25 Ultra", "Redmi Pad SE"), by an **online lookup performed
at most once per code, ever**.

It owns the LOOKUP only. The cache, the identity and the label belong to
[Traffic Devices](traffic_devices.md), which is this module's one caller.

## Why it exists (owner decision 2026-08-13, T74)

The Traffic window printed `SM-S938B (412x892)` and `23073RPBFG (686x1098)`
and he asked why it does not say the real model name. He was offered a
hand-written table and a bundled offline database and **rejected both**, with
one reason: such a snapshot works only until a new phone appears — it can
only ever cover the phones that existed on the day it was written. His
decision was an online lookup, once per device, cached forever.

## The source, and why it survives "a new phone appears"

`https://storage.googleapis.com/play_public/supported_devices.csv` —
**Google's own published list** of every device supported by Google Play.
Columns: Retail Branding, Marketing Name, Device, **Model**. The `Model`
column is exactly the token the phone already sends us, so there is no
transformation and no fuzzy matching anywhere in this module.

Checked against the hard constraints rather than assumed:

| Constraint | How this source meets it |
|---|---|
| No payment for any required part | A static object on Google's public CDN — no account, no quota, no billing |
| No API key the user must obtain | A plain anonymous `GET` |
| Must answer for **both** of his real devices | Measured before implementation: `SM-S938B` → Samsung / Galaxy S25 Ultra; `23073RPBFG` → Redmi / Redmi Pad SE. 53,383 rows, 4.7 MB, ~0.3 s |
| Must survive a new phone appearing | Fetched **on demand**, so the copy consulted next year is the copy Google publishes next year. A device enters this list when it enters Google Play — before he can buy it |

**Rejected alternative:** `cdn.jsdelivr.net/gh/bsthen/device-models/devices.json`
(3.0 MB, also key-free, also answered both codes correctly in the same
measurement). It is a third party re-publishing this very CSV — a middleman
who can stop updating, rename the file or delete the repo, in exchange for a
slightly smaller download. A bad trade for the one property he asked for.

## Key Functions

- `parse_catalogue(raw)` — `{model code -> display name}` from the published
  CSV bytes. Kept separate from the fetch so the gate can drive the real
  parser over real bytes with no network call.
- `display_name(brand, marketing)` — the brand is prefixed only when the
  marketing name does not already start with it: `Redmi` + `Redmi Pad SE`
  must not read "Redmi Redmi Pad SE", and that is one of his two devices.
- `Resolver.request(code, on_resolved)` — **non-blocking**, called on the
  asyncio event loop; enqueues to a lazily-started daemon worker.
- `Resolver.resolve(code)` — `(name, Answer.*)`, blocking, worker only.
- `RESOLVER` — the one process-wide instance; the per-process catalogue memo
  is why there is only one.

## Design Decisions

- **Three outcomes, not two.** `Answer.FOUND` / `Answer.ABSENT` /
  `Answer.UNDECIDED`. Only the first two are ever written down. If a timeout,
  a dead link or a changed file counted as "no such device", one offline
  evening would permanently blind this PC to a phone the list names
  perfectly — a cache poisoned by weather, and indistinguishable from the
  honest fallback while it happened.
- **A zero-row parse is UNDECIDED, never ABSENT.** A 200 that parses to
  nothing is a *changed file* — the day Google renames a column, this must
  degrade to "no answer", not to "none of your phones exist".
- **No guessing, ever.** No prefix matching, no closest row, no near miss. A
  wrong model name is worse than a code (the task's rule 4), so an
  unresolved device keeps exactly the label it had before this module
  existed.
- **Nothing runs on a thread that matters.** `request()` only enqueues; the
  worker is a daemon, so it can never hold the app open at quit. The answer
  arrives by callback and the Traffic window needs **no signal** for it — it
  already rebuilds its device rows on its own 1 s `QTimer`.
- **The fetch is injectable** so the gate can fake the network. A test that
  reached Google would fail whenever the line was down, which is precisely
  the condition this module is written to tolerate.

## Honest limits

- The CSV is 4.7 MB and a lookup that needs it pays that **once per server
  run** (the parsed table is memoized for the process; the answers are on
  disk forever).
- A PC that is offline resolves nothing, and the window keeps printing the
  raw code and the resolution.
- A phone whose code is genuinely absent from Google's list is asked about
  once and then never again — it keeps its code as its label.

## Used by

- [Traffic Devices](traffic_devices.md) — the only caller
  (`DeviceRegistry.note()` requests, `_on_resolved` caches)
- `tests/test_device_names.py` — the gate, fail-closed in `setup/gates.py`
  (0b12/6)
