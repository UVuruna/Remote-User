"""SESSION LEDGER GATE (T111, 2026-08-17) — the plain-Markdown to-do list an
agent keeps beside its project, and the phone reads through `ledger_state {}`.

Contract: `.claude/ledger-plan.md`. This gate proves piece A
(`server/session_ledger.py` + `server/ledger_api.py`) and piece B
(`setup/ledger_hook.py`) against exactly that grammar — parsing, the
downgrade rule, the newest-matching-project lookup, the end-to-end phone
answer, and both hook modes (`prompt`/`stop`).

Every check is proven against a PLANTED defect, either by patching the real
module's source text in memory and reloading it under a scratch name (piece
A — pure, importable) or by writing a patched copy of the hook script to a
temp file and running IT under `python` (piece B — a standalone subprocess
script, exactly like `setup/agent_hook.py` beside it). The plant is applied,
shown to break the very assertion the check makes, then discarded — so a
check that would pass whether or not the feature exists cannot hide in this
file.

Run:  python tests/test_session_ledger.py
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SERVER = PROJECT / "server"
sys.path.insert(0, str(SERVER))

import session_ledger  # noqa: E402
import ledger_api  # noqa: E402

LEDGER_PY = SERVER / "session_ledger.py"
LEDGER_API_PY = SERVER / "ledger_api.py"
HOOK_PY = PROJECT / "setup" / "ledger_hook.py"

PYTHON = sys.executable

DEFECTS = {
    "parse: title/project/states/model/annotations/nesting":
        "swap STATE_COLORS['>'] and STATE_COLORS['?'] — orange and yellow "
        "trade places",
    "[x] without ! downgrades to blue, [x] with ! stays green":
        "short-circuit the downgrade rule in _finalize (`if False and ...`)",
    "category: line": "break _CATEGORY_RE so `category:` never matches",
    "task tags: @model/#feature/stars in ANY order, both star forms":
        "turn each `continue` in the peel loop into a `break` — only the "
        "LAST trailing tag is ever recognized, so any order but the one "
        "sample already uses loses the other two",
    "stars stay 1–5 only": "widen _STARS_TAG_RE past its 1–5 ceiling — *7 "
        "and six stars start counting as a stars tag",
    "an untagged ledger parses exactly as before":
        "make the `#` optional in _FEATURE_TAG_RE — a plain trailing "
        "lowercase word starts looking like a feature slug",
    "a mid-title #word/@word is never stripped":
        "replace the end-anchored, break-on-first-miss peel with a naive "
        "scan that strips a tag-shaped word wherever it sits in the title",
    "ledger_for_project: newest match wins, case/slash-insensitive, None otherwise":
        "make _normalized the identity function (drop casefold + Path "
        "normalization) — case/slash-insensitive matching breaks",
    "send_ledger: focused layout's project (incl. category) arrives, desktop "
    "focus never crashes":
        "drop the `index is not None` bounds guard in send_ledger — a "
        "desktop conn (`active: None`) raises instead of answering empty; "
        "separately, drop `category` from EMPTY and the frame it builds",
    "hook prompt mode: creates the file once, never overwrites":
        "drop the `if not md_path.exists()` guard in cmd_prompt — a second "
        "prompt overwrites the agent's own edits",
    "hook stop mode: blocks unchanged/malformed, never blocks stop_hook_active":
        "drop the `stop_hook_active` early return in cmd_stop — a Claude "
        "Code retry loop would block forever",
}


# ═══════════════════════════ PIECE A — module patch harness ═══════════════════════════
def _load_patched(path: Path, replacements: list[tuple[str, str]], mod_name: str):
    """Read `path`, apply each (old, new) substitution (each old MUST appear
    exactly once — a silent no-op patch proves nothing), exec it as a fresh
    module under `mod_name` so the real, already-imported module is never
    touched. `session_ledger`-derived modules also need `config` on
    sys.modules, already satisfied by the real import above."""
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            raise AssertionError(f"plant text {old!r} appears {count} times in {path}")
        text = text.replace(old, new, 1)
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    exec(compile(text, str(path), "exec"), mod.__dict__)
    return mod


# ═══════════════════════════ SAMPLE LEDGER TEXT ═══════════════════════════
SAMPLE = """\
# Fix the thing
project: U:/Coding/Demo
- [ ] T1 Not started @fable
- [>] T2 In progress @opus
  > a free description
  > second line
