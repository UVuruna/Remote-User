"""WHAT THE LAYOUT'S OWN APPLICATION CAN DO, OFFERED WHERE HE IS ALREADY
STANDING (owner ballot 2026-08-13, T29).

The **New** source ([Recents](recents.py)) offers what the PC can OPEN. His
request adds the other half: opened from INSIDE a layout, the panel must first
offer the acts of the program that layout is made of — his own examples were a
new Claude Code for a VS Code layout, and a new TAB for Chrome and Explorer.

## The three rules this module is built on

1. **It knows where it was asked from.** The same shape the creation list
   already has (constraint 21): from a layout, a first group about THIS layout
   and then the standard one; from the desktop, only the standard one. An act
   here has no meaning at the desktop — there is no member to act ON.

2. **An act reaches the member through the FENCE, never around it.** Every one
   of these is an injection into a foreign application, which is constraint
   11's whole subject: the target is taken from `focus_guard`'s guard, the
   PROCESS is asserted before a single key goes out, and a target that is not
   the app the act is for costs ZERO injections and says so. A `Ctrl+T` fired
   into whatever really holds the keyboard is not a harmless no-op.

3. **Nothing here is a NEW way to do an old thing.** The palette drive is
   [Content](content.py)'s `palette_command`, the same code the Claude button
   has used since task 200; the pastes are its `paste_text`; the launches are
   [Recents](recents.py)'s own `app_exe`, and the Explorer folder list is
   `recents.explorer_recents()`. This module is a CATALOGUE plus a dispatcher.

## What each app offers, and what each one honestly costs

* **VS Code** — *New Claude Code* runs the extension's real palette command
  `Claude Code: New Conversation` (measured on this PC from the extension's own
  `package.json`, 2026-08-13 — the name is read, never invented, the same
  standard `Claude Code: Focus input` was held to). It lands in the SAME
  window, which is said on the row: it is a conversation, not a member.
  *New window on the same folder* is the one that really grows the desk, and
  it needs the folder's PATH — a window title carries only its NAME, so the
  path is recovered by matching that name against VS Code's own recent list
  (`recents.vscode_recents()`). No match = a refusal that says so, never a
  guessed path handed to a launcher.
* **Chrome** — *New tab* and *Reopen the closed tab* are plain chords into the
  member. *New tab from the clipboard* opens the tab and pastes what is on the
  PC clipboard, which the phone and the PC now share both ways (task 182), so
  a link copied on the phone opens on the PC in one tap; an empty clipboard is
  a refusal, not an empty tab.
* **Explorer** — *New tab* and *Up one folder* are chords. *Open a Quick
  Access folder* navigates THIS window (`Ctrl+L`, the path, Enter) instead of
  opening a second Explorer, which is the other of the two possible things to
  do with the list the New source already reads.

## What this module may NOT do

It never creates, removes or re-places a layout, and it never opens a window
into one. A window an act of ours opens (VS Code's new window) is handed to
Windows and to the ordinary popup machinery exactly like any other — it is
marked `layout_popup.mine()` at the moment it appears, for the same reason the
New source marks its own (his report 2026-08-13, picture 2), and whether it
joins the layout is his tap, never ours.
"""

import logging
import time

import clipboard_sync
import content
import focus_guard
import layout_popup
import recents
import window_manager as wm

logger = logging.getLogger(__name__)


# ═══════════════════════════ RULES ═══════════════════════════
# The palette command that starts a fresh conversation IN ITS OWN EDITOR TAB,
# READ from the Claude Code extension's own `package.json` (`claude-vscode.
# editor.open`), never invented — the same standard `CLAUDE_FOCUS_COMMAND` was
# held to, and for the same reason: a mis-typed name run by the palette's Enter
# is an arbitrary VS Code command.
#
# IT WAS `claude-vscode.newConversation` UNTIL 2026-08-17, AND THAT WAS THE
# WRONG DOOR (owner report, his picture 3). "New Conversation" opens the
# conversation wherever the extension currently lives, which on his PC is the
# SECONDARY SIDE BAR — and a side bar is not a window: it cannot be torn into
# one, so it cannot become a layout member, which is the only reason he taps
# this row at all. He pointed at the extension's own tab button (his picture 4)
# and the command behind it is this one. Both names exist in the same
# `package.json` and only one of them produces something this product can use,
# so the gate below pins the ID as well as the title — the READING was correct
# in 2026-08-13 and the CHOICE was not, which no check on "is this name real"
# could ever have caught.
CLAUDE_NEW_COMMAND = "Claude Code: Open in New Tab"

