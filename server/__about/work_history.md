# Work History

**Script:** [Work History (script)](../work_history.py)

## Purpose

The desktop "Work history" page (owner-approved design, 2026-08-21) — the
whole task history across ALL projects, days and sessions, on one page opened
from the tray. Source of truth stays the session ledger Markdown files
[Session Ledger](session_ledger.md) already parses: this module scans EVERY
`*.md` in `session_ledger.sessions_dir()`, not just the newest match for one
project, and re-reads all of them fresh on every request ("measured, never
remembered" — no cache, no database, no generated file).

**Loopback only, no token.** `GET /history` refuses any request whose
`request.client.host` is not `127.0.0.1` or `::1`, with 403. This is a PC
workshop view of the owner's own history — never a phone-facing surface — so
it is gated by the loopback interface itself rather than by the phone
protocol's token, which exists to protect a LAN-reachable socket this route
deliberately is not.

**Grouping.** PROJECT (the casefolded basename of each ledger's `project:`
line — the same folder-name match `session_ledger._normalized` already uses,
so two projects sharing a folder name are one group here too) → DAY (the
file's own mtime date, newest first) → SESSION (newest mtime first) → the
parsed task tree, recursively rendered with its state dot, id, `@model` chip,
`★` stars, `#feature` tag and its `>`/`?`/`!` lines shown always-visible but
visually secondary. A file with no title AND no tasks is skipped — an empty
stub the ledger hook created and nobody ever touched.

**FEATURES.md cross-links.** For each project, `docs/FEATURES.md` (read off
the newest session's own `project:` path) is hand-parsed for the one heading
shape it promises: `### <Name> · `slug`` followed by its first paragraph — no
Markdown library. Every task's `#slug` tag links to that feature's anchor
(`f-<project-basename>-<slug>`), and the feature's own block lists backlinks
to every task that carries it (`t-<session_id>-<n>`, its own anchor). A
project with no `docs/FEATURES.md` simply gets no Features block — not an
error.

**One self-contained page.** Inline CSS + JS, no external resources, no
framework — filtered entirely client-side (free-text search over task titles,
project, state, category, feature, minimum stars). Filtering hides
non-matching task rows and any session/day/project group left empty. Every
string read off disk is `html.escape`d — a ledger is untrusted text the same
way [Session Ledger](session_ledger.md) already treats it.

## Connections

### Uses
- [Session Ledger](session_ledger.md) — `sessions_dir()`, `parse()`; this
  module is the one caller that walks EVERY file instead of the newest match
  for one project

### Used by
- [Web Layer](web.md) — `work_history.register(app)`, beside
  `upload_api.register`
- [Main Window](../gui/__about/main_window.md) — the tray's "Work history"
  action opens `http://127.0.0.1:{port}/history` in the system browser
- [Tests (folder)](../../tests/___tests.md) — `test_work_history.py`

## Functions
- `register(app) -> None`: adds `GET /history`. The handler checks
  `request.client.host` against `LOOPBACK_HOSTS` before doing anything else —
  a non-loopback request never reaches the scan.
- `render_page() -> str`: the whole page, pure and disk-reading — scans,
  groups, renders, and returns one HTML string. No request object involved,
  so it is what the test gate calls directly.
- `_scan_sessions()`: every `*.md`, parsed, stamped with its own mtime,
  skipping an empty stub.
- `_group_by_project(sessions)`: the PROJECT → DAY → SESSION grouping
  described above.
- `_read_features(project_path)`: the hand-parsed `docs/FEATURES.md` reader —
  `[]` when the file or the project path is missing.
- `_render_tasks(...)`: the recursive task-tree renderer; assigns each task's
  own anchor and records `(project_key, slug) -> [(title, anchor), ...]`
  backlinks as it walks.
- `_render_features_block(...)`: the per-project Features block, built from
  the backlinks table gathered while rendering that project's sessions.
- `_render_filter_bar(facets)`: the `<select>` options, built from what the
  page actually contains rather than a guessed catalogue.

## Honest limits
- The project grouping shares `session_ledger`'s own honest limit: matching by
  casefolded folder BASENAME (not a live process check) means two unrelated
  projects that happen to share a folder name are shown as one group.
- `_read_features` reads the NEWEST session's `project:` path for a group — a
  project whose absolute path changed mid-history (moved on disk) may show
  `docs/FEATURES.md` from wherever the newest ledger says it lives now, not
  from whichever path an older session recorded.
