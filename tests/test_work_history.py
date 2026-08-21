"""WORK HISTORY GATE — the desktop "Work history" page (`server/work_history.py`),
the whole task history across ALL projects, days and sessions, re-read fresh
off disk on every request.

`session_ledger.sessions_dir()` reads `config.USER_DIR / "sessions"` directly
and does NOT honor the `VIBECODER_SESSIONS_DIR` environment variable — only
`setup/ledger_hook.py`'s own standalone `sessions_dir()` does that. So this
gate stages a temp directory the same way `tests/test_session_ledger.py`
already does: monkeypatching `session_ledger.sessions_dir` in memory, never
touching the real user directory and never changing server code for
testability.

Every check is proven against a PLANTED defect (the `_load_patched` technique
from `tests/test_session_ledger.py`): the real module's source text is
patched in memory and reloaded under a scratch name, so the plant is shown to
break the very assertion the check makes, then discarded.

Run:  python tests/test_work_history.py
"""

import asyncio
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SERVER = PROJECT / "server"
sys.path.insert(0, str(SERVER))

import session_ledger  # noqa: E402
import work_history  # noqa: E402
from fastapi import FastAPI  # noqa: E402

WORK_HISTORY_PY = SERVER / "work_history.py"


# ═══════════════════════════ module patch harness (test_session_ledger.py's own) ═══════════════════════════
def _load_patched(path: Path, replacements: list[tuple[str, str]], mod_name: str):
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


def _write(path: Path, text: str, mtime: float) -> None:
    path.write_text(text, encoding="utf-8")
    os.utime(path, (mtime, mtime))


def _stage(tmp: Path) -> tuple[Path, Path]:
    """Two projects x two days x several sessions, the NEW grammar (category,
    #feature, stars). Returns (proj_a, proj_b) — the absolute project paths
    written into each ledger's `project:` line."""
    proj_a = tmp / "DemoProject"
    proj_b = tmp / "OtherProject"
    (proj_a / "docs").mkdir(parents=True)
    (proj_a / "docs" / "FEATURES.md").write_text(
        "### Dictation Card · `dictation`\n\n"
        "The card that lets you preview and pick a voice per language.\n\n"
        "### Layout List · `layout-list`\n\n"
        "Rows for every layout the phone can pick.\n",
        encoding="utf-8")

    # Day 1 (older) — DemoProject, one session, a task tagged #dictation.
    _write(tmp / "sess-old.md",
           f"# Old Session\nproject: {proj_a}\ncategory: FEATURE\n"
           "- [x] T1 Ship dictation preview @sonnet #dictation *3\n"
           "  ! tests/test_x.py 4/4\n",
           mtime=1_700_000_000)

    # Day 2 (newer) — DemoProject, two sessions the SAME day, B newer than A.
    _write(tmp / "sess-newA.md",
           f"# Newer Session A\nproject: {proj_a}\ncategory: BUGFIX\n"
           "- [ ] T1 Fix the thing @fable #layout-list\n",
           mtime=1_800_000_000)
    _write(tmp / "sess-newB.md",
           f"# Newer Session B\nproject: {proj_a}\n"
           "- [>] T1 Working on it @opus ***\n"
           "  > a description line\n"
           "  - [?] T1a A nested question @fable\n"
           "    ? does this look right\n",
           mtime=1_800_000_100)

    # OtherProject — the escaping case, an untagged feature slug ("#nothing"),
    # five stars, no docs/FEATURES.md at all (not an error — no block).
    _write(tmp / "sess-other.md",
           f"# Other title\nproject: {proj_b}\ncategory: GUI\n"
           "- [x] T1 <script>alert(1)</script> @sonnet #nothing *5\n"
           "  ! it works\n",
           mtime=1_750_000_000)

    # A file with no title AND no tasks — must be skipped entirely.
    _write(tmp / "sess-empty.md", f"project: {proj_a}\n", mtime=1_760_000_000)
    return proj_a, proj_b


class _StagedDir:
    """Context manager: builds the fixture in a temp dir, points
    `session_ledger.sessions_dir` at it, restores on exit."""

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="ru_workhist_"))
        self._saved = session_ledger.sessions_dir
        _stage(self.tmp)
        session_ledger.sessions_dir = lambda: self.tmp
        return self.tmp

    def __exit__(self, *exc):
        session_ledger.sessions_dir = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)


# ═══════════════════════════ THE CHECKS ═══════════════════════════

