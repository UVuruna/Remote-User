# Vibe Coder

Remote control of a Windows PC from an Android phone or tablet over the LAN (or
a mesh VPN from anywhere). The PC runs a Python server — screen capture, input
injection, window/layout management — and the phone runs a thin Kotlin shell
around a WebView that loads the page the PC serves. The value is not raw
remote-desktop latency but the **app-aware companion layer**: layouts of real
windows, per-app control sets, dictation, notifications, the agent's own ledger
on the phone.

This file inherits the monorepo constitution (`../../CLAUDE.md`) and only ADDS
or TIGHTENS it.

profiles: laptop-avg, pc-low, phone-portrait, phone-landscape, tablet-landscape
installable: yes

## Stack

- **Server:** Python 3.13, FastAPI + uvicorn, `dxcam` (DXGI capture), `ctypes` →
  Win32 `SendInput`, UI Automation for window/focus state, `qrcode` for pairing.
- **Desktop GUI:** PySide6 (window + tray). `bootstrap.init_process()` (DPI →
  logging → user settings) MUST run before any screen-touching import.
- **Streaming:** H.264 via ffmpeg, hardware-encoded (NVENC → QuickSync → AMF)
  with a libx264 fallback; fragmented MP4 decoded by MSE. JPEG-per-frame is the
  fallback when no encoder exists.
- **Client:** vanilla HTML/CSS/JS in the WebView — Pointer Events, canvas
  rendering, no framework and no build step.
- **Android:** Kotlin shell in `android/` (pairing, link routing, file chooser,
  gamepad, TTS bridge) — it adds only what a browser cannot; all guidance lives
  once, in the page.
- **Data:** `actions.json` (control sets, documented in `ACTIONS.md`), user
  settings under `%LOCALAPPDATA%`, layout history on the PC.

## How to run

```
python server/gui_main.py            desktop app (GUI + tray) — what the EXE runs
python server/main.py                headless CLI server
python tools/design_lab.py           the design lab (PC workshop, never shipped)
```

## How to test

```
python -m pytest tests                       full suite
python tests/run_guards.py                   guards, FULL (Stop hook)
python tests/run_guards.py --fast            guards, fast (PostToolUse hook)
python u:/Coding/UVuruna/rules/tools/uv.py shot --all    every Qt window × profile
```

`node` must be on PATH for the client-side guards; without it they skip.

## Entry points

| Path | Role |
|------|------|
| `server/gui_main.py` | desktop process entry (GUI + tray) |
| `server/main.py` | headless entry |
| `server/server_core.py` | capture/inject/stream orchestration |
| `server/web.py` | FastAPI app + the WebSocket handler |
| `server/gui/main_window.py` | the main desktop window |
| `client/index.html` | the page the phone loads |
| `android/app/` | the Kotlin shell |
| `setup/build.py`, `setup/build_apk.py` | installer and APK (owner's word only) |
| `tools/design_lab.py` | the design lab — every control look on one page, Save writes back |
| `.claude/uv_windows.py` | window registry for `uv shot` |

## Project laws (tighter or extra)

- **One monitor per view.** Client coordinates are ALWAYS normalized 0–1 within
  the displayed monitor; never virtual-desktop-wide.
- **No input before auth** — the WebSocket handler rejects every message until a
  valid token arrives.
- **Nothing we force on a window may outlive us.** Every window we raise is
  written into the topmost LEDGER and released on both exit paths; while the app
  is not up, no manipulation of ours may remain.
- **Nothing is a tap** — the finger only steers the cursor; clicks are explicit
  buttons, and a row acts on the LIFTED finger.
- **Measured, never remembered** — a layout's arrangement, a window's position
  and a way back to a window are read from the desktop, never from our notes.
- **We never estimate how long another program needs** — watch for the
  condition, never sleep a guess.
- **A command that exists is not a command that works** — every phone-facing act
  is proven against the real desktop before it is called done.
- **Nothing may overlap anything**, and a notice stands as long as there is to
  read.
- **A question we ask outlives its subject by nothing** — a chip about a window
  that has closed is withdrawn by the PC, never left for him to tap away.
- **The phone product must never lean on this monorepo** — `setup/agent_hook.py`
  and `setup/ledger_hook.py` install themselves onto a stranger's machine and
  read nothing of the owner's `rules/`, `CLAUDE.md` or `.claude/`.
- RATCHET (files allowed over the structure wall): **empty** — both
  `tests/test_structure_law.py` and `tests/test_layout_law.py` carry an empty
  list, and it may only stay empty or shrink.

Each of these is one line here and a dated report in `docs/DECISIONS.md`; read
the entry before arguing with the rule.

## Docs

- `README.md` — what it is, the name story, the navigation chain root
- `docs/DECISIONS.md` — the 36 architecture constraints and every owner decree,
  dated; read the constraint you are about to touch
- `docs/PROTOCOL.md` — the wire frames, streaming, controls, keyboard, panels
- `ACTIONS.md` + `actions.json` — the control sets on the phone
- `ROADMAP.md` — phases and status · `docs/GUIDE.md` — the user's setup flow ·
  `docs/VERIFICATION.md` — the owner's live checklist
- Folder docs: `server/___server.md`, `client/___client.md`,
  `android/___android.md`, `tests/___tests.md`, `setup/___setup.md`,
  `tools/___tools.md` → `__about/`, `__flow/`
- `UV/` — the owner's inbox: read it, never edit or delete it
