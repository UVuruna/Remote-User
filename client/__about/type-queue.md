# type-queue.js — the outbound queue for messages that TYPE

**Script:** [Type Queue (script)](../type-queue.js) · **Flow:** [Type Queue (flow)](../__flow/type-queue.md)

## Purpose

A bounded queue for the four message kinds that TYPE (`key_text`,
`key_special`, `chord`, `paste_text`), so a short WebSocket outage does not
silently drop a keystroke. [State](state.md)'s `send()` pushes onto it when
the socket is not OPEN; [Connection](connection.md)'s `sock.onopen` flushes it
after `auth`. Pure, like [Voice](voice.md) and [Kb Sync](kb-sync.md) before
it, so `tests/test_type_queue.py` can run it whole in node.

## The measured defect (2026-08-13, HALF 1 of 2)

`client/state.js`'s `send()` fired a message only while
`ws.readyState === OPEN`; otherwise it called `ensureConnected()` and
returned — no queue, no retry, no record anything was ever asked for. A
simulation driving the REAL `client/controls.js` input handler and the REAL
`send()` opened a 200ms outage inside a 20-key backspace burst (an ordinary
mid-line edit) and swallowed 8 of 21 messages: the phone showed "the q", the
PC "the quick bro" — and every LATER keystroke on a HEALTHY link kept the
gap, because [Kb Sync](kb-sync.md)'s `kbPrev` (the phone's own model of the
PC text) is never told a message failed to arrive.

Amplification is what makes this likely, not rare: one mid-line backspace
costs roughly `2×(chars after the caret)+1` messages — 21 at 40 characters, 41
at 80, 61 at 120 — so a short blip lands inside a burst far more often than
inside a single keystroke.

HALF 2 of the same defect is `key_special`'s own missing loss report — see
[Focus Guard](../../server/__about/focus_guard.md) and
`tests/test_key_special_loss.py`.

## The bound, and why it has two axes

A brief reconnect (a WiFi hiccup while the phone sits exactly where it was)
should not cost the owner a word. But an outage long enough that he has
plausibly moved his attention — put the phone down, switched apps, walked
over to the PC himself — turns a queued replay into something WORSE than a
drop: a burst of stale backspaces landing in whatever field is now focused,
deleting text he never asked to touch, with no drop toast to explain it
because the replay "succeeded". So the queue is bounded on both count and
age:

- **`TYPE_QUEUE_MAX` = 64** — sized off the amplification numbers above: it
  covers a 120-character mid-line edit (61 messages) with headroom, while
  staying well short of "the owner walked away and is still sending keys" (in
  practice staleness below catches that case first; the count cap is the
  backstop for a burst that somehow outgrows it).
- **`TYPE_QUEUE_STALE_MS` = 4000** — longer than an ordinary WiFi blink,
  shorter than [State](state.md)'s own `CONNECT_TIMEOUT_MS` (6000) and
  `SERVED_TIMEOUT_MS` (8000): this queue exists for outages that resolve on
  their own, faster than either of those give-up points.

**Staleness is all-or-nothing, never a per-item filter.** Once the OLDEST
queued message is stale, the whole queue is abandoned rather than replayed
piecemeal — a partial replay would put some but not all of a backspace-heavy
edit through, exactly the silent, confusing half-state this fix exists to
end.

## What is NOT queued, and why

Every message outside the four typing kinds keeps `send()`'s pre-existing
behaviour: call `ensureConnected()` and drop it. A queued `click` replayed a
second late lands wherever the cursor sits THEN, not where it was aimed; a
queued `layout_focus` replayed after the owner already chose something else
on reconnect would fight his own next tap. Typing is the one category where
the destination — whatever box is focused on the PC, which the owner is
watching per the whole design of this app — does not become a different,
wrong target merely because a few seconds passed.

## Connections

### Uses

Nothing. The module is pure by design (see above).

### Used by

- [State](state.md) — `send()` calls `typeQueueKind`/`typeQueuePush` on the
  dead-socket path; `flushTypeQueue()` (defined in state.js, not here — it
  owns the toast/blur giveup policy) calls `typeQueueFlush`
- [Connection](connection.md) — `sock.onopen` calls `flushTypeQueue()` after
  `auth` is sent
- [Tests (folder)](../../tests/___tests.md) — `tests/test_type_queue.py` runs
  this module whole in node and proves the wiring into state.js/connection.js
