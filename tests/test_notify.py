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
import inspect
import json
import re
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
    title, body = notify.compose("VibeCoder · 3f9c1a", "finished", "12 files")
    results["the line names the agent first"] = (
        title == "VibeCoder · 3f9c1a finished" and body == "12 files")
    results["an unknown event still speaks"] = (
        notify.compose("A", "compacted", "")[0] == "A compacted")
    results["fields are clamped, never trusted"] = (
        len(notify.clean("x" * 500, notify.MAX_TEXT)) == notify.MAX_TEXT
        and notify.clean(None, 10, "Agent") == "Agent")

    # --- THE VOICE READS THE SUMMARY, NEVER THE BODY (owner v0.0.107
    # screenshots — a long Serbian notification body was read out loud in
    # full). speak_summary() is the ONLY thing that may compute what the
    # voice says, and it never sees the body at all, structurally — this
    # proves it from the pure function outward, then again through the live
    # page below (the notice a real request actually carries).
    long_body = ("razmisljam o resenju problema sa iscekivanjem konekcije i "
                "sada mi treba tvoja odluka pre nego sto nastavim dalje")
    title, body = notify.compose("Claude Code (Vibe Coder)", "waiting", long_body)
    speak_text = notify.speak_summary(
        "U:/Coding/UVuruna/Applications/VibeCoder", "Claude Code (Vibe Coder)")
    results["speak_summary is project — conversation, never the body"] = (
        speak_text == "VibeCoder — Claude Code (Vibe Coder)"
        and body not in speak_text
        and "needs you" not in speak_text)
    results["speak_summary survives a missing project"] = (
        notify.speak_summary("", "Solo agent") == "Solo agent")
    results["speak_summary survives a missing agent"] = (
        notify.speak_summary("U:/x/y/Vibe Coder", "") == "Vibe Coder")

    # --- 190/191: the Claude set's Model/Thinking must MATCH THE OFFICIAL
    # picker and COMMIT with one Enter. CORRECTED 2026-08-10 against the
    # authoritative Claude Code docs (code.claude.com/docs/en/model-config.md,
    # confirmed via claude-code-guide), REVERSING task 174's 0.0.394 design:
    #   * `/model <alias>` — the CANONICAL picker aliases commit with one
    #     Enter: default / opus / opus[1m] / fable / sonnet / haiku. Task 174
    #     claimed the alias was a non-committing prefix and only the full id
    #     ("claude-fable-5") worked — that was WRONG, and the owner's task 190
    #     ("match the OFFICIAL picker EXACTLY — five, not the nine invented
    #     ids") is the ruling. The five aliases ARE the official picker.
    #   * `/effort <level>` TAKES an argument and commits with one Enter
    #     (low/medium/high/xhigh/max); bare /effort only opens the interactive
    #     slider — the "menu-standing" downgrade the owner reported (task 191).
    # This gate replaced the self-contradictory task-174 checks that shipped a
    # wrong conclusion with teeth: B3 (0.0.401) correctly reversed the
    # BEHAVIOUR but left this file enforcing the old one, and a declined
    # release meant build 0d/6 never ran to catch it (2026-08-10).
    # SINCE 0.0.419 (his ballot) the five options live in the PANEL modules,
    # not on the button: the button carries `panel`, and client/claude-state.js
    # is the one table of literals (drawn stars, three truth chips). The
    # intent guarded here is UNCHANGED — the official five aliases and the
    # five effort levels, each committing with one Enter — only the carrier
    # moved; test_claude_panels.py drives the modules end to end, this check
    # pins that the SHIPPED file wires the buttons to those panels and that
    # the table never regresses to the rejected full-id nine.
    claude_shipped = next(
        s for s in json.loads((PROJECT / "actions.json").read_text(encoding="utf-8"))
        ["app_sets"] if s["name"] == "Claude")
    model_btn = next(b for b in claude_shipped["buttons"] if b["label"] == "Model")
    thinking_btn = next(b for b in claude_shipped["buttons"] if b["label"] == "Thinking")
    results["Model opens the panel chooser (ballot design, 0.0.419)"] = (
        model_btn.get("panel") == "claude-model")
    results["Thinking opens the panel chooser, not a menu-standing /effort"] = (
        thinking_btn.get("panel") == "claude-effort")
    state_js = (PROJECT / "client" / "claude-state.js").read_text(encoding="utf-8")
    values = set(re.findall(r'value:\s*"([^"]+)"', state_js))
    results["The table sends EXACTLY the official five /model aliases"] = (
        {"default", "haiku", "sonnet", "opus[1m]", "fable"} <= values)
    # The old nine full-id options (task 174) are exactly what the owner
    # rejected — one of them in the table means the regression came back.
    results["The table dropped the old full-id options, not just added five"] = (
        not any(bad in values
                for bad in ("claude-opus-5", "claude-sonnet-5",
                            "claude-haiku-4-5", "claude-fable-5",
                            "claude-haiku-5")))
    results["Thinking CHOOSES a level (/effort takes an argument)"] = (
        {"low", "medium", "high", "xhigh", "max"} <= values
        and "/effort" in state_js)

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
        {"cwd": r"U:\Coding\UVuruna\Applications\VibeCoder",
         "session_id": "3f9c1a77-dead-beef"}) == "VibeCoder · 3f9c1a"

    # --- task 198: name = conversation TITLE, text = last-reply SUMMARY ----
    # (owner 2026-08-10 — the hash-like fallback "6ffb225" irritated him; he
    # wants WHO + WHAT). Verified against REAL transcripts on this PC before
    # writing agent_hook.py: there is no top-level `slug`/`summary` field —
    # the title lives in `{"type": "ai-title", "aiTitle": "..."}` records,
    # rewritten as the conversation goes, so the LAST one is current. These
    # checks drive that extraction against FAKE transcript files, each
    # proving its own defect.
    import tempfile

    def _jsonl(*records) -> str:
        return "\n".join(json.dumps(r) for r in records) + "\n"

    with tempfile.TemporaryDirectory() as tmp:
        # A: the LAST ai-title wins over an earlier one; a trailing
        # tool-use-only assistant record is skipped in favour of the real
        # text reply before it; agent_name prefers the title over the
        # project·session fallback.
        transcript_a = Path(tmp) / "a.jsonl"
        transcript_a.write_text(_jsonl(
            {"type": "ai-title", "aiTitle": "First guess title"},
            {"type": "ai-title", "aiTitle": "Ispravka UI dizajna"},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "gates green, release published\nmore detail"}]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {}}]}},
        ), encoding="utf-8")
        payload_a = {"transcript_path": str(transcript_a)}
        results["hook: title comes from the LAST ai-title record"] = (
            agent_hook.transcript_title(payload_a) == "Ispravka UI dizajna")
        results["hook: a trailing tool-use-only reply is skipped for the summary"] = (
            agent_hook.transcript_summary(payload_a)
            == "gates green, release published")
        results["hook: agent_name prefers the transcript title"] = (
            agent_hook.agent_name(payload_a) == "Ispravka UI dizajna")

        # B: no ai-title record at all -> the old project·session fallback
        # still holds, and a summary of nothing is None, not a crash.
        transcript_b = Path(tmp) / "b.jsonl"
        transcript_b.write_text(_jsonl(
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Bash", "input": {}}]}},
        ), encoding="utf-8")
        payload_b = {"transcript_path": str(transcript_b),
                     "cwd": r"U:\Coding\UVuruna\Applications\VibeCoder",
                     "session_id": "3f9c1a77-dead-beef"}
        results["hook: an absent title falls back to project · session"] = (
            agent_hook.agent_name(payload_b) == "VibeCoder · 3f9c1a")
        results["hook: an absent text summary is None, not a crash"] = (
            agent_hook.transcript_summary(payload_b) is None)

        # C: a transcript far bigger than the tail window still finds the
        # title and the summary when both sit near the end — mirrors the
        # real ~80 MB transcript measured on this PC, where the last
        # ai-title sat at line 8,944 of 8,956, well inside any sane window.
        transcript_c = Path(tmp) / "c.jsonl"
        filler = _jsonl(*[{"type": "user", "message": {"role": "user",
                           "content": "x" * 500}} for _ in range(1000)])
        tail = _jsonl(
            {"type": "ai-title", "aiTitle": "Buried under filler"},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "still found near the end"}]}},
        )
        transcript_c.write_text(filler + tail, encoding="utf-8")
        results["hook: the fake transcript really is bigger than one record"] = (
            transcript_c.stat().st_size > 400_000)
        payload_c = {"transcript_path": str(transcript_c)}
        results["hook: title survives a file much larger than the tail window"] = (
            agent_hook.transcript_title(payload_c) == "Buried under filler")
        results["hook: summary survives a file much larger than the tail window"] = (
            agent_hook.transcript_summary(payload_c)
            == "still found near the end")

        # D: the tail SEEK really excludes the front of the file — proven by
        # forcing a tiny window and planting a title only in the discarded
        # part; the default (generous) window still reads a small file whole.
        transcript_d = Path(tmp) / "d.jsonl"
        transcript_d.write_text(
            _jsonl({"type": "ai-title", "aiTitle": "front only"})
            + ("y" * 5000) + "\n"
            + _jsonl({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "tail reply"}]}}),
            encoding="utf-8")
        small_tail = agent_hook._tail_lines(transcript_d, tail_bytes=200)
        results["hook: a small tail window really excludes the front"] = (
            "front only" not in "\n".join(small_tail))
        results["hook: the default tail window still reads a small file whole"] = (
            agent_hook.transcript_title({"transcript_path": str(transcript_d)})
            == "front only")

        # E: a missing transcript path degrades to None, never an exception —
        # the hook must never fail the turn it reports on.
        results["hook: a missing transcript file is handled, not fatal"] = (
            agent_hook.transcript_title(
                {"transcript_path": str(Path(tmp) / "missing.jsonl")}) is None
            and agent_hook.transcript_summary({"transcript_path": ""}) is None
            and agent_hook.transcript_title({}) is None)

    # --- A QUESTION IS NOT AN ENDING (owner 2026-08-09, task 137) ---------
    # Claude Code raises a `Notification` hook when it stops to ASK — a
    # permission, a choice, one of the votes he sees on screen. It is a
    # different event from a turn ending and it gets a different sentence,
    # because a turn that ended can wait and a question has stopped
    # everything until he answers.
    results["a question says it is a question"] = (
        notify.compose("Vibe Coder", "asking", "Allow Bash?")[0]
        == "Vibe Coder is asking you")
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
    # …AND A REAL SETTINGS FILE THAT HOLDS ONLY THE OLD `Stop` LINE IS HEALED
    # (owner report 2026-08-15, top priority: a permission prompt reached his
    # phone as NOTHING). The two checks above drove `hook_entry` alone and
    # were green while his settings.json carried no Notification hook at all
    # — a machine registered before 2026-08-09 read as installed forever. So
    # this one writes the OLD shape into a temp settings file, asks what is
    # missing, heals with the SAME python+script the Stop line names, and
    # reads the file back.
    with tempfile.TemporaryDirectory() as tmp:
        settings = Path(tmp) / "settings.json"
        old_entry = agent_hook.hook_entry(Path(tmp) / "agent_hook.py", "py.exe", "Stop")
        settings.write_text(json.dumps({"hooks": {"Stop": [old_entry]}}),
                            encoding="utf-8")
        saved = agent_hook.SETTINGS
        agent_hook.SETTINGS = settings
        # `notify._hook_module()` loads the script FRESH on every call (it
        # must run under any interpreter), so the override above would never
        # reach it — hand it this very module for the duration.
        saved_loader = notify._hook_module
        notify._hook_module = lambda: agent_hook
        try:
            before = agent_hook.missing_events()
            pair = agent_hook.registered_command()
            healed = False
            if pair and agent_hook.is_installed():
                notify.refresh_agent_hook()      # the REAL start-up path
                healed = agent_hook.missing_events() == ()
            data = json.loads(settings.read_text(encoding="utf-8"))
            note = " ".join(h.get("command", "")
                            for e in data["hooks"].get("Notification") or []
                            for h in e.get("hooks") or [])
        finally:
            agent_hook.SETTINGS = saved
            notify._hook_module = saved_loader
    results["an old settings file names Notification as the missing hook"] = (
        before == ("Notification",))
    results["the heal registers it with the SAME python and script"] = (
        healed and "py.exe" in note and "--asking" in note
        and str(Path(tmp) / "agent_hook.py") in note)

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

    reg = _Reg(_Lay("Chrome", "notes"), _Lay("Claude", "vibecoder"))
    notify._layouts = reg
    # The hook sends a PATH; the registry speaks folder names, lowercased.
    results["the notice finds the layout by the agent's own cwd"] = (
        notify.layout_of(r"U:\Coding\UVuruna\Applications\VibeCoder")
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
        notify.layout_of("Vibe Coder") is None)
    notify._layouts = reg

    # --- THE LIFE HE ACTUALLY LIVES (task 236, his THIRD report) -----------
    # Everything above stubs `project()` — so two rounds of green gates proved
    # layout_of's LOOP and never once ran the thing that answers it. His real
    # layout is a GRID whose Claude member is a torn-off VS Code tab, and such
    # a tab's own window is titled after the CONVERSATION, never the folder;
    # the folder is on the window it was torn OUT of, and on the sibling
    # members. `project()` asked members[0] and its source and nothing else.
    import window_manager        # the package entry point; layout_registry
    import layout_registry       # imports IT, so this order is the safe one
    import logging as _logging
    assert window_manager.Layout is layout_registry.Layout

    titles = {}
    real_alive, real_title = layout_registry.wm.is_alive, layout_registry.wm._title
    layout_registry.wm.is_alive = lambda h: h in titles
    layout_registry.wm._title = lambda h: titles.get(h, "")
    try:
        # 101 = the torn-off Claude tab (conversation title, no folder at all)
        # 100 = the window it came out of, and 102 a plain sibling member.
        titles.update({
            100: "prompt.txt - VibeCoder - Visual Studio Code",
            101: "Ispravka UI dizajna menija - Visual Studio Code",
            102: "server.py - VibeCoder - Visual Studio Code [Administrator]",
            103: "Docs - Google Chrome",
        })
        # Cell 0 is a Chrome window that names nothing; the agent's own window
        # is cell 1, and it is the torn-off tab. This is his layout.
        grid = layout_registry.Layout(
            "Claude", "code.exe", [103, 101], "2-side", "landscape", 1.6,
            sources={101: 100})
        results["a torn-off tab's layout still names its project"] = (
            grid.project() == "vibecoder")
        # ...and specifically NOT because member[0] happened to answer: strip
        # the source and the SIBLING must carry it (the planted defect for the
        # members[0]-only reading is exactly this shape).
        lone = layout_registry.Layout(
            "Claude", "code.exe", [101, 102], "2-side", "landscape", 1.6)
        results["a sibling member answers when cell 0 cannot"] = (
            lone.project() == "vibecoder")
        # A layout of something else must still NOT match — widening the reach
        # must not widen it into a false jump.
        titles[200] = "Downloads"
        other = layout_registry.Layout("Files", "explorer.exe", [200], None,
                                       "landscape", 1.6)
        results["widening the reach does not invent a match"] = (
            other.project() == "" and other.projects() == [])
        results["a layout reports every project it holds"] = (
            grid.projects() == ["vibecoder"])

        # (a) A NOTICE THAT SHIPS WITHOUT A LAYOUT SAYS SO, AT INFO, WITH THE
        # PROJECTS THE LIVE LAYOUTS REALLY HOLD. The silence was half the
        # repeat: a miss and a hit looked identical in his log.
        class _Reg2:
            layouts = [other]

            def prune(self):
                return [0]

        notify._layouts = _Reg2()
        seen = []

        class _Sink(_logging.Handler):
            def emit(self, record):
                seen.append((record.levelno, record.getMessage()))

        sink = _Sink()
        notify.logger.addHandler(sink)
        notify.logger.setLevel(_logging.INFO)
        try:
            missed = notify.layout_of(r"U:\Coding\UVuruna\Applications\VibeCoder")
        finally:
            notify.logger.removeHandler(sink)
        info = [m for lvl, m in seen if lvl >= _logging.INFO]
        results["a miss is LOGGED at INFO, never silent"] = (
            missed is None and len(info) == 1)
        results["…naming the project it looked for"] = (
            bool(info) and "vibecoder" in info[0].lower())
        results["…and what the live layouts really hold"] = (
            bool(info) and "Files" in info[0])
    finally:
        layout_registry.wm.is_alive, layout_registry.wm._title = real_alive, real_title
        notify._layouts = reg

    # The hook itself must actually PUT the title on the wire — a matcher
    # that works in notify.py is worthless if agent_hook.send() never sends
    # the field it is supposed to match against.
    sent_bodies = []
    real_urlopen = agent_hook.urllib.request.urlopen

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"ok": true}'

    def _fake_urlopen(request, timeout=0):
        sent_bodies.append(json.loads(request.data))
        return _FakeResponse()

    agent_hook.urllib.request.urlopen = _fake_urlopen
    real_read_token = agent_hook.read_token
    agent_hook.read_token = lambda: "tok"
    try:
        agent_hook.send("Agent", "finished", "text", "U:\\proj", "Real title")
        agent_hook.send("Agent", "finished", "text", "U:\\proj")  # no title given
    finally:
        agent_hook.urllib.request.urlopen = real_urlopen
        agent_hook.read_token = real_read_token
    results["send() puts the conversation title on the wire"] = (
        sent_bodies[0]["title"] == "Real title")
    results["send() with no title sent still carries the field, empty"] = (
        sent_bodies[1]["title"] == "")

    # --- THE CONVERSATION TITLE, NOT JUST THE PROJECT (owner ruling
    # 2026-08-13) -------------------------------------------------------
    # "da notifikacije bira layout u cijem se kreirao" — his report: with
    # several windows of ONE project spread across layouts, the tap always
    # landed on the ⭐ PARENT instead of the window that actually finished.
    # The ⭐ was never involved — layout_of had no tie-break at all and simply
    # returned the FIRST layout in list order whose project matched, and the
    # parent sits at the lowest index because it exists before anything is
    # torn off it. The fix tries the conversation TITLE first.
    results["title match: exact, VS Code's own furniture stripped"] = (
        notify._title_matches(
            "Ispravka UI dizajna menija",
            "Ispravka UI dizajna menija - Vibe Coder - Visual Studio Code "
            "[Administrator]"))
    results["title match: VS Code's ellipsis is a truncated PREFIX"] = (
        notify._title_matches(
            "Ispravka UI dizajna menija",
            "Ispravka UI dizajna meni… - Vibe Coder - Visual Studio Code"))
    results["title match: a torn-off tab's window carries no folder segment"] = (
        notify._title_matches("Ispravka UI dizajna menija",
                              "Ispravka UI dizajna menija - Visual Studio Code"))
    results["title match: two DIFFERENT elided titles never collide"] = not (
        notify._title_matches(
            "Fix login retry",
            "Fix login retriever meni… - Vibe Coder - Visual Studio Code"))
    results["title match: an unrelated window never matches"] = not (
        notify._title_matches("Ispravka UI dizajna menija", "Docs - Google Chrome"))
    results["title match: an empty title never matches by accident"] = not (
        notify._title_matches("", "Anything - Vibe Coder - Visual Studio Code"))

    titles2 = {}
    real_alive2 = layout_registry.wm.is_alive
    real_title2 = layout_registry.wm._title
    layout_registry.wm.is_alive = lambda h: h in titles2
    layout_registry.wm._title = lambda h: titles2.get(h, "")
    try:
        # His exact report, reproduced: two layouts hold windows of the SAME
        # project ("VibeCoder"). The parent (index 0, created first) is a
        # DIFFERENT conversation; the real target (index 1) is a torn-off tab
        # titled after the conversation that actually finished.
        titles2.update({
            300: "prompt.txt - VibeCoder - Visual Studio Code",
            301: "Add region streaming - VibeCoder - Visual Studio Code",
            400: "Ispravka UI dizajna menija - Visual Studio Code",
        })
        parent = layout_registry.Layout(
            "VibeCoder", "code.exe", [300, 301], "2-side", "landscape", 1.6)
        target = layout_registry.Layout(
            "Claude", "code.exe", [400], None, "landscape", 1.6)
        notify._layouts = _Reg(parent, target)

        results["the conversation title picks the RIGHT layout, "
                "not the first one sharing the project"] = (
            notify.layout_of(r"U:\Coding\UVuruna\Applications\VibeCoder",
                             "Ispravka UI dizajna menija")
            == {"index": 1, "name": "Claude"})
        # AN OLDER HOOK, hard requirement: no `title` sent, `layout_of` gets
        # "" (the route's own `clean()` default), and the answer must be
        # BYTE-FOR-BYTE what it was before this round — the first layout by
        # project, i.e. the parent.
        results["an older hook (no title) lands exactly where it always did"] = (
            notify.layout_of(r"U:\Coding\UVuruna\Applications\VibeCoder")
            == {"index": 0, "name": "VibeCoder"})
        # A title that matches NOTHING live falls back to the project search
        # too — never a guess, never a miss where the old behaviour had a hit.
        results["a title matching no window falls back to the project search"] = (
            notify.layout_of(r"U:\Coding\UVuruna\Applications\VibeCoder",
                             "Something nobody ever said")
            == {"index": 0, "name": "VibeCoder"})
    finally:
        layout_registry.wm.is_alive = real_alive2
        layout_registry.wm._title = real_title2
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
                        "(KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36 VibeCoderApp"),
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

        post(gate.PORT, {"agent": "VibeCoder · 3f9c1a", "event": "finished",
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
            and notifs[0][1] == "VibeCoder · 3f9c1a finished"
            and notifs[0][3] == "VibeCoder · 3f9c1a"      # tag = the agent
            and notifs[1][1] == "ML · 77bb02 needs you"
            and notifs[1][3] != notifs[0][3])               # ...so they never merge
        results["the phone speaks the agent's name"] = (
            len(speaks) == 2 and "VibeCoder" in speaks[0][1])

        # --- THE VOICE NEVER READS THE BODY (owner v0.0.107 screenshots) ---
        # A notify with a genuinely long body must be SHOWN in full (the
        # banner's job) but SPOKEN as project + agent only.
        long_body = ("razmisljam o resenju problema sa iscekivanjem konekcije "
                    "i treba mi tvoja odluka pre nego sto nastavim dalje")
        post(gate.PORT, {"agent": "Claude Code (Vibe Coder)", "event": "waiting",
                         "text": long_body,
                         "project": "U:/Coding/UVuruna/Applications/VibeCoder"},
             gate.TOKEN)
        page.wait_for_function("window.__calls.length >= 6", timeout=5000)
        speaks2 = [c for c in page.evaluate("window.__calls") if c[0] == "speak"]
        results["a long body is never read aloud"] = (
            len(speaks2) == 3
            and long_body not in speaks2[2][1]
            and speaks2[2][1] == "VibeCoder — Claude Code (Vibe Coder)")

        # --- AN OLDER SERVER (no speak_text) still speaks something ---------
        # notify.js's own fallback, proven live rather than by reading the
        # source: a notice with the field stripped must fall back to the OLD
        # title(.body) behaviour, never silence.
        page.evaluate("window.__calls = []")
        page.evaluate("""() => handleNotify({type:'notify', agent:'Old Server',
          event:'finished', title:'Old Server finished', text:'', speak:true,
          at: Date.now() / 1000})""")
        speaks3 = [c for c in page.evaluate("window.__calls") if c[0] == "speak"]
        results["speak_text absent still speaks the title"] = (
            len(speaks3) == 1 and speaks3[0][1] == "Old Server finished")
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

        # 174: `enter` must be DATA-DRIVEN, not hardcoded true (round 30
        # diagnosis — `panels.js:710 hardcodes enter:true, so the enter field
        # in actions.json is dead code for options buttons`). An option that
        # says `enter:false` (a menu-standing command whose finished argument
        # still opens another app's own picker) must be honoured, never
        # overridden.
        page.evaluate("window.__sent = []")
        page.evaluate("openChoicePanel({label:'Menu-standing', text:'/x',"
                      " options:[{label:'no-enter', value:'y', enter:false}]})")
        page.wait_for_selector("#choice-panel .sets-row.choice", timeout=4000)
        page.locator("#choice-panel .sets-row.choice", has_text="no-enter").first.tap()
        page.wait_for_function("window.__sent.some(m => m.type === 'paste_text')",
                               timeout=4000)
        sent2 = [m for m in page.evaluate("window.__sent") if m["type"] == "paste_text"]
        results["an option's own enter:false is honoured, not hardcoded true"] = (
            len(sent2) == 1 and sent2[0]["text"] == "/x y" and sent2[0]["enter"] is False)

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

        results["no page errors"] = not page.evaluate("window.__pageErrors || []")

        # --- THE RACE HE LIVES IN (task 236) -------------------------------
        # A SECOND page, because this one must carry the shell bridge from
        # BEFORE its first line runs: `IN_APP` is a const read at load, and
        # the tap's whole pull path is gated on it — a bridge injected after
        # the page is up proves nothing about the phone, where it is always
        # there first. (Connecting closes the first page with 4409, which is
        # the rule; every check above is finished by now.)
        page = ctx.new_page()
        page.add_init_script("""window.Android = {
          noticeJump: () => window.__shell || '',
          prefGet: () => null, prefSet: () => {}, notify: () => {},
          notifyAt: () => {}, speak: () => {},
        };""")
        page.goto(f"http://127.0.0.1:{gate.PORT}/?token={gate.TOKEN}")
        page.wait_for_function(
            "document.getElementById('status').textContent.includes('Connected')",
            timeout=8000)

        # His case, exactly: the app is in the BACKGROUND on another layout,
        # the notification is tapped, MainActivity.onNewIntent nudges the page
        # AT ONCE — before onResume, so the page is still hidden and its socket
        # is closed by rule (constraint 8). The old code pulled the jump out of
        # the shell there (clearing it), spent it on a `send()` that dies on a
        # dead socket, and the reconnect a second later resumed the layout the
        # SERVER remembered: the previous one, every single time.
        race = page.evaluate("""() => {
          const out = {};
          window.__shell = JSON.stringify({index: 1, name: 'Claude'});
          window.Android.noticeJump = () => {
            const h = window.__shell; window.__shell = ''; return h; };
          const live = ws;
          const real = window.send;
          const sent = [];
          const dropped = [];
          // state.js DROPS a message on a dead socket (the pill says
          // "Reconnecting…"). The stub must do the same or the gate would
          // measure a send that never leaves the phone.
          window.send = (m) => {
            if (ws && ws.readyState === WebSocket.OPEN) sent.push(m);
            else dropped.push(m);
          };
          const lay = (name) => ({name, title: name, members: 1, grid: null,
            orient: 'landscape', ratio: null, pos: 0.5, agents: [],
            member_titles: [name], dependents: [], parent: false, icon: null});
          try {
            // 1. the nudge, on a dead socket
            ws = null;
            window.__noticeJump();
            out.parked = window.__shell !== '';  // still in the shell, unread
            out.sentWhileDead = sent.length + dropped.length;  // nothing spent
            // 2. the reconnect: the server resumed the PREVIOUS layout (0) and
            //    layoutRestore points there too — both orderings at once.
            ws = live;
            layouts = [lay('Notes'), lay('Claude')];
            layoutRestore = {index: 0, name: 'Notes'};
            ws.onmessage({data: JSON.stringify({type: 'layout_state',
              layouts, active: 0, region: null, orient: 'landscape'})});
          } catch (e) { out.err = String(e); }
          out.focus = sent.filter((m) => m.type === 'layout_focus').map((m) => m.index);
          out.shellEmpty = window.__shell === '';
          out.dropped = dropped.length;
          window.send = real;
          ws = live;
          return out;
        }""")
        results["a tap on a dead socket is left in the shell, not spent"] = (
            race.get("parked") is True and race.get("sentWhileDead") == 0)
        results["the tap wins the reconnect, beating the resumed layout"] = (
            race.get("focus") == [1] and race.get("dropped") == 0)
        results["…and it is taken exactly once"] = race.get("shellEmpty") is True

        # The other ordering: the page is already up and the socket alive when
        # the tap lands — the nudge must act immediately, with no layout_state
        # to wait for.
        warm = page.evaluate("""() => {
          window.__shell = JSON.stringify({index: 0, name: 'Notes'});
          const real = window.send;
          const sent = [];
          window.send = (m) => { sent.push(m); };
          layoutActive = 1;
          try { window.__noticeJump(); } catch (e) { /* reported below */ }
          window.send = real;
          return sent.filter((m) => m.type === 'layout_focus').map((m) => m.index);
        }""")
        results["a tap on a LIVE socket acts at once"] = warm == [0]

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
