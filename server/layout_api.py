"""The phone's LAYOUT commands: pick, list, create, focus, aspect, state.

Split out of web.py on 2026-08-05 (THE STRUCTURE LAW). These are the protocol
handlers for Phase F+ layouts — one coherent responsibility with one engine
underneath it (`window_manager`), and web.py had become the place where every
kind of message happened to live.

The rule these handlers exist to keep (owner decree 2026-08-04, hardened
2026-08-05 after his windows were left hovering for the second time): a layout
member is above EVERYTHING while the phone is showing it, and above nothing
the moment it is not. Every one of these functions is therefore either a raise
or a release; `window_manager`'s topmost ledger is what makes the release
total, including for windows no layout can still name.
"""

import asyncio
import json
import logging

import agents
import uia
import window_manager
from monitors import rect_for_size

logger = logging.getLogger(__name__)


async def toast(ws, text: str) -> None:
    """The one-line notice on the phone's status pill. It lives here because
    these handlers are its heaviest user and web.py imports from this module,
    never the other way round — one definition, no copy."""
    await ws.send_text(json.dumps({"type": "toast", "text": text}))


def mon_rect(stream) -> tuple[int, int, int, int]:
    return rect_for_size(stream.width, stream.height, stream.monitor_index)


async def send_layout_state(ws, layouts, conn: dict) -> None:
    state = await asyncio.to_thread(layouts.state, conn["active"], conn["region"])
    # `state` re-maps the focus through its own prune, so the connection
    # adopts what it says — the focused layout may have SHIFTED (a window
    # closed at the desk), not just vanished. Trusting only the None case is
    # how the phone ended up focused on a layout it never chose.
    conn["active"] = state["active"]
    if state["active"] is None:
        conn["region"] = None
    await ws.send_text(json.dumps(state))


async def layout_pick(ws, layouts, stream, msg: dict) -> None:
    """The phone's armed tap: identify the window under the point and offer
    the layout choices (solo / grid templates + open windows to fill cells)."""
    x, y = float(msg["x"]), float(msg["y"])
    target = await asyncio.to_thread(
        window_manager.window_at, mon_rect(stream), x, y)
    if target is None:
        await toast(ws, "No window there — tap on a window")
        return
    # Tab under the same point (step 2): the offer names it, and the client
    # echoes the pick point back in layout_create so extraction re-finds it.
    # Grid cells are picked by FURTHER taps (owner 2026-08-02), so no window
    # list rides along here — the list-based source is `layout_list`.
    # Only tab-capable apps are asked (owner 2026-08-03) — everything else's
    # TabItems are internal section switchers that cannot become a window.
    tab = None
    if uia.has_tabs(target["process"]):
        tab = await asyncio.to_thread(uia.tab_at, mon_rect(stream), x, y)
    if isinstance(target, dict):
        live = await asyncio.to_thread(agents.live_agents)
        target["agents"] = agents.agents_for(target.get("title", ""), live)
    await ws.send_text(json.dumps({
        "type": "layout_offer",
        "target": target,
        "tab": tab,
        "x": x, "y": y,
        "grids": list(window_manager.GRID_TEMPLATES),
    }))


