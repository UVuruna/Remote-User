# Notify

**Script:** [Notify (script)](../notify.py) ·
**Flow:** [diagram](../__flow/notify.md)

## Purpose

"The PC calls you" — ROADMAP Phase H (owner 2026-08-05). A job on this PC
finishes and the phone says **which one**:

> *"nije dovoljno samo da kaže beep kad završi agent … najbolje od svega je
> da izbaci notifikaciju koja opisuje koji agent je završio, a ime agenta je
> ime sesije u suštini"*

The owner runs several agents at once, so the AGENT's name is the message.
A sound alone carries no information when four of them are working.

`POST /notify?token=…` with `{agent, event, text}` → the phone gets a `notify`
frame → [Notify (client)](../../client/__about/notify.md) raises a real
Android notification, speaks it, and toasts if the page is visible.

## Three carriers, exactly one per notice (owner decree 2026-08-07)

His report: *"notifikacije mi stižu tek kada podignem aplikaciju iako je sve
vreme otvorena u pozadini"*. The cause was structural, not a bug in this file:
every notice rode the **streaming socket**, and that socket is closed on
purpose the moment the page hides (`docs/DECISIONS.md` constraint 8 — the
session lives only while the owner is looking). At the exact moment a notice
mattered there was no channel, so it was queued until he opened the app
himself. The queue had silently become the normal path.

His decision was a small foreground service on the phone holding a **second,
minimal** channel — *"android strana čeka signal, ne prima ništa od
kompjutera, ali ostane u stanju čekanja signala"* — and `deliver()` is the one
function that chooses between them:

| Order | Carrier | When | Result |
|-------|---------|------|--------|
| 1 | **the page** — `active_client["ws"]` | the app is open and he is looking | unchanged behaviour: banner + speech + toast |
| 2 | **the waiting channels** — `GET /notices` | the page is gone, one or more devices are holding the line | banner + speech on EVERY waiting device, from [NoticeService](../../android/__about/NoticeService.md) |
| 3 | **the queue** | neither: app killed, phone off, no network | held, and handed over the moment either channel returns |

**A double notice is impossible by construction**, not by a de-duplication
rule: `deliver()` is a chain of `return`s, so exactly one branch runs. A page
socket that dies between the check and the send is not an error and not a
queue — the phone has just hidden the page, its service is very probably
already waiting, so the notice falls through to carrier 2. Carrier 2 hands the
notice to every waiting DEVICE once (below): "never twice" is a rule about one
device's ear, and the same notice on his tablet and on his phone is the feature.

## One channel per device (task 209, his own log, 2026-08-11)

The waiting channel used to be a single SLOT, mirroring the web layer's
one-device rule — and that mirroring was the mistake. The streaming session
must be one device (two phones driving one mouse is nonsense); WAITING for news
drives nothing. He runs the foreground service on his tablet **and** his phone,
so each attach kicked the other's channel, the kicked one reconnected at once,
and his log carried an attach→kick→retry ping-pong every few seconds,
continuously, since 2026-08-09:

- thousands of log lines a night (192.168.0.30 ↔ .27 on LAN, 100.95.132.34 via
  Tailscale), and both radios woken for nothing;
- and the half he actually felt: a notice reached only whichever device held
  the slot that second, while the other learned about it minutes or hours later
  out of the queue — *"notifications sometimes never arrive"*.

`_waiting` is therefore a dict keyed by a **device id** the shell supplies:

```
GET /notices?token=…&device=<per-install UUID>
```

| Case | What happens |
|------|--------------|
| two devices waiting | the notice goes to both, once each — per-device de-duplication is structural, since a device has exactly one channel |
| a second attach with the SAME id | that device's own older channel is ended (its service restarted); no other device is touched |
| **no `device` parameter** | an APK older than this round: it shares the LEGACY key, so two old shells still fight over one slot — exactly the behaviour they were built against. Nothing about an old phone changes when this PC updates |
| more than `MAX_DEVICES` (8) | the oldest channel gives way, and it is said in the log. Not a policy — a stop against a shell whose id changed on every attach |

`device_key()` trims, caps at 64 and keeps only characters safe to print in a
log line; anything else falls back to the legacy slot.

**The honest limit:** the queue is drained by whichever device attaches while
it is non-empty, and draining is destructive. A notice held while BOTH devices
were unreachable reaches the first one back, not both. That is the pre-existing
behaviour of the last-resort store and it is deliberately unchanged here — the
queue is the path taken when nothing is reachable, and the round's fix is that
it is now almost never taken at all.

