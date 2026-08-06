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
inside it.

**CONTRAST** (owner 2026-08-06: *"je l' moguće da prođe situacija sa dizajnom
elemenata i bojama"* — six white buttons carrying near-white labels, and every
geometric check green). Text nobody can read is not a style opinion; it is
unreadable content, which is this law's whole subject. Every leaf text node is
measured against its **composited** backdrop — each translucent layer painted
over the one below, down to the page — and anything under a 3.0:1 WCAG ratio
fails, naming the element and the ratio. Compositing is not a detail: the first
version of this check ignored alpha and called this project's own translucent
selected states 1.00:1, and a guard that cries wolf gets switched off. It found
two real defects on its first honest run — the Sets picker's live badge at
1.96:1 (`var(--bg)` is not a token here, so the declaration was invalid and the
badge inherited near-white ink) and the command chooser's rows at 1.05:1 (a
`<button>` with no background of its own takes the WebView's light default). Covers the Quality panel, the Sets picker, the Dictation card,
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

**"Fullest state" includes what arrives LATE** (owner screenshots 2026-08-06).
`MainWindow`'s factory used to build the window and stop there — but two things
reach it only after it is on screen: the update button (hidden until GitHub
answers) and the notify switch's caption (one line normally, three when it has
to report a failure, and a failure names a path). The factory now `show()`s the
window first and lets both arrive afterwards, exactly as the owner's evening
does. Self-tested: with the fix disabled the audit reports
`CLIPPED MainWindow: has 820x837, needs at least 618x880` — 43 px, the update
button's own row, which was being drawn over the QR's link.

**MainWindow (reopened from the tray)** is the same window reached the way the
owner actually reaches it: closing this app hides it to the tray, so the update
offer lands on a window nobody is looking at, and Qt gives a hidden window no
real metrics. The case shows the window, hides it, lets the late content
arrive, and hands it back for the audit to show again — proving the minimum is
re-measured on the way BACK. Self-tested the same way (signature on
`isVisible()` + a settle-once `showEvent` restored): `CLIPPED … has 869x837,
needs at least 618x880`.

**E. OVERLAP, and REAL FONTS** (owner 2026-08-06, after this guard reported
PASS over the window he had photographed twice). Two holes, both closed:

- Every check here asked whether an element got its own SIZE; none asked where
  it was PUT. Qt does not clip a layout that is short of space — it OVERLAPS
  it, so every widget reports its full size while the pairing link is painted
  across the QR. `check_overlap` compares the cells of each layout (not
  arbitrary siblings: a scrollbar over a viewport is legitimate) and fails on
  any intersection. It immediately caught one nobody had reported — the
  Traffic window's chart drawn 4 px over the caption beneath it.
- The platform WAS the measurement error: `offscreen` has none of the
  machine's fonts and substitutes metrics, reporting the main window at
  869x880 where the owner's real Segoe UI at 125% scaling needs 503x937 — the
  defect lived in the difference. The native platform is used whenever there
  is a desktop, with `WA_DontShowOnScreen` so the full layout machinery runs
  with real fonts and DPI while nothing appears on screen; offscreen remains
  the fallback. That switch alone surfaced two more genuine defects: the
  Controls editor 59 px short, and a Traffic combo cut to "Last 10 minut" by
  the theme's own 92 px combo floor.
- The container-height blind spot is gone with them. This file used to zero
  out the height of any container with wrapping children and check only its
  width; that is how the QR card could be handed 332 px against a minimum of
  348 in silence. It is now asked `heightForWidth` at the width it actually
  has.
- Each window's screenshot at its DECLARED minimum is written to
  `.claude/shots/` by the audit itself, so the picture the layout gate grades
  can never be of a different build than the one just measured.

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

### `test_focus_guard.py` — Focus Gate
Proves that what the phone types lands where the owner is LOOKING. `SendInput`
has no target, so before 2026-08-06 every dictated character went to whatever
window Windows called the foreground at that instant — and when something on
the PC took focus mid-sentence (an app starting, a dialog, another agent's
editor window), the rest of the sentence went there, silently, with the stream
still showing the PC. The owner reported it three times in one evening, and
the fourth report WAS the bug: a sentence dictated for another project arrived
in this project's session.

Eleven checks, no Windows and no browser (every user32 call is answered by a
fake): the layout fence refusing a foreign foreground and handing focus back
to the member being typed into; the fence holding on a fresh connection with
no pin yet; a move the owner made INSIDE the layout being followed, not
fought; a dialog of a member (Save As…) counting as that member; the desktop
pin arming on the burst's first key and restoring `topmost=False`; a click /
`next_input` / layout switch re-arming it while a thief arms nothing; the
thief being NAMED in the log; `LayoutRegistry.focus()` raising the keyboard
member LAST (one excursion used to move dictation into the other pane);
`prune` moving the target off a window closed at the desk; and the whole path
through the real `web._receive_input` dispatcher.

Run: `.venv\Scripts\python tests/test_focus_guard.py` — also a fail-closed
step in `build.py` (0e/6).

### `test_layout_protocol.py` — Layout Gate
Proves that EVERY layout message the phone can send answers it. Born from the
2026-08-06 live failure — *"layout, kreiraj iz liste, ništa se ne dešava"*: the
loading cube spun and no list ever came, because one line in
`layout_api.layout_list` read `mon_rect = mon_rect(stream)`. That name is the
module's own function, so the assignment made it a LOCAL for the whole function
and the call on the right-hand side raised `UnboundLocalError` before anything
was sent. The owner's server log carried the traceback three times; the build
carried nothing, because **no test walked this path** — four guards, an input
gate, a presence gate, a notify gate and a focus gate, and the phone's entire
layout protocol had none.

Five checks driving the REAL `web._receive_input` dispatcher over the REAL
`layout_api` and `LayoutRegistry`, with only Windows faked (user32, the window
list, UIA, the process table): create from a LIST (windows plus the tabs of
tab-capable apps), create by TAPPING a window, create → focus → desktop,
rename / app-sets / aspect / remove each answering with a fresh `layout_state`,
and a 2×1 grid built from the list. A handler that raises, or that answers the
phone with nothing, fails here. Self-tested by replanting the defect: the
first check reports the exact `UnboundLocalError` and fails.

Run: `.venv\Scripts\python tests/test_layout_protocol.py` — also a
fail-closed step in `build.py` (0f/6).

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
  Claude = 2, Chrome + Explorer + VSCode = 1). Two more rules from the same
  day: **the owner's per-layout ticks beat the guess** — the guard pins his
  real title, `Ispravka UI dizajna meni…`, on which the automatic test can
  only ever find VSCode (Claude Code names its tab after the conversation, and
  nothing else on the window identifies it) — and **the cap of 8 is a law over
  the STORED state**: the SHIPPED `actions.json` may not tick past it, and a
  state that already does is brought back by dropping the app set first.
  It runs `client/sets.js` **whole** in node behind stubs for the prefs bridge
  and the focused layout, rather than lifting a block out of it: the cap is
  enforced across storage, so stubbing the storage away would prove the
  arithmetic and miss the law. Skipped, not failed, when node is absent.
  Self-tested by re-enabling `Cursor` in the shipped file — "the shipped
  actions.json ticks 9 sets by default".
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
