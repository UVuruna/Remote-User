# server/

The PC side of Vibe Coder: captures the screen, streams it over WebSocket as H.264 (JPEG fallback), streams the cursor position, and injects mouse/keyboard input received from the tablet client. Two entry points around one core: `gui_main.py` (the desktop app — what the installed EXE runs) and `main.py` (headless CLI for dev).

## Files

| File | Tier | One line |
|------|------|----------|
| `main.py` | Trivial | CLI entry point — bootstrap + `ServerController(console_pairing=True).run_blocking()`, nothing else |
| `gui_main.py` | Standard | desktop entry point — bootstrap + Qt + `MainWindow`; `--selfcheck` is the build's frozen-exe smoke test — [about](__about/gui_main.md) |
| `bootstrap.py` | Standard | process init shared by both entry points — DPI awareness → logging → user settings, in that order — [about](__about/bootstrap.md) |
| `server_core.py` | Algorithmic | the whole server stack as one start/stoppable component — [about](__about/server_core.md) · [flow](__flow/server_core.md) |
| `config.py` | Algorithmic | single source of every tunable value — code defaults + user settings JSON — [about](__about/config.md) · [flow](__flow/config.md) |
| `capture.py` | Algorithmic | dxcam ownership — capture thread, screenshots, monitor switching; JPEG and H.264 front-ends — [about](__about/capture.md) · [flow](__flow/capture.md) |
| `h264_streamer.py` | Algorithmic | H.264 streamer — one shared capture, one ffmpeg process per client — [about](__about/h264_streamer.md) · [flow](__flow/h264_streamer.md) |
| `encoders.py` | Algorithmic | H.264 encoder auto-detection — NVENC → QuickSync → AMF → libx264, verified by test-encoding — [about](__about/encoders.md) · [flow](__flow/encoders.md) |
| `input_injector.py` | Algorithmic | Win32 `SendInput` injection + the `InjectionMonitor` self-check tripwire — [about](__about/input_injector.md) · [flow](__flow/input_injector.md) |
| `cursor_shape.py` | Standard | WHICH cursor Windows is showing, named — the live `HCURSOR` matched against the system cursors, cached once for the 30 Hz loop, and an app's own cursor answered honestly as `custom` (owner request 2026-08-09) — [about](__about/cursor_shape.md) |
| `web.py` | Algorithmic | FastAPI app — the WebSocket protocol handler, HTTP routes, stream dispatch — [about](__about/web.md) · [flow](__flow/web.md) |
| `content.py` | Algorithmic | what the phone SENDS, turned into what the PC can receive: an upload decoded (HEIC + EXIF, OpenCV fallback) and a typed command pasted — clipboard → Ctrl+V → Enter, with the focus fence re-checked across the 120 ms between the last two (split from web.py 2026-08-08) — [about](__about/content.md) · [flow](__flow/content.md) |
| `presence.py` | Algorithmic | is the owner still working with us, and whose desk are we on — heartbeat, the `away` reason, the excursion hold, and the rule that local input at THIS PC outranks all of it — [about](__about/presence.md) · [flow](__flow/presence.md) |
| `focus_guard.py` | Algorithmic | WHERE typed input lands — the layout is a fence for the phone's keyboard, the desktop gets a pin, the fence stands even INSIDE one dictated sentence (chunk by chunk), and a window that steals focus is named in the log and handed the focus straight back — [about](__about/focus_guard.md) · [flow](__flow/focus_guard.md) |
| `lost_windows.py` | Algorithmic | CAN HE REACH IT AT ALL — the one question that needs no history, so it answers for the window that opened while his phone was LOCKED, which four rounds of baseline-based rules could not even see; a window with no grabbable title bar on any monitor (a minimized one judged by where it would RESTORE to) is offered back on the same chip, and the rescue is the first code here that moves a window it did not place (owner report 2026-08-12, his fifth) — [about](__about/lost_windows.md) · [flow](__flow/lost_windows.md) |
| `layout_popup.py` | Algorithmic | WHOSE window just appeared, and where it belongs — a member's OWN dialog (the owner chain, which is Windows' own statement and not a guess) is placed CENTERED ON ITS PARENT without asking (owner rule 2026-08-13); a member's new window, a process a member started or a window opened moments after an injected click is a GUESS, so it gets a chip he taps and nothing moves before he does; every stranger goes back to the fence untouched (owner eruption 2026-08-11, task 202) — [about](__about/layout_popup.md) · [flow](__flow/layout_popup.md) |
| `layout_birth.py` | Algorithmic | The OTHER question about a new window: he double-clicked something through the stream and it opened, so the phone offers to make a LAYOUT with it (task 185). Split out of `layout_popup.py` on 2026-08-13 — opposite subject (a window HE opened, which nothing may touch), and one file made them read as one feature until that cost him a moved window — [about](__about/layout_birth.md) · [flow](__flow/layout_birth.md) |
| `recents.py` | Standard | WHAT THIS PC CAN OPEN, so a layout can be made from a window that is not open yet — Explorer's Quick Access folders, VS Code's own LIVE Open Recent list read from `state.vscdb` (task 242 corrected this off the stale `storage.json` menu-paint cache), and honestly nothing but New window / Incognito for Chrome; the chosen entry is launched and the window that WAS NOT STANDING BEFORE is handed to the creation flow (owner 2026-08-09, task 184) — [about](__about/recents.md) |
| `layout_acts.py` | Standard | WHAT THE FOCUSED LAYOUT'S OWN APP CAN DO — the group the New panel draws above the standard list when it was opened from INSIDE a layout (owner ballot 2026-08-13, T29): a new Claude Code or a second window on the same project for VS Code, a tab / reopened tab / tab-from-the-clipboard for Chrome, a tab / up / Quick Access folder for Explorer. Every act asserts the PROCESS before one key goes out (constraint 11), the palette command name is READ from the extension's own package.json, and a project whose PATH cannot be found is refused rather than guessed — [about](__about/layout_acts.md) |
| `upload_api.py` | Trivial | PHONE → PC CONTENT over HTTP — one image as a CF_DIB bitmap, several files or any non-image as real CF_HDROP files, both ending in the injected Ctrl+V that makes picking the thing the whole gesture. Split out of `web.py` 2026-08-13 at the structure law's wall, unchanged: that file's subject is the live socket — [about](__about/upload_api.md) |
| `layout_history.py` | Standard | every layout ever created on this PC, persisted across restarts and deduped by member set — the "Recent" creation source's log, re-matched against whatever is open now by process + a fuzzy title match (owner 2026-08-11, task 228) — [about](__about/layout_history.md) |
| `clipboard_sync.py` | Standard | the PC clipboard reaches the phone — a push after every injected Copy/Cut plus a live `AddClipboardFormatListener` on focus_hook's thread shape while a session watches; held latest-only through an away, echo-guarded both directions (owner 2026-08-04, task 182) — [about](__about/clipboard_sync.md) |
| `caret.py` | Algorithmic | WHERE on the PC screen the typing appears, so the phone's keyboard need not cover it — the classic Win32 caret, else UI Automation's text selection (VSCode gives the ROW; measured), held briefly against a popup that steals focus, normalized to the shown monitor, and an unknown that carries NO position — [about](__about/caret.md) · [flow](__flow/caret.md) |
| `focus_hook.py` | Standard | Windows SAYS the foreground moved — one thread, one `SetWinEventHook`, one message loop, so the guard reacts in 2–5 ms instead of waiting up to a poll; it dies on every exit path — [about](__about/focus_hook.md) |
| `agents.py` | Algorithmic | which agent tools are LIVE on this PC and in which project — the process table answers what UI Automation could not, so the Claude set appears by itself instead of being ticked by hand — [about](__about/agents.md) · [flow](__flow/agents.md) |
| `agents_refresh.py` | Standard | the Claude wheel catches up on its own — a per-connection poll re-sends `layout_state` only when the process table's own answer for a live layout actually changed (owner report 2026-08-15) — [about](__about/agents_refresh.md) |
| `layout_api.py` | Algorithmic | the phone's layout protocol — pick, list, create, focus, aspect, state — [about](__about/layout_api.md) · [flow](__flow/layout_api.md) |
| `claude_api.py` | Standard | the Claude Code half of the phone protocol — focusing its prompt before a typed command runs (Command Palette → "Claude Code: Focus input", refused outright outside VS Code) and answering `claude_state` with what the conversation is really running; split off `web.py` 2026-08-11 — [about](__about/claude_api.md) |
| `actions_api.py` | Standard | actions.json ON THE WIRE — the reader + shipped-pool merge (moved off `web.py` 2026-08-11) and the phone's own set editor (`actions_update`: validate against the pool, write only owner-owned keys, re-broadcast `actions`) — [about](__about/actions_api.md) |
| `cursor_api.py` | Standard | the `cursor` message ON THE WIRE — PC pointer position + shape at `cursor_hz`, sent only on change, plus the UIPI input-blocked toast — moved off `web.py` 2026-08-15 (THE STRUCTURE LAW) — [about](__about/cursor_api.md) |
| `config_api.py` | Standard | the `config` frame ON THE WIRE — the phone's full view reset, assembled from the other modules' fields plus the optional `codec` and `stream_region` (owner order 2026-08-12: the encoder crops to the focused layout, and this frame tells the page what rect the video really covers) — moved off `web.py` 2026-08-12, the actions_api precedent — [about](__about/config_api.md) |
| `monitor_api.py` | Standard | the phone's MONITOR protocol — the list of streamable screens that rides the `config` frame, and a switch that can be told WHICH one (task 155); split off `web.py` 2026-08-09 — [about](__about/monitor_api.md) |
| `traffic.py` | Standard | every byte to and from the phone, sampled per second and recorded — the owner's instrument for "does it run while the screen is off" — [about](__about/traffic.md) |
| `traffic_history.py` | Algorithmic | reads months of `traffic.csv` off the UI thread and folds it into a bounded number of chart points — [about](__about/traffic_history.md) · [flow](__flow/traffic_history.md) |
| `traffic_stream.py` | Standard | what the encoder was DOING when these bytes went out — the per-second fps / res / bitrate / crop / sent-size / zoom descriptor appended to every `traffic.csv` row and named on the chart's hover card (T106, 2026-08-15) — [about](__about/traffic_stream.md) |
| `traffic_devices.py` | Standard | which PHONE the traffic belongs to — a resolution-keyed identity, a persisted colour slot, session-length/rate arithmetic, and the cache of the human model name — [about](__about/traffic_devices.md) |
| `device_names.py` | Standard | what the phone is CALLED: an Android model code (`SM-S938B`) becomes "Samsung Galaxy S25 Ultra" via ONE online lookup against Google's own Play device list, off every thread that matters, never a guess (T74) — [about](__about/device_names.md) |
| `grids.py` | Algorithmic | the GEOMETRY of a layout: the region the phone frames and the cells each grid cuts it into — the owner's catalogue of 2026-08-07 (2 / 3×4 arrangements / 4), pure arithmetic — [about](__about/grids.md) · [flow](__flow/grids.md) |
| `window_manager.py` | Standard | the DESK primitives (Phase F+ step 1) — enumerate/hit-test/arrange/raise/CLOSE windows and the topmost ledger; re-exports the registry — [about](__about/window_manager.md) |
| `layout_registry.py` | Standard | the session-scoped layout LIST and its policy (`Layout`/`LayoutRegistry`) — verified arrangement, the resume pointer, `layout_state`; split off `window_manager.py` 2026-08-09 — [about](__about/layout_registry.md) |
| `layout_state.py` | Standard | what a connected phone is TOLD about the layouts — the `layout_state` frame alone (`member_hwnds`, `dependents`/⭐, the prune the focus follows); split off `layout_registry.py` 2026-08-14 — [about](__about/layout_state.md) |
| `window_icons.py` | Standard | an exe path to the real app icon as a PNG data URI, cached per path; split off `window_manager.py` 2026-08-08 — [about](__about/window_icons.md) |
| `uia.py` | Algorithmic | the UI Automation layer — tab hit-test + extraction to a window (app command / Explorer path / SendInput drag), `next_input`'s walk through text fields, and the caret read [Caret](__about/caret.md) needs — [about](__about/uia.md) · [flow](__flow/uia.md) |
| `pairing.py` | Standard | token generation, LAN/Tailscale IP discovery, QR code — [about](__about/pairing.md) |
| `monitors.py` | Standard | physical monitor rects in virtual-desktop coordinates — [about](__about/monitors.md) |
| `clipboard.py` | Standard | screenshot frames into the Windows clipboard as CF_DIB — [about](__about/clipboard.md) |
| `updates.py` | Standard | desktop update discovery via GitHub Releases — [about](__about/updates.md) |
| `update_handover.py` | Algorithmic | installing a new version WITHOUT losing the session you are installing FROM — verify, tell the phone, hand this PC to a detached script that installs silently and starts an app again whatever happened — [about](__about/update_handover.md) · [flow](__flow/update_handover.md) |
| `autostart.py` | Standard | "Start with Windows" as a switch over WINDOWS — the real Task Scheduler logon task read and written, never a preference that only pretends — [about](__about/autostart.md) |
| `foreground_lock.py` | Algorithmic | Windows' own "no program may steal the foreground" setting, borrowed for this session only and given the topmost ledger's discipline so it can never be left behind — [about](__about/foreground_lock.md) · [flow](__flow/foreground_lock.md) |

