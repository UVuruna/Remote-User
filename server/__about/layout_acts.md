# Layout Acts — what the layout's own application can do

Source: [`server/layout_acts.py`](../layout_acts.py) ·
Phone half: [`client/layout-new.js`](../../client/layout-new.js) ·
Gate: [`tests/test_new_source.py`](../../tests/test_new_source.py)

## Why it exists

The **New** source ([Recents](recents.md)) offers what the PC can OPEN. The
owner's ballot of 2026-08-13 (T29) adds the other half, and gave the reason in
his own examples: opened from inside a layout, the panel should first offer the
acts of the program that layout is MADE of — a new Claude Code for a VS Code
layout, a new tab for Chrome and for Explorer.

It is the same rule the creation list already follows (constraint 21): **the
panel knows where it was asked from.** From a layout, a first group about this
layout and then the standard one; from the desktop, only the standard one —
there is no member to act on, so a first group there would be a heading
standing over nothing.

## The three rules it is built on

1. **It knows where it was asked from.** `layout_acts` is answered with
   `in_layout` on the frame rather than leaving the phone to deduce it from
   the layout bar. An order is not a fact the page can check; a field is.
2. **An act reaches the member through the FENCE, never around it.** Every act
   is an injection into a foreign application, which is constraint 11's whole
   subject. `_secured()` takes the target from the focus guard and asserts the
   PROCESS before a single key goes out — a target that is not the app the row
   was drawn for costs **zero** injections and says so. `Ctrl+T` fired into
   whatever really holds the keyboard is not a harmless no-op.
3. **Nothing here is a new way to do an old thing.** The palette drive is
   [Content](content.md)'s `palette_command` (extracted from
   `focus_claude_prompt` unchanged in the same round — same sequence, same
   fence checks at the same three points); the pastes are its `paste_text`;
   the launches use [Recents](recents.md)'s `app_exe`; the Explorer folder
   list is `recents.explorer_recents()`. This module is a CATALOGUE plus a
   dispatcher.

## What each app offers

| App | Act | How it is done | The honest cost |
|-----|-----|----------------|-----------------|
| VS Code | New Claude Code | palette `Claude Code: New Conversation` | lands in the SAME window — a conversation, not a member, and the row says so |
| VS Code | New window, same folder | `code -n <path>` | needs the project's PATH; refused, never guessed, when it cannot be found |
| Chrome | New tab | `Ctrl+T` | nothing new appears on the desk — deliberate, and the row says so |
| Chrome | Reopen the closed tab | `Ctrl+Shift+T` | — |
| Chrome | New tab from the clipboard | `Ctrl+T` + paste + Enter | an empty clipboard is a refusal, not an empty tab |
| Explorer | New tab · Up one folder | `Ctrl+T` · `Alt+↑` | — |
| Explorer | Open a Quick Access folder | `Ctrl+L` + the path + Enter | navigates THIS window, instead of opening a second Explorer |

**The palette command name is READ, never invented.** `Claude Code: New
Conversation` (`claude-vscode.newConversation`) was read from the extension's
own `package.json` on this PC, 2026-08-13, held to exactly the standard
`CLAUDE_FOCUS_COMMAND` is: the palette's Enter runs whatever its filter left
standing, so a wrong name is an arbitrary VS Code command. The gate pins both.

**A window title carries a NAME, never a path.** So "New window, same folder"
recovers the path by matching the layout's project name against VS Code's own
recent list (`recents.vscode_recents()`, the live `state.vscdb` read). No match
is a sentence on the phone — handing a constructed path to a launcher opens a
stranger's folder or nothing at all, and both are worse than saying we do not
know where that project lives.

## What this module may NOT do

It never creates, removes or re-places a layout, and it never puts a window
INTO one. A window an act of ours opens (VS Code's new window) is marked
`layout_popup.mine()` the moment it appears — the same statement
[Recents](recents.md) and tab extraction make, and for the same reason (his
report 2026-08-13, picture 2: the phone asked him about a window he had just
asked us to open). Whether it joins the layout is his tap, never ours.
