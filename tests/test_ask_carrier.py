"""Gate: a question that BLOCKS the agent reaches his phone (owner report
2026-08-17, his third on this one feature — "notifikacija i dalje ne stize za
ovakve stvari ... A to je jako vazno jer agent ne radi dok se ne odgovori").
lang-ok: owner quote, verbatim from his report

WHY THIS FILE EXISTS AT ALL, and why `tests/test_notify.py` could not have
caught the failure: that gate proves the DELIVERY — `/notify` refuses a
stranger, a frame reaches the phone, the page calls the Android bridge, the
hook names the agent. Every one of those checks was green through the whole
failure, and so was the pipe when driven by hand on his own machine. What was
broken was the TRIGGER, one layer above everything test_notify.py can see: the
`Notification` event does not fire in the VS Code extension host his real
sessions run in, while `Stop` does — so the feature was installed, delivered,
and silent. A gate that measures delivery cannot see a carrier that never
fires, which is exactly how three rounds closed this while it was broken.

So this file asks the one question the other cannot: is the notice carried by
an event that actually fires where he works? Two theories died on the way to
that answer and are pinned here so nobody re-runs them:

  * `"matcher": "*"` was NOT the culprit — a harness ran `"*"` and a bare
    matcher side by side and both fired in the same second with byte-identical
    payloads;
  * `PreToolUse` DOES match `AskUserQuestion` — a documentation agent claimed
    it cannot, and his own screenshot shows the machine-wide gate blocking
    exactly that event in a VS Code session.

The honest limit of this gate, named rather than discovered later: it cannot
prove that the VS Code extension host fires `PreToolUse`, because it runs no
host at all. That fact was MEASURED on his machine (his screenshot, plus a
scratch harness whose traces carry `tool_name: AskUserQuestion`), and what is
gated here is everything downstream of it — that we register the carrier, on
the right tool, with the right flag, that one question makes exactly one
notice, and that the notice says WHAT is being asked.

Run:  .venv\\Scripts\\python tests/test_ask_carrier.py
"""

import json
import shutil
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "setup"))

import agent_hook  # noqa: E402


ASK_PAYLOAD = {
    "session_id": "sess-a",
    "hook_event_name": "PreToolUse",
    "tool_name": "AskUserQuestion",
    "tool_use_id": "toolu_01",
    "permission_mode": "bypassPermissions",
    "tool_input": {"questions": [{
        "question": "Which mechanism should the New window act use?",
        "header": "Mechanism",
        "options": [{"label": "Duplicate As Workspace"},
                    {"label": "Drop the act"},
                    {"label": "Measure both first"}],
    }]},
}

# The `Notification` copy of the SAME question, as measured on his machine
# ~6 s later: no tool name, no question, only this sentence.
NOTIFY_PAYLOAD = {
    "session_id": "sess-a",
    "hook_event_name": "Notification",
    "message": "Claude needs your permission",
    "notification_type": "permission_prompt",
}