async def _list_entries(layouts, stream) -> list[dict]:
    """Every open window PLUS each window's content tabs as separate entries
    — 'Google Chrome' alone hid its tabs, the exact reported gap. Windows
    that already belong to a layout are LEFT OUT (owner 2026-08-03): one
    window cannot be shown in two places, so it stays off the list for as
    long as it is in a layout. Shared by `layout_list` (fresh-creation
    source) and `layout_member_list` (task 195's "Add a window" — the same
    exclusion is exactly what a member-add needs: a window already claimed
    by SOME layout, this one included, cannot be added again)."""
    # NOT `mon_rect = mon_rect(stream)`: that name is this module's own
    # function, and assigning to it makes it a LOCAL for the whole function —
    # so the call on the right-hand side raises UnboundLocalError and the
    # phone's list NEVER ARRIVES. That is exactly what killed "create from a
    # list" (owner report 2026-08-06; his server log carried the traceback
    # three times, the phone showed a spinner forever). tests/test_layout_protocol.py
    # walks this path now — it did not exist, which is why nothing caught it.
    rect = mon_rect(stream)
    used = await asyncio.to_thread(layouts.member_hwnds)
    windows = await asyncio.to_thread(window_manager.list_windows, used)
    # ONE snapshot for the whole list, taken off the event loop (owner
    # 2026-08-07). It used to be asked per entry, bare, from this coroutine:
    # a 1.85 s PowerShell probe every time the 2 s cache lapsed between two
    # windows, each one freezing the stream and the heartbeats along with the
    # list. See agents.agents_for.
    live = await asyncio.to_thread(agents.live_agents)
    entries = []
    for w in windows:
        # `agents` is what puts the Claude wheel on a Claude window with no
        # tap from anyone (owner 2026-08-06): the PC reads its own process
        # table, the phone cannot.
        entry = {"kind": "window", "hwnd": w["hwnd"], "title": w["title"],
                 "process": w["process"], "icon": w["icon"],
                 "agents": agents.agents_for(w["title"], live)}
        entries.append(entry)
        # A WINDOW AND ITS ONLY TAB ARE ONE THING, NOT TWO (owner 2026-08-09,
        # task 167). The rule lives in `uia.offerable_tabs`, whole: a lone tab
        # is never offered, so this loop can no longer emit an entry that
        # cannot become a member of anything. It used to append one entry per
        # tab INCLUDING the first, with `has_tabs` — a test of the process
        # NAME — as the only filter, so a VS Code holding one tab was offered
        # twice and the phone counted two windows where the desk had one.
        if not uia.has_tabs(w["process"]):
            continue          # its TabItems are internal sections, not tabs
        if uia.is_minimized(w["hwnd"]):
            # SAY IT, never let the list quietly change shape. A minimized
            # window answers "no tabs" whatever it holds (UIA reports height
            # 0), so the same window used to appear WITHOUT its tabs from the
            # taskbar and WITH them once restored, with nothing on screen to
            # explain the difference. One non-blocking Win32 read, unlike
            # every other call here — hence no thread.
            entry["tabs_hidden"] = True
            continue
        for tab in await asyncio.to_thread(
                uia.offerable_tabs, rect, w["hwnd"], w["process"]):
            entries.append({"kind": "tab", "hwnd": w["hwnd"],
                            "tab": {"name": tab["name"]},
                            "x": tab["x"], "y": tab["y"],
                            "title": tab["name"],
                            "process": w["process"], "icon": w["icon"],
                            "agents": agents.agents_for(w["title"], live)})
    return entries


async def layout_list(ws, layouts, stream) -> None:
    """The list-based creation source (owner 2026-08-02)."""
    entries = await _list_entries(layouts, stream)
    await ws.send_text(json.dumps({
        "type": "layout_offer",
        "target": None,
        "entries": entries,
        "grids": list(window_manager.GRID_TEMPLATES),
    }))


async def layout_member_list(ws, layouts, stream, msg: dict) -> None:
    """The ⚙ sheet's "Add a window" (task 195): the SAME enumeration
    `layout_list` uses — windows already in any layout, this one included,
    are already excluded by `_list_entries`'s `member_hwnds` call, which is
    exactly the rule an add needs — tagged with `add_to` so the client's
    `layout_offer` handler routes it to the add flow instead of a fresh
    creation. No new listing logic: one enumeration, two doors in."""
    entries = await _list_entries(layouts, stream)
    await ws.send_text(json.dumps({
        "type": "layout_offer",
        "target": None,
        "entries": entries,
        "add_to": int(msg["index"]),
        "grids": list(window_manager.GRID_TEMPLATES),
    }))