- [?] T3 Waiting on the human @sonnet
  ? does this look right to you
- [~] T4 Done, no evidence @haiku
- [x] T5 Done with evidence @fable
  ! tests/test_x.py 12/12
  - [x] T5a subtask one @sonnet
    ! tests/test_y.py 3/3
    - [x] T5b grandchild @fable
      ! grandchild evidence
"""


# ═══════════════════════════ THE CHECKS ═══════════════════════════
def check_parse_grammar() -> bool:
    parsed = session_ledger.parse(SAMPLE)
    if parsed["title"] != "Fix the thing" or parsed["project"] != "U:/Coding/Demo":
        print(f"    title/project: {parsed['title']!r} / {parsed['project']!r}")
        return False
    tasks = parsed["tasks"]
    if len(tasks) != 5:
        print(f"    expected 5 root tasks, got {len(tasks)}")
        return False
    wanted = [
        ("T1", "Not started", "fable", "red"),
        ("T2", "In progress", "opus", "orange"),
        ("T3", "Waiting on the human", "sonnet", "yellow"),
        ("T4", "Done, no evidence", "haiku", "blue"),
        ("T5", "Done with evidence", "fable", "green"),
    ]
    for task, (tid, title, model, color) in zip(tasks, wanted):
        if (task["id"], task["title"], task["model"], task["state"]) != (tid, title, model, color):
            print(f"    task mismatch: {task}")
            return False
    t2, t3, t5 = tasks[1], tasks[2], tasks[4]
    if t2["desc"] != "a free description\nsecond line":
        print(f"    T2 desc: {t2['desc']!r}")
        return False
    if t3["question"] != "does this look right to you":
        print(f"    T3 question: {t3['question']!r}")
        return False
    if t5["evidence"] != "tests/test_x.py 12/12":
        print(f"    T5 evidence: {t5['evidence']!r}")
        return False
    # nesting two levels deep: T5 -> T5a -> T5a1
    if len(t5["children"]) != 1:
        print(f"    T5 children: {t5['children']}")
        return False
    t5a = t5["children"][0]
    if (t5a["id"], t5a["state"], t5a["evidence"]) != ("T5a", "green", "tests/test_y.py 3/3"):
        print(f"    T5a: {t5a}")
        return False
    if len(t5a["children"]) != 1:
        print(f"    T5a children: {t5a['children']}")
        return False
    t5b = t5a["children"][0]
    if (t5b["id"], t5b["state"], t5b["evidence"]) != ("T5b", "green", "grandchild evidence"):
        print(f"    T5b: {t5b}")
        return False

    # Prove the check would fail against a planted defect: swap orange/yellow.
    patched = _load_patched(
        LEDGER_PY,
        [('STATE_COLORS = {" ": "red", ">": "orange", "?": "yellow", "~": "blue", "x": "green"}',
          'STATE_COLORS = {" ": "red", ">": "yellow", "?": "orange", "~": "blue", "x": "green"}')],
        "session_ledger_plant_parse")
    broken = patched.parse(SAMPLE)["tasks"]
    if broken[1]["state"] == "orange" and broken[2]["state"] == "yellow":
        print("    plant did not break the color mapping — check proves nothing")
        return False
    return True


def check_downgrade_rule() -> bool:
    text = ("# T\nproject: p\n"
            "- [x] T1 done, no evidence\n"
            "- [x] T2 done, with evidence\n"
            "  ! it works\n")
    parsed = session_ledger.parse(text)
    t1, t2 = parsed["tasks"]
    if t1["state"] != "blue":
        print(f"    [x] without ! should be blue, got {t1['state']}")
        return False
    if t2["state"] != "green":
        print(f"    [x] with ! should be green, got {t2['state']}")
        return False

    patched = _load_patched(
        LEDGER_PY,
        [('    if state == "x" and not task["evidence"]:',
          '    if False and state == "x" and not task["evidence"]:')],
        "session_ledger_plant_downgrade")
    broken = patched.parse(text)["tasks"]
    if broken[0]["state"] == "blue":
        print("    plant did not disable the downgrade rule — check proves nothing")
        return False
    return True


def check_category_line() -> bool:
    text = ("# Category ledger\nproject: U:/Coding/Demo\n"
            "category: FEATURE + GUI\n- [ ] T1 Task one @fable\n")
    parsed = session_ledger.parse(text)
    if parsed["category"] != "FEATURE + GUI":
        print(f"    category: {parsed['category']!r}")
        return False

    # A ledger written before the `category:` line existed (SAMPLE has none)
    # must default to "" rather than crash or misread the next line as it.
    absent = session_ledger.parse(SAMPLE)
    if absent["category"] != "":
        print(f"    category with no such line present: {absent['category']!r}")
        return False

    patched = _load_patched(
        LEDGER_PY,
        [(r'_CATEGORY_RE = re.compile(r"^category:\s*(.*)$")',
          r'_CATEGORY_RE = re.compile(r"^categoryX:\s*(.*)$")')],
        "session_ledger_plant_category")
    broken = patched.parse(text)
    if broken["category"] == "FEATURE + GUI":
        print("    plant did not break category parsing — check proves nothing")
        return False
    return True


_PEEL_LOOP = (
    '    words = rest.split()\n'
    '    while words:\n'
    '        word = words[-1]\n'
    '        m = _MODEL_TAG_RE.match(word)\n'
    '        if m and not model:\n'
    '            model = m.group(1)\n'
    '            words.pop()\n'
    '            continue\n'
    '        m = _FEATURE_TAG_RE.match(word)\n'
    '        if m and not feature:\n'
    '            feature = m.group(1)\n'
    '            words.pop()\n'
    '            continue\n'
    '        m = _STARS_TAG_RE.match(word)\n'
    '        if m and not stars:\n'
    '            stars = len(m.group(1)) if m.group(1) else int(m.group(2))\n'
    '            words.pop()\n'
    '            continue\n'
    '        break\n'
)


def check_tag_order_and_star_forms() -> bool:
    """`@model`, `#feature-slug` and the star complexity ride in ANY order,
    and the star complexity may be written either as repeated `*`/`★` or as
    `*N`/`★N` — a console-font agent typing `***` and one typing `*3` must
    mean the same thing."""
    cases = [
        ("- [ ] T1 Ship the release @fable #layouts ***\n",
         "fable", "layouts", 3, "Ship the release"),
        ("- [ ] T2 Ship the release #layouts *3 @fable\n",
         "fable", "layouts", 3, "Ship the release"),
        ("- [ ] T3 Ship the release ★★★ @sonnet #kluc\n",
         "sonnet", "kluc", 3, "Ship the release"),
        ("- [ ] T4 Ship the release ★3 @opus #zub\n",
         "opus", "zub", 3, "Ship the release"),
        ("- [ ] T5 Ship the release *3 #zub @haiku\n",
         "haiku", "zub", 3, "Ship the release"),
    ]
    for line, model, feature, stars, title in cases:
        task = session_ledger.parse(f"# T\nproject: p\n{line}")["tasks"][0]
        got = (task["model"], task["feature"], task["stars"], task["title"])
        if got != (model, feature, stars, title):
            print(f"    {line!r} -> {got}, wanted {(model, feature, stars, title)}")
            return False

    # Prove the plant matters: turning each `continue` into a `break` only
    # ever recognizes the SINGLE trailing tag, so a line naming all three in
    # an order other than the one check_parse_grammar already uses loses two
    # of them.
    patched = _load_patched(
        LEDGER_PY,
        [(_PEEL_LOOP, _PEEL_LOOP.replace("continue\n", "break\n"))],
        "session_ledger_plant_peel_once")
    broken = patched.parse(
        "# T\nproject: p\n- [ ] T2 Ship the release #layouts *3 @fable\n")["tasks"][0]
    if (broken["model"], broken["feature"], broken["stars"]) == ("fable", "layouts", 3):
        print("    plant did not break multi-tag peeling — check proves nothing")
        return False
    return True


def check_stars_value_range() -> bool:
    """Only 1–5 stars is a stars tag — `*7` and six stars are not, so they
    stay put as ordinary trailing words in the title."""
    text = ("# T\nproject: p\n- [ ] T1 Ship the release *7\n"
            "- [ ] T2 Ship the release ******\n")
    t1, t2 = session_ledger.parse(text)["tasks"]
    if (t1["stars"], t1["title"]) != (0, "Ship the release *7"):
        print(f"    *7 should not be a stars tag: {t1}")
        return False
    if (t2["stars"], t2["title"]) != (0, "Ship the release ******"):
        print(f"    six stars should not be a stars tag: {t2}")
        return False

    patched = _load_patched(
        LEDGER_PY,
        [(r'_STARS_TAG_RE = re.compile(r"^(?:([*★]{1,5})|[*★]([1-5]))$")',
          r'_STARS_TAG_RE = re.compile(r"^(?:([*★]{1,6})|[*★]([1-9]))$")')],
        "session_ledger_plant_stars_range")
    broken = patched.parse(text)["tasks"]
    if broken[0]["stars"] == 0 and broken[1]["stars"] == 0:
        print("    plant did not widen the stars range — check proves nothing")
        return False
    return True


def check_notag_ledger_unchanged() -> bool:
    """A ledger written before any of these tags existed (SAMPLE has none)
    parses exactly as it always did: feature "", stars 0, titles untouched."""
    parsed = session_ledger.parse(SAMPLE)
    for task in parsed["tasks"]:
        if task["feature"] != "" or task["stars"] != 0:
            print(f"    an untagged task should have feature='' stars=0: {task}")
            return False
    titles = [t["title"] for t in parsed["tasks"]]
    wanted = ["Not started", "In progress", "Waiting on the human",
              "Done, no evidence", "Done with evidence"]
    if titles != wanted:
        print(f"    titles changed: {titles}, wanted {wanted}")
        return False

    # Prove the plant matters: make '#' optional in the feature regex, so a
    # plain trailing lowercase word (no tag character at all) starts reading
    # as a feature slug — the exact regression an old ledger must be immune to.
    patched = _load_patched(
        LEDGER_PY,
        [(r'_FEATURE_TAG_RE = re.compile(r"^#([a-z0-9][a-z0-9-]*)$")',
          r'_FEATURE_TAG_RE = re.compile(r"^#?([a-z0-9][a-z0-9-]*)$")')],
        "session_ledger_plant_feature_optional_hash")
    broken = patched.parse(SAMPLE)["tasks"]
    if all(t["feature"] == "" for t in broken):
        print("    plant did not make a bare word look like a feature — check proves nothing")
        return False
    return True


def check_midtitle_tag_words_untouched() -> bool:
    """A `#`/`@` word in the MIDDLE of a title (not trailing) is never eaten
    — the peel loop stops at the first word, counted from the end, that is
    not a recognized tag."""
    text = "# T\nproject: p\n- [ ] T1 Fix the #123 bug for @home users\n"
    task = session_ledger.parse(text)["tasks"][0]
    wanted = ("", "", 0, "Fix the #123 bug for @home users")
    got = (task["model"], task["feature"], task["stars"], task["title"])
    if got != wanted:
        print(f"    a mid-title #/@ word was touched: {got}, wanted {wanted}")
        return False

    # Prove the plant matters: a naive rewrite that scans EVERY word (not
    # just from the end, stopping at the first non-tag) strips a tag-shaped
    # word wherever it sits — exactly the bug the end-anchored design exists
    # to avoid.
    naive = (
        '    words = rest.split()\n'
        '    kept = []\n'
        '    for word in words:\n'
        '        m = _MODEL_TAG_RE.match(word)\n'
        '        if m and not model:\n'
        '            model = m.group(1)\n'
        '            continue\n'
        '        m = _FEATURE_TAG_RE.match(word)\n'
        '        if m and not feature:\n'
        '            feature = m.group(1)\n'
        '            continue\n'
        '        m = _STARS_TAG_RE.match(word)\n'
        '        if m and not stars:\n'
        '            stars = len(m.group(1)) if m.group(1) else int(m.group(2))\n'
        '            continue\n'
        '        kept.append(word)\n'
        '    words = kept\n'
    )
    patched = _load_patched(LEDGER_PY, [(_PEEL_LOOP, naive)], "session_ledger_plant_naive_scan")
    broken = patched.parse(text)["tasks"][0]
    if "#123" in broken["title"] and "@home" in broken["title"]:
        print("    plant did not eat the mid-title tags — check proves nothing")
        return False
    return True


def check_ledger_for_project() -> bool:
    tmp = Path(tempfile.mkdtemp(prefix="ru_ledger_"))
    saved_dir = session_ledger.sessions_dir
    try:
        session_ledger.sessions_dir = lambda: tmp

        # Nothing yet.
        if session_ledger.ledger_for_project("U:/Coding/Demo") is not None:
            print("    empty dir should match nothing")
            return False

        # An older and a newer ledger for the SAME project (case/slash
        # variant), plus an unrelated one that must never win.
        older = tmp / "old-session.md"
        older.write_text("# Old\nproject: u:\\Coding\\Demo\n- [ ] x\n", encoding="utf-8")
        newer = tmp / "new-session.md"
        newer.write_text("# New\nproject: U:/CODING/demo\n- [>] y\n", encoding="utf-8")
        other = tmp / "other-session.md"
        other.write_text("# Other\nproject: U:/Coding/Elsewhere\n- [ ] z\n", encoding="utf-8")
        import os
        os.utime(older, (1_700_000_000, 1_700_000_000))
        os.utime(newer, (1_800_000_000, 1_800_000_000))

        # THE OWNER'S OWN QUERY (his report 2026-08-17, the panel empty from
        # the day it shipped). `Layout.project()` reads a VS Code window
        # TITLE, and a title names a project without ever naming its path —
        # `agents.title_folder` hands back a lowercased BASENAME. That, not
        # a path, is what this lookup is really asked, and until this round
        # no check in this file had ever asked it that way.
        if session_ledger.ledger_for_project("demo") is None:
            print("    a bare folder name — what Layout.project() really "
                  "returns — matched nothing")
            return False

        found = session_ledger.ledger_for_project("U:/Coding/Demo")
        if found is None:
            print("    expected a match, got None")
            return False
        session_id, path, parsed = found
        if session_id != "new-session" or parsed["title"] != "New":
            print(f"    wrong file won: {session_id!r} / {parsed['title']!r}")
            return False

        if session_ledger.ledger_for_project("U:/Coding/NothingHere") is not None:
            print("    a project nothing matches should return None")
            return False
    finally:
        session_ledger.sessions_dir = saved_dir
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # Prove the plant matters: an identity _normalized reproduces the
    # owner's bug exactly — the ledger's absolute `project:` path can never
    # equal the folder NAME a window title yields, so nothing ever matches.
    patched = _load_patched(
        LEDGER_PY,
        [("    return Path(str(path).strip()).name.casefold()",
          "    return path")],
        "session_ledger_plant_normalize")
    tmp2 = Path(tempfile.mkdtemp(prefix="ru_ledger_plant_"))
    try:
        patched.sessions_dir = lambda: tmp2
        f = tmp2 / "s.md"
        f.write_text("# T\nproject: U:/CODING/demo\n- [ ] x\n", encoding="utf-8")
        if patched.ledger_for_project("demo") is not None:
            print("    plant did not break the folder-name query — check proves nothing")
            return False
        if patched.ledger_for_project("U:/Coding/Demo") is not None:
            print("    plant did not break case/slash insensitivity — check proves nothing")
            return False
    finally:
        import shutil
        shutil.rmtree(tmp2, ignore_errors=True)
    return True


# ─── PIECE A part 2: send_ledger end-to-end ───
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


def check_send_ledger_end_to_end() -> bool:
    import asyncio

    tmp = Path(tempfile.mkdtemp(prefix="ru_ledger_send_"))
    saved_dir = session_ledger.sessions_dir
    try:
        session_ledger.sessions_dir = lambda: tmp
        f = tmp / "sess1.md"
        f.write_text(
            "# Demo session\nproject: U:/Coding/Demo\ncategory: FEATURE + GUI\n"
            "- [>] T1 Working on it @fable\n", encoding="utf-8")

        if ledger_api.EMPTY["category"] != "":
            print(f"    EMPTY should default category to '': {ledger_api.EMPTY}")
            return False

        ws = FakeWs()
        # What a REAL `Layout.project()` hands `send_ledger`: the lowercased
        # folder NAME off a VS Code window title, never a path. This fake
        # used to answer with full paths, which is why every check in this
        # file passed while the owner's panel was empty every single day —
        # the gate was proving the lookup to a fake nothing on his PC could
        # produce (the `user = copy(shipped)` failure of 2026-08-07, one
        # layer up).
        layouts = FakeLayouts("other", "demo")
        asyncio.run(ledger_api.send_ledger(ws, layouts, {"active": 1}))
        asyncio.run(ledger_api.send_ledger(ws, layouts, {"active": None}))
        asyncio.run(ledger_api.send_ledger(ws, layouts, {"active": 99}))  # stale index

        if len(ws.sent) != 3:
            print(f"    handler answered {len(ws.sent)} times, wanted 3")
            return False
        focused, desktop, stale = ws.sent
        if focused["type"] != "ledger_state" or focused["title"] != "Demo session":
            print(f"    focused frame: {focused}")
            return False
        if focused["category"] != "FEATURE + GUI":
            print(f"    focused frame's category: {focused.get('category')!r}")
            return False
        if len(focused["tasks"]) != 1 or focused["tasks"][0]["title"] != "Working on it":
            print(f"    focused tasks: {focused['tasks']}")
            return False
        for frame in (desktop, stale):
            if frame["tasks"] != [] or frame["type"] != "ledger_state" or frame["category"] != "":
                print(f"    layout-less frame should be empty (incl. category): {frame}")
                return False
    finally:
        session_ledger.sessions_dir = saved_dir
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # Prove the plant matters: dropping the bounds guard crashes (or
    # mis-answers) the desktop-focus case instead of quietly answering empty.
    patched = _load_patched(
        LEDGER_API_PY,
        [('    index = conn.get("active")\n'
          '    layout = (layouts.layouts[index]\n'
          '              if index is not None and 0 <= index < len(layouts.layouts) else None)',
          '    index = conn.get("active")\n'
          '    layout = layouts.layouts[index]'),
         ('import session_ledger', 'import session_ledger')],
        "ledger_api_plant_bounds")
    tmp2 = Path(tempfile.mkdtemp(prefix="ru_ledger_send_plant_"))
    try:
        patched.session_ledger.sessions_dir = lambda: tmp2
        ws2 = FakeWs()
        layouts2 = FakeLayouts("U:/Coding/Demo")
        crashed = False
        try:
            asyncio.run(patched.send_ledger(ws2, layouts2, {"active": None}))
        except Exception:
            crashed = True
        if not crashed:
            print("    plant did not break the desktop-focus path — check proves nothing")
            return False
    finally:
        import shutil
        shutil.rmtree(tmp2, ignore_errors=True)

    # Prove `category` matters on its own: drop it from EMPTY and from the
    # frame send_ledger builds — a phone reading `frame.category` would
    # silently get `undefined` on a defect an in-memory dict check alone
    # would miss.
    patched2 = _load_patched(
        LEDGER_API_PY,
        [('EMPTY = {\n'
          '    "type": "ledger_state", "session_id": "", "updated": 0,\n'
          '    "title": "", "project": "", "category": "", "tasks": [],\n'
          '}',
          'EMPTY = {\n'
          '    "type": "ledger_state", "session_id": "", "updated": 0,\n'
          '    "title": "", "project": "", "tasks": [],\n'
          '}'),
         ('    await ws.send_text(json.dumps({\n'
          '        "type": "ledger_state", "session_id": session_id, "updated": updated,\n'
          '        "title": parsed["title"], "project": parsed["project"],\n'
          '        "category": parsed["category"], "tasks": parsed["tasks"],\n'
          '    }))',
          '    await ws.send_text(json.dumps({\n'
          '        "type": "ledger_state", "session_id": session_id, "updated": updated,\n'
          '        "title": parsed["title"], "project": parsed["project"],\n'
          '        "tasks": parsed["tasks"],\n'
          '    }))')],
        "ledger_api_plant_no_category")
    if "category" in patched2.EMPTY:
        print("    plant did not drop category from EMPTY — check proves nothing")
        return False
    tmp3 = Path(tempfile.mkdtemp(prefix="ru_ledger_send_cat_plant_"))
    try:
        patched2.session_ledger.sessions_dir = lambda: tmp3
        f3 = tmp3 / "sess1.md"
        f3.write_text(
            "# Demo session\nproject: U:/Coding/Demo\ncategory: FEATURE\n"
            "- [>] T1 Working on it @fable\n", encoding="utf-8")
        ws3 = FakeWs()
        layouts3 = FakeLayouts("demo")
        asyncio.run(patched2.send_ledger(ws3, layouts3, {"active": 0}))
        if "category" in ws3.sent[0]:
            print("    plant did not drop category from the frame — check proves nothing")
            return False
    finally:
        import shutil
        shutil.rmtree(tmp3, ignore_errors=True)
    return True


# ═══════════════════════════ PIECE B — the hook, as a real subprocess ═══════════════════════════
def _run_hook(script: Path, mode: str, payload: dict, sessions_dir: Path) -> subprocess.CompletedProcess:
    import os
    env = dict(os.environ)
    env["VIBECODER_SESSIONS_DIR"] = str(sessions_dir)
    return subprocess.run(
        [PYTHON, str(script), mode],
        input=json.dumps(payload), capture_output=True, text=True, env=env)


def check_hook_prompt_mode() -> bool:
    tmp = Path(tempfile.mkdtemp(prefix="ru_ledger_hook_"))
    try:
        payload = {"session_id": "abc123", "cwd": r"U:\Coding\Demo",
                   "prompt": "Fix the thing that broke\nmore detail here"}
        r1 = _run_hook(HOOK_PY, "prompt", payload, tmp)
        if r1.returncode != 0:
            print(f"    first run failed: {r1.stderr}")
            return False
        md = tmp / "abc123.md"
        if not md.exists():
            print("    ledger file was not created")
            return False
        text = md.read_text(encoding="utf-8")
        if "# Fix the thing that broke" not in text or "project: U:\\Coding\\Demo" not in text:
            print(f"    ledger content wrong: {text!r}")
            return False
        if "grammar" not in r1.stdout.lower() or "current ledger" not in r1.stdout.lower():
            print(f"    stdout missing grammar/current: {r1.stdout[:200]!r}")
            return False
        if str(md) not in r1.stdout:
            print("    stdout does not print the file path")
            return False

        # Simulate the agent editing the file, then a second prompt in the
        # same session — must NOT overwrite the agent's own edits.
        md.write_text(text + "- [x] T1 done\n  ! it works\n", encoding="utf-8")
        r2 = _run_hook(HOOK_PY, "prompt", payload, tmp)
        if r2.returncode != 0:
            print(f"    second run failed: {r2.stderr}")
            return False
        after = md.read_text(encoding="utf-8")
        if "T1 done" not in after:
            print("    second prompt overwrote the agent's own edits")
            return False
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # Prove the plant matters: dropping the exists() guard overwrites.
    hook_text = HOOK_PY.read_text(encoding="utf-8")
    old = ('    if not md_path.exists():\n'
           '        title = _title_from_prompt(prompt)\n')
    if hook_text.count(old) != 1:
        print(f"    plant anchor text appears {hook_text.count(old)} times")
        return False
    patched_text = hook_text.replace(
        old, '    if True:\n        title = _title_from_prompt(prompt)\n', 1)
    tmp2 = Path(tempfile.mkdtemp(prefix="ru_ledger_hook_plant_"))
    try:
        script2 = tmp2 / "ledger_hook_plant.py"
        script2.write_text(patched_text, encoding="utf-8")
        sessions2 = tmp2 / "sessions"
        sessions2.mkdir()
        _run_hook(script2, "prompt", payload, sessions2)
        md2 = sessions2 / "abc123.md"
        md2.write_text(md2.read_text(encoding="utf-8") + "- [x] T1 done\n  ! it works\n",
                        encoding="utf-8")
        _run_hook(script2, "prompt", payload, sessions2)
        if "T1 done" in md2.read_text(encoding="utf-8"):
            print("    plant did not break the overwrite guard — check proves nothing")
            return False
    finally:
        import shutil
        shutil.rmtree(tmp2, ignore_errors=True)
    return True


def check_hook_stop_mode() -> bool:
    tmp = Path(tempfile.mkdtemp(prefix="ru_ledger_stop_"))
    try:
        payload = {"session_id": "s1", "cwd": r"U:\Coding\Demo", "prompt": "Do the thing"}
        _run_hook(HOOK_PY, "prompt", payload, tmp)
        md = tmp / "s1.md"

        # Unchanged since the prompt stamp -> block.
        r = _run_hook(HOOK_PY, "stop", {"session_id": "s1"}, tmp)
        out = json.loads(r.stdout) if r.stdout.strip() else {}
        if out.get("decision") != "block":
            print(f"    unchanged ledger should block: {r.stdout!r}")
            return False

        # Grammar-valid modification -> no block.
        import time
        time.sleep(0.05)
        md.write_text(md.read_text(encoding="utf-8") +
                       "- [>] T1 In progress @fable\n  > working on it\n", encoding="utf-8")
        r = _run_hook(HOOK_PY, "stop", {"session_id": "s1"}, tmp)
        if r.stdout.strip():
            print(f"    a valid, modified ledger should not block: {r.stdout!r}")
            return False

        # A [?] task with no `?` line -> block.
        time.sleep(0.05)
        md.write_text(md.read_text(encoding="utf-8") + "- [?] T2 Needs an answer\n",
                       encoding="utf-8")
        r = _run_hook(HOOK_PY, "stop", {"session_id": "s1"}, tmp)
        out = json.loads(r.stdout) if r.stdout.strip() else {}
        if out.get("decision") != "block":
            print(f"    [?] without a ? line should block: {r.stdout!r}")
            return False

        # stop_hook_active: true -> never blocks, even though the file is
        # still the same broken one that just triggered a block.
        r = _run_hook(HOOK_PY, "stop", {"session_id": "s1", "stop_hook_active": True}, tmp)
        if r.stdout.strip():
            print(f"    stop_hook_active must never block: {r.stdout!r}")
            return False
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # Prove the plant matters: dropping the stop_hook_active early return
    # would block on the very call above that must never block.
    hook_text = HOOK_PY.read_text(encoding="utf-8")
    old = '    if payload.get("stop_hook_active"):\n        return 0  # guard against an infinite block loop — Claude Code\'s own rule\n'
    if hook_text.count(old) != 1:
        print(f"    plant anchor text appears {hook_text.count(old)} times")
        return False
    patched_text = hook_text.replace(old, "", 1)
    tmp2 = Path(tempfile.mkdtemp(prefix="ru_ledger_stop_plant_"))
    try:
        script2 = tmp2 / "ledger_hook_plant.py"
        script2.write_text(patched_text, encoding="utf-8")
        sessions2 = tmp2 / "sessions"
        sessions2.mkdir()
        payload = {"session_id": "s1", "cwd": r"U:\Coding\Demo", "prompt": "x"}
        _run_hook(script2, "prompt", payload, sessions2)
        r = _run_hook(script2, "stop", {"session_id": "s1", "stop_hook_active": True}, sessions2)
        if not r.stdout.strip():
            print("    plant did not break the stop_hook_active guard — check proves nothing")
            return False
    finally:
        import shutil
        shutil.rmtree(tmp2, ignore_errors=True)
    return True


CHECKS = [
    ("parse: title/project/states/model/annotations/nesting", check_parse_grammar),
    ("[x] without ! downgrades to blue, [x] with ! stays green", check_downgrade_rule),
    ("category: line", check_category_line),
    ("task tags: @model/#feature/stars in ANY order, both star forms",
     check_tag_order_and_star_forms),
    ("stars stay 1–5 only", check_stars_value_range),
    ("an untagged ledger parses exactly as before", check_notag_ledger_unchanged),
    ("a mid-title #word/@word is never stripped", check_midtitle_tag_words_untouched),
    ("ledger_for_project: newest match wins, case/slash-insensitive, None otherwise",
     check_ledger_for_project),
    ("send_ledger: focused layout's project (incl. category) arrives, desktop "
     "focus never crashes",
     check_send_ledger_end_to_end),
    ("hook prompt mode: creates the file once, never overwrites", check_hook_prompt_mode),
    ("hook stop mode: blocks unchanged/malformed, never blocks stop_hook_active",
     check_hook_stop_mode),
]


def main() -> int:
    print("=== SESSION LEDGER GATE ===")
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
        print(f"SESSION LEDGER GATE FAILED — {failed} check(s).")
        return 1
    print("SESSION LEDGER GATE PASSED — the ledger parses, downgrades, is "
          "found by project, reaches the phone, and the hook keeps it honest.")
    return 0


def test_session_ledger():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
