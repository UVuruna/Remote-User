"""Gate: the PC calls the phone (ROADMAP Phase H, owner 2026-08-05).

The owner's requirement is not "make a sound" — it is *which agent finished*,
delivered while he is not looking at the phone. So the things that must hold
are:

  1. `/notify` refuses an unauthenticated caller (it would otherwise be a way
     to make any phone on the network buzz);
  2. a notice reaches the connected phone as a `notify` frame carrying the
     AGENT's name, composed into a line worth reading;
  3. with no phone connected the answer says so — nothing is queued, because
     an alarm that arrives an hour late is worse than none;
  4. the page turns that frame into the Android bridge calls (notification +
     speech), tagged per agent so four agents keep four lines;
  5. the hook names the agent the way the owner expects, from a real Claude
     Code `Stop` payload.

Run:  .venv\\Scripts\\python tests/test_notify.py
"""

import asyncio
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_input_pipeline as gate  # noqa: E402 — reuses its fake server


def post(port: int, payload: dict, token: str) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/notify?token={token}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def main() -> int:
    import notify

    results: dict[str, bool] = {}

    # --- 1 + 5: the pure pieces, no server needed --------------------------
    title, body = notify.compose("Remote User · 3f9c1a", "finished", "12 files")
    results["the line names the agent first"] = (
        title == "Remote User · 3f9c1a finished" and body == "12 files")
    results["an unknown event still speaks"] = (
        notify.compose("A", "compacted", "")[0] == "A compacted")
    results["fields are clamped, never trusted"] = (
        len(notify.clean("x" * 500, notify.MAX_TEXT)) == notify.MAX_TEXT
        and notify.clean(None, 10, "Agent") == "Agent")

    sys.path.insert(0, str(PROJECT / "setup"))
    import agent_hook
    results["hook: explicit name wins"] = agent_hook.agent_name(
        {"cwd": r"C:\x", "session_id": "abc123"}) is not None
    import os
    os.environ["CLAUDE_AGENT_NAME"] = "controls round"
    results["hook: $CLAUDE_AGENT_NAME wins"] = (
        agent_hook.agent_name({"cwd": r"C:\x", "session_id": "abc123"}) == "controls round")
    del os.environ["CLAUDE_AGENT_NAME"]
    # The fallback is what he will actually see most of the time: the project
    # folder plus enough of the session id to tell two agents in one repo apart.
    results["hook: falls back to project · session"] = agent_hook.agent_name(
        {"cwd": r"U:\Coding\UVuruna\Applications\Remote User",
         "session_id": "3f9c1a77-dead-beef"}) == "Remote User · 3f9c1a"

    # --- 2 + 3 + 4: the live path ------------------------------------------
    threading.Thread(target=gate.run_server, daemon=True).start()
    gate.server_ready.wait(15)
    deadline = time.time() + 10
    import socket
    while time.time() < deadline:
        if gate.server_error:
            raise gate.server_error[0]
        try:
            with socket.create_connection(("127.0.0.1", gate.PORT), timeout=0.25):
                break
        except OSError:
            time.sleep(0.1)

    status, _ = post(gate.PORT, {"agent": "X"}, "wrong-token")
    results["/notify refuses a bad token"] = status == 403

    status, answer = post(gate.PORT, {"agent": "X"}, gate.TOKEN)
    results["no phone connected -> says so, queues nothing"] = (
        status == 200 and answer.get("ok") is False)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 412, "height": 915}, has_touch=True, is_mobile=True,
            user_agent=("Mozilla/5.0 (Linux; Android 15; Pixel 8) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36 RemoteUserApp"),
        )
        page = ctx.new_page()
        page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
        page.wait_for_selector("#group-left button", timeout=8000)
        page.wait_for_function(
            "document.getElementById('status').textContent.includes('Connected')",
            timeout=8000)
        # Stand in for the shell's bridge and record what the page asks of it.
        page.evaluate("""() => {
          window.__calls = [];
          window.Android = Object.assign(window.Android || {}, {
            notify: (t, x, tag) => window.__calls.push(['notify', t, x, tag]),
            speak: (t) => window.__calls.push(['speak', t]),
            prefGet: () => null, prefSet: () => {},
          });
        }""")

        post(gate.PORT, {"agent": "Remote User · 3f9c1a", "event": "finished",
                         "text": "controls round"}, gate.TOKEN)
        post(gate.PORT, {"agent": "ML · 77bb02", "event": "waiting", "text": ""},
             gate.TOKEN)
        page.wait_for_function("window.__calls.length >= 3", timeout=5000)
        calls = page.evaluate("window.__calls")
        notifs = [c for c in calls if c[0] == "notify"]
        speaks = [c for c in calls if c[0] == "speak"]
        results["the phone raises a banner per agent"] = (
            len(notifs) == 2
            and notifs[0][1] == "Remote User · 3f9c1a finished"
            and notifs[0][3] == "Remote User · 3f9c1a"      # tag = the agent
            and notifs[1][1] == "ML · 77bb02 needs you"
            and notifs[1][3] != notifs[0][3])               # ...so they never merge
        results["the phone speaks the agent's name"] = (
            len(speaks) == 2 and "Remote User" in speaks[0][1])
        # The command CHOOSER (owner idea 2026-08-05): picking a level must
        # send the FINISHED command, not the bare one. This is the same page
        # and socket, so it rides along here rather than paying for a second
        # browser launch.
        # NB: the snippet must not EVALUATE to the wrapper function —
        # Playwright would try to serialise it and call it with null.
        page.evaluate("""() => {
          window.__sent = [];
          const real = window.send;
          window.send = (m) => { window.__sent.push(m); return real(m); };
        }""")
        page.evaluate("openChoicePanel({label:'Thinking', text:'/effort',"
                      " options:['low','medium','high','xhigh','max','auto']})")
        page.wait_for_selector("#choice-panel .sets-row.choice", timeout=4000)
        page.locator("#choice-panel .sets-row.choice", has_text="xhigh").first.tap()
        page.wait_for_function("window.__sent.some(m => m.type === 'paste_text')",
                               timeout=4000)
        sent = [m for m in page.evaluate("window.__sent") if m["type"] == "paste_text"]
        results["a picked option sends the finished command"] = (
            len(sent) == 1 and sent[0]["text"] == "/effort xhigh"
            and sent[0]["enter"] is True)
        results["the chooser closes on the pick"] = page.evaluate(
            "document.getElementById('choice-panel').hidden") is True

        errors = page.evaluate("window.__pageErrors || []")
        results["no page errors"] = not errors
        browser.close()

    print("\n=== NOTIFY GATE ===")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok in results.items() if not ok]
    if failed:
        print(f"\nNOTIFY GATE FAILED — {len(failed)} check(s).", file=sys.stderr)
        return 1
    print("\nNOTIFY GATE PASSED — the PC names the agent, the phone says it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
