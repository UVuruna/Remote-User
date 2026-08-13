"""Type Queue Gate — HALF 1 of the 2026-08-13 MEASURED typing-loss defect
(the other half, `key_special`'s own loss report, is gated by
`tests/test_key_special_loss.py`).

`client/state.js`'s `send()` fired a message only while the socket
`readyState === OPEN`; otherwise it called `ensureConnected()` and returned —
no queue, no retry, no record anything was ever asked for. A simulation
driving the REAL `client/controls.js` input handler and the REAL `send()`
opened a 200ms outage inside a 20-key backspace burst and swallowed 8 of 21
messages: the phone showed "the q", the PC "the quick bro", and every LATER
keystroke on a HEALTHY link kept the gap, because `kbPrev` (the phone's model
of the PC text) never learns a message did not arrive.

`client/type-queue.js` (`typeQueueKind`, `typeQueuePush`, `typeQueueFlush`) is
the pure module that fixes this — see its own header for the count/staleness
reasoning. This gate runs it WHOLE in node (the client/voice.js /
client/kb-sync.js pattern) and separately proves the wiring into
`client/state.js` (`send()`, `flushTypeQueue()`) and `client/connection.js`
(the reconnect flush) is real, not merely available.

Run:  .venv\\Scripts\\python tests/test_type_queue.py
Requires: node on PATH — a HARD requirement (test_voice_dedup.py precedent).
Never skip it silently.
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
TYPE_QUEUE = PROJECT / "client" / "type-queue.js"
STATE = PROJECT / "client" / "state.js"
CONNECTION = PROJECT / "client" / "connection.js"


def fail(msg: str) -> None:
    raise AssertionError(msg)


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        fail("node is required for this gate (it runs the REAL "
             "client/type-queue.js rules) — install Node.js. Never skip a "
             "gate silently.")
    return node


def _module() -> str:
    text = TYPE_QUEUE.read_text(encoding="utf-8")
    for needed in ("function typeQueueKind", "function typeQueuePush",
                   "function typeQueueFlush"):
        if needed not in text:
            fail(f"{needed!r} left client/type-queue.js — the gate cannot "
                 "find what it must test")
    return text


def _run(script_body: str) -> dict:
    import json
    script = f"{_module()}\n{script_body}\n"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.mjs"
        path.write_text(script, encoding="utf-8")
        out = subprocess.run([_node(), str(path)], capture_output=True,
                              text=True, timeout=30)
    if out.returncode != 0:
        fail(f"node failed:\n{out.stderr}")
    return json.loads(out.stdout.strip().splitlines()[-1])


# ── typeQueueKind — only the four typing kinds ─────────────────────────────

def check_typing_kinds_are_recognised() -> None:
    out = _run("""
const kinds = ["key_text", "key_special", "chord", "paste_text"].map(
  (type) => typeQueueKind({ type }));
console.log(JSON.stringify({ kinds }));
""")
    if not all(out["kinds"]):
        fail(f"all four typing kinds must be recognised, got {out!r}")


def check_non_typing_kinds_are_not_queued() -> None:
    """`click`, `pointer_move`, `layout_focus`… never belong in this queue
    (module header: a replayed click lands wherever the cursor sits THEN, not
    where it was aimed)."""
    out = _run("""
const kinds = ["click", "pointer_move", "layout_focus", "scroll", "hb"].map(
  (type) => typeQueueKind({ type }));
console.log(JSON.stringify({ kinds }));
""")
    if any(out["kinds"]):
        fail(f"a non-typing kind was accepted into the queue, got {out!r}")


# ── typeQueuePush — the count bound ────────────────────────────────────────

def check_push_appends_in_order() -> None:
    out = _run("""
let q = [];
q = typeQueuePush(q, { type: "key_text", text: "a" }, 0).queue;
q = typeQueuePush(q, { type: "key_text", text: "b" }, 1).queue;
console.log(JSON.stringify({ texts: q.map((e) => e.msg.text) }));
""")
    if out["texts"] != ["a", "b"]:
        fail(f"push must preserve insertion order, got {out!r}")


def check_the_burst_amplification_case_fits_under_the_cap() -> None:
    """The measured worst case named in the module header: a mid-line
    backspace at 120 characters costs 61 messages. That must fit with room
    to spare, or the very scenario this queue was built for still loses
    messages."""
    out = _run("""
