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
- [Window Icons](window_icons.md) — `icon_data_uri`, imported BY NAME so a
  test that fakes a windowless PC can still patch it here (split 2026-08-08,
  THE STRUCTURE LAW)
- [Grids](grids.md) — the layout GEOMETRY
- otherwise pure Win32 via ctypes

### Used by
- [Web Layer](web.md) — `layout_pick`/`layout_create`/`layout_focus`/
  `layout_remove` handlers and the `layout_state` payload

## Closing a window (owner 2026-08-08, task 116)

`close_windows(hwnds)` is the phone pressing a window's own ✕ on his behalf:
`WM_CLOSE`, **posted**, never sent — `SendMessageW` blocks until the target's
message loop answers, and a target showing a MODAL dialog does not answer
until the owner does, which would hold this thread for as long as he takes to
read it. Nothing here ever reaches for `TerminateProcess`: an app with unsaved
work is *supposed* to put up its dialog and survive.

Each window leaves the always-on-top band FIRST (`drop_topmost`) — a save
dialog is a separate window, and its parent must not be hovering over it.

The return value is the point: the windows still standing after
`CLOSE_TIMEOUT_S` (2.5 s). `LayoutRegistry.remove(index, close=True)` passes
them up so the phone can say *"1 window still open — answer the app on the
PC"*. A claim we did not verify is the habit this project keeps paying for.

`remove`'s flag defaults to `False`, and [Web Layer](web.md) reads the wire
field as `is True` rather than truthiness. Two different acts wore one button
until this round and only one of them can be undone from the phone.

## Classes

### Layout
One phone screen: `name` (target's title at creation, or the owner's own),
`process`, ordered `members` (grid cell order; `[window]` for solo),
`template` (None = solo), `orient` ("portrait" | "landscape"), `aspect` (w/h
last arranged for), plus `source` and `folder` — WHERE the layout's project is
read from, never the answer.

`project()` is the read: the member's own title first, then `source` (the
window an extracted tab was torn OUT of, alive, asked fresh), then `folder`
(the project named at creation) as the last resort. `state()` hands the result
to `agents.agents_in`, which is what puts the Claude set on the wheel. The
title itself is NOT stored any more — see the section below.

### LayoutRegistry
The session-scoped list. `create(...) -> index|None` arranges and registers;
`focus(index, device_ratio, mon_rect) -> region|None` re-validates, re-places
on aspect drift, raises members and returns the fresh monitor-normalized
region; `remove(index)`; `prune()`; `state(active, region)` builds the
`layout_state` payload (pruning first, so the phone never lists a dead layout).

`Layout.last_member` is WHICH member holds the keyboard (owner 2026-08-06).
`focus()` raises it **last**, so it is the window left in the foreground; the
[Focus Guard](focus_guard.md) updates it whenever the phone legitimately types
in another member, and `prune()` moves it off a window closed at the desk.
Raising in plain list order was half of the dictation bug: one excursion
closes the socket, the page re-focuses the layout, and the keyboard went to
whichever window sat last in the grid — so his sentence continued in the other
pane.

`rename(index, name) -> bool` gives a layout the OWNER's name (owner
2026-08-05) — the target window's title is only the default the phone's
creation panel prefills; an empty name or a dead index is refused.

`last_focus` + `resume_index()` / `forget_focus()` are where a returning
phone lands (owner 2026-08-05). Every successful `focus` records
`(index, name)`; leaving work mode minimizes everything but keeps the
pointer, so the next session resumes IN that layout instead of dumping the
owner on the desktop. Both halves must still match — a list that changed
while the phone was away resumes on the desktop rather than on the wrong
window — `remove()` shifts/clears it with the list, `rename()` keeps it
valid, and a deliberate Desktop choice (`forget_focus`, called by the web
layer on `layout_focus -1`) means the desktop IS the state to resume into.

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
  of another layout, layout removal, and the phone leaving work mode. That
  last one is what the [Web Layer](web.md)'s presence watchdog exists for:
  the always-on-top band is only correct while the phone is really showing
  the layout, and a locked phone cannot say so by itself (owner 2026-08-05)
