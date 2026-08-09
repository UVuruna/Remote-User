# Layout Registry

[← server](../___server.md) · code: [layout_registry.py](../layout_registry.py)

## Purpose

The session's layout LIST and the policy over it: `Layout` (one phone screen —
members, orientation, ratio, the `pos` anchor, the keyboard member) and
`LayoutRegistry` (create / focus / prune / rename / set_ratio / set_grid /
merge / reorder / remove / minimize / `state()`). The registry lives for the
server's lifetime — the phone may disconnect and return, the list survives
(owner decision 2026-08-02).

Split out of [Window Manager](window_manager.md) on 2026-08-09 (THE STRUCTURE
LAW — the pos-anchor round pushed it past 1,000 lines; the seam had been named
two days earlier when layout_api.py refused to log inside a module "exactly ON
the 1,000-line limit"). The seam is the one [Grids](grids.md) was cut on:
`window_manager` DRIVES real windows; this module decides WHAT should happen
to them and what `layout_state` claims.

## The import contract (deliberate, and load-bearing)

Every desk primitive is reached LAZILY through the module object —
`wm.place_window(...)`, never `from window_manager import place_window`. The
gates fake a windowless PC by patching names ON `window_manager`
(`tests/test_layout_protocol.py` → `install_fakes`), and a name bound here at
import time would keep pointing at the real desk after the patch. For the same
reason `window_manager` re-exports `Layout` and `LayoutRegistry` at its
bottom, and that is the ONLY import path — importing `layout_registry`
directly, first, finds a half-initialized `window_manager` and fails loudly.

## The rules it carries

- **The arrangement is VERIFIED, never merely remembered** (owner 2026-08-07,
  the Move handle's second round): `focus` computes targets fresh, asks
  `wm._standing` where the windows REALLY are, and re-places on an aspect
  drift, a ratio change, a pending structural change (`place_pending` — set
  by `set_grid`/`merge`, and by a placement that did not land, so the next
  focus retries) or a member off its rect. Details and history:
  [Window Manager](window_manager.md) → the aspect/position section.
- **`pos` moves NOTHING on the PC** (owner decree 2026-08-09, the Move
  handle's FOURTH round): placement is always centred
  (`wm.layout_region` without a position), a pos-only Apply re-places no
  window, and `pos` is stored only to ride `layout_state` to the phone, which
  anchors the letterboxed picture with it (`client/view-anchor.js`). Gated by
  `tests/test_layout_protocol.py` (server half) and
  `tests/test_view_anchor.py` (phone half).
- **Prune on CLOSED, never on hidden** (audit 2026-08-05): a cloaked window
  (another virtual desktop, a minimized Store app) stays a member.
- **The keyboard member is raised LAST** (owner 2026-08-06): `last_member`
  survives excursions, so dictation resumes in the window he was typing into.
- **The ✕ wears two acts** (owner 2026-08-08, task 116): `remove(close=False)`
  only forgets; `close=True` also asks every member to close via
  `wm.close_windows` (WM_CLOSE — the app's own dialog decides).

## Used by

- [Web Layer](web.md) / [Layout API](layout_api.md) — every layout message,
  via `window_manager.LayoutRegistry`
- [Server Core](server_core.md) — owns the instance; `clear_topmost` on
  session end
- [Notify](notify.md) — `layout_of` matches a finishing agent's project to
  `Layout.project()`
- `tests/test_layout_protocol.py` — the gate, fail-closed in `setup/build.py`