# The VS Code core command that puts a SECOND window on the folder this one
# already holds. Read from the installed VS Code's own workbench bundle on
# 2026-08-17 (`workbench.action.duplicateWorkspaceInNewWindow`), the same
# standard every other palette name here is held to.
#
# IT REPLACES A LAUNCH THAT COULD NEVER HAVE WORKED (owner report 2026-08-17,
# and MEASURED before it was believed). The act used to run
# `Code.exe -n <path>`, and `-n` on a folder VS Code ALREADY HAS OPEN does not
# open a second window — it focuses the existing one. The layout's folder is by
# definition already open, so this row was unsatisfiable from the day it
# shipped: his own log says so twice in one minute ("code.exe opened no window
# within 25s"), and a controlled run on his PC confirmed both halves — the same
# call against a folder that was NOT open produced a window immediately.
#
# The palette route needs no path at all, which retires the whole
# title-to-path recovery this act used to depend on: nothing is looked up, so
# nothing can be looked up wrongly.
VSCODE_DUPLICATE_COMMAND = "Duplicate As Workspace in New Window"

# How long a window an act LAUNCHES may take to appear before we stop watching
# for it. Only used to mark it as ours (see the module docstring) — nothing is
# reported to the phone from here, so the give-up point costs nothing but the
# mark, and the same poll cadence as `recents` is deliberate.
LAUNCH_WATCH_S = 25.0

# The plain one-chord acts. A table rather than four branches, because every
# one of them is the same statement — this key, into the member the fence has
# just proved we are standing in.
_CHORDS = {
    "chrome": {"tab": "ctrl+t", "reopen": "ctrl+shift+t"},
    "explorer": {"tab": "ctrl+t", "up": "alt+up"},
}

PROCESS_OF_APP = {"vscode": "code.exe", "chrome": "chrome.exe",
                  "explorer": "explorer.exe"}
APP_OF_PROCESS = {v: k for k, v in PROCESS_OF_APP.items()}
APP_NAME = {"vscode": "VS Code", "chrome": "Chrome", "explorer": "Explorer"}


def app_of(process: str) -> str:
    """Which of the three apps this member window is, or "" for anything else.
    A layout of Notepad has no acts, and offering it an empty group would be a
    heading standing over nothing."""
    return APP_OF_PROCESS.get((process or "").lower(), "")


# ═══════════════════════════ THE CATALOGUE ═══════════════════════════
def catalogue(process: str) -> list[dict]:
    """The rows the New panel draws above the standard list, for a layout made
    of `process`. Empty for anything the three apps do not cover.

    `sub` is not decoration: every row whose act does NOT create a member says
    so there, because every other row in that panel does create one and a
    surprise about which is which is the class of defect constraint 18 is
    about.

    `opens` is the machine-readable half of the same statement, added
    2026-08-17: TRUE on the one act whose whole point is that a new WINDOW
    appears on the PC. The phone reads it to choose which loading animation
    covers the wait (owner's answer this round: FULL for that one, because the
    desk really rearranges itself; CUBE for the acts that happen inside one
    window and are worth watching happen — constraint 16). It is a FIELD and
    never an id the phone matches on: a second act that opens a window one day
    must not need the page reissued to be covered."""
    app = app_of(process)
    if app == "vscode":
        return [
            {"id": "vscode|claude", "label": "New Claude Code",
             "sub": "a new conversation, in its own tab"},
            {"id": "vscode|window", "label": "New window, same folder",
             "sub": "a second VS Code on this project", "opens": True},
        ]
    if app == "chrome":
        return [
            {"id": "chrome|tab", "label": "New tab",
             "sub": "in this window"},
            {"id": "chrome|reopen", "label": "Reopen the closed tab",
             "sub": "in this window"},
            {"id": "chrome|clip", "label": "New tab from the clipboard",
             "sub": "opens what was last copied"},
        ]
    if app == "explorer":
        rows = [
            {"id": "explorer|tab", "label": "New tab", "sub": "in this window"},
            {"id": "explorer|up", "label": "Up one folder",
             "sub": "in this window"},
        ]
        for rec in recents.explorer_recents():
            rows.append({"id": f"explorer|go|{rec['target']}",
                         "label": rec["label"], "sub": rec["sub"]})
        return rows
    return []


