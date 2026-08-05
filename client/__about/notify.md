# Notify (client)

**Script:** [notify.js](../notify.js)

## Purpose

The phone half of "the PC calls you" (ROADMAP Phase H, owner 2026-08-05).
`connection.js` hands it every `notify` frame; it delivers the notice three
ways, strongest first — because the situation this feature exists for is the
one where the owner is **not** looking at the phone:

| Carrier | Reaches him when | Bridge |
|---------|------------------|--------|
| Android notification | the app is backgrounded, the screen is off | `Android.notify(title, text, tag)` |
| Spoken aloud | his eyes and hands are on the PC | `Android.speak(text)` |
| Toast + tone | he is looking at the page | in-page |

The **tag is the agent's name**, so a second notice from the same agent
replaces its own notification line while four agents keep four lines. That is
the owner's requirement in one detail: *"da izbaci notifikaciju koja opisuje
koji agent je završio"*.

## Per-device switches

`notifyPrefs()` / `saveNotifyPrefs()` in the shell's SharedPreferences (via
`prefGet`/`prefSet` — never bare localStorage, which splits per origin
between the LAN and Tailscale addresses):

- `banner` — the Android notification (default ON)
- `speak` — TextToSpeech (default ON)
- `tone` — the in-page chime (default **OFF**: it is the one that annoys when
  the phone sits on the desk beside the PC)

## Connections

### Uses
- [Controls](controls.md) — `showToast`, `prefGet`/`prefSet`, `send` (the
  `client_log` diagnostics channel)
- the shell's bridge — `Android.notify` / `Android.speak`
  ([Android (folder)](../../android/___android.md), `Notifier.kt`)

### Used by
- [Connection](connection.md) — `msg.type === "notify"` → `handleNotify(msg)`
- [Notify (server)](../../server/__about/notify.md) — the frame's author

## Design Decisions

- **The tone is synthesised, not shipped.** Two sine notes through
  `AudioContext`: no file to fetch, no decoder, and the page has long had the
  user gesture autoplay policy asks for.
- **Every carrier fails alone.** A throwing tone, a refused notification
  permission and a missing TTS engine each land one `client_log` line in the
  PC's server log and leave the other two paths working. The owner never gets
  a panel about it — diagnostics go to the log, per his 2026-08-05 rule.
- **Nothing is stored or replayed.** A notice that arrives while no phone is
  connected is dropped by the server; the page never keeps a history to
  re-show, because a stale alarm is worse than none.
