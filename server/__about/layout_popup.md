# Layout Popup

**Split out of this module on 2026-08-17, both by responsibility:**
[Window Claim](window_claim.md) — the maker's own statement that a window
is ours, which is the one statement here that is not a guess · [Window Rescue](window_rescue.md) — can he REACH it, which geometry
answers outright and which therefore needs no history at all.

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
   * a **NEW window seen within `CLICK_GRACE_S` of an INJECTED click** (task
     240) — checked LAST, only when none of the process ties above fired. This
     is the ONE tier with no process evidence at all: it exists for an
     already-running third-party app (his old Chrome, parent long dead) that a
     click through the stream just opened a window in. It reuses the exact
     `click_times` task 185's `note_click` already fills from every left click
     or press (`web.py`) — one source of "did he just click", two features
     that ask it slightly different questions.
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

## Two eyes, because the foreground was never one (task 239, 2026-08-11)
His FOURTH report of this failure carried the mechanism in his own words: the
chip appeared, but only after he **left the layout and came back** — and then
everything worked. `handle()` is reached from `focus_guard._decide` and only
ever with the FOREGROUND window, and a foreground that IS a member returns one
line earlier. The window this module was written about cannot have the
foreground:

* the members are always-on-top while the phone shows them (constraint 10), so
  it opens UNDER them;
* Windows refuses `SetForegroundWindow` to a process with no user input of its
  own and flashes a taskbar button instead — an agent's browser opening an HTML
  report is exactly that process;
* and if it stole the foreground for an instant, `focus_guard.watch`'s own
  defence hands focus straight back into the layout.

So `sweep()` asks the question by ENUMERATION instead: every
`SWEEP_EVERY_S` the watcher lists the top-level windows, and one that is new
since the baseline runs through the SAME attribution and the SAME `_offer`.
It moves nothing — no raise, no placement, no foreground — and it shares
`popup_asked` / `popup_declined` / `popup_known` with the foreground path, so
a window one eye offered can never be offered again by the other. `_judged` is
permanent, so a window that cannot yet be identified is retried for
`SWEEP_GRACE_S` before it is written off: a look taken a moment too early would
otherwise make it a stranger for the whole session.

## The honest limits
* **An already-running third-party app IS now attributed, but only through a
  click** (task 240). Without one within `CLICK_GRACE_S` it is still refused
  like any stranger — the process-tie rules above still catch the far more
  common shape of the same failure: the member's own dialog, its own second
  window, the viewer or browser it launches itself; the click rule is only the
  fallback for the one shape they cannot reach.
* **The click grace is a coincidence window, not proof.** Any new top-level
  window appearing within `CLICK_GRACE_S` of an injected click is offered,
  whoever really opened it. The cost of a wrong guess is a chip he declines,
  never a moved window — nothing places, raises or grabs anything before his
  own tap.
* **A new TAB is not a new window** and is out of this module's scope
  entirely, for every attribution tier including the click one.
* **Parent PIDs can be recycled.** The newness requirement bounds a wrong
  answer to windows created during this phone session.
* **Before the baseline exists, nothing is new.** `baseline()` is taken once
  per connection by `focus_guard.watch`; until it has run, this module does
  nothing at all and the fence behaves exactly as it did before task 202.
* **Detection is bounded by the sweep's cadence**, not instant: up to
  `SWEEP_EVERY_S` (1 s) after the window appears, plus `SWEEP_GRACE_S` (3 s)
  more when it could not be identified on the first look. The foreground path
  is still the faster one when a window does take the foreground.
* **A window that refuses every rect is left alone** after
  `MAX_CONTAIN_TRIES`, logged by name — it is still in `Layout.adopted`, so the
  ledger still owes it the way back down, and it is not fought four times a
  second for the rest of the session.

## Gate
`tests/test_layout_popup.py`, fail-closed in `setup/build.py` (0ad/6).
Twenty-three checks, each proven by planting its own defect: the offer
replaced by an auto-grab, the chip re-sent on every poll, the decline
forgotten, `pick` ignoring his answer, the chip never reaching the phone,
containment removed, attribution loosened to "any new window", the newness
rule dropped, the full-screen branch removed, the release removed, the
prune's clean-up removed, the measurement removed (re-placed on every poll),
the try cap removed, the watcher made to act while the phone is away, the
sweep made a no-op (the pre-239 foreground-only eye), the sweep left unwired
from `watch`, the grace removed so a slow window is judged on its first look,
the one-question rule deleted so a layout switch asks twice, and (task 240)
the click-correlation tier removed so an unattributable window after his own
click is refused, plus the same window with a stale or absent click proving
the rule was not widened into offering every stranger.

