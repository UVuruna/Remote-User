"""CLAUDE STATE GATE — the panels are told what the conversation is running
NOW, read from the PC, and told nothing rather than something wrong.

His report (2026-08-11, task 208): "model ne piše koji je trenutno", and the
Thinking panel highlighted Medium while his PC was really on Max. Both panels
were showing a per-device memory of what the phone last SENT, wearing a look
that reads as live state — and `/model` and `/effort` apply to the RUNNING
session only, so the saved settings file cannot answer the question either.

The source is the transcript Claude Code writes as it goes. Its shape was
MEASURED on real transcripts on this PC (2026-08-11), because task 208's
original note — "effort has no such trail" — was FALSE, and a fix built on it
would have shipped a Thinking panel that could never say anything:

  * every `assistant` record carries BOTH `message.model` and a top-level
    `effort`, tool-call records included (there is nothing to skip);
  * `permissionMode` rides only SOME `user` records — a tool RESULT is a
    `user` record too and carries none, so "the last user record" answers null
    nearly every time and the rule must be "the last record that HAS it";
  * a `{"type": "mode"}` record exists but read `normal` in all 373 of them
    across every project on this PC, so it cannot distinguish plan mode and is
    deliberately not the source.

Those three sentences are what this gate encodes: it drives the REAL reader
over transcripts built to look like his, so a later round cannot quietly go
back to a rule that reads nothing.

Every check was proven by planting its own defect — see DEFECTS below.

Run:  .venv\\Scripts\\python tests/test_claude_state.py
"""

import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import agents  # noqa: E402
import claude_api  # noqa: E402

WEB = PROJECT / "server" / "web.py"
CLIENT = PROJECT / "client"

DEFECTS = {
    "the newest assistant record wins":
        "iterate the tail forwards instead of reversed (the first record wins)",
    "a tool-call record still names the model and the effort":
        "skip assistant records whose content holds no text block",
    "the [1m] variant is one family and keeps its whole id":
        "return the raw id as the family (no [1m] strip)",
    "the mode is the last record that HAS permissionMode":
        "take it from the last `user` record and accept the absent field as "
        "the answer (the natural reading of task 208's own note)",
    "nothing readable answers nulls, never an exception":
        "drop the json.loads guard in _tail_records — a torn last line then "
        "raises instead of being skipped",
    "the newest session of the project is the one read":
        "keep the first matching slug's OLDEST transcript (min instead of "
        "max, first-wins instead of newest-wins)",
    "the reader is really wired to the phone":
        "delete the claude_state branch from web.py",
    "a saved [1m] id lights its family row":
        "drop the two lines that compute `family` in agents.claude_settings "
        "— the raw id alone, which is the shipped behaviour this fixes",
    "the phone matches the saved row by FAMILY":
        "restore `claudeSaved.model === m.value` in claude-panels.js",
}


# ═══════════════════════════ A TRANSCRIPT THAT LOOKS LIKE HIS ═══════════════════════════
def assistant(model: str, effort: str, tool_only: bool = True) -> dict:
    """An assistant record as Claude Code writes it. Tool-call-only by
    default, because in a working session that is most of them — the shape the
    reader must NOT skip."""
    block = ({"type": "tool_use", "id": "t1", "name": "Bash", "input": {}}
             if tool_only else {"type": "text", "text": "…"})
    return {"type": "assistant", "effort": effort, "cwd": r"u:\Coding\Demo",
            "message": {"role": "assistant", "model": model, "content": [block]}}


def prompt(mode: str) -> dict:
    """A real user prompt — the only kind of user record carrying the mode."""
    return {"type": "user", "permissionMode": mode, "cwd": r"u:\Coding\Demo",
            "message": {"role": "user", "content": "go"}}


def tool_result() -> dict:
    """A tool RESULT: also `type: user`, and it carries no permissionMode.
    This record is the whole reason the rule is "the last one that has it"."""
    return {"type": "user", "cwd": r"u:\Coding\Demo",
            "message": {"role": "user",
                        "content": [{"type": "tool_result", "content": "ok"}]}}


def mode_record() -> dict:
    """The dedicated record that reads `normal` on every transcript here."""
    return {"type": "mode", "mode": "normal"}


# What `Projects` below writes into its fake settings.json, as the frame must
# carry it. `model_family` rides BESIDE the raw id, never instead of it (see
# `check_a_saved_1m_id_lights_its_family_row`): the id is the fact on disk and
# the family is the only field anything may MATCH on.
SAVED = {"model": "claude-sonnet-4-5", "model_family": "sonnet",
         "effort": "high"}