**`close_channels()`** (task 234): ends every waiting response NOW, from any
thread — `ServerController.stop()`'s exit funnel calls it because `force_exit`
stops uvicorn from accepting work while an endless generator parked on its
queue is an open connection the shutdown drain still waits on: every Apply &
restart used to stall the full 10 s join and abandon the old thread. It feeds
the SAME `None` sentinel a displaced channel receives, via
`call_soon_threadsafe` on the loop captured at attach time, so each generator
returns through its own normal exit. Gated in `tests/test_notice_channel.py`
(the 234 check, planted-defect proven).

## `GET /notices` — the waiting channel

A response that never ends. The phone opens it once and blocks on a read; the
PC writes to it:

- **one bare newline every `BEAT_S` (60 s)** — the beat. It travels PC → phone
  only, and it buys exactly two things: keeping the router's / carrier's NAT
  mapping for this TCP connection alive (the tightest common idle timeout is
  60 s), and letting either side notice a link that died silently. A write
  that fails is a phone that is gone; the phone reconnects after `BEAT_MISS`
  (3) missed beats. Without it, a dead link would swallow notices while both
  ends believed they were connected.
- **one JSON line per notice** — byte-for-byte the frame the page would have
  received, so the owner cannot tell which carrier brought it.

Plain chunked HTTP rather than a WebSocket, because the Android shell already
speaks `HttpURLConnection` (it probes `/ping` with it): the waiting state costs
the APK no new dependency and no handshake.

## Why a waiting channel can never be mistaken for a present phone

This is the rule, and it is structural:

> **`_page` is written by `register()` and by nothing else in this module.**
> The `/notices` route only ever READS it.

`_wait_for_news()` can reach the notice queue and nothing else. It never
touches the one-device slot, so `stats.clients` stays 0, no traffic session
opens, `presence.watchdog` and `focus_guard.watch` are never armed, and the
layout registry, the capture, the encoder and the injector are not even in
scope. A waiting phone is a phone that is **NOT here** — which is what keeps
the topmost ledger, the presence/away protocol and the layout defence working
exactly as before. Proven by
[tests/test_notice_channel.py](../../tests/___tests.md).

One channel per DEVICE since task 209 (above): a second attach displaces only
the channel of the device it came from.

## HOW it is said: two switches here, the voice on the phone

Round R2 (owner 2026-08-07) put all three values on the desktop. On 2026-08-12
the owner took two of them back to the device: he uses a tablet AND a phone,
their TextToSpeech engines carry different voices, and one PC-side dropdown
could only ever name a voice that exists on one of them — pick the tablet's
and the phone falls silently back to its own default while the Settings window
still shows a name. The card keeps the two MASTER switches, which are
decisions about the JOB rather than about a handset.

**Nothing on the wire changed.** All three fields still ride
on **every** `notify` frame rather than being pushed to the phone once — there
is then no state on the phone to go stale, and a reconnect cannot leave it
speaking in last week's voice:

| Frame field | From | Meaning |
|-------------|------|---------|
| `speak` | the caller's own `speak`, **and** `SETTINGS.notify_speak` | "Say it out loud" off sends `false` and nothing more: the Android banner still appears, so muting one carrier never loses a notice |
| `voice` | `SETTINGS.notify_voice` | a `Voice.name`. Since 2026-08-12 it is the FALLBACK: a phone with its own choice ignores it, a phone that has never chosen still obeys it, so no device changed behaviour when the dropdown moved. No UI writes it any more |
| `rate` | `SETTINGS.notify_rate` | TextToSpeech's speech rate (1.0 = the engine's normal pace). Same fallback rule, and falls back INDEPENDENTLY of `voice` |

**The list of voices can only come from the phone.** A TextToSpeech engine's
voices differ per device, per installed language pack, per Android version, and
the PC can see none of it — so the page sends `tts_info {voices:[{name, label,
locale}…]}` once per connection and `set_voices()` holds it HERE, in memory. It
is never persisted: a list read from a phone that is no longer connected
describes nothing currently true. That per-device truth is exactly why the
choice itself belongs on the device.