# ═══════════════════════════ RUNNING ONE ═══════════════════════════
def _refuse(app: str, name: str) -> str:
    return (f"Nothing was sent — {APP_NAME.get(app, 'that app')} is not the "
            f"window in front{f' ({name} is)' if name else ''}")


def _secured(app: str, guard, process_of=None) -> tuple[int, str]:
    """`(target, "")` when the fence really holds the app this act is for, or
    `(0, sentence)`. The assertion is rule 2 of this module and it is made
    BEFORE any injection, exactly as `content.palette_command` makes its own —
    a chord is global, and the window it lands in is whatever the guard's
    target really is."""
    process_of = process_of or content._target_process
    target = guard() if guard is not None else 0
    if guard is not None and not target:
        logger.error("Layout act refused — focus could not be secured")
        return 0, "Nothing was sent — another window holds the keyboard"
    name = process_of(target) if target else ""
    if name != PROCESS_OF_APP[app]:
        logger.error("Layout act refused — the target runs %s, not %s",
                     name or "nothing readable", PROCESS_OF_APP[app])
        return 0, _refuse(app, name)
    return target, ""


# A PATH IS NO LONGER RECOVERED HERE, AND THAT IS THE POINT (2026-08-17).
# `_vscode_folder_path` used to match a window title's folder NAME against VS
# Code's own recent list to find where the project lives on disk, because the
# act launched `Code.exe -n <path>`. That launch could not do what the row
# promised (see `VSCODE_DUPLICATE_COMMAND`), and VS Code duplicating its own
# window needs no path at all — so the lookup, its refusal sentence, and the
# whole class of "we guessed the wrong folder" went with it. The two projects
# sharing one folder NAME that the New source still has to live with
# (constraint 26) simply cannot arise on this path any more.


def _pasted(injector, text: str, guard) -> str:
    """`content.paste_text`, turned into this module's own kind of answer.

    TWO CONTRACTS MEET HERE AND ONLY ONE OF THEM IS A SENTENCE (found
    2026-08-13, in the round that fenced the paste itself). `paste_text`
    returns what did NOT reach the PC — `web.py` wraps that in
    `focus_guard.loss_notice` before it ever reaches a phone — while `run()`
    below returns a sentence the phone is TOASTED verbatim. Returning the raw
    text straight through, as this module did until now, put a folder path or
    a copied URL on his screen as if it were an explanation.

    So the wrap happens here, with the one shared sentence rather than a
    second copy of it, and a refusal mid-sequence is reported instead of
    swallowed — the whole point of asking for the fence at all."""
    lost = content.paste_text(injector, text, True, guard)
    return focus_guard.loss_notice(lost) if lost else ""


def _watch_and_claim(process: str, before: set[int]) -> None:
    """Mark the window our own launch produced as OURS (`layout_popup.mine`).

    Blocking — every caller of `run` is already on a worker thread. Same
    newness rule as `recents.open_entry`: a handle that was not standing before
    the launch and whose process is the one we started. Without it the sweep
    meets a brand-new top-level window of a known app and asks him about a
    window he just asked US to open (his report 2026-08-13, picture 2)."""
    deadline = time.monotonic() + LAUNCH_WATCH_S
    while time.monotonic() < deadline:
        for win in wm.list_windows():
            hwnd = win["hwnd"]
            if hwnd in before or (win.get("process") or "").lower() != process:
                continue
            layout_popup.mine(hwnd)
            logger.info("Layout act opened %s as %s",
                        process, (win.get("title") or "")[:60])
            return
        time.sleep(recents.OPEN_POLL_S)
    logger.warning("Layout act: %s opened no window within %.0fs",
                   process, LAUNCH_WATCH_S)


