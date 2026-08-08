"""The UI Automation layer: tab detection + extraction, focus cycling, caret.

Everything here speaks to Windows through UI Automation, and that is what
makes it one module: `uiautomation` (COM) must be initialized in whichever
thread makes the call, and `_uia()` is the single place that does it. Three
features ride on it — tab extraction (below), `next_input`'s walk through the
text fields, and the read the [Caret](caret.py) watch needs. The POLICY of
each of those lives with its own subject; only the UIA call lives here.

TAB EXTRACTION — Phase F+ step 2 (spec: ROADMAP → Layouts & Tab Control; probe
2026-08-02 verified all three strategies on the owner's machine). The unit of
selection is the TAB — a VSCode editor tab, Chrome tab or Explorer tab is
turned into its OWN OS window, which the layout machinery then arranges like
any window. Strategies in priority order (owner decision 2026-08-02 — the
app's real functionality first, simulation last):

1. The app's own context-menu command — right-click the tab, find a menu item
   whose name contains "new window" (Chrome `Move tab to new window`, VSCode
   `Move into New Window`), click it.
2. Explorer (no such command): read the tab's folder path from the address
   band, open `explorer.exe <path>` and close the original tab.
3. Universal fallback: simulated drag tear-off with real held-button
   interpolated SendInput moves (the probe proved Explorer's XAML tab strip
   IGNORES cursor-teleport drags), dropped on the taskbar strip — the one
   spot guaranteed outside every window rect (VSCode refuses to detach when
   the drop lands inside ANY VSCode window's rect, visually covered or not).

EVERY failure degrades to None and the caller uses the whole window — a tap
on something that merely looks like a tab (VSCode activity-bar icons are
TabItems too) self-corrects instead of erroring.

`uiautomation` (COM/UIA wrapper) is imported lazily and per-call inside a
thread initializer: the web layer calls these functions from asyncio worker
threads, and COM must be initialized in whichever thread runs the call. A
missing/broken uiautomation (e.g. exotic frozen environment) disables the tab
layer only — window layouts keep working.
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import os
import subprocess
import time
from contextlib import contextmanager

import window_manager

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

MENU_WAIT_S = 0.55        # owner 2026-08-02: extraction was visibly sluggish —
NEW_WINDOW_TIMEOUT_S = 6.0  # every wait here is trimmed to the working minimum
DRAG_GRAB_STEP_S = 0.02
DRAG_MOVE_STEP_S = 0.008
NEW_WINDOW_POLL_S = 0.12
TAB_MIN_WIDTH = 60        # px — narrower TabItems are activity-bar icons, not tabs
TAB_TOP_FRACTION = 0.15   # real tab strips live in the window's top 15%

# Only THESE apps get their tabs offered (owner decision 2026-08-03). UIA has
# no "this tab can become a window" property: an app's internal section
# switcher (the Pointer/Ring/Umbra pills in DOMY Watch's design pane) is a
# TabItem in the window's top strip exactly like a Chrome tab, and offering it
# cost 6 s of extraction that always fell back to the whole window. The list
# is the set of apps the extraction strategies actually cover — everything
# else is offered as a whole window only, and its UIA tree is never walked
# (which also makes the creation list visibly faster).
TAB_APPS = {
    "chrome.exe", "msedge.exe", "brave.exe", "opera.exe", "opera_gx.exe",
    "vivaldi.exe", "firefox.exe", "librewolf.exe",
    "code.exe", "code - insiders.exe", "cursor.exe", "windsurf.exe",
    "explorer.exe", "windowsterminal.exe",
}


def has_tabs(process: str) -> bool:
    """True when this process's TabItems are REAL content tabs (see TAB_APPS)."""
    return (process or "").lower() in TAB_APPS

