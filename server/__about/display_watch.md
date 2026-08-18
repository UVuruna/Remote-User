# Display Watch

**Script:** [Display Watch (script)](../display_watch.py)

## Purpose

The OTHER half of constraint 30's lesson. [Capture Recovery](capture_recovery.md) answers "the picture died — bring it back"; this module answers a smaller, earlier question that the same measurement exposed: "Windows just told everyone the monitors changed — who is listening?" Nobody was. This module watches Windows' own display-change signals and hands subscribers a `DisplayDiff` — added, removed, changed — so a monitor that appears or moves mid-run reaches the rest of the app without a restart and without a timer.

## The defect it answers, measured not theorised

`server/gui/settings_window.py:545` `_populate_monitors()` fills the Settings window's monitor list exactly once, while the window is BUILT, by asking `BaseCapture.output_count()` (`server/capture.py:155`) which asks `dxcam.output_info()`. `dxcam.DXFactory` is an import-time singleton (`docs/DECISIONS.md` constraint 30, [Capture Recovery](capture_recovery.md) mechanism 3) — it enumerates the adapter's outputs ONCE, for the process's whole life. So today: plug in a second monitor while the app is running and it is invisible until the process restarts, and reopening Settings does not help — the window rebuilds its list from the same stale singleton every time. Constraint 30's own failure was a 3.8-hour dead picture measured on the owner's machine from a different symptom of the identical root cause (a stale in-process DXGI enumeration). This module does not fix `DXFactory`'s staleness — [Capture Recovery](capture_recovery.md) already owns that ladder — it fixes the OTHER cost of the same staleness: nobody in this codebase was even told a change had happened, so nothing could react.

## No polling — the owner's explicit ruling

2026-08-16, general and not about one file: the app must react to the EVENT, because plugging in a monitor is not a millisecond occurrence — it is real, observable, human-scale time, exactly the class `docs/DECISIONS.md` constraint 15 already forbids estimating anywhere else in this codebase. A poll loop here would be the same mistake in a new file: guessing how long "changed" takes to become true, instead of asking Windows to say so. `DisplayWatch` therefore holds no timer of its own — it registers for the OS's own change notifications and only ever re-reads the truth (`snapshot()`) when one of them fires.

## The two sources, one outcome

- **`gui_main.py`** runs a `QGuiApplication`, and Qt already turns Windows' display messages into signals — `screenAdded`, `screenRemoved`, `primaryScreenChanged`, and per-screen `geometryChanged` / `logicalDotsPerInchChanged`. `DisplayWatch` just connects to them (`_try_start_qt`), including screens already open at connect time and any added later (`_on_qt_screen_added` wires a newly-arrived screen's own per-screen signals too — a screen added after start must get the same connections one present at start already has).
- **`main.py`** (the headless CLI) has no `QApplication` to lean on, so it borrows `focus_hook.py`'s shape exactly: a message-only window (`HWND_MESSAGE`) on its own thread, catching `WM_DISPLAYCHANGE` (resolution/monitor count) and `WM_DPICHANGED` (scaling). `start()` tries Qt first (the GUI process already has one running) and falls back to the winapi window only when Qt is unavailable — never both at once.

Both paths funnel into the same place: `_check()`. The event itself carries no useful payload here (Windows' `WM_DISPLAYCHANGE`/`WM_DPICHANGED` parameters are partial, and Qt's signals are plain notifications) — every source just means "look again," and `_check()` re-reads `snapshot()` and diffs it against the last known state. A fresh enumeration is cheap and always correct, so there is nothing to gain by trying to parse the event's own parameters.

### The WNDPROC-thunk lesson (copied from `focus_hook.py`, not re-learned the hard way)

A ctypes callback is a real code pointer Windows calls for as long as its window class stays registered, and `RegisterClassW` keeps a class registered for the PROCESS's whole life — not per-`start()`. `focus_hook.py` already paid for finding this out: recreating the WNDPROC on every `start()` crashed the SECOND run in that module, calling into a thunk Python had already freed. `display_watch.py` copies the fix rather than the mistake: `_WNDPROC` and the window class (`_CLASS_NAME` / `_ensure_class_registered`) are created exactly ONCE, at module scope, and every `start()`/`stop()` cycle reuses them.

## The scaling trap

Read this twice before touching `scale_pct`. This server declares `PER_MONITOR_AWARE_V2` (constraint 2) specifically so it sees PHYSICAL pixels — the same pixels `dxcam` captures and the injector's `SendInput` lands clicks on. A 4K monitor running at 150% scaling is still **3840×2160** to dxcam and to this server; "2560×1440" is only the LOGICAL size Windows reports to a DPI-*unaware* process, which this one deliberately is not. `scale_pct` is therefore recorded as its own, separate field on `DisplayInfo` — pure information — and must NEVER be folded into, or used to derive, a resolution anywhere downstream. `width`/`height` are always the physical rect; `scale_pct` exists precisely so nobody is tempted to combine the two into a "scaled resolution" that would then disagree with what the injector actually needs. The gate states this explicitly as its own check (`check_4k_at_150pct_stays_physical`, named "THE TRAP: 4K at 150% still reports 3840x2160" in `tests/test_display_watch.py`) — planting a fold of the two fields reddens it.

