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

    # --- A QUESTION IS NOT AN ENDING (owner 2026-08-09, task 137) ---------
    # Claude Code raises a `Notification` hook when it stops to ASK — a
    # permission, a choice, one of the votes he sees on screen. It is a
    # different event from a turn ending and it gets a different sentence,
    # because a turn that ended can wait and a question has stopped
    # everything until he answers.
    results["a question says it is a question"] = (
        notify.compose("Remote User", "asking", "Allow Bash?")[0]
        == "Remote User is asking you")
    results["…and it is not the same word as a turn ending"] = (
        notify.compose("A", "asking", "")[0] != notify.compose("A", "waiting", "")[0])
    # BOTH hooks are installed, and each carries the flag that tells this one
    # script which event it is answering — the payload does not say.
    lines = {e: agent_hook.hook_entry(None, "py.exe", e)["hooks"][0]["command"]
             for e in agent_hook.HOOK_EVENTS}
    results["the hook installs for Stop AND Notification"] = (
        set(lines) == {"Stop", "Notification"})
    results["only the Notification line carries --asking"] = (
        "--asking" in lines["Notification"] and "--asking" not in lines["Stop"])

    # --- WHERE it happened (owner 2026-08-08, task 110) --------------------
    # "da klikom na notifikaciju nas odvede do tog layouta." The PC answers
    # that at SEND time by matching the agent's OWN cwd — reported by the hook,
    # never guessed — against what each layout's windows really belong to.
    class _Lay:
        def __init__(self, name, project):
            self.name, self._p = name, project

        def project(self):
            return self._p

    class _Reg:
        def __init__(self, *lays):
            self.layouts = list(lays)
            self.pruned = 0

        def prune(self):
            self.pruned += 1
            return list(range(len(self.layouts)))

    reg = _Reg(_Lay("Chrome", "notes"), _Lay("Claude", "remote user"))
    notify._layouts = reg
    # The hook sends a PATH; the registry speaks folder names, lowercased.
    results["the notice finds the layout by the agent's own cwd"] = (
        notify.layout_of(r"U:\Coding\UVuruna\Applications\Remote User")
        == {"index": 1, "name": "Claude"})
    results["a bare folder name works too"] = (
        notify.layout_of("Notes") == {"index": 0, "name": "Chrome"})
    # It PRUNES first, because the index it returns is the one the phone is
    # holding, and layout_state numbers its list after the same prune. Without
    # this the tap would land one layout off whenever a dead one was still in
    # the list.
    results["the index is taken after a prune, like the phone's own"] = reg.pruned >= 2
    # A project nobody is showing offers NO jump. A tap that cannot land is
    # worse than a tap that only opens the app.
    results["a project on no layout offers no jump"] = (
        notify.layout_of(r"C:\somewhere\else") is None
        and notify.layout_of("") is None and notify.layout_of(None) is None)
    notify._layouts = None
    results["with no registry at all the feature is absent, not wrong"] = (
        notify.layout_of("Remote User") is None)
    notify._layouts = reg

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

    # A notice with nobody to hand it to is HELD, not thrown away (owner
    # 2026-08-06: two agents finished while he was on a call with the app
    # closed, and both were silently discarded). The answer still says the
    # phone was not there, so the caller is never misled.
    status, answer = post(gate.PORT, {"agent": "Held", "text": "while away"},
                          gate.TOKEN)
    results["no phone connected -> says so, and HOLDS the notice"] = (
        status == 200 and answer.get("ok") is False
        and "held" in str(answer.get("reason", "")).lower())

    # …and a notice older than the queue's own patience is dropped instead of
    # arriving as stale news.
    import notify as notify_mod
    notify_mod.queue({"type": "notify", "agent": "Ancient", "title": "Ancient",
                      "text": "", "at": time.time() - notify_mod.QUEUE_TTL_S - 60})
    results["a notice too old to matter is dropped, not delivered"] = (
        [n["agent"] for n in notify_mod.drain(time.time())] == ["Held"])

    # …and what is held really is handed over on the phone's next connection,
    # oldest first. A fake socket, because the real one belongs to the page
    # below and a leftover notice would arrive there and be counted twice.
    class _FakeWS:
        def __init__(self):
            self.sent = []

        async def send_text(self, payload):
            self.sent.append(json.loads(payload))

    for i in range(3):
        notify_mod.queue({"type": "notify", "agent": f"A{i}", "title": f"A{i}",
                          "text": "", "at": time.time()})
    fake = _FakeWS()
    delivered = asyncio.run(notify_mod.send_pending(fake))
    results["what was held arrives on the phone's return, oldest first"] = (
        delivered == 3
        and [n["agent"] for n in fake.sent] == ["A0", "A1", "A2"]
        and notify_mod.drain(time.time()) == [])   # …and the queue is empty after

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
            notifyAt: (t, x, tag, j) => window.__calls.push(['notifyAt', t, x, tag, j]),
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
        notifs = [c for c in calls if c[0] in ("notify", "notifyAt")]
        speaks = [c for c in calls if c[0] == "speak"]
        # NO layout was matched for either notice above (the fake server owns
        # no registry), so the page must take the OLD bridge method. This is
        # the compatibility half of task 110: `notifyAt` exists for the case
        # where there IS somewhere to go, and a shell that predates it must
        # keep working.
        results["with nowhere to go the page uses the plain bridge call"] = (
            all(c[0] == "notify" for c in notifs))
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

        # --- the TAP, on the page (task 110) ------------------------------
        # A notice that names a layout must reach the newer bridge method
        # WITH the layout on it — that string is the whole journey through
        # the Android intent and back.
        page.evaluate("""() => {
          window.__calls = [];
          handleNotify({agent: 'Claude', title: 'Claude needs you', text: '',
                        speak: false, layout: {index: 1, name: 'Claude'}});
        }""")
        at = [c for c in page.evaluate("window.__calls") if c[0] == "notifyAt"]
        results["a notice that knows WHERE carries it to the shell"] = (
            len(at) == 1 and json.loads(at[0][4]) == {"index": 1, "name": "Claude"})

        # And the tap is VERIFIED against the list that exists NOW. A layout
        # removed between the notice and the thumb slides every higher index
        # down; following the index blindly would drop him into a stranger's
        # window, which is worse than not moving at all.
        results["the tap follows the NAME, not the stale index"] = page.evaluate("""() => {
          layouts = [{name: 'Notes'}, {name: 'Chrome'}, {name: 'Claude'}];
          return noticeTarget({index: 1, name: 'Claude'}) === 2
              && noticeTarget({index: 2, name: 'Claude'}) === 2
              && noticeTarget({index: 0, name: 'Gone'}) === -1
              && noticeTarget({index: 9, name: 'Notes'}) === 0;
        }""")
        results["two layouts of one name are ambiguous, so nothing moves"] = page.evaluate(
            """() => {
          layouts = [{name: 'Claude'}, {name: 'Claude'}];
          return noticeTarget({index: 5, name: 'Claude'}) === -1;
        }""")
        results["no layouts at all cannot be jumped into"] = page.evaluate("""() => {
          layouts = [];
          return noticeTarget({index: 0, name: 'Claude'}) === -1;
        }""")

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
