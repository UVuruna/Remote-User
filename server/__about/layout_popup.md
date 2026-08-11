# Layout Popup

**Script:** [Layout Popup (script)](../layout_popup.py) ·
**Flow:** [flow](../__flow/layout_popup.md)

## Purpose
Decide **whose window just appeared**, and — when it is the layout's own work —
put it where the phone can operate it.

## The failure this module exists to prevent
Owner report 2026-08-10, repeated furiously on 2026-08-11 (task 202,
escalated). He was watching a LAYOUT on the phone when an agent on the PC
finished a job and opened its HTML report. The window landed OUTSIDE the
layout's region:

* it is **below** the members, which are always-on-top while the phone shows
  them ([Window Manager](window_manager.md) → the topmost ledger), so nothing
  on the phone can bring it forward;
* the one way "out" — choosing Desktop — **minimizes every member** (owner rule
  2026-08-02), which loses his place of work and the popup with it.

He could see the thing he wanted and could not touch it. His rule is now the
specification: *nothing that belongs to the layout's work may open outside the
layout's dimensions — if it cannot fit those dimensions, open it separate, over
the whole screen.*

## The rules
0. **He is ASKED, never overruled** (his amendment the same day, and it
   outranks everything below it): a window this module attributes to the
   layout produces one CHIP on the phone — *Show in layout* / *Leave on
   desktop* — and nothing on the PC moves until he taps. The prompt is on the
   PHONE and never on the PC: a PC-side dialog would itself be an unreachable
   popup, which is the disease. Ignoring the chip is a real answer and the
   answer is the desktop. One chip per window (`popup_asked`), a decline is
   remembered (`popup_declined`) and never asked again, and his tap comes back
   through `POST /window_offer` (registered from `server_core`, answered by
   `pick()`) — over HTTP because the socket's dispatcher lives in `web.py`,
   which another round owned while this was built.
1. **Attribution first, placement second.** This PC is never quiet: other
   agents launch GUI apps all day, which is exactly why
   [Focus Guard](focus_guard.md) refuses a foreground the phone did not choose.
   That refusal stays. Only a window this module can ATTRIBUTE to the focused
   layout is ever touched.
2. **Three attribution tiers, and nothing else counts.**
   * a **dialog of a member** — the owner chain (`GW_OWNER`) walked up, exactly
     as the guard already walks it. The "Open this link?" prompt is his case.
   * a **NEW top-level window of a member's process**. `NEW` is load-bearing:
     process identity may never decide alone (CLAUDE.md constraint 11 — every
     VS Code window shares one process, and his other project's window is
     exactly the thief). A window that already existed when the phone connected
     is refused however well its process matches.
   * a **NEW window of a process a member started** — the parent links in the
     process table, up to `ANCESTRY_HOPS`.
3. **Fit is MEASURED, never assumed** (constraint 13, the lesson the Move
   handle cost four rounds). The region is the union of the members' real frame
   rects, read fresh. A popup that fits is placed inside it at its own size,
   centered. One that does not is ASKED to take the region — a resizable window
   simply obeys — and only its refusal, which is what a minimum size larger
   than the region looks like from here, sends it full screen over the streamed
   monitor.
4. **Whatever we raise, the ledger owes a way back down** (constraint 10).
   Placement goes through `place_window`, so the popup enters the ledger with
   the members; the layout carries the list (`Layout.adopted`) and
   [Layout Registry](layout_registry.md) releases it on every path where the
   layout stops being what the phone shows — another layout focused, Desktop,
   removal, the phone gone, the popup closed at the desk.
5. **It is not a member.** The grid does not grow, nothing is re-arranged
   around it, and it is **never closed** with the layout: only the ✕ chooser
   closes windows, and only the ones he chose (task 116).
6. **Desktop does not minimize it.** Members are minimized, the popup is only
   let go of — minimizing the report he chose Desktop to reach would be the
   original failure in a new place.

## The honest limits
* **An already-running third-party app cannot be attributed.** An agent that
  opens its report in a Chrome that was already running gets a window from a
  process nobody in this layout started, whose parent died long ago. Nothing
  ties it to the layout, so it is refused like any stranger. What this module
  does catch is the common shape of the same failure: the member's own dialog,
  its own second window, and the viewer or browser it launches itself.
* **Parent PIDs can be recycled.** The newness requirement bounds a wrong
  answer to windows created during this phone session.
* **Before the baseline exists, nothing is new.** `baseline()` is taken once
  per connection by `focus_guard.watch`; until it has run, this module does
  nothing at all and the fence behaves exactly as it did before task 202.
* **A window that refuses every rect is left alone** after
  `MAX_CONTAIN_TRIES`, logged by name — it is still in `Layout.adopted`, so the
  ledger still owes it the way back down, and it is not fought four times a
  second for the rest of the session.

## Gate
`tests/test_layout_popup.py`, fail-closed in `setup/build.py` (0ad/6). Fifteen
checks, each proven by planting its own defect: the offer replaced by an
auto-grab, the chip re-sent on every poll, the decline forgotten, `pick`
ignoring his answer, the chip never reaching the phone, containment removed,
attribution loosened to "any new window", the newness rule dropped, the
full-screen branch removed, the release removed, the prune's clean-up removed,
the measurement removed (re-placed on every poll), the try cap removed, and the
watcher made to act while the phone is away.
