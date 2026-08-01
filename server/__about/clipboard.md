# Clipboard

**Script:** [Clipboard (script)](../clipboard.py)

## Purpose
Writes a captured BGR frame into the Windows clipboard as a `CF_DIB` image. Two callers use it: the tablet's screenshot action (paste the PC screen somewhere on the PC) and the phone→PC image upload (paste a phone photo into the focused box).

Implementation notes that matter:
- 32-bit BGRX pixels (no DIB row padding needed), rows written bottom-up per the DIB convention
- Every Win32 signature is declared explicitly — ctypes' default argument/return types truncate 64-bit handles and pointers to a plain `int`, which corrupts `HGLOBAL` silently
- Clipboard `Open` is retried briefly (another app may hold it momentarily); every failure path is logged and returns `False` — no exception, no silent no-op
- After a successful `SetClipboardData` the system owns the memory — it is freed manually only on the failure path

## Connections

### Uses
- Nothing project-internal (leaf module over `user32`/`kernel32`)

### Used by
- [Web Layer](web.md) — the `screenshot` message handler and the `/upload` route

## Functions
- `copy_image(frame_bgr)`: numpy BGR frame → clipboard; returns a success bool, never raises on a clipboard-busy condition
