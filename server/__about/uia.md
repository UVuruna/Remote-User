# UIA Tab Layer

**Script:** [UIA Tab Layer (script)](../uia.py) ·
**Flow:** [diagram](../__flow/uia.md)

## Purpose
Everything in this project that speaks to Windows through **UI Automation**
lives here, and that is what makes it one module: `uiautomation` (COM) must be
initialized in whichever thread makes the call, and `_uia()` is the single
place that does it. Three features ride on that — tab extraction (below),
`next_input`'s walk through the text fields, and the caret read that
[Caret](caret.md) turns into a message for the phone. The POLICY of each lives
with its own subject; only the UIA call lives here.

### Tab extraction — Phase F+ step 2 (spec: ROADMAP → Layouts & Tab Control): the unit of layout
selection is the TAB — a VSCode editor tab, Chrome tab or Explorer tab is
turned into its OWN OS window before the layout machinery arranges it.
`tab_at` names the tab under the phone's pick tap (UI Automation hit-test,
walking ancestors to the `TabItem` — hits often land on an inner element);
`extract_tab` performs the separation with three strategies in the owner's
priority order (all probe-verified live 2026-08-02):

1. **The app's own context-menu command** — right-click the tab, click the
   menu item whose name contains "new window" (Chrome `Move tab to new
   window`, VSCode `Move into New Window`).
2. **Explorer path** (no such command exists there): select the tab, read the
   path from the address band, `explorer.exe <path>`, close the original tab.
