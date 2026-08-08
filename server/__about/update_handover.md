# Update Handover

**Script:** [Update Handover (script)](../update_handover.py)

## Purpose

Installing a new version WITHOUT losing the session you are installing from.

The owner's report (2026-08-07): *"dešava se da ja ne mogu da instaliram novu verziju ako nisam kući, zato što čim uđem u instalaciju on će meni ugasiti Remote User i više neću moći da komandujem odavde."* Every fix this project ships reaches him only through an install, and starting the install killed the remote session he was installing FROM — so a man away from home sat on an old build unable to take the new one. The trap ate itself.

He asked for "quit later". This module builds the stronger requirement, because "later" still leaves him holding a phone in front of a Next button he cannot press: **after one tap on the window's Update button, nothing more is needed from anybody, and control comes back by itself.**

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
- `hand_over(installer, version, exe=None)`: writes `SCRIPT`, writes the record, spawns the script detached with the environment it needs. `exe` defaults to `sys.executable` — under PyInstaller exactly the path the installer replaces and exactly the path the script restarts. Nothing here guesses an install directory.
- `begin(controller, installer, version, expected_size)`: the whole sequence. Returns `("quit", "")` / `("manual", text)` / `("stop", text)`.
- `announce()`: called once per process start. If the previous run handed this PC over, queue the verdict for the phone's next connection — success or failure, both equally loud. Returns the queued title, `""` when there was nothing to report.
- `_write_record` / `_read_record` / `_spawn`: the three seams (disk, disk, process creation).

## Constants

- `MIN_INSTALLER_BYTES = 5_000_000` — a floor no captive-portal login page, HTML error body or zero-length file can reach.
- `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP` — the spawn flags. **`DETACHED_PROCESS` was the first attempt and it is wrong**: with no console at all, `tasklist` returns nothing, so both of the script's questions answered "yes" instantly and falsely. Caught by the gate, not by reasoning.
- `TELL_TIMEOUT_S = 3.0` — how long the update waits for the phone to be told.
- `SCRIPT` — the handover script, constant ASCII text (see [flow](../__flow/update_handover.md)).

## Design Decisions

- **A `.cmd`, not Python.** There is no interpreter in the packaged app, and the one process that could run our code is the process that has to die. `cmd.exe` is present on every Windows PC, needs nothing installed, and a Windows child outlives its parent by default.
- **Every value arrives in the ENVIRONMENT, never baked into the file.** The script text stays constant and pure ASCII, so no code page can corrupt it when a path carries a non-ASCII character — and the gate can run the shipped text unchanged.
- **The script lives in `USER_DIR`, never in the install folder.** The installer is overwriting the install folder; a handover cannot keep its instructions inside the thing it is driving.
- **Windows' own tools by FULL PATH** (`%SystemRoot%\System32\tasklist.exe`, `find.exe`, `ping.exe`). `PATH` is the user's: a PC with Git for Windows answers a bare `find` with GNU find, which reads its argument as a file, fails, and turns every "is that process alive?" question into a confident, instant NO. Found by the gate on the dev machine — it would have meant the installer starting while the app was still writing.
- **The rollback and the success path are the same line.** A silent NSIS run that fails replaces nothing, so the exe path still holds the OLD app; starting it is both "the update worked" and "it did not, here is your PC back". No branch to get wrong, no backup to restore, no state to reconcile.
- **The record answers exactly one question** — did the version we installed become the version now running? — and it is consumed on read, so an "Apply & restart" cannot re-announce last week's update.
- **A failed update is announced as loudly as a successful one.** Silence is how a man ends up testing a build he never installed (the 2026-08-07 stale-build day).
