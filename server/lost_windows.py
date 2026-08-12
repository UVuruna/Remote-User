"""A window nobody can reach is ALWAYS offered a way back — whoever opened it.

WHY THIS MODULE EXISTS (owner report, the FIFTH on one failure, 2026-08-12).
His words, quoted because the fifth report of one bug is itself evidence:

    lang-ok-begin: owner quote — the sentence this module is built from
    "ako mi je telefon bio zaključan ... a desio se pop up prozor ... taj HTML
     stoji na desktopu negde van dimenzija prozora i više nikada ne mogu da ga
     prikažem ... to je game breaking bag"
    lang-ok-end

An agent finished a job while his phone was LOCKED and opened its HTML report.
It landed outside every screen. He can never bring it back: there is no
taskbar on the phone, the window is not on any monitor, and nothing in this
codebase could move a window it had not itself placed.

## Why four rounds of fixing [Layout Popup](layout_popup.py) never reached it

That module is the right answer to the window that opens WHILE HE WATCHES, and
it is built on `baseline(conn)`: every window standing when the phone connects
is filed as KNOWN, so `_is_new()` answers False for it forever. That is
correct there — it is what stops a layout adopting his second VS Code window.

But it makes the locked-phone case STRUCTURALLY invisible:

    phone locked  -> no connection -> no watcher -> nobody sees it open
    he unlocks    -> a NEW connection -> baseline finds it standing -> "old"

The window born during his absence can never be new. Every round fixed the
LIVE path, and the live path was never the one he was reporting.

## So this module asks a different question, and it is the question that works

Not *who opened this window* — HISTORY, which we do not have — but

    **can he reach it at all?**

which is GEOMETRY, measured now, needing no baseline, no attribution, no
process table and no memory of anything. It therefore answers for a window
opened by an agent, by Windows, by his own PC hours before the phone ever
connected, or by us. There is no case it cannot see.

The two halves of the failure are the two halves of this module:

* `lost()` — which windows are unreachable, measured against the real work
  areas of the real monitors;
* `rescue()` — the thing that had never existed anywhere in this codebase:
  moving a window we did not place, back onto a screen.

## The rules it holds itself to

* **A minimized window is judged by where it would RESTORE to.** Windows keeps
  that rect (`GetWindowPlacement.rcNormalPosition`) and it is the whole reason
  the report survived his desktop switch: the layout minimize took it down
  with its owner, and restoring it would have put it straight back off-screen.
  A minimized window whose normal position is fine is NOT lost — the taskbar
  reaches it, and so does the phone once he shows the desktop.
* **Reachable means GRABBABLE, not visible.** A window is reachable when a
  usable piece of its TITLE BAR lies inside some monitor's work area — that is
  what a person needs to drag it back. A sliver of its bottom-right corner
  showing at a screen edge is not a way out, and treating it as one is exactly
  how he ended up reporting this five times.
* **Layout members are never lost.** The layout put them where they are and
  the layout can move them; offering to rescue them would fight it.
* **Nothing moves until he taps.** This module only ever ANSWERS a question
  and performs a rescue he asked for. It raises nothing into the always-on-top
  band (constraint 10: `raise_window(topmost=False)`), so a rescued window is
  a normal window standing on his desk.
* **A rescue lands on the monitor the PHONE IS WATCHING**, passed in live
  rather than remembered — constraint 13's lesson: a note of which monitor was
  being streamed is wrong the moment he switches.
"""

import ctypes
import ctypes.wintypes as wintypes
import logging

import window_manager as wm

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

SW_RESTORE = 9
SW_SHOW = 5

