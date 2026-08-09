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


async def layout_list(ws, layouts, stream) -> None:
    """The list-based creation source (owner 2026-08-02): every open window
    PLUS each window's content tabs as separate entries — 'Google Chrome'
    alone hid its tabs, the exact reported gap. Windows that already belong to
    a layout are LEFT OUT (owner 2026-08-03): one window cannot be shown in
    two places, so it stays off the list for as long as it is in a layout."""
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
        entries.append({"kind": "window", "hwnd": w["hwnd"], "title": w["title"],
                        "process": w["process"], "icon": w["icon"],
                        "agents": agents.agents_for(w["title"], live)})
        if not uia.has_tabs(w["process"]):
            continue  # its TabItems are internal sections, not real tabs
        for tab in await asyncio.to_thread(uia.list_tabs, rect, w["hwnd"]):
            entries.append({"kind": "tab", "hwnd": w["hwnd"],
                            "tab": {"name": tab["name"]},
                            "x": tab["x"], "y": tab["y"],
                            "title": tab["name"],
                            "process": w["process"], "icon": w["icon"],
                            "agents": agents.agents_for(w["title"], live)})
    await ws.send_text(json.dumps({
        "type": "layout_offer",
        "target": None,
        "entries": entries,
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
    target, name, source = resolved[0]
    # The phone may carry the owner's own name (owner 2026-08-05); the tab /
    # window title stays the default the panel prefilled it with.
    typed = str(msg.get("name", "")).strip()[:80]
    name = typed or name
    # `app_sets` used to arrive here — the owner's ticks. It is ignored now
    # (owner 2026-08-07): the PC recognises what runs in a window, and a copy
    # of that answer frozen at creation time is what kept his Claude layout on
    # the VS Code wheel. An old client may still send the key; it changes
    # nothing.
    created = await asyncio.to_thread(
        layouts.create, target, str(msg.get("mode", "solo")),
        msg.get("grid"), [h for h, _, _ in resolved[1:]],
        orient, conn["ratio"], mon_rect(stream), name, source)
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
