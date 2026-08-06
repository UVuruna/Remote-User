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

### `test_layout_audit.py` — Layout Audit (THE SPACE & LEGIBILITY LAW)
The real page in a real headless Chromium at phone sizes (portrait 412×915,
landscape 915×412): every overlay panel is opened and measured — the card
fully inside the viewport, no horizontal page overflow, nothing clipped
inside it. Covers the Quality panel, the Sets picker, the Dictation card,
the Aspect panel (incl. the Move handle's hit size), the layout list with
its rename button, the Rename card and the creation panel's Name field.
Also checks `window_manager._fit_rect` purely: the placed region never
leaves its box, at any aspect or `pos`. Proof source for
`.claude/layout-proof.md`. The Name fields are WRAPPING textareas because
this audit caught the one-line version hiding most of a window title behind
its own horizontal scroll (2026-08-05). Also checks the D-PAD BUTTONS: a set's
pool may hold reserve commands whose names are longer than the shipped four
("Copy path", "Go to file"), the law forbids eliding them, so the label wraps —
and the wrapped label must still sit fully inside its 58 px button.

Run: `.venv\Scripts\python tests/test_layout_audit.py`

### `test_layout_audit_qt.py` — Layout Audit, Qt windows (THE SPACE & LEGIBILITY LAW)
The runtime half of the law for the DESKTOP app (MIGRATE-LAYOUT.md step 2,
owner go 2026-08-05). Every Qt window the project has — `MainWindow`,
`ControlsEditor`, `ChordRecorder` — is built offscreen in its FULLEST
realistic state (a running server with a Tailscale URL and the longest guided
text; the set with the longest command pool), shown at its DECLARED minimum
and at +50%, and its whole widget tree measured for: CLIPPED (a widget with
less room than it minimally needs), ELIDED (text wider than its element),
ITEM CUT (a list/table row wider than its column — Qt's item views truncate
silently, and an item is not a QWidget, so the widget checks cannot see it),
SCROLL+SLACK (something scrolling while a spacer in the same window holds
unused space), plus the law's precondition: a declared, computed minimum size.

Three measurement notes, each about measuring the RIGHT thing rather than
loosening a tolerance: a `QHeaderView`'s `minimumSizeHint` is an
orientation-blind square (68×68 whatever its sections hold), so only the
header's own axis is compared, against Qt's size hint and the font; a `QLabel`
is charged no control padding, because it paints straight into its
contentsRect; and a container of WRAPPING children has no single minimum
height (`minimumSizeHint` quotes it at the narrowest width), so only its width
is checked there — the vertical truth is measured element by element by the
wrapped-text branch.

Run: `.venv\Scripts\python tests/test_layout_audit_qt.py` — also a full-run
guard in `run_guards.py`.

### `test_presence.py` — Presence Gate
Proves that the phone leaving work mode frees the owner's desk: layout
members are always-on-top while the phone shows them, and before 2026-08-05
only a CLEAN socket close ever ended that — which a locked phone rarely
manages (Wi-Fi sleeps, the connection just goes quiet), so the windows kept
hovering over everything at the desk. Checks the heartbeat holding a
session, the watchdog ending a silent one (members minimized, socket closed
4408), an announced excursion (image picker, camera, voice) NOT counting as
a leave, an announced leave acting at once, `_leave_session` being
idempotent, and the resume pointer (`LayoutRegistry.last_focus`) surviving
rename/remove and forgetting on a deliberate Desktop choice. No browser and
no real windows — the window calls are stubbed.

Run: `.venv\Scripts\python tests/test_presence.py` — also a fail-closed step
in `build.py` (0c/6).

### Guard tests (THE LAWS — rules/CODE.md → Enforcement, rules/DOCS.md → Enforcement)
Five standard-named guard tests, a fast runner, and a small shared helper —
four installed 2026-08-01 alongside the MD-First 2.0 docs migration, the fifth
(the layout law) on 2026-08-05:

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
- `test_layout_law.py` — THE SPACE & LEGIBILITY LAW, static half: no banned
  API in a GUI source (`server/gui`, `client`) — elision, forced scrollbars,
  disabled wrapping, hard pixel sizes on text-bearing widgets, CSS
  `text-overflow: ellipsis` and `-webkit-line-clamp`. One line may opt out
  with `layout-law: exempt - <reason>` ON that line; `RATCHET` is empty.
- `test_controls_sets.py` — the owner's `actions.json` is never silently
  rewritten: two sets of one process both survive a pool merge, renames are
  carried across it, a pool corrupted by an older build repairs itself, and
  switching sets in the editor never writes into another set's pool (both
  failures of 2026-08-05). Builds the real Controls dialog offscreen, so it
  is a full-run guard.
- `test_app_set_wheel.py` — the app-aware sets appear for the RIGHT window
  and pay for their seat (owner's two rules of 2026-08-06): only the Claude
  conversation wears the Claude set — never an open `CLAUDE.md`, a transcript
  or any other document carrying the word — and an app set charges a wheel
  slot, the charge being the largest group that can appear together (VSCode +
  Claude = 2, Chrome + Explorer + VSCode = 1). The functions under test are
  pure but live in a browser script, so the guard lifts the block out of
  `client/controls.js` and runs it in **node** with stubs — the same
  parse-the-client trick the desktop editor uses for `ICONS`/`BUILTINS`.
  Skipped, not failed, when node is absent.
- `run_guards.py` — runs all guards (or, with `--fast`, structure +
  config-sections + the static layout law — a grep costs nothing, so it
  belongs in the PostToolUse hook's budget; the Qt audit is full-run only,
  it builds a QApplication); exits 2 on any failure. Wired into
  `.claude/settings.json` (PostToolUse `--fast`, Stop full). Run directly:
  `python tests/run_guards.py`.

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