async def resolve_slot(ws, stream, slot: dict) -> tuple[int, str | None, int] | None:
    """One creation slot → `(hwnd, tab name, SOURCE hwnd)`. A slot naming a
    TAB is extracted into its own window first (app command → Explorer path →
    drag); every failure falls back to the slot's whole window.

    The third value is the whole point of the triple (owner report
    2026-08-08): a torn-off tab's own window may be titled `Visual Studio
    Code` and nothing else, so the window it came OUT of is the only one that
    can still name the project — and the layout keeps its HANDLE, to be read
    live, never its answer. 0 = nothing was extracted, the window speaks for
    itself. See `window_manager.Layout.project`."""
    hwnd = int(slot["hwnd"])
    tab = slot.get("tab")
    if not tab:
        return (hwnd, None, 0)
    info = await asyncio.to_thread(window_manager.window_at_hwnd, hwnd)
    if info is None:
        return None
    extracted = await asyncio.to_thread(
        uia.extract_tab, mon_rect(stream),
        float(slot.get("x", 0.5)), float(slot.get("y", 0.5)),
        info, tab.get("name"))
    if extracted is None:
        await toast(ws, f"Could not separate “{tab.get('name', 'tab')}” — using the whole window")
        return (hwnd, None, 0)
    return (extracted, tab.get("name"), hwnd)


def grid_for(layouts, count: int, wanted: str | None) -> tuple[str | None, str | None]:
    """The shape `count` windows can REALLY wear, plus what to tell the phone
    when that is not the shape it asked for. `(template, notice)`; a template
    of None means a single-window layout.

    Owner report 2026-08-09 (task 166): the panel offered a grid of four while
    the desktop held three, and the server built it in silence. `create()`
    truncates its members to the template's cells, `zip` stops at the shorter
    side, `placed` stays True because every window it DID place landed — and
    the region is the union of the cells, so a 2x2 filled by three windows
    frames four quadrants with the fourth showing bare desktop. Nothing in
    that chain is wrong on its own; what was missing is anybody deciding that
    a four cannot be built out of three, and saying so.

    The decision is NOT re-invented here. `LayoutRegistry._template_for` is the
    one definition of "what shape does a layout of N windows take", written for
    `merge` (growing one) and `drop_member` (shrinking one) — it honours the
    phone's own choice whenever it FITS and falls back to the only sane shape
    for that size otherwise. This path is the third way a layout's size is
    decided, so it asks the same function rather than growing a second opinion
    that can drift from it. Reaching for a private name is deliberate and is
    the cheaper of the two evils; the alternative was a copy."""
    template = layouts._template_for(count, wanted)
    cells = window_manager.GRID_CELLS[template] if template else 1
    asked = window_manager.GRID_CELLS.get(
        window_manager.normalize_grid(wanted) or "")
    if count > cells:
        # More windows arrived than any shape holds — `create` would drop the
        # extras without a word.
        return template, (f"A layout holds at most {cells} windows — "
                          f"{count - cells} were left out")
    if not asked or asked == cells:
        return template, None
    if cells == 1:
        return template, "Only one window was ready — made a single window"
    return template, (f"Only {cells} windows were ready — made a "
                      f"{cells}-window layout instead of a {asked}")


