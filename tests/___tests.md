# tests/

End-to-end regression gates PLUS the four project guard tests (rules/CODE.md
→ Enforcement). Per rules/DOCS.md's tier table, every file in this folder is
**tests tier — this folder doc is the only doc any of them get**, individual
files are not otherwise documented below except by name and one line.

## Files

### `test_input_pipeline.py` — Input Pipeline Gate
The REAL client page and the REAL server app, driven by a REAL headless
Chromium with touch emulation; only injection is faked (a recorder replaces
`SendInput`). Every scenario walks the full chain:

```
touch on the page → Pointer Events → WebSocket protocol → FastAPI handler → injector call
```

Scenarios: cursor steering (and the no-tap decree — a canvas touch never
clicks), the Click button (left), the Right button (right click), a chord
button, **the stolen-tap rescue** (Android ends edge-zone touches with
`pointercancel` — a no-travel cancel must still fire or buttons die
on-device, the 2026-07-26 live failure) and its inverse (**a system swipe
crossing a button — real travel, then cancel — must NOT fire**), edge
reachability with no reserved margin (the pointer sits exactly under the
finger — the offset system is gone), keyboard capture (typed
text + the Shift+Enter new-row rule), **the mic-survives-the-tap rule**
(owner 2026-08-09, amending the 2026-08-04 both-off rule: he steers the
cursor WHILE dictating, so a canvas tap closes only the KEYBOARD and a
listening mic keeps listening — while Esc (`inputOff()`) and the keyboard
going ON still switch the mic off), **the /ping contract** — the
endpoint must answer EXACTLY 204: the Android shell's reachability probe
counts only 204 as "the PC answered", because captive portals on foreign
Wi-Fi answer any request with a 2xx/redirect login page (live failure
2026-07-27); a drift to 200 would strand every phone — and **the injection
tripwire** (`InjectionMonitor` decision logic): Windows silently discards
all injected input from a non-elevated process while an elevated window
has focus (UIPI, live failure 2026-07-29 — SendInput "succeeds", the phone
looks healthy, the mouse is dead); the monitor must alarm on exactly the
configured miss streak, ignore small jumps, and re-arm after a success —
plus the WIRING: the real `InputInjector.move()` (with `SendInput` stubbed
out, so the build machine's cursor is never touched) must raise the alarm
that the web layer forwards to the phone, and clear it once read.

**The gamepad** (build rounds G1/G2, 2026-08-07) is gated in the same file
and by the same standard: synthetic pad events are driven through the page's
REAL mapping (`__padButton` / `__padAxis` — the two names the Android shell
calls) and the exact protocol that must come out is asserted. A D-pad arrow
presses the LEFT group's button in that direction and HOLDS the PC button
while the key is held; a face button presses the RIGHT group's, on the
RELEASE; L2/R2 are Layout (+) / Hide; the left stick steers on the tuned
curve at three deflections including the deadzone; the right stick scrolls
(and up is up); L1 held + a stick + release picks a wheel category and fires
NO button; a short shoulder tap steps the layout bar instead. Because the pad
is only ever let in through `buttonPress()` — the same activator a finger's
`pointerup` runs — this block also pins that there is no second button path
left to drift away from the pointercancel rescue (CLAUDE.md constraint 9).

The **stick curve is pinned by SHAPE, not by number**: the gate reads
`PAD_DEADZONE` / `PAD_CURVE` / `PAD_CURSOR_SPEED` out of the page and
recomputes the expected coordinate independently. The owner's answer to the
open question was "start from this table and tune it on the real controller",
so retuning the feel may never turn a build red — changing the FORMULA must.

The control layout comes from `tests/fixtures/actions.json` — pinned on
purpose: the repo `actions.json` is the owner's hand-edited file, and a
layout edit there must never block a build.

Run directly:

```
.venv\Scripts\python tests/test_input_pipeline.py
```

Requires `pip install playwright` + `playwright install chromium` (dev/build
machine only — nothing of this ships in the app).

### `test_layout_audit.py` — Layout Audit (THE SPACE & LEGIBILITY LAW)
The real page in a real headless Chromium at phone sizes (portrait 412×915,
landscape 915×412): every overlay panel is opened and measured — the card
fully inside the viewport, no horizontal page overflow, nothing clipped
inside it.

**CONTRAST** (owner 2026-08-06: *"je l' moguće da prođe situacija sa dizajnom
elemenata i bojama"* — six white buttons carrying near-white labels, and every
geometric check green). Text nobody can read is not a style opinion; it is
unreadable content, which is this law's whole subject. Every leaf text node is
measured against its **composited** backdrop — each translucent layer painted
over the one below, down to the page — and anything under a 3.0:1 WCAG ratio
fails, naming the element and the ratio. Compositing is not a detail: the first
version of this check ignored alpha and called this project's own translucent
selected states 1.00:1, and a guard that cries wolf gets switched off. It found
two real defects on its first honest run — the Sets picker's live badge at
1.96:1 (`var(--bg)` is not a token here, so the declaration was invalid and the
badge inherited near-white ink) and the command chooser's rows at 1.05:1 (a
`<button>` with no background of its own takes the WebView's light default). Covers the Quality panel, the Sets picker, the Dictation card,
the Aspect panel (incl. the Move handle's hit size), the layout list with
its rename button, the Rename card and the creation panel's Name field.
Also checks `grids._fit_rect` purely: the placed region never
leaves its box and sits centred, at any aspect (`pos` left the server's
geometry on 2026-08-09 — the phone anchors the letterboxed picture,
`tests/test_view_anchor.py`). Proof source for
`.claude/layout-proof.md`. The Name fields are WRAPPING textareas because
this audit caught the one-line version hiding most of a window title behind
its own horizontal scroll (2026-08-05). Also checks the D-PAD BUTTONS: a set's
pool may hold reserve commands whose names are longer than the shipped four
("Copy path", "Go to file"), the law forbids eliding them, so the label wraps —
and the wrapped label must still sit fully inside its 58 px button.

**TEXT CUT BEFORE THE DOM EVER SEES IT** (`__truncated`, independent grader
2026-08-07 — the hole that let the owner's own complaint pass three rounds
green). Every other clip check in this file measures the DOM: `scrollWidth >
clientWidth`, a card wider than its viewport, a label outside its button. A
string JavaScript shortened BEFORE the node existed defeats all of them by
construction — `client/layouts.js` did `s.title.slice(0, 29) + "…"`, so the
element fitted perfectly and the audit could only report PASS while 225 device
px stood idle on the same row and the owner was writing *"a pun naziv se na tom
ekranu ne vidi nigde"*. The tell such a cut leaves is the ellipsis IN THE TEXT,
so that is what is measured: a text node ending in "…" (or "...") with more
than 24 CSS px still free to its right on its own row, failing with the string,
the element and the number. CSS elision leaves no ellipsis in the text — that
case belongs to the `scrollWidth` check, and the two together cover both ways a
string can be shortened. The one deliberate ellipsis this app draws ("More
languages (2)…") declares itself with `data-opens-more` in `client/panels.js`,
in the product rather than in an allow-list nobody editing the product would
see. Self-tested by planting the cap again: 14 checks fail, naming *"Claude
Code - Remote User - V…" … was cut with 129 CSS px still free on its row*.

**THE REGION FRAME OPENS CLEAR OF EVERY CONTROL** (same grader). `#region-panel`
draws at z-index 55, above every control, so a newborn grab frame lying on one
paints its dashed edge and its 44 px handles across that control's label — his
picture read "Layou" where the corner button says "Layout". The default rect is
now placed in the band the chrome leaves free, and this check measures the
frame, its four handles and its hint bar against every `.corner`,
`#layout-bar` and `.group` rect, in both orientations. The panel's own entry in
`PANELS` was also changed to open at that default (`rgBox = null`): it used to
be staged into the top-left corner, which proved nothing about the bottom-centre
bar it claimed to test and handed every grader a picture of a state the product
never opens in.

**EIGHT LOOKS, not one** (build round R3, 2026-08-07). The desktop now
chooses one of four phone themes (dark / light / colored / colored-light —
the fourth arrived the same day with the owner's colour correction) and one of
two fills (outlined / filled), so there are eight real renderings of every
surface and a theme audited in one combination is not audited. The two
coloured themes are not variations of each other for this file's purposes:
they are different pages under DIFFERENT palettes (`server/config.py` ships
two), which is the whole reason the colour sweep exists — a colour that reads
on one surface can be invisible on the other. `_apply_look` therefore fetches
the palette through `config.ui_config()` instead of carrying a table of its
own, so the audit can never measure the light page with the dark colours. The full panel sweep runs in
every combination at PORTRAIT (narrowest cards, where a row starves first);
landscape keeps the default look, because what landscape tests is GEOMETRY and
geometry does not change with a colour. Three things changed with it:

- the contrast check's page FLOOR is read from the live `--surface-0` instead
  of the dark theme's literal `[15, 23, 42]` — otherwise every light panel
  would have been scored against a dark page that is not there;
- the check moved into one installed `window.__contrast(root)` so the panels,
  the D-pad and the wheel are judged by the same function, not three copies;
- **the D-pad groups and the category wheel are measured too.** That is where
  a set's colour actually lands in the coloured themes, and no panel check had ever
  looked at them. Self-tested by forcing `theme.js`'s `inkOn()` to return white
  whatever the surface, so
  every ink comes out white: thirteen labels go red at 1.74–2.72:1 in
  `colored/full`, in both orientations, and green again when it is put back.

**A LOOK-NAMED SHOT MUST BE THAT LOOK** (`_shoot`, 2026-08-07 — the tooth this
file was missing, and the reason three rounds of independent graders were
handed pictures of the wrong look while every check printed PASS). Twelve
`Controls*` pictures carry a theme and a fill in their filenames, and nothing
here had ever compared those two words with `body.dataset.theme` /
`body.dataset.fill` at the instant the shutter fired. Two of the twelve
therefore showed a different look: `Controls_dark_full.png` was byte-identical
to `Controls.png` (max per-channel diff 0 over all 1,507,920 pixels; both
87,024 px of the 20 % tint `rgb(18,26,45)`, never the solid `rgb(30,41,59)`),
and `Controls_light_transparent_landscape.png` rendered the dark page
`(15,23,42)` where its portrait twin renders `(236,238,246)`. Both were
labelled `audit: PASS`. Two things close it:

- `_shoot(page, label, look, results)` is now the ONLY way a look-named shot is
  written. It reads the two dataset attributes, records a per-shot result, and
  **FAILS the audit** — not warns — when they disagree, printing `asked for
  X/Y, the page was showing A/B at the shutter`. The picture is still written:
  a grader has to be able to see what was measured.
- The drift itself is gone at both ends. `_apply_look` also calls
  `config.apply(phone_theme=…, phone_fill=…)` — the audit runs the real server
  in THIS process, so the look it asks for is the look every later `config`
  frame carries, instead of the audit fighting its own server (in-memory only;
  `save_user_settings` is the sole writer of the owner's file). And the page's
  readiness gate now waits for `monitor.w > 0`, the socket's first `config`:
  `#group-left button` goes green about **1.4 s** earlier — the D-pad renders
  from the page's own defaults — and everything done in that window used to be
  silently overwritten when the frame finally landed. Exactly one look per
  browser context was being stomped, which is why the wrong picture moved from
  run to run.

Self-tested by planting the reset back: `_apply_look` was made to close the
socket and wait 2.5 s, delivering a `config` between the request and the
shutter exactly as it used to happen by accident. **35 look-named shots go
red** in one run (`the shot shows the look it is named for: Controls dark
full → FAIL`), `Controls.png` and `Controls_dark_full.png` return to a
per-channel difference of **0**, and every `light` shot returns to the dark
page. Restored, the audit is green and the same pair differs by R13 G16 B15
across 134,804 pixels (8.94 %), with the filled shot carrying 87,023 px of the
solid `rgb(30,41,59)`.

**THE DICTATION CARD'S THREE ROW STATES, AND WHOSE LANGUAGES THEY ARE** (owner
2026-08-09, task 127). The card now names the DEVICE it describes and offers a
listen button per language, so the sweep alone is not enough: it measures fit
and contrast, but it cannot say whether the states that carry the honest limit
are on the card at all. `tests/_audit_panels.py` → `DICT_STAGE_JS` therefore
stages four rows on purpose — sr-RS and en-US (a voice AND a sample → the
button), de-DE (no voice on this device) and is-IS (a voice, no sample
sentence written) — and a dedicated check asserts all three states are
present, that every listen button is a ≥40 px finger target inside the card
and clear of its own row's name, and that the device line contains the model
THIS browser context's User-Agent carries (`UA_MODEL`) rather than the
"this device" fallback, which renders perfectly while the real path is broken.
Self-tested by planting both defects: dropping `speakAs` from the stub turns
the whole card into the no-preview case (**4 findings** — no listen button, no
honest-limit row, and each of the two notes named), and asserting a model this
context never sends reports the line's real text back. A row state nobody
stages is where this project's bugs keep arriving.

**The panel catalogue moved out** on 2026-08-09 (THE STRUCTURE LAW — the
listen control pushed this file past 1,000 lines): `tests/_audit_panels.py`
now holds WHICH overlay is opened and in WHAT state, the boundary this file's
own docstring already drew, while `tests/_audit_js.py` keeps HOW a truth about
pixels is measured.

Run: `.venv\Scripts\python tests/test_layout_audit.py`

### `test_layout_audit_qt.py` — Layout Audit, Qt windows (THE SPACE & LEGIBILITY LAW)
The runtime half of the law for the DESKTOP app (MIGRATE-LAYOUT.md step 2,
owner go 2026-08-05). Every Qt window the project has — `MainWindow`,
`ControlsEditor`, `ChordRecorder` — is built offscreen in its FULLEST
realistic state (a running server with a Tailscale URL and the longest guided
text; the set with the longest command pool), shown at its DECLARED minimum
and at +50%, and its whole widget tree measured for: CLIPPED (a widget with
less room than it minimally needs), ELIDED (text wider than its element),
ITEM CUT (a list/table row wider than its column — Qt's item views truncate
silently, and an item is not a QWidget, so the widget checks cannot see it),
SCROLL+SLACK (something scrolling while a spacer in the same window holds
unused space), plus the law's precondition: a declared, computed minimum size.

Three measurement notes, each about measuring the RIGHT thing rather than
loosening a tolerance: a `QHeaderView`'s `minimumSizeHint` is an
orientation-blind square (68×68 whatever its sections hold), so only the
header's own axis is compared, against Qt's size hint and the font; a `QLabel`
is charged no control padding, because it paints straight into its
contentsRect; and a container of WRAPPING children has no single minimum
height (`minimumSizeHint` quotes it at the narrowest width), so only its width
is checked there — the vertical truth is measured element by element by the
wrapped-text branch.

**"Fullest state" includes what arrives LATE** (owner screenshots 2026-08-06).
`MainWindow`'s factory used to build the window and stop there — but two things
reach it only after it is on screen: the update button (hidden until GitHub
answers) and the notify switch's caption (one line normally, three when it has
to report a failure, and a failure names a path). The factory now `show()`s the
window first and lets both arrive afterwards, exactly as the owner's evening
does. Self-tested: with the fix disabled the audit reports
`CLIPPED MainWindow: has 820x837, needs at least 618x880` — 43 px, the update
button's own row, which was being drawn over the QR's link.

**MainWindow (reopened from the tray)** is the same window reached the way the
owner actually reaches it: closing this app hides it to the tray, so the update
offer lands on a window nobody is looking at, and Qt gives a hidden window no
real metrics. The case shows the window, hides it, lets the late content
arrive, and hands it back for the audit to show again — proving the minimum is
re-measured on the way BACK. Self-tested the same way (signature on
`isVisible()` + a settle-once `showEvent` restored): `CLIPPED … has 869x837,
needs at least 618x880`.

**It is a measurement case and NOT a second picture** (`NO_SHOT`, 2026-08-07 —
independent graders reported it three times: `MainWindow.png` and
`MainWindow__reopened_from_the_tray.png` were byte-identical, md5
`12c59bd6ae08`, as were their light pair `c72b15932b44` — four proof lines
standing over two pictures). Measured before deciding: both windows built,
each resized to its own declared minimum and rendered at 2x, in both palettes.
All four report **minimum 463x685, sizeHint 463x657**, and the two pixel
buffers hash the same in each palette (`7ce0566f4066` dark, `3bcd7da153a3`
light). They cannot differ, and not by accident — the tray factory reaches the
identical widget state by a longer road. What the case proves is that the
hidden round trip leaves no WRONG FLOOR behind, a claim about numbers, and a
photograph says nothing about it. So the case stays in `WINDOWS` and its name
goes into `NO_SHOT`: `audit_window` skips the screenshot only, never the
checks. A picture that is a copy of another picture is not evidence — it is a
second proof line that costs a grader a second look and returns the first
look's answer.

**E. OVERLAP, and REAL FONTS** (owner 2026-08-06, after this guard reported
PASS over the window he had photographed twice). Two holes, both closed:

- Every check here asked whether an element got its own SIZE; none asked where
  it was PUT. Qt does not clip a layout that is short of space — it OVERLAPS
  it, so every widget reports its full size while the pairing link is painted
  across the QR. `check_overlap` compares the cells of each layout (not
  arbitrary siblings: a scrollbar over a viewport is legitimate) and fails on
  any intersection. It immediately caught one nobody had reported — the
  Traffic window's chart drawn 4 px over the caption beneath it.
- The platform WAS the measurement error: `offscreen` has none of the
  machine's fonts and substitutes metrics, reporting the main window at
  869x880 where the owner's real Segoe UI at 125% scaling needs 503x937 — the
  defect lived in the difference. The native platform is used whenever there
  is a desktop, with `WA_DontShowOnScreen` so the full layout machinery runs
  with real fonts and DPI while nothing appears on screen; offscreen remains
  the fallback. That switch alone surfaced two more genuine defects: the
  Controls editor 59 px short, and a Traffic combo cut to "Last 10 minut" by
  the theme's own 92 px combo floor.
- The container-height blind spot is gone with them. This file used to zero
  out the height of any container with wrapping children and check only its
  width; that is how the QR card could be handed 332 px against a minimum of
  348 in silence. It is now asked `heightForWidth` at the width it actually
  has.
- Each window's screenshot at its DECLARED minimum is written to
  `.claude/shots/` by the audit itself, so the picture the layout gate grades
  can never be of a different build than the one just measured.

- **BOTH PALETTES** (build round R3, 2026-08-07). The whole registry is built
  and audited under dark and then under light, and each window is shot in
  each — the light shots carry a `__light` suffix so the dark ones keep the
  filenames the existing proof lines already point at. A light theme is not a
  repaint of a dark one: a translucent white border vanishes on white, a
  16 %-alpha wash reads as nothing on a card, and an icon whose ink was baked
  in at build time turns invisible. `use_palette()` sets `SETTINGS.ui_theme`
  as well as calling `apply_theme`, because `MainWindow` applies that setting
  in its own constructor and would otherwise flip the app back.

Run: `.venv\Scripts\python tests/test_layout_audit_qt.py` — also a full-run
guard in `run_guards.py`.

### `test_presence.py` — Presence Gate
Proves that the phone leaving work mode frees the owner's desk: layout
members are always-on-top while the phone shows them, and before 2026-08-05
only a CLEAN socket close ever ended that — which a locked phone rarely
manages (Wi-Fi sleeps, the connection just goes quiet), so the windows kept
hovering over everything at the desk. Checks the heartbeat holding a
session, the watchdog ending a silent one (members minimized, socket closed
4408), an announced excursion (image picker, camera, voice) NOT counting as
a leave, an announced leave acting at once, `_leave_session` being
idempotent, and the resume pointer (`LayoutRegistry.last_focus`) surviving
rename/remove and forgetting on a deliberate Desktop choice. No browser and
no real windows — the window calls are stubbed.

Run: `.venv\Scripts\python tests/test_presence.py` — also a fail-closed step
in `build.py` (0c/6).

### `test_notice_channel.py` — Notice Channel Gate
Proves that a notice reaches the phone while the owner is **not looking at
it**. His report on 2026-08-07: *"notifikacije mi stižu tek kada podignem
aplikaciju iako je sve vreme otvorena u pozadini"*. The cause was structural —
every notice rode the streaming socket, and that socket is closed on purpose
the moment the page hides (project CLAUDE.md constraint 8), so at the exact
moment a notice mattered there was no channel and the server queued it until
he opened the app himself.

Eight checks against a REAL server (`web.create_app` with a fake stream,
registry and injector) and a real HTTP client standing in for the phone's
foreground service: `/notices` refusing a bad token; a notice arriving whole
down the waiting channel with the page closed; **a waiting phone never
counting as a present phone** (the one-device slot empty, `stats.clients` 0,
the capture not started, the layout registry untouched, neither
`presence.watchdog` nor `focus_guard.watch` armed — a notice connection that
looked present would nail his own windows always-on-top over his desk); the
idle channel carrying one beat byte and nothing else; an open page taking a
notice ALONE, never twice; a page dying mid-notice falling through to the
channel instead of into the queue; and the queue being the last resort, drained
oldest-first the moment the phone starts waiting again.

Every check was shown red on a planted defect before being trusted — including
one plant that revealed a real weakness in the gate itself (the isolation check
ran after another check's `reset()` and would have scrubbed a live defect out
from under itself; it runs first now).

The Kotlin half — `NoticeService`, `NoticeLink`, `Bridge` — cannot be exercised
here: there is no Android runtime on the build machine. What this gate pins is
the PC's half of the contract and the exact bytes the shell must read.

Run: `.venv\Scripts\python tests/test_notice_channel.py`

### `test_link_recovery.py` — Link Recovery Gate
Proves that a phone which loses its **route** comes back by itself. His report
on 2026-08-07: *"kada nismo na wi-fi mreži … dešava nam se prekid veze, i ovo
'Try again' dugme retko kad pomogne, već moramo više puta, nekad čak i da
zatvorimo celu aplikaciju."*

A REPEAT. Three mechanisms were already written as the answer to this exact
complaint — two stored addresses probed at start, a self-re-probing error card,
a `/ping` contract only an exact 204 satisfies — and all three hold. All three
only run in states he is not in. The state he **is** in is a page that loaded
perfectly and is now retrying an address that no longer reaches the PC, and
there: the shell re-probed only behind its error card, the page cannot move
itself (its socket goes to `location.host` and nowhere else), a socket stuck
CONNECTING or opened onto silence is skipped by `ensureConnected` so the page
retries nothing at all, and on the PC a socket the watchdog had already
declared dead still held the one-device slot — so the returning phone arrived
as a *second device against its own corpse* and its first act was
`await prev.close(4409)` on a socket with nowhere to send.

Eleven checks in three parts. **The PC** (fakes, no Windows): a watchdogged
session vacating the one-device slot; `presence.hand_over` bounded against a
socket whose `close()` never returns; and the real `ws_endpoint` still
delivering `actions`, `layout_state` and `config` to a new client while a
corpse sits in the slot. **The page** — the REAL `client/state.js` +
`client/connection.js` run in node inside a sandbox with a virtual clock, a
scripted WebSocket and a fake `window.Android` (no browser, no server, no
waiting): a socket that never opens abandoned and retried, a socket that opens
and is never served abandoned and retried, a run of unserved connections
(silent **or** flapping) asking the shell exactly once, a served connection
never asking, and 4401/4409 never being read as a lost route. **The shell**
(source contract — no Android runtime here): the network-change re-probe not
gated on the error card, `Android.linkLost()` existing and reaching the
resolver, and session health judged by ADDRESS rather than by a whole URL
string (with the callback now firing on a live page, a string mismatch would
reload a working session on every blip).

Every check was shown red on a planted defect before being trusted — ten
plants, ten reds, tree restored green.

Needs `node` on PATH for the page half; a missing node fails the gate rather
than skipping it.

Run: `.venv\Scripts\python tests/test_link_recovery.py` — also a fail-closed
step in `build.py` (0j/6).

### `test_focus_guard.py` — Focus Gate
Proves that what the phone types lands where the owner is LOOKING. `SendInput`
has no target, so before 2026-08-06 every dictated character went to whatever
window Windows called the foreground at that instant — and when something on
the PC took focus mid-sentence (an app starting, a dialog, another agent's
editor window), the rest of the sentence went there, silently, with the stream
still showing the PC. The owner reported it three times in one evening, and
the fourth report WAS the bug: a sentence dictated for another project arrived
in this project's session.

Twenty-three checks, no browser and (for the policy half) no real windows —
every user32 call is answered by a fake: the layout fence refusing a foreign
foreground and handing focus back to the member being typed into; the fence
holding on a fresh connection with no pin yet; a move the owner made INSIDE
the layout being followed, not fought; a dialog of a member (Save As…)
counting as that member; the desktop pin arming on the burst's first key and
restoring `topmost=False`; a click / `next_input` / layout switch re-arming it
while a thief arms nothing; the thief being NAMED in the log;
`LayoutRegistry.focus()` raising the keyboard member LAST (one excursion used
to move dictation into the other pane); `prune` moving the target off a window
closed at the desk; and the whole path through the real `web._receive_input`
dispatcher.

**Build round R1 (owner-approved 2026-08-07) closed the hole INSIDE one
message.** `SendInput` types one code unit at a time, and it was MEASURED on
the owner's PC at ~1.84 ms per character — a 600-character dictated sentence
is over a SECOND during which a thief used to get the remainder. The gate
proves that a steal at EIGHT different offsets costs zero characters and the
rest still lands in the right window; that a steal inside an emoji costs at
most that character's tail, never a whole character; that typing which cannot
be re-aimed STOPS and names both the thief and what was never sent; that the
**phone is told** what never reached the PC; that half a character never goes
out and never raises into the dispatcher; that a caller passing no guard
behaves exactly as before; and that the real dispatcher hands the injector the
checkpoint.

Run: `.venv\Scripts\python tests/test_focus_guard.py` — also a fail-closed
step in `build.py` (0e/6) and a full-run check in `run_guards.py`.

### `test_focus_hook.py` — Focus Hook Gate
The other half of the focus work, split out on 2026-08-07 when the two
subjects together crossed THE STRUCTURE LAW's 1,000 lines: `test_focus_guard`
proves the POLICY, this proves the MACHINERY that carries it.

Nine checks: the hook announcement defending the layout measurably before a
poll tick could have; **the callback only SIGNALLING** — a WinEventProc runs
inside Windows' own event dispatch, and the first version called the guard
from there, measured stalling a second caller for 2.99 s (the owner felt it as
a juddering mouse); the log line when a listener overruns that contract;
a hook that Windows still claims to hold but that has gone quiet being reported
once; the 0.25 s poll still defending when Windows refuses the hook; the
thread's start / stop / unhook / restart; a timed-out `stop()` keeping the
thread's identity instead of orphaning it with the hook still installed and
letting a second one be built over it; every documented exit path really
calling `ServerController.release_windows` — **parsed with `ast` inside the
function that handles that exit**, because a file-wide grep stays green when
tray Quit stops calling it while another line still names it; and two threads
never deciding the target at once.

**It installs no real hook and touches no real window.** The owner works on
this machine: a hook or a thread a FAILING test forgot to release is his mouse
juddering, not a red line in a terminal. The thread, the joins and the identity
book are real; Windows is faked.

Run: `.venv\Scripts\python tests/test_focus_hook.py` — also a fail-closed step
in `build.py` (0e/6) and a full-run check in `run_guards.py`.

### `_focus_fakes.py` — the fake Windows both focus gates share
`FakeWin32` (the user32 calls the guard makes), `Raises` (records what would
have been raised, raises nothing), `FakeHookWin32` (the four calls
`focus_hook` makes into Windows, incl. a `deaf` mode that swallows `WM_QUIT`
so a timed-out stop can be tested on purpose), `TypeSpy` (the REAL injector
with only `SendInput` replaced, recording every UTF-16 unit and the window
that would have received it), the fake socket/injector, and the shared runner.

### `test_layout_protocol.py` — Layout Gate
Proves that EVERY layout message the phone can send answers it. Born from the
2026-08-06 live failure — *"layout, kreiraj iz liste, ništa se ne dešava"*: the
loading cube spun and no list ever came, because one line in
`layout_api.layout_list` read `mon_rect = mon_rect(stream)`. That name is the
module's own function, so the assignment made it a LOCAL for the whole function
and the call on the right-hand side raised `UnboundLocalError` before anything
was sent. The owner's server log carried the traceback three times; the build
carried nothing, because **no test walked this path** — four guards, an input
gate, a presence gate, a notify gate and a focus gate, and the phone's entire
layout protocol had none.

Six checks driving the REAL `web._receive_input` dispatcher over the REAL
`layout_api` and `LayoutRegistry`, with only Windows faked (user32, the window
list, UIA, the process table): create from a LIST (windows plus the tabs of
tab-capable apps), create by TAPPING a window, create → focus → desktop,
rename / app-sets / aspect / remove each answering with a fresh `layout_state`,
and a 2×1 grid built from the list. A handler that raises, or that answers the
phone with nothing, fails here. Self-tested by replanting the defect: the
first check reports the exact `UnboundLocalError` and fails.

**And three checks on the Move handle's SERVER half** (owner decree
2026-08-09, the FOURTH round of the same feature). Round two taught this file
to follow the handle to the WINDOWS with `install_fakes(track_placement=True)`
— a model of the desk where every commanded rect becomes the window's real
frame — and that was still the wrong screen: the server crops the region and
streams the SAME picture wherever the windows sit, so three green rounds
moved nothing the owner could see. The phone half (where the letterboxed
picture actually lands) is `tests/test_view_anchor.py`; what this file owns
now is the server's side of that contract, still asserted on the RECT:
- *placement is CENTRED whatever the pos* — solo **and** grid, portrait
  **and** landscape: fresh applies at 0 / 500 / 1000 land on identical,
  centred rects, and each answer's `layout_state` carries the pos the phone
  anchors by.
- *a pos change moves the phone's picture, never the windows* — the SAME
  ratio re-applied at a new pos places NOTHING (the untangled trigger:
  `place_pending` + `arranged_ratio` + `_standing`, with pos deliberately
  absent) while the reply still carries the new pos to the phone.
- *a wandered window is put back — centred* — the desk is still re-read on
  every Apply (round three's lesson, kept): a member that drifted off its
  rect is re-placed, to the centre.

Proven by planting the old behaviour back: sliding the region by `lay.pos` in
`layout_registry.focus` turns the first two red — *"placement FOLLOWED pos"*
with the union rects at y=0/290/581, and *"a pos-only change re-placed
windows"*.

Run: `.venv\Scripts\python tests/test_layout_protocol.py` — also a
fail-closed step in `build.py` (0f/6).

### `test_view_anchor.py` — View Anchor Gate

THE POSITION LIVES ON THE PHONE (owner decree 2026-08-09, the Move handle's
FOURTH round). Three rounds shipped green through gates that measured window
rects on the PC monitor — a screen the owner never sees — while the geometry
he grades the feature by, where the letterboxed picture sits on his tablet,
was computed by no check. The fit-and-anchor math therefore lives in a PURE
module (`client/view-anchor.js`, the caret.js/voice.js pattern) and this gate
runs it WHOLE in node: pos 0 flush to the near edge of the slack axis
(his gesture — the app at the TOP, empty space below), 1 flush far, 0.5
centred, both orientations, matching aspects immune to pos, a missing pos
read as centred (old servers), out-of-range clamped, and a region off the
origin still landing on its anchor. Wiring checks pin both ends — render.js's
`computeViewHome` must run `fitAnchorView` with `layoutAnchorPos()`, the page
must load the module before render.js, the module must stay pure, and the
server must keep centring windows while `layout_state` still echoes `pos` —
because a pure function nobody calls is a feature that does not exist
(the actions.json lesson). Proven by planting the old always-centred rule in
`fitAnchorView`: pos 0 then draws at y=866.25 — the owner's centred picture,
to the pixel — and the gate goes red.

Run: `.venv\Scripts\python tests/test_view_anchor.py` (needs node) — also a
fail-closed step in `build.py` (0o/6).

### `test_caret_lift.py` — Caret Lift Gate

THE KEYBOARD LIFTS THE PICTURE ONLY IF NEEDED, ONLY BY THE SHORTFALL (owner
2026-08-07, after asking for the opposite thing twice and being right both
times: a box at the bottom is covered unless the picture rises, a box at the
top leaves the screen if it does). Runs `client/caret.js` WHOLE in node — it
is pure by design, the `voice.js` / `view-anchor.js` pattern.

**Rewritten 2026-08-09, because this file is half of why five rounds shipped
green while the rise was pinned at exactly 0 on his tablet.** The old fixture
handed the rule a view transform with `VIEW = {"scale": float(CANVAS_H)}` —
1800 — under a confident paragraph explaining why that was right. `view.scale`
is a ZOOM FACTOR and is 1 at home; it can never hold 1800 in production. So the
fixture made `caret.y * scale` mean "canvas pixels", the rule agreed with it,
and on the real device the same expression put a caret at y=0.95 at 0.95
PIXELS from the top of the screen. Same lesson as the Move handle two sections
up: **a gate that invents its own value for a production variable proves the
fixture to itself.**

The rule now takes the rect the picture is DRAWN into (`drawnRect()`), which is
what the owner actually looks at, and this gate feeds it rects a real phone
produces:
- *the production case really produces pixels* — the check the old fixture
  could not make. Caret at y=0.95, a 700 px keyboard on an 1800 px canvas, and
  the answer asserted EXACTLY: **660 px** on a full-canvas picture and
  **519 px** on a LETTERBOXED one (`picture = {y: 150, h: 1500}` — layout
  focus, where he does most of his typing, and a shape the old fixture had no
  way to express). They must differ: the old arithmetic dropped the letterbox
  offset entirely, so a check that cannot tell those two apart never looked at
  the picture at all.
- *only if needed / only by the shortfall / never off the top* — a caret at the
  top moves nothing, a 20 px overlap lifts 34 px and not 700, and a keyboard
  leaving a 50 px strip lifts only what the strip can take.
- *an unknown caret never moves the picture* — and a caller still passing the
  retired `unknownMode` argument changes nothing, so the deleted branch cannot
  come back by accident.
- *the plumbing, not just the arithmetic* — `window.__imeHeight` must exist in
  `render.js`, be folded in as `Math.max(kbSelf, imeHeight)`, and sit BETWEEN
  `updateViewport` and `initMse`. That last one is not pedantry: the receiver
  was deleted as collateral by a revert of the streaming block it happened to
  sit next to, and nothing noticed because nothing in the repo calls a
  `window.*` global. `Insets.kt` must still push the inset and must carry
  `forgetImeInset`.

Proven by planting the pre-2026-08-09 `caret.y * view.scale + view.ty` back:
five checks go red, every one of them reporting a rise of **0** — the exact
symptom he reported six times.

Run: `.venv\Scripts\python tests/test_caret_lift.py` (needs node) — also a
fail-closed step in `build.py` (0m/6).

### `test_stream_lifecycle.py` — Stream Lifecycle Gate
Proves that a client which is GONE takes its encoder with it. Born from the
2026-08-07 live failure, found in the owner's own running app while his mouse
juddered: **one leaked H.264 session ran for four hours at native 4K with no
phone connected at all** — 12,924 s of `ffmpeg.exe` CPU, `_sessions` never
empty again (so capture could never stop), and 1,890 `Client stream backlog —
resetting the H.264 session` warnings, one every ~7 s, for a client that had
disconnected at 12:05.

Root cause, dated to the millisecond by his server log: `await
asyncio.to_thread(manager.open_session, …)` **cannot be cancelled.** The socket
died 910 ms after auth; the awaiting coroutine raised `CancelledError` at once;
the worker thread ran on and finished the encoder 219 ms later, registering a
session whose only reference had just been thrown away. `close_session` was
never called for it, and its `push` callback kept overflowing a queue nobody
would ever drain again.

Seven checks driving the REAL `web._stream_h264` loop over the REAL
`H264Session` / `H264Manager`, with only the process and the frame source faked
(a stand-in on ffmpeg's exact pipe contract, emitting a minimal but genuine
`ftyp`+`moov(avcC)` init segment — no dxcam, no ffmpeg, no 4K, because the
owner's CPU was already saturated by the very bug under repair): **cancelled
mid-open** (the live bug — the fake encoder's `head_delay` is that 219 ms
window, widened), a clean close, a 4409 takeover / silent network death
mid-stream, an exception in the send path, server stop mid-spawn, **no reset
ever fires for a client with no live socket**, and — the check that keeps the
gate honest — **a live but SLOW client still is reset**, so the suite can never
pass by having the backlog feature deleted.

Every check ends on one verdict: the active count is zero, capture is stopped,
every encoder is terminated, and (unless the check asked for one) not one reset
was logged.

Self-tested by planting each defect separately, which is how the two defences
were shown to be genuinely independent:

| Planted | What goes red |
|---------|---------------|
| `open_session` ignores `owner.take()`'s answer (the live code) | only *cancelled mid-open* — the other six stay green, and the dead-client check proves the queue guard alone still silences the log |
| `owner.release()` removed from `_stream_h264`'s cancellation path | only *cancelled mid-open* |
| the `if not o.alive` guard removed from `push` | only *a client with no live socket is NEVER reset* |

The dead-client check disables the first defence ON PURPOSE (`DeafOwner`, a
claim that accepts every session and remembers none — exactly the pre-fix
world) so the second defence is tested on its own, and it asserts that the leak
it planted was real (`leaked == 1`) so it can never quietly decay into testing
nothing.

Run: `.venv\Scripts\python tests/test_stream_lifecycle.py` — also a
fail-closed step in `build.py` (0g/6).

### `test_actions_migration.py` — Actions Migration Gate
Proves that a NEW VERSION'S FIELDS actually reach the owner's own
`%LOCALAPPDATA%\RemoteUser\actions.json`. His copy is seeded once, at his first
install, and never replaced — `merge_shipped_pools` is the only path a later
version has into it, and until 2026-08-07 it copied a **hardcoded list of field
names** (`name, icon, required, process, title`). Anything invented after that
list was written silently never arrived. The bill: the shipped Claude app set
gained `"agent": "claude"` on 2026-08-06, his copy never did, so the set could
only match by TITLE — and Claude Code names its VS Code tab after the
CONVERSATION, making the condition unsatisfiable forever. **He reported the
Claude set missing across four or five releases.** The same engine had already
kept "Anywhere" in his Settings set after the update that replaced it, and
`wheel_order` (build round R5) was one release from joining them.

Why every guard stayed green through all of it, which is the part worth
remembering: `tests/test_controls_sets.py` builds its "user file" with
`user = copy(shipped)`. **A user file made out of the shipped file already has
every new field**, so the guards proved the repo's actions.json to itself and
could not fail. This gate therefore starts from an OLDER shape — the owner's
real file, held as literal text, not derived from the shipped one — and it does
NOT test for the field named `agent`: it plants a field name nobody has
invented, because a gate written around today's field would ship broken on
tomorrow's.

Six checks: his real file receives the agent switch · a field nobody has
invented yet arrives · a new top-level key arrives (`wheel_order`, plus an
invented one) · everything he owns survives (`active`, `order_land`,
`order_port`, `enabled`, `wheel_order`, `custom_sets`, `left`/`right`, and his
button renames) · a field we retired stops lying · a set he has never had
arrives whole.

Self-tested by planting the defect: restoring the old hardcoded field list and
removing the top-level migration turns **four of the six red**, while all four
merge checks in `test_controls_sets.py` stay **green** — the exact shape of the
failure this gate exists to end.

Run: `.venv\Scripts\python tests/test_actions_migration.py` — also in
`run_guards.py` and a fail-closed step in `build.py` (0h/6).

### `test_update_handover.py` — Update Handover Gate
Proves that an update never costs him the session he is installing FROM. His
report on 2026-08-07: *"dešava se da ja ne mogu da instaliram novu verziju ako
nisam kući, zato što čim uđem u instalaciju on će meni ugasiti Remote User i
više neću moći da komandujem odavde."* Every fix this project ships reaches him
only through an install, so an install that kills the remote session is a bug
that eats the project.

Nine checks against `server/update_handover.py` and, for six of them, the
SHIPPED handover script itself — written out of `update_handover.SCRIPT` and
really executed, so the batch this project ships is the batch this gate proves:
nothing unverified is ever run (truncated / too small / not-a-program /
missing) · a damaged download stops EVERYTHING before anything irreversible
(no notice, no record, no script, no spawn) · the phone is told BEFORE the app
can exit · the script waits for the old app's own pid to be gone before the
installer starts (proven by the fake installer looking that pid up and writing
down what it found) · **THE ROLLBACK** — a non-zero installer exit still starts
an app again from the same path · it proves the app came back, and tries once
more when it did not · "nothing to run" is SAID, never shrugged off · and the
next start tells him how it went, good or bad.

**Nothing real is touched.** The installer and the app are fakes; the pid it
waits on and the image name it probes are the gate's own (`RU_GATE_FAKE_APP.exe`),
and `refuse_to_touch_the_real_app()` asserts that before every run — a gate that
could take his live session down while proving his live session is safe would be
its own worst bug. It kills what it starts and prints a check proving nothing of
its own is left running.

It earned its keep on the first run: the `DETACHED_PROCESS` spawn flag left the
script with no console at all, where `tasklist` silently returns nothing — so
"is the old app gone?" answered yes instantly and wrongly. And a bare `find`
in the script resolves to **GNU find** on any PC with Git for Windows, which
reads its argument as a file name and fails the same way. Both are real
shipping defects that no amount of reading would have found; every system tool
is called by full path now.

Self-tested by planting three defects: making the restart conditional on the
installer's exit code turns the rollback check red; moving `tell_phone` after
the spawn turns the ordering check red; disabling the declared-size comparison
turns the verify check red. Each returns exit 1 and is green again on revert.

The NSIS half — `/S`, the silent-mode section choices — is compile-verified
only (`makensis` against a throwaway payload). Running a real silent install on
the dev machine would taskkill the owner's live app, rewrite his autostart task
and his firewall rule; that half is proven on his PC or not at all.

Run: `.venv\Scripts\python tests/test_update_handover.py` — also a fail-closed
step in `build.py` (0i/6).

### Guard tests (THE LAWS — rules/CODE.md → Enforcement, rules/DOCS.md → Enforcement)
Five standard-named guard tests, a fast runner, and a small shared helper —
four installed 2026-08-01 alongside the MD-First 2.0 docs migration, the fifth
(the layout law) on 2026-08-05:

- `_guards_common.py` — `iter_source_files()` / `iter_doc_files()`, pruning
  `.venv`/`build`/`dist`/etc. during the walk (not after) so the guards stay
  fast.
- `test_structure_law.py` — THE STRUCTURE LAW: no source file (`.py`/`.js`/
  `.ts`/`.kt`/`.html`/`.css`) over ~1,000 lines outside the `RATCHET`
  allowlist (currently empty).
- `test_config_sections.py` — THE CONFIG SECTION LAW: every top-level
  definition in a `CONFIG_FILES` entry sits under a `# ══...══` section
  banner; no post-definition table patching; no duplicate dict keys.
  `CONFIG_FILES` = `server/config.py`, `server/gui/theme.py`.
- `test_docs_coverage.py` — every source file has the `__about`/`__flow`
  docs its tier requires; the tier lists here are the project's single
  source of truth (update this file in the same commit as any tier change).
- `test_doc_links.py` — every relative link in every `.md` resolves to a
  real file, and every `.md` is reachable from `README.md`.
- `test_layout_law.py` — THE SPACE & LEGIBILITY LAW, static half: no banned
  API in a GUI source (`server/gui`, `client`) — elision, forced scrollbars,
  disabled wrapping, hard pixel sizes on text-bearing widgets, CSS
  `text-overflow: ellipsis` and `-webkit-line-clamp`. One line may opt out
  with `layout-law: exempt - <reason>` ON that line; `RATCHET` is empty.
- `test_controls_sets.py` — the owner's `actions.json` is never silently
  rewritten: two sets of one process both survive a pool merge, renames are
  carried across it, a pool corrupted by an older build repairs itself, and
  switching sets in the editor never writes into another set's pool (both
  failures of 2026-08-05). Builds the real Controls dialog offscreen, so it
  is a full-run guard.
- `test_app_set_wheel.py` — the app-aware sets appear for the RIGHT window
  and pay for their seat (owner's two rules of 2026-08-06): only the Claude
  conversation wears the Claude set — never an open `CLAUDE.md`, a transcript
  or any other document carrying the word — and an app set charges a wheel
  slot, the charge being the largest group that can appear together (VSCode +
  Claude = 2, Chrome + Explorer + VSCode = 1). Two more rules from the same
  day: **the owner's per-layout ticks beat the guess** — the guard pins his
  real title, `Ispravka UI dizajna meni…`, on which the automatic test can
  only ever find VSCode (Claude Code names its tab after the conversation, and
  nothing else on the window identifies it) — and **the cap of 8 is a law over
  the STORED state**: the SHIPPED `actions.json` may not tick past it, and a
  state that already does is brought back by dropping the app set first.
  It runs `client/sets.js` **whole** in node behind stubs for the prefs bridge
  and the focused layout, rather than lifting a block out of it: the cap is
  enforced across storage, so stubbing the storage away would prove the
  arithmetic and miss the law. Skipped, not failed, when node is absent.
  Self-tested by re-enabling `Cursor` in the shipped file — "the shipped
  actions.json ticks 9 sets by default".
- `run_guards.py` — runs all guards plus the focus gate (or, with `--fast`,
  structure + config-sections + the static layout law — a grep costs nothing, so it
  belongs in the PostToolUse hook's budget; the Qt audit is full-run only,
  it builds a QApplication); exits 2 on any failure. Wired into
  `.claude/settings.json` (PostToolUse `--fast`, Stop full). Run directly:
  `python tests/run_guards.py`.

These are plain `assert`-based functions (pytest-discoverable, but
`run_guards.py` calls them directly — no pytest dependency, since neither
this project's venv nor `requirements.txt` install pytest).

## Connections

### Uses
- [Client (folder)](../client/___client.md) — the page under test, served from disk
- [Web Layer](../server/__about/web.md) — the real FastAPI app + protocol handler

### Used by
- [Setup (folder)](../setup/___setup.md) — `build.py` runs this as the
  fail-closed INPUT GATE before packaging; a broken click path cannot ship

## Design Decisions

- **Real browser, fake injector.** Unit-testing the JS or the protocol alone
  kept missing the class of bug that actually shipped (handlers correct,
  events never delivered). Touch emulation in real Chromium exercises the
  same Pointer Events pipeline the WebView uses, headless and screen-safe.
- **Fail-closed in the build.** A missing playwright/Chromium fails the build
  rather than skipping the gate — a silently skipped gate is the same as no
  gate ([Code Rules](../../../rules/CODE.md) → No Error Masking).
- **Guards prune, not filter.** `_guards_common.py` excludes `.venv` et al.
  by pruning `os.walk`'s `dirnames` in place, never descending into them —
  filtering AFTER an unpruned walk was measured at 2.3s+ against this
  project's `.venv` (tens of thousands of files), over the guard runner's
  ~2s budget; pruning brought the full run to ~0.3s.
