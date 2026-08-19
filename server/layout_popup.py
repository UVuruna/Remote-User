"""A window the LAYOUT'S OWN WORK opened must stay where the phone can reach it.

WHY THIS MODULE EXISTS (owner report 2026-08-10, and again — furious — on
2026-08-11, the third time this class of failure reached him): he was watching
a LAYOUT on the phone when an agent on the PC finished a job and opened its
HTML report. The report window appeared OUTSIDE the layout's region. He could
SEE a sliver of it in the letterboxed picture, and he could do nothing with it:

  * it is below the layout members, which are always-on-top while the phone
    shows them (constraint 10), so it cannot be brought forward from the phone;
  * choosing Desktop MINIMIZES every layout member (owner rule 2026-08-02) —
    which loses the place he was working in, and the popup with it.

His rule, and the whole specification of this module (2026-08-11): nothing
that belongs to the layout's work may open outside the layout's dimensions.
lang-ok: owner quote — the sentence this module is built from
    "ako ne može da stane u dimenzije layouta onda ga otvaraš zasebnog preko celog ekrana"

So: **if it fits the region, it is placed INSIDE the region; if it cannot fit,
it is opened separate, over the FULL screen** — the streamed monitor — so the
phone both sees and operates it.

**AND HE IS ASKED FIRST** (his amendment to the same task, hours later): a new
window is not silently grabbed into the layout. The phone shows a two-button
chip naming it — *Show in layout* / *Leave on desktop* — and his tap decides.
The prompt is on the PHONE and never on the PC: a PC-side dialog would itself
be an unreachable popup, which is the disease. Ignoring the chip is a real
answer, and the answer is the desktop: nothing moves unless he says so, and a
window he leaves on the desktop is never asked about again.

## What this module may NOT do

It sits inside [Focus Guard](focus_guard.py)'s layout branch, which exists to
refuse a foreground the phone did not choose. That refusal is CORRECT for a
thief and must stay exactly as it is: this PC is never quiet, and the windows
that pop up on it are usually another agent's, not this layout's. Adopting a
stranger would be a new way to lose his work — his window would be moved,
resized and nailed above everything by a session it has nothing to do with.

Hence ATTRIBUTION comes first, and it is deliberately narrow:

1. **A dialog of a member is the layout's work.** Ownership is walked up
   (`GW_OWNER`) exactly as the guard already does it — the "Open this link?"
   prompt is the case he reported.
2. **A NEW top-level window of a member's process** is the layout's work.
   NEW is load-bearing: constraint 11 forbids process identity as an
   attribution rule on its own, because every VS Code window shares one
   process and one of those windows is exactly the thief. A window that
   already existed when the phone connected is therefore never adopted, however
   well its process matches.
3. **A NEW window of a process a member STARTED** is the layout's work — the
   member's own child (or grandchild) process, read from the process table's
   parent links.
4. **A NEW top-level window seen within `CLICK_GRACE_S` of an INJECTED
   click** is the layout's work, even with no process tie at all (task 240,
   owner GO). Rules 2 and 3 both assume the window's PROCESS says something —
   and an already-running third-party app (his old Chrome, opened long before
   the layout existed) says nothing: a new window of that process has a
   parent that has been dead for hours. The click is the same evidence task
   185 already uses for "did he just open something" — the only difference
   is WHERE the answer goes. Task 185 asks "make a layout with it?" for a
   window at the DESKTOP; this asks "show it in THIS layout?" for a window
   that appeared while a layout was already focused, through the very same
   `popup_offers.offer` chip rules 1–3 use (`pick(..., "layout")` adopts it exactly as a
   member's own dialog would). A new TAB in an existing window is not a new
   TOP-LEVEL window and is out of scope here, same as everywhere else in this
   module.

Everything else is a stranger and goes back to the guard's refusal, untouched.

## The honest limits (named, not hidden)

* **An already-running third-party app opened through a click IS now
  attributed** (rule 4) — that is the point of task 240. What is still
  refused is the same app appearing with NO recent click: a background
  agent's browser opening its own tab moments after he happened to click a
  layout button gets nothing from that coincidence, because rule 4 only
  fires on a window that is genuinely NEW since the baseline — an existing
  window raising a tab is not this module's business at all.
* **The click grace is a coincidence window, not proof.** A click followed
  within `CLICK_GRACE_S` by ANY new top-level window offers it, whoever
  really opened it — a background agent's dialog landing in that gap would
  be offered too. The cost of a wrong guess here is a chip he can decline,
  never a moved window: nothing places, raises or grabs anything before his
  own tap on "Show in layout".
* **Parent PIDs can be recycled.** Windows re-uses PIDs, and a parent link is
  only a number; the newness requirement bounds that to windows created during
  this phone session, which is the only stretch of time where a wrong answer
  could act.
* **Newness is judged against a baseline taken when the phone connected**
  (`baseline()`, called once from `focus_guard.watch`). Before that baseline
  exists, nothing is new and nothing is adopted — the guard behaves exactly as
  it did before this module.

## What "contained" means, and how it is decided

MEASURED, never remembered (constraint 13 — the Move handle cost four rounds
to that lesson). The region is the union of the members' real frame rects,
read fresh; the popup's own frame is read fresh; and whether a window that
could not shrink must go full screen is decided by ASKING it to take the
region and looking at where it really stands (`place_window` verifies).

The always-on-top band is entered through `place_window`, so the LEDGER
(constraint 10) owes every adopted window a way back down; the layout carries
the list (`Layout.adopted`) and [Layout Registry](layout_registry.py) releases
it on every path where the layout stops being what the phone shows.
"""

