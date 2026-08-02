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
- `place_window(hwnd, rect)`: restore + `SetWindowPos`, compensating the
  invisible-border offsets so the VISIBLE frame lands on rect
- `raise_window(hwnd)`: restore + `SetForegroundWindow`, with the Alt-nudge
  retry when Windows refuses foreground to a background process
- `is_alive(hwnd)`: window exists, visible, not DWM-cloaked

## Refinements (owner feedback 2026-08-02, same day)
`minimize_members()` — the Desktop slider position minimizes every layout
member, so the full-desktop view shows only non-layout windows; focusing a
layout later restores its own members. `window_at_hwnd(hwnd)` returns the
list_windows-shaped info dict for a known handle (slot resolution).