Since 2026-08-12 **nothing on the desktop chooses from this list** — it is the
PC's diagnostic record of what the connected device could speak with (the log
line in `set_voices`). The phone's own card is
[client/notify.js](../../client/__about/notify.md) → `openNotifyVoicePanel()`,
where every voice can also be HEARD before it is picked.

## Where the tap leads (owner 2026-08-08, task 110)

*"da klikom na notifikaciju nas odvede do tog layouta … gde je zavrsio taj
sabagent ili glavni agent."* A notice that names an agent but leaves him to
find the window is half the job — he has to step the layout bar looking for
it.

Nothing here is inferred. The finishing agent reports its own `cwd`
(`setup/agent_hook.py` → `agent_project`), and every layout can be asked which
project its windows really belong to (`window_manager.Layout.project`).
`layout_of(project, title)` matches the two and returns `{index, name}`, which
rides the notice as `layout`.

### The conversation TITLE, not just the project (owner ruling 2026-08-13)

*"da notifikacije bira layout u cijem se kreirao"* — the notice must land in
the layout the conversation was really created in. His report: with several
windows of ONE project spread across layouts, the tap always took him to the
⭐ PARENT layout instead of the window the agent actually finished in. The ⭐
was never involved — `layout_of` had no tie-break at all, and simply returned
the FIRST layout in list order whose project matched; the parent happens to
sit at the lowest index because it exists before anything is torn off it.

The hook already reads the conversation's own title off the transcript's
`ai-title` record to NAME the agent (task 198, `agent_hook.transcript_title`).
`agent_hook.send()` now rides that SAME string a second time, unabbreviated,
as its own `title` field — separate from `agent`, which may be the same title
already cut to 60 characters for the banner, or, when no title exists yet,
something else entirely (an explicit name, a project·session fallback) that
names no window at all.

`layout_of` tries the title FIRST: `_layout_by_title` walks every layout's
live member titles (the same `wm._title(h) for h in lay.members` reading
`layout_state` already sends the phone) and looks for the one that is really
this conversation. A VS Code window's title is the conversation title PLUS
VS Code's own furniture (`" - <folder> - Visual Studio Code[ tail]"`), and
VS Code elides a title too long for its tab with a trailing "…" — so the
comparison (`_title_matches`) strips the tail, then requires either an exact
match or, when the window's own copy ends in that ellipsis, a strict
`startswith` (the window's copy is a truncated PREFIX of the real title,
never a fuzzy neighbour of it — two different elided titles must never
collide). Only when nothing matches confidently does it fall through to
today's project-folder search — the loop this feature had all along, and
exactly what an OLDER hook (no `title` field, so `layout_of` receives `""`)
still gets, unchanged.

Three details, each of which would be a bug without it:

- It **prunes first**, because the index it returns is the one the PHONE is
  holding, and `layout_state` numbers its list after the same prune. One dead
  layout still in the list and the tap lands one window off.
- It sends the **name beside the index**, so the phone can check the index
  still points at what we meant. A layout removed between the notice and the
  thumb slides every higher index down.
- The field is **absent** whenever that project is on no layout. A tap that
  cannot land must not be offered.

Resolved at SEND time, not at tap time: this is the one moment the agent told
us its project, and it costs one cheap Win32 read per layout, off the loop.

### Task 236 — his THIRD report, and the two halves that made it possible

*"still takes me to the previously open layout."* Two rounds closed this with
green gates. Both halves are fixed here and in `client/notify.js`.

**A miss was SILENT.** Only the SUCCESS path wrote a log line, so a notice
that shipped with no `layout` field looked in his log exactly like one that
carried it — there was no way to tell which half had failed, and the app was
the last to know. `layout_of` now logs at **INFO** on every miss, naming the
project it looked for and every project each live layout really holds
(`Layout.projects()`).

**`Layout.project()` could not reach the agent's window.** It asked
`members[0]` and the window THAT member was torn out of, and nothing else. His
Claude layout is a GRID: the agent's window is as often cell 2 as cell 0, and a
torn-off Claude tab is titled after the CONVERSATION — never after the folder.
So a match that was structurally impossible reported as an honest "that project
is on no layout". Every member is asked now, each followed by its own source,
authority-first. The gate builds exactly that layout (a Chrome cell 0, a
torn-off conversation cell 1) instead of stubbing `project()` away, which is
what let the previous rounds pass while the real function could not answer.

## Why a push, not a watcher

The alternative was reading the screen (UIA on the Claude panel, or watching
pixels for a spinner). It was rejected on the merits, not on effort:

