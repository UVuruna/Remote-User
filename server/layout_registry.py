"""The layout REGISTRY: the session's layout list and its lifecycle.

Split out of `window_manager.py` on 2026-08-09 (THE STRUCTURE LAW — the pos
anchor round pushed it past 1,000 lines, and the seam had been named for two
days: layout_api.py already logged focus geometry on its own side "for a plain
reason worth recording: window_manager.py stands exactly ON the 1,000-line
limit"). The seam is the same one grids.py was cut on: `window_manager` DRIVES
real windows (enumerate, place, raise, close, the topmost ledger); this module
holds the SESSION STATE and the policy over it — which layouts exist, which
members they hold, when a focus re-places them and what `layout_state` claims.

Every desk primitive is reached LAZILY through the `wm` module object
(`wm.place_window(...)`, never `from window_manager import place_window`):
the gates fake a windowless PC by patching names ON `window_manager`
(tests/test_layout_protocol.py `install_fakes`), and a name bound here at
import time would keep pointing at the real desk after the patch. Import this
module only through `window_manager` (which re-exports `Layout` and
`LayoutRegistry` at its bottom) — imported first, it would find a
half-initialized `window_manager` and fail loudly.

All methods are blocking ctypes/Win32 — the web layer calls them via
asyncio.to_thread.
"""

import logging

import agents
import layout_history
import window_manager as wm

logger = logging.getLogger(__name__)


class Layout:
    """One phone screen: member windows + the orientation/aspect it was built
    for. Members are ordered — grid cell order for grids, [window] for solo."""

    def __init__(self, name: str, process: str, members: list[int],
                 template: str | None, orient: str, aspect: float,
                 icon: str | None = None, sources: dict[int, int] | None = None,
                 folder: str = ""):
        self.name = name
        self.process = process
        # WHERE this layout's project is READ FROM — never the answer itself.
        # `sources` maps an extracted member window to the window its TAB was
        # torn out of; `folder` is the project the pair's titles named at
        # creation, the last resort for when that source window is gone. This
        # used to be the window's TITLE, frozen — see `project()` and
        # __about/layout_registry.md.
        #
        # ONE ENTRY PER SLOT, NOT ONE PER LAYOUT (task 173, 2026-08-09). It was
        # a single `source` int written from the FIRST slot alone, so a tab
        # extracted into cell 2, 3 or 4 of a grid left no record at all — and
        # both readers of that record under-reported: the ⭐ that says "another
        # layout's content lives in a window of this one" (task 169) and the
        # ✕ chooser's warning built on it (task 171). A dict keyed by the
        # MEMBER rather than a list keyed by position, because members are
        # filtered on the way in (a dead handle, a duplicate) and re-ordered on
        # the way out (`drop_member`, `merge`) — a positional list would have
        # to be kept in step by every one of those paths, which is exactly the
        # kind of second bookkeeping this project keeps paying for.
        self.sources = dict(sources or {})
        self.folder = folder
        self.members = members
        # WHICH member holds the keyboard (owner 2026-08-06). The phone types
        # into one window of a grid, and every re-focus used to hand the
        # keyboard to whichever member sat LAST in this list — so a dictation
        # interrupted by one excursion continued in the other agent's session.
        # Kept in the registry, not in the connection: an excursion closes the
        # socket, and the target must outlive it. See focus_guard.
        self.last_member: int = members[0] if members else 0
        self.template = template  # None = solo
        self.orient = orient      # "portrait" | "landscape" (owner 2026-08-07:
                                  # never "wide" again — one name per thing)
        self.aspect = aspect      # w/h the layout was last arranged for
        self.icon = icon          # target app's icon (PNG data URI) for the bar
        # Owner-chosen W:H for THIS layout (None = the phone's own shape) and
        # `pos`, the 0–1 free-axis anchor of the letterboxed PICTURE on the
        # phone (0.5 = centered — the Move handle). `pos` moves NOTHING on
        # the PC (owner decree 2026-08-09, the Move handle's FOURTH round:
        # the server crops the region and streams the same picture wherever
        # the windows sit, so three rounds of moving windows changed nothing
        # he could see) — it is stored only to ride `layout_state` to the
        # phone, which anchors the picture with it (client/view-anchor.js).
        # `arranged_ratio` is the ratio the windows last LANDED in — a ratio
        # change is what makes the next focus re-place them (owner
        # 2026-08-03); `place_pending` is the explicit re-place order a
        # structural change (grid arrangement, orientation, merge) leaves,
        # for the case where every member still happens to pass `_standing`.
        # WINDOWS THIS LAYOUT'S WORK OPENED (owner eruption 2026-08-11, task
        # 202): an agent's HTML report, a member's "Open this link?" dialog,
        # the viewer a member started. They are not members — the grid does
        # not grow and nothing is re-arranged around them — but while the
        # phone shows this layout they are brought INTO its picture and into
        # the always-on-top band with it ([Layout Popup](layout_popup.py)),
        # so this list is what owes them the way back down (constraint 10).
        self.adopted: list[int] = []
        self.ratio: tuple[int, int] | None = None
        self.pos: float = 0.5
        self.arranged_ratio: tuple[int, int] | None = None
        self.place_pending: bool = False

    @property
    def source(self) -> int:
        """The window THIS layout's first member was torn out of (0 = none).

        A read of `sources`, never a second field: `project()` asks about
        `members[0]` and about nothing else, so the answer has to follow that
        member when the list changes under it (`drop_member` removing cell 0,
        `merge` re-ordering). A stored int could only have gone stale."""
        return self.sources.get(self.members[0], 0) if self.members else 0

    def release_adopted(self) -> list[int]:
        """Hand every window this layout ADOPTED back to the desk — out of the
        always-on-top band, with its own minimize/restore animation returned —
        and forget it. Returns what was released, for the log.

        Called wherever this layout stops being what the phone shows: another
        layout focused, Desktop chosen, the layout removed, the phone gone.
        The window is NOT moved back and NOT closed: no window is ever moved
        by us without being asked to be (the rule `remove` and `drop_member`
        already follow), and closing one is an act only the ✕ chooser has —
        a report he still wants to read must survive being let go of."""
        released, self.adopted = self.adopted, []
        for hwnd in released:
            wm.freeze_transitions(hwnd, False)
            wm.drop_topmost(hwnd)
        return released

    def project(self) -> str:
        """The project folder this layout's window belongs to, MEASURED every
        call — an extracted tab's own window can be titled bare `Visual Studio
        Code`, so the window it was torn OUT of is asked next, live. `folder`
        is the last resort (that source closed): a FOLDER is not an answer —
        what is LIVE in it comes from the process table, every frame.

        EVERY member is asked, not only the first (task 236, the owner's THIRD
        report of the notification tap landing on the previous layout). A grid
        holds up to four windows and the agent's own window is as often cell 2
        as cell 0; asking `members[0]` alone made a four-window layout answer
        for a quarter of itself, and a torn-off Claude tab — titled after the
        CONVERSATION, never after the folder — answered for none of it. The
        order is still authority-first: each member, then the window it was
        torn out of, so a member that can name the folder itself outranks a
        source that only inherited it."""
        titles = []
        for hwnd in self.members:
            for h in (hwnd, self.sources.get(hwnd, 0)):
                if h and wm.is_alive(h):
                    titles.append(wm._title(h))
        return agents.first_folder(titles) or self.folder

    def projects(self) -> list[str]:
        """Every project folder this layout's members name, in cell order,
        without duplicates. `project()` answers with the first of these; this
        is what a MISS is reported against, so the log can say what the live
        layouts really held instead of leaving him to guess (task 236)."""
        found: list[str] = []
        for hwnd in self.members:
            for h in (hwnd, self.sources.get(hwnd, 0)):
                if not h or not wm.is_alive(h):
                    continue
                folder = agents.title_folder(wm._title(h))
                if folder and folder not in found:
                    found.append(folder)
        if not found and self.folder:
            found.append(self.folder)
        return found


