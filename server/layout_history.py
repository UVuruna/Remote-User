"""Layout HISTORY — every layout previously created, remembered across
restarts so the phone can re-create yesterday's set with one tap (owner
report 2026-08-11, task 228: "Recent" as a FOURTH creation source, beside
Tap / List / New — client/chrome.js's `openMiniRadial`).

Split out as its own module by THE STRUCTURE LAW: `LayoutRegistry` already
carries the LIVE layouts (server-lifetime, gone on restart); history is a
different responsibility — a persisted, capped, deduped LOG that outlives the
process. Stored at `%LOCALAPPDATA%/RemoteUser/layout_history.json`, the
`server/recents.py` / `user_settings` precedent — one small file per concern.

A history entry names each member the way the phone can re-find it LATER,
never by a raw HWND (which means nothing after the app that owned it closes,
let alone after a restart): `process` (exe name, lower-cased) and
`title_words` (the significant words of the title at creation time, for a
fuzzy re-match against whatever the window is called NOW — a browser tab's
title drifts, a file gets saved with unsaved-changes asterisks gone). The
layout's own `project` (the folder `LayoutRegistry.create` already resolves
via `agents.first_folder`, when there is one) rides at the ENTRY level, not
per member — the same honest-limit shape `recents.py` documents rather than
hides: a per-member project would need the same resolution run once per
window, which nothing here currently does.

`signature()` turns a member set into one dedupe key, ORDER-INDEPENDENT (his
usual pair picked in a different tap order is still the SAME layout, not a
new history row) — `record()` uses it to bump an existing entry's
`count`/`ts` instead of piling up near-duplicates every time he re-opens his
usual VSCode+Chrome pair.
"""

import json
import logging
import os
import re
import time
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_ENTRIES = 30

# Words too short or too common to mean anything on their own — "the file
# was Open" would otherwise "match" any window with the word "open" in its
# title. Deliberately short: this is a FUZZY aid, not a search engine.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "new", "untitled", "window",
}


def _path() -> Path:
    base = os.environ.get("LOCALAPPDATA", "")
    return Path(base) / "RemoteUser" / "layout_history.json"


def _title_words(title: str) -> list[str]:
    """The significant words of a title, lower-cased — what a fuzzy re-match
    compares. `re.findall` rather than `.split()`: separators (` — `, `|`,
    `:`) are exactly where a window's OWN name meets the app's own suffix,
    and splitting on whitespace alone would keep the punctuation glued on."""
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", title or "")]
    return [w for w in words if len(w) > 2 and w not in _STOPWORDS]


def member_key(process: str, title: str) -> dict:
    return {"process": (process or "").lower(), "title_words": _title_words(title)}


def signature(members: list[dict]) -> str:
    """One dedupe key for a member SET — sorted, so the same windows picked
    in a different order still collide (a layout is what it holds, not the
    order it was tapped in)."""
    parts = sorted(
        f'{m["process"]}|{"+".join(sorted(m["title_words"]))}' for m in members)
    return "\x01".join(parts)


def load() -> list[dict]:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError) as e:
        logger.info("Layout history unavailable: %s", e)
        return []


def save(entries: list[dict]) -> None:
    p = _path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    except OSError as e:
        # A history that fails to save is a missed convenience, never a
        # reason to refuse the layout that was just built.
        logger.warning("Could not save layout history: %s", e)


def record(name: str, template: str | None, orient: str, project: str | None,
           members: list[dict]) -> None:
    """Append (or bump) one history row. `members` = `[{process, title}, …]`
    in the layout's own member order — the order is kept for RE-CREATE's
    target-first rule, even though `signature()` ignores it for dedupe.

    Called from `LayoutRegistry.create()`, right where a layout is BORN — the
    one place that already knows the process, the title and the resolved
    project for every member that survived truncation. Never raises: a
    history write is best-effort, and a stack trace here must not cost him
    the layout he just asked for."""
    try:
        keyed = [member_key(m["process"], m["title"]) for m in members]
        sig = signature(keyed)
        entries = load()
        now = time.time()
        for e in entries:
            if e.get("sig") == sig:
                e["ts"], e["count"] = now, e.get("count", 1) + 1
                e["name"], e["grid"], e["orient"] = name, template, orient
                e["project"], e["members"] = project, keyed
                save(entries[:MAX_ENTRIES])
                return
        entries.insert(0, {
            "sig": sig, "name": name, "grid": template, "orient": orient,
            "project": project, "members": keyed, "ts": now, "count": 1,
        })
        save(entries[:MAX_ENTRIES])
    except Exception:  # noqa: BLE001 — a history write must never break create()
        logger.exception("Could not record layout history")


def list_entries() -> list[dict]:
    """Most-recent first, but a FREQUENTLY used entry ranks up (owner spec:
    "sorted most-recent-first with a use-count so frequent ones rank up") —
    each use is worth roughly an hour of extra recency, so a layout he opens
    daily stays near the top between uses instead of sliding down behind
    whatever he touched once five minutes ago."""
    now = time.time()

    def score(e: dict) -> float:
        age_h = max(0.0, (now - e.get("ts", 0)) / 3600.0)
        return e.get("count", 1) * 1.0 - age_h / 24.0
    return sorted(load(), key=score, reverse=True)


def find(sig: str) -> dict | None:
    for e in load():
        if e.get("sig") == sig:
            return e
    return None


def _title_words_match(stored: list[str], title: str) -> bool:
    """Best-effort: with nothing stored to compare (an app that had a blank
    title, or a process match is all we ever had), a process match alone is
    accepted — refusing every re-match for a title-less window would defeat
    the feature on exactly the apps least likely to carry a stable title."""
    if not stored:
        return True
    now = set(_title_words(title))
    hits = sum(1 for w in stored if w in now)
    return hits >= max(1, (len(stored) + 1) // 2)  # a majority of the words


def match(entry: dict, open_windows: list[dict]) -> tuple[list[dict], list[str]]:
    """Best-effort re-match against what stands on the desk RIGHT NOW — never
    a stored handle, which means nothing after the app that owned it closed
    (`recents.py`'s own rule). Two passes per member: process + a majority of
    the stored title words first, then process alone as a fallback, so a
    renamed tab still matches something rather than nothing. Each open window
    is claimed by at most one member.

    Returns `(matched, missing)` — the windows found, in entry member order,
    and the human-readable name of every member that was NOT found. Neither
    list is ever silently short: what could not be matched is named, and the
    caller builds the layout from whatever WAS found."""
    used: set[int] = set()
    matched: list[dict] = []
    missing: list[str] = []
    for m in entry.get("members", []):
        proc = m.get("process", "")
        words = m.get("title_words") or []
        best = None
        for w in open_windows:
            if w["hwnd"] in used or w["process"].lower() != proc:
                continue
            if _title_words_match(words, w["title"]):
                best = w
                break
        if best is None:
            for w in open_windows:
                if w["hwnd"] not in used and w["process"].lower() == proc:
                    best = w
                    break
        if best is not None:
            used.add(best["hwnd"])
            matched.append(best)
        else:
            missing.append(" ".join(words[:3]) or proc or "a window")
    return matched, missing