- a long silent build looks **identical** to a finished one on screen;
- nothing on screen can tell four agents apart;
- every editor/agent version would move the thing being read.

Whatever finishes already KNOWS it finished, so it tells us. That also makes
the feature general: any tool that can run a command on completion — a build,
a test suite, a render — gets the same notification for free.
[setup/agent_hook.py](../../setup/___setup.md) is the Claude Code `Stop` hook
that does it.

## Connections

### Uses
- the web layer's own one-device slot (`active_client`) — this module keeps
  no second registry, so the phone that took the session over (code 4409) is
  the one that hears about it. **Read only**, which is what keeps a waiting
  channel from ever looking like a present phone.

### Used by
- [Web Layer](web.md) — `notify.register(app, token, active_client)` inside
  `create_app`. Nothing else in `web.py` knows the waiting channel exists;
  the route was added here, in the feature's own module, and `web.py` was not
  touched (it stands at exactly 1,000 lines).
- [setup/agent_hook.py](../../setup/___setup.md) — the Stop hook that POSTs
- [NoticeLink (Android)](../../android/__about/NoticeLink.md) — the phone's
  end of `GET /notices`; the beat interval is a shared rule between them
- [tests/test_notify.py](../../tests/___tests.md) and
  [tests/test_notice_channel.py](../../tests/___tests.md) — the gates
- `gui/settings_window.py` (see [GUI (subfolder)](../gui/___gui.md)) — the
  agent-hook switch and the two master switches. It no longer reads
  `voices()`: the Voice dropdown moved to the phone on 2026-08-12

## Functions

- `layout_of(project, title="") -> {index, name} | None` — where a finished
  agent's project (or, first, its exact conversation) is showing. Title match
  first (`_layout_by_title` / `_title_matches` / `_vscode_conversation_part`),
  project-folder loop as the fallback an older hook still gets.
- `set_voices(reported) -> int` / `voices() -> list` — the phone's own
  text-to-speech voices, held for this run only. Anything unusable in the
  reported list is dropped rather than trusted: a name that reaches the log
  must be a real one. Diagnostic since 2026-08-12 — no desktop UI reads it.
- `clean(value, limit, fallback)` — one incoming field: string, trimmed,
  length-capped. Nothing from a POST body reaches a notification unclamped.
- `compose(agent, event, text) -> (title, body)` — the AGENT leads, the event
  is the verb (`EVENT_WORDS`: finished / needs you / failed), free text is the
  second line. An unknown event is shown as-is rather than swallowed.
- `deliver(notice) -> "page" | "waiting" | "held"` — the carrier decision, and
  the reason a notice can never arrive twice ON ONE DEVICE. The `waiting`
  branch fans out to every waiting device, once each.
- `waiting() -> bool` — whether ANY device is holding a channel open.
- `waiting_devices() -> int` — how many are. The whole point of task 209 is
  that this can be 2.
- `device_key(value) -> str` — the id as we are willing to keep it: trimmed,
  capped at 64, log-safe characters only; anything else is the LEGACY slot,
  which is what an APK that sends no id already lands on.
- `queue(notice)` / `drain(now)` — the last-resort store: `QUEUE_TTL_S` 30 min,
  `QUEUE_MAX` 20, each notice carrying the time it happened so the phone can
  say "8 min ago" instead of pretending it just landed.
- `send_pending(ws)` — what was held, on a page's return. Normally empty since
  2026-08-07, and that is the fix rather than a regression.
- `register(app, token, active_client)` — adds `POST /notify` and
  `GET /notices` (whose optional `device` parameter keys the channels), and
  hands this module the web layer's one-device slot.

## Design Decisions

- **The queue is the LAST resort, not the path.** It was added on 2026-08-06
  (two agents finished while he was on a call with the app closed and both
  notices were discarded) and it kept its numbers unchanged on 2026-08-07 —
  what changed is that it is now only reached when the phone has no live
  channel of either kind. Reaching it means the phone is genuinely
  unreachable, which is what it was always meant to mean.
- **The token is the same one the phone uses.** No token, no answer — a
  notification endpoint that anyone on the LAN could ring is a way to make
  the owner's phone buzz at will.
- **Its own module, not another branch in `web.py`.** One responsibility with
  its own route and its own gate; `web.py` is the busiest file in the project
  and was being split for exactly this reason on the same day.

