"""WHEN AN APP OPENS ON THE PC, OFFER TO MAKE A LAYOUT WITH IT.

Owner request 2026-08-09 (task 185): he double-clicks a picture or an .xlsx
through the stream, the viewer or Excel opens — and the phone should ASK
whether to make a layout with it, with the usual single/grid choices.

The SCOPING was recorded before a line was written, and every clause of it is a
rule below rather than a hope:

* **Only while a phone session is live.** This runs inside
  [Focus Guard](focus_guard.py)'s watcher, which exists per connection, and it
  stands down while the phone is away — those windows belong to his desk again.
* **Only NEW top-level windows, never dialogs.** `window_manager.list_windows`
  drops tool windows, cloaked windows, shell chrome, untitled windows, our
  own process — and, since 2026-08-19, every DIALOG (`window_manager.is_dialog`:
  a window owned by a visible one), which is the one definition every chip
  path shares. A layout member cannot hold a dialog anyway.
* **Correlated with an injected DOUBLE-CLICK.** This is the load-bearing one.
  This PC is never quiet — background agents launch GUI apps all day
  (constraint 11) — so "a window appeared" is not evidence of anything. What
  makes it HIS act is that the phone injected two clicks, close together,
  moments before. No click, no question.
* **A non-modal chip, on the phone, that auto-dismisses**, reusing
  [Layout Popup](layout_popup.py)'s offer flow rather than a second one.
  Ignoring it is an answer.
* **It never steals PC focus.** Nothing here places, raises or foregrounds
  anything at all: the offer is a sentence on the phone, and the creation panel
  does every later step through the paths that already exist.

## Why it is its own module

It shipped inside [Layout Popup](layout_popup.py), whose subject is the
opposite one — a window the LAYOUT'S work opened, which the layout must
contain. This module's subject is a window HE opened, which nothing may touch
until he says so. Sharing a file made them look like one feature, and on
2026-08-12 that cost him a moved window: both fired on the same window in the
same tick and the phone showed only the last chip (constraint 18). They are
apart now, and the one rule they share — a window the focused layout can claim
belongs to the popup module's question, never to this one — is written once,
below, where it can be read.
"""

import logging
import time

import popup_contain
import popup_offers
import layout_popup
import window_manager as wm

logger = logging.getLogger(__name__)


# ═══════════════════════════ RULES ═══════════════════════════
# Two clicks no further apart than this are a double-click. Windows' own
# default is 500 ms; a little more is right for a finger on a phone driving a
# button, and being generous here can only ask a question, never move a window.
DOUBLE_CLICK_S = 0.7
# How long after that double-click a new window may still be its result. Cold
# starts are slow (Excel on a busy machine), and the correlation is only ever
# used to decide whether to ASK.
BIRTH_AFTER_CLICK_S = 15.0


def note_click(conn: dict) -> None:
    """The phone injected a mouse click. Called from the web layer's click and
    press branches — the ONLY source, deliberately: a click the PC's own mouse
    made is not the phone opening something, and cannot be one."""
    times = conn.setdefault("click_times", [])
    times.append(time.monotonic())
    del times[:-4]


def _double_clicked(conn: dict) -> bool:
    times = conn.get("click_times") or []
    if len(times) < 2:
        return False
    now = time.monotonic()
    return (times[-1] - times[-2] <= DOUBLE_CLICK_S
            and now - times[-1] <= BIRTH_AFTER_CLICK_S)


def _offer_birth(conn: dict, win: dict) -> None:
    """Queue the "layout with it?" chip for a window he just opened."""
    hwnd = win["hwnd"]
    popup_offers.queue_offer(
        conn, hwnd, "b", {"lay": None, "birth": True},
        {"act": "layout_new", "title": win.get("title", ""),
         "process": win.get("process", ""), "hwnd": hwnd,
         "icon": win.get("icon")},
        "birth_asked")
    logger.info("New window %s offered as a layout (task 185)",
                popup_contain.describe(hwnd))


