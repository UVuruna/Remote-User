# Clipboard

**Script:** [Clipboard (script)](../clipboard.py)

## Purpose
Puts phone-sent content into the Windows clipboard, ready to paste. Two payloads (owner 2026-08-04): one image → `CF_DIB` bitmap (screenshot action + single-image upload — pastes into any image box); a LIST of files → `CF_HDROP` (multi-file / non-image uploads — exactly what Explorer's own Copy puts there, so Ctrl+V drops real files).

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
- `copy_text(text)` — plain text as **CF_UNICODETEXT** (UTF-16LE + the
  terminating NUL). What the phone's TYPED command buttons paste (owner
  2026-08-05 — the Claude set's `/usage`, `/model`, `/effort`): one atomic
  insert instead of a character storm through an autocomplete menu that
  re-filters on every keystroke.
- `copy_image(frame_bgr)`: numpy BGR frame → clipboard (`CF_DIB`); returns a success bool, never raises on a clipboard-busy condition
- `copy_files(paths)`: real files → clipboard (`CF_HDROP`: `DROPFILES` header + UTF-16 double-NUL list); same success-bool contract
- `_set_clipboard(fmt, payload, what)`: the shared open-retry / GlobalAlloc / SetClipboardData path both of the above use
