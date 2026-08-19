# Notify

**Script:** [Notify (script)](../notify.py) ·
**Flow:** [diagram](../__flow/notify.md)

## Purpose

**Split 2026-08-18 (THE STRUCTURE LAW, VC-R4).** This module is now the NOTICE
ITSELF — its fields, its clamps, what the banner shows and what the voice says
— plus the two routes that put it on the wire. Three neighbours own the rest:

- [Notice Channel](notice_channel.md) — HOW it travels (page socket, waiting
  channels, the held queue, `deliver()`'s one-carrier rule)
- [Notify Layout](notify_layout.md) — WHERE it happened (`layout_of`)
- [Agent Hook Switch](agent_hook_switch.md) — what makes it fire at all

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
  is the verb (`EVENT_WORDS`: finished / needs you / failed / is asking you /
  has a dialog waiting), free text is the second line. An unknown event is
  shown as-is rather than swallowed.
- `make_notice(agent, event, text, speak_text, speak=True, where=None) -> dict`
  — THE ONE `notify` frame builder (2026-08-19): the `/notify` route feeds it
  an agent's hook, [Dialog Center](dialog_center.md) feeds it a dialog waiting
  in a layout the phone is not showing; `where` is the `{index, name}` jump.
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

