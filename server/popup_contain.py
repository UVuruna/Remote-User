"""WHERE an adopted window is put, so the phone can operate it.

Split out of `layout_popup.py` on 2026-08-18 (THE STRUCTURE LAW, VC-R5). Its
one responsibility is the owner's own ladder (2026-08-11, amended 2026-08-13):
on its parent if we know it, else inside the layout's region, else full screen
over the streamed monitor. WHOSE window it is and whether to ask him are
decided next door; by the time anything here runs, that is settled.

MEASURED, never remembered (constraint 13): the region is the union of the
members' real frame rects read fresh, the popup's own frame is read fresh, and
"it cannot fit" is what a window REFUSING the region looks like from here —
never a size we predicted.
"""

import logging

import window_manager as wm
from grids import PLACE_TOLERANCE_PX

logger = logging.getLogger(__name__)

# How many times we try to contain ONE window before leaving it where it is.
# A window that refuses every rect we command (a fixed-size tool window, a
# process at a higher integrity level) must not be fought four times a second
# for the rest of the session.
MAX_CONTAIN_TRIES = 3


def _region(lay) -> tuple[int, int, int, int] | None:
    """The rect the phone is really framing: the union of the members' visible
    frames, MEASURED now. Not the region `focus()` computed — that one is what
    was COMMANDED, and a note of an intention is exactly what constraint 13
    was written about."""
    rects = [wm._frame_rect(h) for h in lay.members
             if wm.user32.IsWindow(h) and not wm.user32.IsIconic(h)]
    rects = [r for r in rects if r]
    if not rects:
        return None
    x1 = min(r[0] for r in rects)
    y1 = min(r[1] for r in rects)
    x2 = max(r[0] + r[2] for r in rects)
    y2 = max(r[1] + r[3] for r in rects)
    if x2 - x1 <= 0 or y2 - y1 <= 0:
        return None
    return (x1, y1, x2 - x1, y2 - y1)


def _inside(rect, region) -> bool:
    x, y, w, h = rect
    rx, ry, rw, rh = region
    t = PLACE_TOLERANCE_PX
    return (x >= rx - t and y >= ry - t
            and x + w <= rx + rw + t and y + h <= ry + rh + t)


def describe(hwnd: int) -> str:
    return f'{wm._process_name(hwnd) or "?"} "{wm._title(hwnd)[:60]}" ({hwnd:#x})'


