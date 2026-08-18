# Popup Contain

**Script:** [Popup Contain (script)](../popup_contain.py)
**Flow:** [Popup Contain - Flow](../__flow/popup_contain.md)

## Purpose

WHERE an adopted window is put, so the phone can operate it. Split out of
[Layout Popup](layout_popup.md) on 2026-08-18 (THE STRUCTURE LAW, VC-R5).

One responsibility: the owner's own ladder (2026-08-11, amended 2026-08-13) -
on its parent if we know it, else inside the layout's region, else full screen
over the streamed monitor. WHOSE window it is and whether to ask him are
decided next door; by the time anything here runs, that is settled.

MEASURED, never remembered (constraint 13): the region is the union of the
members' real frame rects read fresh, the popup's own frame is read fresh, and
"it cannot fit" is what a window REFUSING the region looks like from here -
never a size we predicted.

## Connections

### Uses
- [Window Manager](window_manager.md) - `_frame_rect`, `place_window` (which
  verifies, and which enters the always-on-top LEDGER), `_work_area`
- [Grids](grids.md) - `PLACE_TOLERANCE_PX`, the slack a placement is judged on

### Used by
- [Layout Popup](layout_popup.md) - `adopt_owned` on rule 1, `describe` in
  every log line
- [Popup Offers](popup_offers.md) - `contain` when he taps "Move it in"
- [Layout Registry](layout_registry.md) - `contain` when a layout re-focuses
- [Layout Birth](layout_birth.md), [Offer Withdraw](offer_withdraw.md),
  [Window Rescue](window_rescue.md) - `describe`, so one window reads the same
  way in every log line about it

## Functions

- `MAX_CONTAIN_TRIES`: how many times one window may be pushed before it is
  left where it is
- `_region(lay)`: the rect the phone is really framing, measured now
- `_inside(rect, region)` / `_centered_in(rect, box)`: the two geometry tests
- `describe(hwnd)`: `process "title" (0xhandle)` - one window, one wording
- `contain(lay, hwnd, conn, anchor=None)`: the ladder
- `adopt_owned(lay, hwnd, root, conn)`: a member's OWN popup, placed on it
  without asking, with the home rect remembered so it can be given back
