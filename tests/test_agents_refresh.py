"""AGENTS REFRESH GATE — a process-table change reaches the phone without a
human action having to cause it, and an unchanged one sends nothing.

Owner report 2026-08-15: he built a new layout on a VS Code window that was
still loading its previous Claude conversation. `agents_in()` answered empty
at that instant, and the Claude set stayed off the wheel until he switched to
Desktop and back — nothing in the codebase ever re-asked on its own.
`layout_state.state()` already computes `agents` live on every send; the gap
was that nothing re-SENT it when the process table changed between the human
actions (focus, switch, aspect, member add/remove) that already trigger one.

`server/agents_refresh.py`'s `watch()` is the missing trigger: one task per
connection, same family as `caret.watch`/`clipboard_sync.watch`, polling a
comparable SIGNATURE of "which agents does each live layout hold" and
re-sending through the existing `layout_api.send_layout_state` choke point
only when that signature actually moved.

Every check was proven by planting its own defect — see each docstring.

Run:  .venv\\Scripts\\python tests/test_agents_refresh.py
"""

import asyncio
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import agents_refresh  # noqa: E402

MODULE = PROJECT / "server" / "agents_refresh.py"


class FakeLayout:
    """Only `project()` is asked by `_signature` — nothing else about a real
    `Layout` (Win32 titles, members, sources) is needed to drive this poll."""

    def __init__(self, project: str):
        self._project = project

    def project(self) -> str:
        return self._project


class FakeLayouts:
    def __init__(self, layouts):
        self.layouts = layouts


def _counting_sender():
    """A fake `layout_api.send_layout_state` that only counts."""
    calls: list[int] = []

    async def fake_send(ws, layouts, conn):
        calls.append(1)

    return calls, fake_send


async def _drive(live_agents_fn, layouts, polls: int = 4, poll_s: float = 0.02):
    """Runs `agents_refresh.watch` for `polls` cycles against a fake
    `agents.live_agents` and a counting fake `send_layout_state`, then
    cancels it and returns the call count."""
    calls, fake_send = _counting_sender()
    orig_poll = agents_refresh.POLL_S
    orig_live = agents_refresh.agents.live_agents
    orig_send = agents_refresh.layout_api.send_layout_state
    agents_refresh.POLL_S = poll_s
    agents_refresh.agents.live_agents = live_agents_fn
    agents_refresh.layout_api.send_layout_state = fake_send
    try:
        task = asyncio.create_task(
            agents_refresh.watch(object(), layouts, {"away": None, "left": False}))
        await asyncio.sleep(poll_s * (polls + 1.5))
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        agents_refresh.POLL_S = orig_poll
        agents_refresh.agents.live_agents = orig_live
        agents_refresh.layout_api.send_layout_state = orig_send
    return calls


def check_a_process_table_change_sends_exactly_one_layout_state() -> bool:
    """His report exactly: the process table CHANGES (a transcript starts
    being written) while nothing else happens on the phone, and the wheel
    must catch up without a human action.

    PLANTED DEFECT: in `watch()`, change `if sig == last: continue` to
    `continue` unconditionally (never send) — the original bug this module
    exists to fix: nothing ever re-sends on a process-table change alone."""
    state = {"n": 0}

    def live_agents():
        state["n"] += 1
        # The FIRST call happens before the loop even starts (the initial
        # signature) and answers empty — exactly his report: no transcript
        # yet. Every call from the loop onward answers as if the transcript
        # had started, so the signature changes exactly ONCE.
        if state["n"] <= 1:
            return {}
        return {"claude": {"demo"}}

    layouts = FakeLayouts([FakeLayout("demo")])
    calls = asyncio.run(_drive(live_agents, layouts))
    if len(calls) != 1:
        print(f"    got {len(calls)} layout_state sends, wanted exactly 1")
        return False
    return True


def check_an_unchanged_process_table_sends_nothing() -> bool:
    """Constraint 27's own lesson, applied here too: a `layout_state` that
    changes nothing must never be sent for its own sake — the poll exists to
    catch a real change, not to become a second heartbeat.

    PLANTED DEFECT: delete the `if sig == last: continue` guard in `watch()`
    entirely (always send) — every poll then re-sends layout_state whether
    anything changed or not, spamming a fresh encoder-adjacent frame every
    5 s for the lifetime of every connection with a layout open."""
    def live_agents():
        return {"claude": {"demo"}}   # never changes across polls

    layouts = FakeLayouts([FakeLayout("demo")])
    calls = asyncio.run(_drive(live_agents, layouts))
    if calls:
        print(f"    got {len(calls)} layout_state sends for an unchanged "
              "process table, wanted 0")
        return False
    return True


def check_no_layouts_does_no_repeated_work() -> bool:
    """"While at least one layout exists" (the owner's own scoping): with no
    layout open there is nothing for a Claude wheel to appear ON, so the LOOP
    must not keep computing a signature every poll — only the one, cheap,
    unconditional read every `watch()` in this family does at start (the
    initial signature, matching `caret.watch`'s own opening read) is allowed.

    PLANTED DEFECT: remove the `if not layouts.layouts: continue` guard — the
    poll would then call `_signature` (and possibly send) every 5 s cycle
    even at the desktop, for every connection, forever."""
    reads = {"n": 0}

    def live_agents():
        reads["n"] += 1
        return {}

    layouts = FakeLayouts([])
    calls = asyncio.run(_drive(live_agents, layouts, polls=4))
    if reads["n"] > 1:
        print(f"    live_agents() was read {reads['n']} times with no "
              "layouts open across 4 poll cycles — wanted 1 (the initial "
              "read only), the loop is not skipping empty layouts")
        return False
    return not calls


def check_the_watcher_is_really_started_per_connection() -> bool:
    """SOMETHING CALLS IT — the actions.json lesson of 2026-08-07, repeated
    for every pure-module-with-no-caller class of bug in this project: a
    module nobody starts is a feature that does not exist.

    PLANTED DEFECT: remove the `agents_refresh.watch(ws, layouts, conn)` task
    creation from web.py's per-connection setup (or the `import agents_refresh`
    line) — this check reads the source rather than driving the real FastAPI
    app, because that app needs a live capture/injector stack this gate does
    not want to depend on."""
    web = (PROJECT / "server" / "web.py").read_text(encoding="utf-8")
    if "import agents_refresh" not in web:
        print("    web.py no longer imports agents_refresh")
        return False
    if "agents_refresh.watch(" not in web:
        print("    web.py no longer starts agents_refresh.watch() per connection")
        return False
    return True


CHECKS = [
    ("a process-table change sends exactly one layout_state",
     check_a_process_table_change_sends_exactly_one_layout_state),
    ("an unchanged process table sends nothing",
     check_an_unchanged_process_table_sends_nothing),
    ("no layouts open does no repeated work",
     check_no_layouts_does_no_repeated_work),
    ("the watcher is really started per connection",
     check_the_watcher_is_really_started_per_connection),
]


def main() -> int:
    print("=== AGENTS REFRESH GATE ===")
    failed = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as e:                 # a crashing check is a failing one
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"AGENTS REFRESH GATE FAILED — {failed} check(s).")
        return 1
    print("AGENTS REFRESH GATE PASSED — the Claude wheel catches up on its own.")
    return 0


def test_agents_refresh():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
