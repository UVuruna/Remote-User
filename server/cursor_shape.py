"""WHICH CURSOR THE PC IS SHOWING, resolved to a short stable NAME.

Owner request 2026-08-09 (task 142). The phone draws the pointer itself —
DXGI capture never contains it — and until now it drew ONE fixed arrow. From
the tablet that made a draggable window edge, a text box and plain background
look identical, so the one thing a cursor is FOR (telling you what the pixel
under it will do) was missing. His words, which are also the acceptance test:
# lang-ok: owner quote
"prikazi mi stvarni kursor kako izgleda, a ne da stalno bude strelica, tako da znam da tu mogu da kliknem i da promenim dimenzije prozora."

HOW it is read: `GetCursorInfo` hands back the HCURSOR the system is showing
right now, and every SYSTEM cursor has a stable handle obtainable from
`LoadCursorW(NULL, IDC_*)`. Matching the two names the shape without ever
touching pixels — no image travels to the phone, only a word from the table
below, on the `cursor` message that already flows.

Three rules this module exists to keep:

1. **The handles are resolved ONCE.** This runs inside the ~30 Hz cursor
   loop; a `LoadCursorW` sweep per frame would be a per-frame syscall storm
   for an answer that changes only when the user changes their cursor SCHEME.
2. **An unmatched handle is never a guess.** Applications ship their own
   cursors (a browser's custom drag image, a game, a paint tool) and those
   match nothing here. The honest answer is `custom` — the phone then draws
   the plain arrow. A near-miss ("looks like a resize one") would be worse
   than the arrow: it would tell him an edge is grabbable when it is not.
3. **Nothing here touches DPI or injection.** Only `hCursor` is read;
   `ptScreenPos` is deliberately ignored (position stays
   `input_injector.cursor_norm()`'s job, mapped through the monitor rect), so
   the process-wide DPI declaration this project depends on is untouched.

See server/__about/cursor_shape.md.
"""

import ctypes
import ctypes.wintypes as wintypes
import logging
import time

logger = logging.getLogger(__name__)

user32 = ctypes.windll.user32

# ═══════════════════════════ WIN32 ═══════════════════════════
# IDC_* — the system cursor resource ids (winuser.h). Passed to LoadCursorW
# as MAKEINTRESOURCE, i.e. the bare integer in the pointer argument.
IDC_ARROW = 32512
IDC_IBEAM = 32513
IDC_WAIT = 32514
IDC_CROSS = 32515
IDC_UPARROW = 32516
IDC_SIZENWSE = 32642
IDC_SIZENESW = 32643
IDC_SIZEWE = 32644
IDC_SIZENS = 32645
IDC_SIZEALL = 32646
IDC_NO = 32648
IDC_HAND = 32649
IDC_APPSTARTING = 32650
IDC_HELP = 32651

CURSOR_SHOWING = 0x00000001


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE),
        ("ptScreenPos", wintypes.POINT),
    ]


# Both handles are 64-bit pointers: without an explicit restype ctypes would
# truncate them to a C int and EVERY cursor would resolve to "custom".
user32.LoadCursorW.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
user32.LoadCursorW.restype = ctypes.c_void_p
user32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
user32.GetCursorInfo.restype = wintypes.BOOL

# ═══════════════════════════ THE NAME TABLE ═══════════════════════════
# The whole protocol surface of this feature: the words that may ride the
# `cursor` message. Short, lowercase, hyphenated — the phone's drawn-shape
# table (client/cursor-shapes.js) is keyed by exactly these, and the gate
# (tests/test_cursor_shape.py) fails the build if the two ever disagree.
#
# `move` rather than "size-all": what IDC_SIZEALL means to the person looking
# at it is "this window/object moves", and the phone already calls that shape
# move (ICONS.move, owner 2026-08-05).
ARROW = "arrow"
CUSTOM = "custom"