# The apps whose torn-out content still DEPENDS on the window it came from
# (owner correction 2026-08-10, task 201): a VS Code editor group belongs to
# its window; a Chrome/Explorer tab moved out is an independent window and
# closing the origin destroys nothing. Consulted by `state()`'s dependents
# computation — the ⭐ and the ✕ chooser's warning.
PARENT_CLOSE_APPS = {"code.exe"}


class LayoutRegistry:
    """Session-scoped layout list (server lifetime — survives phone drops).
    All methods are blocking; the web layer wraps them in to_thread."""

    def __init__(self):
        self.layouts: list[Layout] = []
        # The layout the phone was last working in (owner 2026-08-05): the app
        # leaving work mode minimizes everything, and the next session comes
        # back HERE instead of on the desktop. Server-side on purpose — the
        # client's own memory dies with the page when the app is closed.
        # (index, name) — the name guards against the list having shifted.
        self.last_focus: tuple[int, str] | None = None

    def prune(self) -> list[int]:
        """Closing a member at the desk removes it from its layout (owner
        rule); a layout with no live members disappears. Returns the surviving
        layouts' ORIGINAL indices, so a caller holding one (the focused
        layout) can follow it instead of pointing at whatever slid into its
        place.

        CLOSED, not merely HIDDEN (audit 2026-08-05). This used to prune on
        `is_alive`, which is also false for a CLOAKED window — and Windows
        cloaks every window sitting on another VIRTUAL DESKTOP, and Store apps
        while minimized. So the owner pressing Win+Ctrl+Right at his desk
        silently DELETED his layout, and its members — still on screen, still
        always-on-top — were forgotten by the only list that could have
        lowered them. Only a window that no longer exists is pruned now, and
        even that one is handed back clean on the way out."""
        for lay in self.layouts:
            alive = []
            for hwnd in lay.members:
                if wm.user32.IsWindow(hwnd):
                    alive.append(hwnd)
                else:
                    wm.drop_topmost(hwnd)
            lay.members = alive
            # A member that is gone takes its source record with it: the record
            # is what makes ANOTHER layout wear the ⭐, and a layout must never
            # be marked as the trunk of a branch it no longer holds.
            lay.sources = {h: s for h, s in lay.sources.items() if h in alive}
            # An ADOPTED window (task 202) that has been closed leaves the same
            # way a member does: off the list, and handed back through the
            # ledger so nothing of ours is left claiming it.
            still = []
            for hwnd in lay.adopted:
                if wm.user32.IsWindow(hwnd):
                    still.append(hwnd)
                else:
                    wm.drop_topmost(hwnd)
            lay.adopted = still
            if alive and lay.last_member not in alive:
                lay.last_member = alive[0]  # the typing target closed at the desk
        kept = [i for i, lay in enumerate(self.layouts) if lay.members]
        # A layout whose last member closed disappears — and it is exactly the
        # list that could still name the windows IT adopted, so they are handed
        # back here rather than left above the desk forever (constraint 10).
        for i, lay in enumerate(self.layouts):
            if i not in kept:
                lay.release_adopted()
        self.layouts = [self.layouts[i] for i in kept]
        return kept

    def create(self, target: int, mode: str, template: str | None,
               fill: list[int], orient: str, device_ratio: float,
               mon_rect: tuple[int, int, int, int], name: str | None = None,
               sources: dict[int, int] | None = None) -> tuple[int, bool] | None:
        """Arrange the windows and register the layout. Returns (index, all
        members verified on their rects), or None when the target window died
        between pick and create. device_ratio = the phone's short/long side
        ratio; the layout's chosen orientation turns it into the actual w/h
        aspect."""
        if not wm.is_alive(target):
            return None
        aspect = device_ratio if orient == "portrait" else 1.0 / device_ratio
        members = [target] + [h for h in fill if wm.is_alive(h) and h != target]
        placed = True
        template = wm.normalize_grid(template) if mode == "grid" else None
        if template:
            cells = wm._cells(wm.layout_region(wm._work_area(mon_rect), aspect),
                              template, orient)
            members = members[:len(cells)]
            for hwnd, cell in zip(members, cells):
                placed = wm.place_window(hwnd, cell) and placed
        else:
            template = None
            members = members[:1]
            placed = wm.place_window(
                target, wm.layout_region(wm._work_area(mon_rect), aspect))
        # `sources` = per member, the window whose TAB it was torn out of
        # (absent = a whole window); the project is LOGGED, so HIS log says
        # what the wheel will offer. Only the members that SURVIVED the
        # truncation above keep a record — a slot that never became a member
        # cannot make this layout anybody's trunk.
        kept = {h: s for h, s in (sources or {}).items() if h in members and s}
        title = wm._title(target) or ""
        name = name or title or "Window"
        first = kept.get(target, 0)
        folder = agents.first_folder([title, wm._title(first) if first else ""])
        logger.info("Layout %r from %#x (tab sources %s): title %r, project %r",
                    name, target, {f"{h:#x}": f"{s:#x}" for h, s in kept.items()},
                    title, folder)
        self.layouts.append(Layout(name, wm._process_name(target), members,
                                   template, orient, aspect,
                                   wm.icon_data_uri(wm._process_path(target)),
                                   kept, folder))
        # RECORDED, not merely built (owner report 2026-08-11, task 228 — the
        # "Recent" creation source): every successful create() is a row in
        # the persisted history, so it can be tapped back into being after a
        # restart. Best-effort and never fatal — `layout_history.record`
        # swallows its own errors — because a history write must not cost
        # him the layout he just asked for.
        layout_history.record(name, template, orient, folder, [
            {"process": wm._process_name(h), "title": wm._title(h) or ""}
            for h in members])
        return len(self.layouts) - 1, placed

    def focus(self, index: int, device_ratio: float,
              mon_rect: tuple[int, int, int, int]) -> tuple[dict, bool] | None:
        """Raise the layout's windows and return (FRESH monitor-normalized
        region to frame, every member verified on its rect). Re-arranges when
        the connecting device's aspect drifted from what the layout was built
        for (tablet vs phone — owner 2026-08-02). Returns None when the layout
        is gone (pruned). Members of every OTHER layout drop out of the
        topmost band — only what the phone shows is above the world.

        The drop pass runs FIRST, before any early return (audit 2026-08-05):
        it used to sit after them, so focusing a layout whose window had been
        closed at the desk returned None with the PREVIOUS layout still nailed
        above everything, and the phone then showed the desktop over it."""
        self.prune()
        for other in self.layouts:
            if 0 <= index < len(self.layouts) and other is self.layouts[index]:
                continue
            for hwnd in other.members:
                wm.drop_topmost(hwnd)
            # …and whatever that layout's work had opened goes with it (task
            # 202): the popup was above the world only for as long as the
            # phone was showing the layout it belongs to.
            other.release_adopted()
        if not 0 <= index < len(self.layouts):
            return None
        lay = self.layouts[index]
        placed = True
        aspect = device_ratio if lay.orient == "portrait" else 1.0 / device_ratio
        # WHERE THE MEMBERS BELONG — computed fresh on every focus. It is pure
        # arithmetic (grids.py), so asking is cheaper than remembering wrong.
        # ALWAYS CENTERED on the monitor (owner decree 2026-08-09, the Move
        # handle's FOURTH round): `lay.pos` used to slide this region along
        # the free axis, and three rounds of gates proved the windows moved —
        # on a screen the owner never sees. The server crops the region and
        # streams the same picture wherever the windows sit, so the position
        # that exists FOR HIM is where the letterboxed picture lands on the
        # phone; `pos` acts THERE now (client/view-anchor.js) and placement
        # here stopped following it.
        region = wm.layout_region(wm._work_area(mon_rect), aspect, lay.ratio)
        targets = (wm._cells(region, lay.template, lay.orient)[:len(lay.members)]
                   if lay.template else [region])
        members = lay.members[:len(targets)]
        # AND THE ARRANGEMENT IS VERIFIED, NEVER MERELY REMEMBERED (owner
        # 2026-08-07, the Move handle's second round: "uvek ostavi centrirano").
        # `arranged_ratio` alone used to be the guard, written from an
        # INTENTION before place_window was even called — so once a member
        # left its rect, every later Apply of the same ratio matched the
        # remembered value and re-placed NOTHING. A claim about windows is
        # MEASURED (the law layout_state already lives by, owner 2026-08-04).
        # A pos change is deliberately NOT a trigger: it re-places nothing
        # (see above) — the fresh `layout_state` the caller sends is what
        # carries it to the phone, whose view re-anchors on arrival.
        if (abs(aspect - lay.aspect) > 0.05 or lay.arranged_ratio != lay.ratio
                or lay.place_pending or not wm._standing(members, targets)):
            lay.aspect = aspect
            for hwnd, cell in zip(members, targets):
                placed = wm.place_window(hwnd, cell) and placed
            # Only an arrangement that LANDED is written down; a refusal
            # leaves the re-place order standing so the next focus tries again.
            lay.arranged_ratio = lay.ratio if placed else None
            lay.place_pending = not placed
            if not placed:
                logger.warning("Layout %r did not take its arrangement "
                               "(ratio=%s) — it will be retried",
                               lay.name, lay.ratio)
        # The member that holds the KEYBOARD is raised last, so it is the one
        # left in the foreground (owner 2026-08-06). Raising in plain list
        # order handed the keyboard to whatever sat last in the grid, and an
        # excursion — a picker, a permission dialog — re-focuses the layout on
        # every reconnect: his dictation resumed in the other window.
        order = [h for h in lay.members if h != lay.last_member]
        if lay.last_member in lay.members:
            order.append(lay.last_member)
        for hwnd in order:
            wm.raise_window(hwnd)
        self.last_focus = (index, lay.name)  # where the next session resumes
        if lay.template:
            # The union of the cells the members actually occupy — the same
            # `targets` that were just placed, never a second computation of
            # them (one source, so the frame can never disagree with the desk).
            x2 = max(c[0] + c[2] for c in targets)
            y2 = max(c[1] + c[3] for c in targets)
            region = (targets[0][0], targets[0][1],
                      x2 - targets[0][0], y2 - targets[0][1])
        else:
            region = wm._frame_rect(lay.members[0])
            if region is None:
                return None
        return wm._normalize(region, mon_rect), placed

    def minimize_members(self) -> None:
        """Desktop position (owner 2026-08-02): every window that belongs to
        ANY layout gets minimized — the full-desktop view shows the desktop
        and only the windows that are NOT layout material. Focusing a layout
        later restores its own members (place/raise SW_RESTORE)."""
        self.prune()
        members = [h for lay in self.layouts for h in lay.members]
        # The adopted windows (task 202) leave the topmost band with their
        # layout, but are NOT minimized: Desktop means "show me what is not
        # layout material", and a report the layout's work opened is exactly
        # the thing he chose Desktop to get to. Minimizing it here would be
        # the original failure again, in a new place.
        for lay in self.layouts:
            lay.release_adopted()
        for hwnd in members:
            wm.freeze_transitions(hwnd)  # no slide-down to watch
            # Out of the topmost band FIRST — a member the owner later restores
            # from the taskbar at the desk must come back as a normal window.
            # (drop_topmost gives its DWM animation back at the same time; the
            # freeze above only has to outlive this one minimize.)
            wm.drop_topmost(hwnd)
            wm.user32.ShowWindow(hwnd, wm.SW_MINIMIZE)
        # Only report Desktop once they are ALL really gone (owner 2026-08-03).
        wm.wait_minimized(members)

    def forget_focus(self) -> None:
        """The user DELIBERATELY chose the full desktop — that is the state the
        next session must resume into, so there is nothing to come back to."""
        self.last_focus = None

    def resume_index(self) -> int | None:
        """The layout a returning phone should land in (owner 2026-08-05), or
        None for the desktop. Both the index AND the name must still match —
        a list that changed while the phone was away resumes on the desktop
        rather than on the wrong window."""
        self.prune()
        if self.last_focus is None:
            return None
        index, name = self.last_focus
        if 0 <= index < len(self.layouts) and self.layouts[index].name == name:
            return index
        self.last_focus = None
        return None

    def rename(self, index: int, name: str) -> bool:
        """Owner-typed name (owner 2026-08-05). The auto name — the target
        window's title — is only the default; this replaces it for good."""
        name = name.strip()[:80]
        if not name or not 0 <= index < len(self.layouts):
            return False
        self.layouts[index].name = name
        if self.last_focus and self.last_focus[0] == index:
            self.last_focus = (index, name)  # keep the resume pointer valid
        return True

    def set_ratio(self, index: int, w: int, h: int, pos: float = 0.5) -> bool:
        """Store this layout's owner-chosen W:H (0/0 = back to the phone's own
        shape) and the free-axis anchor `pos` (0.5 = centered — the Move
        handle). The ratio is applied by the next focus, which re-places the
        windows; `pos` re-places NOTHING (owner decree 2026-08-09) — it rides
        the `layout_state` that same focus sends, and the PHONE anchors the
        letterboxed picture with it (client/view-anchor.js)."""
        if not 0 <= index < len(self.layouts):
            return False
        self.layouts[index].ratio = (w, h) if w > 0 and h > 0 else None
        self.layouts[index].pos = max(0.0, min(1.0, pos))
        return True

    def set_grid(self, index: int, grid: str, orient: str | None = None) -> bool:
        """This layout's grid ARRANGEMENT and/or orientation (owner 2026-08-07).

        His rule, exactly: a two- or four-window grid may change nothing but
        portrait/landscape, because there is only one sane way to cut a region
        into two or four. A THREE has four arrangements — the single window
        takes the top, bottom, left or right edge — and that choice belongs in
        the same panel as the name and the aspect. Only stored; the focus that
        follows re-places the windows."""
        if not 0 <= index < len(self.layouts):
            return False
        lay = self.layouts[index]
        wanted = wm.normalize_grid(grid)
        # A grid may only be re-arranged INTO A SHAPE OF THE SAME SIZE. Asking
        # a three-window layout to become a "4" would leave a cell with no
        # window in it, and asking a four to become a "2" would orphan two.
        if wanted and lay.template and wm.GRID_CELLS[wanted] == len(lay.members):
            lay.template = wanted
        if orient in ("portrait", "landscape"):
            lay.orient = orient
        lay.place_pending = True   # force the next focus to re-place, always
        return True

    @staticmethod
    def _template_for(count: int, wanted: str | None = None) -> str | None:
        """The shape a layout of `count` windows must wear. `wanted` is the
        phone's own choice and is honoured whenever it FITS; anything else
        falls back to the only sane shape for that size.

        The catalogue is the owner's sheet (2026-08-07, UV/grid_variations.png)
        and its asymmetry is the reason this is one function: a TWO and a FOUR
        have exactly one arrangement each, so there is nothing to ask about,
        and a THREE has four — which is why `wanted` exists at all. A three
        with no answer defaults to a bar along the top, the first drawing on
        his sheet.

        One definition, used by every path that changes a layout's size —
        `merge` growing one and `drop_member` shrinking one — so the two can
        never disagree about what a three is."""
        if count <= 1:
            return None                       # solo: no grid at all
        wanted = wm.normalize_grid(wanted)
        if wanted and wm.GRID_CELLS[wanted] == count:
            return wanted
        return {2: "2", 3: "3-top", 4: "4"}[min(count, 4)]

    def drop_member(self, index: int, member: int,
                    grid: str | None = None) -> str:
        """Throw ONE window out of a grid — a four becomes a three, a three a
        two, a two a single (owner request 2026-08-09, task 164/165: "there
        must be a button by which I can throw one member out of the grid").
        Until today a grid could only be BUILT (`merge`) or removed WHOLE, so
        the only way to lose one window of four was to delete the layout and
        make it again.

        `member` is the ORDINAL of the window inside `members`, never a
        handle: the phone is never told a handle, and it picks by pointing at
        a CELL of the drawing — cell k is member k (see client/grid-icons.js).

        THE WINDOW IS NEVER CLOSED. Only the ✕ chooser closes windows, and
        only when he explicitly asked for that act (2026-08-08, task 116).
        The one that leaves simply stops being layout material: out of the
        topmost band, because a window we raised must never be stranded above
        everything (constraint 10 — the LEDGER exists for exactly this), and
        with its normal minimize/restore animation given back. Where it sits
        on screen is left alone, the same rule `remove` follows — no window is
        ever moved by us without being asked to be.

        Removing the LAST member is removing the layout, and it goes through
        `remove()` rather than a second teardown of its own.

        Returns "gone" (nothing matched — say so), "removed" (the layout is
        no more) or "dropped" (it survives, one window smaller). The survivors
        are re-placed by the focus that follows: `place_pending` makes it
        unconditional, because the shape changed even where every window
        still happens to stand on a rect of the old one."""
        if not 0 <= index < len(self.layouts):
            return "gone"
        lay = self.layouts[index]
        if not 0 <= member < len(lay.members):
            return "gone"
        if len(lay.members) <= 1:
            self.remove(index)
            return "removed"
        hwnd = lay.members.pop(member)
        # Its source record leaves with it: the record is what makes the window
        # it was torn OUT of wear the ⭐ (task 169) and what the ✕ chooser's
        # warning is built from (task 171). A layout that no longer holds the
        # branch must stop making anybody its trunk.
        lay.sources.pop(hwnd, None)
        # Back to being an ordinary desktop window, in this order: the
        # animation first, then out of the topmost band (drop_topmost is what
        # takes it off the ledger, so nothing can strand it up there).
        wm.freeze_transitions(hwnd, False)
        wm.drop_topmost(hwnd)
        if lay.last_member == hwnd:
            # The phone was typing into the window that just left. The
            # keyboard goes to the first survivor rather than to nothing —
            # `focus` raises `last_member` LAST, and a handle no longer in
            # the list would leave the raise order pointing at a stranger.
            lay.last_member = lay.members[0]
        lay.template = self._template_for(len(lay.members), grid)
        lay.place_pending = True
        logger.info("Layout %r dropped member %d (%#x): now %d window(s), %s",
                    lay.name, member, hwnd, len(lay.members),
                    lay.template or "solo")
        return "dropped"

    def add_member(self, index: int, hwnd: int, source: int = 0,
                  grid: str | None = None) -> str:
        """Grow a layout by ONE window — solo→2, 2→3, 3→4 (owner request,
        task 195, in translation: "add a member to an existing layout, if
        there is room ... unless it already has four"). The mirror of
        `drop_member`: the same `_template_for` decides the new shape, so
        growing and shrinking a layout can never disagree about what a three
        is. `hwnd` has already been resolved by `layout_api.resolve_slot` —
        a tab slot is torn into its own window there, exactly as a creation
        slot is — so this only ever files a whole window.

        Returns "gone" (layout or window gone), "full" (already four —
        nothing to add to), "duplicate" (already a member of THIS or ANY
        other layout — one window belongs to exactly one layout, the same
        rule `member_hwnds` enforces on the creation list) or "added". The
        caller re-places through `focus()`, which is what puts the new
        member on the topmost ledger — the same path every member joins it
        through, never a special case here."""
        if not 0 <= index < len(self.layouts):
            return "gone"
        lay = self.layouts[index]
        if len(lay.members) >= 4:
            return "full"
        if not wm.is_alive(hwnd):
            return "gone"
        if any(hwnd in other.members for other in self.layouts):
            return "duplicate"
        lay.members.append(hwnd)
        if source:
            lay.sources[hwnd] = source
        lay.template = self._template_for(len(lay.members), grid)
        lay.place_pending = True
        logger.info("Layout %r gained member %#x: now %d window(s), %s",
                    lay.name, hwnd, len(lay.members), lay.template or "solo")
        return "added"

    def split(self, index: int) -> list[int] | None:
        """Break a grid into as many SOLO layouts as it has members — one
        per window (owner request, task 197a: "decompose a grid into several
        individual layouts"). Each new Layout keeps ITS OWN source record
        (task 173's whole reason for keying `sources` per member rather than
        once per layout), so the ⭐/dependents a window carried inside the
        grid survive it splitting apart.

        Replaces the source layout in place, in member order, so the new
        layouts land where it stood in the list rather than at the end.
        Returns the new layouts' indices, or None when the layout is gone or
        already solo (nothing to split)."""
        if not 0 <= index < len(self.layouts):
            return None
        lay = self.layouts[index]
        if len(lay.members) < 2:
            return None
        made: list[Layout] = []
        for hwnd in lay.members:
            title = wm._title(hwnd) or ""
            src = lay.sources.get(hwnd, 0)
            src_title = wm._title(src) if src else ""
            made.append(Layout(
                title or lay.name, wm._process_name(hwnd), [hwnd], None,
                lay.orient, lay.aspect, wm.icon_data_uri(wm._process_path(hwnd)),
                {hwnd: src} if src else None,
                agents.first_folder([title, src_title]) or lay.folder))
        self.layouts[index:index + 1] = made
        if self.last_focus and self.last_focus[0] == index:
            self.last_focus = None   # the layout it named is gone
        logger.info("Layout %r split into %d solo layouts", lay.name, len(made))
        return list(range(index, index + len(made)))

    def eject_member(self, index: int, member: int,
                     grid: str | None = None) -> str:
        """Pull ONE member out of a grid into ITS OWN new layout — never to
        the desktop (owner request, task 197b, contrasted with the existing
        "Take one window out" / `drop_member`, which leaves the window
        standing as plain desktop material). `member` is the cell ordinal,
        the same convention `drop_member` and `layout_member_remove` use.

        The survivors are re-shaped by `_template_for` exactly as
        `drop_member` shapes them — `grid` names the arrangement a four
        landing on a three should take. The ejected window drops out of the
        topmost band here (it is no longer part of the FOCUSED layout) but
        is NOT unfrozen and NOT handed back to the desk: it stays layout
        material, and the focus that later shows its new layout raises it
        again exactly like any other member.

        Returns "gone" (nothing matched, or the layout has only one member —
        there is nothing to eject FROM) or "ejected"."""
        if not 0 <= index < len(self.layouts):
            return "gone"
        lay = self.layouts[index]
        if not 0 <= member < len(lay.members) or len(lay.members) <= 1:
            return "gone"
        hwnd = lay.members.pop(member)
        src = lay.sources.pop(hwnd, 0)
        wm.drop_topmost(hwnd)   # no longer part of the layout the phone shows
        if lay.last_member == hwnd:
            lay.last_member = lay.members[0]
        lay.template = self._template_for(len(lay.members), grid)
        lay.place_pending = True
        title = wm._title(hwnd) or ""
        src_title = wm._title(src) if src else ""
        solo = Layout(title or "Window", wm._process_name(hwnd), [hwnd], None,
                      lay.orient, lay.aspect, wm.icon_data_uri(wm._process_path(hwnd)),
                      {hwnd: src} if src else None,
                      agents.first_folder([title, src_title]) or "")
        self.layouts.append(solo)
        logger.info("Layout %r ejected member %d (%#x) into new layout %r",
                    lay.name, member, hwnd, solo.name)
        return "ejected"

    def merge(self, source: int, target: int, grid: str | None = None) -> bool:
        """Drag one layout's window onto another and they become a GRID (owner
        2026-08-07, "like holding a file in Explorer and dragging it into a
        folder" — his words: "kao kada u eksploreru držiš fajl", lang-ok: owner quote).
        The source layout DISAPPEARS — his answer to the first
        question, and the only one consistent with the standing rule that a
        window belongs to exactly one layout.

        Sizes: 1+1 -> 2, 1+2 -> 3 (he picks which of the four arrangements),
        1+3 -> 4 (no choice exists, so none is offered). A full four refuses,
        which is why the phone greys it while a drag is in flight."""
        if not (0 <= source < len(self.layouts) and 0 <= target < len(self.layouts)):
            return False
        if source == target:
            return False
        src, dst = self.layouts[source], self.layouts[target]
        members = dst.members + [h for h in src.members if h not in dst.members]
        if len(members) > 4 or len(members) < 2:
            return False
        # The phone may name a shape; one of the wrong size (or none at all)
        # falls back to the only sane default for this count — see
        # `_template_for`, which `drop_member` shrinks a layout by too, so
        # growing and shrinking can never disagree about what a three is.
        dst.members = members
        # The dragged layout's source records travel with its windows — the
        # source layout is about to disappear, and a branch that loses its
        # record silently un-stars its own trunk.
        dst.sources = {h: s for h, s in {**dst.sources, **src.sources}.items()
                       if h in members}
        # The dragged layout is about to disappear, so anything ITS work had
        # opened (task 202) is inherited rather than orphaned — the windows
        # are the same windows, in the same picture, and the list that owes
        # them the way out of the topmost band must not be the one popped.
        dst.adopted += [h for h in src.adopted if h not in dst.adopted]
        src.adopted = []
        dst.template = self._template_for(len(members), grid)
        dst.place_pending = True    # the shape changed — re-place on focus
        self.layouts.pop(source)
        if self.last_focus and self.last_focus[0] == source:
            self.last_focus = None
        return True

    def reorder(self, source: int, before: int) -> bool:
        """Move a layout to another position in the list (owner 2026-08-07:
        dropping BETWEEN two rows reorders, dropping ON a row makes a grid —
        the Explorer-drag comparison quoted under `merge`). Nothing on the PC
        moves."""
        if not 0 <= source < len(self.layouts):
            return False
        before = max(0, min(len(self.layouts), before))
        lay = self.layouts.pop(source)
        if before > source:
            before -= 1
        self.layouts.insert(before, lay)
        self.last_focus = None      # the indices it pointed at just moved
        return True

    def member_hwnds(self) -> set[int]:
        """Every window that already belongs to SOME layout — the creation
        list hides them (owner 2026-08-03: one window cannot be shown twice)."""
        self.prune()
        return {h for lay in self.layouts for h in lay.members}

    def remove(self, index: int, close: bool = False) -> list[int]:
        """Deleting a layout leaves the desktop exactly as it is (owner rule —
        no auto-return of windows). Its windows get their normal Windows
        minimize/restore animation back — we only froze it while they were
        layout material — and leave the topmost band.

        `close=True` is the owner's SECOND act (2026-08-08, task 116): the
        same removal, plus every member window is asked to close for real.
        "Brisanje layouta ga samo obrise iz nase liste ali ostavlja prozor na
        desktopu. Nekad hocemo to, a nekad hocemo bas da zatvorimo sve tu."
        (lang-ok: owner quote)

        The flag DEFAULTS to the harmless act on purpose. Two different things
        wore one button until today, and of the two only one cannot be undone;
        a page from before this round — or a message that lost the field on
        the way — must land on the one that leaves his windows alone.

        Returns the members that are still standing, which is empty for a
        plain removal and, after a close, the ones asking about unsaved work.
        The caller tells the phone; see `close_windows`."""
        alive: list[int] = []
        if 0 <= index < len(self.layouts):
            # Whatever this layout's work opened stops being ours first (task
            # 202) — and is never closed with the members: `close` is the act
            # he asked for on the windows he chose, and a popup he never
            # listed is not one of them.
            self.layouts[index].release_adopted()
            members = list(self.layouts[index].members)
            if close:
                # close_windows drops topmost and unfreezes each window itself
                # — it must do that BEFORE posting, so it owns both halves.
                alive = wm.close_windows(members)
            else:
                for hwnd in members:
                    wm.freeze_transitions(hwnd, False)
                    wm.drop_topmost(hwnd)
            del self.layouts[index]
            # The resume pointer rides on INDICES — the removed one is gone,
            # every higher one shifted down by one.
            if self.last_focus is not None:
                last, name = self.last_focus
                self.last_focus = (None if last == index
                                   else (last - 1, name) if last > index
                                   else (last, name))
        return alive

    def clear_topmost(self) -> None:
        """Every window back to the normal z-band — the phone hung up, nothing
        is being shown, no window may stay always-on-top at the desk.

        Goes through the LEDGER, not through the member lists: a window that
        fell out of its layout (closed, cloaked, extracted as a tab) is
        exactly the one no member list can still name, and exactly the one
        that used to stay stranded up there."""
        wm.release_all()

    def state(self, active: int | None, region: dict | None) -> dict:
        """The layout_state payload. Prune first so the phone never lists a
        dead layout — and FOLLOW the focused layout through that prune.

        The focus used to be a bare index, so closing a window at the desk
        slid the list down under it and the phone was suddenly focused on —
        and one X away from removing — a layout it had never chosen (audit
        2026-08-05). `prune` returns the surviving original indices, which is
        exactly the map the focus needs."""
        kept = self.prune()
        # One process-table snapshot for every layout in the frame, not one
        # per layout (owner 2026-08-07 — see agents.agents_in).
        live = agents.live_agents()
        if active is not None:
            active = kept.index(active) if active in kept else None
            if active is None:
                region = None
        if active is not None and not 0 <= active < len(self.layouts):
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
        owners = [(lay, src) for lay in self.layouts for src in lay.sources.values()]
        dependents = {
            id(lay): [other.name for other, src in owners
                      if other is not lay and src in lay.members
                      and (other.process or "").lower() in PARENT_CLOSE_APPS]
            for lay in self.layouts}
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
                        for lay in self.layouts],
            "active": active,
            "region": region,
            "orient": self.layouts[active].orient if active is not None else None,
        }
