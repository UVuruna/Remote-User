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
   **A refusal mid-sequence is REPORTED, not swallowed** (2026-08-13). The two
   multi-step acts — `chrome|clip` and `explorer|go` — fire a chord and then
   paste, and until the paste itself was fenced (see [Content](content.md)) a
   thief between those two steps got the text while `run()` answered `""`.
   Two contracts meet here and only one of them is a sentence: `paste_text`
   returns what did NOT reach the PC, while `run()`'s return is toasted on the
   phone verbatim — so `_pasted()` wraps it in `focus_guard.loss_notice`, the
   one shared sentence. Returning the raw text straight through, as this module
   did until now, put a folder path or a copied URL on his screen as if it were
   an explanation.
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
| VS Code | New Claude Code | palette `Claude Code: Open in New Tab` | lands in the SAME window — a conversation in its own editor tab, not a member, and the row says so |
| VS Code | New window, same folder | a NAMED `.code-workspace` we write, opened with `Code.exe -n` | VS Code allows one window per FOLDER, so the second window wears a workspace identity — its title reads `<project> (Workspace)`, which `agents.VSCODE_WORKSPACE_TAIL` strips for every reader downstream |
| Chrome | New tab | `Ctrl+T` | nothing new appears on the desk — deliberate, and the row says so |
| Chrome | Reopen the closed tab | `Ctrl+Shift+T` | — |
| Chrome | New tab from the clipboard | `Ctrl+T` + paste + Enter | an empty clipboard is a refusal, not an empty tab |
| Explorer | New tab · Up one folder | `Ctrl+T` · `Alt+↑` | — |
| Explorer | Open a Quick Access folder | `Ctrl+L` + the path + Enter | navigates THIS window, instead of opening a second Explorer |

**The palette command name is READ, never invented**, and since 2026-08-17
the gate pins WHICH name and not merely that the name is real — because both
of this round's defects were commands that existed.

**The Claude row opened the SIDE BAR** (owner report 2026-08-17, his picture 3).
`claude-vscode.newConversation` was read correctly from the extension's own
`package.json` in 2026-08-13, and it starts the conversation wherever the
extension currently lives — on his PC, the secondary side bar. A side bar is
not a window: it cannot be torn into one, so it can never become a layout
member, which is the only reason this row exists. He pointed at the extension's
own tab button (his picture 4) and the command behind it is
`claude-vscode.editor.open`. The reading was right in 2026-08-13 and the
CHOICE was not, which no check on "is this name the extension's own" could ever
have caught.

**The second-window row could never have worked, and that was MEASURED**
(same report). It ran `Code.exe -n <path>`, and `-n` on a folder VS Code
ALREADY HAS OPEN does not open a second window — it focuses the existing one.
A layout's folder is by definition already open, so the act was unsatisfiable
from the day it shipped; his own log says so twice inside one minute
(`code.exe opened no window within 25s`), and a controlled run on his PC
confirmed both halves — the same call against a folder that was NOT open
produced a window at once. It is a palette command now
(`workbench.action.duplicateWorkspaceInNewWindow`, read from the installed VS
Code's own workbench bundle), which asks VS Code to duplicate the window the
fence has just proved we are standing in.

**So no path is recovered any more, and that is the point.** The old act
matched the layout's project NAME against VS Code's own recent list, because a
window title carries a name and never a path. Duplicating a window needs
neither, so the lookup, its refusal sentence and the whole class of "we found
the wrong folder of that name" went with the launcher.

## What this module may NOT do

**And it never runs inside the receive loop** — that half lives one door
further out, in [Layout Acts API](layout_acts_api.md), which is also where the
25 seconds of silence that ended his session are written down.

It never creates, removes or re-places a layout **itself**. A window an act of
ours opens is marked `layout_popup.mine()` the moment it appears — the same
statement [Recents](recents.md) and tab extraction make, and for the same
reason (his report 2026-08-13, picture 2: the phone asked him about a window
he had just asked us to open) — and its HANDLE is handed up through `run()`'s
`opened` callback.

**The window then joins the layout it was opened from** (owner decree
2026-08-20, constraint 43). The growing happens one door out, in
[Layout Acts API](layout_acts_api.md), through `LayoutRegistry.add_member` —
the same call the ⚙ sheet's "add a member" makes, never a second placement
path. The sentence that used to stand here — *"whether it joins the layout is
his tap, never ours"* — cited constraints 18 and 19, and neither of them says
anything of the kind; read the constraint before arguing with the rule.
