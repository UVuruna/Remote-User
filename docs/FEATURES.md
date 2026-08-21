# Features

What Vibe Coder does, told for the person holding the phone. This document is
the product's feature catalogue — README-level: the first place a future user
(or a session working on the code) looks to learn what exists. Every feature
carries a slug in backticks; a session task tags the feature it serves with
`#slug`, and the desktop [Work history](#work-tracking) links the two
together, both ways.

- [Remote Screen & Input](#remote-screen-input)
- [Control Sets & Wheel](#control-sets-wheel)
- [Layouts](#layouts-group)
- [Work Tracking (TASKS)](#work-tracking)
- [AI Agent Companion](#agent-companion)
- [Voice & Dictation](#voice-dictation)
- [Content Exchange](#content-exchange)
- [Pairing, Security & Remote Access](#pairing-security)
- [Desktop App & Updates](#desktop-updates)

<a id="remote-screen-input"></a>

## Remote Screen & Input

The primitive loop everything else stands on: see the PC, drive the PC.

### Live screen · `screen-streaming`

The PC's screen, live on the phone: H.264 hardware-encoded (NVENC → QuickSync
→ AMF, libx264 fallback) as fragmented MP4 the browser decodes natively, with
JPEG-per-frame as the no-ffmpeg fallback. One monitor per view with an
explicit switch, per-device quality overrides, pinch-zoom with the server
raising resolution so the zoomed picture stays sharp. The picture never goes
blank — a starved player recovers by itself.

### Touch input · `touch-input`

The finger only steers the cursor — nothing is a tap. Clicks are explicit
buttons, and held corner buttons change what the finger does (right-click,
drag, scroll). The phone's native soft keyboard types into whatever is
focused on the PC — full Unicode, emoji included — while the picture rises
only as much as the typing caret needs.

### Game controller · `gamepad`

A Bluetooth controller mapped onto the same controls the finger uses — stick
curve for the cursor, buttons through the same activator, the category wheel
held-and-pointed. Coding from the couch, thumbing a controller.

<a id="control-sets-wheel"></a>

## Control Sets & Wheel

Talking to the PC through per-app command sets — built for touch and gamepad
alike.

### Control sets · `control-sets`

Named sets of commands (`actions.json`) — per application: VS Code, browser,
media, Claude tools… The right sets ride along automatically: the owner ticks
which sets belong to which layout, and at most 8 ride the wheel at once.

### Category wheel & D-pads · `category-wheel`

The wheel opens from a group's centre button, a row acts on the LIFTED
finger, and the D-pad groups keep the everyday commands one thumb away — the
whole surface built so touch and gamepad share one muscle memory.

### Set editing · `set-editing`

The same set is editable in both places — on the phone (Settings → Wheel
sets) and in the desktop Controls editor — both saving into the same
`actions.json`.

<a id="layouts-group"></a>

## Layouts

The app-aware layer that makes this a companion, not a remote desktop.

### Window layouts · `layouts`

Real PC windows arranged into named grids (six shapes plus solo, fourteen
with orientations), listed in a bar on the phone. Everything is measured from
the desktop, never remembered — what the phone shows is what the PC really
holds. Nothing forced on a window outlives the app.

### Layout life · `layout-lifecycle`

Creating a layout (choose sources, arm a slot, done), changing one (rename,
aspect ratio, orientation, arrangement), the chip that asks where a freshly
opened window should go, recovering lost windows, and opening new programs
straight from the phone.

<a id="work-tracking"></a>

## Work Tracking (TASKS)

Its own feature, deliberately agent-agnostic: the mechanic lives in OUR
implementation — a plain-Markdown ledger file and a parser — not in any
assistant's plugin system. Today Claude Code writes it; any assistant that
can be given the same file contract (Codex, Cursor, …) plugs into the same
tracking unchanged.

### Session tasks · `session-tasks`

Every working session keeps a ledger: tasks with five states (not started, in
progress, waiting for you, done-unproven, done WITH evidence), a description,
a question when one waits on you, and the evidence line that earns green.
Each task can carry who works it (`@model`), which feature it serves
(`#slug` — an entry of this very document) and a 1–5 star complexity. The
phone shows the focused project's ledger live, and a question is answered
straight from the phone.

### Work history · `work-history`

The whole history on the desktop: every project, grouped by day and session,
every task with its state, stars and feature — served by the PC as a live
HTML page (loopback-only) with filters for project, state, category, feature
and complexity. Task tags link into this catalogue and each feature links
back to the tasks that built it. Rendered fresh from the ledger files on
every open — nothing stored twice, nothing stale.

<a id="agent-companion"></a>

## AI Agent Companion

Living with a coding agent on the PC while holding only the phone. Claude
Code today; the surface is built to grow toward other popular assistants.

### Agent control cards · `claude-cards`

Model, Thinking and Mode cards showing the PC's Claude Code state live —
never guessing, never showing a remembered value as a live one — plus slash
commands from the phone's Claude set.

### Finished-work notifications · `agent-notifications`

Anything on the PC that finishes a job can call one endpoint, and the phone
raises a real notification naming the agent — spoken aloud if wanted. A tap
lands in the layout showing that agent's project.

<a id="voice-dictation"></a>

## Voice & Dictation

### Dictation · `dictation`

Speak instead of type: text lands as you speak, never types a re-heard tail
twice, languages grouped language-first (one row for a language, its variants
inside). Built for dictating instructions to an agent as much as for any text
box.

### Spoken notices · `tts-notices`

The PC's notices read aloud on the phone in the language and voice chosen per
device.

<a id="content-exchange"></a>

## Content Exchange

### Clipboard sync · `clipboard-sync`

What is copied on the PC lands in the phone's clipboard.

### Attach & upload · `attach-upload`

Phone → PC: photos and files uploaded and pasted where the PC's focus is.

### Region grab · `region-grab`

A frame the finger sizes over the live picture, captured on the PC and pasted
— point at the thing instead of describing it.

<a id="pairing-security"></a>

## Pairing, Security & Remote Access

### QR pairing · `pairing`

Scan the QR the PC shows, done. A pairing token gates everything — the
server injects NOTHING before a valid token arrives, and no port is ever
opened to the public internet.

### Anywhere access · `remote-access`

Away from home, both devices join a private Tailscale mesh — end-to-end
encrypted, no forwarded ports, no third-party relay ever seeing the screen.
The same QR works at home and away.

### Watching is the session · `watch-gated-session`

The PC is controllable only while the page is actually on screen —
backgrounding the app or locking the phone pauses control instantly.

<a id="desktop-updates"></a>

## Desktop App & Updates

### Desktop app · `desktop-app`

A windowed PC app living in the tray: the pairing QR, server start/stop,
settings, the Controls editor, traffic monitoring and the Work history — the
server keeps running when the window closes.

### Self-updating pair · `updates`

Updates flow downhill: GitHub Releases → the PC updates itself → the PC
offers the phone the matching APK in-app, with honest progress. A loaded page
that outlives its server's version reloads itself.
