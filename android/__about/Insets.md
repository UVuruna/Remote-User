# Insets — what the window's edges do

**Folder:** [Android](../___android.md) ·
**Owner of the page:** [MainActivity](MainActivity.md)

## Purpose

Two things, both of them the platform's idea of where the window ends:

- **The system bars are hidden** while the PC is being controlled.
- **The keyboard's height is measured** and pushed to the page.

Split out of `MainActivity.kt` on 2026-08-09 (THE STRUCTURE LAW). One job, one
dependency — `WindowInsets` — and it is the seam where Android's idea of the
window meets the page's. Everything left in MainActivity is about WHICH page to
load and how to survive losing it.

## Why the keyboard height must come from here

The page's own reading is `window.innerHeight - visualViewport.height`. That is
correct **only while the window is resized by the IME**, which
`android:windowSoftInputMode="adjustResize"` used to guarantee.

It no longer does. This app targets SDK 35 and draws **edge-to-edge** with the
system bars hidden, and under edge-to-edge Android stops resizing the window
for the keyboard — the app is expected to read the `ime` inset itself. So
`adjustResize` sits in the manifest, honestly declared, and quietly does
nothing, and the page's subtraction is a subtraction of nothing.

**That zero is the whole history of one bug.** The owner reported six times
that the soft keyboard covers the row he is typing into — *"ja uopšte ne mogu
da brišem ni jednu reč koju pogrešim, zato što mi tastatura prekrije sve što
vidim"* (lang-ok: his own words, quoted). Five rounds rebuilt the RULE on the
page (`client/caret.js`), measured the caret on the PC, joined the seam in
`render.js` — and every one of them fed a correct rule a keyboard height of
zero. Nothing in the page could ever have found it: from inside the WebView the
keyboard genuinely does not exist.

`watchImeInsets` reads `WindowInsetsCompat.Type.ime()` and pushes the height in
**CSS pixels**, because that is what the page thinks in. Pushed rather than
polled: a keyboard opens and closes on the user's timing.

The page takes the LARGER of its own reading and this one — a zero from either
must never win over a real measurement, and a device that really does resize
its window keeps working exactly as before.

## Key Functions

| Name | What it does |
|------|--------------|
| `hideSystemBars()` | Immersive, transient-by-swipe. Re-applied on every focus gain — the system restores the bars after dialogs, app switches and the keyboard. |
| `watchImeInsets()` | Pushes `__imeHeight(cssPx)` to the page whenever the inset changes, and only when it changes. |
| `lastImeCss` | The last value pushed, so a re-layout that changes nothing costs no JavaScript call. |
| `forgetImeInset()` | Clears that memo and re-requests the insets. Called from `onPageFinished`. |

## Why the memo has to be forgotten on every page load

`lastImeCss` is file-scope, so it **outlives the document**. `window.__imeHeight`
does not — a fresh page starts knowing nothing. A keyboard reopened at the
**same height** after a reload (a reconnect, a re-pair, any `web.reload()`)
therefore matched the memo, was skipped as "no change", and the new page never
learned there was a keyboard at all: the caret rescue simply did not happen for
the rest of that session, silently, and only after a reload.

`forgetImeInset()` resets it to `-1` and calls `ViewCompat.requestApplyInsets`,
so the current inset is re-delivered down the **same listener** immediately
rather than waiting for the user to close and reopen the keyboard. One path to
the page, so the two can never disagree.
