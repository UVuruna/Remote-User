"""The desktop-only Work history page (owner-approved design, 2026-08-21) —
the whole task history across ALL projects, days and sessions, on one page
the PC's own browser can open from the tray.

"Measured, never remembered" (project law): there is no cache, no database,
no generated file. Every request re-scans `session_ledger.sessions_dir()` and
re-parses every `*.md` with `session_ledger.parse` fresh off disk, exactly the
way `ledger_api.send_ledger` re-reads the ONE ledger a phone's focused layout
names. This page instead reads ALL of them, groups them PROJECT -> DAY ->
SESSION -> task tree, and cross-links each task's `#feature` tag to that
project's own `docs/FEATURES.md` (hand-parsed — no Markdown library, the
convention is one `### Name · `slug`` heading plus its first paragraph).

Loopback only. This is a PC workshop view of the owner's own history, not a
phone-facing surface — `request.client.host` must be `127.0.0.1` or `::1`, or
the request is refused with 403. No token: the phone protocol's token exists
to gate a LAN-reachable socket, and this route is refused to everything but
the machine's own loopback interface regardless of any token.

The page is a single self-contained HTML document — inline CSS + JS, no
external resources, filtered entirely client-side (project / state / category
/ feature / minimum stars / free-text search over task titles). Every string
that came off disk is `html.escape`d before it reaches the page: a ledger is
edited by hand (and by an agent under deadline), and its text is untrusted the
same way `session_ledger.parse` already treats it as untrusted structure.
"""

import html
import logging
import re
from datetime import datetime
from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse, PlainTextResponse

import session_ledger

logger = logging.getLogger(__name__)

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})

STATE_LABELS = {
    "red": "not started", "orange": "in progress", "yellow": "waiting",
    "blue": "done (no evidence)", "green": "done",
}
STATE_ORDER = ["red", "orange", "yellow", "blue", "green"]

_FEATURE_HEADING_RE = re.compile(
    r"^###\s+(.+?)\s*(?:·|\|)\s*`([a-z0-9][a-z0-9-]*)`\s*$")
_HEADING_RE = re.compile(r"^#{1,6}\s")


def register(app) -> None:
    """`GET /history` — the whole cross-project task history, rendered fresh
    on every request. Registers itself the same way `upload_api.register` and
    `notify.register` do (THE STRUCTURE LAW — this is its own responsibility,
    never a route bolted onto `web.py`)."""

    @app.get("/history")
    async def history_page(request: Request):
        host = request.client.host if request.client is not None else None
        if host not in LOOPBACK_HOSTS:
            logger.warning("Work history refused a non-loopback request from %r", host)
            return PlainTextResponse(
                "Work history is only available from this PC.", status_code=403)
        return HTMLResponse(render_page())

    return None


# ═══════════════════════════ SCAN + GROUP ═══════════════════════════

def _project_basename(project: str) -> str:
    return Path(str(project).strip()).name if project else ""


def _id_slug(text: str) -> str:
    """A basename or a feature slug, made safe as one HTML id/href fragment
    (lowercased, non `[a-z0-9]` runs collapsed to one `-`). Never empty — an
    unnamed project still needs an id every anchor pointing at it can share."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")
    return slug or "unknown"


def _day_key(mtime: float) -> str:
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")


def _day_label(mtime: float) -> str:
    return datetime.fromtimestamp(mtime).strftime("%A, %B %d, %Y")


def _scan_sessions() -> list[dict]:
    """Every `*.md` in the sessions directory, parsed and stamped with its own
    file mtime — skipping a file with no title AND no tasks (an empty stub the
    hook created and the agent never touched). Never raises: an unreadable
    file is skipped, exactly like `session_ledger.ledger_for_project` already
    treats one."""
    directory = session_ledger.sessions_dir()
    if not directory.is_dir():
        return []
    out = []
    for path in directory.glob("*.md"):
        try:
            text = path.read_text(encoding="utf-8")
            mtime = path.stat().st_mtime
        except OSError:
            continue
        parsed = session_ledger.parse(text)
        if not parsed["tasks"] and not parsed["title"]:
            continue
        out.append({"session_id": path.stem, "mtime": mtime, **parsed})
    return out


def _group_by_project(sessions: list[dict]) -> dict:
    """`{project_key: {"display": str, "path": str, "days": {day_key: {...}}}}`
    — one entry per casefolded project BASENAME, the same folder-name match
    `session_ledger._normalized` uses (a ledger's `project:` line is an
    absolute cwd; two projects sharing a folder name are one group here, the
    same honest limit that function already carries). `path` is the newest
    session's own `project:` text — what `_read_features` tries to open."""
    projects: dict = {}
    for sess in sessions:
        basename = _project_basename(sess["project"])
        key = _id_slug(basename) if basename else ""
        group = projects.setdefault(
            key, {"display": basename or "(no project)", "path": "", "days": {}})
        if sess["mtime"] >= _latest_mtime(group):
            group["path"] = sess["project"]
        day_key = _day_key(sess["mtime"])
        group["days"].setdefault(day_key, {"label": _day_label(sess["mtime"]),
                                            "sessions": []})["sessions"].append(sess)
    return projects


