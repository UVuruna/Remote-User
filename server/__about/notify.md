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
purpose the moment the page hides (project CLAUDE.md constraint 8 — the
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
| 2 | **the waiting channel** — `GET /notices` | the page is gone, the service is holding the line | banner + speech, from [NoticeService](../../android/__about/NoticeService.md) |
| 3 | **the queue** | neither: app killed, phone off, no network | held, and handed over the moment either channel returns |

**A double notice is impossible by construction**, not by a de-duplication
rule: `deliver()` is a chain of `return`s, so exactly one branch runs. A page
socket that dies between the check and the send is not an error and not a
queue — the phone has just hidden the page, its service is very probably
already waiting, so the notice falls through to carrier 2.

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

One waiting phone at a time, mirroring the web layer's own one-device rule: a
second attach displaces the first rather than doubling every notice.

## HOW it is said is the desktop's decision (round R2, owner 2026-08-07)

The Settings window's NOTIFICATIONS card owns three values, and all three ride
on **every** `notify` frame rather than being pushed to the phone once — there
is then no state on the phone to go stale, and a reconnect cannot leave it
speaking in last week's voice:

| Frame field | From | Meaning |
|-------------|------|---------|
| `speak` | the caller's own `speak`, **and** `SETTINGS.notify_speak` | "Say it out loud" off sends `false` and nothing more: the Android banner still appears, so muting one carrier never loses a notice |
| `voice` | `SETTINGS.notify_voice` | a `Voice.name` exactly as this phone reported it; a device that does not have it falls back to its own default |
| `rate` | `SETTINGS.notify_rate` | TextToSpeech's speech rate (1.0 = the engine's normal pace) |

**The list of voices can only come from the phone.** A TextToSpeech engine's
voices differ per device, per installed language pack, per Android version, and
the PC can see none of it — so the page sends `tts_info {voices:[{name, label,
locale}…]}` once per connection and `set_voices()` holds it HERE, in memory,
beside the feature that uses it. It is never persisted: a list read from a
phone that is no longer connected would offer the owner voices he cannot hear.
The stored CHOICE is a plain name, never an index, for the same reason.

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
  agent-hook switch, and `voices()` for the Voice dropdown

## Functions

- `set_voices(reported) -> int` / `voices() -> list` — the phone's own
  text-to-speech voices, held for this run only. Anything unusable in the
  reported list is dropped rather than trusted: it is drawn in a dropdown on
  the PC.
- `clean(value, limit, fallback)` — one incoming field: string, trimmed,
  length-capped. Nothing from a POST body reaches a notification unclamped.
- `compose(agent, event, text) -> (title, body)` — the AGENT leads, the event
  is the verb (`EVENT_WORDS`: finished / needs you / failed), free text is the
  second line. An unknown event is shown as-is rather than swallowed.
- `deliver(notice) -> "page" | "waiting" | "held"` — the carrier decision, and
  the reason a notice can never arrive twice.
- `waiting() -> bool` — whether a phone is holding the waiting channel open.
- `queue(notice)` / `drain(now)` — the last-resort store: `QUEUE_TTL_S` 30 min,
  `QUEUE_MAX` 20, each notice carrying the time it happened so the phone can
  say "8 min ago" instead of pretending it just landed.
- `send_pending(ws)` — what was held, on a page's return. Normally empty since
  2026-08-07, and that is the fix rather than a regression.
- `register(app, token, active_client)` — adds `POST /notify` and
  `GET /notices`, and hands this module the web layer's one-device slot.

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
