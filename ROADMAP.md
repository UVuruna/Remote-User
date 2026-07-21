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

## ✅ Phase 1 — First Working Loop: See & Click

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
- [x] **Owner test on a real device** — passed 2026-07-21: click lands precisely, stream smooth, no perceptible lag

<a id="phase-2"></a>

## 📋 Phase 2 — Core Remote v1

Goal: daily-usable control of the PC.

- [x] Input mechanics — **modifier buttons** (owner decision, replaces timed-gesture plan): glass corner buttons per DESIGN.md; hold RIGHT + tap = right click, hold DRAG + finger = real mouse drag, hold SCROLL + finger = wheel
- [x] Pinch zoom of the local view for precise targeting — pulled forward after the first device test (owner: small targets need it); includes two-finger pan, clicks fire only on clean tap release
- [x] **Region streaming — sharp zoom** (owner report: downscaled stream pixelated when zoomed): client reports its visible region, server crops the native frame to it; constant bandwidth, native pixels from ~2.4× zoom
- [x] Visibility-gated session (owner security decision): socket closes when the page hides (tab switch / screen lock), reconnects on return
- [x] Auto-reconnect (network blip, tablet sleep/wake) — shipped with Phase 1 client
- [x] Frame backpressure: per-client queue of size 1 drops stale frames when the client lags — shipped with Phase 1 server
- [x] Keyboard: ⌨ toggle button → hidden input field + value diffing (`key_text`), `keydown` for special keys (`key_special`); `KEYEVENTF_UNICODE` injection incl. surrogate pairs; tapping the screen keeps the keyboard open
- [x] Invalid-token UX: close code 4401 shows "scan the fresh QR" instead of retrying forever
- [x] Monitor switch button (MON): cycles dxcam outputs, swaps injector rect via monitor enumeration, client view reset through a fresh `config`
- [x] Screenshot to PC clipboard (SNAP, owner request): native-res frame → CF_DIB in the Windows clipboard, paste-ready on the PC; toast confirmation
- [x] Persistent pairing token across restarts (`logs/token.txt`) — no re-scan after server updates
- [x] DPI declaration hardened: pointer-sized context + checked return (bare-int ctypes call failed silently; dxcam's own declaration was masking it)
- [x] PAN toggle (owner request): one-finger view panning while zoomed, clicks blocked — top-left, opposite the action cluster
- [x] ENTER button (owner request): promoted accent button so Send/Enter is never hunted for
- [x] Chord engine + action sets + radial wheel (owner design): server `press_chord` (`ctrl+win+alt+1`), owner-edited `actions.json` (Edit / Nav / Zones), hold-a-pill → joystick wheel → release fires. Custom-set editor + login deferred to the desktop GUI phase (owner)
- [x] See-through buttons + text labels (owner: buttons were opaque "film" and unlabelled) — low-opacity fill, no blur, icon+label
- [x] Newline button replaces Enter (owner: phone keyboard's action key already = Enter; needed Shift+Enter for newline)
- [x] Instant keyboard fit (owner: view lifted late) — `visualViewport` resizes the canvas and lifts the pad the moment the keyboard opens
- [x] Momentum scrolling (owner: mouse wheel felt nothing like a phone flick) — velocity-based fling with decay
- [ ] Keyboard tuning on real devices (Gboard/Samsung IME quirks — swipe typing, autocorrect)
- [x] Control redesign → two configurable D-pad groups (owner design): each group = one category of 4, D-pad cross (landscape) / column (portrait), small dashed centre opens a **tap-based** category wheel (tap-open, tap-select, ✕ cancel — no hold/drag, smaller centre button). All old fixed buttons became category actions in `actions.json`. Top-left Move, top-right Hide (hide all controls)
- [x] HOVER mouse mode (owner: "show more" only appears on hover) — move the cursor with no button held
- [x] Two-layer rendering (owner: pan/zoom felt slow) — persistent full-monitor base + sharp region overlay, so motion never flashes blank
- [x] Mouse modes are toggles, not holds (owner correction) — single active `touchMode`, one-at-a-time, Move included
- [x] Visible keyboard bar (owner: hidden field caused a blank banner + couldn't see typed/dictated text) — capture input shown at top while focused
- [x] Phone → PC image (owner request): file-picker (gallery/camera) → `/upload` → PC clipboard, paste-ready; replaces PC `snap` in the default layout
- [ ] Wheel/D-pad tuning on real device (sizes, positions, portrait vs landscape feel)

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