def _latest_mtime(group: dict) -> float:
    best = -1.0
    for day in group["days"].values():
        for sess in day["sessions"]:
            best = max(best, sess["mtime"])
    return best


# ═══════════════════════════ FEATURES.md (hand-parsed) ═══════════════════════════

def _read_features(project_path: str) -> list[dict]:
    """`[{"name", "slug", "para"}, ...]` in file order, or `[]` when the
    project has no `docs/FEATURES.md` — not an error, just nothing to cross-
    link. Convention: `### <Name> · `slug`` followed by its first paragraph
    (contiguous non-blank lines up to the next blank line or heading). No
    Markdown library — this is the one heading shape the whole file promises."""
    if not project_path:
        return []
    fpath = Path(project_path) / "docs" / "FEATURES.md"
    try:
        text = fpath.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = text.splitlines()
    features = []
    i = 0
    while i < len(lines):
        m = _FEATURE_HEADING_RE.match(lines[i])
        if not m:
            i += 1
            continue
        name, slug = m.group(1).strip(), m.group(2)
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        para_lines = []
        while i < len(lines) and lines[i].strip() and not _HEADING_RE.match(lines[i]):
            para_lines.append(lines[i].strip())
            i += 1
        features.append({"name": name, "slug": slug, "para": " ".join(para_lines)})
    return features


# ═══════════════════════════ TASK TREE RENDERING ═══════════════════════════

def _render_tasks(tasks: list[dict], project_key: str, session_id: str,
                   category: str, backlinks: dict, counter: list[int]) -> str:
    parts = []
    for task in tasks:
        counter[0] += 1
        anchor = f"t-{session_id}-{counter[0]}"
        state = task["state"]
        title = html.escape(task["title"] or "(untitled task)")
        tid = html.escape(task["id"])
        feature_href = ""
        if task["feature"]:
            fslug = _id_slug(task["feature"])
            feature_href = (f'<a class="chip chip-feature" '
                             f'href="#f-{project_key}-{fslug}">#{html.escape(task["feature"])}</a>')
            backlinks.setdefault((project_key, fslug), []).append(
                (title, anchor))
        model_chip = (f'<span class="chip chip-model">@{html.escape(task["model"])}</span>'
                       if task["model"] else "")
        stars_chip = (f'<span class="stars" title="{task["stars"]} of 5">'
                       f'{"★" * task["stars"]}</span>' if task["stars"] else "")
        meta_parts = []
        if task["desc"]:
            meta_parts.append(f'<div class="task-desc">{html.escape(task["desc"])}</div>')
        if task["question"]:
            meta_parts.append(f'<div class="task-question">? {html.escape(task["question"])}</div>')
        if task["evidence"]:
            meta_parts.append(f'<div class="task-evidence">! {html.escape(task["evidence"])}</div>')
        meta_html = f'<div class="task-meta">{"".join(meta_parts)}</div>' if meta_parts else ""
        children_html = (_render_tasks(task["children"], project_key, session_id,
                                        category, backlinks, counter)
                          if task["children"] else "")
        children_wrap = (f'<div class="task-children">{children_html}</div>'
                          if children_html else "")
        parts.append(
            f'<div class="task">'
            f'<div class="task-row" id="{anchor}" data-project="{project_key}" '
            f'data-state="{state}" data-category="{html.escape(category)}" '
            f'data-feature="{project_key}::{_id_slug(task["feature"]) if task["feature"] else ""}" '
            f'data-stars="{task["stars"]}">'
            f'<span class="dot dot-{state}" title="{STATE_LABELS[state]}"></span>'
            f'{f"<span class=\"task-id\">{tid}</span>" if tid else ""}'
            f'<span class="task-title">{title}</span>'
            f'{model_chip}{stars_chip}{feature_href}'
            f'</div>{meta_html}{children_wrap}</div>')
    return "".join(parts)


