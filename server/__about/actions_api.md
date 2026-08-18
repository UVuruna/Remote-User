# actions_api.py — actions.json on the wire, and the phone's set editor

New 2026-08-11 (**task 218b**). Two jobs, one responsibility: this module is
the single place that knows the shape of `actions.json` as the phone reads it —
both when it is first sent and when the phone itself changes it.

## What moved here, and why

`_merge_shipped_actions` and `load_actions` were in `web.py` until this round.
They moved out under THE STRUCTURE LAW (web.py stood at 1,004 lines), but the
placement is by responsibility: the re-broadcast below has to send the same
frame the first `actions` message sends, and a second copy of that field
whitelist is *exactly* how `wheel_order` once became a feature the desktop
saved and the phone never saw. One owner, one whitelist.

`web.py` keeps two lines: `actions_api.send_actions(...)` after auth, and the
`actions_update` branch.

## The message

```
client → server:  actions_update {set, active, order_land?, order_port?}
server → client:  actions {…}      (the whole set list, re-read from disk)
                  toast {text}     ("<set> saved", or the refusal)
```

`active` names the ≤4 pool commands that ride the D-pad **by id** — never by
index, so a later version inserting a pool command cannot re-point his choice.
`order_land` / `order_port` are permutations of the active list's own
positions, which is exactly what the client's `renderGroup` accepts.

## THE OWNERSHIP CONTRACT — why `PHONE_EDITABLE` is a subset

`server/gui/controls_data.py` owns THE OWNERSHIP RULE: `OWNER_SET_KEYS` names
the per-set keys that belong to the owner and survive every shipped-pool merge.
This module's `PHONE_EDITABLE` is asserted to be a **subset of it, at import
time** — so a future round that makes a new key phone-editable without adding
it to the merge's owner list cannot start. The server refuses to import, at the
desk, instead of writing a field the next release's merge would silently delete
out of his file. That deletion is the 2026-08-07 failure recorded in CLAUDE.md,
arriving from the other direction, and it would have been the quietest bug this
project has: he arranges his D-pad, it works, and one update later it resets
itself with nothing in any log.

`enabled` is deliberately **not** phone-editable although it IS an owner key.
It is the wheel COMPOSITION default, and the phone already owns composition per
DEVICE through the sets picker's SharedPreferences (which must stay per device
— his tablet and his phone want different wheels). This editor edits a set's
INTERIOR. The two never meet, and the wheel-cap law is untouched.

## Refusals

| Refused | Why not simply trimmed |
|---|---|
| any key outside `PHONE_EDITABLE` — `buttons`, `enabled`, `process`, `name`… | the message is refused WHOLE, never filtered: anything on the LAN holding the token could otherwise rewrite a set's commands one accepted field at a time |
| an id not in that set's pool | a phone working from a stale `actions` frame must be told no; honouring the half we recognise leaves him looking at a D-pad he did not choose |
| an `active` that is empty, longer than 4, duplicated, or not a list of strings | every one of these is something `renderGroup` would have to silently ignore |
| an arrangement that is not a real permutation | a silently-ignored arrangement is this project's own signature bug (the layout Move handle, four rounds) |

Every refusal is a **toast and a log line**, never a silent no-op, and it never
touches the bytes on disk — a validator that writes and then complains is worse
than no validator.

**The pool is the file's own**, not a separately-read shipped copy: for a
built-in or app set the user file's `buttons` IS the shipped pool (the merge
overwrites it every start, it is OURS under the ownership rule), it is the list
the phone was actually shown, and a custom set has no shipped pool at all.

## The merge is imported from the Qt-FREE module, never through the dialog

`_merge_shipped_actions()` runs once per server start (FROZEN only) and calls
`merge_shipped_pools`. It took that name off `gui.controls_editor` until
2026-08-18 — a dialog module that imports `PySide6.QtCore/QtGui/QtWidgets` at
module level, and merely re-imports the merge from `gui.controls_data`, where
it is actually defined. This module runs on the HEADLESS path
(`main.py` -> `web.py` -> here), so on a server without PySide6 the import
raised, the broad `except` around the merge caught it and logged a warning,
and the merge did nothing at all: a phone-visible default change from a new
release sat unmerged with no failure anyone would read as one. The import now
names `gui.controls_data`, which owns the function and holds no Qt on purpose.

## Where it writes

`gui.controls_data.user_actions_path()` — the same file the desktop Controls
editor writes, seeded into `%LOCALAPPDATA%` and the running `SETTINGS`
repointed at it on a frozen install, so a phone edit made before he has ever
opened the Controls editor still lands in his own file rather than failing
against read-only Program Files.

## Gate

`tests/test_set_editor.py`, fail-closed in `setup/build.py` — see
`client/__about/set-editor.md` for what its four promises are and how each was
proven by planting its own defect. `tests/test_actions_migration.py` holds the
other side: what the phone wrote survives the next release's merge.

## Related

- [controls_data.py](../gui/__about/controls_data.md) — `OWNER_SET_KEYS`, the merge,
  `button_id`, `active_buttons`
- `client/__about/set-editor.md` — the phone's half
- [web.py](web.md) — the two lines that remain