import logging
import time

import desk_facts
import popup_contain
import popup_offers
import window_claim
import window_manager as wm

logger = logging.getLogger(__name__)


# ═══════════════════════════ RULES ═══════════════════════════
# How long after an INJECTED click a brand-new top-level window is still
# attributable BY CORRELATION ALONE — task 240. This is deliberately its own
# constant and not task 185's `BIRTH_AFTER_CLICK_S`: that one waits out a cold
# app start before asking "make a layout with it?" at the DESKTOP; this one
# only needs to catch a window that has ALREADY appeared while a layout was
# focused, so "a few seconds" (his own phrase) is enough and a shorter window
# means fewer chips offered on a coincidence.
CLICK_GRACE_S = 5.0


# ═══════════════════════════ THE BASELINE ═══════════════════════════
# THE DESK AS THE PHONE LAST LEFT IT (owner decision 2026-08-17). Module-level
# and not per-connection, deliberately: its whole job is to outlive the
# connection, because the windows he wants to hear about are the ones born
# while there was no connection at all. None = this server has never had a
# phone watching, and then the live desk is the honest answer.
_DESK: set[int] | None = None


def remember_desk() -> None:
    """Write down what stands on the desk right now, as the answer the NEXT
    connection's baseline will use. Called when a session stops watching
    ([Focus Guard](focus_guard.py)'s watcher teardown) — the moment after
    which anything that appears is news he has not seen.

    Blocking Win32 (EnumWindows); the watcher's teardown already runs off the
    event loop. Cheap — once per session, not per tick."""
    global _DESK
    _DESK = desk_facts.top_level_hwnds()


def _remembered_desk() -> set[int]:
    return set(_DESK) if _DESK is not None else desk_facts.top_level_hwnds()


