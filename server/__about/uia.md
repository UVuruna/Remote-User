# UIA Tab Layer

**Script:** [UIA Tab Layer (script)](../uia.py) ·
**Flow:** [diagram](../__flow/uia.md)

## Purpose
Phase F+ step 2 (spec: ROADMAP → Layouts & Tab Control): the unit of layout
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

## Functions
- `tab_at(mon_rect, nx, ny)`: `{"name"}` of the tab under a
  monitor-normalized point, or None
- `extract_tab(mon_rect, nx, ny, target)`: run the strategy chain; returns
  the new window's hwnd or None (fall back to the whole window)

## Refinements (owner feedback 2026-08-02, same day)
`list_tabs` enumerates a window's REAL content tabs for the list-based
creation source (filter: top strip within the window's top 15%, width ≥ 60 px
— drops VSCode activity-bar/panel icons and Explorer's Home pills).
Extraction re-finds the tab BY NAME inside the window after raising it (tabs
shift; a stale point grabs the wrong one) with the pick point as fallback.
All waits are trimmed to the working minimum — the owner found the visible
clicking/choosing too slow.

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
Pointer / Ring / Umbra pills in DOMY Watch's design pane) is a `TabItem` in
the window's top strip exactly like a Chrome tab — offering those cost six
seconds of extraction that always fell back to the whole window. The list is
the set of apps the three strategies actually cover; everything else is
offered as a whole window only, and its UIA tree is never walked (which also
makes the creation list visibly faster). [Web Layer](web.md) applies the gate
before calling `list_tabs` / `tab_at`.