# ═══════════════════════════ CONFIG ═══════════════════════════
# How much of a window's title bar must stand inside a work area for a person
# to be able to drag it back. Both numbers are about a HAND, not about pixels
# being technically visible: a 20 px sliver of title bar at the screen edge is
# not a handle, and calling it one is the bug.
GRAB_WIDTH_PX = 120
# The strip of the window's top edge that IS the title bar, near enough. Real
# title bars run ~30-40 px; asking for less than a full one keeps a window
# whose caption is half off the top edge — still draggable — off the list.
TITLE_HEIGHT_PX = 20
# Space left around a rescued window inside the work area, so it never lands
# flush against an edge and never covers the whole screen.
RESCUE_MARGIN_PX = 40


# ═══════════════════════════ WHERE THE SCREENS ARE ═══════════════════════════
class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


_MonitorEnumProc = ctypes.WINFUNCTYPE(
    wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
    ctypes.POINTER(wintypes.RECT), wintypes.LPARAM,
)


def work_areas() -> list[tuple[int, int, int, int]]:
    """Every monitor's WORK area (taskbar excluded) as (x, y, w, h).

    The work area and not the full monitor rect, deliberately: a window whose
    only on-screen part sits under the taskbar is not reachable either, and
    that is a real place for a stray window to hide."""
    out: list[tuple[int, int, int, int]] = []

    @_MonitorEnumProc
    def callback(hmonitor, _hdc, _rect, _lparam):
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            w = info.rcWork
            out.append((w.left, w.top, w.right - w.left, w.bottom - w.top))
        return True

    user32.EnumDisplayMonitors(None, None, callback, 0)
    return out


# ═══════════════════════════ IS IT REACHABLE ═══════════════════════════
def _overlap(a: tuple[int, int, int, int],
             b: tuple[int, int, int, int]) -> tuple[int, int]:
    """(width, height) of the intersection of two rects — zeros when apart."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    w = min(ax + aw, bx + bw) - max(ax, bx)
    h = min(ay + ah, by + bh) - max(ay, by)
    return (max(0, w), max(0, h))


def reachable(rect: tuple[int, int, int, int],
              areas: list[tuple[int, int, int, int]]) -> bool:
    """Can a person GRAB this window and drag it back?

    Pure, so the gate can drive it with rects instead of real windows — which
    is the only way to test a bug whose whole nature is a window nobody can
    put on a screen.

    The test is the TITLE BAR, not the window: a window is reachable when at
    least `GRAB_WIDTH_PX` x `TITLE_HEIGHT_PX` of its top strip lies inside one
    work area. Summing pieces across two monitors is deliberately NOT done —
    two 60 px halves on either side of a gap are not a 120 px handle."""
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return False
    strip = (x, y, w, min(h, TITLE_HEIGHT_PX))
    need_w = min(GRAB_WIDTH_PX, w)
    need_h = min(TITLE_HEIGHT_PX, h)
    for area in areas:
        ow, oh = _overlap(strip, area)
        if ow >= need_w and oh >= need_h:
            return True
    return False


class _WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [("length", wintypes.UINT), ("flags", wintypes.UINT),
                ("showCmd", wintypes.UINT), ("ptMinPosition", wintypes.POINT),
                ("ptMaxPosition", wintypes.POINT),
                ("rcNormalPosition", wintypes.RECT)]


def resting_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Where this window IS — or, when it is minimized, where it would come
    back to.

    THE MINIMIZED CASE IS THE OWNER'S CASE, not an edge case. His report window
    went down with the layout it was owned by, so by the time he looked it was
    minimized; a check that skipped minimized windows would have found nothing
    wrong, and restoring it would have put it straight back off the screen.
    `GetWindowPlacement.rcNormalPosition` is where Windows will put it, so it
    is what must be judged."""
    if not user32.IsWindow(hwnd):
        return None
    if user32.IsIconic(hwnd):
        wp = _WINDOWPLACEMENT()
        wp.length = ctypes.sizeof(_WINDOWPLACEMENT)
        if not user32.GetWindowPlacement(hwnd, ctypes.byref(wp)):
            return None
        r = wp.rcNormalPosition
        return (r.left, r.top, r.right - r.left, r.bottom - r.top)
    return wm._frame_rect(hwnd)


