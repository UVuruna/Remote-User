# tests/

End-to-end regression gates PLUS the four project guard tests (rules/CODE.md
→ Enforcement). Per rules/DOCS.md's tier table, every file in this folder is
**tests tier — this folder doc is the only doc any of them get**, individual
files are not otherwise documented below except by name and one line.

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
reachability with the cursor-offset margin, keyboard capture (typed
text + the Shift+Enter new-row rule), **the /ping contract** — the
endpoint must answer EXACTLY 204: the Android shell's reachability probe
counts only 204 as "the PC answered", because captive portals on foreign
Wi-Fi answer any request with a 2xx/redirect login page (live failure
2026-07-27); a drift to 200 would strand every phone — and **the injection
tripwire** (`InjectionMonitor` decision logic): Windows silently discards
all injected input from a non-elevated process while an elevated window
has focus (UIPI, live failure 2026-07-29 — SendInput "succeeds", the phone
looks healthy, the mouse is dead); the monitor must alarm on exactly the
configured miss streak, ignore small jumps, and re-arm after a success —
plus the WIRING: the real `InputInjector.move()` (with `SendInput` stubbed
out, so the build machine's cursor is never touched) must raise the alarm
that the web layer forwards to the phone, and clear it once read.

The control layout comes from `tests/fixtures/actions.json` — pinned on
purpose: the repo `actions.json` is the owner's hand-edited file, and a
layout edit there must never block a build.

Run directly:

```
.venv\Scripts\python tests/test_input_pipeline.py
```

Requires `pip install playwright` + `playwright install chromium` (dev/build
machine only — nothing of this ships in the app).

### Guard tests (THE LAWS — rules/CODE.md → Enforcement, rules/DOCS.md → Enforcement)
Four standard-named guard tests, a fast runner, and a small shared helper —
installed 2026-08-01 alongside the MD-First 2.0 docs migration:

- `_guards_common.py` — `iter_source_files()` / `iter_doc_files()`, pruning
  `.venv`/`build`/`dist`/etc. during the walk (not after) so the guards stay
  fast.
- `test_structure_law.py` — THE STRUCTURE LAW: no source file (`.py`/`.js`/
  `.ts`/`.kt`/`.html`/`.css`) over ~1,000 lines outside the `RATCHET`
  allowlist (currently empty).
- `test_config_sections.py` — THE CONFIG SECTION LAW: every top-level
  definition in a `CONFIG_FILES` entry sits under a `# ══...══` section
  banner; no post-definition table patching; no duplicate dict keys.
  `CONFIG_FILES` = `server/config.py`, `server/gui/theme.py`.
- `test_docs_coverage.py` — every source file has the `__about`/`__flow`
  docs its tier requires; the tier lists here are the project's single
  source of truth (update this file in the same commit as any tier change).
- `test_doc_links.py` — every relative link in every `.md` resolves to a
  real file, and every `.md` is reachable from `README.md`.
- `run_guards.py` — runs all four (or, with `--fast`, just structure +
  config-sections — the PostToolUse hook's speed budget); exits 2 on any
  failure. Wired into `.claude/settings.json` (PostToolUse `--fast`,
  Stop full). Run directly: `python tests/run_guards.py`.

These are plain `assert`-based functions (pytest-discoverable, but
`run_guards.py` calls them directly — no pytest dependency, since neither
this project's venv nor `requirements.txt` install pytest).

## Connections

### Uses
- [Client (folder)](../client/___client.md) — the page under test, served from disk
- [Web Layer](../server/__about/web.md) — the real FastAPI app + protocol handler

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
  gate ([Code Rules](../../../rules/CODE.md) → No Error Masking).
- **Guards prune, not filter.** `_guards_common.py` excludes `.venv` et al.
  by pruning `os.walk`'s `dirnames` in place, never descending into them —
  filtering AFTER an unpruned walk was measured at 2.3s+ against this
  project's `.venv` (tens of thousands of files), over the guard runner's
  ~2s budget; pruning brought the full run to ~0.3s.