def check_grouping_and_order() -> bool:
    with _StagedDir():
        page = work_history.render_page()

    if "sess-empty" in page or "sess-empty.md" in page:
        print("    a file with no title and no tasks should be skipped entirely")
        return False

    # Projects sorted alphabetically by display name: DemoProject < OtherProject.
    i_demo, i_other = page.find("DemoProject"), page.find("OtherProject")
    if i_demo == -1 or i_other == -1 or i_demo > i_other:
        print(f"    project order wrong: DemoProject@{i_demo}, OtherProject@{i_other}")
        return False

    # Newest DAY first: "Newer Session" (day 2) must appear before "Old Session" (day 1).
    i_newer, i_old = page.find("Newer Session"), page.find("Old Session")
    if i_newer == -1 or i_old == -1 or i_newer > i_old:
        print(f"    day order wrong: newer@{i_newer}, old@{i_old}")
        return False

    # Newest SESSION first within the same day: B (mtime+100) before A.
    i_b, i_a = page.find("Newer Session B"), page.find("Newer Session A")
    if i_b == -1 or i_a == -1 or i_b > i_a:
        print(f"    session order wrong within the day: B@{i_b}, A@{i_a}")
        return False

    if "A nested question" not in page or "does this look right" not in page:
        print("    the nested [?] child task and its question line did not render")
        return False

    # Plant: sorting the DAYS ascending instead of descending must break it.
    patched = _load_patched(
        WORK_HISTORY_PY,
        [('    for day_key in sorted(group["days"], reverse=True):',
          '    for day_key in sorted(group["days"], reverse=False):')],
        "work_history_plant_day_order")
    with _StagedDir():
        broken = patched.render_page()
    bi_newer, bi_old = broken.find("Newer Session"), broken.find("Old Session")
    if not (bi_newer != -1 and bi_old != -1 and bi_newer > bi_old):
        print("    plant did not reverse the day order — check proves nothing")
        return False
    return True


def check_loopback_gate() -> bool:
    class FakeClient:
        def __init__(self, host):
            self.host = host

    class FakeRequest:
        def __init__(self, host):
            self.client = FakeClient(host) if host is not None else None

    def _endpoint(mod):
        app = FastAPI()
        mod.register(app)
        for route in app.router.routes:
            if getattr(route, "path", None) == "/history":
                return route.endpoint
        raise AssertionError("GET /history was never registered")

    endpoint = _endpoint(work_history)
    with _StagedDir():
        ok1 = asyncio.run(endpoint(FakeRequest("127.0.0.1")))
        ok2 = asyncio.run(endpoint(FakeRequest("::1")))
        refused = asyncio.run(endpoint(FakeRequest("8.8.8.8")))
        no_client = asyncio.run(endpoint(FakeRequest(None)))

    if ok1.status_code != 200 or b"Work history" not in ok1.body:
        print(f"    127.0.0.1 should render the page, got {ok1.status_code}")
        return False
    if ok2.status_code != 200:
        print(f"    ::1 should render the page, got {ok2.status_code}")
        return False
    if refused.status_code != 403:
        print(f"    a non-loopback host should get 403, got {refused.status_code}")
        return False
    if no_client.status_code != 403:
        print(f"    a request with no client at all should get 403, got {no_client.status_code}")
        return False

    # Plant: disabling the loopback check must let the LAN/phone through.
    patched = _load_patched(
        WORK_HISTORY_PY,
        [("        if host not in LOOPBACK_HOSTS:",
          "        if False:")],
        "work_history_plant_loopback")
    broken_endpoint = _endpoint(patched)
    with _StagedDir():
        broken = asyncio.run(broken_endpoint(FakeRequest("8.8.8.8")))
    if broken.status_code == 403:
        print("    plant did not disable the loopback gate — check proves nothing")
        return False
    return True


