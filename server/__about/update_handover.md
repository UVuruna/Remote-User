# Update Handover

**Script:** [Update Handover (script)](../update_handover.py)

## Purpose

Installing a new version WITHOUT losing the session you are installing from.

The owner's report (2026-08-07): *"dešava se da ja ne mogu da instaliram novu verziju ako nisam kući, zato što čim uđem u instalaciju on će meni ugasiti Remote User i više neću moći da komandujem odavde."* Every fix this project ships reaches him only through an install, and starting the install killed the remote session he was installing FROM — so a man away from home sat on an old build unable to take the new one. The trap ate itself.

He asked for "quit later". This module builds the stronger requirement, because "later" still leaves him holding a phone in front of a Next button he cannot press: **after one tap on the window's Update button, nothing more is needed from anybody, and control comes back by itself.**

And exactly ONE handover may be live at a time (owner 2026-08-09 — the updater installed his app more than twenty times in one night). Nothing used to stop a SECOND script being armed while the first still ran: every armed script survives the process on purpose, each ran the installer and started an app, every started app checked GitHub within seconds, and with six releases published in four hours each fresh app found a newer version to arm again — one script became two became four, and his update.log printed "--- handover finished ---" dozens of times in one second (every waiting script's "did it come up?" probe is satisfied by ANY instance of the image name). The ARMING LOCK cuts the fork at the one choke point every arm must pass; its twin guard, one GUI instance per PC, lives in [gui_main](gui_main.md).

The responsibility is the HANDOVER, not the discovery: [Updates](updates.md) still answers "is there a newer release?", and [gui/main_window.py](../gui/__about/main_window.md) still owns the button and the download. What lives here is everything from "the installer is on disk" to "the phone is talking to the new version".

## Connections

### Uses
- [Config](config.md) — `update_record_path`, `update_script_path`, `update_log_path`, `update_wait_exit_s`, `update_wait_up_s`, `notify_speak` / `notify_voice` / `notify_rate`, `app_version()`
- [Updates](updates.md) — `numbers()`, to compare the version now running against the one that was installed
- [Notify](notify.md) — `deliver()` for the warning before the app goes, `queue()` for the verdict on the next start
- `cmd.exe` — the handover script itself; the only executor guaranteed present on a Windows PC that can outlive this process

### Used by
- `gui/main_window.py` (see [GUI (subfolder)](../gui/___gui.md)) — `_begin_handover()` on the Update button's "ready" state
- [Server Core](server_core.md) — `announce()` in `ServerController.__init__`, and `controller.loop` is what `tell_phone()` speaks through
- [Setup (folder)](../../setup/___setup.md) — `installer.nsi` honours the `/S` this module passes; `build.py` runs the gate

## Functions

- `verify(path, expected_size)`: `""` when the download is a complete Windows program, otherwise a sentence for the log. Checks, in order: it exists; its size matches what GitHub declared for the asset; it is not absurdly small (`MIN_INSTALLER_BYTES`); it starts with `MZ`.
- `elevated()`: whether this process can start an admin-manifested installer with no UAC prompt. Always true in the packaged app (`--uac-admin`); the false branch exists for a dev checkout.
- `tell_phone(controller, version)`: the last message before the screen goes dark, through `notify.deliver` — so it takes the open page or the waiting channel, whichever is alive. Returns whether it landed; a phone that has gone quiet never vetoes an update.
- `hand_over(installer, version, exe=None)`: takes the arming lock atomically (raises `OSError` when a handover is already live — the fork guard), then writes `SCRIPT`, writes the record, spawns the script detached, and re-stamps the lock with the script's own `cmd.exe` pid. An arm that fails after taking the lock releases it — a lock with no script behind it must not cost him the next try. `exe` defaults to `sys.executable` — under PyInstaller exactly the path the installer replaces and exactly the path the script restarts. Nothing here guesses an install directory.
- `begin(controller, installer, version, expected_size)`: the whole sequence. Returns `("quit", "")` / `("manual", text)` / `("stop", text)`. Consults `live_handover()` BEFORE `tell_phone` — a refused arm must never announce "Installing vX" for an install that will not run, and the refusal names the live script's pid in the log.
- `live_handover()`: the pid of a handover genuinely running right now, else `None`. Garbage, a dead pid and old age all read as `None` — every one of those is a lock to reclaim, never a reason to refuse updates forever.
- `announce()`: called once per process start. If the previous run handed this PC over, queue the verdict for the phone's next connection — success or failure, both equally loud. Returns the queued title, `""` when there was nothing to report.
- `_write_record` / `_read_record` / `_spawn`: the three seams (disk, disk, process creation).
- `_lock_path` / `_pid_alive` / `_acquire_lock` / `_stamp_lock` / `_release_lock`: the arming lock's own seams. The lock file (`handover.lock`, `{pid, at}`) lives beside the script it guards — derived from `update_script_path.parent`, so wherever the script is told to live (USER_DIR in production, a temp folder in the gate), the lock is already beside it. `_pid_alive` is Windows-honest: a pid that exists but refuses to open counts as ALIVE (refusing an arm is recoverable; forking again is the bug), and an open handle is asked for its exit code, because `OpenProcess` also succeeds on a process that exited while somebody still holds a handle to it.

## Constants

- `MIN_INSTALLER_BYTES = 5_000_000` — a floor no captive-portal login page, HTML error body or zero-length file can reach.
- `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP` — the spawn flags. **`DETACHED_PROCESS` was the first attempt and it is wrong**: with no console at all, `tasklist` returns nothing, so both of the script's questions answered "yes" instantly and falsely. Caught by the gate, not by reasoning.
- `TELL_TIMEOUT_S = 3.0` — how long the update waits for the phone to be told.
- `LOCK_STALE_S = 15 * 60` — a handover still "live" after this long is a lie: far past `update_wait_exit_s` (30) + the silent install + `update_wait_up_s` (40) + antivirus first-touch slack. Age outranks even a live pid, because Windows recycles pids and a stranger's process must not hold the door shut.
- `ALREADY_ARMED_TEXT` — the fourth button sentence, worn when a second arm is refused.
- `SCRIPT` — the handover script, constant ASCII text (see [flow](../__flow/update_handover.md)).

## Design Decisions

- **A `.cmd`, not Python.** There is no interpreter in the packaged app, and the one process that could run our code is the process that has to die. `cmd.exe` is present on every Windows PC, needs nothing installed, and a Windows child outlives its parent by default.
- **Every value arrives in the ENVIRONMENT, never baked into the file.** The script text stays constant and pure ASCII, so no code page can corrupt it when a path carries a non-ASCII character — and the gate can run the shipped text unchanged.
- **The script lives in `USER_DIR`, never in the install folder.** The installer is overwriting the install folder; a handover cannot keep its instructions inside the thing it is driving.
- **Windows' own tools by FULL PATH** (`%SystemRoot%\System32\tasklist.exe`, `find.exe`, `ping.exe`). `PATH` is the user's: a PC with Git for Windows answers a bare `find` with GNU find, which reads its argument as a file, fails, and turns every "is that process alive?" question into a confident, instant NO. Found by the gate on the dev machine — it would have meant the installer starting while the app was still writing.
- **The rollback and the success path are the same line.** A silent NSIS run that fails replaces nothing, so the exe path still holds the OLD app; starting it is both "the update worked" and "it did not, here is your PC back". No branch to get wrong, no backup to restore, no state to reconcile.
- **The record answers exactly one question** — did the version we installed become the version now running? — and it is consumed on read, so an "Apply & restart" cannot re-announce last week's update.
- **A failed update is announced as loudly as a successful one.** Silence is how a man ends up testing a build he never installed (the 2026-08-07 stale-build day).
- **The arming lock is a fact on DISK, reclaimed on two conditions and bricked by none** (owner 2026-08-09, the 20-install fork). The fork's whole nature is that the processes involved know nothing about each other, so no in-process latch can cut it. The lock holds `{pid, at}` — the armer's pid first, the script's `cmd.exe` pid the moment the spawn returns — so it stays honest exactly as long as a handover is genuinely alive, and there is no release step on the success path: the script dies, the lock goes stale, the next arm reclaims it. A dead pid is reclaimed; a lock older than `LOCK_STALE_S` is reclaimed even with a live pid (pid recycling); and the refusal happens BEFORE the phone is told, with the live script named in the log. Gate: the two lock checks in `tests/test_update_handover.py`, fail-closed in `build.py` (0i/6), proven by planting the defect (the consult deleted → the gate went red on the fork check).