def baseline(conn: dict) -> None:
    """Write down which windows already existed, so a window that appears
    LATER can be told apart from the owner's own second VS Code window.

    Called once per connection from `focus_guard.watch`. Blocking (EnumWindows)
    — the caller runs it on a worker thread. Before it has run, `_is_new`
    answers False for everything and this whole module does nothing: a guard
    that adopted windows on a missing baseline would adopt his entire desk.

    IT NO LONGER FILES HIS ABSENCE AS HISTORY (owner decision 2026-08-17, and
    the mechanism was named by an independent agent before it was believed).
    This function used to enumerate the LIVE desk on every connection, which
    quietly answered the wrong question: a window born while NO phone was
    connected — screen locked, app in the background, session ended by presence
    — is standing there by the time the next connection looks, so the very
    connection that comes looking for it files it as already known, and it can
    never be new again. An agent's report window is born at exactly that
    moment, every time. That is why the phone was silent about precisely the
    windows he wanted to hear about, and it is constraint 17's lesson restated
    one layer up: a feature whose trigger is a connection can never answer for
    what happened while there was none.

    So the baseline is what the desk looked like the LAST TIME A PHONE WAS
    WATCHING, remembered in this process across connections. On the first
    connection after the server starts there is no such memory and the live
    desk is the honest answer — those windows really are his desk, not news.

    His choice, asked and answered: he wants to be asked about them when he
    comes back, with no time limit ("ask me for them when I return"), rather
    than have anything older than a few minutes silently absorbed. The honest
    cost is stated where it lands: after a long absence several windows can be
    waiting, and they arrive one chip at a time through the existing queue —
    never two strips, never two at once (constraint 18)."""
    known = _remembered_desk()
    conn["popup_known"] = known
    # THE SECOND SET, and it must be a second one (task 185). `popup_known` is
    # also the JUDGED set — a window it has ruled on stops being "new" for the
    # attribution above — so the layout-birth scan below cannot share it: one
    # look at a window would make it old for the other feature. Same baseline,
    # separate bookkeeping.
    conn["birth_seen"] = set(known)
    # …and a THIRD, for the same reason once more: the dialog pass
    # ([Dialog Center](dialog_center.py), 2026-08-19) asks "which dialogs are
    # NEW since the desk was last watched", and it may neither make a window
    # old for the two above nor be made blind by their judgements.
    conn["dialog_seen"] = set(known)


def _is_new(conn: dict, hwnd: int) -> bool:
    known = conn.get("popup_known")
    return known is not None and hwnd not in known


def _judged(conn: dict, hwnd: int) -> None:
    """One judgement per window. A stranger that fights for the foreground
    would otherwise be re-attributed — process table read included — four
    times a second for as long as it fights."""
    known = conn.get("popup_known")
    if known is not None:
        known.add(hwnd)


# THE MAKER'S OWN STATEMENT lives in its own module now
# ([Window Claim](window_claim.py), split out 2026-08-17 at the structure law's
# wall). These two names stay because every maker in this codebase already
# calls them through this module, and because a window we made is not an
# attribution at all — it is the one statement here that is not a guess.
mine = window_claim.mine
expect = window_claim.expect
_is_ours = window_claim.is_ours


# ═══════════════════════════ ATTRIBUTION ═══════════════════════════
def _recent_click(conn: dict) -> bool:
    """Did the phone inject a mouse click within `CLICK_GRACE_S`? The SAME
    `click_times` task 185's `note_click` already fills from every left click
    or press (server/web.py) — one source, read by two features that ask
    slightly different questions of it."""
    times = conn.get("click_times") or []
    return bool(times) and time.monotonic() - times[-1] <= CLICK_GRACE_S


# THE ONE ATTRIBUTION THAT IS NOT A GUESS, and therefore the one that is not a
# question either (owner report 2026-08-13 — see THE PARENT'S OWN POPUP below).
# Its own constant because two places must agree on it exactly: the rule that
# produces it, and the rule that acts on it without asking him.
OWNED_BY_MEMBER = "a dialog of a layout window"


def _attribute(lay, hwnd: int, root: int, conn: dict) -> str:
    """WHY this window is the layout's work — a phrase for the log — or "" for
    a stranger, which is every window this module is not certain about."""
    if root and root in lay.members:
        return OWNED_BY_MEMBER
    if not _is_new(conn, hwnd):
        # Not new = it was standing here before the phone connected. His other
        # VS Code window is exactly that, and it shares its process with the
        # member — which is why process identity may never decide alone
        # (constraint 11).
        return ""
    pid = desk_facts.pid_of(hwnd)
    if pid:
        member_pids = {p for p in (desk_facts.pid_of(h) for h in lay.members) if p}
        if pid in member_pids:
            return "a new window of a layout window's own process"
        if desk_facts.descends_from(pid, member_pids):
            return "a window a layout window started"
    # No process tie — the shape task 240 exists for: an ALREADY-RUNNING
    # third-party app (old Chrome, dead parent) opened a new window through
    # his own click on the stream. The click is the only evidence left, so it
    # is checked LAST, after every process-based rule has had its say.
    if _recent_click(conn):
        return "opened moments after an injected click"
    return ""


