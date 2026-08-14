"""What the phone is TOLD about the layouts — the `layout_state` frame.

Split out of `layout_registry.py` on 2026-08-14 (THE STRUCTURE LAW) when that
file stood at exactly 1,000 lines and `member_hwnds` could not land inside it.
The split is by RESPONSIBILITY and not by line count: `layout_registry.py` owns
the WINDOWS — creating, growing, shrinking, focusing and letting go of them —
while this module owns the separate question of what a connected phone is told
about them, which is a wire contract with its own audience and its own reasons
to change (a new field here moves no window).

`LayoutRegistry.state()` survives as a one-line delegator, so no caller had to
learn a new name in the same commit that moved the code.
"""

import agents
import window_manager as wm


# The apps whose torn-out content still DEPENDS on the window it came from
# (owner correction 2026-08-10, task 201): a VS Code editor group belongs to
# its window; a Chrome/Explorer tab moved out is an independent window and
# closing the origin destroys nothing. It moved here with `state()` on
# 2026-08-14 — this is its ONLY reader (the ⭐ and the ✕ chooser's warning),
# and a constant that outlives its reader's module is how a second copy
# eventually gets written next to the first.
PARENT_CLOSE_APPS = {"code.exe"}


def state(reg, active: int | None, region: dict | None) -> dict:
    """The layout_state payload. Prune first so the phone never lists a
    dead layout — and FOLLOW the focused layout through that prune.

    The focus used to be a bare index, so closing a window at the desk
    slid the list down under it and the phone was suddenly focused on —
    and one X away from removing — a layout it had never chosen (audit
    2026-08-05). `prune` returns the surviving original indices, which is
    exactly the map the focus needs."""
    kept = reg.prune()
    # One process-table snapshot for every layout in the frame, not one
    # per layout (owner 2026-08-07 — see agents.agents_in).
    live = agents.live_agents()
    if active is not None:
        active = kept.index(active) if active in kept else None
        if active is None:
            region = None
    if active is not None and not 0 <= active < len(reg.layouts):
        active, region = None, None
    # WHO IS THE TRUNK, AND WHAT HANGS OFF IT (owner decision 2026-08-09,
    # task 169 — the ⭐ on the layout selector's rows; task 171 — the ✕
    # chooser must NAME what closing this layout's windows would destroy).
    # A layout is a PARENT when one of its member windows is the window
    # ANOTHER layout's content was torn out of: closing it takes that other
    # layout's tab with it, which is exactly the thing worth saying before
    # he taps.
    #
    # Read off `Layout.sources`, which `resolve_slot` records per SLOT at
    # creation — no new probe, no guess from a title, and no new field on
    # any window. Paired with the layout it belongs to so a layout can
    # never be its own parent: the window a tab came out of may itself be
    # a member of the SAME layout, and closing that pair together
    # surprises nobody.
    #
    # `dependents` is the NAMES, in list order, and `parent` is simply
    # whether there are any — one computation, so the star and the warning
    # can never disagree about which row is a trunk. Until task 173 only
    # the FIRST slot's source was stored, so a tab extracted into cell 2+
    # of a grid left no record and BOTH under-reported; every slot is
    # recorded now.
    # ONLY VS CODE HAS THE PARENT-CLOSE DEPENDENCY (owner correction
    # 2026-08-10, task 201, with his screenshot of a starred Chrome
    # layout): a Chrome or Explorer tab moved to its own window is a
    # fully independent window — closing the origin destroys nothing —
    # so an extraction records a source for EVERY app, but the star and
    # the ✕ warning are about what a close would DESTROY, and that is
    # true only where the torn-out content still depends on its origin.
    # Judged by the BRANCH's app (the tab and its origin are the same
    # app), so no extra Win32 call rides the state frame.
    owners = [(lay, src) for lay in reg.layouts for src in lay.sources.values()]
    dependents = {
        id(lay): [other.name for other, src in owners
                  if other is not lay and src in lay.members
                  and (other.process or "").lower() in PARENT_CLOSE_APPS]
        for lay in reg.layouts}
    return {
        "type": "layout_state",
        "layouts": [{"name": lay.name, "process": lay.process,
                     # Both READ, never remembered: prune just ran, so the
                     # member is alive and can be asked. `agents` is the
                     # ONLY answer to "does the Claude wheel belong here"
                     # (server/agents.py; `project()` is what lets an
                     # EXTRACTED tab be asked at all).
                     "title": wm._title(lay.members[0]),
                     "agents": agents.agents_in(lay.project(), live),
                     # WHICH grid, so the phone can draw its shape and
                     # offer the arrangement choice for a three
                     # (owner 2026-08-07). None = a solo layout.
                     # These three — grid, members, orient — are also what
                     # the LIST draws each row's little diagram from
                     # (owner 2026-08-09, task 164; client/grid-icons.js).
                     # The "only a three may re-arrange" asymmetry is read
                     # off them and is deliberately NOT a field of its own:
                     # a second statement of a rule is a second thing to
                     # keep in step.
                     "grid": lay.template,
                     "members": len(lay.members),
                     # WHO is in each cell, in cell order (owner request
                     # 2026-08-09, task 165). Throwing one window out of a
                     # grid means naming which one, and the phone knows
                     # only what this frame tells it. Titles only, never
                     # icons: `layout_state` rides every focus and every
                     # change, and an icon per member would multiply the
                     # frame for a panel that opens rarely — the CELL is
                     # the picture (client/grid-icons.js), the title is
                     # the word. Read live, like `title` beside it.
                     "member_titles": [wm._title(h) for h in lay.members],
                     # Which windows this layout ALREADY holds, so the tap
                     # refuses "already in here" locally instead of
                     # guessing from titles (2026-08-13; __about doc).
                     "member_hwnds": list(lay.members),
                     # The ⭐ (owner 2026-08-09, task 169) and the ✕
                     # chooser's warning (task 171) — see `owners` above.
                     # The names of every OTHER layout whose content came
                     # out of a window this one holds; the star is simply
                     # whether that list is empty.
                     "dependents": dependents[id(lay)],
                     "parent": bool(dependents[id(lay)]),
                     "orient": lay.orient, "icon": lay.icon,
                     "ratio": list(lay.ratio) if lay.ratio else None,
                     # The free-axis anchor of the letterboxed picture on
                     # the phone — the ONLY thing `pos` still moves
                     # (owner decree 2026-08-09).
                     "pos": round(lay.pos, 3)}
                    for lay in reg.layouts],
        "active": active,
        "region": region,
        "orient": reg.layouts[active].orient if active is not None else None,
    }
