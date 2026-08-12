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
   `_offer` chip rules 1–3 use (`pick(..., "layout")` adopts it exactly as a
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

import asyncio
import ctypes
import ctypes.wintypes as wintypes
import json
import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse

import lost_windows
import notify
import window_manager as wm
from grids import PLACE_TOLERANCE_PX

logger = logging.getLogger(__name__)


# ═══════════════════════════ RULES ═══════════════════════════
# How many parent hops a window may be from a member's process and still be
# that member's work. A member starting a launcher that starts a browser is
# two; beyond a handful the link stops meaning anything.
ANCESTRY_HOPS = 4
# How many times we try to contain ONE window before leaving it where it is.
# A window that refuses every rect we command (a fixed-size tool window, a
# process at a higher integrity level) must not be fought four times a second
# for the rest of the session.
MAX_CONTAIN_TRIES = 3
# How long after an INJECTED click a brand-new top-level window is still
# attributable BY CORRELATION ALONE — task 240. This is deliberately its own
# constant and not task 185's `BIRTH_AFTER_CLICK_S`: that one waits out a cold
# app start before asking "make a layout with it?" at the DESKTOP; this one
# only needs to catch a window that has ALREADY appeared while a layout was
# focused, so "a few seconds" (his own phrase) is enough and a shorter window
# means fewer chips offered on a coincidence.
CLICK_GRACE_S = 5.0


# ═══════════════════════════ WINDOWS FACTS ═══════════════════════════
TH32CS_SNAPPROCESS = 0x00000002
_INVALID_HANDLE = -1


class _PROCESSENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_char * 260)]


