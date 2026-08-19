"""A DIALOG OPENS IN THE MIDDLE OF ITS PARENT — whichever layout the parent is
in, and even when it is in none.

Owner report 2026-08-19, and it was a REPEAT of constraint 19 ("a member's own
popup opens in the middle of its parent, and nobody is asked"): his UVuruna
VS Code raised its "open this link in Chrome?" box while the phone was showing
ANOTHER layout. The box — 625x189, owned by that VS Code — was offered to him
as a new window, he said yes, and the app built a layout out of a dialog that
cannot take a rect. His words, and the whole specification of this module:

lang-ok-begin: owner quote — the sentences this module is built from
    "taj mali isečak ... nije nešto što treba da se nudi kao novi prozor
     on treba da bude u centru roditeljskog ... ne u centru bilo kojeg nego u
     centru roditeljskog"
    "ako ga je uvuruna napravio sledeći put kad dođem na layout uvuruna on
     treba da bude na centru njega"
    "treba da se pojavi notifikacija koja da tu informaciju ... i onda ja kad
     kliknem odvede me na layout od uvuruna"
    "ako nema layout i dalje treba da se pojavi po sredini roditelja"
lang-ok-end

WHY CONSTRAINT 19 DID NOT COVER IT. Its rule lives in [Layout Popup](layout_popup.py),
whose every question is asked of the FOCUSED layout: "is the owner root one of
THIS layout's members?" The owner was a member of a layout one step along the
bar, so rule 1 failed, and rule 2 — "a new window of a member's process" —
matched the focused layout's own VS Code, which shares the exe. Correct rules,
asked of the wrong layout.

## The three sentences, as code

* **The parent is in SOME layout** — the dialog is centred on its parent NOW
  (a plain move, never the topmost band: that band is the shown layout's
  alone, and Windows keeps an owned window above its owner by itself), it is
  ADOPTED into that layout — so the next `focus()` of it re-contains the dialog
  like any adopted popup and `release_adopted` owes it the way home — and he
  gets ONE notice naming the layout, whose tap jumps there. Never a chip.
* **The parent is in the FOCUSED layout** — not this module's case at all:
  `layout_popup`'s own rule 1 places it, as it has since 2026-08-13.
* **The parent is in NO layout** — centred on its parent all the same, once,
  with no adoption and no notice: there is no layout to jump to, and the
  window belongs to nobody's session.

## What this module may NOT do

It moves ONLY dialogs — `window_manager.is_dialog`: a window owned by a
VISIBLE window — and only ones NEW since the desk was last watched (the third
copy of the connection baseline, `dialog_seen`; see `layout_popup.baseline`
for why each pass keeps its own). It never raises, never foregrounds, never
touches the topmost band, and gives up on a window that refuses its rect
after `popup_contain.MAX_CONTAIN_TRIES` tries, for the same reason that
constant exists. A dialog of OUR OWN process (the Settings window's own
boxes) and a window we made ourselves (`window_claim`) are left alone.
"""

import logging
import os
import time

import desk_facts
import layout_popup
import notice_channel
import notify
import popup_contain
import window_manager as wm

logger = logging.getLogger(__name__)

# How often the desk is enumerated — the sweep's own cadence, and for the
# same reason: "within a few seconds", beside a defence loop that must stay
# cheap.
SWEEP_EVERY_S = layout_popup.SWEEP_EVERY_S


def _layout_holding(layouts, root: int):
    """`(index, layout)` of the layout `root` is a MEMBER of, or (None, None)."""
    for i, lay in enumerate(getattr(layouts, "layouts", None) or ()):
        if root in lay.members:
            return i, lay
    return None, None


def _centre(hwnd: int, root: int, conn: dict) -> bool:
    """Put `hwnd` in the middle of `root`, measured now; returns whether it
    stands there afterwards. A plain, non-topmost move. Bounded per window, so
    a dialog that refuses every rect is not fought four times a second."""
    rect = wm._frame_rect(hwnd)
    anchor = wm._frame_rect(root)
    if rect is not None and anchor is not None and popup_contain._inside(rect, anchor):
        return True
    tries = conn.setdefault("dialog_tries", {})
    tries[hwnd] = tries.get(hwnd, 0) + 1
    if tries[hwnd] > popup_contain.MAX_CONTAIN_TRIES or rect is None or anchor is None:
        return False
    target = popup_contain._centered_in(rect, anchor)
    if target is None:
        return False            # bigger than its parent: nothing to centre on
    return wm.place_window(hwnd, target, topmost=False)


