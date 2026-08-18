"""Which layout is showing the conversation an agent just finished in.

Split out of `notify.py` on 2026-08-18 (THE STRUCTURE LAW). One
responsibility: turning "this agent's project, and the conversation title it
was working under" into the layout index the phone may jump to — and nothing
else. `notify.py` owns the notice; this module owns WHERE it happened.

Nothing is INFERRED here. The finishing agent sends its own `cwd`
(setup/agent_hook.py -> agent_project), and every layout can be asked which
project its windows really belong to, live (Layout.project). Matching those
two is the whole feature; there is no name-guessing, no title heuristic, and
no stored answer that could go stale between the notice and the tap.
"""

import logging
import pathlib
import re

import window_manager as wm  # the same live-title read `layout_state` already
                              # uses (layout_registry.py's member_titles) — no
                              # second copy of how a member's title is read

logger = logging.getLogger(__name__)

_layouts = None      # the live LayoutRegistry, handed over by set_layouts()


def set_layouts(layouts) -> None:
    """The live registry, handed over by `notify.register()`. None — a server
    built without layouts — simply means every notice carries no jump, and the
    feature is absent rather than wrong."""
    global _layouts
    _layouts = layouts


# --- Matching a CONVERSATION TITLE to the window that carries it -----------
# Owner ruling 2026-08-13: notifications must choose the layout the
# conversation was really created in. When several windows of ONE project are
# spread across layouts (the exact case a project-folder match cannot tell
# apart), the tap must land in the layout that holds the CONVERSATION that
# finished, not merely a project it shares. A VS Code window running Claude
# Code is titled after the conversation (project CLAUDE.md constraint 11 /
# the `agents` notes); the hook already reads that title off the transcript's
# own `ai-title` record (task 198, `agent_hook.transcript_title`) to NAME the
# agent, so this reuses the exact same string rather than inventing a second
# way to find it — see `agent_hook.send()`, which now rides it as the `title`
# field.
#
# The tail is what makes an EQUALITY check wrong: VS Code appends
# " - <folder> - Visual Studio Code[ tail]" to every window title, and — per
# the owner's own example in constraint 19's report — elides a title too long
# for its tab with a trailing "…". So the window's title is not the
# conversation title, it is a (possibly truncated) PREFIX of it plus VS
# Code's own furniture. Both halves have to be undone before two strings can
# honestly be compared.
#
# Two shapes exist and neither can be assumed: a member window standing in a
# workspace carries the FOLDER segment ("<file> - <folder> - Visual Studio
# Code"), the same shape `agents.VSCODE_TITLE_RE` already reads a folder out
# of; a torn-off conversation tab dragged into its own window frequently
# carries NO folder segment at all ("<conversation> - Visual Studio Code") —
# exactly the shape this project's own test fixtures use for one. The FOLDER
# form is tried first (its middle segment is required to hold no dash of its
# own, same rule `agents.py` uses, so a conversation title that itself
# contains " - " is never mistaken for a folder); the BARE form is the
# fallback.
_VSCODE_TAIL_WITH_FOLDER_RE = re.compile(
    r"^(.*?)\s-\s[^-]+\s-\s*Visual Studio Code(?:\s*\[[^\]]*\])?\s*$")
_VSCODE_TAIL_BARE_RE = re.compile(
    r"^(.*?)\s-\s*Visual Studio Code(?:\s*\[[^\]]*\])?\s*$")


def _vscode_conversation_part(title: str) -> str:
    """The conversation-naming part of a VS Code window title — everything
    before its " - Visual Studio Code[ tail]" furniture, folder segment
    included when there is one — or "" when the title carries no such tail
    at all (a plain window, an app that isn't VS Code, a bare "Visual Studio
    Code" with nothing in front of it)."""
    text = str(title or "")
    for pattern in (_VSCODE_TAIL_WITH_FOLDER_RE, _VSCODE_TAIL_BARE_RE):
        match = pattern.match(text)
        if match:
            return match.group(1).strip()
    return ""