let q = [];
let dropped = 0;
for (let i = 0; i < 61; i++) {
  const r = typeQueuePush(q, { type: "key_special", key: "backspace" }, i);
  q = r.queue;
  dropped += r.dropped;
}
console.log(JSON.stringify({ length: q.length, dropped }));
""")
    if out["dropped"] != 0 or out["length"] != 61:
        fail(f"the 120-char backspace burst (61 messages) must fit under "
             f"the cap with nothing dropped, got {out!r}")


def check_pushing_past_the_cap_drops_the_oldest_and_reports_it() -> None:
    out = _run("""
let q = [];
let dropped = 0;
for (let i = 0; i < 70; i++) {
  const r = typeQueuePush(q, { type: "key_special", key: String(i) }, i);
  q = r.queue;
  dropped += r.dropped;
}
console.log(JSON.stringify({
  length: q.length, dropped, oldestKey: q[0].msg.key,
}));
""")
    if out["dropped"] == 0:
        fail("pushing 70 messages past a 64 cap must report drops")
    if out["length"] > 64:
        fail(f"the queue must never exceed its own cap, got length "
             f"{out['length']!r}")
    if out["oldestKey"] == "0":
        fail("overflow must drop the OLDEST entries first (FIFO), not the "
             "newest — the survivors must be the most RECENT keystrokes")


# ── typeQueueFlush — all-or-nothing staleness ──────────────────────────────

def check_a_fresh_queue_flushes_whole_and_in_order() -> None:
    out = _run("""
let q = [];
q = typeQueuePush(q, { type: "key_text", text: "a" }, 1000).queue;
q = typeQueuePush(q, { type: "key_text", text: "b" }, 1500).queue;
const r = typeQueueFlush(q, 2000); // 500ms and 1000ms old — well under 4000
console.log(JSON.stringify({
  texts: r.messages.map((m) => m.text), dropped: r.dropped,
}));
""")
    if out["texts"] != ["a", "b"] or out["dropped"] != 0:
        fail(f"a fresh queue must flush every message in order, got {out!r}")


def check_a_stale_queue_is_dropped_whole_not_partially() -> None:
    """The module's central design choice: staleness is judged by the OLDEST
    entry and applies to the WHOLE queue — never a per-item filter that
    would let some but not all of one edit through."""
    out = _run("""
let q = [];
q = typeQueuePush(q, { type: "key_special", key: "backspace" }, 0).queue;
q = typeQueuePush(q, { type: "key_special", key: "backspace" }, 4001).queue;
const r = typeQueueFlush(q, 5000); // oldest entry is 5000ms old — over 4000
console.log(JSON.stringify({
  messageCount: r.messages.length, dropped: r.dropped,
}));
""")
    if out["messageCount"] != 0:
        fail(f"a stale queue must send NOTHING, not even its newer half — "
             f"got {out!r}")
    if out["dropped"] != 2:
        fail(f"a stale queue's drop count must cover every entry it held, "
             f"got {out!r}")


def check_staleness_is_judged_against_the_oldest_entry_not_the_newest() -> None:
    """A queue whose OLDEST entry is still fresh must flush whole even if it
    has been growing for a while — staleness is about how long a message has
    waited, not how long the queue has existed."""
    out = _run("""
let q = [];
q = typeQueuePush(q, { type: "key_text", text: "a" }, 0).queue;
const r = typeQueueFlush(q, 3999); // just under the 4000ms staleness bound
console.log(JSON.stringify({ messageCount: r.messages.length }));
""")
    if out["messageCount"] != 1:
        fail(f"a queue just under the staleness bound must still flush, "
             f"got {out!r}")


def check_flushing_an_empty_queue_is_a_harmless_noop() -> None:
    out = _run("""
