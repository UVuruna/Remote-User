# CLAUDE.md — Remote User

Project-specific guidance. Inherits ALL rules from the root [CLAUDE.md](../../CLAUDE.md).

---

## What This Project Is

Remote control of the Windows PC from an Android tablet/phone over LAN. The PC runs a Python server (screen capture + input injection); the tablet runs **no native app** — it opens a web page served by the PC. Full architecture and design decisions: [Remote User](README.md). Phase status: [Roadmap](ROADMAP.md).

## Tech Stack (decided — do not relitigate without owner approval)

**The authoritative record of the product direction and build plan is [ROADMAP.md](ROADMAP.md#direction) (Product Direction, decided 2026-07-22). Read it before proposing architecture changes.** Summary:

- **Server:** Python 3.13, FastAPI + uvicorn, `dxcam` (DXGI capture), `ctypes` → Win32 `SendInput` (injection), `qrcode` (pairing).
- **Streaming:** **H.264** via ffmpeg, hardware-encoded with auto-detection (NVENC → QuickSync → AMF) and a **libx264 software fallback** so it runs on any PC; output is fragmented MP4 decoded by the client via MSE. JPEG-per-frame is the fallback when no ffmpeg/encoder exists. (Measured ~2 Mbps static vs ~48 Mbps JPEG.)
- **Product = two installable apps:** a Windows desktop app (server + GUI + tray, `.exe`) and an Android **hybrid** app (native shell + WebView reusing the web client, shipped as an APK). Not "open a URL in a browser".
- **Connection:** a mesh VPN installed on both devices (Tailscale recommended), one-time, wizard-guided; works anywhere incl. mobile data via the mesh's free relay. Server already binds all interfaces + pairing detects the Tailscale address, so this is code-ready.
- **Login = the Tailscale login** (owner decision, option a): the mesh identity IS the account; one login per device, no custom account backend.
- **The app installs/drives all dependencies — the user never side-installs anything** (hard owner requirement). Wizard in the `.exe` AND the APK: ffmpeg bundled; Tailscale chain-installed on desktop / store-deep-linked-and-detected on Android; user only follows in-app prompts. Never tell the *end user* to download/copy/configure anything (telling the *owner* to install a dep for dev-time testing is fine, but say so explicitly).
- **Client UI:** vanilla HTML/CSS/JS in the WebView, Pointer Events, canvas rendering — no framework, no build step.
- **Hard constraints (owner):** no payment for any required part; third-party services/installs OK if best; not over-indexing on privacy/security. Don't fight mature remote-desktop tools on latency — the unique value is the **app-aware companion layer** (Windows UI Automation state reading, notifications, per-app controls).
- **Open decisions** (see ROADMAP): mesh provider (Tailscale vs ZeroTier), distribution (APK vs later Play Store), build order.

## Architecture Constraints

1. **One monitor per view.** The client always displays and controls exactly one monitor; a switch button changes which. Client coordinates are ALWAYS normalized 0–1 within the displayed monitor; the server maps them to that monitor's rect. Never send virtual-desktop-wide coordinates.
2. **The server process must declare DPI awareness** (`DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2`) before any capture or injection — otherwise Windows silently rescales injected coordinates.
3. **No input before auth.** The WebSocket handler rejects every message until a valid token arrives. This is a hard security rule (Remote Mouse CVE class), not a nice-to-have.
4. **Unicode text goes through `KEYEVENTF_UNICODE`** (VK_PACKET), never through virtual-key mapping. Special keys (Enter, Backspace, arrows, Tab, Esc) go through VK codes. Two distinct protocol messages: `key_text` vs `key_special`.
5. **Client keyboard capture:** hidden focusable `<input>` (`opacity:0`, NOT `display:none`) with `autocapitalize/autocorrect/autocomplete/spellcheck` disabled; printable characters via input-event diffing, structural keys via `keydown`. Never trust `keydown.key` for printable characters (Android IME).
6. **Input mechanics are modifier buttons, not timed gestures** (owner decision, 2026-07-21): tap = left click on clean release; corner buttons held with one finger modify what the other finger does (RIGHT → right click, DRAG → mouse drag, SCROLL → wheel). Two fingers on the canvas = local pinch zoom/pan, which never sends clicks. Do not reintroduce long-press/timer gestures.
7. **Session lives only while the owner is looking** (owner security decision): the client closes the WebSocket when the page is hidden (tab backgrounded / screen locked) and reconnects on return. UAC-elevated windows still ignore injected input unless the server runs elevated (silent failure — UIPI).

## Protocol

- Client → server (JSON text): `auth {token}`, `pointer_down/pointer_up {x, y, button}`, `pointer_move {x, y}`, `scroll {x, y, ticks}`, `viewport {x, y, w, h}`, `key_text {text}`, `key_special {key}`, `chord {chord}`, `monitor_switch {}`, `screenshot {}`. Coordinates are always 0–1 within the displayed monitor.
- Server → client: `config {monitor_width, monitor_height}` JSON text (after auth and after a monitor switch — client must fully reset its view), `actions {sets}` (radial-wheel shortcut sets from `actions.json`, after auth), `toast {text}` (user-facing notice shown on the status pill), then binary frames: **16-byte header (4 × float32 LE — monitor-normalized x, y, w, h of the region the frame covers) + JPEG bytes**.
- **Controls are two configurable D-pad groups** (owner design): each group shows one category of up to 4 buttons, arranged as a D-pad cross in landscape and a column in portrait. A small dashed centre button opens a **tap-based** category wheel (tap to open, tap an item, ✕ cancels — no hold/drag). Top-left **Move** (pan, no click) and top-right **Hide** (hide all controls) are fixed. Everything — mouse modes, keyboard, monitor, snap, and chord shortcuts — is a category button defined in the owner-edited `actions.json` (see [ACTIONS.md](ACTIONS.md)), re-read every connection; the client renders from config and never hardcodes the layout. Custom-set editing UI and login belong to the future desktop GUI (owner decision).
- **Mouse modes are toggles, not holds** (owner correction): a single active `touchMode` — `click` (default) · `right` · `drag` · `scroll` · `hover` · `pan` (the top-left Move) — decides what one finger does. Tapping a mode button toggles it (again → back to `click`); only one is ever active; two fingers always pinch-zoom. Do not reintroduce hold-to-activate.
- **Keyboard is a visible top bar** (owner: a hidden field left a blank banner and you couldn't see what you typed): the capture `<input>` is shown at the top while focused, so typed/dictated text is visible; it still uses value-diffing for injection.
- **Phone → PC image** (`upload` action, owner request): a phone file-picker (gallery/camera) POSTs the image to `/upload` (token-gated); the server decodes it and puts it in the **PC clipboard** to paste. This is the opposite of `snap` (which captures the PC screen); the owner wants phone→PC, so `snap` is not in the default layout.
- **Rendering is two layers** (owner request — smooth pan/zoom): a full-monitor **base** frame kept in memory (drawn always, so motion never flashes blank) plus the sharp **region** crop drawn on top when zoomed. Full native resolution is never streamed live (bandwidth); the base is the last full frame, the region refreshes while zoomed.
- Region streaming: when zoomed, the client requests its visible region (`viewport`); the server crops the 4K frame to it before downscaling — zoom stays sharp at constant bandwidth. Full frame = region (0, 0, 1, 1).

## Testing Notes

- Gesture disambiguation (tap vs drag vs scroll) can only be tuned on a **real touch device** — do not assume defaults are right.
- Test Unicode injection against real targets (VSCode, browser inputs) — VK_PACKET has known quirks in some apps (e.g. Windows Terminal surrogate-pair bugs).
- After long-running capture sessions, verify frame latency fresh — restart before measuring (see root CLAUDE.md profiling section).