def _render_features_block(project_key: str, project_path: str,
                            backlinks: dict) -> str:
    features = _read_features(project_path)
    if not features:
        return ""
    rows = []
    for feat in features:
        fslug = _id_slug(feat["slug"])
        anchor = f"f-{project_key}-{fslug}"
        back = backlinks.get((project_key, fslug), [])
        back_html = ""
        if back:
            items = "".join(
                f'<li><a href="#{a}">{t}</a></li>' for t, a in back)
            back_html = f'<ul class="feature-backlinks">{items}</ul>'
        else:
            back_html = '<p class="feature-empty">No tasks tagged yet.</p>'
        rows.append(
            f'<div class="feature" id="{anchor}">'
            f'<h4>{html.escape(feat["name"])} '
            f'<code>{html.escape(feat["slug"])}</code></h4>'
            f'<p class="feature-para">{html.escape(feat["para"])}</p>'
            f'{back_html}</div>')
    return f'<div class="features"><h3>Features</h3>{"".join(rows)}</div>'


# ═══════════════════════════ PAGE ASSEMBLY ═══════════════════════════

def _render_project(project_key: str, group: dict, backlinks: dict) -> tuple[str, dict]:
    """Returns (html, filter_facets) — facets collected while walking this
    project's tasks so the filter bar can be built from what the page
    actually contains, never a guessed catalogue."""
    facets = {"categories": set(), "features": {}}  # features: {key: label}
    day_htmls = []
    for day_key in sorted(group["days"], reverse=True):
        day = group["days"][day_key]
        sessions = sorted(day["sessions"], key=lambda s: s["mtime"], reverse=True)
        session_htmls = []
        for sess in sessions:
            category = sess["category"]
            if category:
                facets["categories"].add(category)
            counter = [0]
            tasks_html = _render_tasks(sess["tasks"], project_key, sess["session_id"],
                                        category, backlinks, counter)
            cat_chip = (f'<span class="chip chip-category">{html.escape(category)}</span>'
                        if category else "")
            title = html.escape(sess["title"] or "(untitled session)")
            session_htmls.append(
                f'<div class="session" data-category="{html.escape(category)}">'
                f'<div class="session-head"><span class="session-title">{title}</span>'
                f'{cat_chip}<span class="session-id">{html.escape(sess["session_id"])}</span>'
                f'</div><div class="tasks">{tasks_html}</div></div>')
        day_htmls.append(
            f'<div class="day"><h3>{html.escape(day["label"])}</h3>'
            f'{"".join(session_htmls)}</div>')
    # feature facets are collected once the whole project's tasks were walked
    # (backlinks now holds every (project, slug) pair this project produced).
    for (pkey, fslug), entries in backlinks.items():
        if pkey == project_key and entries:
            facets["features"][f"{project_key}::{fslug}"] = fslug
    features_html = _render_features_block(project_key, group["path"], backlinks)
    for feat in _read_features(group["path"]):
        facets["features"][f"{project_key}::{_id_slug(feat['slug'])}"] = feat["name"]
    project_html = (
        f'<section class="project" data-project="{project_key}">'
        f'<h2>{html.escape(group["display"])}</h2>'
        f'{features_html}{"".join(day_htmls)}</section>')
    return project_html, facets


def render_page() -> str:
    sessions = _scan_sessions()
    projects = _group_by_project(sessions)
    backlinks: dict = {}
    project_order = sorted(projects, key=lambda k: projects[k]["display"].casefold())
    project_htmls = []
    all_facets = {"projects": {}, "categories": set(), "features": {}}
    for key in project_order:
        group = projects[key]
        html_out, facets = _render_project(key, group, backlinks)
        project_htmls.append(html_out)
        all_facets["projects"][key] = group["display"]
        all_facets["categories"] |= facets["categories"]
        all_facets["features"].update(facets["features"])

    body = "".join(project_htmls) if project_htmls else (
        '<p class="empty">No session ledgers found yet.</p>')
    filter_bar = _render_filter_bar(all_facets)
    return _PAGE_TEMPLATE.format(filter_bar=filter_bar, body=body)


