# VS Code Windows — Flow

**About:** [description](../__about/vscode_windows.md)

## Grouping and the two records read

```
trunk_map([hwnd1, hwnd2, hwnd3, ...])
  │
  ├─ keep only code.exe windows                    _process_name(h) == "code.exe"
  │
  ├─ group by project folder                        title_folder(_title(h))
  │     "…- VibeCoder - Visual Studio Code…"  ──▶  "vibecoder"
  │
  └─ per folder:
        project_dir_of(folder)  ──▶  "u:\Coding\UVuruna\Applications\VibeCoder"
              (read off a live Claude Code transcript — agents.py's own path)
        _workspace_storage_dir(project_dir)
              ──▶  %APPDATA%\Code\User\workspaceStorage\<hash>\

        state.vscdb  (a copy — VS Code holds the live file open)
          SELECT value FROM ItemTable
           WHERE key = 'memento/workbench.editorParts'
              │
              ▼
        {"editorparts.state": {"auxiliary": [
            {"state": {"serializedGrid": {…}}, "bounds": {x,y,w,h}},
            {"state": {"serializedGrid": {…}}, "bounds": {x,y,w,h}},
        ]}}
              │  walk each aux entry's grid for {"id","value": "<json>"}
              │  editors, pull "title" out of the inner JSON
              ▼
        records = [{"titles": [...], "bounds": {...}}, ...]
              one entry PER AUXILIARY (torn-off) WINDOW
```

## Matching a record to a live window

```
for each record, against the folder's still-unmatched windows:

  title match      _bare(window title).startswith(_bare(record title))
                    or the reverse (elision can strip either side)

    0 matches   →  logged at DEBUG, record contributes nothing (rule 1)
    1 match     →  that window is a BRANCH of this record
    2+ matches  →  bounds tie-break:
                      record["bounds"]  vs  lost_windows.resting_rect(hwnd)
                      x+y distance, must be < BOUNDS_TOLERANCE_PX (60)
                      AND the next-closest must not also tie
                    still ambiguous  →  logged at DEBUG, left out

  WHY resting_rect AND NOT window_manager._frame_rect: a MINIMIZED window's
  live frame is a fixed off-screen rect regardless of which window it
  really is (measured (-32000, -32000, 199, 34) for every minimized window
  on the owner's desk), so _frame_rect alone could never break a tie for a
  minimized window at all. `resting_rect` (rcNormalPosition when iconic,
  the live frame otherwise) is where the window would actually land, so it
  is what the tie-break reads — the same function `lost_windows.py`
  answers this identical question with (constraint 17), imported rather
  than re-derived.

  BUT THIS ONLY HELPS WHERE THE WINDOWS ACTUALLY SIT APART (measured,
  2026-08-17): a SOLO layout places its one member into the layout's own
  region, and every solo layout on the same desk shares that region — three
  minimized solo-layout members on the owner's own machine all rested at
  the IDENTICAL rect, (1148, 1, 775, 1678), down to the pixel. Geometry
  cannot separate windows WE put in one place. A genuine title collision
  inside one layout's region is UNRESOLVABLE BY DESIGN and stays that way:
  the tie-break refuses, the owner sees no ⭐ for it — a missing star,
  never a wrong one.
```

## The remainder rule

```
branches = every window a record matched (this folder)
trunks   = this folder's windows MINUS branches

len(trunks) == 1   →  every branch in `branches` maps to that ONE trunk
                       trunk_map[branch] = trunk   (logged once, INFO)
len(trunks) != 1   →  0 or 2+ candidates left — the file cannot answer this
                       honestly, so NOTHING is returned for this folder,
                       branches included (a resolved branch with no
                       resolvable trunk is still a miss)
```

## Cost

```
per call                one os.stat per storage dir touched   ~6 µs (cached)
file changed since      one copy + two SQL queries             ~2 ms (92 KB file)
never                    no timer, no polling — nothing runs unless asked
```

## Verified on the owner's desk, 2026-08-17

Three `code.exe` windows of one project, all MINIMIZED, with three DISTINCT
tab titles (one of them literally "Fix repetitive window de…" — the owner's
own live Claude Code conversation title, English throughout on this run):

```
input hwnds: 0x1c0fc8, 0x4054e, 0x2c0bc0   (all IsIconic == True)
RESULT: {0x1c0fc8: 0x4054e, 0x2c0bc0: 0x4054e}
INFO  vscode_windows: trunk 263502 -> branch 1839048
INFO  vscode_windows: trunk 263502 -> branch 2886592
```

Both auxiliary records matched their window by title alone — the titles
were distinct, so the bounds tie-break was never reached in this run. An
EARLIER run in the same session saw two windows briefly sharing one title
(VS Code had not yet flushed a title update for a conversation mid-rename)
and returned `{}` for that folder — correctly: with two candidates tied on
title, `resting_rect` is exactly the field the tie-break needs, and the
live frame of a minimized window (what the first version of this module
read) carries none of it.

A SEPARATE measurement the same day, of the same three windows, shows the
limit of that fix rather than its closing: each of them is a SOLO layout,
and all three `resting_rect` calls answered the identical rect,
`(1148, 1, 775, 1678)` — the region a solo layout gives its one member is
the same region for every solo layout on this desk. Had two of these three
windows shared a tab title at that moment (as one pair briefly did, above),
`resting_rect` would have been unable to tell them apart either — geometry
cannot separate windows the product itself placed in one spot. That case is
not a bug to close; it is rule 1 refusing to guess, and the owner loses a
star he would otherwise get, never gains a wrong one.
