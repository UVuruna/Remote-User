# Page Version — the page must not outlive its own protocol

**File:** `client/page-version.js` · **Gate:** `tests/test_zoom_crop.py`
(section 12) · **Wired by:** `client/connection.js` (`config` handler),
state in `client/state.js` (`pageServedVersion`).

## Why it exists (T94, owner report 2026-08-14)

The PC updates ITSELF mid-evening (`update_handover`) while the phone's page
is a long-lived DOCUMENT — constraint 8 closes only the SOCKET on every hide,
so the phone reconnects last hour's client to this hour's server. Measured
live in the owner's own server log and reproduced byte for byte in a
real-browser harness: the v0.0.205 page's zoom-echo guard, facing the
v0.0.209 server, reset its view on every `config` (the old guard demanded a
`stream_region` that echoes the pinched rect; the new server correctly never
sends one) and its settle watcher then told the server to drop the zoom —
his "the zoom does not survive two seconds", ~0.5 s per pinch, twice in the
log at 20:32.

No gate that imports only the current tree can even express that failure —
two versions have to face each other — so the rule is structural and ends
the whole class, not one symptom.

## The rule

`pageVersionStep(servedVersion, configVersion)` → `{servedVersion, reload}`:

- the FIRST `config` carrying an `app_version` arms the memory, quietly;
- every later config with the SAME version changes nothing (reconnects
  restate `config` constantly);
- ANY different version — newer or older alike, a rollback changes the wire
  just as surely — answers `reload: true`; the caller re-fetches the
  document (`location.reload()`) BEFORE acting on the frame, so a stale page
  never rebuilds its pipeline on a foreign protocol;
- a config with NO version (an older server) decides nothing and never arms
  the memory.

Pure — no DOM, no socket — so the gate runs a whole document lifetime
through the real module. `connection.js` owns the one side effect and its
ordering (reload + `return` before `initMse`).

## Honest limits

- The fix cannot reach a page that predates it: the v0.0.205 document that
  hit this live has no such code and heals only by its next full page load.
  Every page from this version on heals itself.
- The reload costs one visible page load at the moment of a PC update —
  which is exactly when the picture blinks anyway (the update restarts the
  server and every session with it).
