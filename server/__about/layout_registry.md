# Layout Registry

[← server](../___server.md) · code: [layout_registry.py](../layout_registry.py)

## Purpose

The session's layout LIST and the policy over it: `Layout` (one phone screen —
members, orientation, ratio, the `pos` anchor, the keyboard member) and
`LayoutRegistry` (create / focus / prune / rename / set_ratio / set_grid /
merge / reorder / drop_member / remove / minimize / `state()`). The registry lives for the
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
- **A layout can be TURNED and RE-ARRANGED after it exists** (`set_grid`, owner
  2026-08-07 for a three's arrangement, extended by task 175 on 2026-08-09 to
  the thing he could not do at all: a layout built portrait had to be DELETED
  and made again to become landscape). It stores only — a shape of the WRONG
  SIZE is refused rather than obeyed into a cell nobody is in — and sets
  `place_pending`, so the focus that follows re-places the windows. Gate:
  `tests/test_layout_shape.py`, which asserts the RECTS (a shape change the
  phone shows and the PC ignores is the Move handle's bug in a new place) and
  the re-place order at the method's own boundary, because `focus` re-places on
  `_standing` anyway and would mask its absence.
- **Every SLOT's source is recorded, not just the first** (task 173,
  2026-08-09). `Layout.sources` maps an extracted member window to the window
  its TAB was torn out of. It used to be one `source` int written from the
  first slot alone, so a tab extracted into cell 2, 3 or 4 of a grid left no
  record — and both readers under-reported: the ⭐ (`state()` → `parent`) and
  the ✕ chooser's warning (`state()` → `dependents`, the NAMES a close would
  destroy). A dict keyed by the MEMBER rather than a positional list, because
  members are filtered on the way in and re-ordered on the way out; the record
  leaves with its member in `drop_member`, in `prune` and through `merge`.
  `Layout.source` survives as a read-only property — `project()` asks about
  `members[0]` and about nothing else, so the answer follows that member
  instead of going stale. Gates: `tests/test_layout_drag.py` (both cells, and
  the names asserted by relation), `tests/test_layout_member.py`.
- **Only VS Code's torn-out content depends on its origin** (task 201, owner
  correction 2026-08-10 — his screenshot: a Chrome layout wearing the ⭐). A
  Chrome/Explorer tab moved to its own window is fully independent, so a close
  destroys nothing there; the star and the ✕ warning therefore consult
  `PARENT_CLOSE_APPS` (`{"code.exe"}`), judged by the BRANCH layout's process
  — the tab and its origin are the same app, and no extra Win32 call rides the
  state frame. The extraction still records its source for every app
  (`project()` needs it); the rule scoped the STAR, never the record. Gate:
  the Chrome-pair check in `tests/test_layout_drag.py`.
- **The keyboard member is raised LAST** (owner 2026-08-06): `last_member`
  survives excursions, so dictation resumes in the window he was typing into.
- **The ✕ wears two acts** (owner 2026-08-08, task 116): `remove(close=False)`
  only forgets; `close=True` also asks every member to close via
  `wm.close_windows` (WM_CLOSE — the app's own dialog decides).
- **A grid can lose ONE window** (owner request 2026-08-09, task 165):
  `drop_member(index, member, grid=None)` — a four becomes a three, a three a
  two, a two a single. `member` is the ORDINAL of the cell the phone tapped,
  never a handle (the phone is never told a handle; cell *k* of the drawing is
  member *k* — `client/grid-icons.js`). Returns `"gone"` / `"dropped"` /
  `"removed"`.
  - **The window that leaves is NEVER closed.** Only the ✕ chooser closes
    windows, and only when he asked. It stops being layout material — out of
    the topmost band (constraint 10: a window we raised must never be
    stranded above everything, which is exactly what the LEDGER exists for),
    normal minimize/restore animation given back — and stays standing where
    it stands, the same "no auto-return of windows" rule `remove` follows.
  - **Removing the LAST member removes the layout**, through `remove()` and
    not a second teardown of its own.
  - The survivors are re-placed by the focus that follows; `place_pending` is
    the explicit order, for the case where every member happens to satisfy
    `_standing` already.
- **One catalogue for growing and shrinking** (owner's sheet, 2026-08-07):
  `_template_for(count, wanted)` is the single answer to "what shape does a
  layout of N windows wear", used by `merge` and `drop_member` alike, so the
  two directions can never disagree about what a three is. `wanted` is
  honoured only when it FITS — a name of the wrong size would leave a cell
  with no window in it. A THREE is the one size with a real choice (four
  arrangements); a two and a four have one each.

## Used by

- [Web Layer](web.md) / [Layout API](layout_api.md) — every layout message,
  via `window_manager.LayoutRegistry`
- [Server Core](server_core.md) — owns the instance; `clear_topmost` on
  session end
- [Notify](notify.md) — `layout_of` matches a finishing agent's project to
  `Layout.project()`
- `tests/test_layout_protocol.py` — the gate, fail-closed in `setup/build.py`
- `tests/test_layout_member.py` — `drop_member`'s own gate (0t/6)
- `tests/test_grid_icons.py` — pins `state()` still carrying `grid` /
  `members` / `orient`, the three fields the phone draws each row's shape from