def _tell(conn: dict, lay, index: int, hwnd: int, root: int) -> None:
    """ONE notice per dialog: which layout has it, so his tap can jump there.
    Built by `notify.make_notice` — the same frame an agent's "needs you"
    rides on — and queued for the watcher loop to deliver (`flush_notices`),
    because this pass runs on a worker thread and the carrier is async."""
    told = conn.setdefault("dialog_told", set())
    if hwnd in told:
        return
    told.add(hwnd)
    process = wm._process_name(root) or "?"
    notice = notify.make_notice(
        lay.name, "dialog",
        f'{process}: "{wm._title(hwnd)[:80]}"',
        f"{lay.name}: a dialog is waiting",
        where={"index": index, "name": lay.name})
    conn.setdefault("dialog_notices", []).append(notice)
    logger.info("Dialog %s of %s — layout %d (%r) told", popup_contain.describe(hwnd),
                popup_contain.describe(root), index, lay.name)


def sweep(layouts, conn: dict) -> None:
    """One pass over the desk: is a NEW dialog standing off its parent?
    Blocking Win32 — the watcher runs it on a worker thread, on its own
    cadence, beside the birth scan (so at the desktop too)."""
    seen = conn.get("dialog_seen")
    if seen is None or conn.get("away") or conn.get("left"):
        return
    now = time.monotonic()
    if now - conn.get("dialog_swept", 0.0) < SWEEP_EVERY_S:
        return
    conn["dialog_swept"] = now
    focused = layout_popup._focused(layouts, conn)
    me = os.getpid()
    for hwnd in desk_facts.top_level_hwnds():
        if hwnd in seen:
            continue
        if not wm.is_dialog(hwnd) or layout_popup._is_ours(hwnd):
            seen.add(hwnd)          # not a dialog: judged once, like every pass
            continue
        root = layout_popup._owner_root(hwnd)
        if root == hwnd or not wm.user32.IsWindow(root) \
                or wm.user32.IsIconic(root) or desk_facts.pid_of(hwnd) == me:
            continue                # no parent to centre on (yet) — look again
        index, lay = _layout_holding(layouts, root)
        if lay is not None and lay is focused:
            continue                # layout_popup's own rule 1 (constraint 19)
        if lay is not None and hwnd not in lay.adopted:
            # His first two sentences: the layout's from here on — adopted,
            # with its home remembered for `release_adopted` — and a notice
            # naming where. (His third: no layout, no adoption, no notice.)
            lay.adopted.append(hwnd)
            home = wm._frame_rect(hwnd)
            if home is not None and hwnd not in lay.adopted_home:
                lay.adopted_home[hwnd] = home
        centred = _centre(hwnd, root, conn)
        gave_up = conn.get("dialog_tries", {}).get(hwnd, 0) > popup_contain.MAX_CONTAIN_TRIES
        if centred:
            logger.info("Dialog %s centred on its parent %s%s",
                        popup_contain.describe(hwnd), popup_contain.describe(root),
                        f" in layout {index} ({lay.name!r})" if lay else " (in no layout)")
        if centred or gave_up:
            seen.add(hwnd)          # done, or it will not take a rect — leave it
        if lay is not None:
            _tell(conn, lay, index, hwnd, root)


async def flush_notices(conn: dict) -> int:
    """Deliver what `sweep` queued, through the one notice carrier. Returns
    how many went out. Called from the watcher loop — its only async
    context — right after the offer flush."""
    pending = conn.get("dialog_notices")
    if not pending:
        return 0
    sent = 0
    while pending:
        notice = pending.pop(0)
        carrier = await notice_channel.deliver(notice)
        logger.info("Dialog notice %r → %s", notice.get("title"), carrier)
        sent += 1
    return sent
