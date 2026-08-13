// Outbound queue for messages that TYPE — the phone's own half of the
// 2026-08-13 MEASURED defect (server half: server/focus_guard.py's
// key_special loss report, tests/test_key_special_loss.py).
//
// THE MEASURED FAILURE. `client/state.js`'s `send()` fires a message only
// while the socket `readyState === OPEN`; otherwise it calls
// `ensureConnected()` and returns — no queue, no retry, no record that
// anything was ever asked for. A simulation driving the REAL
// `client/controls.js` input handler and the REAL `send()` opened a 200ms
// outage inside a 20-key backspace burst (a normal mid-line edit) and
// swallowed 8 of 21 messages: the phone showed "the q", the PC "the quick
// bro" — and EVERY LATER KEYSTROKE ON A HEALTHY LINK kept the gap, because
// `kbPrev` (kb-sync.js's model of what the PC now holds) is never told a
// message did not arrive. Amplification is what makes this likely rather
// than rare: one mid-line backspace costs ~2x(chars after the caret)+1
// messages — 21 at 40 chars, 41 at 80, 61 at 120 — so a short blip lands
// inside a burst far more often than inside a single keystroke.
//
// THE FIX, and why it is bounded rather than unlimited. A brief reconnect
// (a WiFi hiccup while the phone sits exactly where it was) should not cost
// the owner a word. But an outage that runs long enough for him to have
// moved his attention — put the phone down, switched apps, walked over to
// the PC himself — turns a queued replay into something WORSE than a drop:
// a burst of stale backspaces landing in whatever field is now focused,
// deleting text he never asked to touch, with no drop toast to explain it
// because the replay "succeeded". So the queue is bounded on BOTH axes:
//
//   - COUNT (`TYPE_QUEUE_MAX`): sized off the amplification numbers above —
//     64 covers a 120-character mid-line edit (61 messages) with headroom,
//     while staying far short of "the owner walked away and came back
//     twenty minutes later and is still sending keys" (which staleness
//     below catches first, in practice, but the count cap is the backstop
//     for a burst that somehow outgrows it).
//   - AGE (`TYPE_QUEUE_STALE_MS`): 4000ms — long enough that an ordinary
//     WiFi blink (state.js's own CONNECT_TIMEOUT_MS is 6000, SERVED_TIMEOUT_MS
//     8000 — this queue is for outages SHORTER than either, the ones that
//     resolve on their own) never loses a keystroke, short enough that a
//     genuinely dead link gives up before the owner has plausibly moved on.
//
// STALENESS IS ALL-OR-NOTHING, never a per-item filter: once the OLDEST
// queued message is stale, the whole queue is abandoned rather than
// replayed piecemeal. A partial replay would put some but not all of a
// backspace-heavy edit through — exactly the kind of silent, confusing
// half-state this fix exists to end. Dropping everything and TELLING the
// phone (state.js's own job, via the existing toast, never a new channel)
// is the honest answer: he sees "some typing wasn't sent" and can look at
// the PC screen — which he is already watching per the whole design of this
// app — and decide whether to retype.
//
// WHAT IS NOT QUEUED, and why: every message OUTSIDE the four typing kinds
// (pointer/click/scroll/layout/etc.) keeps `send()`'s existing behaviour —
// call `ensureConnected()` and drop it. A queued CLICK replayed a second
// late lands at whatever the cursor sits over THEN, not where it was aimed;
// a queued LAYOUT SWITCH replayed after the owner already chose something
// else on the reconnect would fight his own next tap. Typing is the one
// category where the DESTINATION (whatever box is focused on the PC, which
// the owner is looking at) does not become a different, wrong target merely
// because a few seconds passed — it is the same box until he moves the
// caret himself, on the PC or the phone.
"use strict";

const TYPE_QUEUE_KINDS = new Set(["key_text", "key_special", "chord", "paste_text"]);
const TYPE_QUEUE_MAX = 64;
const TYPE_QUEUE_STALE_MS = 4000;

/** Is this message one of the four kinds that TYPE — the only ones this
 *  queue ever holds. */
function typeQueueKind(msg) {
  return !!(msg && TYPE_QUEUE_KINDS.has(msg.type));
}

/** Push one message onto `queue` (an array of `{msg, t}`, oldest first) at
 *  time `now`. Returns `{queue, dropped}` — a NEW array (the caller holds
 *  the queue in a `let`, same immutable-update shape as `kbDiff`'s callers)
 *  and how many of the OLDEST entries were evicted to stay at
 *  `TYPE_QUEUE_MAX`. A caller with `dropped > 0` must tell the phone —
 *  see the module header on why silence here is the exact bug this queue
 *  exists to end. */
function typeQueuePush(queue, msg, now) {
  const next = queue.concat([{ msg, t: now }]);
  let dropped = 0;
  while (next.length > TYPE_QUEUE_MAX) {
    next.shift();
    dropped++;
  }
  return { queue: next, dropped };
}

/** What to actually SEND on reconnect, at time `now`. All-or-nothing on
 *  staleness (module header): the OLDEST entry decides for the whole queue,
 *  because a queue old enough to distrust is old enough to distrust WHOLE —
 *  a caret-position replay half right is not a safer failure than no replay
 *  at all. Returns `{messages, dropped}` — `messages` in original order,
 *  ready to hand to `send()` one at a time; `dropped` is the count that was
 *  thrown away for staleness (0 or the whole queue's length, never
 *  in-between). Never mutates `queue`. */
function typeQueueFlush(queue, now) {
  if (queue.length === 0) return { messages: [], dropped: 0 };
  const oldest = queue[0].t;
  if (now - oldest > TYPE_QUEUE_STALE_MS) {
    return { messages: [], dropped: queue.length };
  }
  return { messages: queue.map((e) => e.msg), dropped: 0 };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    TYPE_QUEUE_KINDS, TYPE_QUEUE_MAX, TYPE_QUEUE_STALE_MS,
    typeQueueKind, typeQueuePush, typeQueueFlush,
  };
}