def _title_matches(conversation: str, window_title: str) -> bool:
    """Whether `window_title` is honestly THIS conversation, never a guess.

    Equal after VS Code's own furniture is stripped is the confident case.
    When the window's own copy ends in VS Code's ellipsis, it is a TRUNCATED
    prefix of the real title — matched with a strict `startswith`, because a
    fuzzy match loose enough to bridge two DIFFERENT elided titles would send
    him into a stranger's conversation. Whenever nothing matches confidently,
    this returns False and the caller falls back to the project-folder search
    rather than guess. No lower-casing either: a conversation title is prose,
    not a folder name, and two titles differing only in case are still two
    different sentences."""
    part = _vscode_conversation_part(window_title)
    if not conversation or not part:
        return False
    if part == conversation:
        return True
    for ellipsis in ("…", "..."):
        if part.endswith(ellipsis):
            return conversation.startswith(part[: -len(ellipsis)].rstrip())
    return False


def _layout_by_title(conversation: str):
    """The live layout carrying a member window titled after `conversation`,
    or None. Reads member titles the SAME way `layout_state` already presents
    them to the phone (`wm._title(h) for h in lay.members`) — a torn-off tab's
    OWN window is what carries the conversation title, never the window it
    was torn out of, so unlike `project()` there is no source to fall back
    to here."""
    for layout in _layouts.layouts:
        for hwnd in layout.members:
            if wm.is_alive(hwnd) and _title_matches(conversation, wm._title(hwnd)):
                return layout
    return None


def layout_of(project: str, title: str = "") -> dict | None:
    """`{index, name}` of the layout showing this project, or None.

    Blocking Win32 (each layout is asked for its members' titles), so callers
    reach it through `asyncio.to_thread`.

    The INDEX is what the phone acts on, and it only means anything after a
    prune — the same prune `layout_state` runs before numbering the list the
    phone is holding. The NAME rides along so the phone can check the index
    still points at what we meant: a layout removed between the notice and the
    tap slides every higher index down, and a jump into the wrong window is
    worse than no jump at all.

    `title` (owner ruling 2026-08-13) is the conversation's own title, when
    the hook sent one: it is tried FIRST, because it can tell apart several
    windows of the SAME project spread across layouts — the exact case a
    project-folder match cannot. An older hook sends no title at all
    (`data.get("title")` is simply absent), `title` arrives here as `""`, and
    the method falls straight through to today's project-folder search —
    byte-for-byte the same result an old hook always got.
    """
    folder = pathlib.Path(str(project or "").strip()).name.lower()
    if not folder or _layouts is None:
        logger.info("Notify: no layout jump — project=%r registry=%s",
                    project, "absent" if _layouts is None else "present")
        return None
    try:
        _layouts.prune()
        conversation = str(title or "").strip()
        if conversation:
            hit = _layout_by_title(conversation)
            if hit is not None:
                index = _layouts.layouts.index(hit)
                logger.info("Notify: %r matched by conversation title → "
                            "layout %d (%s)", conversation, index, hit.name)
                return {"index": index, "name": hit.name}
        for index, layout in enumerate(_layouts.layouts):
            if layout.project() == folder:
                return {"index": index, "name": layout.name}
        # A MISS IS SAID OUT LOUD (task 236 — his THIRD report of this one
        # feature). Until now the only line written was the one on SUCCESS, so
        # a notice that shipped with no `layout` field looked in the log
        # exactly like a notice that carried one, and two rounds closed this
        # bug without anyone being able to tell which half had failed. What is
        # printed is what the match was made of: the folder we were looking
        # for, and every folder each live layout really names.
        logger.info("Notify: no layout shows %r — live layouts: %s", folder,
                    "; ".join(f"{i}:{lay.name}={lay.projects() if hasattr(lay, 'projects') else [lay.project()]}"
                              for i, lay in enumerate(_layouts.layouts)) or "none")
    except Exception as e:  # noqa: BLE001 — a notice must never fail on this
        logger.warning("Could not match %r to a layout: %s", folder, e)
    return None
