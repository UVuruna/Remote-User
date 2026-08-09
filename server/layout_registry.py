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
import window_manager as wm

logger = logging.getLogger(__name__)


class Layout:
    """One phone screen: member windows + the orientation/aspect it was built
    for. Members are ordered — grid cell order for grids, [window] for solo."""

    def __init__(self, name: str, process: str, members: list[int],
                 template: str | None, orient: str, aspect: float,
                 icon: str | None = None, source: int = 0, folder: str = ""):
        self.name = name
        self.process = process
        # WHERE this layout's project is READ FROM — never the answer itself.
        # `source` is the window an extracted tab was torn out of (0 = none);
        # `folder` is the project its title named at creation, the last resort
        # for when that window is gone. This used to be the window's TITLE,
        # frozen — see `project()` and __about/window_manager.md.
        self.source = source
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
        self.ratio: tuple[int, int] | None = None
        self.pos: float = 0.5
        self.arranged_ratio: tuple[int, int] | None = None
        self.place_pending: bool = False

    def project(self) -> str:
        """The project folder this layout's window belongs to, MEASURED every
        call — an extracted tab's own window can be titled bare `Visual Studio
        Code`, so the window it was torn OUT of is asked next, live. `folder`
        is the last resort (that source closed): a FOLDER is not an answer —
        what is LIVE in it comes from the process table, every frame."""
        seen = [h for h in (self.members[0] if self.members else 0, self.source)
                if h and wm.is_alive(h)]
        return agents.first_folder(wm._title(h) for h in seen) or self.folder


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
            if alive and lay.last_member not in alive:
                lay.last_member = alive[0]  # the typing target closed at the desk
        kept = [i for i, lay in enumerate(self.layouts) if lay.members]
        self.layouts = [self.layouts[i] for i in kept]
        return kept

    def create(self, target: int, mode: str, template: str | None,
               fill: list[int], orient: str, device_ratio: float,
               mon_rect: tuple[int, int, int, int], name: str | None = None,
               source: int = 0) -> tuple[int, bool] | None:
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
        # `source` = the window a tab was torn out of (0 = whole window); the
        # project is LOGGED, so HIS log says what the wheel will offer.
        title = wm._title(target) or ""
        name = name or title or "Window"
        folder = agents.first_folder([title, wm._title(source) if source else ""])
        logger.info("Layout %r from %#x (tab source %#x): title %r, project %r",
                    name, target, source, title, folder)
        self.layouts.append(Layout(name, wm._process_name(target), members,
                                   template, orient, aspect,
                                   wm.icon_data_uri(wm._process_path(target)),
                                   source, folder))
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
            for hwnd in other.members:
                if not (0 <= index < len(self.layouts)) or other is not self.layouts[index]:
                    wm.drop_topmost(hwnd)
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
        wanted = wm.normalize_grid(grid)
        if not wanted or wm.GRID_CELLS[wanted] != len(members):
            # The phone did not name a shape, or named one of the wrong size:
            # take the only sane default for this count. Three defaults to a
            # bar along the top, which is the first drawing on his sheet.
            wanted = {2: "2", 3: "3-top", 4: "4"}[len(members)]
        dst.members = members
        dst.template = wanted
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
                         "grid": lay.template,
                         "members": len(lay.members),
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
