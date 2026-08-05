# Remote User — Roadmap

Development plan for the remote-control system. See [Remote User](README.md) for architecture and design decisions.

## Table of Contents

- [Product Direction (decided 2026-07-22)](#direction)
- [Open Decisions](#open)
- [Build Plan](#build-plan)
- [Phase F+ Spec — Layouts & Tab Control (owner spec 2026-08-02)](#layout-spec)
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
- **One account, one-time login = the mesh (Tailscale) login** (owner decision 2026-07-22, option **a**): the Tailscale identity **is** the account — a single login on each device, no custom account backend; the app finds the PC via the mesh device list.
- **The app installs and drives its own dependencies — the user NEVER does a side-install** (hard owner requirement, restated firmly 2026-07-22). The setup wizard in **both** the desktop `.exe` installer **and** the Android APK drives every dependent component:
  - **ffmpeg** is **bundled** inside the desktop installer — zero user action.
  - **Tailscale** is **chain-installed by the desktop installer**; the wizard then guides the one-time login.
  - On **Android**, an app cannot silently install another (OS security), so the wizard **deep-links to the store, detects when Tailscale is installed, then continues** — as automated as Android allows.
  - In every case the user only follows in-app prompts; "go download X / copy this / configure Y" is forbidden.
- **Media: H.264**, hardware-encoded with **auto-detection** (NVENC → QuickSync → AMF) and a **software fallback** (libx264) so it runs on any PC — NVIDIA, Intel iGPU, AMD, or no GPU. Replaces JPEG-per-frame. Region-of-interest streaming dropped: inter-frame compression makes the full-frame stream cheap (measured **~2 Mbps static vs ~48 Mbps JPEG**).
- **Virtual cursor + trackpad (relative) mode** — learned from the pro tools, for precision on small targets.
- **Hard constraint: NO payment** for any required part. Third-party services/installs are acceptable if they are genuinely the best option; the owner does **not** over-index on privacy/security — this is a personal productivity tool, not a security product.
- **Strategy — don't fight a lost battle.** Do NOT try to beat mature free remote-desktop tools (RustDesk, Moonlight/Sunshine, Chrome Remote Desktop) on raw latency. Get streaming **"good enough"** (hardware H.264) and put the real, unique value into the **app-aware companion layer**: read PC application state via **Windows UI Automation** (the accessibility tree — structured, cheap, reliable, no OCR/AI), send notifications, and offer per-app controls. Canonical use case: **watch how far an AI coding agent has gotten while away from the PC.** Specific companion features to be specified by the owner.
- **Learn/borrow techniques** (not code) from the pros: hardware encoder, inter-frame compression, trackpad relative cursor, adaptive quality, bidirectional clipboard sync.

<a id="open"></a>

### ❓ Open Decisions (not yet settled)

- **Mesh provider:** Tailscale (recommended) vs ZeroTier (equivalent). Owner observation (2026-07-22, went through signup live): Tailscale's account onboarding shows a one-time marketing survey — harmless (answers are irrelevant, "Personal use" fine, appears once per ACCOUNT, never again on other devices) but it is third-party friction our wizard cannot remove, only guide through. If it ever matters more: ZeroTier, or self-hosted Headscale (no Tailscale account at all). Not blocking.
- **Distribution:** APK-only vs eventual Play Store.
- **Build order:** the plan below is proposed; owner to confirm the sequence.

<a id="build-plan"></a>

### 🔨 Build Plan (phases)

- **Phase A — H.264 end-to-end** *(code complete — pending on-device feel test)*: encoder core + auto-detect (`0.0.019`), then the full wiring (`0.0.030`–`0.0.033`): per-client ffmpeg fMP4 sessions over the WebSocket, MSE decode on the client (codec string parsed from the live `avcC`), virtual cursor (server streams `GetCursorPos`, client draws — DXGI never captures the pointer), JPEG fallback verified intact. Measured live: **~1.5 Mbps H.264 vs ~37 Mbps JPEG** on the same static 4K→1600×900 screen; captured stream ffprobe-validated (Main@4.0, 30 fps, clean decode). Remaining in Phase A: the owner's on-device pass (latency feel, Android WebView autoplay/MSE quirks) and the trackpad-relative mode listed under the product direction.
- **Phase B — Off-LAN validation** via the mesh: install Tailscale on both, test from mobile data. PC side DONE live (`0.0.041` session): installer chain-installed Tailscale, owner signed in, PC on the mesh (100.x). **Phone side is now fully in-app guided** (hard owner principle — the app explains every step, never a human): the client page's "anywhere access" wizard deep-links to Google Play, waits, detects the phone joining via `/ping`, and hands over the permanent link. Remaining: owner runs the phone wizard + measures from mobile data.
- **Phase C — Desktop app** *(core delivered `0.0.034`–`0.0.037`; owner install-test pending)*: server refactored into a reusable core (`bootstrap` + `server_core` + user-settings persistence in `%LOCALAPPDATA%`), PySide6 window (status pill, in-window QR, settings with apply-and-restart) + tray, and the full build pipeline — PyInstaller onedir, code signing, NSIS installer that **bundles ffmpeg** (pinned 7.1.1: newest builds need NVENC API 13.1 / driver ≥ 610 and would silently drop to software encoding), **chain-installs Tailscale**, adds the firewall rule, optional autostart (`--minimized` to tray). Verified end-to-end: the frozen EXE streams 4K H.264 via NVENC with its own token. Remaining: owner runs the installer for real, Tailscale login guidance polish, GUI niceties (tunnel toggle, log viewer) as needed.
- **Phase D — Phone app (APK)** *(v1 shipped this session; owner device-test pending)*: a native Kotlin shell around the EXISTING web client — one wizard, one client, two containers. The shell adds only what a browser cannot: QR-scan pairing, real-app routing for the in-page wizard's Play Store link (so the guided Tailscale flow — deep-link, detect join via `/ping`, continue — works identically in the app), the upload file-chooser, a native unreachable-PC card, `Android.rescan()` re-pairing, keep-screen-on + rotation-safe session. Distribution is in-product and the browser is ONLY a funnel (owner rule 2026-07-22 — no half-working browser sessions): an Android browser on the QR link gets the full-screen `install.html` (served by User-Agent; the APK's WebView appends a `RemoteUserApp` marker) — Install downloads `/app.apk`, **Open the app** hands the tokened URL over via `remoteuser://pair` and the app pairs itself, nothing typed or scanned; the desktop installer bundles the APK. Remaining: owner installs on the phone and walks the guided flow; login/device-list shell UI is deferred to the Play-Store decision.
- **Phase E — Login / pairing:** the "click Connect and my PC appears" flow tying the account to finding the PC.
- **Phase F+ — App-aware companion layer** (the differentiator): focused-window/process detection, Windows UI Automation state reading, notifications, per-app controls. First concrete feature specced and probe-verified: [Layouts & Tab Control](#layout-spec).

---

<a id="layout-spec"></a>

## 📐 Phase F+ Spec — Layouts & Tab Control (owner spec 2026-08-02)

The first concrete slice of the companion layer, shaped with the owner and
feasibility-proven the same day. End goal restated by the owner: navigation and
(mostly textual) command entry as fast and easy as possible — minimal direct
mouse work, everything through commands that ease those processes when there is
no mouse and keyboard.

### The model

- **Layout** = one window full-screen or a grid of windows (Windows-Snap-like).
  Layouts are composed by the user ON THE SPOT — never predefined. UI (owner
  2026-08-02, correcting the earlier "switcher mode" idea): the top line —
  where Hide lives; the old Move/pan corner button is DROPPED as unnecessary —
  carries the **layout bar**: left arrow · app icon + open-tab name · right
  arrow, cycling the layouts; the bar does not exist while no layout does. A
  separate **create-layout button** (not called "switcher") arms the next tap
  on the stream: the server identifies what is under the point and the phone
  offers "solo" or "grid"; grid presents PREDEFINED templates (2x1, 1x2,
  2x2, …) whose remaining cells the user fills from a list of open apps.
- **Rotation** (owner 2026-08-02): in layout focus the phone's screen rotation
  is LOCKED to the layout's chosen orientation (portrait or wide, picked at
  creation); on the full-desktop view rotation is free — turning the phone
  swaps portrait/wide as usual.
- **Zoom in layout focus** (owner 2026-08-04): pinch zoom/pan is NOT skipped in
  layout mode — same two fingers as everywhere. The layout's region fitted to
  the screen is the maximum zoom-out and the default framing on every layout
  switch; panning can never bring the surrounding desktop into view.
- **Creation sources & Desktop behavior** (owner refinements 2026-08-02,
  after the first on-device pass): the Layout (+) button offers TWO sources —
  "From a list" (the server enumerates every window AND each window's content
  tabs — a window name alone hid its tabs) or "Tap a window" (a grid takes
  one tap per cell); both fill the same ordered slots. Server-side tab
  extraction is covered by a phone-side loading overlay and runs at trimmed
  waits. The Desktop slider position MINIMIZES every layout member — the
  full-desktop view shows only the windows that are not layout material.
- **The unit of selection is the TAB, not the application** (VSCode editor tab,
  Chrome tab, Explorer tab): the tab is extracted into its own OS window, which
  the layout then arranges. Extraction strategies in priority order (owner
  decision 2026-08-02 — the app's real functionality first, simulation last):
  1. **The app's own "move to new window" command** — tab context menu invoked
     via UIA: Chrome `Move tab to new window`, VSCode `Move into New Window`.
  2. **Explorer has no such command:** read the tab's folder path via UIA, open
     a new window at that path, close the original tab.
  3. **Universal fallback — simulated drag tear-off** with real held-button
     interpolated `SendInput` moves (the injector's own mechanics).
- **Layout focus locks the view:** the phone shows ONLY the focused member's
  region — the stream crop AND the mouse-move mapping are both constrained to
  that region. Focus switch = raise the window (which also solves overlap) and
  recompute its current rect.
- **Window sizing:** target the phone's aspect (portrait or wide — user's
  choice). Apps with min-size constraints get the nearest legal size — same
  aspect but larger, or other dimensions with a small letterbox on the phone.
- **Lifetime** (owner 2026-08-02): layouts are session-scoped but persist on
  the PC while the server runs — the phone may disconnect and return, the
  slider list survives; they die with the server app. The desktop is never
  restored: extracted tabs stay as windows, no auto-return.
- **Desk-side changes:** the user closing a member window at the PC removes it
  from the layout (identical to removing it via the phone); moving/resizing a
  member does NOT break the layout — the server tracks the live window and
  recomputes the crop at focus time.
- **Two devices, one at a time** (owner 2026-08-02): the owner alternates
  between a tablet and a phone, whose screens differ — so window dimensions
  saved on the PC cannot fit both. At app open the layouts ADAPT to the
  connecting device (its aspect/size re-drives the member-window sizing), and
  simultaneous use is forbidden: opening the app on one device closes the
  session on the other.
- **`next_input` command** *(shipped 2026-08-02, step 3)*: UIA-cycled focus
  through TEXT-INPUT fields only (Edit/Document elements), scoped to what is
  visible — full desktop view → fields of all visible windows; layout focus →
  only that layout's members. Built for the dictation-first workflow (IME ↵
  already = new row; real Enter is a D-pad button).
- **Quality setting** *(shipped 2026-08-02, step 3)*: the `quality` action
  cycles full → reduced (half resolution, ~10 fps, low bitrate — per client,
  in its own ffmpeg) → auto (reduced only on mobile data via the shell's
  `Android.transport()` bridge); the choice persists on the device and is
  restated on every connect.

### Probe results (2026-08-02, Windows build 26200, elevated server)

| | Chrome | VSCode | Explorer |
|---|---|---|---|
| Tab enumeration (UIA `TabItem`) | ✓ | ✓ | ✓ |
| Hit-test (`ElementFromPoint`) | ✓ | ✓ | ✓ |
| Context-menu "move to new window" | ✓ | ✓ | ✗ → path strategy |
| Drag tear-off (`SendInput`) | ✓ | ✓ | ✓ |

Hard-won specifics the implementation must respect:

- **Explorer's XAML tab strip ignores cursor-teleport drags** (`SetCursorPos`
  moves with a held button never grab the tab — the owner spotted it live):
  tear-off needs real interpolated `SendInput` moves.
- **VSCode detaches only when the drop lands outside EVERY VSCode window
  RECT** — visual occlusion is irrelevant; a fully tiled desktop leaves no drop
  zone and the taskbar can be hidden. Exactly why the native command is primary
  and drag is only the fallback.
- **Tab lists carry noise:** VSCode also exposes activity-bar/panel items and
  Explorer exposes Home-page pills (Recent/Favorites) as `TabItem` — filter by
  geometry (the tab band at the window top), name and parent chain.
- **Hit-test may return an INNER element** (VSCode: a `GroupControl` label) —
  walk ancestors up to the `TabItem`/window.
- Dev quirk: `Code.exe` rejects `-n`/`--new-window` when invoked directly —
  window options only work through the `code` CLI wrapper.

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
- [x] **Touch modes as toggles** (single active): cursor-move (default, never clicks — owner 2026-07-22) / right / drag / scroll / pan (Move); explicit **Click** button (twice = double click). Two fingers pinch-zoom
- [x] Chord engine (`ctrl+win+alt+1`) + owner-edited categories (Mouse / Edit / Keys / View / Zones)
- [x] Keyboard: invisible textarea + value-diffing capture (typed text is watched on the PC stream itself), `KEYEVENTF_UNICODE` (emoji), special keys; IME ↵ = new row (Shift+Enter), real Enter is a D-pad button; instant fit above the soft keyboard via `visualViewport`
- [x] Input stability on device (2026-07-22): ghost-pointer self-heal (a lost `pointerup` froze all taps into "pinch" until refresh) + instant reconnect on return (app switch swallowed the first taps)
- [x] APK dual-address (2026-07-22): LAN from QR + Tailscale learned via `Android.setTailscaleUrl`; `/ping` probe on start picks the reachable one — the app connects on mobile data (single stored LAN URL = minutes of timeout)
- [x] Upload auto-paste (2026-07-22): `/upload` injects Ctrl+V after filling the clipboard — the picked image lands in the focused box by itself
- [x] Updates flow downhill (2026-07-22): desktop checks GitHub Releases once per start → in-window Update button (download installer, launch, quit); phone compares `config.app_version` with its shell and updates from the PC's own `/app.apk` — no internet check on the phone
- [x] Install funnel (2026-07-22): an Android browser on the QR link never sees the client, only `install.html` (Open the app / Install) — one-tap `intent://` pairing; the browser is a funnel, not a second way to use the product
- [x] Adversarial review pass (2026-07-22): 6-lens fan-out over the day's changes surfaced 14 real defects, all fixed in 0.0.062–0.0.065 — reconnect-race stream freeze (stale socket had no identity guard), stuck PC mouse button after a lost drag-up, pinch leaking a cursor move that broke the new Click, mid-string IME edits corrupting PC text, 4401 retry storm, native-keyboard-dismiss breaking the Keys toggle, `monitor_switch` crashing the JPEG socket (missing `token` since 0.0.041), update installer failing UAC (Popen → WinError 740), no download timeout, and four Android intent/lifecycle/probe/re-pair strands
- [x] Momentum scrolling; pinch zoom + two-layer base+region rendering (no blank flashes)
- [x] Monitor switch; PC→clipboard screenshot; **phone→PC image upload** (`/upload`)
- [x] See-through labelled buttons; Move (top-left) + Hide-all (top-right); visibility-gated session; auto-reconnect
- [ ] On-device tuning (gesture feel, Gboard/Samsung IME quirks) — ongoing

---

<a id="editor"></a>

## 🖥️ Phase G — Desktop Controls Editor (owner decree 2026-08-04)

The owner announced this flow repeatedly and it was recorded only as "future
desktop GUI" — never phased, so it never got built (process failure, owner
called it out 2026-08-04). Standing rule from that day: **every "X is done on
the desktop" decision enters this roadmap as a phase immediately.**

A "Controls" section in the desktop app that edits the user copy of
`actions.json` — end users must NEVER hand-edit files. The phone picks up
edits on its next connection (already works). Bridge until built: the
"Edit controls" button (v0.0.072) opens the JSON in the system editor.

- [x] **G1 — Custom sets & arrangement** (done 2026-08-05, v0.0.073): the
  desktop "Controls…" dialog — create/delete/rename custom sets (4 buttons:
  builtin dropdown or RECORDED chord + icon from the client's set), choose
  which sets are shown by default, per-orientation arrangement (landscape
  cross / portrait column) for EVERY set with reset-to-default. Phone side:
  Settings → Sets picker (per-device choice + app-sets toggle, localStorage),
  per-orientation ordering in the D-pads. Wheel model (owner, same day):
  Mouse/Input/Settings `required`; Edit/Attach/Navigate/Cursor + Media/
  Windows (off by default) + customs toggleable; hard cap 8.
  Deferred from G1: a live D-pad preview inside the editor.
  Deferred 2026-08-05 (owner): **set/preset combining** — the desktop editor
  lets the user compose sets from the FULL action pool (incl. `anywhere`,
  `next_input`, which left the phone defaults) and combine presets; the
  `anywhere` action deliberately stays registered for this.
- [ ] **G2 — App sets** (½ session): same editor over `app_sets`, with the
  process picked from the list of running programs (real app icons — the
  server already extracts them for layouts).
- [ ] **G3 — Zones creator** (1 session): the owner's described flow —
  group (name + icon) and individual zones (name + shortcut + optional icon),
  written as a custom category.
- Login (Tailscale identity) stays a separate, later phase — not part of the
  editor.

---

<a id="future"></a>

## 💡 Future Ideas

- Adaptive bitrate/quality on the H.264 stream (drop quality on a slow/relayed link)
- Hardware zero-copy capture→encode (Desktop Duplication → NVENC) for lowest latency
- Audio streaming; file drop (phone → PC)
- Run-as-administrator option (control over UAC-elevated windows)