def scan(layouts, conn: dict) -> None:
    """One pass: did a window HE opened appear? Blocking Win32 — the watcher
    runs it on a worker thread.

    Cheap in the common case, and that matters because this runs beside a
    0.25 s poll: with no recent double-click it costs one comparison and
    returns. The window sweep is only paid when he has just clicked twice."""
    seen = conn.get("birth_seen")
    if seen is None or conn.get("away") or conn.get("left"):
        return
    # THE DOUBLE-CLICK IS NO LONGER REQUIRED (owner decision 2026-08-17, off a
    # ballot). It used to be the whole trigger: a new window earned "a layout
    # with it?" only within `BIRTH_AFTER_CLICK_S` of a click the PHONE had
    # injected — which answers "did HE open this", and that is not the question
    # he wants asked. His report: the app asks him only where he made the
    # window himself and stays silent where somebody else did, "and there I DO
    # want a layout from it". An agent's report window arrives with no click of
    # his anywhere near it, and under the old rule could never be offered at
    # the desktop at all.
    #
    # So the pass now runs on every tick and the click evidence is gone. What
    # still silences it is unchanged and is the whole safety of the rule: a
    # window WE made on his tap (`_is_ours`, armed BEFORE the act since this
    # round — window_claim.py), a window some layout already holds, a dialog of
    # something else, and a window already asked about. Nothing moves before
    # his tap, and a decline is remembered.
    #
    # The honest cost, which he was told and accepted: at the desktop every new
    # window is now a chip. `wm.list_windows()` on every tick is the price —
    # the "cheap in the common case" note above no longer holds, and this pass
    # is deliberately the one that pays it, because the alternative is the
    # silence he reported.
    members: set[int] = set()
    for other in getattr(layouts, "layouts", []):
        members.update(other.members)
        members.update(getattr(other, "adopted", ()))
    # The layout the phone is SHOWING — the only one whose work can claim a
    # window out from under this pass (see the one-window-one-question rule
    # below). Named here rather than in the loop above, because a loop variable
    # that leaks its last value is how a rule about the FOCUSED layout would
    # quietly become a rule about the last one in the list.
    focused = layout_popup._focused(layouts, conn)
    for win in wm.list_windows():
        hwnd = win["hwnd"]
        if hwnd in seen:
            continue
        seen.add(hwnd)          # judged once, whatever the answer
        # (A dialog of something else never reaches this loop: `list_windows`
        # refuses it through `window_manager.is_dialog` — ONE definition of
        # "a dialog", since 2026-08-19, shared with every chip path.)
        if hwnd in members or hwnd in conn.get("birth_asked", ()):
            continue
        # THE SWEEP GOT THERE FIRST (owner report 2026-08-19 — two chips, two
        # identical layouts, and closing one closed both). The rule below asks
        # `_attribute` whether the focused layout can claim the window — but
        # `_attribute` answers "" for any window the sweep has already JUDGED,
        # because `_judged` makes it old. So whenever the sweep saw the window
        # one tick before this pass did (a window visible a moment before it
        # was listable, a hook wake between two passes), its chip was already
        # out and this pass put a second one behind it. A chip the sweep has
        # out, or an answer he has already given it, is the one-window-one-
        # question rule's own bookkeeping — read it, and stand down.
        if hwnd in conn.get("popup_asked", ()) or hwnd in conn.get("popup_declined", ()):
            continue
        # A WINDOW WE MADE OURSELVES IS NOT A WINDOW HE OPENED (owner report
        # 2026-08-13, his point 4A). Creating a layout from a TAP inside a
        # layout is a double-click followed, a second later, by a brand-new
        # top-level window — because we tore that tab off ourselves on his
        # instruction. Every test above is right about it and that is exactly
        # the problem; only the maker knows, so the maker says so.
        if layout_popup._is_ours(hwnd):
            continue
        # ONE WINDOW, ONE QUESTION (owner report 2026-08-12, and his own log
        # dated it to the millisecond). This pass and the popup sweep are two
        # features that never knew about each other, and at 20:29:58 they both
        # fired on the SAME window inside one tick:
        #
        #   New window python.exe "Controls …" offered as a layout (task 185)
        #   Popup     python.exe "Controls …" offered to the phone as 570a0a-3
        #
        # The phone has ONE chip strip and ONE live offer id, so the second
        # message silently replaced the first — and four more birth chips
        # followed within 400 ms. His single tap therefore answered a question
        # he had never read: the "Show in layout" one, whose yes runs `_contain`
        # and PLACES the window into the layout's region. That is his report
        # exactly — "it made the dimensions as if for the phone, but there is
        # no layout".
        #
        # So a window the focused layout can claim is the SWEEP's question,
        # never this one. A new layout from a window that already belongs to
        # the layout's own work was never a sensible offer anyway.
        if focused is not None and layout_popup._attribute(
                focused, hwnd, layout_popup._owner_root(hwnd), conn):
            continue
        _offer_birth(conn, win)