const r = typeQueueFlush([], 99999);
console.log(JSON.stringify({ messages: r.messages, dropped: r.dropped }));
""")
    if out["messages"] != [] or out["dropped"] != 0:
        fail(f"flushing nothing must report nothing, got {out!r}")


# ── Purity + wiring ─────────────────────────────────────────────────────

def check_type_queue_js_stays_pure() -> None:
    """This gate runs the module WHOLE in node — only possible while
    type-queue.js touches no DOM, no socket, no Android bridge (the
    voice.js/kb-sync.js rule, same reasoning)."""
    text = TYPE_QUEUE.read_text(encoding="utf-8")
    code = "\n".join(ln for ln in text.splitlines()
                     if not ln.lstrip().startswith(("//", "*", "/*")))
    for forbidden in ("document", "window.", "ws.send(", "Android"):
        if forbidden in code:
            fail(f"client/type-queue.js reaches for {forbidden!r} — it must "
                 "stay pure so the gate can run it whole")


def check_state_js_wires_the_queue_into_send_and_a_flush_function() -> None:
    text = STATE.read_text(encoding="utf-8")
    if "typeQueuePush(" not in text:
        fail("client/state.js no longer calls typeQueuePush() — a dropped "
             "typing message would go back to being silently lost")
    if "typeQueueFlush(" not in text:
        fail("client/state.js no longer calls typeQueueFlush() — nothing "
             "would ever replay a queued typing message")
    if "function flushTypeQueue" not in text:
        fail("client/state.js no longer defines flushTypeQueue() — "
             "connection.js has nothing to call on reconnect")


def check_a_giveup_shows_a_toast_not_silence() -> None:
    """Requirement 2: the phone must SAY so when a typing message is given
    up on — the existing toast machinery, not a new channel."""
    text = STATE.read_text(encoding="utf-8")
    m = re.search(r"function noteTypeQueueLoss\(\)\s*\{.*?\n\}", text, re.S)
    if not m:
        fail("client/state.js no longer defines noteTypeQueueLoss() — the "
             "give-up path may have gone silent again")
    if "showToast(" not in m.group(0):
        fail("noteTypeQueueLoss() no longer calls showToast() — a give-up "
             "must be VISIBLE (constraint 8: a dropped command that stays "
             "silent reads as \"buttons randomly stopped working\")")


def check_connection_js_flushes_the_queue_after_auth_on_reconnect() -> None:
    """The queue must drain on `sock.onopen`, and strictly AFTER the `auth`
    message — nothing may reach the server before it (hard security rule)."""
    text = CONNECTION.read_text(encoding="utf-8")
    m = re.search(r"sock\.onopen\s*=\s*\(\)\s*=>\s*\{.*?\n  \};", text, re.S)
    if not m:
        fail("sock.onopen handler not found in client/connection.js")
    body = m.group(0)
    if "flushTypeQueue(" not in body:
        fail("sock.onopen no longer calls flushTypeQueue() — a queued "
             "typing message would never be replayed on reconnect")
    auth_at = body.find('type: "auth"')
    flush_at = body.find("flushTypeQueue(")
    if auth_at == -1:
        fail("the auth send was not found inside sock.onopen — cannot "
             "verify ordering")
    if flush_at < auth_at:
        fail("flushTypeQueue() runs BEFORE auth is sent — nothing may reach "
             "the server before auth (hard security rule)")


CHECKS = [
    ("all four typing kinds are recognised", check_typing_kinds_are_recognised),
    ("non-typing kinds are never queued", check_non_typing_kinds_are_not_queued),
    ("push appends in order", check_push_appends_in_order),
    ("the measured 120-char backspace burst (61 msgs) fits under the cap",
     check_the_burst_amplification_case_fits_under_the_cap),
    ("pushing past the cap drops the oldest and reports it",
     check_pushing_past_the_cap_drops_the_oldest_and_reports_it),
    ("a fresh queue flushes whole and in order",
     check_a_fresh_queue_flushes_whole_and_in_order),
    ("a stale queue is dropped WHOLE, never partially",
     check_a_stale_queue_is_dropped_whole_not_partially),
    ("staleness is judged against the oldest entry, not the newest",
     check_staleness_is_judged_against_the_oldest_entry_not_the_newest),
    ("flushing an empty queue is a harmless no-op",
     check_flushing_an_empty_queue_is_a_harmless_noop),
    ("client/type-queue.js stays pure, so the gate can run it whole",
     check_type_queue_js_stays_pure),
    ("state.js wires the queue into send() and flushTypeQueue()",
     check_state_js_wires_the_queue_into_send_and_a_flush_function),
    ("a give-up shows a toast, never silence",
     check_a_giveup_shows_a_toast_not_silence),
    ("connection.js flushes the queue on reconnect, strictly after auth",
     check_connection_js_flushes_the_queue_after_auth_on_reconnect),
]


def main() -> int:
    print("\n=== TYPE QUEUE GATE ===")
    if shutil.which("node") is None:
        print("TYPE QUEUE GATE FAILED — node is required (it runs the REAL "
              "client/type-queue.js rules) and is not on PATH. Never skip a "
              "gate silently.")
        return 1
    failed = 0
    for name, check in CHECKS:
        try:
            check()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}\n        {e}")
    if failed:
        print(f"\nTYPE QUEUE GATE FAILED — {failed} check(s) broken.")
        return 1
    print("\nTYPE QUEUE GATE PASSED — a typing message survives a short "
          "reconnect, and a give-up is TOLD to the phone, never silent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