# ---------------------------------------------------------------------------
# SendInput synthesis (server-side, not phone input): the extraction clicks
# and drags below are OUR OWN synthetic mouse — kept separate from the
# injector, which speaks phone-normalized coordinates and self-verifies.


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [("mi", _MOUSEINPUT)]
    _anonymous_ = ("i",)
    _fields_ = [("type", ctypes.c_ulong), ("i", _I)]


def _mouse(flags: int, x: int = 0, y: int = 0) -> None:
    gsm = user32.GetSystemMetrics
    vl, vt, vw, vh = gsm(76), gsm(77), gsm(78), gsm(79)
    inp = _INPUT()
    inp.type = 0
    if flags & 0x8000:  # ABSOLUTE → normalize to the virtual desktop
        inp.mi.dx = (x - vl) * 65535 // max(1, vw - 1)
        inp.mi.dy = (y - vt) * 65535 // max(1, vh - 1)
        flags |= 0x4000  # VIRTUALDESK
    inp.mi.dwFlags = flags
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _click(x: int, y: int, button: str = "left") -> None:
    down, up = (0x0002, 0x0004) if button == "left" else (0x0008, 0x0010)
    _mouse(0x0001 | 0x8000, x, y)
    time.sleep(0.04)
    _mouse(down)
    time.sleep(0.04)
    _mouse(up)
    time.sleep(0.04)


