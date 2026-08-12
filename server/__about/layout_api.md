# Layout API

**Script:** [Layout API (script)](../layout_api.py)

## Purpose
The protocol handlers for the phone's LAYOUT commands — pick, list, create,
focus, aspect, state — with [Window Manager](window_manager.md) as their
engine and [UIA](uia.md) as the tab layer underneath.

Split out of [Web Layer](web.md) on 2026-08-05 (THE STRUCTURE LAW): one
coherent responsibility that had ended up living in the module where every
kind of message happened to be handled.

## The rule these handlers keep
Owner decree 2026-08-04, hardened 2026-08-05 after his windows were left
hovering for the second time: **a layout member is above EVERYTHING while the
phone is showing it, and above nothing the moment it is not.** Every function
here is therefore either a raise or a release, and
[Window Manager](window_manager.md)'s topmost ledger is what makes the release
total — including for windows no layout can still name.

## Interface
| Function | What it does |
|----------|--------------|
| `toast(ws, text)` | the one-line notice on the phone's status pill (defined here because these handlers are its heaviest user and web.py imports from this module, never the other way round — one definition, no copy) |
| `mon_rect(stream)` | the displayed monitor's rect, for every normalized coordinate |
| `send_layout_state(ws, layouts, conn)` | the `layout_state` payload; the connection ADOPTS the focus it returns, because a prune may have SHIFTED it, not only cleared it |
| `layout_pick(ws, layouts, stream, msg)` | one armed tap → the window (and tab) under it, plus the grid templates |
| `layout_list(ws, layouts, stream)` | every window PLUS each window's content tabs; windows already in a layout are left out. A tab rides only when its window has MORE THAN ONE ([UIA](uia.md) → `offerable_tabs`, owner 2026-08-09), and a minimized window carries `tabs_hidden` instead of quietly showing fewer rows than it will after a restore |
| `grid_for(layouts, count, wanted)` | the shape `count` windows can REALLY wear, plus what to tell the phone when that is not the shape it asked for (see below) |
| `resolve_slot(ws, stream, slot)` | one creation slot → `(hwnd, tab name, SOURCE hwnd)`; a slot naming a TAB is extracted into its own window first, and every failure falls back to the whole window. The third value is the window the tab was torn OUT of (`0` = nothing was extracted) — a torn-off VS Code tab can be born titled bare `Visual Studio Code`, and that source window is then the only one that can still name the project (owner 2026-08-08; the layout keeps its HANDLE, never its answer — see [Window Manager](window_manager.md) → `Layout.project`) |
| `layout_create(ws, layouts, stream, conn, msg)` | resolve every slot (one cube turn per slot), derive the shape from what ARRIVED (`grid_for`), register, then focus. **Every slot's SOURCE is passed on, not just the first** (task 173, 2026-08-09): `resolve_slot` returns the window a tab was torn out of, and only `resolved[0]`'s used to be kept — so a tab extracted into cell 2, 3 or 4 left no record, and the ⭐ (task 169) plus the ✕ chooser's warning (task 171) both under-reported on exactly the grids they exist for. Handed to `create` as a dict keyed by the extracted window, because `create` filters and truncates the member list and a positional list would have to be kept in step by hand |
| `layout_aspect(ws, layouts, stream, conn, msg)` | store this layout's W:H and free-axis anchor `pos`, then re-focus — the focus re-places windows for a RATIO change (always centred since 2026-08-09) and sends the `layout_state` whose `pos` anchors the picture on the phone |
| `layout_member_remove(ws, layouts, stream, conn, msg)` | throw ONE window out of a grid (owner request 2026-08-09, task 165): a four becomes a three, a three a two, a two a single, and the survivors are RE-ARRANGED by the focus that follows — three windows still standing in a 2×2 is not a three. It is **not** a close (only the ✕ chooser closes windows, and only when he asked); the window leaves the layout, leaves the topmost band and stays standing where it is. Removing the LAST member removes the layout, through `remove()` and not a second teardown — with the same `conn["active"]` bookkeeping `layout_remove` does. A `member` that names nothing is refused IN WORDS: a silent no-op reads as the button being broken |
| `layout_focus(ws, layouts, stream, conn, index)` | `-1` = the full desktop, which also minimizes every member. A REFUSED placement schedules `_retry_place` (task 231, owner report 2026-08-11: a grid whose windows he had moved with the mouse drew only the top member, and only reopening the layout healed it — `place_pending` already re-placed on the next focus, but "next focus" was HIS act): one automatic re-place ~1.2 s later, only while the phone still shows that layout; a second failure leaves the standing order for the next manual focus. Gated in `tests/test_layout_protocol.py` (two 231 checks, planted-defect proven) |

