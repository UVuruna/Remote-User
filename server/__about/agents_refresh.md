# Agents Refresh

**Script:** [Agents Refresh (script)](../agents_refresh.py)

## Purpose
The Claude wheel appears the moment the process table says so, not only on
the next `layout_state` a human action (focus, switch, aspect, member
add/remove) already causes.

**Owner report 2026-08-15.** He built a new layout on a VS Code window that
was still loading its previous Claude conversation. `agents_in()` answered
empty at that instant — the transcript had not been written yet — and the
Claude set stayed off the wheel until he switched to Desktop and back,
because nothing in the codebase ever re-asked. [Layout State](layout_state.md)
already computes `agents` live on every send; the gap was that nothing
re-SENT it when the process table changed on its own, between the sends a
human action already triggers.

## Connections

### Uses
- [Agents](agents.md) — `live_agents()` (the 2 s process-table cache),
  `agents_in()`
- [Layout API](layout_api.md) — `send_layout_state()`, the one existing
  choke point every layout-changing message already passes through

### Used by
- [Web Layer](web.md) — one task per connection, started alongside
  `focus_guard.watch` / `caret.watch` / `presence.watchdog` /
  `clipboard_sync.watch`, cancelled the same way on teardown

## Functions
- `_signature(layouts) -> tuple`: one fact per live layout worth re-telling
  the phone — which agent tools it holds, keyed by object identity so a
  rename never reads as a change. This is the whole comparison; nothing
  heavier is computed.
- `watch(ws, layouts, conn)`: polls every `POLL_S` (5 s) while a layout
  exists and the phone is not away/left, recomputes the signature off the
  worker thread, and calls `send_layout_state` only when it differs from the
  last one sent. A signature equal to the last is never a send — the
  constraint 27 lesson (a `layout_state` that changes nothing must not be
  sent for ITS sake either) applies here just as much as to the zoom.

## Honest limits
- The poll is 5 s: a Claude conversation whose transcript starts writing a
  few seconds after the layout was made reaches the wheel within one poll,
  never instantly. A tighter interval was rejected — `agents.live_agents()`
  already caches at 2 s, and polling faster than that cache buys nothing.
- Goes quiet while the phone is away or has left: nobody is reading the
  wheel then, and a send would only race the returning connection's own
  resume logic.

## Gate
`tests/test_agents_refresh.py`, fail-closed in `setup/gates.py` alongside its
neighbours — proves a signature change sends exactly one `layout_state` and
an unchanged process table sends none.
