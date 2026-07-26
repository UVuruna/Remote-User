# tests/

End-to-end regression gates. These exist because input bugs shipped in
releases while every file looked correct in review — the pipeline is now
PROVEN before anything is packaged (the build runs these fail-closed).

## Files

### `test_input_pipeline.py` — Input Pipeline Gate
The REAL client page and the REAL server app, driven by a REAL headless
Chromium with touch emulation; only injection is faked (a recorder replaces
`SendInput`). Every scenario walks the full chain:

```
touch on the page → Pointer Events → WebSocket protocol → FastAPI handler → injector call
```

Scenarios: cursor steering (and the no-tap decree — a canvas touch never
clicks), the Click button (left), the Right button (right click), a chord
button, **the stolen-tap rescue** (Android ends edge-zone touches with
`pointercancel` — a no-travel cancel must still fire or buttons die
on-device, the 2026-07-26 live failure) and its inverse (**a system swipe
crossing a button — real travel, then cancel — must NOT fire**), edge
reachability with the cursor-offset margin, and keyboard capture (typed
text + the Shift+Enter new-row rule).

The control layout comes from `tests/fixtures/actions.json` — pinned on
purpose: the repo `actions.json` is the owner's hand-edited file, and a
layout edit there must never block a build.

Run directly:

```
.venv\Scripts\python tests/test_input_pipeline.py
```

Requires `pip install playwright` + `playwright install chromium` (dev/build
machine only — nothing of this ships in the app).

## Connections

### Uses
- [Client App](../client/app.md) — the page under test, served from disk
- [Web Layer](../server/web.md) — the real FastAPI app + protocol handler

### Used by
- [Setup (folder)](../setup/___setup.md) — `build.py` runs this as the
  fail-closed INPUT GATE before packaging; a broken click path cannot ship

## Design Decisions

- **Real browser, fake injector.** Unit-testing the JS or the protocol alone
  kept missing the class of bug that actually shipped (handlers correct,
  events never delivered). Touch emulation in real Chromium exercises the
  same Pointer Events pipeline the WebView uses, headless and screen-safe.
- **Fail-closed in the build.** A missing playwright/Chromium fails the build
  rather than skipping the gate — a silently skipped gate is the same as no
  gate (root Rule #1).