async def layout_create(ws, layouts, stream, conn: dict, msg: dict) -> None:
    # ONE NAME PER THING (owner 2026-08-07): the shape is "landscape" or
    # "portrait" everywhere — in the protocol, the UI and the docs. "wide" was
    # the same thing under a second name and he banned it; it is still
    # ACCEPTED here so a phone serving an older page keeps working.
    orient = "landscape" if msg.get("orient") in ("landscape", "wide") else "portrait"
    slots = msg.get("slots") or []
    if not slots:
        await toast(ws, "Nothing selected — layout not created")
        await send_layout_state(ws, layouts, conn)
        return
    resolved: list[tuple[int, str | None, int]] = []
    for i, slot in enumerate(slots):
        r = await resolve_slot(ws, stream, slot)
        if r is not None:
            resolved.append(r)
        # one turn of the phone's loading cube per processed window
        await ws.send_text(json.dumps(
            {"type": "layout_progress", "done": i + 1, "total": len(slots)}))
    if not resolved:
        await toast(ws, "Those windows are gone — layout not created")
        await send_layout_state(ws, layouts, conn)
        return
    target, name, _ = resolved[0]
    # EVERY SLOT'S SOURCE, NOT ONLY THE FIRST (task 173, 2026-08-09). The
    # triple's third value is the window a tab was torn OUT of, and only
    # `resolved[0]`'s used to be kept — so a tab extracted into cell 2, 3 or 4
    # of a grid left no record, and the ⭐ (task 169) plus the ✕ chooser's
    # warning (task 171) both under-reported on exactly the layouts they exist
    # for. Keyed by the extracted window, because `create` filters and
    # truncates the member list and a positional list would have to be kept in
    # step by hand.
    sources = {h: s for h, _, s in resolved if s}
    # The phone may carry the owner's own name (owner 2026-08-05); the tab /
    # window title stays the default the panel prefilled it with.
    typed = str(msg.get("name", "")).strip()[:80]
    name = typed or name
    # `app_sets` used to arrive here — the owner's ticks. It is ignored now
    # (owner 2026-08-07): the PC recognises what runs in a window, and a copy
    # of that answer frozen at creation time is what kept his Claude layout on
    # the VS Code wheel. An old client may still send the key; it changes
    # nothing.
    #
    # THE SHAPE FOLLOWS THE WINDOWS THAT ARRIVED, and a downgrade is SPOKEN
    # (owner 2026-08-09, task 166). The phone's `grid` is a request, never the
    # answer: slots die between the pick and the create, a tab refuses to be
    # extracted, and until today a four built from three simply framed an
    # empty quadrant.
    # A SOLO layout stays solo whatever arrived — `grid_for` derives a shape
    # from the count, and a count is only a shape when a grid was asked for.
    template, notice = (
        grid_for(layouts, len(resolved), msg.get("grid"))
        if str(msg.get("mode", "solo")) == "grid" else (None, None))
    if notice:
        await toast(ws, notice)
    created = await asyncio.to_thread(
        layouts.create, target, "grid" if template else "solo",
        template, [h for h, _, _ in resolved[1:]],
        orient, conn["ratio"], mon_rect(stream), name, sources)
    if created is None:
        await toast(ws, "That window is gone — layout not created")
    else:
        index, placed = created
        if not placed:
            # Verified placement failed for at least one member (min-size or a
            # stubborn app) — say so instead of pretending (owner 2026-08-04).
            await toast(ws, "A window would not take its exact spot")
        await layout_focus(ws, layouts, stream, conn, index)
        return
    await send_layout_state(ws, layouts, conn)


async def layout_aspect(ws, layouts, stream, conn: dict, msg: dict) -> None:
    """The phone's Aspect panel (owner 2026-08-03): store this layout's W:H
    (0/0 = back to the phone's own shape) and free-axis anchor `pos` (owner
    2026-08-05 — the Move handle; 0–1000, 500 = centered), then focus it.
    The focus re-places the windows for a RATIO change — always centred on
    the monitor since 2026-08-09 (owner decree, after three rounds moved
    windows on a screen he never sees) — and, either way, sends the
    `layout_state` that carries `pos` to the phone, which anchors the
    letterboxed picture with it (client/view-anchor.js)."""
    index = int(msg["index"])
    w, h = int(msg.get("w") or 0), int(msg.get("h") or 0)
    pos = int(msg.get("pos") if msg.get("pos") is not None else 500) / 1000
    logger.info("Aspect from the phone: layout %d w=%d h=%d pos=%.3f",
                index, w, h, pos)
    if not await asyncio.to_thread(layouts.set_ratio, index, w, h, pos):
        await toast(ws, "That layout is gone")
        await send_layout_state(ws, layouts, conn)
        return
    await layout_focus(ws, layouts, stream, conn, index)


async def layout_member_remove(ws, layouts, stream, conn: dict,
                               msg: dict) -> None:
    """Throw ONE window out of a grid (owner request 2026-08-09, task 165):
    a four becomes a three, a three a two, a two a single. Until today a grid
    could only be BUILT (`layout_merge`) or removed WHOLE, so losing one
    window of four meant deleting the layout and making it again.

    It is NOT a close. The window leaves the layout, leaves the topmost band
    and goes on standing exactly where it stands — only the ✕ chooser closes
    windows, and only when he asked for that act (2026-08-08, task 116).
    `member` is the ordinal of the cell he tapped; `grid` is optional and is
    the arrangement a four landing on a three should take (the four
    three-shapes are the only real choice in his catalogue, owner
    2026-08-07 — see `LayoutRegistry._template_for`).

    Lives here rather than in web.py's dispatcher for the reason the whole
    module exists: this is the phone's layout protocol, and web.py stands at
    the 1,000-line wall (the guard refuses to let it grow at all)."""
    index = int(msg["index"])
    outcome = await asyncio.to_thread(
        layouts.drop_member, index, int(msg.get("member", -1)),
        msg.get("grid"))
    if outcome == "gone":
        await toast(ws, "That window is no longer in the layout")
        await send_layout_state(ws, layouts, conn)
    elif outcome == "removed":
        # The last member left, so the layout did too. The same index
        # bookkeeping `layout_remove` does — because it IS that path.
        if conn["active"] is not None:
            if conn["active"] == index:
                conn["active"], conn["region"] = None, None
            elif conn["active"] > index:
                conn["active"] -= 1
        await send_layout_state(ws, layouts, conn)
        await toast(ws, "That was the last window — the layout is gone")
    else:
        # The survivors must be RE-ARRANGED, not merely re-listed: three
        # windows still standing in a 2x2 is not a three.
        await layout_focus(ws, layouts, stream, conn, index)