- `is_alive(hwnd)`: window exists, visible, not DWM-cloaked

## Per-layout aspect ratio + position (owner 2026-08-03, position 2026-08-05)
Each layout carries its own `ratio` (W:H, `None` = the phone's own shape) and
`pos` (0–1 fraction of the free-axis slack, 0.5 = centered — the phone's Move
handle), set from the phone's aspect panel via `set_ratio(index, w, h, pos)`
and applied by the next `focus` (which is what re-places the windows). Both
ride in `layout_state` entries.

**The arrangement is VERIFIED, never merely remembered** (owner report
2026-08-07 — the Move handle's SECOND round: he set 10:13 portrait, dragged the
handle to the top, pressed Apply, and the window came out vertically centred,
"uvek ostavi centrirano"). `arranged_ratio`/`arranged_pos` are a note of what
was COMMANDED — they are written from an intention, and the old guard was that
note alone. So the moment a member left its rect for any reason (the app
re-laying itself out, a restore out of the taskbar, a Windows snap, a
placement that quietly did not take), the note became a lie and every later
Apply of the SAME position matched it and re-placed NOTHING: the phone's panel
moved and the PC never did again. `focus` therefore computes the targets fresh
every time and asks `_standing(members, targets)` where the windows REALLY
are (`grids.at_rect`, the same ±8 px tolerance `wait_landed` uses, so a
min-size app that legitimately sits larger never re-places forever); and the
note is written only when the placement LANDED — a refusal leaves it unwritten
(`None` / `-1.0`), logs a warning naming the layout, and the next focus tries
again. Same law `layout_state` already lives by (owner 2026-08-04): a claim
about windows is measured, not remembered. Gated by
`tests/test_layout_protocol.py`, which asserts on the placement RECT.

`layout_region(mon_rect, aspect, ratio, pos)` is the single place the rule
lives: the DEVICE shape gives the outer box (`_region_rect`), and the override
is the largest rect of that W:H fitted INSIDE it (`_fit_rect`), placed at
fraction `pos` of the leftover slack (only one axis ever has slack, so a
single fraction covers both orientations). The region can therefore only ever
shrink — portrait keeps the phone's full width and only loses height,
landscape keeps its height and only loses width; anything that would grow past
the phone's shape is clamped by the same fit. The unused strip stays black on
the phone.

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

## The topmost ledger (owner decree 2026-08-05)

The always-on-top band is ours only while we are running to take it back, and
twice the owner came to his desk to find HIS Chrome and HIS VSCode nailed above
everything with nothing left alive to lower them. So every hwnd we raise is
written down (`mark_topmost`), and there are exactly two ways out — one for
each way this process can end:

1. **We get to run code** — tray Quit, server stop, Apply & restart, Ctrl+C, a
   console close, an unhandled crash, Windows logoff: `release_all()` walks
   the ledger. It is wired into `ServerController.release_windows()` (called
   before every stop and in `_serve`'s `finally`), Qt's `aboutToQuit`,
   `atexit` in both entry points, and a `SetConsoleCtrlHandler` in the CLI.
   Idempotent — running all of them is the design.
2. **We do NOT** — Task Manager, the installer's `taskkill`, a power cut:
   nothing inside the process can help, so the ledger is mirrored to
   `SETTINGS.topmost_ledger_path` on every change and `repair_stranded()`
   reads it at the next start (`ServerController.__init__`). A recycled handle
   could by then belong to a stranger's window, so an entry is acted on ONLY
   while its window still runs the executable it ran when we raised it.

`LayoutRegistry.clear_topmost()` now delegates to `release_all()`: it goes
through the LEDGER, not the member lists, because a window that fell out of its
layout (closed, cloaked, extracted as a tab) is exactly the one no member list
can name — and exactly the one that used to stay stranded.

Three more corrections from the same audit:

- **`raise_window(hwnd, topmost=False)`** — the function was doing two jobs
  under one name. `True` is "this is what the phone shows" (TOPMOST + a ledger
  entry); `False` is "bring this forward for a moment" (HWND_TOP, no entry),
  which is what [UIA](uia.md) needs for tab extraction and `next_input`.
- **`drop_topmost` is VERIFIED and returns a bool.** SetWindowPos can be
  refused (a higher-integrity window, a hung owning thread), and a window we
  failed to lower KEEPS its ledger entry — that is precisely the record the
  next start's repair needs.
- **`prune()` drops CLOSED windows, not merely hidden ones**, and returns the
  surviving original indices. Windows cloaks every window on another VIRTUAL
  DESKTOP and Store apps while minimized, so pruning on `is_alive` meant the
  owner pressing Win+Ctrl+Right silently DELETED his layout and abandoned its
  members — still on screen, still always-on-top — in a list nothing could
  reach. The returned index map is what lets `state()` follow the focused
  layout through a prune instead of pointing at whatever slid into its place.

## A layout carries NO answer about its app sets (owner 2026-08-07)

`Layout.app_sets` existed for exactly one day and this section is its
tombstone, because the mistake is worth more than the feature was.

The problem it answered is real. Probing his PC with a Claude Code
conversation open found the window titled
`Ispravka UI dizajna meni… - Remote User - Visual Studio Code [Administrator]`
and its tab `Ispravka UI dizajna meni…, Window 2: Editor Group 1` — Claude
Code names itself after the CONVERSATION. Beside it sat `prompt.txt` with an
identical UIA class and empty `AutomationId`/`HelpText`; a walk of the whole
extracted window (20 elements) found no "claude" anywhere, VSCode keeping its
webview content out of accessibility. No string on this machine identifies it.

The answer chosen on 2026-08-06 was to make the OWNER tick it at creation. The
answer built the *same day* was `server/agents.py`, which reads the process
table and knows. Both shipped, and the tick list won: the client answered a
layout that carried the list "from it ALONE". So the list — written once, out
of whatever the PC happened to see in that second — outranked a live detection
that was saying `claude` on every `layout_state`, forever, and his Claude
layout offered the VS Code wheel and nothing else.

**The rule that came out of it: never store an answer the PC can read.**
`state()` asks `agents.agents_in(lay.project(), live)` on every frame, with one
process-table snapshot for the whole frame.

### …and it did not stop at `app_sets` (owner report 2026-08-08)

The very next round he built a layout out of the Claude Code TAB, and the wheel
offered VS Code alone. `Layout.title` was the reason, and it was the SAME
mistake one layer up: a one-shot snapshot of a window taken 0.15–1.5 s after it
was born, handed to `agents_for` on every frame forever. VS Code creates every
"Move into New Window" window with `title: productService.nameLong` on
`about:blank` and the workbench overwrites `document.title` only afterwards, so
a torn-off tab is BORN titled `Visual Studio Code` — no folder, nothing any
regex can match, and `agents_for` correctly answering "no agent" to a string
that names no project. Freezing it made that answer permanent.

So `Layout.title` is gone. What the layout keeps is WHERE to look:

| Kept | What it is | Why it is not an answer |
|------|-----------|-------------------------|
| `members[0]` | the window itself | its title is read live, every frame |
| `source` | the window an extracted tab was torn out of, `0` = none | a HANDLE; its title is read live too, and it is checked alive first |
| `folder` | the project its title named at creation | last resort, for a source that has since closed. A folder is not an answer — whether a conversation is LIVE in it still comes from the process table on every frame |

`layout_state.title` is likewise read at send time (`prune()` has just run, so
the member is alive and can simply be asked). Creation logs the whole reading —
`Layout %r from %#x (tab source %#x): title %r, project %r` — because THE
REPEAT LAW asks for a claim checkable in HIS log, not in ours.

Gate: `tests/test_app_set_wheel.py` → section F. It drives the real
`layout_create` with a TAB slot and asks the real `client/sets.js` which set
names come out, over the whole family of titles a torn-off window can carry
(bare product name, the tab's own name, empty, settled-with-folder). Both
earlier guards were green throughout the bug because each hand-typed one half
of the join — the server gate faked `agents_for` and answered `_title` with one
string for every hwnd, the phone gate was handed `agents: ["claude"]` as an
input. **When a value the phone reads is DERIVED from another, the gate feeds
the derivation's INPUT, never its output.**
