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

## A window this module opens JOINS the layout it was opened FROM

**Owner decree 2026-08-20, and it REVERSES what stood here** (constraint 43).
The sentence that used to close this docstring — *"whether it joins the layout
is his tap, never ours"* — cited constraints 18 and 19, and NEITHER of them
says any such thing: 18 is about one window asking one question, 19 about a
dialog opening in the middle of its parent. It was an invented prohibition
wearing somebody else's number, and together with constraint 33 (which
silences the chip for *"a window WE made on his own tap"*) it produced the one
outcome nobody ever wrote down: he taps **New window, same folder**, a window
opens somewhere on the desk, no layout takes it, and no chip asks about it.
In his own words, the whole specification:
    lang-ok: owner quote
    "pa kako drugačije radimo nego što sam program ubacuje u layout"

So: the tap on this row IS the answer. `run()` reports the handle it opened
through its `opened` callback, and [Layout Acts API](layout_acts_api.py) adds
it to the layout the row was drawn for. `layout_popup.mine()` is still called
— for the reason it was always called, so the sweep does not ALSO ask about a
window that is already being placed.

This module still never creates, removes or re-places a layout **itself**: it
opens the window and names it. The layout is grown one door up, through
`LayoutRegistry.add_member`, the same call the ⚙ sheet's "add a member" uses.
"""

import json
import logging
import os
import subprocess
import time
from pathlib import Path

import agents
import clipboard_sync
import content
import focus_guard
import layout_popup
import recents
import window_manager as wm
from config import USER_DIR

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

# ═══════ A SECOND WINDOW ON A PROJECT VS CODE ALREADY HOLDS ═══════
# VS CODE ALLOWS EXACTLY ONE WINDOW PER FOLDER, and that is not an opinion —
# it is what FOUR routes measured on this PC on 2026-08-20 all ran into:
#
#   Code.exe -n <folder already open>   no window at all in 25.2 s
#   Code.exe -n            (no path)    a window in 0.5 s   <- the control
#   Code.exe -r <folder>  into that new empty window        folder never landed
#   palette File: Open Recent / Open Folder in that window  folder never landed
#
# Every route funnels the folder back into the window that already holds it.
# The control line is what makes the other three trustworthy: the launcher
# itself works, so "no window" is VS Code's answer and not our failure.
#
# THE ONE IDENTITY A SECOND WINDOW CAN WEAR IS A WORKSPACE. The act shipped
# 2026-08-17 had found that too, through the palette's
# `Duplicate As Workspace in New Window` — and it produced an **untitled**
# workspace, which is a different thing and the defect the owner reported
# (2026-08-19, his pictures 1-2): the root reads `UNTITLED (WORKSPACE)`, the
# window opens on Welcome, closing it nags to save a workspace file he never
# asked for, and — the half that breaks US — the title carries no project name
# at all, so `agents.title_folder` cannot read it, which is what the Claude
# wheel, the layout's own name and the "already open" dimming all decide off.
#
# So we write the workspace file OURSELVES, with the project's own name, and
# open it with `-n`. Measured the same day: a window in 0.6 s titled
# `VibeCoder (Workspace) - Visual Studio Code` — the project IS in the title,
# there is nothing to save, and `agents.VSCODE_WORKSPACE_TAIL` strips the one
# word we added so every reader downstream sees the same project as the first
# window. Same VS Code instance, so the same extensions, the same settings and
# the same Claude Code sign-in as the window it was opened from.
WORKSPACE_DIR_NAME = "workspaces"
WORKSPACE_SUFFIX = ".code-workspace"

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


# ═══════ WHICH PROJECT, READ OFF THE WINDOW THE ACT REALLY RAN AGAINST ═══════
# THE PATH IS RECOVERED FROM `target`, NEVER FROM THE LAYOUT (2026-08-20), and
# that is a fix and not a detail. The panel draws its rows for the FOCUSED
# layout, while `run()` re-asks the fence which window really holds the
# keyboard at the moment of the tap — and `_secured` used to assert only that
# the answer runs `code.exe`. With two VS Code windows on the desk, both
# answers pass and they can be different windows, so a row drawn for one
# project could act on another. Reading the folder off the very handle the
# fence returned makes that mismatch impossible to express.
#
# A title carries a folder's NAME and never its path, so the path comes from
# VS Code's own recent list. Two projects sharing one folder name (constraint
# 26's honest limit) are REFUSED with a sentence naming both, never resolved
# by picking the first — this act opens a window somewhere, and the wrong
# somewhere is worse than a refusal he can act on.
def _folder_path(hwnd: int) -> tuple[str, str]:
    """`(path, "")` for the project this VS Code window holds, or
    `(", sentence)`."""
    title = ""
    for win in wm.list_windows():
        if win["hwnd"] == hwnd:
            title = win.get("title") or ""
            break
    name = agents.title_folder(title)
    if not name:
        return "", ("Nothing was opened — that VS Code window does not name a "
                    "project in its title")
    hits = {rec["target"] for rec in recents.vscode_recents()
            if (Path(rec["target"]).name or "").lower() == name}
    if not hits:
        return "", (f"Nothing was opened — the PC could not find where "
                    f"{name} lives on disk")
    if len(hits) > 1:
        return "", (f"Nothing was opened — {len(hits)} different projects on "
                    f"this PC are called {name}")
    return hits.pop(), ""


def _workspace_file(path: str) -> str:
    """The `.code-workspace` that lets VS Code open `path` a SECOND time, in
    our own user folder and named after the project (see the block above
    `WORKSPACE_DIR_NAME` for why a workspace is the only identity a second
    window can wear).

    Rewritten on every act rather than reused blindly: the file is machinery,
    it is tiny, and a stale one pointing at a folder that has moved would open
    a window on nothing. Nothing of his is written — it lives beside our own
    settings, never in his project."""
    home = USER_DIR / WORKSPACE_DIR_NAME
    home.mkdir(parents=True, exist_ok=True)
    target = home / ((Path(path).name or "project") + WORKSPACE_SUFFIX)
    target.write_text(
        json.dumps({"folders": [{"path": path}]}, indent=2), encoding="utf-8")
    return str(target)


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


def _watch_and_claim(process: str, before: set[int]) -> int:
    """Mark the window our own launch produced as OURS (`layout_popup.mine`)
    and RETURN its handle — 0 if none ever came.

    Blocking — every caller of `run` is already on a worker thread. Same
    newness rule as `recents.open_entry`: a handle that was not standing before
    the launch and whose process is the one we started. Without it the sweep
    meets a brand-new top-level window of a known app and asks him about a
    window he just asked US to open (his report 2026-08-13, picture 2).

    THE HANDLE IS THE RETURN VALUE SINCE 2026-08-20 (constraint 43): the
    layout this window joins is grown from it one door up, and the only
    statement in this codebase that a given handle is the window we just made
    is the one this function is already holding."""
    deadline = time.monotonic() + LAUNCH_WATCH_S
    while time.monotonic() < deadline:
        for win in wm.list_windows():
            hwnd = win["hwnd"]
            if hwnd in before or (win.get("process") or "").lower() != process:
                continue
            layout_popup.mine(hwnd)
            logger.info("Layout act opened %s as %s",
                        process, (win.get("title") or "")[:60])
            return hwnd
        time.sleep(recents.OPEN_POLL_S)
    logger.warning("Layout act: %s opened no window within %.0fs",
                   process, LAUNCH_WATCH_S)
    return 0


def run(act_id: str, injector, guard=None, process_of=None, opened=None) -> str:
    """Do it. `""` = it was done; anything else is the sentence for the phone,
    and in every refusal NOTHING was injected.

    Blocking on purpose (the caller runs it in a thread), like every other
    injecting path in this project: the fence check, the chord and the paste
    have to happen in that order.

    `opened(hwnd)` is called ONCE, by the one act that makes a window, with
    the handle it made (constraint 43, owner decree 2026-08-20). It is a
    callback and not a return value because every other ending of this
    function is a SENTENCE, and a function whose answer is sometimes a
    complaint and sometimes a handle is a function every caller has to
    disambiguate. Whoever passes it decides what a new window is for — this
    module still knows nothing about layouts."""
    app, _, rest = act_id.partition("|")
    act, _, target_path = rest.partition("|")
    if app not in PROCESS_OF_APP:
        return "Unknown command"

    # THE FENCE FIRST, ALWAYS — including for the acts that end in a launch:
    # the point of the assertion is that the layout he is watching really is
    # the app this row was drawn for, and that is as true of opening a second
    # window on its project as it is of a chord.
    target, refusal = _secured(app, guard, process_of)
    if refusal:
        return refusal

    if app == "vscode" and act == "claude":
        # The palette drive, shared with the Claude button since 2026-08-13.
        return content.palette_command(
            injector, CLAUDE_NEW_COMMAND, guard, PROCESS_OF_APP["vscode"],
            process_of=process_of,
            wrong_app=_refuse("vscode", ""), what="New Claude Code")

    if app == "vscode" and act == "window":
        # THE PROJECT IS READ OFF `target` — the window the fence just proved
        # we are standing in — and never off the layout (see `_folder_path`).
        path, problem = _folder_path(target)
        if problem:
            return problem
        exe = recents.app_exe("vscode")
        if not exe:
            return "Nothing was opened — VS Code is not installed on the PC"
        # The window list is taken BEFORE the launch, so the watcher's newness
        # rule cannot race the window it is waiting for.
        before = {w["hwnd"] for w in wm.list_windows()}
        # ARMED BEFORE THE ACT, never after (owner report 2026-08-17). VS Code
        # can raise the window the instant the launch lands, while
        # `_watch_and_claim` below cannot start looking until `Popen` has
        # RETURNED — and the popup sweep runs every second on its own thread
        # with no grace at all for a window it can tie to a member. The claim
        # closes that gap structurally instead of hoping to win the race; the
        # exact handle is still marked by `_watch_and_claim`, which is what
        # outlives the claim's short life. See server/window_claim.py.
        layout_popup.expect(PROCESS_OF_APP["vscode"])
        try:
            # `launch_env()` and not the bare environment: under
            # ELECTRON_RUN_AS_NODE this executable is not VS Code at all and
            # no window can ever appear (see `recents.launch_env`).
            subprocess.Popen([exe, "-n", _workspace_file(path)],
                             close_fds=True, env=recents.launch_env())
        except OSError as error:
            logger.error("Could not start %s: %s", exe, error)
            return f"Nothing was opened — could not start {os.path.basename(exe)}"
        hwnd = _watch_and_claim(PROCESS_OF_APP["vscode"], before)
        if not hwnd:
            return "The window never appeared — is VS Code still starting?"
        if opened:
            opened(hwnd)
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
