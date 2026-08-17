# Elevation — who we are, and who has the foreground

[← Server](../___server.md) · code: [elevation.py](../elevation.py)

## Why this exists

The injector's UIPI alarm used to end with a fixed parenthesis:

```
Injected input is being DISCARDED by Windows — commanded cursor jumps do not
land (UIPI: an elevated window or the lock screen has focus, and this process
is not elevated).
```

Every word after the dash was a hypothesis. Nothing under `server/` measured
any of it — not our own elevation, not the foreground window, not its
integrity level. The sentence printed identically whether we were elevated or
not, and whether anything had focus at all.

What a printed hypothesis does is exactly what happened: on 2026-08-16 that
line was read out of the owner's log and reported to him as the cause of a
failure it had nothing to do with. The real defect that evening was a dead
capture ([Capture Recovery](capture_recovery.md)); the alarm fired once, in the
same seconds, because a commanded cursor move genuinely failed to land — and
then explained itself with a cause it had never checked.

His ruling on 2026-08-17 settled it and it is general: a thing that does not do
what it says either starts doing it or goes away. This module is the "starts
doing it".

## What is measured

| Reading | How | Answers |
|---|---|---|
| Our own elevation | `shell32.IsUserAnAdmin()` | Is the "this process is not elevated" half true at all? The packaged app is manifested to require elevation (`build.py --uac-admin`, `VibeCoder.spec uac_admin=True`), so a `False` here is genuinely worth reporting — and used to be printed either way. |
| The foreground window | `GetForegroundWindow` + `GetWindowTextW` | WHICH window has the input focus. UIPI is decided by that window, so naming it separates "something stole your input" from "Task Manager did". |
| Its process | `QueryFullProcessImageNameW` | The name a person can act on. |
| Its integrity level | `OpenProcessToken` + `GetTokenInformation(TokenIntegrityLevel)` | The reading that actually settles UIPI: a HIGH or SYSTEM window above a non-elevated us is the documented case where Windows discards `SendInput` and still returns success. |

## What is deliberately NOT concluded

Every field is independently nullable and is rendered as unknown rather than
filled in with a plausible value.

- A process that refuses to open yields `integrity: None`. That is *consistent*
  with a more privileged process and is **not proof** of one, so `describe()`
  says so in those words instead of writing "high".
- No foreground window at all is not a failure — it is the secure desktop (a
  UAC prompt or the lock screen), which discards injected input by design, and
  that IS the answer.
- Exactly one conclusion is drawn anywhere, because exactly one is decidable
  from the readings: not elevated **and** a foreground at high/system is named
  as the UIPI case. Everything else is reported, not diagnosed.

## Where it is used

- [Input Injector](input_injector.md) — the alarm prints `describe()`.
- The use log's `state.app` record ([Session Log](session_log.md)) carries
  `snapshot()`, so a future report about dead input can be answered from the
  log instead of from a guess.

## Honest limits

- Windows-only. On any other platform every reading is `None` and `describe()`
  says the environment could not be measured.
- `integrity_of` reads the level at the moment it is called. A window that
  takes focus after the alarm fires is a different window; this is a snapshot
  of the failure, not a history of it.
- The module never raises. It runs inside an error path, where a diagnosis
  that throws replaces a wrong explanation with no explanation at all.

## A defect found by RUNNING it

The first version left the SID calls at ctypes' default `int` signatures.
`GetSidSubAuthorityCount` raised `ArgumentError: int too long to convert` on
the very first real call — a PSID is a pointer and does not fit an int on
64-bit Windows. Found by calling it against this desk, not by reading the
diff. The signatures are now declared explicitly, and the module's own
verification run reports `explorer.exe` at `medium`, our own elevated process
at `high`, and pid 4 (SYSTEM) as `None` — three different answers, which is
what proves the reading is real rather than constant.
