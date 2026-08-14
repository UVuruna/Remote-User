# ScreenAwake — what is on screen, and whether the screen stays lit

**Folder:** [Android](../___android.md) ·
**Owner of the page:** [MainActivity](MainActivity.md)

## Purpose

One question in two halves:

- **`showLayer(error, loading)`** — which layer is on screen: the native error
  card, the "Connecting…" loader, or the live page.
- **`ScreenAwake`** — whether `FLAG_KEEP_SCREEN_ON` may be held, which is
  decided by exactly that.

Split out of `MainActivity.kt` on 2026-08-14 (THE STRUCTURE LAW, the same seam
[Insets](Insets.md) was cut on). MainActivity is about WHICH page to load and
how to survive losing it; this is one job with one dependency — the window.

## T80a — the flag had one owner, and it was not always alive

`FLAG_KEEP_SCREEN_ON` used to be added once in `onCreate` and cleared by
exactly one thing: the PAGE, through `Bridge.keepAwake(false)` after three idle
minutes. That fixed the case it was written for and left the other half open.

Whenever the native error card is up — no network, PC unreachable, Tailscale
missing or off — **there is no page at all**. Nothing could clear the flag, so
the phone held its screen on, indefinitely, over a card saying the session was
dead. The screen is by far the biggest battery consumer a phone has, and this
is the state a phone sits in longest: in a bag, out of Wi-Fi range, with the
app left open.

**Ownership is therefore inverted.** The shell owns the flag, because only the
shell knows whether a live session is on screen at all; the page owns one INPUT
to it and keeps the full power it had — releasing the screen mid-session is the
presence signal the whole layout design rests on. It simply can no longer FAIL
to release it, because it is no longer the only thing that can.

Held only while ALL of these are true at once:

| Input | Written by |
|-------|-----------|
| `started` — a window is on screen | `onStart` / `onStop` |
| `pageAlive` — a document really loaded (a failed load is not one) | the WebViewClient callbacks |
| neither the error card nor the loader is visible | `showLayer` |
| the page has not asked us to let go | `Bridge.keepAwake` → `pageAsked` |

A document that goes away and comes back is a NEW page which has not called
`keepAwake` yet, so `apply()` restores the wish the moment a live page returns
(`sawLivePage`) — otherwise a page that released the screen and was then
reloaded could never take it back.

## Why `showLayer` is a funnel and not two assignments

The six places that used to set `errorView`/`loadingView` visibility directly
are exactly the places the awake rule has to be re-weighed. Keeping the two in
step by hand at six call sites is how a rule ships correct and never runs; one
funnel means no future call site can raise the error card without the screen
following it. An argument left out is left exactly as it stands, so
`onPageStarted` can hide the card without deciding anything about the loader.

## Key Functions

| Name | What it does |
|------|--------------|
| `showLayer(error, loading)` | Sets whichever layer was named and re-applies the awake rule. |
| `ScreenAwake.apply(host)` | The ONE writer of `FLAG_KEEP_SCREEN_ON` in the shell. Idempotent. |
| `ScreenAwake.pageAsked(host, on)` | Records the page's wish (`Bridge.keepAwake`) and re-applies. |

## Connections

### Uses

- `MainActivity` — `errorView`, `loadingView`, `started`, `pageAlive`, `window`

### Used by

- [MainActivity](MainActivity.md) — `onStart`, `onStop`, the resolver, the
  error card, the WebViewClient callbacks
- [Bridge](Bridge.md) — `keepAwake(on)`

## Gate

`tests/test_shell_battery.py` (fail-closed in `setup/gates.py`, 0b14/6): the
flag has exactly one writer in the whole shell, the rule weighs all four
inputs, and the error card, the background and a finished load each re-apply
it. Kotlin cannot be executed in this repo — there is no JVM test runner — so
the checks read the source and assert the structural promises; what the phone
really does is proven only on the owner's device.
