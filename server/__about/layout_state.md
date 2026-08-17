# Layout State

[← server](../___server.md) · code: [layout_state.py](../layout_state.py)

## Purpose

What a connected phone is TOLD about the layouts — the `layout_state` frame,
and nothing else.

Split out of [Layout Registry](layout_registry.md) on 2026-08-14 (THE
STRUCTURE LAW). The trigger was mechanical — that file stood at exactly 1,000
lines, so `member_hwnds` could not be added to it — but the seam is by
RESPONSIBILITY and would have been the right one at any size: the registry
owns the WINDOWS (create, grow, shrink, focus, let go), while this module owns
a WIRE CONTRACT with its own audience and its own reasons to change. A new
field here moves no window.

`LayoutRegistry.state()` survives as a one-line delegator, so no caller had to
learn a new name in the same commit that moved the code.

## What the frame carries

`state(reg, active, region)` prunes first — so the phone never lists a dead
layout — and FOLLOWS the focused layout through that prune by identity rather
than by index (a closed window at the desk used to slide the list down under
the focus, leaving the phone one ✕ away from removing a layout it had never
chosen). Per layout it reports the name, icon, process, `agents`, the grid and
orientation, `member_titles`, `member_hwnds`, `dependents`, `ratio` and `pos`.

- **`member_hwnds`** (owner correction 2026-08-13) — which windows this layout
  ALREADY holds, in `member_titles`' own cell order, read live off
  `Layout.members`. The tap has three cases and the phone could tell only two
  apart: an ordinary window, a window no layout could hold, and a window that
  is already a member of the layout he is looking at. The last has to be
  refused where the tap happens, and the page was left guessing it from
  titles. Handles are opaque to the phone — it never sends one back, it only
  compares. Gate: `tests/test_layout_claim.py`, driven through the REAL
  dispatcher and the REAL frame, never a fixture that writes the field by hand.
- **`dependents`** and the ⭐ — the names of every OTHER layout whose content
  was torn out of a window this one holds, so closing it is known to destroy
  them before he taps. `PARENT_CLOSE_APPS` lives here, with its only reader:
  a VS Code editor group still belongs to its window, while a Chrome or
  Explorer tab moved out is an independent window and closing the origin
  destroys nothing.

  **The ⭐ has TWO sources now** (owner GO 2026-08-17). `Layout.sources` is
  our own memory — written only when THIS server tore a tab off during
  creation — and it always wins where it has an answer. Where a `code.exe`
  member carries no such record (a restart, a layout built from windows that
  were already open, the owner tearing a tab off by hand), [VS Code Windows](
  vscode_windows.md) is asked instead, off VS Code's own on-disk record of
  which window a torn-off editor belongs to. It is asked ONLY when it can
  matter — fewer than two layouts, or a desk where every `code.exe` member
  already has its own record, reads nothing — and its answer is merged in
  under the same rule the file itself keeps: a miss is never a guess, so a
  member neither source can explain simply carries no star.

## Reads

- [Layout Registry](layout_registry.md) — the layouts themselves
- [Agents](agents.md) — one process-table snapshot per frame, never one per
  layout
- [Window Manager](window_manager.md) — live titles, lazily through the module
  object for the reason that module's own doc gives
- [VS Code Windows](vscode_windows.md) — the ⭐'s second source, for a trunk
  we did not watch get built
