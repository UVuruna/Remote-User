# VS Code Windows

**Script:** [VS Code Windows (script)](../vscode_windows.py) ·
**Flow:** [diagram](../__flow/vscode_windows.md)

## Purpose

Which torn-off ("floating editor") VS Code window belongs to which trunk
window — read from VS Code's own on-disk record, never guessed from what we
did ourselves.

**Why it exists** (owner GO, 2026-08-17): the layout list's ⭐ marks a layout
whose window is the TRUNK another layout's content hangs off (see
[Layout State](layout_state.md)). Until this module the ⭐ was read ONLY off
`Layout.sources`, written when THIS server tore a tab off during creation, in
THIS run. So it went silent for the owner in every one of these cases:

- the server restarted;
- he built a layout from windows that were already open;
- he tore a tab off BY HAND, without going through the creation flow.

`Layout.sources` still wins wherever it has an answer — we watched ourselves
do that extraction, and no external source can be more certain than that.
This module is the second source, for what we did not watch happen.

## Where the answer lives (measured, do not re-derive)

VS Code keeps this itself, per window, in
`%APPDATA%\Code\User\workspaceStorage\<hash>\state.vscdb` — a real SQLite
file, table `ItemTable`, the SAME database
[Agents](agents.md#which-tab-is-active-owner-bug-2026-08-15) already reads
for the active-tab lookup:

- `memento/workbench.parts.editor` → the MAIN window's editor grid. Read by
  `agents._tabs_from_memento` for Claude Code panels only — left exactly as
  it is, its known flat-key bug included, on instruction.
- `memento/workbench.editorParts` → `{"editorparts.state": {"auxiliary":
  [...]}}` — a LIST of the auxiliary (torn-off) windows this project's
  storage remembers. Each entry carries `state` (the same nested
  `serializedGrid` shape as the main grid) and `bounds` (that window's own
  rectangle).
- An editor inside either grid is `{"id": ..., "value": "<json string>"}`;
  the inner JSON has `"title"` — the tab title, elided with a real `…`
  exactly as the Windows window title is. A VS Code window title reads
  `<tab title> - <folder> - Visual Studio Code[ tail]`, so the window title
  STARTS WITH the tab title.

Verified on the owner's desk: 3 live windows of one project, main grid held
one tab, the auxiliary list held two, and the window left over was the
trunk — independently confirmed by photographing the title bars.

## The remainder rule (why the trunk is never READ, only left over)

Matching a branch to its auxiliary record only proves it is NOT the main
window — the main window's own bounds live in a different file
(`workspace.json` names the folder, nothing about the live grid), and
reading a third source for one more fact was rejected on purpose. The trunk
is whatever is LEFT once every branch for that project folder is accounted
for, and `trunk_map` maps every branch to it **only when exactly one window
is left over**. Zero or several leftovers answers nothing for that folder —
a wrong guess would tell the owner a window is safe to close when it is not,
which is the one failure this module exists to never commit.

## Read policy

**No timer, no polling, no read at all unless `trunk_map` is called** — this
runs inside the `layout_state` frame, which rides every focus and every
change. The auxiliary records are cached per storage dir, keyed by the
file's own `(st_mtime, st_size)`:

- a call whose file is unchanged costs one `os.stat` — measured ~6 µs;
- a changed file costs one real read — measured ~2 ms on a 92 KB file (a
  throwaway copy via `agents._readonly_copy`, since VS Code holds the live
  file open, plus two SQL queries).

The hwnd matching itself is pure and re-runs fresh on every call
(`docs/DECISIONS.md` constraint 13 — never remember geometry); nothing is cached
against a window handle, because Windows reuses handles.

## Honest limits

- **VS Code flushes this file LAZILY**, as part of its own on-disk cache —
  measured 56 s old at one read, 4 minutes at another, on the owner's own
  desk. It IS written during a session, not only on exit, but a window torn
  off seconds ago may be absent until the next flush. This is exactly why a
  miss must always mean no ⭐, never a guess.
- **VS Code only.** Nothing here says anything about Chrome, Explorer or any
  other app's own multi-window story.
- **One project folder maps to one storage folder.** The same folder opened
  in two real main windows correctly leaves two windows "left over" for that
  folder, and the remainder rule refuses to pick one.
- **The project folder is recovered through `agents.project_dir_of`**, which
  reads it off a live Claude Code transcript for that folder — the same path
  `agents.claude_state` already depends on. A folder VS Code has open that
  Claude Code has never touched cannot be resolved to a storage dir at all,
  and `trunk_map` answers {} for it rather than guessing a path from the
  window title's basename.
- **The bounds tie-break judges the RESTING rect, not the live frame — and
  that is a NARROWER fix than it sounds.** A minimized window's live frame
  (`wm._frame_rect`) is a fixed off-screen rect regardless of which window it
  really is (measured `(-32000, -32000, 199, 34)` for every minimized window
  on the owner's desk), so `_frame_rect` alone could never break a tie for a
  minimized window at all. The tie-break therefore asks `lost_windows.
  resting_rect(hwnd)` — `GetWindowPlacement.rcNormalPosition` when the
  window is iconic, the live frame otherwise — the same function
  `lost_windows.py` already answers this exact question with
  (constraint 17), imported rather than re-derived.

  **But `resting_rect` only helps where the windows actually sit apart, and
  on the owner's own desk they routinely do not** (measured 2026-08-17): a
  SOLO layout places its one member into the layout's own region, and every
  solo layout shares that same region — three minimized solo-layout members
  on his machine all rested at the IDENTICAL rect, `(1148, 1, 775, 1678)`,
  down to the pixel. Geometry cannot separate windows WE put in one place; no
  amount of tolerance tuning changes that. **A genuine title collision inside
  one layout's region is UNRESOLVABLE BY DESIGN, and correctly stays that
  way**: two candidates tied on both title and resting rect are still left
  unresolved rather than guessed, per rule 1. The cost is a missing ⭐ — never
  a wrong one.

## Contents

- `trunk_map(hwnds)` — the public contract: `{branch: trunk}` for the
  `code.exe` windows among `hwnds`, `{}` when the answer is not known. Groups
  by project folder (`agents.title_folder`), matches each folder's auxiliary
  records to a live window by tab title (`_match_record`), and applies the
  remainder rule.
- `_match_record(record, candidates, titles)` — a record names exactly one
  candidate by title, or the bounds tie-break (`BOUNDS_TOLERANCE_PX` = 60 px,
  x+y distance) breaks a tie between several, or neither and the record
  contributes nothing.
- `_parse_auxiliary` / `_cached_auxiliary` — the read and its cache; see Read
  policy above.
- `_editor_titles(node)` — walks a `serializedGrid` node generically for the
  `{"id", "value"}` editor shape, mirroring `agents._walk_editors`'s walk of
  the differently-shaped Claude-webview descriptors.
- `_log_once(trunk, branch)` — a resolved pair is logged at INFO exactly
  once; `layout_state` asks on every focus, and the owner's log must be able
  to answer "did it see it" without a flood.

## Connections

### Uses
- [Agents](agents.md) — `title_folder`, `project_dir_of`,
  `_workspace_storage_dir`, `_readonly_copy` (reused, never duplicated)
- [Window Manager](window_manager.md) — `_process_name`, `_title`
- [Lost Windows](lost_windows.md) — `resting_rect`, for the bounds
  tie-break (imported, never a second copy of that arithmetic)

### Used by
- [Layout State](layout_state.md) — the ⭐'s second source, called only when
  it can matter

## Gate

`tests/test_vscode_windows.py` (planned alongside this module) drives the
real reader over a fixture database and a planted defect per rule, in the
style of `tests/test_claude_state.py`.