def _render_filter_bar(facets: dict) -> str:
    project_opts = "".join(
        f'<option value="{key}">{html.escape(name)}</option>'
        for key, name in sorted(facets["projects"].items(), key=lambda kv: kv[1].casefold()))
    state_opts = "".join(
        f'<option value="{s}">{STATE_LABELS[s]}</option>' for s in STATE_ORDER)
    category_opts = "".join(
        f'<option value="{html.escape(c)}">{html.escape(c)}</option>'
        for c in sorted(facets["categories"], key=str.casefold))
    feature_opts = "".join(
        f'<option value="{key}">{html.escape(name)}</option>'
        for key, name in sorted(facets["features"].items(), key=lambda kv: kv[1].casefold()))
    return f"""
<div class="filters">
  <input id="f-search" type="search" placeholder="Search task titles…" aria-label="Search task titles">
  <select id="f-project" aria-label="Filter by project"><option value="">All projects</option>{project_opts}</select>
  <select id="f-state" aria-label="Filter by state"><option value="">All states</option>{state_opts}</select>
  <select id="f-category" aria-label="Filter by category"><option value="">All categories</option>{category_opts}</select>
  <select id="f-feature" aria-label="Filter by feature"><option value="">All features</option>{feature_opts}</select>
  <select id="f-stars" aria-label="Minimum stars">
    <option value="0">Any complexity</option>
    <option value="1">★ 1+</option><option value="2">★ 2+</option>
    <option value="3">★ 3+</option><option value="4">★ 4+</option>
    <option value="5">★ 5</option>
  </select>
</div>"""


# ═══════════════════════════ THE SELF-CONTAINED PAGE ═══════════════════════════

