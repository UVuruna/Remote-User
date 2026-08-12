# Build Orchestrator

**Script:** [Build Orchestrator (script)](../build.py) ·
**Flow:** [diagram](../__flow/build.md)

## Purpose

The full desktop build pipeline (root SHIP.md's 7-step pipeline, plus two
project-specific fail-closed gates layered on top): version info → INPUT
GATE → icons → vendor payloads → PyInstaller → smoke test → sign exe → NSIS
installer → sign installer → VERIFY. Produces the signed
`dist/VibeCoder_Setup.exe` that the owner installs and self-updates through
(root SHIP.md's Release Law). Always re-execs itself under the project's own
`.venv` first — the only interpreter guaranteed to carry the complete
dependency set (a system-Python build once shipped v0.0.045 without
`qrcode` and crashed on first launch).

Run: `python setup/build.py` (auto re-execs under `.venv`) or directly
`.venv\Scripts\python setup/build.py`.

## Connections

### Uses
- [Server (folder)](../../server/___server.md) — `server/gui_main.py` is
  the PyInstaller entry point
- [Client (folder)](../../client/___client.md) — bundled via PyInstaller
  `--add-data` (served to the tablet at runtime)
- [Tests (folder)](../../tests/___tests.md) —
  `tests/test_input_pipeline.py`, run as the fail-closed INPUT GATE
  (Step 0b) BEFORE anything is packaged — confirmed wired: `input_gate()`
  shells out to it directly and a non-zero exit stops the build
- [SVG To ICO](svg_to_ico.md) — Step 1, invoked as a subprocess
- [Create Cert](create_cert.md) — consumes its output
  (`setup/cert/*.pfx`, `setup/cert/password.txt`) via `sign_file()`; does
  not invoke it directly — the cert is a one-time manual prerequisite, an
  unsigned build is the documented fallback when it's absent
- `setup/installer.nsi` — Step 5, invoked via `makensis`
- `setup/app_info.json` — version, names, description, exe/installer
  filenames
- [Agent Hook](agent_hook.md) — bundled via `--add-data` into
  `_internal/setup/`, where the desktop window's notify switch finds it
- root `company.json` — publisher/copyright, read for the version resource
  and the installer's version info
- `android/app/build/outputs/apk/release/app-release.apk` — bundled into
  the installed app and into `dist/` when present (built separately, and
  BEFORE this script, by [Build APK](build_apk.md))

### Used by
- The owner / a build session — the entry point for root SHIP.md's GIT
  RELEASE procedure (`.venv\Scripts\python setup/build.py` →
  `dist/VibeCoder_Setup.exe`)

## Functions

One line each; the full call sequence is in [flow](../__flow/build.md).

- `reexec_under_venv()` — re-launches the whole script under
  `.venv\Scripts\python.exe` if not already running there
- `generate_version_info()` — writes `version_info.txt` (a Windows
  VERSIONINFO resource source) from `app_info.json` + `company.json`
- `input_gate()` — the fail-closed gate run, whose SUITE lives in
  [Gates](gates.md) since 2026-08-12 (THE STRUCTURE LAW — the gate list grows
  every round, the packaging steps barely change); this module keeps the
  console's voice and the subprocess policy and hands both to it. A non-zero exit
  from any of them stops the build before anything is packaged:
  `test_input_pipeline` (0b), `test_presence` (0c), `test_notify` +
  `test_notice_channel` (0d), `test_focus_guard` + `test_focus_hook` (0e),
  `test_layout_protocol` (0f), `test_stream_lifecycle` (0g),
  `test_actions_migration` (0h), **`test_update_handover` (0i)** — added
  2026-08-07 because everything the others prove only matters if the
  release can be INSTALLED, and until then it could not be from away: entering
  the install killed the remote session driving it (see
  [Update Handover](../../server/__about/update_handover.md)) —
  `test_link_recovery` (0j), `test_voice_dedup` (0k),
  `test_user_settings` (0l), `test_caret_lift` (0m), `test_caret` (0n), and
  **`test_view_anchor` (0o)** — added 2026-08-09, the Move handle's fourth
  round: it computes the geometry the OWNER judges (where the letterboxed
  picture sits on the phone), after three rounds of gates measured window
  rects on a screen he never sees
- `generate_icons()` — runs `svg_to_ico.py` as a subprocess (Step 1)
- `fetch_vendor()` — downloads and caches `ffmpeg.exe` (pinned gyan.dev
  7.1.1) and `tailscale-setup.exe` into gitignored `setup/vendor/`
  (Step 2)
- `build_pyinstaller()` — runs PyInstaller `--onedir --windowed
  --uac-admin` around `server/gui_main.py`; copies ffmpeg, `icon.ico`, and
  the Android APK (if built) into `dist/VibeCoder/` (Step 3). Ends with the
  **PAYLOAD GATE**: every path the frozen code resolves under `BUNDLE_DIR`
  (`client/index.html`, `actions.json`, `assets/logo.svg`,
  `assets/check.svg`, `setup/app_info.json`, `setup/agent_hook.py`) must
  exist in `_internal/`, or the build stops. A file left out of `--add-data`
  breaks nothing here and nothing in the smoke test — which imports the
  module graph, not the data — it breaks on the owner's PC, as a switch that
  cannot be turned on (v0.0.085 shipped exactly that: the notifier hook was
  missing, see [Notify](../../server/__about/notify.md))
- `smoke_test(exe_path)` — runs the FROZEN exe with `--selfcheck`; a
  missing bundled module fails the build here, not the user's first
  launch (Step 3b, fail-closed)
- `sign_file(file_path)` — shared Authenticode signer (`signtool.exe`),
  applied to both the exe (Step 4) and the installer (Step 6); returns
  `False` (skip, not fail) when no cert/signtool is available
- `build_installer()` — runs `makensis` on `installer.nsi` (Step 5), then
  calls `sign_file()` on the resulting installer (Step 6)
- `verify_build(exe_path, installer_path)` — the fail-closed final gate:
  asserts exe `CompanyName` / `FileVersion`, and (when a cert is
  configured) that BOTH the exe and the installer carry an Authenticode
  signature; exits 1 on any mismatch — see [flow](../__flow/build.md) for
  the exact checks
- `main()` — runs all of the above in order

## Design Decisions

- **Re-exec under `.venv` always.** Any other interpreter silently drops
  whatever it's missing from the bundle (root cause of the v0.0.045
  crash); re-execing once, guarded by an env sentinel
  (`RU_BUILD_REEXEC`), makes "wrong interpreter" a build-time
  impossibility instead of a runtime surprise for the owner.
- **Two extra fail-closed gates beyond SHIP.md's base 7 steps.** The
  INPUT GATE (Step 0b) and the frozen-exe smoke test (Step 3b) exist
  because both failure classes shipped to the owner before: a broken
  click path ("left click dead") and a missing bundled module (`qrcode`)
  each looked correct in every file reviewed. Both turn an invisible
  runtime failure into a loud, un-shippable build failure.
- **`verify_build` asserts on OUTPUT, not on "did the steps run."**
  Matches SHIP.md Step 7's rationale exactly: PyInstaller without
  `--version-file` still produces an exe; a skipped signing step still
  produces a file. Only reading the finished artifact's actual
  metadata/signature catches a silently degraded build.
- **The exe runs elevated always (`--uac-admin`).** Not the SHIP.md
  default ("only when truly required") — here it IS required. Windows
  UIPI silently discards `SendInput` from a non-elevated process whenever
  an elevated window has focus, so a non-elevated Vibe Coder becomes a
  dead input device the moment the owner opens one admin window
  (2026-07-29 live failure — see project
  [CLAUDE.md](../../CLAUDE.md) Architecture Constraint 8).
