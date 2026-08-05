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
| `layout_list(ws, layouts, stream)` | every window PLUS each window's content tabs; windows already in a layout are left out |
| `resolve_slot(ws, stream, slot)` | one creation slot → a concrete hwnd; a slot naming a TAB is extracted into its own window first, and every failure falls back to the whole window |
| `layout_create(ws, layouts, stream, conn, msg)` | resolve every slot (one cube turn per slot), register, then focus |
| `layout_aspect(ws, layouts, stream, conn, msg)` | store this layout's W:H and free-axis position, then re-focus (the focus is what re-places the windows) |
| `layout_focus(ws, layouts, stream, conn, index)` | `-1` = the full desktop, which also minimizes every member |

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