## The switch that turns it on (ROADMAP H2, owner 2026-08-06)

The feature shipped working in v0.0.081 and then stayed silent on the owner's
own PC for a day: `agent_hook.py --install` had never been run. The rule is
that an end user never types a command, so the desktop window carries a
checkbox and `agent_hook_installed()` / `set_agent_hook()` are what it
operates. They live here rather than in the GUI because this is the
notification feature's module — the window only owns the checkbox.

The switch shows the REAL state (it reads `~/.claude/settings.json` every
time) instead of remembering a setting of its own, so a hook removed by hand
is reflected the next time the window opens.

Two things the packaged app must handle and a dev checkout need not:

- **the script would vanish with the next update** — inside the bundle it is
  replaced wholesale, so turning the switch on copies it to the user directory
  and registers that permanent path;
- **there is no interpreter in the EXE** — `sys.executable` is the app itself,
  so a real `python` is looked up on PATH. A PC with none is TOLD so, plainly,
  in the caption under the switch. A switch that silently fails to arm is the
  same failure this whole task exists to end.

**And the script has to BE in the bundle** (owner screenshot 2026-08-06):
v0.0.085 shipped without it — `setup/agent_hook.py` was never in PyInstaller's
`--add-data` — so the installed app could not turn the switch on at all and
answered with `[Errno 2] No such file or directory: …\_internal\setup\
agent_hook.py`. Fixed at all three layers, because each failed on its own:
the file is bundled ([Build](../../setup/__about/build.md)), the build's
**payload gate** refuses to package without it, and `_hook_module()` no longer
hands a raw path to a user — a missing script is the APP being broken, so the
sentence says that, and the log keeps the path.

### Every sentence this switch can print is named, and NONE of them is `str(e)` (round R2's SECOND independent grader, 2026-08-07)

The fix above closed the ONE path that used to leak — `_hook_module()`'s own
missing-script check — but `set_agent_hook()` still had two UNGUARDED steps
downstream of it: `shutil.copyfile()` (copying the script to `USER_DIR` on a
frozen build) and `module.install(...)` (writing `~/.claude/settings.json`).
Either one raising a bare `OSError` — a locked file, a full disk, a
permissions error — flowed straight through to `gui/settings_window.py`'s
`except OSError as e: ... str(e)`, which is exactly how a raw exception's own
repr became the caption's text on the owner's screen: the SAME class of bug
`_hook_module()` had already been fixed for, one function down. The whole
body of `set_agent_hook()` (after `_hook_module()` itself, which is the only
thing still allowed to raise — always with a message written for a human) is
now inside one `try/except OSError`, and every sentence it can return is a
named constant instead of a call-site literal:

| Constant | Shown when |
|----------|-----------|
| `MISSING_SCRIPT_TEXT` | `_hook_module()` — the bundled script is genuinely absent |
| `UNLOADABLE_SCRIPT_TEXT` | `_hook_module()` — found, but `importlib` could not load it |
| `NO_PYTHON_TEXT` | frozen build, no `python`/`py` on PATH |
| `HOOK_CHANGE_FAILED_TEXT` | anything else raising `OSError` (copy, or the settings-file write inside `agent_hook.install()`) |

`gui/settings_window.py` also gives the caption the theme's semantic **Error**
colour when — and only when — it is showing one of these, instead of the
routine caption grey every other sentence in that window uses; the fixture in
`tests/test_layout_audit_qt.py` that used to hardcode the OLD raw exception
text as its "worst case" caption now imports `NO_PYTHON_TEXT` (the longest
sentence this module can produce today, 125 chars) so the audit can never
drift back to sizing the window for text the product no longer emits.

## One notice, one use-log record (T113, 2026-08-17)

`deliver()` is now a thin wrapper over `_carry()`, which holds the unchanged
three-carrier chain of returns. The wrapper exists for one reason: the use
log's `notice.<carrier>` record is written THERE and nowhere else. A record at
each of `_carry`'s three returns would be three copies of one fact, and three
copies drift — the same rule the carrier chain itself is built on.

The record carries the agent, the event, `waited_s` (measured from the
notice's own `at` stamp) and `waited` — whether it had really been held for a
later connection rather than landing the second it was raised, which is the
exact distinction the phone's own "8 min ago" suffix exists for. A second of
slack keeps an ordinary round trip from being reported as a wait.

Never raises. Gate: `tests/test_log_wiring.py` (0b24/6).