# ═══════════════════════════ THE ENTRY POINT ═══════════════════════════
def handle(lay, hwnd: int, root: int, conn: dict) -> str:
    """A foreground window that is NOT a member of the focused layout: is it
    the layout's own work, and if so, is it now reachable?

    Returns the attribution phrase (truthy) ONLY for a window he has already
    put in the layout — the guard then leaves the keyboard on it instead of
    yanking focus away. A window that is merely attributed gets him a CHIP on
    the phone and nothing else: until he taps it, the window is an ordinary
    desktop window and the fence treats it as one (his amendment, 2026-08-11
    — never auto-grab).

    Blocking Win32; called from `focus_guard._decide`, which the web layer
    always reaches through `asyncio.to_thread`."""
    if not hwnd or lay is None or not lay.members:
        return ""
    if hwnd in lay.adopted:
        # Already his choice. Re-measured rather than trusted: an app that
        # re-lays itself out (or a second dialog of the same window) can walk
        # back out of the region, and a note of a placement is not a placement.
        popup_contain.contain(lay, hwnd, conn)
        return "a window this layout already holds"
    if hwnd in conn.get("popup_declined", ()) or hwnd in conn.get("popup_asked", ())             or hwnd in conn.get("birth_asked", ()):
        # He said desktop, or he has been asked and has not answered — by this
        # module or by the birth one (one window, one question, constraint
        # 18; the birth chip was the missing case, 2026-08-19). Either way
        # nothing here may move it — and it must not be re-offered on the
        # next of four polls a second.
        return ""

    reason = _attribute(lay, hwnd, root, conn)
    if reason == OWNED_BY_MEMBER and popup_contain.adopt_owned(lay, hwnd, root, conn):
        # Its parent's own dialog, put on its parent (2026-08-13). It is the
        # layout's now, so the keyboard may stay on it — the same answer
        # `lay.adopted` gives above, reached without a tap because this
        # attribution is Windows' own statement and not our guess.
        return "a dialog this layout's own window raised"
    _judged(conn, hwnd)
    if not reason or _is_ours(hwnd) or not wm.is_listable(hwnd):
        return ""
    popup_offers.offer(lay, hwnd, conn, reason)
    return ""


# ═══════════════════════ THE SWEEP — DETECTION WITHOUT FOCUS ═══════════════
# HIS FOURTH REPORT OF ONE BUG (task 239, 2026-08-11): the chip did appear —
# but only after he LEFT the layout and came back, and then everything worked.
#
# That timeline names the defect exactly. `handle` above is reached from
# `focus_guard._decide`, and only ever with the FOREGROUND window: a foreground
# that IS a member returns one line earlier (focus_guard.py, the `if fg in
# members` branch), so `handle` is never called at all. And the window this
# whole module was written about CANNOT take the foreground:
#
#   * the layout's members are always-on-top while the phone shows them
#     (constraint 10), so the new window comes up UNDER them;
#   * Windows refuses `SetForegroundWindow` to a process with no user input of
#     its own and flashes a taskbar button instead — an agent's browser opening
#     an HTML report is precisely that process;
#   * and if it did steal the foreground for an instant, `focus_guard.watch`'s
#     own defence hands focus straight back inside the layout.
#
# So the window stood there, attributable, offerable — and unseen, because the
# only eye we had was the foreground. The moment he switched layouts the
# members left the topmost band, the report window finally reached the
# foreground, `handle` ran for the first time and the chip appeared. Every
# gate written for task 202 passed throughout, because every one of them hands
# the popup the foreground it never gets in real life.
#
# The sweep is therefore ENUMERATION, not focus: which top-level windows are
# new since the baseline, attributed by the same rules, offered by the same
# `_offer` with the same one-chip-per-window bookkeeping — so a window the
# sweep offered can never be offered a second time when it later does reach
# the foreground and `handle` looks at it.
#
# It moves NOTHING. No raise, no placement, no foreground: the only act is a
# sentence on the phone, and the PC is touched only when he taps Show in
# layout, exactly as before.

