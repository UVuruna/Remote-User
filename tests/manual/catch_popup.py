"""CATCH THE POPUP: run this, then make the popup happen. It says exactly what
that popup IS.

Why this exists: the owner reports that when an agent produces an HTML report
in his VS Code, something pops up with an OPEN button that launches Chrome —
and that this is the window our layout code mishandles. Two completely
different things can look like that on screen:

  A. A REAL top-level Windows window (owned by VS Code, or owned by nothing).
     Our code can see it, attribute it and place it.
  B. An overlay VS Code DRAWS INSIDE ITSELF. It is not a window at all — no
     hwnd, no owner, nothing for us to move. If it is this, no amount of work
     in layout_popup.py can ever touch it, and saying otherwise would be a
     lie.

Guessing which one it is has already cost this project a round. So it is
measured instead.

USAGE
    .venv\\Scripts\\python.exe tests\\manual\\catch_popup.py

Then trigger the popup. Every window that appears, changes its enabled state,
or disappears is printed the moment it happens, with its owner chain, process
and rect. Ctrl+C to stop; it prints a summary of everything it saw.
"""
import ctypes
import ctypes.wintypes as w
import os
import sys
import time

u = ctypes.windll.user32
k32 = ctypes.windll.kernel32
u.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

GW_OWNER = 4
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080

POLL_S = 0.15


def title(h):
    n = u.GetWindowTextLengthW(h)
    if not n:
        return ""
    b = ctypes.create_unicode_buffer(n + 1)
    u.GetWindowTextW(h, b, n + 1)
    return b.value


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    u.GetClassNameW(h, b, 256)
    return b.value


def rect(h):
    r = w.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def pid_of(h):
    p = w.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


_names: dict[int, str] = {}


def process_name(pid):
    if pid in _names:
        return _names[pid]
    name = "?"
    h = k32.OpenProcess(0x1000, False, pid)      # LIMITED_INFORMATION
    if h:
        size = w.DWORD(260)
        buf = ctypes.create_unicode_buffer(260)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            name = os.path.basename(buf.value)
        k32.CloseHandle(h)
    _names[pid] = name
    return name


def snapshot():
    out = {}

    def cb(h, _l):
        if not u.IsWindowVisible(h) and not u.IsIconic(h):
            return 1
        t = title(h)
        if not t:
            return 1
        out[h] = {
            "title": t,
            "cls": cls(h),
            "pid": pid_of(h),
            "owner": u.GetWindow(h, GW_OWNER),
            "enabled": bool(u.IsWindowEnabled(h)),
            "rect": rect(h),
            "tool": bool(u.GetWindowLongW(h, GWL_EXSTYLE) & WS_EX_TOOLWINDOW),
        }
        return 1

    u.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_int, w.HWND, w.LPARAM)(cb), 0)
    return out


def describe(h, d, mark):
    owner = d["owner"]
    line = (f"{mark} {h:#x}  {process_name(d['pid'])}  cls={d['cls']}\n"
            f"      title  : {d['title'][:95]}\n"
            f"      rect   : {d['rect']}   enabled={d['enabled']}"
            f"   toolwindow={d['tool']}")
    if owner:
        line += (f"\n      OWNED BY {owner:#x} — {title(owner)[:70]}"
                 f"\n      >>> a real owned dialog: our code CAN place it")
    else:
        line += "\n      >>> a top-level window, owned by nothing"
    return line


def main():
    print(__doc__.split("USAGE")[0].rstrip())
    print("=" * 72)
    print("WATCHING. Trigger the popup now. Ctrl+C to stop.\n")
    before = snapshot()
    seen_new = {}
    try:
        while True:
            time.sleep(POLL_S)
            now = snapshot()
            for h, d in now.items():
                if h not in before:
                    print(describe(h, d, "NEW    "), "\n", flush=True)
                    seen_new[h] = d
                elif before[h]["enabled"] != d["enabled"]:
                    state = "ENABLED" if d["enabled"] else "DISABLED"
                    print(f"{state:7} {h:#x}  {d['title'][:70]}\n"
                          f"      >>> a modal is holding it"
                          if not d["enabled"] else
                          f"{state:7} {h:#x}  {d['title'][:70]}", flush=True)
                elif before[h]["rect"] != d["rect"]:
                    print(f"MOVED   {h:#x}  {before[h]['rect']} -> {d['rect']}"
                          f"   {d['title'][:60]}", flush=True)
            for h, d in before.items():
                if h not in now:
                    print(f"GONE    {h:#x}  {d['title'][:70]}\n", flush=True)
            before = now
    except KeyboardInterrupt:
        print("\n" + "=" * 72)
        print(f"SUMMARY — {len(seen_new)} new window(s) appeared while watching")
        for h, d in seen_new.items():
            print("\n" + describe(h, d, "       "))
        if not seen_new:
            print("\nNOTHING NEW APPEARED. If a popup was visible on screen "
                  "during this run,\nit is NOT a Windows window — VS Code drew "
                  "it inside itself, and no\ncode of ours can ever move it. "
                  "That is a real answer, not a failure.")


if __name__ == "__main__":
    sys.exit(main())
