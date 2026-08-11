# clipboard.js — the phone's half of the shared clipboard

**Task 182.** One job: `handleClipboardPush(text)` — the `clipboard {text}`
frame from the PC lands in the device clipboard. Inside the APK that is
`Android.setClipboard(text)` (ClipboardManager via the bridge — a NEW method,
never changed arity); in a dev browser it falls back to
`navigator.clipboard.writeText`, silently swallowed where the browser refuses
(clipboard write needs a user gesture outside the APK).

The held-while-away rule lives SERVER-side
([clipboard_sync](../../server/__about/clipboard_sync.md)): Android only lets
the foreground app write the clipboard, which the app is exactly while the
page is visible — so the server flushes the latest held text on connect and
the page applies it immediately.