# How often the desk is enumerated. Not every 0.25 s tick: `desk_facts.top_level_hwnds`
# is one EnumWindows returning handles only, but it runs beside a defence loop
# that must stay cheap, and the requirement is "within a few seconds", not
# "within a frame".
SWEEP_EVERY_S = 1.0
# How long a brand-new window keeps being re-attributed before it is written
# off as a stranger. A window is often visible a moment before the thing that
# identifies it — its owner chain, or the child process that will host it —
# exists, and `_judged` is permanent: one look taken at the wrong instant would
# make a window unattributable for the rest of the session.
SWEEP_GRACE_S = 3.0


GW_OWNER = 4


def _owner_root(hwnd: int) -> int:
    """The top of `hwnd`'s owner chain — a dialog resolves to the window that
    raised it. A local copy of the walk [Focus Guard](focus_guard.py) does,
    because that module imports THIS one and the import may not run both ways.
    Bounded, since a recycled handle can make the chain a ring."""
    seen = hwnd
    for _ in range(8):
        nxt = int(wm.user32.GetWindow(seen, GW_OWNER) or 0)
        if not nxt or nxt == seen:
            break
        seen = nxt
    return seen


def _focused(layouts, conn: dict):
    """The layout the phone is showing, or None. Also a local copy, for the
    import reason above — and it must stay in step with
    `focus_guard._active_layout`, which is why both are three lines long."""
    index = conn.get("active")
    if layouts is None or index is None or not 0 <= index < len(layouts.layouts):
        return None
    lay = layouts.layouts[index]
    return lay if lay.members else None


def _held_by_any(layouts) -> set[int] | None:
    """Every window any layout holds — members and adopted alike — or None
    when there is no registry to ask. The SAME reading `sweep_lost` makes, and
    for the same reason: a window a layout is already responsible for is not a
    window nobody has placed."""
    if layouts is None:
        return None
    held: set[int] = set()
    for lay in getattr(layouts, "layouts", []):
        held.update(lay.members)
        held.update(getattr(lay, "adopted", ()))
    return held