async def layout_member_add(ws, layouts, stream, conn: dict, msg: dict) -> None:
    """Grow a layout by ONE window — solo→2, 2→3, 3→4 (owner request, task
    195, in translation: "add a member to an existing layout, if there is
    room ... unless it already has four"). The ⚙ sheet's mirror of
    `layout_member_remove`.

    `hwnd`/`tab` name the chosen slot exactly like a creation slot — this
    reuses `resolve_slot`, the SAME tab-extraction path `layout_create` uses,
    so a tab picked here is torn into its own window exactly as a creation
    slot would be, never a second implementation of that dance. Only
    `layouts.add_member` decides how the layout's SHAPE changes, and it is
    the same `_template_for` `drop_member` shrinks a layout through — growing
    and shrinking can never disagree about what a three is."""
    index = int(msg["index"])
    slot = {"hwnd": msg["hwnd"], "tab": msg.get("tab"),
            "x": msg.get("x", 0.5), "y": msg.get("y", 0.5)}
    resolved = await resolve_slot(ws, stream, slot)
    if resolved is None:
        await toast(ws, "That window is gone")
        await send_layout_state(ws, layouts, conn)
        return
    hwnd, _tab, source = resolved
    outcome = await asyncio.to_thread(
        layouts.add_member, index, hwnd, source, msg.get("grid"))
    if outcome == "gone":
        await toast(ws, "That layout is gone")
        await send_layout_state(ws, layouts, conn)
    elif outcome == "full":
        await toast(ws, "That layout already has four windows")
        await send_layout_state(ws, layouts, conn)
    elif outcome == "duplicate":
        await toast(ws, "That window is already in a layout")
        await send_layout_state(ws, layouts, conn)
    else:
        # The new member joins the topmost ledger through the ordinary raise
        # order `focus()` already walks — never a special case for it — and
        # the survivors are re-arranged into the new shape alongside it.
        await layout_focus(ws, layouts, stream, conn, index)


async def layout_split(ws, layouts, stream, conn: dict, msg: dict) -> None:
    """Break a grid into as many SOLO layouts as it has members (owner
    request, task 197a: "decompose a grid into several individual layouts").
    Each member keeps its own `Layout.sources` record — task 173's whole
    reason for keying it per member — so the ⭐/dependents a window carried
    inside the grid survive the split.

    The source layout's INDEX is replaced by the new layouts, in member
    order, so `conn["active"]` needs the same care `layout_remove` takes,
    only shifted by however many layouts now stand where one did: unaffected
    when it pointed above the split, focused fresh on the first new layout
    when the split layout WAS the active one, and pushed down by the extra
    layouts otherwise."""
    index = int(msg["index"])
    was_active = conn["active"]
    made = await asyncio.to_thread(layouts.split, index)
    if not made:
        await toast(ws, "Nothing to split — that layout has one window")
        await send_layout_state(ws, layouts, conn)
        return
    if was_active is not None and was_active == index:
        # The phone was looking at exactly the layout that just split apart —
        # land it on the first piece, the same spot in the bar/list it stood
        # in before.
        await layout_focus(ws, layouts, stream, conn, made[0])
        return
    if was_active is not None and was_active > index:
        conn["active"] = was_active + (len(made) - 1)
    await send_layout_state(ws, layouts, conn)