def _centered_in(rect, box):
    """`rect`'s own size, centered in `box` — or None when it cannot fit."""
    _, _, w, h = rect
    bx, by, bw, bh = box
    if w > bw or h > bh:
        return None
    return (bx + (bw - w) // 2, by + (bh - h) // 2, w, h)


def contain(lay, hwnd: int, conn: dict, anchor=None) -> bool:
    """Put this window where the phone can operate it. Returns whether it
    ended up inside the streamed picture.

    The branches are the owner's own sentences, and which one applies is
    MEASURED, never assumed:

    * `anchor` — the window this popup BELONGS to, when we know it (his rule of
      2026-08-13: a popup belongs in the middle of its parent application). It
      is tried first and at the popup's own size, because a dialog centered on
      the app that raised it is where the app itself would have put it if
      Windows had let it.
    * it FITS the region — placed inside it, at its own size, centered. A
      dialog stretched to fill a whole layout would be a worse answer than the
      one Windows gave.
    * it does NOT fit — asked to take the region anyway (a resizable window
      simply obeys, and that is still the first answer), and only when it
      REFUSES, which is what a minimum size larger than the region looks like
      from here, does it go full screen over the streamed monitor.

    The anchor is a PREFERENCE and never a promise: a dialog larger than the
    one quadrant its parent occupies still lands in the region, which is still
    inside the picture. Falling through is the feature, not a failure."""
    region = _region(lay)
    rect = wm._frame_rect(hwnd) if wm.user32.IsWindow(hwnd) else None
    if region is None or rect is None:
        return False
    if _inside(rect, region) and (anchor is None or _inside(rect, anchor)):
        return True

    tries = conn.setdefault("popup_tries", {})
    tries[hwnd] = tries.get(hwnd, 0) + 1
    if tries[hwnd] > MAX_CONTAIN_TRIES:
        return False

    if anchor is not None:
        target = _centered_in(rect, anchor)
        if target and wm.place_window(hwnd, target):
            return True
    target = _centered_in(rect, region)
    if target and wm.place_window(hwnd, target):
        return True
    if wm.place_window(hwnd, region):
        return True
    # It cannot be made to fit, so it opens separate over the whole screen —
    # the full work area of the monitor the members stand on, which is the
    # monitor being streamed.
    full = wm._work_area(region)
    if wm.place_window(hwnd, full):
        logger.info("Popup %s could not fit the layout region %s — opened "
                    "full screen on %s", describe(hwnd), region, full)
        return True
    logger.error("Popup %s would take NEITHER the layout region %s NOR the "
                 "full screen %s — it stays where Windows put it",
                 describe(hwnd), region, full)
    return False


# ═══════════════════ THE PARENT'S OWN POPUP ═══════════════════
# OWNER REPORT 2026-08-13, and he had to correct the whole previous round to
# get here. What actually happens to him is not "a window opened while I was
# away" — it is this:
# lang-ok-begin: owner quote — the sentence this section is built from
#   "nekada ja otvaram aplikaciju kada aplikacija otvara aplikaciju"
#   "Dakle kada se otvori popup WINDOWS ga baci VAN GRANICA NAŠEG PROZORA"
#   "Rješenje je da se taj POPUP od MATIČNE APLIKACIJE PRIKAZUJE U NJENOJ
#    SREDINI"
# lang-ok-end
#
# An agent working in a layout's VS Code opens a report, a "Record a shortcut"
# window, a permission dialog. Windows centers such a window on its parent's
# *restored* geometry or on the last place that app used — neither of which is
# the quarter of the screen the layout just moved the parent into. The popup
# lands outside the region, under the members' always-on-top band, and there is
# no taskbar on a phone.
#
# WHY THIS ONE IS NOT A QUESTION. Every other rule in this module is a guess
# about WHOSE window this is, and a wrong guess would move a stranger's window
# — which is why they all end in a chip he taps. The owner chain is not a
# guess: Windows itself says this window was raised BY that member, takes it
# down when the member minimizes, and closes it when the member closes. Asking
# permission to put an application's own dialog on top of that application is
# asking him to confirm what the application already decided. So rule 1 places,
# and rules 2-4 still ask.
#
# IT IS THE PARENT AND NOT THE REGION. A layout of four holds four windows; a
# VS Code dialog belongs on the VS Code, not floating in the middle of a grid
# over three windows it has nothing to do with. `_contain`'s ladder falls back
# to the region and then to the full screen when the dialog is simply too big
# for one cell, so the guarantee — it is inside the picture — never depends on
# the anchor succeeding.


def adopt_owned(lay, hwnd: int, root: int, conn: dict) -> bool:
    """A member's OWN popup: put it on the member, now, without asking.

    Returns whether it was handled here (so the caller offers nothing). The
    LEDGER is owed either way (constraint 10) — `place_window` raises it into
    the always-on-top band, and `lay.adopted` is what `release_adopted()` walks
    when the layout stops being what the phone shows."""
    if root == hwnd or root not in lay.members:
        return False
    if not wm.user32.IsWindow(hwnd) or wm.user32.IsIconic(hwnd):
        return False
    if hwnd not in lay.adopted:
        lay.adopted.append(hwnd)
    # Where Windows put it, remembered BEFORE we move it. He never asked for
    # this placement — the owner chain did (constraint 19) — so it is ours to
    # undo when the layout stops being shown, and `release_adopted` undoes it.
    # Measured 2026-08-13: left in place, a member's MODAL dialog parked here
    # leaves him an application he can raise and cannot click, because a modal
    # disables its owner until it is answered.
    if hwnd not in lay.adopted_home:
        home = wm._frame_rect(hwnd)
        if home is not None:
            lay.adopted_home[hwnd] = home
    anchor = wm._frame_rect(root)
    if contain(lay, hwnd, conn, anchor):
        logger.info("Popup %s centered on its parent %s", describe(hwnd),
                    describe(root))
    return True
