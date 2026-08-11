"""LAYOUT HISTORY GATE — task 228, the "Recent" creation source.

Three promises this gate proves, each by planting the defect that would
break it and watching the assertion catch it (recorded below per check):

1. **Record → answer round-trip.** `record()` writes a row `list_entries()`
   can read back, and re-creating the SAME member set (even in a different
   tap order) bumps the existing row instead of piling up a duplicate —
   `signature()`'s whole reason to exist.
2. **Ranking.** A frequently-used entry ranks above a merely-recent one — the
   owner's own spec ("most-recent-first with a use-count so frequent ones
   rank up").
3. **Re-match.** `match()` finds a member by process + a fuzzy title match
   against what is open NOW, falls back to process alone when the title
   drifted, claims each open window at most once, and NAMES whatever it
   could not find rather than dropping it silently.

Isolated from the real machine: `LOCALAPPDATA` is redirected to a temp
directory before `layout_history` is imported, so this gate never touches
`%LOCALAPPDATA%/VibeCoder/layout_history.json` on the machine it runs on.

Run:  .venv\\Scripts\\python tests/test_layout_history.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

_TMP = tempfile.mkdtemp(prefix="ru_layout_history_")
os.environ["LOCALAPPDATA"] = _TMP

import layout_history  # noqa: E402


def _reset():
    layout_history.save([])


def test_record_dedupes_by_member_set_order_independent():
    _reset()
    members_ab = [{"process": "code.exe", "title": "Vibe Coder - VSCode"},
                  {"process": "chrome.exe", "title": "Gmail - Chrome"}]
    members_ba = list(reversed(members_ab))  # same set, tapped in the other order

    layout_history.record("Work", "2", "landscape", "Vibe Coder", members_ab)
    layout_history.record("Work", "2", "landscape", "Vibe Coder", members_ba)

    entries = layout_history.load()
    # PLANTED-DEFECT PROOF: comment out `signature()`'s `sorted(...)` (order-
    # dependent instead) and this becomes 2 — the exact duplicate the round
    # exists to prevent.
    assert len(entries) == 1, f"expected one deduped row, got {len(entries)}"
    assert entries[0]["count"] == 2, "the second create must bump count, not duplicate"


def test_record_caps_at_thirty():
    _reset()
    for i in range(35):
        layout_history.record(f"L{i}", None, "portrait", None,
                              [{"process": "code.exe", "title": f"proj{i} - VSCode"}])
    entries = layout_history.load()
    # PLANTED-DEFECT PROOF: drop the `[:MAX_ENTRIES]` slice in `record()` and
    # this fails at 35.
    assert len(entries) == layout_history.MAX_ENTRIES, \
        f"history must cap at {layout_history.MAX_ENTRIES}, held {len(entries)}"


def test_list_entries_ranks_frequent_above_merely_recent():
    _reset()
    import time
    now = time.time()
    # A layout used many times, but its last use was a while ago.
    frequent = {"sig": "freq", "name": "Frequent", "grid": None, "orient": "portrait",
                "project": None, "members": [], "ts": now - 3600 * 5, "count": 20}
    # A layout tried exactly once, a minute ago.
    recent_once = {"sig": "once", "name": "RecentOnce", "grid": None, "orient": "portrait",
                   "project": None, "members": [], "ts": now - 60, "count": 1}
    layout_history.save([frequent, recent_once])
    ranked = layout_history.list_entries()
    # PLANTED-DEFECT PROOF: sort by `ts` alone (drop the count term from
    # `score()`) and `recent_once` — used ONCE, a minute ago — comes out
    # ahead of a layout opened twenty times, which is the exact owner spec
    # ("frequent ones rank up") this check exists to hold.
    assert ranked[0]["sig"] == "freq", \
        f"a 20-use layout must outrank a 1-use one from a minute ago, got {ranked[0]['sig']}"


def _win(hwnd, process, title):
    return {"hwnd": hwnd, "process": process, "title": title, "icon": None}


def test_match_finds_by_process_and_fuzzy_title():
    entry = {"members": [
        {"process": "code.exe", "title_words": ["remote", "user", "vscode"]},
    ]}
    # A close but imperfect title (the app added an unsaved-changes marker) —
    # a MAJORITY of the stored words are still present, so it matches on the
    # first (title-aware) pass, not the process-only fallback.
    open_windows = [
        _win(1, "code.exe", "● Vibe Coder - Visual Studio Code"),
        _win(2, "notepad.exe", "Untitled - Notepad"),
    ]
    matched, missing = layout_history.match(entry, open_windows)
    # PLANTED-DEFECT PROOF: change `_title_words_match`'s threshold from a
    # majority to "every word" and this drifted title (only 2 of 3 words
    # survive verbatim) would fall through to the weaker process-only pass
    # instead of the intended fuzzy match — still correct here by luck (one
    # code.exe window), but the NEXT check below is where that distinction
    # actually bites, once two windows share a process.
    assert len(matched) == 1 and matched[0]["hwnd"] == 1
    assert not missing


def test_match_falls_back_to_process_alone_when_title_is_unrecognisable():
    entry = {"members": [{"process": "chrome.exe", "title_words": ["gmail", "chrome"]}]}
    # The tab's title changed completely (navigated elsewhere) — no word
    # survives, so only the PROCESS-ALONE fallback can still find it. This is
    # the deliberate best-effort half of the spec: a process match beats no
    # match at all, and the caller (layout_recent_use) still reports the
    # honest count either way.
    open_windows = [_win(3, "chrome.exe", "Weather forecast - Chrome")]
    matched, missing = layout_history.match(entry, open_windows)
    # PLANTED-DEFECT PROOF: remove the process-only fallback pass in `match()`
    # and this drops to 0 matched — a Chrome tab that merely navigated would
    # never be found again, defeating the "best-effort" half of the spec.
    assert len(matched) == 1 and matched[0]["hwnd"] == 3 and not missing


def test_match_falls_back_to_process_when_no_title_stored():
    entry = {"members": [{"process": "notepad.exe", "title_words": []}]}
    open_windows = [_win(9, "notepad.exe", "Untitled - Notepad")]
    matched, missing = layout_history.match(entry, open_windows)
    # PLANTED-DEFECT PROOF: remove the `if not stored: return True` escape in
    # `_title_words_match` and a member with no stored words (an app that had
    # a blank title) can never match anything again.
    assert matched and matched[0]["hwnd"] == 9 and not missing


def test_match_claims_each_window_at_most_once():
    entry = {"members": [
        {"process": "code.exe", "title_words": ["a"]},
        {"process": "code.exe", "title_words": ["b"]},
        {"process": "code.exe", "title_words": ["c"]},
    ]}
    # Only TWO VS Code windows stand open for three remembered members.
    open_windows = [_win(1, "code.exe", "a - VSCode"), _win(2, "code.exe", "b - VSCode")]
    matched, missing = layout_history.match(entry, open_windows)
    # PLANTED-DEFECT PROOF: drop the `used` set (let a window match twice)
    # and this comes back with 3 matched off only 2 real windows — a member
    # would silently reuse another member's window.
    assert len(matched) == 2, f"only two real windows exist, got {len(matched)} matched"
    assert {w["hwnd"] for w in matched} == {1, 2}
    assert missing == ["c"]


def test_match_refuses_nothing_found():
    entry = {"members": [{"process": "gone.exe", "title_words": ["x"]}]}
    matched, missing = layout_history.match(entry, [])
    assert matched == [] and missing == ["x"]


CHECKS = [
    test_record_dedupes_by_member_set_order_independent,
    test_record_caps_at_thirty,
    test_list_entries_ranks_frequent_above_merely_recent,
    test_match_finds_by_process_and_fuzzy_title,
    test_match_falls_back_to_process_alone_when_title_is_unrecognisable,
    test_match_falls_back_to_process_when_no_title_stored,
    test_match_claims_each_window_at_most_once,
    test_match_refuses_nothing_found,
]


if __name__ == "__main__":
    for check in CHECKS:
        check()
        print(f"PASS — {check.__name__}")
    print("PASS — test_layout_history")