def _held_drag(x1: int, y1: int, x2: int, y2: int) -> None:
    """Real held-button drag: slow 40 px grab first (XAML strips need the
    drag state to engage), then interpolated travel, hover, release."""
    _mouse(0x0001 | 0x8000, x1, y1)
    time.sleep(0.15)
    _mouse(0x0002)
    time.sleep(0.25)
    for i in range(1, 9):
        _mouse(0x0001 | 0x8000, x1, y1 + 5 * i)
        time.sleep(DRAG_GRAB_STEP_S)
    n = 40
    for i in range(1, n + 1):
        _mouse(0x0001 | 0x8000,
               x1 + (x2 - x1) * i // n, (y1 + 40) + (y2 - (y1 + 40)) * i // n)
        time.sleep(DRAG_MOVE_STEP_S)
    time.sleep(0.4)
    _mouse(0x0004)
    time.sleep(0.2)


# ---------------------------------------------------------------------------
# UIA access (lazy, per-thread COM)

_uia_broken = False


@contextmanager
def _uia():
    """Yields the uiautomation module with COM alive in THIS thread, or None
    when the tab layer is unavailable (window layouts keep working)."""
    global _uia_broken
    if _uia_broken:
        yield None
        return
    try:
        import uiautomation as auto
    except Exception as e:  # noqa: BLE001 — any import failure disables tabs only
        logger.error("uiautomation unavailable — tab extraction disabled: %s", e)
        _uia_broken = True
        yield None
        return
    with auto.UIAutomationInitializerInThread():
        yield auto


def _tab_item_from(auto, control):
    """Walk `control` and a few ancestors looking for a TabItem (hit-tests
    often return an INNER element — probe finding)."""
    c = control
    for _ in range(6):
        if c is None:
            return None
        if c.ControlTypeName == "TabItemControl":
            return c
        c = c.GetParentControl()
    return None


def tab_at(mon_rect: tuple[int, int, int, int], nx: float, ny: float) -> dict | None:
    """The tab under a monitor-normalized point: {"name"} or None. Blocking —
    call via to_thread."""
    left, top, width, height = mon_rect
    px, py = int(left + nx * width), int(top + ny * height)
    with _uia() as auto:
        if auto is None:
            return None
        try:
            tab = _tab_item_from(auto, auto.ControlFromPoint(px, py))
            if tab is None or tab.IsOffscreen:
                return None
            return {"name": tab.Name}
        except Exception as e:  # noqa: BLE001 — a UIA hiccup must never kill the pick
            logger.warning("tab_at failed: %s", e)
            return None


# ---------------------------------------------------------------------------
# next_input — cycle keyboard focus through text-input fields

def focus_next_input(scope_hwnds: list[int] | None) -> str | None:
    """Move keyboard focus to the NEXT text-input field (Edit/Document
    elements), ordered top-to-bottom then left-to-right. Scope (owner spec):
    layout focus → only that layout's member windows; full desktop → every
    visible (non-minimized) window. Returns a short label for the toast, or
    None when no field exists. Blocking — call via to_thread."""
    with _uia() as auto:
        if auto is None:
            return None
        try:
            if scope_hwnds:
                windows = [h for h in scope_hwnds if window_manager.is_alive(h)]
            else:
                windows = [w["hwnd"] for w in window_manager.list_windows()
                           if not user32.IsIconic(w["hwnd"])]
            fields: list[tuple[int, object]] = []
            for hwnd in windows:
                win = auto.ControlFromHandle(hwnd)
                if win is None:
                    continue
                for ct in (auto.ControlType.EditControl, auto.ControlType.DocumentControl):
                    for c in _find_all(auto, win, ct):
                        try:
                            if (c.IsOffscreen or not c.IsEnabled
                                    or not getattr(c, "IsKeyboardFocusable", True)):
                                continue
                            r = c.BoundingRectangle
                        except Exception:  # noqa: BLE001 — a dying element mid-walk
                            continue
                        if r.width() < 20 or r.height() < 10:
                            continue
                        fields.append((hwnd, c))
            if not fields:
                return None
            fields.sort(key=lambda f: (f[1].BoundingRectangle.top,
                                       f[1].BoundingRectangle.left))
            focused_id = None
            try:
                focused_id = tuple(auto.GetFocusedControl().Element.GetRuntimeId())
            except Exception:  # noqa: BLE001 — nothing focused is normal
                pass
            idx = -1
            if focused_id:
                for i, (_, c) in enumerate(fields):
                    try:
                        if tuple(c.Element.GetRuntimeId()) == focused_id:
                            idx = i
                            break
                    except Exception:  # noqa: BLE001
                        continue
            hwnd, nxt = fields[(idx + 1) % len(fields)]
            # FOREGROUND, not always-on-top (audit 2026-08-05): this window
            # belongs to no layout, so a topmost raise here left an arbitrary
            # third-party window nailed above the owner's desk for the rest of
            # the Windows session, with no list that could ever name it again.
            window_manager.raise_window(hwnd, topmost=False)
            nxt.SetFocus()
            return nxt.Name or window_manager.window_at_hwnd(hwnd)["title"]
        except Exception as e:  # noqa: BLE001 — must fail soft
            logger.warning("next_input failed: %s", e)
            return None


# ---------------------------------------------------------------------------
# The caret — WHERE the typing lands on screen (policy: caret.py)

CARET_HOPS = 8        # element → … → a node that owns a real window handle
_caret_warned: set[str] = set()


def _warn_once(message: str) -> None:
    """A caret failure is logged ONCE per distinct message. This read runs
    several times a second for the life of a connection, so an app that always
    fails the same way would otherwise write the server log by itself — and
    that log is where the owner looks to find out why a feature did nothing."""
    if message in _caret_warned:
        logger.debug("caret: %s", message)
        return
    _caret_warned.add(message)
    logger.warning("Caret unreadable: %s", message)


def _element_window(auto, control) -> int:
    """The top-level window an element belongs to, or 0 for "cannot tell".

    The walk is not defensive padding: MEASURED on the owner's Chrome and
    VSCode 2026-08-08, the focused element itself reports
    `NativeWindowHandle == 0` and the handle appears two parents up.

    0 is a real answer and NOT a mismatch — see `caret_rect`. Measured the
    same day on his VSCode: while he types, the suggestion list holds UIA
    focus and the whole chain above those items carries no window handle at
    all, so treating 0 as "some other window" threw away every caret in the
    app that matters most to him."""
    node = control
    for _ in range(CARET_HOPS):
        if node is None:
            return 0
        handle = int(node.NativeWindowHandle or 0)
        if handle:
            return int(user32.GetAncestor(handle, window_manager.GA_ROOT) or handle)
        node = node.GetParentControl()
    return 0


def _range_rect(text_range) -> tuple[int, int, int, int] | None:
    """The first bounding rectangle of a text range, in screen pixels."""
    rects = text_range.GetBoundingRectangles()
    if not rects:
        return None
    r = rects[0]
    if r.height() <= 0:
        return None
    return (r.left, r.top, max(r.width(), 1), r.height())


def _text_caret(auto, control) -> tuple[int, int, int, int] | None:
    """The caret rect of a focused TEXT control, or None when the app exposes
    none — a real, measured answer for many apps, not an error.

    Two steps, and the second is load-bearing: a caret is a COLLAPSED range,
    and a provider is free to give a zero-length range no rectangle at all.
    Measured 2026-08-08 — the Claude Code chat box inside VSCode returns an
    empty rect list for its selection and the range expanded to one CHARACTER
    returns (1203, 936, 21, 21). VSCode's editor, by contrast, answers the
    plain selection with the caret's whole LINE — which is what the phone's
    keyboard actually has to clear."""
    if not hasattr(control, "GetTextPattern"):
        return None      # not a text control — how `uiautomation` says so
    pattern = control.GetTextPattern()
    if pattern is None:
        return None
    ranges = pattern.GetSelection()
    if not ranges:
        return None
    rect = _range_rect(ranges[0])
    if rect is not None:
        return rect
    expanded = ranges[0].Clone()
    expanded.ExpandToEnclosingUnit(auto.TextUnit.Character)
    return _range_rect(expanded)


def caret_rect(hwnd: int) -> tuple[int, int, int, int] | None:
    """Screen-pixel rect of the text caret inside `hwnd`, from whatever holds
    KEYBOARD focus. None when there is no caret to be had — the caller must
    report that as unknown and never as a position. Blocking (COM, ~4 ms
    measured) — call via to_thread.

    The focused element is asked for its owning window before its rect is
    used: keyboard focus is global, and a caret belonging to some OTHER window
    is not the caret of the window the phone is typing into. A window that
    cannot be named (0) is accepted, deliberately — keyboard focus lives in
    the foreground window, and refusing every element whose chain carries no
    handle refuses VSCode outright (measured 2026-08-08)."""
    with _uia() as auto:
        if auto is None:
            return None
        try:
            control = auto.GetFocusedControl()
            if control is None:
                return None
            owner = _element_window(auto, control)
            if hwnd and owner and owner != hwnd:
                return None
            return _text_caret(auto, control)
        except Exception as e:  # noqa: BLE001 — a UIA hiccup is "no caret", never a crash
            _warn_once(f"{type(e).__name__}: {e}")
            return None


# ---------------------------------------------------------------------------
# Extraction

def _find_all(auto, control, control_type):
    """Native FindAll of a control type under `control` (fast, one COM batch)."""
    from uiautomation.uiautomation import _AutomationClient
    cond = _AutomationClient.instance().IUIAutomation.CreatePropertyCondition(
        auto.PropertyId.ControlTypeProperty, control_type)
    arr = control.Element.FindAll(4, cond)  # TreeScope_Descendants
    return [auto.Control.CreateControlFromElement(arr.GetElement(i))
            for i in range(arr.Length)]


def _real_tabs(auto, hwnd: int) -> list:
    """The window's REAL content tabs: TabItems in the top strip, wide enough
    to carry a name — filters out VSCode activity-bar/panel icons and
    Explorer's Home-page pills (probe findings 2026-08-02)."""
    win = auto.ControlFromHandle(hwnd)
    if win is None:
        return []
    wr = win.BoundingRectangle
    if wr.height() <= 0:
        return []
    out = []
    for tab in _find_all(auto, win, auto.ControlType.TabItemControl):
        r = tab.BoundingRectangle
        if (not tab.IsOffscreen and r.width() >= TAB_MIN_WIDTH
                and (r.top - wr.top) < wr.height() * TAB_TOP_FRACTION):
            out.append(tab)
    return out


def list_tabs(mon_rect: tuple[int, int, int, int], hwnd: int) -> list[dict]:
    """Content tabs of one window as list entries: {"name", "x", "y"} with
    the tab centre monitor-normalized (the pick point extraction re-hits).
    Blocking — call via to_thread."""
    left, top, width, height = mon_rect
    with _uia() as auto:
        if auto is None:
            return []
        try:
            out = []
            for tab in _real_tabs(auto, hwnd):
                r = tab.BoundingRectangle
                out.append({
                    "name": tab.Name,
                    "x": (r.xcenter() - left) / width,
                    "y": (r.ycenter() - top) / height,
                })
            return out
        except Exception as e:  # noqa: BLE001 — a UIA hiccup yields an empty list
            logger.warning("list_tabs failed for %#x: %s", hwnd, e)
            return []


def _same_process_windows(process: str) -> set[int]:
    return {w["hwnd"] for w in window_manager.list_windows() if w["process"] == process}


def _wait_new_window(process: str, before: set[int]) -> int | None:
    deadline = time.monotonic() + NEW_WINDOW_TIMEOUT_S
    while time.monotonic() < deadline:
        new = _same_process_windows(process) - before
        if new:
            return new.pop()
        time.sleep(NEW_WINDOW_POLL_S)
    return None


def _find_tab_rect(auto, mon_rect, nx, ny, hwnd: int | None = None,
                   name: str | None = None) -> tuple[int, int, int, int] | None:
    """The tab's CURRENT rect. Name match within the window wins (tabs shift
    when the window is raised/re-ordered — a stale point would grab the wrong
    one); the pick point is the fallback."""
    if hwnd and name:
        try:
            for tab in _real_tabs(auto, hwnd):
                if tab.Name == name:
                    r = tab.BoundingRectangle
                    return (r.left, r.top, r.width(), r.height())
        except Exception:  # noqa: BLE001 — fall through to the point hit
            pass
    left, top, width, height = mon_rect
    tab = _tab_item_from(auto, auto.ControlFromPoint(
        int(left + nx * width), int(top + ny * height)))
    if tab is None:
        return None
    r = tab.BoundingRectangle
    if r.width() <= 0:
        return None
    return (r.left, r.top, r.width(), r.height())


def _try_context_menu(auto, tab_rect, target: dict, before: set[int]) -> int | None:
    """Strategy 1: right-click the tab, click the app's own '… new window'
    menu item (Chrome/Edge, VSCode; probe-verified names)."""
    root_before = {c.NativeWindowHandle for c in auto.GetRootControl().GetChildren()}
    cx, cy = tab_rect[0] + tab_rect[2] // 2, tab_rect[1] + tab_rect[3] // 2
    _click(cx, cy, "right")
    time.sleep(MENU_WAIT_S)
    sources = []
    for c in auto.GetRootControl().GetChildren():
        if c.NativeWindowHandle == target["hwnd"] or c.NativeWindowHandle not in root_before:
            sources.append(c)
    item = None
    for src in sources:
        try:
            for mi in _find_all(auto, src, auto.ControlType.MenuItemControl):
                if "new window" in (mi.Name or "").lower() and not mi.IsOffscreen:
                    item = mi
                    break
        except Exception:  # noqa: BLE001 — try the next source
            continue
        if item:
            break
    if item is None:
        auto.SendKeys("{Esc}")
        return None
    r = item.BoundingRectangle
    _click(r.xcenter(), r.ycenter())
    return _wait_new_window(target["process"], before)


def _try_explorer_path(auto, tab_rect, target: dict, before: set[int]) -> int | None:
    """Strategy 2 (Explorer only — it has no menu command and its address
    band knows the truth): select the tab, read the path, open a new window
    there, close the original tab."""
    cx, cy = tab_rect[0] + tab_rect[2] // 2, tab_rect[1] + tab_rect[3] // 2
    _click(cx, cy)  # select the picked tab so the address band shows ITS path
    time.sleep(0.4)
    path = None
    try:
        win = auto.ControlFromHandle(target["hwnd"])
        for tb in _find_all(auto, win, auto.ControlType.ToolBarControl):
            name = tb.Name or ""
            if name.startswith("Address"):
                path = name.split(":", 1)[1].strip() if ":" in name else None
                break
    except Exception as e:  # noqa: BLE001
        logger.warning("Explorer address read failed: %s", e)
    if not path or not os.path.exists(path):
        return None
    subprocess.Popen(["explorer.exe", path])
    hwnd = _wait_new_window(target["process"], before)
    if hwnd is None:
        return None
    # Close the original tab (Ctrl+W on the original window) — the content
    # now lives in its own window.
    # Both raises are stage directions, not layout membership: the SOURCE
    # window keeps its other tabs and the new window is not registered yet.
    # A topmost raise here stranded them both (audit 2026-08-05).
    window_manager.raise_window(target["hwnd"], topmost=False)
    time.sleep(0.25)
    auto.SendKeys("{Ctrl}w")
    time.sleep(0.2)
    window_manager.raise_window(hwnd, topmost=False)
    return hwnd


def _try_drag(tab_rect, target: dict, before: set[int],
              mon_rect: tuple[int, int, int, int]) -> int | None:
    """Strategy 3: tear-off drag onto the taskbar strip — outside every
    window rect (the VSCode condition) and proven on all three apps."""
    cx, cy = tab_rect[0] + tab_rect[2] // 2, tab_rect[1] + tab_rect[3] // 2
    ml, mt, mw, mh = mon_rect
    wl, wt, ww, wh = window_manager._work_area(mon_rect)
    drop_x = ml + mw - 400
    drop_y = min(wt + wh + 25, mt + mh - 5)
    _held_drag(cx, cy, drop_x, drop_y)
    time.sleep(1.2)
    return _wait_new_window(target["process"], before)


def extract_tab(mon_rect: tuple[int, int, int, int], nx: float, ny: float,
                target: dict, tab_name: str | None = None) -> int | None:
    """Turn the picked tab into its own window; returns the new hwnd or None
    (caller falls back to the whole window). `tab_name` (from the offer/list)
    re-finds the tab by NAME after the window is raised — tabs shift, a stale
    point grabs the wrong one. Blocking, seconds — call via to_thread."""
    with _uia() as auto:
        if auto is None:
            return None
        try:
            # The SOURCE window — it stays behind with its remaining tabs
            # and never becomes a layout member, so it must never be left in
            # the always-on-top band (audit 2026-08-05).
            window_manager.raise_window(target["hwnd"], topmost=False)
            time.sleep(0.15)
            tab_rect = _find_tab_rect(auto, mon_rect, nx, ny,
                                      target["hwnd"], tab_name)
            if tab_rect is None:
                return None
            before = _same_process_windows(target["process"])
            proc = target["process"].lower()
            if proc == "explorer.exe":
                hwnd = _try_explorer_path(auto, tab_rect, target, before)
            else:
                hwnd = _try_context_menu(auto, tab_rect, target, before)
            if hwnd is None:
                # the tab may have moved after a failed attempt — re-find it
                tab_rect = _find_tab_rect(auto, mon_rect, nx, ny,
                                          target["hwnd"], tab_name) or tab_rect
                hwnd = _try_drag(tab_rect, target, before, mon_rect)
            return hwnd
        except Exception as e:  # noqa: BLE001 — extraction must fail soft
            logger.error("Tab extraction failed: %s", e)
            return None
