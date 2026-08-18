# Desk Facts

**Script:** [Desk Facts (script)](../desk_facts.py)

## Purpose

What Windows says about the desk RIGHT NOW, read cheaply. Split out of
[Layout Popup](layout_popup.md) on 2026-08-18 (THE STRUCTURE LAW, VC-R5):
three readings and nothing else, separated from the RULES that use them
because a rule is an argument and a reading is a fact.

It is also the seam the gates cut on. Every popup gate replaces exactly these
three functions so it can run without touching the owner's real desk - which
is why they were worth a module of their own and why they carry no logic
beyond the reading itself.

## Why not `window_manager`

`window_manager.list_windows` also reads a process path and renders an ICON per
window. That is right for the creation list the phone draws and far too much
for a set of numbers taken once per connection, so `top_level_hwnds()` is the
deliberately weaker version: `IsWindowVisible` and a handle, nothing else.

## Nothing here caches

A cache would answer about a process table that has since changed, and every
question asked here is about something that just started. One Toolhelp snapshot
costs about a millisecond and is taken on demand.

## Connections

### Uses
- [Window Manager](window_manager.md) - the `user32` / `kernel32` handles and
  the `EnumWindows` callback type

### Used by
- [Layout Popup](layout_popup.md) - the baseline, the attribution rules and
  the sweep
- [Layout Birth](layout_birth.md) - the same live desk, for task 185's question

## Functions

- `ANCESTRY_HOPS`: how many parent hops still mean "that member's work"
- `pid_of(hwnd)`: the process a window belongs to (0 = unknown)
- `parent_pids()`: `{pid: parent pid}` for the whole machine, one snapshot
- `descends_from(pid, roots)`: was it started by one of these, bounded by
  `ANCESTRY_HOPS` and by a seen-set (a live process table can contain a cycle
  after a PID was recycled)
- `top_level_hwnds()`: every visible top-level window, handles only