class Projects:
    """A fake `~/.claude/projects`. Nothing on the owner's own machine is read
    while this stands — he works on it while these run."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="ru_claude_state_"))

    def __enter__(self):
        self._saved = (agents.CLAUDE_PROJECTS, agents.CLAUDE_SETTINGS)
        agents.CLAUDE_PROJECTS = self.dir
        agents.CLAUDE_SETTINGS = self.dir / "settings.json"
        agents.CLAUDE_SETTINGS.write_text(
            json.dumps({"model": "claude-sonnet-4-5", "effortLevel": "high"}),
            encoding="utf-8")
        return self

    def __exit__(self, *_exc):
        agents.CLAUDE_PROJECTS, agents.CLAUDE_SETTINGS = self._saved
        shutil.rmtree(self.dir, ignore_errors=True)
        return False

    def session(self, slug: str, name: str, records: list[dict],
                mtime: float | None = None, cwd: str = r"u:\Coding\Demo") -> Path:
        folder = self.dir / slug
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}.jsonl"
        # `folder_of` reads `cwd` out of the first lines — the slug's own name
        # can never be split back into a folder (it flattens spaces to dashes).
        lines = [json.dumps({"type": "summary", "cwd": cwd})]
        lines += [json.dumps(r) for r in records]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        if mtime is not None:
            import os
            os.utime(path, (mtime, mtime))
        return path


# ═══════════════════════════ THE CHECKS ═══════════════════════════
def check_the_newest_assistant_record_wins() -> bool:
    """He switches model mid-conversation; the panel must show what it is
    running NOW, not what it opened as."""
    with Projects() as pj:
        pj.session("u--Coding-Demo", "s1", [
            assistant("claude-opus-5", "low"),
            prompt("default"),
            assistant("claude-sonnet-4-5", "medium"),
            prompt("plan"),
            assistant("claude-fable-5", "high"),
        ])
        state = agents.claude_state("demo")
    if (state["model_id"], state["effort"]) != ("claude-fable-5", "high"):
        print(f"    got {state}")
        return False
    return state["model"] == "fable" and state["mode"] == "plan"


def check_a_tool_call_record_still_names_the_model() -> bool:
    """The measured truth: EVERY assistant record carries model + effort, and
    in a working session the last one is almost always a bare tool call. A
    reader that waited for a text block would answer null exactly while he is
    watching the agent work."""
    with Projects() as pj:
        pj.session("u--Coding-Demo", "s1", [
            assistant("claude-sonnet-4-5", "low", tool_only=False),
            prompt("auto"),
            assistant("claude-fable-5", "max", tool_only=True),
            tool_result(),
            assistant("claude-fable-5", "max", tool_only=True),
        ])
        state = agents.claude_state("demo")
    if state["effort"] != "max" or state["model_id"] != "claude-fable-5":
        print(f"    got {state}")
        return False
    return True


def check_the_1m_variant_is_one_family_and_keeps_its_id() -> bool:
    """`claude-opus-5[1m]` is the opus family with a bigger context window.
    The family is what lights a row; the raw id is what a later panel or a log
    needs, so it is passed through whole."""
    with Projects() as pj:
        pj.session("u--Coding-Demo", "s1",
                   [prompt("default"), assistant("claude-opus-5[1m]", "medium")])
        state = agents.claude_state("demo")
    if state["model"] != "opus" or state["model_id"] != "claude-opus-5[1m]":
        print(f"    got {state}")
        return False
    # Every family, and an id we do not know answers nothing rather than the
    # nearest match — a panel lighting the wrong row is a lie he would act on.
    for raw, family in (("claude-fable-5", "fable"), ("claude-haiku-4-5", "haiku"),
                        ("claude-sonnet-4-5[1m]", "sonnet"),
                        ("some-other-model", ""), ("", "")):
        if agents.model_family(raw) != family:
            print(f"    {raw!r} → {agents.model_family(raw)!r}, wanted {family!r}")
            return False
    return True


def check_a_saved_1m_id_lights_its_family_row() -> bool:
    """THE SAVED HALF IS NORMALISED TOO (grader 2026-08-11).

    The owner's own settings.json holds `claude-fable-5[1m]` — a full id with a
    context-window suffix. The LIVE half of this frame has always been reduced
    to a family, but the saved half was handed to the phone raw, and the phone
    compares it against the five literals of its own picker ("fable",
    "opus[1m]", …). A full id equals none of them, so the "saved" mark could
    never land on any row on HIS machine and the chip printed the id back at
    him — a panel about which model is chosen that cannot say which is chosen.

    So the check is the owner's own file, not a tidy one: a `[1m]` id must
    carry `model_family` that the phone's row list can match, the raw id must
    still be there beside it, and an alias that names no family (`default`)
    must leave the field OFF rather than guess a near one.

    PLANTED DEFECT (proof this check can fail): dropping the two lines that
    compute `family` in `agents.claude_settings` — i.e. returning the raw id
    alone, which is exactly the shipped behaviour this fixes — makes the first
    branch below fail with `model_family` absent."""
    with Projects() as pj:
        for raw, family in (("claude-fable-5[1m]", "fable"),
                            ("claude-opus-5[1m]", "opus"),
                            ("sonnet", "sonnet")):
            agents.CLAUDE_SETTINGS.write_text(
                json.dumps({"model": raw, "effortLevel": "high"}),
                encoding="utf-8")
            saved = agents.claude_state("demo")["saved"]
            if saved.get("model_family") != family:
                print(f"    {raw!r} → model_family "
                      f"{saved.get('model_family')!r}, wanted {family!r}")
                return False
            if saved.get("model") != raw:
                print(f"    the raw id was lost: {saved}")
                return False
        # A family we cannot name is answered with SILENCE, never the nearest
        # one — the same rule `model_family` itself obeys. `default` names no
        # family on purpose: it resolves to whatever the account picks, so no
        # row of the phone's list may claim to be it.
        for raw in ("default", "some-other-model"):
            agents.CLAUDE_SETTINGS.write_text(
                json.dumps({"model": raw, "effortLevel": "high"}),
                encoding="utf-8")
            saved = agents.claude_state("demo")["saved"]
            if "model_family" in saved:
                print(f"    {raw!r} guessed a family: {saved}")
                return False
            if saved.get("model") != raw:
                print(f"    the raw id was lost: {saved}")
                return False
    return True


def check_the_phone_matches_the_saved_row_by_family() -> bool:
    """The other half of the same bug, on the page: a field the server sends
    that nothing reads is a feature that does not exist (the actions.json
    lesson, 2026-08-07). `client/claude-state.js` must reduce `saved` through
    its OWN row list and `client/claude-panels.js` must mark the row by that
    answer — never by `saved.model`, which is the raw id.

    PLANTED DEFECT: restoring `claudeSaved.model === m.value` in
    claude-panels.js fails the second branch."""
    state_js = (CLIENT / "claude-state.js").read_text(encoding="utf-8")
    panels_js = (CLIENT / "claude-panels.js").read_text(encoding="utf-8")
    if "model_family" not in state_js or "claudeSavedModel" not in state_js:
        print("    claude-state.js never reduces the saved id to a family")
        return False
    if "claudeSavedModel(claudeSaved)" not in panels_js:
        print("    the Model panel does not ask which row is saved")
        return False
    if "claudeSaved.model ===" in panels_js:
        print("    the Model panel still compares the RAW saved id to a row")
        return False
    return True


def check_the_mode_is_the_last_record_that_has_it() -> bool:
    """Tool results are `user` records with no permissionMode, and a session
    ends on one far more often than not. "The last user record" would answer
    null; "the last record that has the field" answers his real mode."""
    with Projects() as pj:
        pj.session("u--Coding-Demo", "s1", [
            prompt("plan"),
            assistant("claude-fable-5", "high"),
            tool_result(),
            mode_record(),          # reads `normal` on every real transcript
            tool_result(),
        ])
        state = agents.claude_state("demo")
    if state["mode"] != "plan":
        print(f"    got mode {state['mode']!r} (wanted 'plan')")
        return False
    return True


def check_nothing_readable_answers_nulls() -> bool:
    """A project with no conversation, a project directory that does not
    exist, a transcript holding nothing yet, and a half-written last line —
    each answers null and none of them raises. `saved` still stands: it comes
    from a different file and is the one thing that is always knowable."""
    with Projects() as pj:
        for folder in ("demo", "", "nothing-here"):
            state = agents.claude_state(folder)
            if any(state[k] is not None for k in ("model", "model_id", "effort", "mode")):
                print(f"    {folder!r} invented {state}")
                return False
            if state["saved"] != SAVED:
                print(f"    saved was {state['saved']}")
                return False
        empty = pj.session("u--Coding-Demo", "s1", [])
        if agents.claude_state("demo")["model"] is not None:
            return False
        # A transcript being appended to while we read it legitimately ends
        # mid-line; the good records before it must still be read.
        with empty.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(assistant("claude-fable-5", "high")) + "\n")
            fh.write('{"type": "assis')
        state = agents.claude_state("demo")
        if state["model_id"] != "claude-fable-5":
            print(f"    a torn last line lost the record before it: {state}")
            return False
    return True


def check_the_newest_session_of_the_project_is_read() -> bool:
    """He resumes, or opens a second conversation on the same project. The one
    he is looking at is the one being WRITTEN — and a different project's
    newer transcript must not be borrowed for it."""
    with Projects() as pj:
        pj.session("u--Coding-Demo", "old",
                   [prompt("default"), assistant("claude-haiku-4-5", "low")],
                   mtime=1_700_000_000)
        pj.session("u--Coding-Demo", "new",
                   [prompt("auto"), assistant("claude-opus-5", "max")],
                   mtime=1_800_000_000)
        pj.session("u--Coding-Other", "elsewhere",
                   [prompt("plan"), assistant("claude-sonnet-4-5", "medium")],
                   mtime=1_900_000_000, cwd=r"u:\Coding\Other")
        state = agents.claude_state("demo")
    if state["model_id"] != "claude-opus-5" or state["effort"] != "max":
        print(f"    got {state}")
        return False
    return state["mode"] == "auto"


class FakeWs:
    def __init__(self):
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))


class FakeLayout:
    def __init__(self, folder):
        self.folder = folder

    def project(self):
        return self.folder


class FakeLayouts:
    def __init__(self, *folders):
        self.layouts = [FakeLayout(f) for f in folders]


def check_the_reader_is_really_wired_to_the_phone() -> bool:
    """A pure function nobody calls is a feature that does not exist (the
    actions.json lesson, 2026-08-07). Driven through the REAL handler: the
    focused layout's project decides, and the desktop — where there is no one
    conversation to describe — answers nulls with `saved` still standing."""
    with Projects() as pj:
        pj.session("u--Coding-Demo", "s1",
                   [prompt("plan"), assistant("claude-fable-5", "high")])
        ws = FakeWs()
        layouts = FakeLayouts("other", "demo")
        asyncio.run(claude_api.send_state(ws, layouts, {"active": 1}))
        asyncio.run(claude_api.send_state(ws, layouts, {"active": None}))
        asyncio.run(claude_api.send_state(ws, layouts, {"active": 7}))  # stale index
    if len(ws.sent) != 3:
        print(f"    the handler answered {len(ws.sent)} times")
        return False
    focused, desktop, stale = ws.sent
    if focused != {"type": "claude_state", "model": "fable",
                   "model_id": "claude-fable-5", "effort": "high", "mode": "plan",
                   "saved": SAVED}:
        print(f"    focused frame was {focused}")
        return False
    for frame in (desktop, stale):
        if frame["model"] is not None or frame["mode"] is not None:
            print(f"    a layout-less frame claimed {frame}")
            return False
        if frame["saved"] != SAVED:
            return False
    web = WEB.read_text(encoding="utf-8")
    if 'kind == "claude_state"' not in web or "claude_api.send_state" not in web:
        print("    web.py never answers claude_state")
        return False
    return True


CHECKS = [
    ("the newest assistant record wins", check_the_newest_assistant_record_wins),
    ("a tool-call record still names the model and the effort",
     check_a_tool_call_record_still_names_the_model),
    ("the [1m] variant is one family and keeps its whole id",
     check_the_1m_variant_is_one_family_and_keeps_its_id),
    ("the mode is the last record that HAS permissionMode",
     check_the_mode_is_the_last_record_that_has_it),
    ("nothing readable answers nulls, never an exception",
     check_nothing_readable_answers_nulls),
    ("the newest session of the project is the one read",
     check_the_newest_session_of_the_project_is_read),
    ("the reader is really wired to the phone",
     check_the_reader_is_really_wired_to_the_phone),
    ("a saved [1m] id lights its family row",
     check_a_saved_1m_id_lights_its_family_row),
    ("the phone matches the saved row by FAMILY",
     check_the_phone_matches_the_saved_row_by_family),
]


def main() -> int:
    print("=== CLAUDE STATE GATE ===")
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
        print(f"CLAUDE STATE GATE FAILED — {failed} check(s).")
        return 1
    print("CLAUDE STATE GATE PASSED — the panels can be told what the "
          "conversation is really running.")
    return 0


def test_claude_state():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
