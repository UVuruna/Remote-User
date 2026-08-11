# clipboard_sync — the PC clipboard reaches the phone

**Task 182 (owner order 2026-08-04 ~17:05, built 2026-08-11):** everything
copied lands on BOTH clipboards. Two paths, one module:

1. **After an injected Copy/Cut** (`after_copy_chord`) — the server reads the
   PC clipboard (CF_UNICODETEXT, retry ladder: `SendInput` returns before the
   target app fills the clipboard) and pushes `clipboard {text}` to the page.
2. **A copy made AT the PC** (`watch`, one task per connection) — a
   message-only window + `AddClipboardFormatListener`, on `focus_hook.py`'s
   proven listener-thread shape: the WNDPROC only signals; reads and pushes
   run off that signal, never on Windows' dispatch thread. Runs only while a
   phone session is live.

## Rules with teeth (tests/test_clipboard_sync.py, build-gated)

- A push while the page is hidden is **held, latest-only**, flushed on the
  return/connect — never dropped, never stale-over-newer.
- **No echo loops**: text the phone sent (`paste_text` → `note_written`) never
  returns to it; our own clipboard reads never re-push unchanged text.
- Text only — non-text formats are out of scope by the owner's scoping.

## Hard-won signatures

Every Win32 call carries explicit `restype`/`argtypes`: the ctypes default
(c_int) TRUNCATES 64-bit handles — `CreateWindowExW` raised OverflowError and
`GetClipboardData`→`GlobalLock` was a live access violation before the
signatures were pinned. `STOP_TIMEOUT_S` is 2.0 s: a daemon thread still
running its ctypes WNDPROC at interpreter teardown is a hard crash
(0xC000041D), so the stop join must outlast one full clipboard-retry ladder.

The page half is [clipboard.js](../../client/__about/clipboard.md); the shell
half is `Android.setClipboard(text)` — a NEW bridge method (the page is served
by the PC while the shell installs separately; changed arity stops resolving).
