# Window Claim — the maker's own statement that a window is ours

Source: [`server/window_claim.py`](../window_claim.py) ·
Asked by: [Layout Popup](layout_popup.md), [Layout Birth](layout_birth.md),
[Window Rescue](window_rescue.md) ·
Gate: [`tests/test_layout_popup.py`](../../tests/test_layout_popup.py)

## Why it is its own module

Split out of [Layout Popup](layout_popup.md) on 2026-08-17 at THE STRUCTURE
LAW's wall, and **by responsibility**. Every other rule in that module is a
GUESS about a window nobody told us anything about — a process match, an owner
chain, a click that happened to be recent — and each of those guesses is
exactly why the phone ASKS instead of acting.

This is the opposite kind of statement. It is not evidence weighed against
other evidence; it is the code that made the window saying so. The only correct
answer to it is **silence**: he already answered this question, with the tap
that made the window.

## Two records, because the first one arrives late

| | What it says | When it is written |
|---|---|---|
| `mine(hwnd)` | *this exact window is ours* | after the window exists and its handle is known |
| `expect(process)` | *a window of this process is about to appear because he asked* | **before** the act |

`is_ours(hwnd)` is true for either.

**`expect()` exists because `mine()` cannot be early enough, and that was
MEASURED** (owner report 2026-08-17; two independent agents, each with
file:line evidence). Every maker in this codebase works the same way: do the
thing, then watch for a window, then call `mine()`. What that costs:

* [`uia.extract_tab`](uia.md) leaves the torn-off window standing for up to
  **6–8 seconds** before the claim — it waits for the rect to stabilise, for
  the Explorer address band, for the foreground;
* [Layout Acts](layout_acts.md)' VS Code act only begins watching after the
  Command Palette sequence RETURNS, while VS Code can raise the window the
  instant Enter lands;
* [Recents](recents.md)' launch waits out a cold start.

Meanwhile [Layout Popup](layout_popup.md)'s `sweep` runs **every second** on an
independent thread, and its attribution has **no grace at all** for a window it
can tie to a member. Whoever looks first wins, and nothing arbitrates. That is
not a missing line — it is a race — so it is closed structurally: the claim is
armed before the act, and a claim deliberately names **no handle**, because the
whole difficulty is that the handle does not exist yet.

The two are not alternatives. The claim covers the gap; `mine()` marks the real
window and is what survives past the claim's short life.

## The honest limits

* **A claim is by PROCESS, so it is coarse.** For its `EXPECT_TTL_S` seconds,
  any new window of that exe counts as ours — including one a background agent
  happened to open in the same moment. The cost of that is one chip he does not
  get; the cost of the other direction is the chip he reported.
* **Both records are time-bounded, and they must be.** A handle is a number
  Windows re-uses, so a permanent set would one day silence a chip about a
  stranger's window that inherited the number.
* **Module-level, not per-connection.** The maker does not have a `conn` —
  `uia.extract_tab` is called on a worker thread — and a window we made is ours
  on every connection, not only the one that happened to be open.