### `gui_main.py` / `gui/` — Desktop App
PySide6 window (status, in-window QR) + tray around the server core, with three windows behind icon buttons — Controls, Traffic and (since round R2) Settings; `--minimized` starts in the tray. See [GUI (subfolder)](gui/___gui.md).

Action sets for the radial wheels are defined in [actions.json](../ACTIONS.md) at the project root (hand-edited by the owner) and served by [Web Layer](__about/web.md).

## Connections

### Uses
- [Client (folder)](../client/___client.md) — static files served to the tablet

### Used by
- Desktop app: `python server/gui_main.py` (what the packaged EXE runs — see [Setup (folder)](../setup/___setup.md))
- Headless dev CLI: `python server/main.py` (venv: `.venv`)
- [Tests (folder)](../tests/___tests.md) — `test_input_pipeline.py` drives the real [Web Layer](__about/web.md) app end to end
- [Setup (folder)](../setup/___setup.md) — packages `gui_main.py` as the PyInstaller entry point

## Design Decisions

- **Frames and input share one WebSocket.** JPEG mode: a per-client queue of size 1 drops stale frames when the tablet lags. H.264 mode: bytes are a continuous stream and can never be dropped individually — a client that falls a whole queue behind gets its session reset (fresh init segment + keyframe) instead of accumulating latency.
- **One ffmpeg per client, capture shared** — each client's stream starts with its own init segment and keyframe (no mid-stream joining), and capture+encode run only while at least one client is connected.
- **A RE-open is not a first open** (owner's #1 report 2026-08-10 — "changing the bitrate kills the whole app"). The phone's quality panel can only be applied by swapping encoders, so the gap between two of one client's sessions is a working state: capture is HELD across it (`h264_streamer.hold_source` — with a single client, closing the old session used to tear dxcam down, and the new ffmpeg then had no frame to encode, so it wrote no init segment and the open timed out), and a re-open that still fails is retried rather than closing a socket that also carries input, layouts and dictation. A FIRST open that fails is still fatal at once. Gate: [`tests/test_quality_reset.py`](../tests/___tests.md).
- **No input before auth** — the socket closes (4401) unless the first message is a valid `auth` within 5 s.
- **Downscale before encode** — a 4K monitor at native resolution is ~216 Mbps of JPEG; capped at `max_stream_width` (1600 px). With H.264 the same screen streams natively at ~3.6 Mbps.
- **The client draws the cursor** — DXGI frames never contain the pointer, so the server streams `GetCursorPos` (normalized, on change) and the client renders a virtual cursor.
- **DPI awareness is declared in `bootstrap.py`, called first by both entry points** — a root architecture constraint (see project [CLAUDE.md](../CLAUDE.md)).
- **`main.py` stays a one-line-of-logic Trivial file.** `server_core.py` owns everything the CLI used to wire inline (stream-mode decision, injector, pairing, uvicorn) precisely so both entry points — CLI and GUI — share one implementation; `main.py`'s only job left is the console-pairing flag.