def _pid(hwnd: int) -> int:
    """The process a window belongs to (0 = unknown). Its own function because
    the gate replaces it — nothing here may enumerate the owner's real desk."""
    pid = wintypes.DWORD()
    wm.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _parent_pids() -> dict[int, int]:
    """`{pid: parent pid}` for every process on the machine, from one Toolhelp
    snapshot (~a millisecond). Read on demand — only a window that is NEW and
    does not already match a member's process ever costs it — and never
    cached: a cache would answer about a process table that has since changed,
    and the whole question here is about something that just started."""
    snap = wm.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == _INVALID_HANDLE:
        return {}
    parents: dict[int, int] = {}
    try:
        entry = _PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32)
        ok = wm.kernel32.Process32First(snap, ctypes.byref(entry))
        while ok:
            parents[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            ok = wm.kernel32.Process32Next(snap, ctypes.byref(entry))
    finally:
        wm.kernel32.CloseHandle(snap)
    return parents


def _descends_from(pid: int, roots: set[int]) -> bool:
    """Was `pid` started by one of `roots` (child, grandchild, …)? Bounded by
    `ANCESTRY_HOPS` and by a seen-set, because a process table read from a
    live machine can contain a cycle after a PID was recycled."""
    if not pid or not roots:
        return False
    parents = _parent_pids()
    seen = {pid}
    for _ in range(ANCESTRY_HOPS):
        pid = parents.get(pid, 0)
        if not pid or pid in seen:
            return False
        if pid in roots:
            return True
        seen.add(pid)
    return False


def _top_level_hwnds() -> set[int]:
    """Every visible top-level window, handles only.

    Deliberately NOT `window_manager.list_windows`: that one also reads a
    process path and renders an ICON per window, which is right for the
    creation list the phone draws and far too much for a set of numbers taken
    once per connection."""
    found: set[int] = set()

    @wm._EnumWindowsProc
    def callback(hwnd, _lparam):
        if wm.user32.IsWindowVisible(hwnd):
            found.add(int(hwnd))
        return True

    wm.user32.EnumWindows(callback, 0)
    return found


# ═══════════════════════════ THE BASELINE ═══════════════════════════
def baseline(conn: dict) -> None:
    """Write down which windows already existed, so a window that appears
    LATER can be told apart from the owner's own second VS Code window.

    Called once per connection from `focus_guard.watch`. Blocking (EnumWindows)
    — the caller runs it on a worker thread. Before it has run, `_is_new`
    answers False for everything and this whole module does nothing: a guard
    that adopted windows on a missing baseline would adopt his entire desk."""
    known = _top_level_hwnds()
    conn["popup_known"] = known
    # THE SECOND SET, and it must be a second one (task 185). `popup_known` is
    # also the JUDGED set — a window it has ruled on stops being "new" for the
    # attribution above — so the layout-birth scan below cannot share it: one
    # look at a window would make it old for the other feature. Same baseline,
    # separate bookkeeping.
    conn["birth_seen"] = set(known)


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


# ═══════════════════════════ ATTRIBUTION ═══════════════════════════
def _recent_click(conn: dict) -> bool:
    """Did the phone inject a mouse click within `CLICK_GRACE_S`? The SAME
    `click_times` task 185's `note_click` already fills from every left click
    or press (server/web.py) — one source, read by two features that ask
    slightly different questions of it."""
    times = conn.get("click_times") or []
    return bool(times) and time.monotonic() - times[-1] <= CLICK_GRACE_S


def _attribute(lay, hwnd: int, root: int, conn: dict) -> str:
    """WHY this window is the layout's work — a phrase for the log — or "" for
    a stranger, which is every window this module is not certain about."""
    if root and root in lay.members:
        return "a dialog of a layout window"
    if not _is_new(conn, hwnd):
        # Not new = it was standing here before the phone connected. His other
        # VS Code window is exactly that, and it shares its process with the
        # member — which is why process identity may never decide alone
        # (constraint 11).
        return ""
    pid = _pid(hwnd)
    if pid:
        member_pids = {p for p in (_pid(h) for h in lay.members) if p}
        if pid in member_pids:
            return "a new window of a layout window's own process"
        if _descends_from(pid, member_pids):
            return "a window a layout window started"
    # No process tie — the shape task 240 exists for: an ALREADY-RUNNING
    # third-party app (old Chrome, dead parent) opened a new window through
    # his own click on the stream. The click is the only evidence left, so it
    # is checked LAST, after every process-based rule has had its say.
    if _recent_click(conn):
        return "opened moments after an injected click"
    return ""


# ═══════════════════════════ CONTAINMENT ═══════════════════════════
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


def _describe(hwnd: int) -> str:
    return f'{wm._process_name(hwnd) or "?"} "{wm._title(hwnd)[:60]}" ({hwnd:#x})'


def _contain(lay, hwnd: int, conn: dict) -> bool:
    """Put this window where the phone can operate it. Returns whether it
    ended up inside the streamed picture.

    The two branches are the owner's two sentences, and which one applies is
    MEASURED, never assumed:

    * it FITS the region — placed inside it, at its own size, centered. A
      dialog stretched to fill a whole layout would be a worse answer than the
      one Windows gave.
    * it does NOT fit — asked to take the region anyway (a resizable window
      simply obeys, and that is still the first answer), and only when it
      REFUSES, which is what a minimum size larger than the region looks like
      from here, does it go full screen over the streamed monitor."""
    region = _region(lay)
    rect = wm._frame_rect(hwnd) if wm.user32.IsWindow(hwnd) else None
    if region is None or rect is None:
        return False
    if _inside(rect, region):
        return True

    tries = conn.setdefault("popup_tries", {})
    tries[hwnd] = tries.get(hwnd, 0) + 1
    if tries[hwnd] > MAX_CONTAIN_TRIES:
        return False

    x, y, w, h = rect
    rx, ry, rw, rh = region
    if w <= rw and h <= rh:
        target = (rx + (rw - w) // 2, ry + (rh - h) // 2, w, h)
        if wm.place_window(hwnd, target):
            return True
    if wm.place_window(hwnd, region):
        return True
    # It cannot be made to fit, so it opens separate over the whole screen —
    # the full work area of the monitor the members stand on, which is the
    # monitor being streamed.
    full = wm._work_area(region)
    if wm.place_window(hwnd, full):
        logger.info("Popup %s could not fit the layout region %s — opened "
                    "full screen on %s", _describe(hwnd), region, full)
        return True
    logger.error("Popup %s would take NEITHER the layout region %s NOR the "
                 "full screen %s — it stays where Windows put it",
                 _describe(hwnd), region, full)
    return False


# ═══════════════════════════ ASKING HIM ═══════════════════════════
# How long an unanswered offer is kept. He is allowed to ignore the chip —
# that IS an answer, and the answer is "leave it on the desktop" — so this is
# only about not growing a dictionary for the life of the process.
OFFER_TTL_S = 10 * 60

# id -> {hwnd, lay, conn, at}. Module-level rather than per-connection because
# the answer comes back over HTTP (`register` below), which has no socket and
# no `conn` — the id is the whole handle. An offer whose connection has since
# died still resolves safely: the layout is checked, and a window that closed
# meanwhile is refused.
_OFFERS: dict[str, dict] = {}
_NEXT_ID = 0


def _expire() -> None:
    cutoff = time.monotonic() - OFFER_TTL_S
    for key in [k for k, o in _OFFERS.items() if o["at"] < cutoff]:
        del _OFFERS[key]


def _offer(lay, hwnd: int, conn: dict, reason: str) -> str:
    """Queue the phone's two-button chip for this window and return its id.

    ONE PROMPT PER WINDOW (`popup_asked`): the watcher runs four times a
    second, and a chip that reappeared on every tick would be worse than the
    bug it answers."""
    global _NEXT_ID
    _expire()
    _NEXT_ID += 1
    key = f"{hwnd:x}-{_NEXT_ID}"
    _OFFERS[key] = {"hwnd": hwnd, "lay": lay, "conn": conn,
                    "at": time.monotonic()}
    conn.setdefault("popup_asked", set()).add(hwnd)
    conn.setdefault("popup_send", []).append({
        "type": "window_offer", "id": key,
        "title": wm._title(hwnd), "process": wm._process_name(hwnd),
        "layout": lay.name})
    logger.info("Popup %s offered to the phone as %s (%s)",
                _describe(hwnd), key, reason)
    return key


async def flush_offers(conn: dict) -> int:
    """Send whatever the watcher queued, over the page's own socket. Returns
    how many went out.

    The socket comes from [Notify](notify.py)'s one-device slot — the web
    layer's own registry, which this project deliberately keeps only one of.
    A phone that is gone simply drops the chip: an offer is about a window
    that opened just now, and a chip arriving after the next connection would
    ask him about something he has long since walked past."""
    pending = conn.get("popup_send")
    if not pending:
        return 0
    ws = notify.page_socket()
    if ws is None:
        pending.clear()
        return 0
    sent = 0
    while pending:
        payload = pending.pop(0)
        try:
            await ws.send_text(json.dumps(payload))
        except Exception as e:      # noqa: BLE001 — a dead socket must not kill the watcher
            logger.warning("Window offer not delivered: %s", e)
            pending.clear()
            break
        sent += 1
    return sent


# ═══════════════════════ WHEN AN APP OPENS, OFFER A LAYOUT ═══════════════════
# Owner request 2026-08-09 (task 185): he double-clicks a picture or an .xlsx
# through the stream, the viewer or Excel opens — and the phone should ASK
# whether to make a layout with it, with the usual single/grid choices.
#
# The SCOPING was recorded before a line was written, and every clause of it is
# a rule below rather than a hope:
#
# * **Only while a phone session is live.** This runs inside `focus_guard.watch`,
#   which exists per connection, and it stands down while the phone is away —
#   those windows belong to his desk again.
# * **Only NEW top-level windows, never dialogs.** `wm.list_windows` already
#   drops tool windows, cloaked windows, shell chrome, untitled windows and our
#   own process; an OWNED window (`GW_OWNER`) is a dialog of something else and
#   is dropped here. A layout member cannot hold a dialog anyway.
# * **Correlated with an injected DOUBLE-CLICK.** This is the load-bearing one.
#   This PC is never quiet — background agents launch GUI apps all day
#   (constraint 11, and the memory note that names it) — so "a window
#   appeared" is not evidence of anything. What makes it HIS act is that the
#   phone injected two clicks, close together, moments before. No click, no
#   question.
# * **A non-modal chip, on the phone, that auto-dismisses**, reusing the
#   window-offer flow above rather than a second one. Ignoring it is an answer.
# * **It never steals PC focus.** Nothing here places, raises or foregrounds
#   anything at all: the offer is a sentence on the phone, and the creation
#   panel does every later step through the paths that already exist.

# Two clicks no further apart than this are a double-click. Windows' own
# default is 500 ms; a little more is right for a finger on a phone driving a
# button, and being generous here can only ask a question, never move a window.
DOUBLE_CLICK_S = 0.7
# How long after that double-click a new window may still be its result. Cold
# starts are slow (Excel on a busy machine), and the correlation is only ever
# used to decide whether to ASK.
BIRTH_AFTER_CLICK_S = 15.0
GW_OWNER = 4


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
    global _NEXT_ID
    _expire()
    _NEXT_ID += 1
    hwnd = win["hwnd"]
    key = f"b{hwnd:x}-{_NEXT_ID}"
    _OFFERS[key] = {"hwnd": hwnd, "lay": None, "conn": conn, "birth": True,
                    "at": time.monotonic()}
    conn.setdefault("birth_asked", set()).add(hwnd)
    conn.setdefault("popup_send", []).append({
        "type": "window_offer", "id": key, "act": "layout_new",
        "title": win.get("title", ""), "process": win.get("process", ""),
        "hwnd": hwnd, "icon": win.get("icon")})
    logger.info("New window %s offered as a layout (task 185)",
                _describe(hwnd))


# ═══════════════════ AND THE WINDOW NOBODY CAN REACH ═══════════════════
# Owner report 2026-08-12, the FIFTH on one failure: a window that opened while
# his phone was LOCKED sits off every screen and can never be shown again.
#
# Everything above this line asks WHO opened a window, and every one of those
# rules is built on `baseline` — which is exactly why none of them could ever
# see his case: a window born while no phone was connected is filed as KNOWN by
# the next connection's baseline and is never new again. See
# [Lost Windows](lost_windows.py) for the whole diagnosis.
#
# So this pass asks a different question — CAN HE REACH IT — which is geometry,
# measured now, and needs no history at all. It therefore answers for a window
# opened by an agent, by Windows, or hours before the phone ever connected.
#
# It rides the SAME chip as everything else here (one strip of screen, one
# dismissal rule) and, unlike every other pass in this module, it runs at the
# DESKTOP as well as inside a layout: a lost window is lost either way.
LOST_EVERY_S = 4.0


def _offer_lost(conn: dict, win: dict) -> None:
    """Queue the "bring it back?" chip for a window nobody can reach."""
    global _NEXT_ID
    _expire()
    _NEXT_ID += 1
    hwnd = win["hwnd"]
    key = f"l{hwnd:x}-{_NEXT_ID}"
    _OFFERS[key] = {"hwnd": hwnd, "lay": None, "conn": conn, "lost": True,
                    "at": time.monotonic()}
    conn.setdefault("lost_asked", set()).add(hwnd)
    conn.setdefault("popup_send", []).append({
        "type": "window_offer", "id": key, "act": "rescue",
        "title": win.get("title", ""), "process": win.get("process", ""),
        "hwnd": hwnd, "icon": win.get("icon")})
    logger.warning("Window %s is off every screen (%s%s) — rescue offered",
                   _describe(hwnd), win.get("rect"),
                   ", minimized" if win.get("minimized") else "")


def sweep_lost(layouts, conn: dict) -> None:
    """One pass over the unreachable. Blocking Win32 — the watcher runs it on
    a worker thread, on its own slow cadence.

    ONE CHIP PER WINDOW PER CONNECTION (`lost_asked`), and ignoring it is an
    answer — but a DELIBERATE decline is remembered separately (`lost_left`),
    because the two mean different things: an unanswered chip may simply have
    been missed while he was reading the PC screen, and the next connection
    asking again is the behaviour that makes this a guarantee rather than a
    lottery. A window he actually said "leave it" about is never raised again
    on this connection."""
    if conn.get("away") or conn.get("left"):
        return
    now = time.monotonic()
    if now - conn.get("lost_swept", 0.0) < LOST_EVERY_S:
        return
    conn["lost_swept"] = now
    # A layout's own windows are where the layout put them and the layout can
    # move them; offering a rescue there would fight it.
    held: set[int] = set()
    for lay in getattr(layouts, "layouts", []) if layouts is not None else []:
        held.update(lay.members)
        held.update(getattr(lay, "adopted", ()))
    asked = conn.get("lost_asked", ())
    left = conn.get("lost_left", ())
    for win in lost_windows.lost(held):
        hwnd = win["hwnd"]
        if hwnd in asked or hwnd in left:
            continue
        _offer_lost(conn, win)


def scan(layouts, conn: dict) -> None:
    """One pass: did a window HE opened appear? Blocking Win32 — the watcher
    runs it on a worker thread.

    Cheap in the common case, and that matters because this runs beside a
    0.25 s poll: with no recent double-click it costs one comparison and
    returns. The window sweep is only paid when he has just clicked twice."""
    seen = conn.get("birth_seen")
    if seen is None or conn.get("away") or conn.get("left"):
        return
    if not _double_clicked(conn):
        return
    members: set[int] = set()
    for other in getattr(layouts, "layouts", []):
        members.update(other.members)
        members.update(getattr(other, "adopted", ()))
    # The layout the phone is SHOWING — the only one whose work can claim a
    # window out from under this pass (see the one-window-one-question rule
    # below). Named here rather than in the loop above, because a loop
    # variable that leaks its last value is how a rule about the FOCUSED
    # layout would quietly become a rule about the last one in the list.
    focused = _focused(layouts, conn)
    for win in wm.list_windows():
        hwnd = win["hwnd"]
        if hwnd in seen:
            continue
        seen.add(hwnd)          # judged once, whatever the answer
        if wm.user32.GetWindow(hwnd, GW_OWNER):
            continue            # a dialog of something else, never a member
        if hwnd in members or hwnd in conn.get("birth_asked", ()):
            continue
        # ONE WINDOW, ONE QUESTION (owner report 2026-08-12, and his own log
        # dated it to the millisecond). This pass and the sweep below are two
        # features that never knew about each other, and at 20:29:58 they both
        # fired on the SAME window inside one tick:
        #
        #   New window python.exe "Controls …" offered as a layout (task 185)
        #   Popup     python.exe "Controls …" offered to the phone as 570a0a-3
        #
        # The phone has ONE chip strip and ONE live offer id, so the second
        # message silently replaced the first — and four more birth chips
        # followed within 400 ms. His single tap therefore answered a question
        # he had never read: the "Show in layout" one, whose yes runs
        # `_contain` and PLACES the window into the layout's region. That is
        # his report exactly — "it made the dimensions as if for the phone,
        # but there is no layout".
        #
        # So a window the focused layout can claim is the SWEEP's question,
        # never this one. A new layout from a window that already belongs to
        # the layout's own work was never a sensible offer anyway.
        if focused is not None and _attribute(focused, hwnd,
                                              _owner_root(hwnd), conn):
            continue
        _offer_birth(conn, win)


def pick(offer_id: str, act: str) -> bool:
    """His tap. `act` is "layout" (place it by the rules above) or anything
    else, which is "leave it on the desktop" — the safe answer, so an act we
    do not recognise lands on the one that moves nothing.

    Blocking Win32 on the accept path; the route below runs it in a thread."""
    _expire()
    offer = _OFFERS.pop(offer_id, None)
    if offer is None:
        return False
    lay, hwnd, conn = offer["lay"], offer["hwnd"], offer["conn"]
    if offer.get("lost"):
        # THE RESCUE (owner report 2026-08-12). `act` is "rescue" or anything
        # else, which is "leave it" — the safe answer, so an act we do not
        # recognise lands on the one that moves nothing, exactly as below.
        conn.get("lost_asked", set()).discard(hwnd)
        if act != "rescue":
            conn.setdefault("lost_left", set()).add(hwnd)
            logger.info("Lost window %s left where it is — his choice",
                        _describe(hwnd))
            return True
        # THE MONITOR IS ASKED FOR, NEVER REMEMBERED (constraint 13): `mon_rect`
        # is a callable the web layer put here, so a monitor switch between the
        # chip going out and his tap cannot land the rescue on a screen he
        # stopped watching.
        getter = conn.get("mon_rect")
        mon = getter() if callable(getter) else None
        # Either way the window leaves `lost_asked` (above) and NOT
        # `lost_left`: a rescue that failed is still a window he cannot reach,
        # so the next sweep asks again — and a rescue that worked simply is not
        # lost any more, which the sweep measures rather than remembers.
        return lost_windows.rescue(hwnd, mon)
    if offer.get("birth"):
        # Task 185's chip. NOTHING on the PC moves either way — a yes opens the
        # creation panel on the phone, seeded with this window, and every step
        # after that is the ordinary creation flow. All that is settled here is
        # that the question has been answered and will not be asked again.
        conn.get("birth_asked", set()).discard(hwnd)
        return bool(wm.user32.IsWindow(hwnd))
    # The question is answered, so it stops being a question. `popup_asked` is
    # ONLY "a chip is out for this window": what stops it being offered again
    # afterwards is his ANSWER — `popup_declined` for the desktop, membership
    # of `lay.adopted` for the layout. Keeping it here instead would make the
    # decline record dead code and hide the day it stopped working.
    conn.get("popup_asked", set()).discard(hwnd)
    if act != "layout":
        # Remembered, so the watcher does not ask again and never places it:
        # he has answered this window.
        conn.setdefault("popup_declined", set()).add(hwnd)
        logger.info("Popup %s stays on the desktop — his choice", _describe(hwnd))
        return True
    if not wm.user32.IsWindow(hwnd) or hwnd in lay.members:
        return False
    if hwnd not in lay.adopted:
        lay.adopted.append(hwnd)
    _contain(lay, hwnd, conn)
    return True


def register(app, token: str) -> None:
    """Add `POST /window_offer` — the phone's answer coming back.

    Over HTTP and not over the WebSocket for one honest reason: the socket's
    message dispatcher lives in [Web Layer](web.py), and this feature was
    built while that file was owned by another round. The route is the same
    shape every other one here has (token-gated, JSON in, `{ok}` out), and
    the page already speaks it for uploads.

    Registered from `server_core` beside the app, so nothing about it is
    hidden inside another module's setup."""
    @app.post("/window_offer")
    async def window_offer(request: Request):  # noqa: ANN202 — FastAPI route
        if request.query_params.get("token") != token:
            return JSONResponse({"ok": False}, status_code=403)
        try:
            data = await request.json()
        except (json.JSONDecodeError, ValueError):
            return JSONResponse({"ok": False}, status_code=400)
        ok = await asyncio.to_thread(pick, str(data.get("id") or ""),
                                     str(data.get("act") or ""))
        return JSONResponse({"ok": ok})


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
        _contain(lay, hwnd, conn)
        return "a window this layout already holds"
    if hwnd in conn.get("popup_declined", ()) or hwnd in conn.get("popup_asked", ()):
        # He said desktop, or he has been asked and has not answered. Either
        # way nothing here may move it — and it must not be re-offered on the
        # next of four polls a second.
        return ""

    reason = _attribute(lay, hwnd, root, conn)
    _judged(conn, hwnd)
    if not reason:
        return ""
    _offer(lay, hwnd, conn, reason)
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

# How often the desk is enumerated. Not every 0.25 s tick: `_top_level_hwnds`
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
    for hwnd in _top_level_hwnds():
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
        if hwnd in asked or hwnd in declined:
            continue
        reason = _attribute(lay, hwnd, _owner_root(hwnd), conn)
        if reason:
            pending.pop(hwnd, None)
            _judged(conn, hwnd)
            _offer(lay, hwnd, conn, f"{reason}, seen by the sweep")
            continue
        # Not yet attributable. Give it the grace above before writing it off
        # for good — `_judged` cannot be taken back.
        first = pending.setdefault(hwnd, now)
        if now - first >= SWEEP_GRACE_S:
            pending.pop(hwnd, None)
            _judged(conn, hwnd)