3. **Drag tear-off fallback** — real held-button interpolated `SendInput`
   moves (Explorer's XAML strip ignores cursor-teleport drags) dropped on the
   taskbar strip, the one spot outside every window rect (VSCode refuses to
   detach when the drop lands inside ANY VSCode window's rect).

**Every failure returns None and the caller uses the whole window** — a tap
on something that merely looks like a tab (VSCode activity-bar icons are
`TabItem`s too) self-corrects instead of erroring. `uiautomation` is imported
lazily inside a per-thread COM initializer (the web layer calls from asyncio
worker threads); a missing/broken package disables ONLY the tab layer.
Extraction clicks/drags are this module's own SendInput synthesis — separate
from the phone-driven, self-verifying injector.

## Connections
### Uses
- [Window Manager](window_manager.md) — window enumeration/raising and the
  work-area rect for the drag drop point

### Used by
- [Web Layer](web.md) — `layout_pick` names the tab in `layout_offer`;
  `layout_create` extracts it before arranging
- [Caret](caret.md) — `caret_rect(hwnd)`, several times a second while a
  phone is connected

## Functions
- `tab_at(mon_rect, nx, ny)`: `{"name"}` of the tab under a
  monitor-normalized point, or None
- `list_tabs(mon_rect, hwnd)`: the RAW read — every real content tab of one
  window
- `is_minimized(hwnd)`: a Win32 fact kept beside the tab reader, because that
  reader is the one thing whose answer depends on it
- `offerable_tabs(mon_rect, hwnd, process)`: the tabs the creation panel is
  allowed to show (see below)
- `extract_tab(mon_rect, nx, ny, target)`: run the strategy chain; returns
  the new window's hwnd or None (fall back to the whole window)
- `caret_rect(hwnd)`: the screen-pixel rect of the text caret inside `hwnd`,
  or None (see below)

## The caret read (2026-08-08)
`caret_rect(hwnd)` answers "where is the text caret in this window", in screen
pixels, for the [Caret](caret.md) watch — which owns the policy (which window
to ask about, the hold, the normalization, the honest unknown) and holds the
measurements. Three things about the read itself are load-bearing, and all
three were MEASURED on the owner's desktop, read-only, on 2026-08-08:

1. **Keyboard focus is global, the question is not.** The focused element is
   walked up to the window that owns it and discarded when that is not the
   window asked about — a caret in some other window is not this window's.
   The walk is not padding: the focused element in both Chrome and VSCode
   reports `NativeWindowHandle == 0`, and the handle appears two parents up.
2. **A caret is a COLLAPSED range, and a provider may give it no rectangle at
   all.** The Claude Code chat box inside VSCode returns an empty rect list
   for its selection; only `ExpandToEnclosingUnit(Character)` yields
   `(1203, 936, 21, 21)`. VSCode's editor, by contrast, answers the plain
   selection with the caret's whole LINE — which is what the phone's keyboard
   actually has to clear.
3. **A failure is not a crash and not a log flood.** No caret is a normal,
   frequent answer; the read runs several times a second, so a failure is
   logged ONCE per distinct message (`_warn_once`) and the caller is told
   "none".

## Refinements (owner feedback 2026-08-02, same day)
`list_tabs` enumerates a window's REAL content tabs for the list-based
creation source (filter: top strip within the window's top 15%, width ≥ 60 px
— drops VSCode activity-bar/panel icons and Explorer's Home pills).
Extraction re-finds the tab BY NAME inside the window after raising it (tabs
shift; a stale point grabs the wrong one) with the pick point as fallback.
### There are no waits here any more — only timeouts (owner ruling 2026-08-12)

His ruling, in translation: *estimating how long something needs to load is
not allowed here or in any other place*. Every fixed sleep on this path was a
guess at ANOTHER application's speed, and he was right to ask the prior
question — is there really no signal? There is one for every case, and each
sleep is now a `_poll()` on the condition it was guessing at, with the old
number kept only as the give-up point:

| Was | The condition now watched |
|-----|---------------------------|
| `MENU_WAIT_S` after the right-click | the menu-item search itself, repeated until it finds "new window" |
| `0.4 s` after clicking an Explorer tab | the address band reading an EXISTING path, stable across two consecutive reads (evidence, not a clock — a tab already selected legitimately reads the same value) |
| `0.25 s` before `Ctrl+W` | the source window really being the foreground window; on timeout the close is **skipped and logged**, because closing a tab in a stranger's window is far worse than leaving one open |
| `0.2 s` after `Ctrl+W` | the source window's tab count really dropping |
| `1.2 s` after the tear-off drag | **deleted** — `_wait_new_window` on the very next line already polls exactly that; the new window's rect is then watched until two reads agree, since the app may still be finishing its own tear-off |
| `0.15 s` after raising, before reading tab rects | the same foreground poll (non-fatal: `_find_tab_rect` still re-finds the tab by name) |

The micro-sleeps inside `_click` / `_held_drag` (8–40 ms) are deliberately
untouched and say so in place: they are the physical pacing of an injected
mouse gesture — a real held-button drag needs real milliseconds between its
own synthetic input events to register as a drag at all — not an estimate of
how fast some other program reacts.

## Step 3 (owner spec 2026-08-02)
`focus_next_input(scope_hwnds)` — the `next_input` action: collect Edit +
Document elements (visible, enabled, keyboard-focusable, sensibly sized) of
the scope windows (layout members, or every non-minimized window), order them
top-to-bottom/left-to-right, find the currently focused one by RuntimeId and
SetFocus the next (raising its window first). Fails soft to None.

## Tab-capable apps only (owner decision 2026-08-03)
`TAB_APPS` / `has_tabs(process)` gate the whole tab layer: only Chrome, Edge,
Firefox, Brave, Opera, Vivaldi, LibreWolf, VSCode/Insiders, Cursor, Windsurf,
Explorer and Windows Terminal get their tabs offered. UIA has no "this tab can
become a window" property, and an app's internal section switcher (the
Pointer / Ring / Umbra pills in Watch Academy's design pane) is a `TabItem` in
the window's top strip exactly like a Chrome tab — offering those cost six
seconds of extraction that always fell back to the whole window. The list is
the set of apps the three strategies actually cover; everything else is
offered as a whole window only, and its UIA tree is never walked (which also
makes the creation list visibly faster). [Web Layer](web.md) applies the gate
before calling `list_tabs` / `tab_at`.

## A tab is offered only when it can really leave (owner 2026-08-09, task 167)
`offerable_tabs(mon_rect, hwnd, process)` is the ONE place the creation list's
tab rule lives, and it holds three answers that were previously spread across
a caller, a process-name test and nothing at all:

1. **Not tab-capable → none.** `has_tabs`, above.
2. **Minimized → none, and the caller SAYS so.** Measured 2026-08-09: a
   minimized window reports the classic `(-32000, -32000)` rect to Win32 and a
   bounding height of **0** to UI Automation, so `_real_tabs` bails on
   `wr.height() <= 0` and answers "no tabs" whatever the window holds. The
   creation list therefore showed the SAME window without its tabs from the
   taskbar and with them once restored, with nothing on screen to explain the
   difference. It is now refused deliberately and the entry carries
   `tabs_hidden`, which the phone draws as a `minimized` note on the row plus
   one line under the list — an empty answer that looks like a fact is worse
   than a stated limit.
3. **One tab → none.** His rule: *a tab can be extracted into its own window
   only when the window has more than one tab.* A lone tab and its window are
   the same picture on screen, so offering both counted one window twice — a
   VS Code with three tabs was offered as **four** entries, and the phone then
   let him ask for a grid of four that only three windows could fill. The lone
   tab **vanishes entirely** and the window stands for it.

The count was always available and always thrown away: `list_tabs` returns a
materialised list and the caller used to iterate the temporary without ever
binding `len()`.

## Transient raises are never TOPMOST (audit 2026-08-05)

Every `raise_window` call in this module is a **stage direction**, not layout
membership, and all four now pass `topmost=False`:

- `focus_next_input` raises whichever window owns the next text field. On the
  full desktop that is an arbitrary third-party window, in no layout at all —
  a topmost raise nailed it above the owner's desk for the rest of the Windows
  session, with no list that could ever name it again.
- `_try_explorer_path` raises the SOURCE window (to send Ctrl+W) and then the
  freshly created one, before either is registered.
- `_try_drag` raises the SOURCE window to find the tab under the cursor. It
  keeps its remaining tabs and never becomes a member.

Only [Layout API](layout_api.md) via `window_manager.place_window` /
`raise_window(topmost=True)` may put a window into the always-on-top band, and
those are the ones the ledger owes a way back down.
