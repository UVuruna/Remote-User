# Notify

**Script:** [Notify (script)](../notify.py) ·
**Flow:** [diagram](../__flow/notify.md)

## Purpose

"The PC calls you" — ROADMAP Phase H (owner 2026-08-05). A job on this PC
finishes and the phone says **which one**:

> *"nije dovoljno samo da kaže beep kad završi agent … najbolje od svega je
> da izbaci notifikaciju koja opisuje koji agent je završio, a ime agenta je
> ime sesije u suštini"*

The owner runs several agents at once, so the AGENT's name is the message.
A sound alone carries no information when four of them are working.

`POST /notify?token=…` with `{agent, event, text}` → the connected phone gets
a `notify` frame → [Notify (client)](../../client/__about/notify.md) raises a
real Android notification, speaks it, and toasts if the page is visible.

## Why a push, not a watcher

The alternative was reading the screen (UIA on the Claude panel, or watching
pixels for a spinner). It was rejected on the merits, not on effort:

- a long silent build looks **identical** to a finished one on screen;
- nothing on screen can tell four agents apart;
- every editor/agent version would move the thing being read.

Whatever finishes already KNOWS it finished, so it tells us. That also makes
the feature general: any tool that can run a command on completion — a build,
a test suite, a render — gets the same notification for free.
[setup/agent_hook.py](../../setup/___setup.md) is the Claude Code `Stop` hook
that does it.

## Connections

### Uses
- the web layer's own one-device slot (`active_client`) — this module keeps
  no second registry, so the phone that took the session over (code 4409) is
  the one that hears about it

### Used by
- [Web Layer](web.md) — `notify.register(app, token, active_client)` inside
  `create_app`
- [setup/agent_hook.py](../../setup/___setup.md) — the Stop hook that POSTs
- [tests/test_notify.py](../../tests/___tests.md) — the gate

## Functions

- `clean(value, limit, fallback)` — one incoming field: string, trimmed,
  length-capped. Nothing from a POST body reaches a notification unclamped.
- `compose(agent, event, text) -> (title, body)` — the AGENT leads, the event
  is the verb (`EVENT_WORDS`: finished / needs you / failed), free text is the
  second line. An unknown event is shown as-is rather than swallowed.
- `register(app, token, active_client)` — adds the route.

## Design Decisions

- **Nothing is queued.** With no phone connected the answer is
  `{"ok": false, "reason": "no phone connected"}`. An alarm that arrives an
  hour late is worse than no alarm, and the caller can decide what to do.
- **The token is the same one the phone uses.** No token, no answer — a
  notification endpoint that anyone on the LAN could ring is a way to make
  the owner's phone buzz at will.
- **Its own module, not another branch in `web.py`.** One responsibility with
  its own route and its own gate; `web.py` is the busiest file in the project
  and was being split for exactly this reason on the same day.