def run(act_id: str, injector, guard=None, process_of=None) -> str:
    """Do it. `""` = it was done; anything else is the sentence for the phone,
    and in every refusal NOTHING was injected.

    Blocking on purpose (the caller runs it in a thread), like every other
    injecting path in this project: the fence check, the chord and the paste
    have to happen in that order.

    IT TAKES NO `folder` SINCE 2026-08-17. It used to, for the one act that
    opened a second VS Code on the layout's project BY PATH; that act is a
    palette command now and asks VS Code to duplicate the window it is already
    standing in, so the project is never named — by us, or by anything of ours
    that could name it wrongly."""
    app, _, rest = act_id.partition("|")
    act, _, target_path = rest.partition("|")
    if app not in PROCESS_OF_APP:
        return "Unknown command"

    # THE FENCE FIRST, ALWAYS — including for the acts that end in a launch:
    # the point of the assertion is that the layout he is watching really is
    # the app this row was drawn for, and that is as true of opening a second
    # window on its project as it is of a chord.
    _, refusal = _secured(app, guard, process_of)
    if refusal:
        return refusal

    if app == "vscode" and act == "claude":
        # The palette drive, shared with the Claude button since 2026-08-13.
        return content.palette_command(
            injector, CLAUDE_NEW_COMMAND, guard, PROCESS_OF_APP["vscode"],
            process_of=process_of,
            wrong_app=_refuse("vscode", ""), what="New Claude Code")

    if app == "vscode" and act == "window":
        # VS Code duplicating its OWN window needs no path and no launcher —
        # see `VSCODE_DUPLICATE_COMMAND` for why the launcher could never have
        # worked here. The window list is taken BEFORE the command goes out, so
        # the watcher's newness rule cannot race the window it is waiting for.
        before = {w["hwnd"] for w in wm.list_windows()}
        # ARMED BEFORE THE ACT, never after (owner report 2026-08-17). VS Code
        # can raise the duplicate the instant the palette's Enter lands, while
        # `_watch_and_claim` below cannot start looking until this call
        # RETURNS — and the popup sweep runs every second on its own thread
        # with no grace at all for a window it can tie to a member. The claim
        # closes that gap structurally instead of hoping to win the race; the
        # exact handle is still marked by `_watch_and_claim`, which is what
        # outlives the claim's short life. See server/window_claim.py.
        layout_popup.expect(PROCESS_OF_APP["vscode"])
        problem = content.palette_command(
            injector, VSCODE_DUPLICATE_COMMAND, guard, PROCESS_OF_APP["vscode"],
            process_of=process_of,
            wrong_app=_refuse("vscode", ""), what="New VS Code window")
        if problem:
            return problem
        _watch_and_claim(PROCESS_OF_APP["vscode"], before)
        return ""

    if act in _CHORDS.get(app, {}):
        injector.press_chord(_CHORDS[app][act])
        return ""

    if app == "chrome" and act == "clip":
        text = (clipboard_sync.read_text() or "").strip()
        if not text:
            # An empty tab is not what the row promised, and a button that
            # silently does the wrong thing is worse than one that says why.
            return "Nothing was opened — the PC clipboard is empty"
        injector.press_chord("ctrl+t")
        return _pasted(injector, text, guard)

    if app == "explorer" and act == "go":
        if not target_path:
            return "Unknown command"
        # Ctrl+L is the address band — the same route `uia` reads a path FROM,
        # driven the other way. It navigates THIS window, which is the whole
        # difference from the standard list's row for the same folder.
        injector.press_chord("ctrl+l")
        return _pasted(injector, target_path, guard)

    return "Unknown command"
