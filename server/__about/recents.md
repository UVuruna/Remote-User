# Recents

**Script:** [Recents (script)](../recents.py)

## Purpose
Answer two questions for the phone's **New** layout source (task 184):
*what can this PC open?* and *open that, and tell me which window appeared.*

## The request behind it
Owner, 2026-08-09, with three jump-list screenshots. Until this module a layout
could only be built out of what was already standing on the desk — "Tap a
window" and "From a list" both enumerate the present. His observation is the
whole feature:

> "recent imaju svi" <!-- lang-ok: owner quote -->

VS Code, Chrome and Explorer each keep a recent list the taskbar already shows
him, so the phone can offer one, open it, and make a layout out of the window
that appears.

## Where each list comes from — and how hard each one is
Recorded as an honest difficulty **before** anything was built, because the
three are not equally knowable:

| App | Source | Difficulty |
|-----|--------|------------|
| Explorer | `Shell.Application` over the Quick Access shell folders — `{3936E9E4-…}` (pinned + frequent FOLDERS) then `{679F85CB-…}` (Quick Access itself, filtered to folders) | a clean API; `comtypes` already ships with `uiautomation` |
| VS Code | `%APPDATA%/Code/User/globalStorage/storage.json` → `lastKnownMenubarData.menus.File.items` → the "Open Recent" submenu's `openRecent*` entries | a plain read; the key was verified against the real file on this machine, 2026-08-11 |
| Chrome | nothing — **New window** and **Incognito** only | its recently-closed list lives in an undocumented binary session file; parsing is deferred |

## The rules
1. **An entry that cannot be opened is not an offer.** An app with no
   executable contributes no rows at all, and a recent path that has since
   vanished comes back as a NAMED error the phone toasts. A row that does
   nothing when tapped is the dead-button failure of task 166 in a new panel.
2. **Every app starts with a plain New window.** A recent list can legitimately
   be empty, and an app with no rows would read as uninstalled.
3. **VS Code is forced to open a NEW window** (`-n`). Without it VS Code
   re-uses the window that already holds the folder, so the flow would produce
   no new member — and might silently "join" a window a layout already owns.
4. **Only a handle that was NOT standing before the launch may be handed
   back.** This is the correctness argument, and it is this project's oldest
   lesson in a new place: every VS Code window shares one process
   (`docs/DECISIONS.md` constraint 11), so "a window of the app I started" would very
   likely be the one he was already working in. The handles are written down
   before the launch and only a new one is returned.
5. **Nothing here ever takes the foreground.** Launching an app naturally makes
   Windows raise its own window — that is what he asked for — but this module
   never calls `SetForegroundWindow`, never raises, places or pins anything.
   Every placement afterwards belongs to the creation flow.

## The honest limits
* **Chrome recents are not read.** Two plain entries stand in their place.
* **VS Code's list is a cached MENU.** A profile whose File menu has never been
  opened, or a VS Code fork under another folder name, yields nothing — and
  nothing is returned, never a guess.
* **Quick Access is mostly recent FILES.** Only its folders are offered, so the
  list is usually shorter here than in Explorer's own pane.
* **A path can be gone.** Opening it is what discovers that.

## Interfaces
* `GET /recents?token=…` → `{ok, entries: [{id, app, kind, label, sub}]}` —
  `kind` is `new` | `private` | `recent`, and it is the only thing the opener
  reads.
* `POST /recents/open?token=…` `{id}` → `{ok, window: {hwnd, title, process,
  icon}}` or `{ok: false, error}`.

Both are registered from [Server Core](server_core.md) beside
[Layout Popup](layout_popup.md)'s own route, and both are HTTP rather than
WebSocket for the same reason: the socket's dispatcher lives in
[Web Layer](../web.py), and a list and a window are plain request/response.

## Gate
`tests/test_layout_birth.py` — the list sources, the honest Chrome limit, the
not-installed rule, the vanished-path error, and the newness rule, each proven
by planting its own defect.

## Look first, sleep after (2026-08-12)

`open_entry`'s wait loop polled AFTER its sleep, so an app that already had its
window up when `Popen` returned — Explorer on a warm cache, a second Chrome
window — still cost a flat `OPEN_POLL_S` before anyone looked: 250 ms of the
phone's loading cube spent watching a window that was already there. The sleep
is now at the end of the turn. Nothing else changed, timeout included.

Gate: `tests/test_return_speed.py`.