def sweep(layouts, conn: dict) -> None:
    """One enumeration pass: has a window of THIS layout's work appeared,
    whether or not it ever took the foreground? Blocking Win32 — the watcher
    runs it on a worker thread, on its own cadence.

    Offers only. Nothing here places, raises or foregrounds anything."""
    lay = _focused(layouts, conn)
    if lay is None or conn.get("away") or conn.get("left"):
        return
    if conn.get("popup_known") is None:
        return          # no baseline yet: nothing is new, exactly as in `handle`
    now = time.monotonic()
    if now - conn.get("popup_swept", 0.0) < SWEEP_EVERY_S:
        return
    conn["popup_swept"] = now

    pending = conn.setdefault("popup_pending", {})
    asked = conn.get("popup_asked", ())
    declined = conn.get("popup_declined", ())
    # Every window ANY layout holds — not just this one's. The catch-all rule
    # at the bottom of the loop is about windows nobody has placed, and a
    # window sitting in the layout one step along the bar has been placed.
    # Read fresh on every sweep, like everything else here (constraint 13).
    held = _held_by_any(layouts)
    for hwnd in desk_facts.top_level_hwnds():
        # A WINDOW OWNED BY A MEMBER IS THE LAYOUT'S WORK WHATEVER ITS AGE
        # (owner reasoning 2026-08-12, and he was right): "if the desktop
        # minimizes it WITH the layout, does it know that window belongs to
        # it?" It does — Windows takes an OWNED window down with its owner,
        # and `LayoutRegistry.minimize_members` touches only real members. So
        # the owner chain is real evidence, and `_attribute` has always known
        # that: its FIRST rule is the owner root, deliberately ahead of the
        # newness test. This loop was throwing such a window away before that
        # rule could ever run — which is why a dialog raised while the phone
        # was away was never offered, however plainly it belonged.
        if not _is_new(conn, hwnd) and _owner_root(hwnd) not in lay.members:
            continue
        if hwnd in lay.members or hwnd in lay.adopted:
            continue
        # A WINDOW ANY LAYOUT HOLDS IS NOBODY'S QUESTION (owner report
        # 2026-08-19). This used to exempt only the FOCUSED layout's windows,
        # so a dialog another layout had adopted — its VS Code's own "open
        # this link?" box — still ran the process rule below against the
        # focused layout, whose VS Code shares the exe, and was offered as a
        # new window. `held` is read fresh one screen above for the catch-all
        # rule; it is the same fact, asked first.
        if held is not None and hwnd in held:
            continue
        if hwnd in asked or hwnd in declined or hwnd in conn.get("birth_asked", ())                 or _is_ours(hwnd):
            continue
        root = _owner_root(hwnd)
        reason = _attribute(lay, hwnd, root, conn)
        if reason == OWNED_BY_MEMBER and popup_contain.adopt_owned(lay, hwnd, root, conn):
            # Placed, not offered — his rule of 2026-08-13. Deliberately NOT
            # `_judged`: an app's dialog can be moved again by the app itself
            # (a resize as its content loads), and the next sweep must be free
            # to put it back. `_contain`'s own `popup_tries` is what stops that
            # becoming a fight with a window that refuses every rect.
            pending.pop(hwnd, None)
            continue
        if reason:
            pending.pop(hwnd, None)
            _judged(conn, hwnd)
            if not wm.is_listable(hwnd):
                # Attributable but not a window a layout could hold — a tool
                # window, a cloaked shell surface, something with no title. It
                # would not appear in the creation list, so a chip about it is
                # a question the app cannot honour (his point 3).
                continue
            popup_offers.offer(lay, hwnd, conn, f"{reason}, seen by the sweep")
            continue
        # NOBODY HAS PLACED THIS WINDOW ANYWHERE — and that is now a reason of
        # its own (owner decision 2026-08-17, chosen off a ballot).
        #
        # THE QUESTION THIS MODULE ASKED WAS THE WRONG ONE, and his report is
        # what named it: "it asks me only where it has nothing to ask me — where
        # I make the window myself — and not where somebody else made it, where
        # I DO want a layout from it." Every rule in `_attribute` answers "does
        # this window BELONG to this layout", and answers it mostly by process
        # identity — so his own second VS Code window (same exe as a member)
        # was reported to him as an intrusion, while an agent's report window
        # (its own exe, no ancestry, no click of his anywhere near it) fell
        # through all four rules and was filed as a stranger to be ignored.
        # Exactly inverted from what he wants, by construction.
        #
        # He chose the other question: is this a window I have not put anywhere
        # yet? So a NEW, listable, unheld window earns its chip on that alone,
        # with no evidence about who made it — because "who made it" is what we
        # cannot read, and what we CAN read is that it is standing on his PC
        # unplaced while he is looking at a layout from across the room.
        #
        # THE THREE THINGS THAT STILL SILENCE IT, and they are the whole safety
        # of this rule: a window WE made on his own tap (`_is_ours` above —
        # armed BEFORE the act since this round, see window_claim.py), a window
        # some layout already holds (`held` below), and a window no layout
        # could hold anyway (`is_listable`). The honest cost he was told about
        # and accepted: every unrelated new window — an installer, a browser he
        # started at the desk — is now a chip he can decline. Declining is
        # remembered for the connection, and nothing ever moves before his tap.
        if held is not None and _is_new(conn, hwnd) and hwnd not in held \
                and wm.is_listable(hwnd):
            pending.pop(hwnd, None)
            _judged(conn, hwnd)
            popup_offers.offer(lay, hwnd, conn, "a window nobody has placed, seen by the sweep")
            continue
        # Not yet attributable. Give it the grace above before writing it off
        # for good — `_judged` cannot be taken back.
        first = pending.setdefault(hwnd, now)
        if now - first >= SWEEP_GRACE_S:
            pending.pop(hwnd, None)
            _judged(conn, hwnd)
