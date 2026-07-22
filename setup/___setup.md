# setup/

The desktop build pipeline (root CLAUDE build spec): SVG → ICO, PyInstaller,
code signing, NSIS installer — plus this project's specialty, **dependency
bundling**: the user NEVER side-installs anything (hard owner requirement).

```
.venv\Scripts\python setup/build.py     → dist/RemoteUser_Setup.exe
```

## Files

### `build.py` — Build Orchestrator
Six steps: version info (app_info.json + root company.json) → ICOs → vendor
payloads → PyInstaller (`--onedir --windowed`, entry `server/gui_main.py`) →
sign exe → NSIS + sign installer.

Vendor payloads (cached in gitignored `setup/vendor/`, fetched on first build):
- **ffmpeg.exe** — bundled INTO the app (`dist/RemoteUser/ffmpeg/`); the frozen
  config finds it there. **Pinned to gyan.dev 7.1.1** — the newest git builds
  need NVENC API 13.1 (NVIDIA driver ≥ 610) and silently drop hardware encoding
  to libx264 on slightly older drivers (found on the dev PC itself).
- **tailscale-setup.exe** — the official installer stub, chain-run by the NSIS
  installer when Tailscale is absent.

PyInstaller notes: uvicorn's importlib-loaded backends need explicit
hidden-imports; numpy/cv2 are runtime deps (never exclude); QtWebEngine and
friends are excluded (500 MB of unused Chromium).

### `installer.nsi` — NSIS Installer
Standard wizard (welcome → directory → components → install → finish) plus:
- **Tailscale section** — chain-installs from the bundled stub, skipped when
  `$PROGRAMFILES64\Tailscale` already exists; never uninstalled by us
- **Firewall rule** — allow-rule for the exe (LAN + Tailscale WebSocket
  traffic); without it Windows silently blocks the phone's connection
- Autostart = HKCU Run with `--minimized` (standard-user app, starts in tray)
- Uninstall removes program files, shortcuts, firewall rule, autostart and
  `%LOCALAPPDATA%\RemoteUser` (settings/token/logs)
- Script is saved as **UTF-8 with BOM** — `Unicode true` + makensis reject a
  BOM-less file containing non-ASCII text

### `svg_to_ico.py` — Icon Generator
`assets/logo.svg` → `setup/icon.ico` (+ `icon-setup.ico` for the wizard,
from `logo-setup.svg` when present). Supersampled Lanczos, 16–256 px.

### `create_cert.py` — Certificate (run ONCE)
Self-signed code-signing cert → gitignored `setup/cert/` (pfx + generated
password). Back it up externally; recreate only on expiry (5 years).

### `app_info.json` — App Metadata
Version, names, exe/installer filenames. Company-level info comes from the
monorepo root `company.json` — never duplicated here.

## Connections

### Uses
- [Server (folder)](../server/___server.md) — the code being packaged; `gui_main.py` is the exe entry
- Root `company.json` — publisher/copyright for version resources

### Used by
- The owner, when cutting a release (then the GIT RELEASE procedure from root CLAUDE)