## A grid is built from the windows that ARRIVED (owner 2026-08-09, task 166)
The phone's `grid` is a **request**, never the answer. Slots die between the
pick and the create, a tab refuses to be extracted, and — until this round —
the panel itself offered a grid of four while the desktop held three. The
server then built it in silence, because every link behaved: `create`
truncates its members to the template's cells, `zip` stops at the shorter
side, `placed` stays `True` since every window it *did* place landed, and the
framed region is the UNION of the cells — so a 2×2 filled by three windows
frames four quadrants and streams bare desktop in the fourth. Nothing was
wrong; nobody had **decided** that a four cannot be built out of three.

`grid_for(layouts, count, wanted)` is that decision, and it does not invent
it: it asks `LayoutRegistry._template_for`, the one definition of "what shape
does a layout of N windows wear", written for `merge` (growing one) and
`drop_member` (shrinking one). Creation is the third way a layout's size is
decided, so it asks the same function rather than growing a second opinion
that can drift. Reaching for a private name is deliberate — the alternative
was a copy.

Every downgrade is **spoken** on the phone's status pill: fewer windows than
the grid needs (*"Only 3 windows were ready — made a 3-window layout instead
of a 4"*), one window left (*"…made a single window"*), or more windows than
any shape holds. A grid that fits toasts nothing — a notice on every create is
noise, and noise is how a real one gets ignored.

Gated by `tests/test_layout_protocol.py`, which measures the **coverage** of
the framed region, not the stored template: under the old behaviour three
windows covered 75 % of the picture his phone was showing.

## Connections
### Uses
- [Window Manager](window_manager.md) — placement, raising, the registry, the ledger
- [UIA](uia.md) — tab hit-test, tab listing, tab extraction
- [Monitors](monitors.md) — `rect_for_size`

### Used by
- [Web Layer](web.md) — dispatches every `layout_*` message here, and imports
  `toast` from here

### Flow
- [Layout API — Flow](../__flow/layout_api.md)

## The encoder is rebuilt BEFORE the phone is told (2026-08-12)

`send_layout_state` ends a session whose crop no longer matches *above* the
`send_text`, not below it. The ffmpeg spawn is ~470 ms on the owner's machine
and `layout_state` is what ARMS the phone's settle watcher, so ending the
session first lets the rebuild and the phone's catch-up run side by side
instead of one after the other. It stays AFTER `layouts.state` — that call is
what re-maps the focus, so the region is final by then; a reset reading a
region the prune was about to null would crop to a dead layout.

`resuming` (optional) is the other half of the same round. On a fresh
connection the server sends an interim frame with `active: null` and only then
focuses the layout it remembers — and `active: null` is exactly the phone's own
restore trigger, so it asked for the focus the server had already started: 11
of 60 "Layout N focused" lines in his log fired within a second of the
previous. The frame now NAMES the resume and the page stands down on it
(keeping its overlay and its rotation lock, which the same seconds still need).

`_retry_place` is deduped per layout (`conn["retry_place"]`) for the same
reason: a duplicated focus armed two of them, and both passed the `active`
guard — two placement passes and two more state frames inside one overlay.

Gate: `tests/test_return_speed.py`.
