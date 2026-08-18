# Popup Offers

**Script:** [Popup Offers (script)](../popup_offers.py)

## Purpose

THE CHIP: the question the phone asks about a new window, and his tap. Split
out of [Layout Popup](layout_popup.md) on 2026-08-18 (THE STRUCTURE LAW,
VC-R5). The offer registry, its expiry, the frames that carry a chip to the
phone, and `pick()` - where every answer he can give lands.

Every question this project asks about a window goes through `queue_offer`,
including the ones raised next door ([Layout Birth](layout_birth.md), [Window
Rescue](window_rescue.md)): each of them used to keep its own copy of the same
eight lines of bookkeeping, and three copies of that dance is three places for
the day one of them stops matching the others.

The registry is module-level rather than per-connection because the answer
comes back over HTTP (`POST /window_offer`), which has no socket and no `conn`
- the id is the whole handle. An offer whose connection has since died still
resolves safely: the layout is checked, and a window that closed meanwhile is
refused.

## Connections

### Uses
- [Popup Contain](popup_contain.md) - `contain` on "Move it in", `describe` in
  every log line
- [Notice Channel](notice_channel.md) - `page_socket()`, the one-device slot a
  chip is sent over
- [Lost Windows](lost_windows.md) - `rescue` on the lost-window chip
- [Window Manager](window_manager.md) - title, process name, icon for the frame

### Used by
- [Layout Popup](layout_popup.md) - `offer()` for rules 2-4
- [Layout Birth](layout_birth.md) - `queue_offer` for task 185's chip
- [Window Rescue](window_rescue.md) - `queue_offer` for the lost-window chip
- [Focus Guard](focus_guard.md) - `flush_offers(conn)` on the watcher's tick
- [Offer Withdraw](offer_withdraw.md) - `open_offers()` / `drop_offer()`
- [Server Core](server_core.md) - `register(app, token)` beside the app

## Functions

- `OFFER_TTL_S`: how long an unanswered offer is kept (ignoring a chip IS an
  answer, so this only stops a dictionary growing for the life of the process)
- `queue_offer(conn, hwnd, prefix, held, payload, asked_key)`: one function for
  every question this project asks about a window
- `offer(lay, hwnd, conn, reason)`: this module's own three-answer chip -
  Make a layout, Move it in, Leave
- `flush_offers(conn)`: send what the watcher queued, over the page's socket
- `open_offers()` / `drop_offer(key)`: so a question can be UNASKED
- `pick(offer_id, act)`: his tap - rescue, birth, layout_new, layout, or the
  safe default, which moves nothing
- `register(app, token)`: `POST /window_offer`, the answer coming back
