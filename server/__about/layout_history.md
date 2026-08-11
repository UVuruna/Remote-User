# Layout History

**Script:** [Layout History (script)](../layout_history.py)

## Purpose
Remember every layout ever created on this PC — across restarts — so the
phone's fourth creation source, **Recent** (task 228), can re-create one with
a single tap.

## The request behind it
Owner, 2026-08-11, alongside task 227's footer fix. Tap / List / New (see
[Recents](recents.md)) all build a layout from what is CURRENTLY on the desk;
none of them remember what he built YESTERDAY. He asked for a fourth source
that does — the phone asks, the PC answers from a persisted log, and tapping
one re-creates it against whatever is open right now.

## The shape of a history entry
Never a raw HWND — a handle means nothing after the app that owned it closes,
let alone after a restart (the same lesson [Recents](recents.md) is built
around). Instead, each member is remembered by:
* **`process`** — the exe name, lower-cased.
* **`title_words`** — the significant words of the title AT CREATION TIME,
  for a fuzzy re-match against whatever the window is called now.

The layout's own `project` (the folder `LayoutRegistry.create` already
resolves via `agents.first_folder`, when there is one) rides at the ENTRY
level, not per member — an honest limit named rather than hidden: a
per-member project would need the same resolution run once per window, which
nothing here currently does.

## The rules
1. **Recorded where a layout is BORN.** `LayoutRegistry.create()` calls
   `record()` right after a layout is registered — the one place that already
   knows the process, the title and the resolved project for every member
   that survived truncation.
2. **Deduped by member SET, order-independent.** `signature()` sorts the
   member keys before joining them, so re-creating the SAME windows in a
   different tap order still collides with the existing row — `record()`
   bumps its `count`/`ts` instead of piling up a near-duplicate every time he
   re-opens his usual pair.
3. **Capped at 30, most-recent-first.** `save()` truncates after every write.
4. **Ranked by recency AND frequency.** `list_entries()`'s score gives each
   use roughly a day of extra "recency" — a layout he opens daily stays near
   the top between uses rather than sliding behind whatever he touched once
   five minutes ago (owner spec: "sorted most-recent-first with a use-count
   so frequent ones rank up").
5. **Re-match is best-effort, never a stored handle.** `match()` tries
   process + a MAJORITY of the stored title words first, then falls back to
   process alone (a Chrome tab that merely navigated should still be found).
   Each open window is claimed by at most one member. Whatever cannot be
   matched is NAMED, never silently dropped, and the caller
   (`layout_api.layout_recent_use`) builds the layout from whatever WAS
   found, refusing only when nothing was.
6. **Never fatal.** `record()` swallows its own exceptions — a history write
   failing must not cost the owner the layout he just asked for.

## The honest limits
* **No project match.** Re-matching compares process + title only; a window
  that changed BOTH its title and its process (rare) will not be found.
* **Never auto-opens an app.** A member with nothing standing for it is
  named in a toast; nothing here launches anything to fill the gap (owner
  spec: "Do not auto-open apps in v1" — the door [Recents](recents.md)
  already opened for a LATER round).
* **A title that changed completely falls back to process alone**, which can
  claim the wrong one of several same-process windows if more than one is
  open and none of their titles match. Accepted for v1 — the caller still
  reports the honest found/missing count either way.

## Interfaces
* `record(name, template, orient, project, members)` — called from
  `LayoutRegistry.create()`.
* `list_entries()` → ranked history rows.
* `find(sig)` → one row, or `None`.
* `match(entry, open_windows)` → `(matched, missing)`.

Protocol (see the project [CLAUDE.md](../../CLAUDE.md) → Protocol): the phone
sends `layout_recent {}`, answered `layout_recent {entries}`
(`{id, name, project, count}` per row); tapping one sends
`layout_recent_use {id}`, handled in [Layout API](layout_api.md) —
`layout_api.layout_recent`/`layout_recent_use`.

Stored at `%LOCALAPPDATA%/RemoteUser/layout_history.json`.

## Gate
`tests/test_layout_history.py` — dedupe (order-independent), the 30-entry
cap, frequency-aware ranking, and every half of `match()` (title-aware,
process-only fallback, no-stored-words escape, claiming each window once,
refusing when nothing is found), each proven by planting its own defect.