# ═══════════════════════════ THE LIST ═══════════════════════════
def lost(exclude: set[int] | None = None) -> list[dict]:
    """Every window a person cannot reach, in enumeration order.

    `exclude` is the layout's own windows: they are where the layout put them
    and the layout can move them, so offering a rescue there would fight it.

    Blocking Win32 (EnumWindows plus a placement read per window) — every
    caller runs it on a worker thread."""
    areas = work_areas()
    if not areas:
        return []                   # no screens: nothing to be lost FROM
    skip = exclude or set()
    out: list[dict] = []
    for win in wm.list_windows():
        hwnd = win["hwnd"]
        if hwnd in skip:
            continue
        rect = resting_rect(hwnd)
        if rect is None or reachable(rect, areas):
            continue
        out.append({**win, "rect": rect,
                    "minimized": bool(user32.IsIconic(hwnd))})
    return out


# ═══════════════════════════ THE WAY BACK ═══════════════════════════
def _target(rect: tuple[int, int, int, int],
            area: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Where a rescued window should land: its own size where that fits, the
    work area minus a margin where it does not, centered either way.

    Pure, so the gate can check the arithmetic without a screen. Its own size
    is kept wherever possible on purpose — a dialog blown up to fill a monitor
    is a second surprise on top of the first."""
    _, _, w, h = rect
    ax, ay, aw, ah = area
    max_w = max(1, aw - 2 * RESCUE_MARGIN_PX)
    max_h = max(1, ah - 2 * RESCUE_MARGIN_PX)
    w = max(1, min(w, max_w))
    h = max(1, min(h, max_h))
    return (ax + (aw - w) // 2, ay + (ah - h) // 2, w, h)


def _work_area_of(mon_rect: tuple[int, int, int, int] | None
                  ) -> tuple[int, int, int, int] | None:
    """The work area of the monitor the phone is WATCHING. `None` — nobody
    told us — falls back to the first enumerated work area rather than to
    nothing: a rescue onto the wrong screen is recoverable, a rescue that
    refuses to run is the bug this module exists for."""
    if mon_rect is not None:
        return wm._work_area(mon_rect)
    areas = work_areas()
    return areas[0] if areas else None


def rescue(hwnd: int, mon_rect: tuple[int, int, int, int] | None) -> bool:
    """Bring one window back onto the screen the phone is watching.

    THE FIRST CODE IN THIS PROJECT THAT MOVES A WINDOW IT DID NOT PLACE, and
    it runs only on his own tap. Restore FIRST, then place: a minimized window
    takes `SetWindowPos` geometry into its placement without coming back, so
    placing first would look like it worked and change nothing he can see.

    Raised WITHOUT topmost (constraint 10). A rescued window is a normal
    window on his desk, not a member of anything — and the ledger exists
    precisely because a topmost raise here would strand it above everything
    for the rest of the Windows session."""
    if not user32.IsWindow(hwnd):
        return False
    area = _work_area_of(mon_rect)
    if area is None:
        logger.error("Cannot rescue %s — no monitor work area", hwnd)
        return False
    rect = resting_rect(hwnd)
    if rect is None:
        return False
    wm.freeze_transitions(hwnd)
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    elif not user32.IsWindowVisible(hwnd):
        user32.ShowWindow(hwnd, SW_SHOW)
    target = _target(rect, area)
    ok = wm.place_window(hwnd, target)
    # RAISED EVEN IF THE PLACEMENT REFUSED. A window that would not take the
    # rect may still have been restored out of the taskbar, and putting it in
    # front is the half of the rescue that can still succeed.
    wm.raise_window(hwnd, topmost=False)
    if not ok:
        logger.error("Rescue of %s: placement to %s refused — it was restored "
                     "and raised, but may still be off-screen",
                     wm._title(hwnd)[:60], target)
        return False
    logger.info("Rescued %s from %s to %s", wm._title(hwnd)[:60], rect, target)
    return True