SYSTEM_CURSORS: tuple[tuple[int, str], ...] = (
    (IDC_ARROW, ARROW),
    (IDC_IBEAM, "ibeam"),
    (IDC_WAIT, "wait"),
    (IDC_CROSS, "cross"),
    (IDC_UPARROW, "up-arrow"),
    (IDC_SIZENWSE, "size-nwse"),
    (IDC_SIZENESW, "size-nesw"),
    (IDC_SIZEWE, "size-we"),
    (IDC_SIZENS, "size-ns"),
    (IDC_SIZEALL, "move"),
    (IDC_NO, "no"),
    (IDC_HAND, "hand"),
    (IDC_APPSTARTING, "app-starting"),
    (IDC_HELP, "help"),
)

# How long an unmatched handle may go unquestioned before the table is loaded
# again. Windows hands out NEW handles for every system cursor when the user
# switches cursor SCHEME (Settings -> Mouse -> Cursor style, or an accessibility
# size change), and a table cached at start would then call every cursor on the
# machine "custom" for the rest of the session. Re-reading is bounded to one
# sweep of 14 LoadCursorW calls per interval, and only while something
# unmatched is actually on screen.
RELOAD_SECONDS = 5.0


def _load_system_cursor(idc: int) -> int | None:
    """The one Win32 call this module's resolution depends on — a separate
    function so the gate can drive the REAL resolver with faked handles
    instead of faking the resolver itself."""
    return user32.LoadCursorW(None, idc)


class CursorNamer:
    """Handle -> name, with the system table cached across frames."""

    def __init__(self, load=_load_system_cursor, clock=time.monotonic) -> None:
        self._load = load
        self._clock = clock
        self._by_handle: dict[int, str] = {}
        self._loaded_at = 0.0

    def _reload(self) -> None:
        table: dict[int, str] = {}
        for idc, name in SYSTEM_CURSORS:
            handle = self._load(idc)
            # A handle we cannot get is not a failure worth a log line per
            # frame: the cursor simply resolves to `custom` and the phone
            # draws the arrow. Only a WHOLE table coming back empty is odd.
            if handle:
                table.setdefault(int(handle), name)
        self._by_handle = table
        self._loaded_at = self._clock()
        if not table:
            logger.warning("No system cursor handles could be loaded — "
                           "every cursor will be reported as %r", CUSTOM)

    def name_for(self, handle: int | None) -> str:
        """The name for a live HCURSOR. Anything not in the system table is
        `custom` — an application's own cursor, which we must never dress up
        as a shape we recognise."""
        if handle is None:
            return CUSTOM
        handle = int(handle)
        if not self._by_handle:
            self._reload()
        name = self._by_handle.get(handle)
        if name is not None:
            return name
        # Unmatched: either a genuinely custom cursor, or the scheme changed
        # under us and every handle in the table is stale. Asking again costs
        # one bounded sweep per RELOAD_SECONDS, never one per frame.
        if self._clock() - self._loaded_at >= RELOAD_SECONDS:
            self._reload()
            name = self._by_handle.get(handle)
            if name is not None:
                return name
        return CUSTOM

    def current(self) -> str | None:
        """The cursor Windows is showing right now, or None when it cannot be
        read at all (a UAC secure desktop, the lock screen — the same moments
        `cursor_norm()` returns None). A HIDDEN cursor (fullscreen video, a
        game that draws its own) reports the plain arrow: the phone must keep
        drawing SOMETHING to aim with, and the arrow is the honest default."""
        info = CURSORINFO()
        info.cbSize = ctypes.sizeof(CURSORINFO)
        if not user32.GetCursorInfo(ctypes.byref(info)):
            return None
        if not (info.flags & CURSOR_SHOWING):
            return ARROW
        return self.name_for(info.hCursor)


_namer: CursorNamer | None = None


def current_cursor_name() -> str | None:
    """Process-wide entry point for the ~30 Hz cursor loop (server/web.py).
    One namer, so the system table is loaded once for the whole run."""
    global _namer
    if _namer is None:
        _namer = CursorNamer()
    return _namer.current()