async def layout_member_eject(ws, layouts, stream, conn: dict,
                              msg: dict) -> None:
    """Pull ONE member out of a grid into ITS OWN new layout — never to the
    desktop (owner request, task 197b, explicitly contrasted with the
    existing "Take one window out" / `layout_member_remove`, which leaves the
    window standing as plain desktop material). Lives in the member chooser
    beside that act, and reads `member` the same way — the cell ordinal, not
    a handle."""
    index = int(msg["index"])
    outcome = await asyncio.to_thread(
        layouts.eject_member, index, int(msg.get("member", -1)),
        msg.get("grid"))
    if outcome == "gone":
        await toast(ws, "That window is no longer in the layout")
        await send_layout_state(ws, layouts, conn)
    else:
        # The survivors are re-arranged, same as after a plain member remove;
        # the ejected window's own new layout stays off the topmost band
        # until the phone focuses it (eject_member already dropped it there).
        await layout_focus(ws, layouts, stream, conn, index)


async def layout_reorder(ws, layouts, conn: dict, msg: dict) -> None:
    """A row dropped BETWEEN two others — the list's own order, and nothing on
    the PC moves (owner 2026-08-07).

    THE FOCUS RIDES ON AN INDEX, AND A REORDER MOVES INDICES (found 2026-08-09
    while wiring the phone's member chooser). `conn["active"]` is a plain
    position in `layouts.layouts`, so re-ordering the list while a layout was
    focused left it pointing at a DIFFERENT layout: the phone framed one
    layout while the server believed another was active — and the bar's ✕
    would then have offered to close the wrong windows.

    `layout_merge` corrects its own shift arithmetically at the call site
    (`dst - 1 if src < dst else dst`); this one corrects it by IDENTITY,
    because `reorder` never drops a layout — the object that must stay focused
    is right there to be found again, and an index recomputed a second way is
    a second thing to keep in step with the first.

    Nothing is placed and nothing is raised: a reorder is a fact about the
    LIST, so the phone simply gets the corrected state back."""
    active = conn["active"]
    focused = (layouts.layouts[active]
               if active is not None and 0 <= active < len(layouts.layouts)
               else None)
    await asyncio.to_thread(layouts.reorder, int(msg["source"]),
                            int(msg["before"]))
    if focused is not None:
        conn["active"] = next(
            (i for i, lay in enumerate(layouts.layouts) if lay is focused),
            conn["active"])
    await send_layout_state(ws, layouts, conn)


async def layout_focus(ws, layouts, stream, conn: dict, index: int) -> None:
    """index -1 = back to the full desktop. Region is re-read fresh on every
    focus — desk-side moves/resizes never break a layout (owner rule)."""
    if index < 0:
        conn["active"], conn["region"] = None, None
        # Desktop position minimizes every layout member — the desktop shows
        # only the windows that are NOT layout material (owner 2026-08-02).
        await asyncio.to_thread(layouts.minimize_members)
    else:
        focused = await asyncio.to_thread(
            layouts.focus, index, conn["ratio"], mon_rect(stream))
        if focused is None:
            conn["active"], conn["region"] = None, None
            await toast(ws, "That layout's window is gone")
        else:
            region, placed = focused
            # THE APP MUST SAY ITS OWN GEOMETRY, EVERY TIME (owner's FOURTH
            # Move-handle report, 2026-08-08). His log holds not one line about
            # placement — the only one that existed fired on REFUSAL, nothing
            # had refused, and so four rounds argued about whether a window
            # moved while the app, which knew, said nothing. A feature he
            # judges by geometry has to log geometry: the stored position, the
            # region it produced, and whether the members really took it.
            # Logged here rather than inside `focus()` for a plain reason worth
            # recording: window_manager.py stands exactly ON the 1,000-line
            # limit, so the guard refuses to let it grow at all — and this
            # layer already has both halves of the answer.
            lay = layouts.layouts[index] if index < len(layouts.layouts) else None
            logger.info("Layout %d focused: pos=%s ratio=%s -> region=%s landed=%s",
                        index, getattr(lay, "pos", "?"), getattr(lay, "ratio", "?"),
                        region, placed)
            conn["active"], conn["region"] = index, region
            if not placed:
                await toast(ws, "A window would not take its exact spot")
    await send_layout_state(ws, layouts, conn)