---

## A member's OWN popup is PLACED, never asked about (owner report 2026-08-13)

The round before this one built [Lost Windows](lost_windows.md) — a sweep for
any window standing off every screen — and shipped it as the answer to his
report. **It was the wrong target, and he said so plainly.** His case is not
"a window opened while nobody was watching"; it is:

> lang-ok-begin: owner quote — the correction this section exists for
> "nekada ja otvaram aplikaciju kada aplikacija otvara aplikaciju"
> "Dakle kada se otvori popup WINDOWS ga baci VAN GRANICA NAŠEG PROZORA"
> "Rješenje je da se taj POPUP od MATIČNE APLIKACIJE PRIKAZUJE U NJENOJ SREDINI"
> lang-ok-end

An agent working inside a layout's VS Code opens a report, a *Record a
shortcut* window, a permission dialog. Windows places such a window on its
parent's **restored** geometry, or wherever that app last used — neither of
which is the quarter of the screen the layout just moved the parent into. The
popup lands outside the region, under the members' always-on-top band, and a
phone has no taskbar.

### Why this one alone does not ask

Every other rule here is a **guess about whose window this is**, and a wrong
guess would move a stranger's window — which is why each of them ends in a chip
he taps. The owner chain is not a guess. Windows itself says this window was
raised by that member: it takes it down when the member minimizes, and closes
it when the member closes. Asking permission to put an application's own dialog
on that application is asking him to confirm what the application decided.

So **rule 1 places; rules 2–4 still ask.**

### The parent, not the region

A layout of four holds four windows. A VS Code dialog belongs on the VS Code,
not floating in the middle of a grid over three windows it has nothing to do
with. `_contain` therefore takes an `anchor`, tried first and at the popup's own
size.

The anchor is a **preference, never a promise**. A dialog too big for the one
cell its parent occupies falls through to the region, and then to the full
screen — so the guarantee he actually cares about (it is inside the streamed
picture) never depends on the anchor succeeding.

### Two more windows that may never wear a chip

* **A window no layout could hold** (his point 3). The creation list is built
  by `window_manager.list_windows`; the popup sweep's own eye was
  `IsWindowVisible` and nothing more. So the phone asked "a layout with it?"
  about tool windows and shell surfaces that the list would not even carry when
  he tapped — a question the app cannot honour. The filter is now a function,
  `window_manager.is_listable`, and both paths ask it.
* **A window WE made** (his point 4A). Tearing a tab off is a double-click
  followed by a brand-new top-level window of a member's process: every
  attribution rule is *correct* about it, which is why none of them could fix
  it. `layout_popup.mine()` is the maker saying so, once, bounded in time
  because Windows re-uses handles.

Gate: `tests/test_layout_popup.py` — the three new checks plus the rewritten
dialog checks, every one proven by planting its own defect.

## THE QUESTION CHANGED (owner decision 2026-08-17)

Every rule below asks **does this window belong to this layout**, and answers
it mostly by process name. His report says that is the wrong question: the app
asked him only about windows HE had just made — his own second VS Code window
shares a member's exe — and stayed silent about the ones somebody else made,
which is where he actually wants a layout offered.

So `sweep` now carries a final rule after all four below: **a NEW, listable
window that no layout holds earns a chip on that alone**, with no evidence
about who made it. What silences a chip is the safety of the whole feature and
is asserted as such in [`tests/test_window_offer.py`](../../tests/test_window_offer.py):

* a window WE made on his own tap — [Window Claim](window_claim.md), and since
  this round the claim is armed BEFORE the act, because `mine()` could not be
  early enough (6–8 s of exposure on the tear-off, measured);
* a window some layout already holds — his own placement, any layout, not only
  the focused one;
* a window no layout could hold — `is_listable`, his point 3 of 2026-08-13.

And an offer is still only ever a QUESTION: nothing is placed, raised, resized
or moved before his tap. The honest cost, named to him before he chose: every
unrelated new window is now a chip he can decline.

`baseline()` changed with it — see its own docstring. It is the desk as the
phone LAST LEFT IT rather than the live desk, because a window born while
nobody was connected used to be filed as already known by the very connection
that came looking for it.