_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vibe Coder — Work history</title>
<style>
:root {{
  --bg: #f4f5f7; --card: #ffffff; --border: #d9dce2; --ink: #1c2230;
  --ink-muted: #5b6474; --chip-bg: #eef1f6; --link: #2563eb;
  --state-red: #dc2626; --state-orange: #ea9a1f; --state-yellow: #d9b400;
  --state-blue: #2563eb; --state-green: #16a34a; --dot-border: rgba(0,0,0,.25);
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #14171f; --card: #1c2029; --border: #2c313d; --ink: #e6e9ef;
    --ink-muted: #9aa3b2; --chip-bg: #262b36; --link: #7fb0ff;
    --state-red: #ff6b6b; --state-orange: #ffb454; --state-yellow: #f5df6e;
    --state-blue: #7fb0ff; --state-green: #6fdc8c; --dot-border: rgba(255,255,255,.35);
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; padding: 24px; background: var(--bg); color: var(--ink);
  font: 15px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif;
}}
h1 {{ font-size: 22px; margin: 0 0 4px; }}
a {{ color: var(--link); }}
.sub {{ color: var(--ink-muted); margin: 0 0 20px; }}
.filters {{
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 20px;
  position: sticky; top: 0; background: var(--bg); padding: 8px 0; z-index: 5;
}}
.filters input, .filters select {{
  background: var(--card); color: var(--ink); border: 1px solid var(--border);
  border-radius: 6px; padding: 6px 8px; font-size: 14px;
}}
#f-search {{ flex: 1 1 220px; min-width: 160px; }}
.project {{
  background: var(--card); border: 1px solid var(--border); border-radius: 10px;
  padding: 16px 18px; margin-bottom: 18px; overflow-x: auto;
}}
.project h2 {{ margin: 0 0 10px; font-size: 19px; }}
.features {{ border: 1px dashed var(--border); border-radius: 8px; padding: 10px 12px; margin-bottom: 16px; }}
.features h3 {{ margin: 0 0 8px; font-size: 14px; text-transform: uppercase; color: var(--ink-muted); letter-spacing: .04em; }}
.feature {{ margin-bottom: 10px; }}
.feature h4 {{ margin: 0 0 2px; font-size: 14.5px; }}
.feature code {{ font-size: 12px; color: var(--ink-muted); font-weight: normal; }}
.feature-para {{ margin: 2px 0 4px; color: var(--ink-muted); }}
.feature-backlinks {{ margin: 0; padding-left: 18px; font-size: 13px; }}
.feature-empty {{ margin: 0; font-size: 13px; color: var(--ink-muted); font-style: italic; }}
.day h3 {{ font-size: 13px; color: var(--ink-muted); margin: 14px 0 6px; text-transform: uppercase; letter-spacing: .04em; }}
.session {{ border-left: 3px solid var(--border); padding-left: 10px; margin-bottom: 12px; }}
.session-head {{ display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; }}
.session-title {{ font-weight: 600; }}
.session-id {{ font-size: 11.5px; color: var(--ink-muted); font-family: ui-monospace, monospace; }}
.tasks {{ min-width: max-content; }}
.task-row {{ display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding: 3px 0; white-space: nowrap; }}
.task-children {{ margin-left: 20px; }}
.dot {{ width: 10px; height: 10px; border-radius: 50%; border: 1px solid var(--dot-border); flex: 0 0 auto; }}
.dot-red {{ background: var(--state-red); }}
.dot-orange {{ background: var(--state-orange); }}
.dot-yellow {{ background: var(--state-yellow); }}
.dot-blue {{ background: var(--state-blue); }}
.dot-green {{ background: var(--state-green); }}
.task-id {{ font-family: ui-monospace, monospace; font-size: 12px; color: var(--ink-muted); }}
.task-title {{ white-space: normal; }}
.chip {{
  font-size: 12px; background: var(--chip-bg); border-radius: 5px; padding: 1px 6px;
  color: var(--ink-muted); text-decoration: none; white-space: nowrap;
}}
.chip-feature {{ color: var(--link); }}
.stars {{ color: var(--state-yellow); font-size: 12px; letter-spacing: 1px; }}
.task-meta {{ margin: 0 0 4px 16px; color: var(--ink-muted); font-size: 13px; }}
.task-desc {{ white-space: pre-wrap; }}
.task-question {{ color: var(--state-yellow); }}
.task-evidence {{ color: var(--state-green); }}
.empty {{ color: var(--ink-muted); font-style: italic; }}
.hidden {{ display: none !important; }}
</style>
</head>
<body>
<h1>Work history</h1>
<p class="sub">Every session ledger, across every project — read fresh off disk on every load.</p>
{filter_bar}
<main>{body}</main>
<script>
(function() {{
  var search = document.getElementById('f-search');
  var project = document.getElementById('f-project');
  var state = document.getElementById('f-state');
  var category = document.getElementById('f-category');
  var feature = document.getElementById('f-feature');
  var stars = document.getElementById('f-stars');

  function apply() {{
    var q = search.value.trim().toLowerCase();
    var pv = project.value, sv = state.value, cv = category.value;
    var fv = feature.value, minStars = parseInt(stars.value, 10) || 0;
    var rows = document.querySelectorAll('.task-row');
    rows.forEach(function(row) {{
      var titleEl = row.querySelector('.task-title');
      var title = titleEl ? titleEl.textContent.toLowerCase() : '';
      var ok = true;
      if (q && title.indexOf(q) === -1) ok = false;
      if (ok && pv && row.dataset.project !== pv) ok = false;
      if (ok && sv && row.dataset.state !== sv) ok = false;
      if (ok && cv && row.dataset.category !== cv) ok = false;
      if (ok && fv && row.dataset.feature !== fv) ok = false;
      if (ok && minStars && parseInt(row.dataset.stars, 10) < minStars) ok = false;
      row.classList.toggle('hidden', !ok);
    }});
    document.querySelectorAll('.session').forEach(function(sess) {{
      var any = sess.querySelectorAll('.task-row:not(.hidden)').length > 0;
      sess.classList.toggle('hidden', !any);
    }});
    document.querySelectorAll('.day').forEach(function(day) {{
      var any = day.querySelectorAll('.session:not(.hidden)').length > 0;
      day.classList.toggle('hidden', !any);
    }});
    document.querySelectorAll('.project').forEach(function(proj) {{
      var any = proj.querySelectorAll('.day:not(.hidden)').length > 0;
      proj.classList.toggle('hidden', !any);
    }});
  }}

  [search, project, state, category, feature, stars].forEach(function(el) {{
    el.addEventListener('input', apply);
    el.addEventListener('change', apply);
  }});
}})();
</script>
</body>
</html>
"""
