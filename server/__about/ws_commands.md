# WS Commands

**Script:** [WS Commands (script)](../ws_commands.py)
**Flow:** [WS Commands - Flow](../__flow/ws_commands.md)

## Purpose

THE PHONE'S COMMANDS: one handler per `kind`, in one registry. Split out of
[Web Layer](web.md) on 2026-08-18 (THE STRUCTURE LAW + ONE KIND ONE CLASS,
VC-R2).

Until this round every client message was a branch in a 366-line
`if kind == "hb": / elif kind == "press": / ...` chain inside
`web._receive_input`, and adding a command meant inserting another `elif` into
one function. That is the exact shape THE ONE KIND, ONE CLASS LAW names a
violation - a kind with 41 instances, no registry, grown by copying a branch -
and it was also most of why `web.py` sat at the 1,000-line wall through three
consecutive splits (the OOP audit of 2026-08-18, finding 1a).

A command is now an OBJECT in `HANDLERS`: `@on("layout_grid")` above an
`async def`. Adding one is adding an entry.

## The `Wire`

Each branch used to read four things straight out of `_receive_input`'s
closure - `ws`, `injector`, `stream`, `token` - plus the two the loop threads
through (`layouts`, `conn`) and the message itself. A registry has no closure,
so those seven travel in one explicit `Wire` dataclass, built once per message
by the loop that owns the socket.

That is not merely plumbing: it is what a handler may touch, written down. A
command cannot reach the receive loop, the auth state or the send task,
because it is never handed them.

`Wire.kind` is a property over `msg["type"]` - the pointer trio share one
handler exactly as they shared one branch, and it still has to know which of
the three it got.

## What the SPLIT deliberately did not move

Everything that runs for every message alike stayed in `web._receive_input`,
because it is the frame a command arrives in and not a command:

- the presence bookkeeping (`seen`, `away`, `left`, `paused`)
- the FOCUS PRELUDE - `TYPING_KINDS` / `RETARGET_KINDS` and the
  `focus_guard.guard` / `retarget` call. It must stay in `web.py` in any case:
  `tests/test_claude_panels.py` reads that source text to prove `chord` is
  still fenced
- the double-click note that task 185 reads

## Behaviour, and the one honest difference

Every handler body is byte-identical to the branch it came from. `continue`
became `return`, which is the same statement here - the dispatch was the last
thing in the loop. `hb` and `away` moved into the registry too, from ahead of
the focus prelude: neither is in `TYPING_KINDS` or `RETARGET_KINDS` and
neither is `click`/`press`, so the prelude is a no-op for them and running it
first changes nothing.

The difference: a handler's log lines now carry the logger name
`ws_commands` instead of `web`. Same words, same level, same order - only the
module that says them. `tests/test_quality_reset.py`'s end-to-end check
watches the new name.

## Connections

### Uses
- every module a command acts through: [Layout API](layout_api.md),
  [Layout Acts API](layout_acts_api.md), [Claude API](claude_api.md),
  [Ledger API](ledger_api.md), [Actions API](actions_api.md),
  [Monitor API](monitor_api.md), [Content](content.md),
  [Clipboard Sync](clipboard_sync.md), [Focus Guard](focus_guard.md),
  [Presence](presence.md), [Traffic](traffic.md), [UIA](uia.md),
  [Notify](notify.md), [Config](config.md)

### Used by
- [Web Layer](web.md) - `_receive_input` looks a message up in `HANDLERS` and
  hands it a `Wire`. That is the whole dispatch.

## Functions

- `Wire`: the seven things a handler may act on
- `on(*kinds)`: the decorator that registers one handler under every kind it
  serves; a second registration for the same kind raises at import, so two
  handlers for one command cannot ship
- `HANDLERS`: `kind` -> coroutine
- `_screenshot(...)`: the one helper that moved with its command