def check_feature_anchors_and_backlinks() -> bool:
    with _StagedDir():
        page = work_history.render_page()

    if 'id="f-demoproject-dictation"' not in page:
        print("    the Dictation Card feature anchor is missing")
        return False
    if "The card that lets you preview and pick a voice per language." not in page:
        print("    the feature's first paragraph did not render")
        return False
    if 'href="#f-demoproject-dictation"' not in page:
        print("    the task's #dictation tag does not link to the feature anchor")
        return False
    # The backlink: "Ship dictation preview" (tagged #dictation) must link
    # back to ITS OWN task anchor from under the feature block.
    if 'Ship dictation preview</a>' not in page:
        print("    no backlink to the task that tagged #dictation")
        return False
    # "Fix the thing" tagged #layout-list must backlink under Layout List.
    if 'Fix the thing</a>' not in page:
        print("    no backlink to the task that tagged #layout-list")
        return False
    # A project with no docs/FEATURES.md (OtherProject) gets no Features block
    # at all — not an error, simply absent.
    other_start = page.find('data-project="otherproject"')
    if other_start != -1:
        other_chunk = page[other_start:other_start + 4000]
        if 'class="features"' in other_chunk.split("</section>")[0]:
            print("    OtherProject has no FEATURES.md yet got a Features block")
            return False

    # Plant: breaking the backlink lookup must drop the backlinks.
    patched = _load_patched(
        WORK_HISTORY_PY,
        [('        back = backlinks.get((project_key, fslug), [])',
          '        back = []')],
        "work_history_plant_backlinks")
    with _StagedDir():
        broken = patched.render_page()
    if 'Ship dictation preview</a>' in broken:
        print("    plant did not drop the backlinks — check proves nothing")
        return False
    if "No tasks tagged yet." not in broken:
        print("    plant should leave every feature reporting no tasks tagged")
        return False
    return True


def check_escaping() -> bool:
    with _StagedDir():
        page = work_history.render_page()

    if "<script>alert(1)</script>" in page:
        print("    an unescaped <script> task title reached the page")
        return False
    if "&lt;script&gt;alert(1)&lt;/script&gt;" not in page:
        print("    the escaped task title did not render at all")
        return False

    # Plant: dropping html.escape on the task title must let it back in raw.
    patched = _load_patched(
        WORK_HISTORY_PY,
        [('        title = html.escape(task["title"] or "(untitled task)")',
          '        title = task["title"] or "(untitled task)"')],
        "work_history_plant_escape")
    with _StagedDir():
        broken = patched.render_page()
    if "<script>alert(1)</script>" not in broken:
        print("    plant did not let the raw <script> tag back in — check proves nothing")
        return False
    return True


def check_tag_rendering() -> bool:
    with _StagedDir():
        page = work_history.render_page()

    if '<span class="chip chip-model">@sonnet</span>' not in page:
        print("    the @sonnet model chip did not render")
        return False
    if '<span class="chip chip-model">@fable</span>' not in page:
        print("    the @fable model chip did not render")
        return False
    if '<span class="stars" title="3 of 5">★★★</span>' not in page:
        print("    the *3 stars tag (Ship dictation preview) did not render as three stars")
        return False
    if '<span class="stars" title="5 of 5">★★★★★</span>' not in page:
        print("    the *5 stars tag did not render as five stars")
        return False
    if '<span class="stars" title="1 of 5">' in page or '<span class="stars" title="0 of 5">' in page:
        print("    an untagged (0-star) task rendered a stars chip")
        return False

    # Plant: disabling the stars condition must drop every stars chip.
    patched = _load_patched(
        WORK_HISTORY_PY,
        [('        stars_chip = (f\'<span class="stars" title="{task["stars"]} of 5">\'\n'
          '                       f\'{"★" * task["stars"]}</span>\' if task["stars"] else "")',
          '        stars_chip = ""')],
        "work_history_plant_stars")
    with _StagedDir():
        broken = patched.render_page()
    if 'class="stars"' in broken:
        print("    plant did not remove the stars chips — check proves nothing")
        return False
    return True


CHECKS = [
    ("grouping: project -> day -> session, newest first, empty ledgers skipped",
     check_grouping_and_order),
    ("loopback gate: 127.0.0.1/::1 render, any other host (or no client) gets 403",
     check_loopback_gate),
    ("feature anchors + backlinks: #slug links to FEATURES.md, tasks link back",
     check_feature_anchors_and_backlinks),
    ("escaping: a <script> task title never reaches the page unescaped",
     check_escaping),
    ("tag rendering: @model chips and ***/*N star counts",
     check_tag_rendering),
]


def main() -> int:
    print("=== WORK HISTORY GATE ===")
    failed = 0
    for name, fn in CHECKS:
        try:
            ok = fn()
        except Exception as e:               # a crashing check is a failing one
            ok = False
            print(f"  ERROR {name}: {e!r}")
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        failed += 0 if ok else 1
    print()
    if failed:
        print(f"WORK HISTORY GATE FAILED — {failed} check(s).")
        return 1
    print("WORK HISTORY GATE PASSED — grouped, gated to loopback, cross-linked, "
          "escaped, and tagged correctly.")
    return 0


def test_work_history():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