## Why it reports and never acts

This module calls no `dxcam` function and no `capture_recovery` function — it never touches either, on purpose. [Capture Recovery](capture_recovery.md) decides what a display change MEANS for a LIVE camera (its own three-rung ladder); that is a different job with different failure rules (nothing there may block, nothing there may trust dxcam to let go). Keeping the two separate means a bug in either is never reachable through the other: `display_watch.py` only ever answers "what does Windows say is true about the monitors right now, and did that answer just change" — every consumer (capture's own staleness handling, the Settings window's monitor list, the use log, the phone's `config` frame) is wired to `DisplayWatch` from OUTSIDE this module, by subscribing.

### Why a diff carries the whole new snapshot, not just what moved

`DisplayDiff.snapshot` is the full, ordered new state — not only `added`/`removed`/`changed`. The capture layer's own question is never "did *some* monitor change," it is "is the monitor *I am capturing* one of the ones that vanished or moved" — and answering that needs the whole picture, indices and all, not a partial delta it would have to reassemble against state it does not otherwise keep.

## Public API

- `snapshot() -> DisplaySnapshot` — the current truth, read now, never remembered (`docs/DECISIONS.md` constraint 13). Safe from any thread; `EnumDisplayMonitors` is synchronous and reentrant. Never raises — a failed enumeration is logged and answered with an empty tuple.
- `DisplayInfo` — one monitor: `index` (enumeration order, matching `monitors.py`'s convention), `left`/`top`/`width`/`height` (physical pixels), `primary`, `scale_pct` (100 = no scaling).
- `DisplayDiff` — `added` / `removed` / `changed` (tuples of `(old, new)` pairs at the same index) / `snapshot` (the full new state) / `is_empty`.
- `DisplayWatch` — the subscribable watcher:
  - `subscribe(callback)` / `unsubscribe(callback)` — `callback(diff: DisplayDiff)`, called only when a fresh read differs from the last known state; a raising subscriber is caught and logged, never allowed to silence the others or the watch itself.
  - `start()` — idempotent; picks Qt or the headless winapi window (Qt tried first), logs which, and takes an initial `snapshot()` as the baseline so nothing fires for the state already true at start. Never raises; if neither source attaches, it logs a warning and the caller falls back to whatever it did before this module existed (a manual `snapshot()` call still works — it just is not told WHEN to make one).
  - `stop()` — THE exit call. Idempotent, safe from any thread, tears down whichever source is live and clears subscribers.
  - `source` — `"qt"` / `"winapi"` / `None`.
  - `last_snapshot` — the most recently known state, or `None` before `start()`.

## Connections

### Uses
- Qt (`PySide6.QtGui.QGuiApplication`), when one is already running — imported lazily inside `_try_start_qt` so this module stays importable from the headless CLI, where PySide6 may not even be installed
- raw Win32 (`user32`, `kernel32`, `shcore`) directly for `snapshot()` and the headless message-only window, in the same shape `focus_hook.py` already uses for its own foreground hook

### Used by
- Not yet wired to a caller as of this doc (server/session_log.py's own `__about` names this module's planned `state("pc", …)` monitor facts as an intended future call site). `capture.py`, `settings_window.py` and the phone's `config` frame are the consumers this module exists FOR, but none of them subscribe yet — this module reporting correctly is the prerequisite, wiring a reaction to it is separate follow-up work.

## Honest limits

- If neither Qt nor the headless window can attach (`start()` finds no source), changes are silently missed until the next explicit `snapshot()` call from elsewhere — logged as a warning, never a crash, but also never retried on a timer (that would be exactly the polling the owner's ruling forbids).
- The winapi source is one process-wide resource: a second `DisplayWatch` in the same process cannot also own the message-only window (`_start_winapi` refuses and logs when `_active_winapi_watch` is already someone else) — only one headless watcher may run at a time per process, which matches this app's own shape (one server process, one watch).
- Windows' `WM_DISPLAYCHANGE`/`WM_DPICHANGED` payloads are not read at all; every event, however it arrived, only triggers a fresh `snapshot()`. This is deliberate (see "the two sources, one outcome" above) but means a change that fires the event and then reverts before `_check()` runs would be missed — accepted, since a `snapshot()` reflects only what is true at the moment it runs, same as everywhere else in this codebase.