def main() -> int:
    results: dict[str, bool] = {}
    tmp = Path(__file__).resolve().parent / "_ask_carrier_tmp"
    tmp.mkdir(exist_ok=True)
    agent_hook.ASK_STAMP = tmp / "asking.json"
    if agent_hook.ASK_STAMP.exists():
        agent_hook.ASK_STAMP.unlink()

    # --- 1: the carrier is registered at all ------------------------------
    # The whole failure in one check: `Notification` alone is a carrier that
    # does not fire where he works.
    results["PreToolUse is one of the hook events"] = (
        "PreToolUse" in agent_hook.HOOK_EVENTS)

    # --- 2: it is matched on the ASKING tool, not on everything -----------
    # `"*"` here would post a notice for every Read and Bash in the session —
    # the feature would be worse than its absence.
    entry = agent_hook.hook_entry(Path("x.py"), "py.exe", "PreToolUse")
    results["the PreToolUse hook matches AskUserQuestion only"] = (
        entry.get("matcher") == "AskUserQuestion")

    # --- 3: it speaks the ASKING sentence ---------------------------------
    cmd = entry["hooks"][0]["command"]
    results["the PreToolUse hook carries --asking"] = "--asking" in cmd

    # --- 4: the turn-ended carrier is untouched ---------------------------
    stop = agent_hook.hook_entry(Path("x.py"), "py.exe", "Stop")
    results["the Stop hook stays a plain '*' with no --asking"] = (
        stop.get("matcher") == "*" and "--asking" not in stop["hooks"][0]["command"])

    # --- 5: installing writes it, and leaves a stranger's hook alone ------
    # His settings.json carries other people's PreToolUse hooks (the
    # machine-wide `rules/hooks/gate.py` is one). Ours must join them,
    # never replace them.
    settings = tmp / "settings.json"
    settings.write_text(json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "AskUserQuestion", "hooks": [
            {"type": "command", "command": "python gate.py pre"}]}]}}),
        encoding="utf-8")
    real_settings = agent_hook.SETTINGS
    agent_hook.SETTINGS = settings
    try:
        agent_hook.install(script=tmp / "agent_hook.py", python="py.exe",
                           ledger_script=Path("l.py"))
        written = json.loads(settings.read_text(encoding="utf-8"))
    finally:
        agent_hook.SETTINGS = real_settings
    pre = written.get("hooks", {}).get("PreToolUse") or []
    ours = [h for h in pre if agent_hook.MARKER in json.dumps(h)]
    theirs = [h for h in pre if "gate.py" in json.dumps(h)]
    results["install registers our PreToolUse hook"] = len(ours) == 1
    results["install leaves a stranger's PreToolUse hook standing"] = len(theirs) == 1

    # --- 6: the heal LOOKS for it -----------------------------------------
    # The 2026-08-15 defect repeated one event along: a machine registered
    # before this round is "installed" and would never receive the new
    # carrier unless something goes looking for it.
    old = tmp / "old_settings.json"
    old.write_text(json.dumps({"hooks": {
        "Stop": [{"matcher": "*", "hooks": [
            {"type": "command", "command": 'py "agent_hook.py"'}]}],
        "Notification": [{"matcher": "*", "hooks": [
            {"type": "command", "command": 'py "agent_hook.py" --asking'}]}],
    }}), encoding="utf-8")
    agent_hook.SETTINGS = old
    try:
        missing = agent_hook.missing_events()
    finally:
        agent_hook.SETTINGS = real_settings
    results["the heal reports PreToolUse missing on an older machine"] = (
        missing == ("PreToolUse",))

    # --- 7: the notice says WHAT is being asked ---------------------------
    # The reason this carrier is better and not merely available: he can read
    # the question and its choices off the notification itself.
    text = agent_hook.asking_text(ASK_PAYLOAD)
    results["the notice carries the question"] = (
        "Which mechanism" in text)
    results["the notice carries the options"] = (
        "Duplicate As Workspace" in text and "Measure both first" in text)

    # --- 8: the weaker carrier still says something -----------------------
    # A `Notification` payload has no question in it at all; it must fall
    # back rather than send an empty line.
    results["a Notification payload falls back to its message"] = (
        agent_hook.asking_text(NOTIFY_PAYLOAD) == "Claude needs your permission")

    # --- 9: one question is ONE notice ------------------------------------
    # In a terminal session BOTH carriers fire for a single question, ~6 s
    # apart. The first through claims it.
    first = agent_hook.claim_question(ASK_PAYLOAD)
    second = agent_hook.claim_question(NOTIFY_PAYLOAD)
    results["the first carrier claims the question"] = first is True
    results["the second carrier is suppressed"] = second is False

    # --- 10: two agents asking at once never silence each other -----------
    # The claim is keyed on the SESSION; keying it on time alone would make
    # one agent's question swallow another's.
    results["another session's question is its own"] = (
        agent_hook.claim_question({**ASK_PAYLOAD, "session_id": "sess-b"}) is True)

    # --- 11: the same session may ask again later -------------------------
    # Read defensively: a claim that never writes its stamp is itself the
    # defect (a fail-CLOSED `claim_question` silences him), and that must
    # arrive as a NAMED failing check rather than as a traceback — planting
    # `return False` in the stamp-read branch blocked the build with a bare
    # FileNotFoundError, which is fail-closed but tells the next reader
    # nothing about which promise broke.
    results["the claim wrote its stamp at all"] = agent_hook.ASK_STAMP.exists()
    try:
        stamps = json.loads(agent_hook.ASK_STAMP.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        stamps = {}
    stamps["sess-a"] = time.time() - agent_hook.ASK_DEDUP_S - 1
    agent_hook.ASK_STAMP.write_text(json.dumps(stamps), encoding="utf-8")
    results["a later question in the same session is not suppressed"] = (
        agent_hook.claim_question(ASK_PAYLOAD) is True)

    # --- 12: an unreadable stamp file must never cost him a notice --------
    # Fail OPEN, deliberately: a duplicate is an annoyance, silence is the
    # bug this entire round exists to end.
    agent_hook.ASK_STAMP.write_text("{ not json", encoding="utf-8")
    results["a corrupt stamp file still lets the notice through"] = (
        agent_hook.claim_question({**ASK_PAYLOAD, "session_id": "sess-c"}) is True)

    # --- 13: the hook may never block the question it reports on ----------
    # A PreToolUse hook that fails, or that writes a deny to stdout, would
    # stop the very question it exists to announce — turning a missing
    # notification into a broken agent.
    import io
    sent: list[tuple] = []
    real_send = agent_hook.send
    agent_hook.send = lambda *a, **k: sent.append(a) or True
    real_stdin, real_argv = sys.stdin, sys.argv
    sys.stdin = io.StringIO(json.dumps({**ASK_PAYLOAD, "session_id": "sess-d"}))
    sys.argv = ["agent_hook.py", "--asking"]
    try:
        code = agent_hook.main()
    finally:
        agent_hook.send, sys.stdin, sys.argv = real_send, real_stdin, real_argv
    results["the hook exits 0 so the question is never blocked"] = code == 0
    results["the hook really sent the asking notice"] = (
        len(sent) == 1 and sent[0][1] == "asking")

    # --- 14: the SUPPRESSED path must exit 0 too --------------------------
    # Found by planting: check 13 drives a fresh session, which always sends,
    # so nothing was measuring the early return the de-duplication takes. A
    # non-zero exit there is not a missing notification — it is a PreToolUse
    # hook failing on `AskUserQuestion`, which blocks the question itself and
    # leaves the agent stopped with nothing on screen. The worse failure of
    # the two had no check at all.
    sent.clear()
    agent_hook.send = lambda *a, **k: sent.append(a) or True
    sys.stdin = io.StringIO(json.dumps({**ASK_PAYLOAD, "session_id": "sess-d"}))
    sys.argv = ["agent_hook.py", "--asking"]
    try:
        code = agent_hook.main()
    finally:
        agent_hook.send, sys.stdin, sys.argv = real_send, real_stdin, real_argv
    results["a suppressed duplicate still exits 0"] = code == 0
    results["a suppressed duplicate sends nothing"] = sent == []

    # THE GATE CLEANS UP AFTER ITSELF (owner instruction 2026-08-18). Every
    # run used to leave `tests/_ask_carrier_tmp/` standing in the working tree
    # — four scratch files that git reported as untracked forever, and that he
    # had to ask about. The whole folder is this function's own, made three
    # lines above, so removing it takes nothing that was not made here.
    #
    # AFTER the results are collected and BEFORE they are printed, so a failing
    # check still leaves a clean tree: the evidence of what failed is the
    # printed line, never a directory left behind.
    shutil.rmtree(tmp, ignore_errors=True)

    print("\n=== ASK CARRIER GATE ===")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok in results.items() if not ok]
    if failed:
        print(f"\nASK CARRIER GATE FAILED — {len(failed)} check(s).", file=sys.stderr)
        return 1
    print("\nASK CARRIER GATE PASSED — a blocking question reaches his phone.")
    return 0


def test_gate():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
