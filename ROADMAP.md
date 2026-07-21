# Remote User — Roadmap

Development plan for the remote-control system. See [Remote User](README.md) for architecture and design decisions.

## Table of Contents

- [Product Direction (decided 2026-07-22)](#direction)
- [Open Decisions](#open)
- [Build Plan](#build-plan)
- [Foundation — LAN Prototype (done)](#foundation)
- [Future Ideas](#future)

---

<a id="direction"></a>

## 🧭 Product Direction — decided 2026-07-22

After the LAN prototype proved the control loop and touch UX on real code, the product direction was set in discussion with the owner. **This section is the authoritative record of what was accepted** (the code history is under [Foundation](#foundation)).

### Decided (confirmed with owner)

- **A real product = two installable apps**, not "open a URL in a browser":
  - **Windows desktop app** — the Python server + a GUI (login, settings, status, monitor/quality) + tray, packaged as a signed `.exe`.
  - **Android app** — a **hybrid**: a native shell (login, device list, Connect, settings) wrapping a **WebView that reuses the existing web client**. The browser holds the communication logic; the user sees a real app with its own interface (no browser chrome, no URL/QR copying).
- **Distribution:** APK first (e.g. GitHub Releases); Play Store only later, for wide public distribution.
- **Connection across the internet:** a **mesh VPN installed on both devices** (Tailscale recommended; ZeroTier equivalent), set up **once**, guided by an in-app wizard. Works anywhere including mobile data via the mesh's **free relay fallback**. The server already binds all interfaces and pairing already detects/prefers the Tailscale address (`0.0.017`), so the connection layer is **code-ready** — going off-LAN needs the install, not new code.
- **One account, one-time login** (exact mechanism still open — see below).
- **Media: H.264**, hardware-encoded with **auto-detection** (NVENC → QuickSync → AMF) and a **software fallback** (libx264) so it runs on any PC — NVIDIA, Intel iGPU, AMD, or no GPU. Replaces JPEG-per-frame. Region-of-interest streaming dropped: inter-frame compression makes the full-frame stream cheap (measured **~2 Mbps static vs ~48 Mbps JPEG**).
- **Virtual cursor + trackpad (relative) mode** — learned from the pro tools, for precision on small targets.
- **Hard constraint: NO payment** for any required part. Third-party services/installs are acceptable if they are genuinely the best option; the owner does **not** over-index on privacy/security — this is a personal productivity tool, not a security product.
- **Strategy — don't fight a lost battle.** Do NOT try to beat mature free remote-desktop tools (RustDesk, Moonlight/Sunshine, Chrome Remote Desktop) on raw latency. Get streaming **"good enough"** (hardware H.264) and put the real, unique value into the **app-aware companion layer**: read PC application state via **Windows UI Automation** (the accessibility tree — structured, cheap, reliable, no OCR/AI), send notifications, and offer per-app controls. Canonical use case: **watch how far an AI coding agent has gotten while away from the PC.** Specific companion features to be specified by the owner.
- **Learn/borrow techniques** (not code) from the pros: hardware encoder, inter-frame compression, trackpad relative cursor, adaptive quality, bidirectional clipboard sync.

<a id="open"></a>

### ❓ Open Decisions (not yet settled)

- **Login mechanism:** (a) the mesh/Tailscale login **is** the account — one login, no custom backend, the app finds the PC via the mesh device list (**recommended, simplest**); vs (b) our own account on Hostinger with the mesh underneath (own brand, but a second login or federation). *Owner to confirm.*
- **Mesh provider:** Tailscale (recommended) vs ZeroTier (equivalent).
- **Distribution:** APK-only vs eventual Play Store.
- **Build order:** the plan below is proposed; owner to confirm the sequence.

<a id="build-plan"></a>

### 🔨 Build Plan (phases)

- **Phase A — H.264 end-to-end** *(in progress)*: encoder core + auto-detect **done** (`0.0.019`, verified NVENC + software fallback). Remaining: wire the server to send H.264, client decodes via MSE into the canvas, add the virtual cursor. Biggest responsiveness lever; testable on LAN.
- **Phase B — Off-LAN validation** via the mesh: install Tailscale on both, test from mobile data. Connection code already ready — mostly an install + measure step.
- **Phase C — Desktop app:** server wrapped in a GUI (login, settings, status, monitor/quality) + tray, packaged as a signed `.exe` installer (monorepo build pipeline), with the Tailscale setup wizard.
- **Phase D — Phone app (APK):** native shell + WebView + login + device list + Connect + Tailscale wizard.
- **Phase E — Login / pairing:** the "click Connect and my PC appears" flow tying the account to finding the PC.
- **Phase F+ — App-aware companion layer** (the differentiator): focused-window/process detection, Windows UI Automation state reading, notifications, per-app controls. Owner specs the features.

---

<a id="foundation"></a>

## ✅ Foundation — LAN Prototype (done)

The prototype that proved the control loop and UX on real code — now the foundation the product is built on. Runs on LAN with a browser client, JPEG streaming, and token pairing.

### Research & Foundation
- [x] Feasibility research (capture/streaming/injection; client stack, touch UX, keyboard capture)
- [x] Single-monitor-per-view policy (owner) — simplifies coordinate math
- [x] Project docs (README, ROADMAP, CLAUDE, logo); registered in root PROJECTS.md / README.md

### First working loop — See & Click
- [x] FastAPI server serving the client + WebSocket; `dxcam` capture → JPEG → WebSocket
- [x] Tap → `SendInput` absolute click; DPI awareness (`PER_MONITOR_AWARE_V2`, hardened)
- [x] Token auth gate; QR pairing (persistent token across restarts)
- [x] Verified on a real device 2026-07-21 (precise click, smooth, no perceptible lag)

### Core controls & UX (all owner-driven)
- [x] Two configurable **D-pad groups** from `actions.json`: D-pad cross (landscape) / column (portrait), small dashed centre opens a **tap-based** category wheel (tap-select, ✕ cancel)
- [x] **Touch modes as toggles** (single active): left click (default) / right / drag / scroll / hover / pan (Move). Two fingers pinch-zoom
- [x] Chord engine (`ctrl+win+alt+1`) + owner-edited categories (Mouse / Edit / Keys / View / Zones)
- [x] Keyboard: visible top bar + value-diffing capture, `KEYEVENTF_UNICODE` (emoji), special keys; instant fit above the soft keyboard via `visualViewport`
- [x] Momentum scrolling; pinch zoom + two-layer base+region rendering (no blank flashes)
- [x] Monitor switch; PC→clipboard screenshot; **phone→PC image upload** (`/upload`)
- [x] See-through labelled buttons; Move (top-left) + Hide-all (top-right); visibility-gated session; auto-reconnect
- [ ] On-device tuning (gesture feel, Gboard/Samsung IME quirks) — ongoing

---

<a id="future"></a>

## 💡 Future Ideas

- Adaptive bitrate/quality on the H.264 stream (drop quality on a slow/relayed link)
- Hardware zero-copy capture→encode (Desktop Duplication → NVENC) for lowest latency
- Audio streaming; file drop (phone → PC)
- Run-as-administrator option (control over UAC-elevated windows)
