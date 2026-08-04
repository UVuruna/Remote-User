# Window Manager

**Script:** [Window Manager (script)](../window_manager.py)

## Purpose
Phase F+ step 1 (spec: ROADMAP → Layouts & Tab Control): the phone composes
window LAYOUTS live from open PC windows — solo (one window sized to the
phone's aspect) or a grid template (2x1 / 1x2 / 2x2) — and cycles them with
the layout bar. This module owns everything Win32 about that: enumerating
candidate windows, identifying the window under a monitor-normalized tap,
arranging windows (visible-frame accurate — DWM extended frame bounds, not
`GetWindowRect`, which includes invisible resize borders), raising/focusing
(with the Alt-nudge `SetForegroundWindow` unlock), and the session-scoped
`LayoutRegistry`.

Key rules encoded here (owner decisions 2026-08-02):

- **Layouts live for the SERVER's lifetime** — the phone may disconnect and
  return; they die with the server app.
- **Members are LIVE window references** (hwnds): a window the user moved or
  resized at the desk is re-read at every focus (fresh region), and one the
  user closed silently drops out (`prune`) — an empty layout disappears.
- **Device adaptation:** `create`/`focus` take the device's short/long side
  ratio; the layout's chosen orientation (portrait/wide) turns it into the
  real aspect, and a focus from a different-aspect device re-arranges the
  windows (tablet vs phone).
- **Removal leaves the desktop as-is** — no auto-return of windows.

All functions are blocking ctypes calls — the web layer wraps them in
`asyncio.to_thread`. Tab extraction (context menu / Explorer path / SendInput
drag, probe-verified 2026-08-02) is step 2 and does not live here yet.

## Connections
### Uses
- none (pure Win32 via ctypes — no project imports)

### Used by
- [Web Layer](web.md) — `layout_pick`/`layout_create`/`layout_focus`/
  `layout_remove` handlers and the `layout_state` payload

## Classes

### Layout
One phone screen: `name` (target's title at creation), `process`, ordered
`members` (grid cell order; `[window]` for solo), `template` (None = solo),
`orient` ("portrait" | "wide"), `aspect` (w/h last arranged for).

### LayoutRegistry
The session-scoped list. `create(...) -> index|None` arranges and registers;
`focus(index, device_ratio, mon_rect) -> region|None` re-validates, re-places
on aspect drift, raises members and returns the fresh monitor-normalized
region; `remove(index)`; `prune()`; `state(active, region)` builds the
`layout_state` payload (pruning first, so the phone never lists a dead layout).

## Functions
- `list_windows(exclude)`: visible, titled, non-cloaked, non-shell, non-tool,
  not-our-process top-level windows → `{hwnd, title, process}` dicts
- `window_at(mon_rect, nx, ny)`: the app window under a monitor-normalized
  point (`WindowFromPoint` → `GA_ROOT` ancestor), same dict shape or None
- `place_window(hwnd, rect) -> bool`: restore + `SetWindowPos`, compensating
  the invisible-border offsets so the VISIBLE frame lands on rect, then
  VERIFIES it landed (`wait_landed`, one retry). Places into the TOPMOST band
  (owner decree 2026-08-04: a layout member is never below any other window,
  not even mid-creation). False = the window refused its rect — the web layer
  toasts it, never shrugs it off.
- `raise_window(hwnd)`: restore + z-top (`HWND_TOPMOST` — `HWND_TOP` cannot
  pass an always-on-top window like Task Manager) + `SetForegroundWindow`,
  with the Alt-nudge retry when Windows refuses foreground to a background
  process
- `drop_topmost(hwnd)` / `LayoutRegistry.clear_topmost()`: the other half of
  the TOPMOST lifecycle — back to the normal z-band on desktop focus, focus
  of another layout, layout removal, and phone disconnect
- `is_alive(hwnd)`: window exists, visible, not DWM-cloaked

## Per-layout aspect ratio (owner decision 2026-08-03)
Each layout carries its own `ratio` (W:H, `None` = the phone's own shape),
set from the phone's aspect panel via `set_ratio(index, w, h)` and applied by
the next `focus` (which is what re-places the windows — `arranged_ratio`
records what they currently stand in, so a changed ratio forces the rebuild).

`layout_region(mon_rect, aspect, ratio)` is the single place the rule lives:
the DEVICE shape gives the outer box (`_region_rect`), and the override is the
largest rect of that W:H fitted INSIDE it (`_fit_rect`). The region can
therefore only ever shrink — portrait keeps the phone's full width and only
loses height, landscape keeps its height and only loses width; anything that
would grow past the phone's shape is clamped by the same fit. The unused strip
stays black on the phone.

`member_hwnds()` returns every window that already belongs to some layout —
[Web Layer](web.md) leaves those out of the creation list, because one window
cannot be shown in two places (owner 2026-08-03).

## The move must be INVISIBLE (owner rule, hardened 2026-08-03)
The phone's cube overlay exists so the user never sees windows moving — it
covers the rearrangement and fades out onto the finished picture. Twice it
faded out onto a window still sliding up out of the taskbar, because this
module reported "done" too early:

- `ShowWindow(SW_RESTORE)` / `SW_MINIMIZE` return immediately while DWM plays
  the slide transition, which the screen capture faithfully records.
  `freeze_transitions(hwnd)` (DWMWA_TRANSITIONS_FORCEDISABLED) turns that
  animation off for every layout member, so restore/minimize are instant —
  there is nothing left to watch. `remove()` gives the window its normal
  animation back.
- Even without the transition, the app re-lays-out after the resize.
  `wait_settled(hwnd) -> bool` blocks until the window is out of the taskbar
  and its visible frame has stopped changing (4 identical reads, 1.5 s cap);
  `wait_minimized(hwnds)` blocks until every member is really iconic before
  the Desktop position is reported.
- "Stopped moving" alone lied twice (owner 2026-08-04): a window paused
  mid-restore read as settled, and a timeout logged a warning and carried on.
  `wait_landed(hwnd, rect) -> bool` verifies the POSITION — the frame rect
  must match the commanded rect (±8 px; a larger minimum size is
  owner-accepted, the phone letterboxes) and hold it through 4 reads.
  `create`/`focus` report the verdict up; a failure reaches the phone as the
  "would not take its exact spot" toast.

`place_window`, `raise_window` and `minimize_members` all wait AND verify, so
`layout_state` now means "the desk is finished, checked", which is exactly
what the phone's overlay needs to fade out on — see
[Layouts](../../client/__about/layouts.md) for the client half (it must also
wait out the stream latency before judging the picture).

## Refinements (owner feedback 2026-08-02, same day)
`minimize_members()` — the Desktop slider position minimizes every layout
member, so the full-desktop view shows only non-layout windows; focusing a
layout later restores its own members. `window_at_hwnd(hwnd)` returns the
list_windows-shaped info dict for a known handle (slot resolution).
