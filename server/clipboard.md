# Clipboard

**Script:** [Clipboard (script)](clipboard.py)

## Purpose
Writes a captured BGR frame into the Windows clipboard as a `CF_DIB` image — the tablet's SNAP button ends with a paste-ready screenshot on the PC (chat windows, editors, anywhere images paste).

Implementation notes that matter:
- 32-bit BGRX pixels (no DIB row padding), rows bottom-up per DIB convention
- All Win32 signatures declared explicitly — ctypes defaults truncate 64-bit handles/pointers to `int`, which corrupts `HGLOBAL` silently
- Clipboard open retried briefly (another app may hold it); every failure path is logged and returns `False`
- After a successful `SetClipboardData` the system owns the memory — it is only freed on failure

## Connections

### Uses
- Nothing project-internal (leaf module over user32/kernel32)

### Used by
- [Web Layer](web.md) — the `screenshot` message handler

## Functions
- `copy_image(frame_bgr)`: numpy BGR frame → clipboard; returns success bool
