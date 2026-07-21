# Remote User — Roadmap

Development phases for the remote-control system. See [Remote User](README.md) for architecture and design decisions.

## Table of Contents

- [Phase 0 — Research & Foundation](#phase-0)
- [Phase 1 — Prototype: See & Click](#phase-1)
- [Phase 2 — Core Remote v1](#phase-2)
- [Phase 3 — Usability & Polish](#phase-3)
- [Phase 4 — App-Aware Layer](#phase-4)
- [Future Ideas](#future)

---

<a id="phase-0"></a>

## ✅ Phase 0 — Research & Foundation

- [x] Feasibility research (PC side: capture/streaming/injection; client side: stack comparison, touch UX, keyboard capture)
- [x] Architecture decided: Python server + browser PWA client, WebSocket, JPEG streaming, `SendInput` injection
- [x] Single-monitor-per-view policy (owner decision) — simplifies all coordinate math
- [x] Project documentation: README, ROADMAP, CLAUDE, logo
- [x] Registered in root PROJECTS.md / README.md

<a id="phase-1"></a>

## 🔨 Phase 1 — First Working Loop: See & Click

Goal: live screen on the tablet, tap lands a click on the PC — the complete loop on real code that Phase 2 builds on.

- [x] FastAPI server: serves the client page + WebSocket endpoint
- [x] `dxcam` capture loop (primary monitor) → JPEG → push over WebSocket
- [x] Stream downscaling (`max_stream_width`) — 4K native was ~216 Mbps, capped to ~48 Mbps
- [x] Client page: canvas rendering of incoming frames (letterbox-aware)
- [x] Tap → `pointer_down`/`pointer_up` → `SendInput` left click at absolute position
- [x] DPI awareness declaration (`PER_MONITOR_AWARE_V2`) from day one
- [x] Token auth gate on the WebSocket (moved up from Phase 2 — security is not optional)
- [x] QR code encoding `http://<lan-ip>:<port>/?token=…` (console ASCII + PNG)
- [x] Smoke test passed on the dev machine (real 4K frame captured, encoded, injector mapping verified)
- [ ] **Owner test on a real tablet** — the Phase 1 exit criterion

<a id="phase-2"></a>

## 📋 Phase 2 — Core Remote v1

Goal: daily-usable control of the PC.

- [ ] Gesture disambiguation: tap / hold-then-drag / two-finger scroll
- [ ] Floating right-click icon (arms next tap as right click, auto-reverts)
- [ ] Pinch zoom of the local view (client-side only) for precise targeting
- [ ] Keyboard: hidden input field + text diffing (`key_text`), `keydown` for special keys (`key_special`)
- [ ] Monitor switch button (capture source + coordinate rect swap)
- [ ] Auto-reconnect (network blip, tablet sleep/wake)
- [ ] Frame backpressure: drop stale frames when the client lags

<a id="phase-3"></a>

## 📋 Phase 3 — Usability & Polish

- [ ] PWA manifest — installable, fullscreen, stable icon
- [ ] Quality/FPS settings (JPEG quality, capture rate, downscale)
- [ ] PC-side GUI per root DESIGN.md: tray icon, status window, QR display
- [ ] Run-as-administrator option (control over elevated windows)
- [ ] Wake Lock integration + documented one-time Chrome flag setup
- [ ] Account login on both sides (shared credential replacing the raw token)

<a id="phase-4"></a>

## 📋 Phase 4 — App-Aware Layer

The long-term goal: the server knows which application is focused and adapts.

- [ ] Focused-window/process detection on the PC
- [ ] Per-app profiles: extra buttons and shortcuts per application
- [ ] State watching: app-specific conditions trigger notifications on the tablet
- [ ] First target: VSCode / agent workflow (send instruction, watch for completion)

<a id="future"></a>

## 💡 Future Ideas

- H.264 + MSE streaming upgrade (Weylus pattern) if JPEG bandwidth becomes limiting on high-res monitors
- Flutter client — only if background operation across tablet screen-lock becomes a requirement
- Audio streaming
- File drop (tablet → PC)
