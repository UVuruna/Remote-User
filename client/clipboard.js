// THE CLIPBOARD LIVES ON BOTH DEVICES (task 182, owner order ~2026-08-11
// 17:05): the server pushes `clipboard {text}` after an injected Copy/Cut,
// and again for a copy made AT THE PC while this phone is watching
// (server/clipboard_sync.py). This module is the one place that hands that
// text to the device — the shell's `Android.setClipboard` bridge method
// (android/.../Bridge.kt, NEW — never a changed-arity method, the
// page-served-vs-shell-installed rule) when running inside the APK, and
// `navigator.clipboard.writeText` as the dev-browser fallback, silently
// skipped where the browser refuses it (no secure context, no focus — a
// permission prompt for a plain browser tab is not this feature's job).
//
// TEXT ONLY (owner scoping) — the server never sends anything else.

function handleClipboardPush(text) {
  if (typeof text !== "string" || !text) return;
  if (window.Android && typeof window.Android.setClipboard === "function") {
    window.Android.setClipboard(text);
    return;
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).catch(() => {
      // Dev-browser fallback only — a refusal here (no focus, insecure
      // context) is not user-facing; the APK path above is what matters.
    });
  }
}
