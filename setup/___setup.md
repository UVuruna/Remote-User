# setup/

The desktop build pipeline (root SHIP.md's 7-step pipeline) — plus this
project's specialty, **dependency bundling**: the user NEVER side-installs
anything (hard owner requirement), so `build.py` fetches/bundles ffmpeg and
chain-installs Tailscale itself.

```
.venv\Scripts\python setup/build_apk.py   → dist/VibeCoder.apk   (run first if android/ or client/ changed)
.venv\Scripts\python setup/build.py       → dist/VibeCoder_Setup.exe
```

## Files

| File | Tier | One line |
|------|------|----------|
| `build.py` | Algorithmic | 7-step build pipeline orchestrator + the fail-closed `verify_build` gate — [about](__about/build.md) · [flow](__flow/build.md) |
| `build_apk.py` | Algorithmic | Android release-APK build protocol — toolchain, keystore, Gradle — [about](__about/build_apk.md) · [flow](__flow/build_apk.md) |
| `svg_to_ico.py` | Algorithmic | SVG → multi-resolution ICO, supersampled Lanczos downscale — [about](__about/svg_to_ico.md) · [flow](__flow/svg_to_ico.md) |
| `agent_hook.py` | Standard | the Claude Code `Stop` hook: names the agent that finished and POSTs it to the running server, which notifies the phone (ROADMAP Phase H) — also installs `ledger_hook.py` in the same `install()` call (T111) — [about](__about/agent_hook.md) |
| `ledger_hook.py` | Standard | the Claude Code `UserPromptSubmit`/`Stop` hooks that keep a project's session ledger honest — creates the file, stamps the turn, refuses a `Stop` when the ledger went unchanged or ungrammatical (T111) — [about](../server/__about/session_ledger.md) |
| `create_cert.py` | Standard | one-time self-signed code-signing certificate generator — [about](__about/create_cert.md) |
| `rehearse_update.py` | Standard | the update-storm rehearsal — 8 concurrent throwaway installers prove the one-handover mutex (1/8 with the lock, 8/8 without), verdict by PID markers never wall-clock (task 187 closer c) — [about](__about/rehearse_update.md) |
| `release_hygiene.py` | Standard | refuses a release while the owner's update.json says a handover is in flight — runs at the top of `build.py` (task 187 closer d) — [about](__about/release_hygiene.md) |
| `installer.nsi` | *(not in this doc pass)* | NSIS installer script — sections Main / Tailscale / Desktop shortcut / Autostart, plus the **unattended `/S` path** the running app drives itself ([Update Handover](../server/__about/update_handover.md)); see Design Decisions below |
| `app_info.json` | *(data, not code)* | project metadata (version, names, exe/installer filenames) read by every script above |

`installer.nsi` and `app_info.json` are outside this session's per-file
`__about`/`__flow` scope (the task covered the four `.py` files only) — see
the session report for why `installer.nsi`'s sections are a
Config-Section-Law candidate worth a future look.

## Connections

### Uses
- [Server (folder)](../server/___server.md) — `server/gui_main.py` is the
  PyInstaller entry point; the whole `server/` tree is what gets frozen
- [Client (folder)](../client/___client.md) — bundled via PyInstaller
  `--add-data` (served to the tablet at runtime)
- [Android (folder)](../android/___android.md) — the release APK
  (`build_apk.py`'s output) rides along in the installer when present
- [Tests (folder)](../tests/___tests.md) — `tests/test_input_pipeline.py`,
  run by `build.py` as the fail-closed INPUT GATE before anything is
  packaged (confirmed wired — see `input_gate()` in
  [Build Orchestrator](__about/build.md))
- root `company.json` — publisher/copyright, read by `build.py` for the
  version resource and the installer's version info
- `setup/app_info.json` — version, names, description, exe/installer
  filenames; the single version source read by every script here

### Used by
- The owner, cutting a release — root SHIP.md's GIT RELEASE procedure
  starts from this folder's `build.py`

## Design Decisions

- **`--onedir`, never `--onefile`** — lower RAM, faster startup, fewer AV
  false positives (root SHIP.md Step 3); this project additionally needs
  `--onedir` so `ffmpeg.exe` and the Android APK can sit as plain files next
  to the exe rather than inside a one-file archive.
- **Fail-closed everywhere a step could otherwise break silently.** Four
  gates stop the build rather than let a broken artifact through: the INPUT
  GATE (`build.py` Step 0b — a broken click path), the frozen-exe smoke test
  (Step 3b — a missing bundled module), `sign_file`'s explicit
  skip-with-warning (never a silent unsigned build the log doesn't call
  out), and `verify_build` (the final read of the actual artifact
  metadata/signatures). Each one exists because its failure class shipped to
  the owner at least once before it was added — see
  [Build Orchestrator](__about/build.md) Design Decisions.
- **The exe runs elevated always (`--uac-admin`)** — not the SHIP.md default
  ("only when truly required"); here it IS required. Windows UIPI silently
  discards `SendInput` from a non-elevated process whenever an elevated
  window has focus, so a non-elevated Vibe Coder is a dead input device the
  moment the owner opens one admin window (2026-07-29 live failure, see
  project [CLAUDE.md](../CLAUDE.md) Architecture Constraint 8). Autostart
  therefore uses a Task Scheduler `/RL HIGHEST` logon task, not the registry
  Run key, which silently refuses to start elevated apps.
- **The build always re-execs under `.venv`** — the only interpreter
  guaranteed to have the complete dependency set; any other interpreter
  silently ships an incomplete bundle (root cause of the v0.0.045 crash that
  shipped without `qrcode`).
- **The installer must be able to run with NOBODY at the PC** (owner report
  2026-08-07). He installs from his phone, through the session the install
  replaces — so `installer.nsi` honours NSIS's `/S` end to end. Three things
  make that real, all decided in `.onInit` (which sits BELOW the sections, so
  the section ids exist): the Tailscale chain-install is unselected (its setup
  opens a VISIBLE wizard and our `ExecWait` would hang the whole update on a
  Next button nobody is there to press — and a silent run is by definition an
  upgrade of an app already reaching a phone over Tailscale); the desktop
  shortcut and the autostart task are read OFF THE MACHINE and the sections set
  to match, because a silent run must change nothing he did not ask to change
  (silent mode otherwise takes the DEFAULT selection and would re-arm both);
  and the `taskkill` in `SecMain` — the line that used to end his session — is
  kept only as the backstop for a hand-run install, because the handover script
  waits for the app's own pid to disappear first. See
  [Update Handover](../server/__about/update_handover.md).
- **`build_apk.py` runs BEFORE `build.py`, never the reverse** — the desktop
  installer only bundles the phone APK when it already exists on disk
  (`build.py` prints a note and ships without it otherwise); there is no
  automatic chaining between the two scripts.
