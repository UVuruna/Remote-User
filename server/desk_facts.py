"""What Windows says about the desk RIGHT NOW, read cheaply.

Split out of `layout_popup.py` on 2026-08-18 (THE STRUCTURE LAW, VC-R5). Three
readings and nothing else: which process a window belongs to, who started whom,
and every visible top-level handle. They are separated from the RULES that use
them because a rule is an argument and a reading is a fact — and because the
gates replace exactly these three functions to run without touching the
owner's real desk.

Nothing here caches. A cache would answer about a process table that has since
changed, and every question asked here is about something that just started.
"""

import ctypes
import ctypes.wintypes as wintypes

import window_manager as wm

# How many parent hops a window may be from a member's process and still be
# that member's work. A member starting a launcher that starts a browser is
# two; beyond a handful the link stops meaning anything.
ANCESTRY_HOPS = 4

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


def pid_of(hwnd: int) -> int:
    """The process a window belongs to (0 = unknown). Its own function because
    the gate replaces it — nothing here may enumerate the owner's real desk."""
    pid = wintypes.DWORD()
    wm.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def parent_pids() -> dict[int, int]:
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


def descends_from(pid: int, roots: set[int]) -> bool:
    """Was `pid` started by one of `roots` (child, grandchild, …)? Bounded by
    `ANCESTRY_HOPS` and by a seen-set, because a process table read from a
    live machine can contain a cycle after a PID was recycled."""
    if not pid or not roots:
        return False
    parents = parent_pids()
    seen = {pid}
    for _ in range(ANCESTRY_HOPS):
        pid = parents.get(pid, 0)
        if not pid or pid in seen:
            return False
        if pid in roots:
            return True
        seen.add(pid)
    return False


def top_level_hwnds() -> set[int]:
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
