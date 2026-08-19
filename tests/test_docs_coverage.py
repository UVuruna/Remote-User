"""Guard: MD-First 2.0 tier coverage (rules/DOCS.md -> Tiers). Every source
file must have the docs its tier requires:

  Trivial     -> no own doc (a one-line mention in the folder's ___folder.md)
  Standard    -> __about/{name}.md
  Algorithmic -> __about/{name}.md AND __flow/{name}.md
  tests/      -> no own doc (___tests.md folder doc covers the whole folder)

`{name}` is the source file's basename without extension, e.g.
`server/config.py` -> `server/__about/config.md`.

The tier lists below are the single source of truth for tier assignment
(DOCS.md: "changing a file's tier means updating this test in the same
commit"). Any project source file not listed in exactly one tier is a build
failure — an unclassified file is exactly the drift this guard exists to
catch.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _guards_common import PROJECT_ROOT, iter_source_files  # noqa: E402

# Trivial: glue/__init__/re-exports/<~60 lines of plain wiring. One line in
# the parent ___folder.md only — no __about/__flow doc of their own.
TRIVIAL = {
    "server/main.py",
    "server/gui/__init__.py",
    "android/app/src/main/java/com/uvuruna/vibecoder/Prefs.kt",
}

# Standard: ordinary module. Needs __about/{name}.md only.
STANDARD = {
    # THE DESIGN LAB, new 2026-08-19 — the workshop page where every look of
    # every control is on screen at once and Save writes a tuned value back
    # into the file it came from. The server and the page script share
    # __about/design_lab.md (the layouts.js / layouts.css precedent — one doc
    # per JOB, not per file); the specimen board and the registry each carry
    # their own, because "what is on the bench" and "which values are tunable
    # and why is each grouped where it is" are the two questions a reader
    # actually arrives with.
    # The markup and the chrome share that doc too, and are listed here rather
    # than as Trivial for a mechanical reason worth writing down: the tier
    # table maps a file to `__about/{basename}.md`, so a Trivial file whose
    # basename matches a Standard one reads as a STRAY doc on that name. Four
    # files, one job, one doc — the layouts.js / layouts.css precedent.
    "tools/design_lab.py",
    "tools/design_lab.js",
    "tools/design_lab.html",
    "tools/design_lab.css",
    "tools/preview.html",
    "tools/design_tokens.py",
    # Round 2 (2026-08-19). The catalogue split away from the engine at the
    # structure wall: `design_tokens.py` says where a value lives and how it is
    # written, `design_groups.py` says which knobs exist, in which group, what
    # each one is FOR and which specimen it points at. Two questions, two docs.
    "tools/design_groups.py",
    # The mini diagrams — one picture per KIND of number (a radius, a gap, a
    # halo). Its own doc rather than a paragraph inside design_lab.md, because
    # what a reader wants from it is the VOCABULARY: which ids exist and what
    # each one is supposed to be saying.
    "tools/design_pics.js",
    # Developer tools (owner 2026-08-19): the five taps on the title, and the
    # rule about what may and may not sit behind them.
    "server/gui/developer_mode.py",
    # New 2026-08-16 (the owner's blue-screen report): a bounded three-rung
    # ladder (abandon -> reopen -> re-enumerate) plus one guard thread that
    # judges a single fact (did a frame arrive). No branching state machine
    # worth its own diagram — the ladder's order IS the whole flow, and it
    # reads straight off the __about doc.
    "server/capture_recovery.py",
    # Split out of MainActivity.kt 2026-08-18 (VC-R7): the default-network
    # callback, mirroring Updater's watch/release shape. Standard — one
    # callback with two overrides; the reasoning is prose, not a diagram.
    "android/app/src/main/java/com/uvuruna/vibecoder/ConnectivityWatcher.kt",
    # Split out of layout_api.py 2026-08-18 (VC-R6): the T76 zoom
    # arithmetic, pure and callerless. Standard — two derivations and three
    # guards; what a diagram would have to draw is the owner's five rounds,
    # and those are prose in docs/DECISIONS.md section 27.
    "server/layout_zoom.py",
    # Split out of gui/main_window.py 2026-08-18 (VC-R3) on its own banner:
    # the window's power over the server it wraps. Standard — four methods
    # and a worker rule; the DIAGRAM that matters is the exit funnel, and it
    # is drawn once, in server_core's flow.
    "server/gui/main_window_server.py",
    # Split out of gui/main_window.py 2026-08-18 (VC-R3) on its own banner:
    # the update state machine. Standard rather than Algorithmic — the
    # states are a straight line (found -> downloading -> ready -> launched),
    # and the handover THEY end in already carries its own flow doc.
    "server/gui/main_window_updates.py",
    # Split out of layout_popup.py 2026-08-18 (VC-R5): the cheap Windows
    # readings the popup rules are decided on, and the seam every popup gate
    # replaces. Standard — three readings, no logic beyond the reading.
    "server/desk_facts.py",
    # Split out of layout_popup.py 2026-08-18 (VC-R5): the offer registry and
    # `pick()`. Standard — a dictionary with a TTL and one dispatch on the
    # act he tapped; the DECISIONS it serves are documented next door.
    "server/popup_offers.py",
    # Split out of notify.py 2026-08-18 (VC-R4): WHERE a notice happened.
    # Standard — a lookup with two ordered fallbacks (conversation title,
    # then project folder); a diagram would restate the four ifs.
    "server/notify_layout.py",
    # Split out of notify.py 2026-08-18 (VC-R4): the desktop switch that
    # registers Claude Code's hooks. Standard — file copies and a settings
    # write, plus the four sentences it is allowed to print.
    "server/agent_hook_switch.py",
    # Split out of gui/traffic_window.py 2026-08-18 (VC-R4): two pure
    # functions and the span table. Standard — the quantization rule is
    # one expression, and its WHY is prose, not a diagram.
    "server/gui/traffic_spans.py",
    # Split out of gui/traffic_window.py 2026-08-18 (VC-R4): the drawn
    # legend swatch. Standard even though it is a widget — nature beats
    # the band (DOCS.md): four paint branches a diagram would only echo.
    "server/gui/traffic_legend.py",
    # New 2026-08-17 (his ruling on the UIPI alarm: "why would we have things
    # that do not do what they are supposed to do" — measure, or delete).
    # Standard: four independent readings of the environment (our own token,
    # the foreground window, its process, its integrity level) plus one
    # sentence built out of what was found. Every field is nullable and no
    # branch invents a cause, so there is no flow to draw — the __about doc
    # carries what is measured and what is deliberately left unknown.
    "server/elevation.py",
    # New 2026-08-16/17 (constraint 30's other half — react to the display
    # EVENT instead of polling). Standard, not Algorithmic: the same
    # message-only-window thread shape focus_hook.py already carries at
    # Standard (see its own tier note below), plus a Qt-first/winapi-fallback
    # pick and a straightforward tuple diff — no real state machine, no
    # branching worth a picture; the __about doc reads it straight off the
    # code, same as its sibling.
    "server/display_watch.py",
    # Split out of gates.py on 2026-08-16 (THE STRUCTURE LAW), by
    # RESPONSIBILITY: the gates that prove the PC's OWN Qt windows, apart from
    # the ones that prove the wire and the phone. Standard rather than its
    # parent's Algorithmic tier — it is four subprocess calls in a row, each
    # explained where it stands; there is no order to reason about and no
    # state, so a flow page would draw a straight line.
    "setup/gates_desktop.py",
    # Split out of gates.py the SAME day (THE STRUCTURE LAW), by
    # RESPONSIBILITY: the gates that prove the CAPTURE/ENCODE/DECODE/DRAW
    # path — that the owner actually sees a picture — apart from the ones
    # that prove protocol/layout/input/actions/docs. Standard rather than
    # its parent's Algorithmic tier for the same reason as its sibling
    # above: seven subprocess calls in a row, each explained in place, no
    # order to reason about and no state.
    "setup/gates_picture.py",
    # Split out of gates.py on 2026-08-17 (THE STRUCTURE LAW, the third time
    # that file crossed the wall), by RESPONSIBILITY: the five gates that prove
    # the app can ACCOUNT FOR ITS OWN RUN — the use log opened, written, rolled,
    # closed, shipped and summed — apart from the ones that prove the wire and
    # the phone. Standard rather than its parent's Algorithmic tier for exactly
    # the reason its two siblings above are: five subprocess calls in a row,
    # each explained where it stands, no order to reason about and no state.
    "setup/gates_log.py",
    # New 2026-08-14 (T94, the version-skew round): the page must not outlive
    # its own protocol — one pure decision (remember the first config's
    # app_version, reload on any different one), no state machine beyond a
    # single remembered string. Gate: tests/test_zoom_crop.py section 12.
    "client/page-version.js",
    "server/gui_main.py",
    # New 2026-08-12 (THE STRUCTURE LAW — main_window.py stands at the
    # 1,000-line wall): the window's blocking work, off the window's thread.
    # Standard: one thread helper plus the two slow calls that used to freeze
    # the GUI (the pairing probe, the quit's shutdown). No state machine, no
    # geometry — and its one promise is gated in tests/test_gui_nonblocking.py.
    "server/gui/offthread.py",
    "server/bootstrap.py",
    "server/pairing.py",
    "server/monitors.py",
    # Split out of web.py on 2026-08-09 (THE STRUCTURE LAW — task 155's two
    # `config` fields arrived while that file sat exactly on 1,000 lines).
    # Standard, not Algorithmic: two protocol handlers over `monitors`, with
    # no state machine and no geometry of its own to draw.
    "server/monitor_api.py",
    # New 2026-08-11 (THE STRUCTURE LAW — web.py stands at the 1,000-line
    # wall and neither handler belonged to monitor_api or layout_api). The
    # Claude Code half of the protocol: focusing its prompt before a typed
    # command, and answering what the conversation is running now. Standard:
    # transport only — the keystrokes live in content.py and the transcript
    # read in agents.py, each already covered.
    "server/claude_api.py",
    # New 2026-08-17 (T111 — the session ledger). Standard, exactly like
    # claude_api.py right above: the project comes from Layout.project(),
    # measured live, and this module is transport only — one message
    # answered from what session_ledger.py already parsed. No state machine
    # of its own to draw.
    "server/ledger_api.py",
    # New 2026-08-17 (T111). The parser is a single-pass stack walk over
    # indented lines (task line, then its own >/?/! annotations one level
    # deeper) — a real loop, but a straight one: no branching state machine,
    # no backtracking, and the frozen grammar in server/__about/session_ledger.md
    # already narrates it end to end in prose. A flowchart here would restate
    # the code (DOCS.md's own test for the flow tier), so Standard, not
    # Algorithmic — matching this file's own doc, which carries no Flow link.
    "server/session_ledger.py",
    # New 2026-08-18 (his "I have to press No a thousand times" report, and
    # THE STRUCTURE LAW — layout_popup.py stood at the 1,000-line wall again).
    # Standard, not Algorithmic: one pass over the open offers asking a single
    # measured question (is the window still alive), plus the bookkeeping that
    # follows a yes. No state machine and no geometry — the __about doc reads
    # the four steps straight off the code.
    "server/offer_withdraw.py",
    # New 2026-08-19 (his repeat of constraint 19 one layout over — a VS Code
    # dialog offered as a new layout). Standard: one pass over the desk asking
    # two measured questions (is it a dialog, whose is the root), one centred
    # move, one notice. The ladder with geometry stays in popup_contain.py.
    "server/dialog_center.py",
    # New 2026-08-11 (task 184 — a layout from a window that is not open yet).
    # Standard: three READS of places other apps keep their own recent lists,
    # plus a launch and a wait. The one rule with teeth — only a handle that
    # was NOT standing before the launch may be handed back — is a comparison,
    # not a flow, and it is gated in tests/test_layout_birth.py.
    "server/recents.py",
    # New 2026-08-13 (owner ballot, T29 — the New panel opened from INSIDE a
    # layout offers its own app's acts first). Standard: a catalogue keyed by
    # process plus a dispatcher, whose one rule with teeth — the PROCESS is
    # asserted before a single key goes out — is the same fence
    # content.palette_command already makes, and is gated in
    # tests/test_new_source.py.
    "server/layout_acts.py",
    # Split out of layout_popup.py on 2026-08-17 at the structure law's wall,
    # by RESPONSIBILITY: every other rule there is a GUESS about a window
    # nobody told us anything about, while this is the maker's own statement
    # that a window is ours. Standard: two records and one question, whose one
    # rule with teeth — the claim is armed BEFORE the act, never after — is
    # what closed the race the owner reported.
    "server/window_claim.py",
    # Split out of layout_popup.py in the same round, also by responsibility:
    # this pass asks whether he can REACH a window, which geometry answers
    # outright and which therefore needs no history — the one pass that can
    # speak for a window opened before the phone ever connected. Standard: a
    # throttled sweep over lost_windows.py's own measurement.
    "server/window_rescue.py",
    # Split out of layout_api.py on 2026-08-17 at the structure law's wall, by
    # RESPONSIBILITY: layout_api answers what layouts exist and what may be
    # done TO them, while these two handlers ask what the program a layout is
    # MADE OF can be asked to do — which touches no layout and creates no
    # member. Standard: two handlers and one rule with teeth (the act runs OFF
    # the receive loop, or it starves this connection's own heartbeat), gated
    # in tests/test_new_source.py.
    "server/layout_acts_api.py",
    # Split out of web.py on 2026-08-13 at the structure law's wall, by
    # responsibility: web.py's subject is the live SOCKET, and an upload is a
    # plain request/response that happens to end in one injected Ctrl+V.
    # Trivial: two routes, moved unchanged, with no logic of their own.
    "server/upload_api.py",
    # New 2026-08-11 (task 228 — the "Recent" creation source). Standard: a
    # persisted, capped, deduped log with a dedupe key and a fuzzy re-match —
    # each promise is a comparison over a member list, not a state machine or
    # geometry of its own, and every one is gated in tests/test_layout_history.py.
    "server/layout_history.py",
    # New 2026-08-11 (owner 2026-08-04 order, task 182 — the clipboard lives
    # on both devices). Standard: a Win32 clipboard read, a message-only
    # listener window on focus_hook's proven thread shape, and the held-while-
    # away/echo-guard policy — each promise gated in test_clipboard_sync.py.
    "server/clipboard_sync.py",
    # New 2026-08-15 (owner report — the Claude wheel stayed silent on a
    # freshly built layout until Desktop and back). Standard: a per-connection
    # poll that computes a comparable signature and re-sends layout_state
    # through the existing choke point only when it moved. Gate:
    # tests/test_agents_refresh.py.
    "server/agents_refresh.py",
    # New 2026-08-11 (task 182, page half). Standard: one push handler —
    # Android.setClipboard inside the APK, navigator.clipboard in a browser.
    "client/clipboard.js",
    # New 2026-08-11 (task 187 closer c). Standard: the concurrency rehearsal
    # that proves the installer's one-handover mutex with throwaway NSIS stubs.
    "setup/rehearse_update.py",
    # New 2026-08-11 (task 187 closer d). Standard: the release refusal while
    # his machine's update.json says a handover is in flight.
    "setup/release_hygiene.py",
    # New 2026-08-11 (owner 2026-08-04, task 218b). actions.json ON THE WIRE:
    # the reader and the shipped-pool merge moved off web.py, plus the phone's
    # own set editor (`actions_update`). Standard: the validation is a handful
    # of shape checks and the ownership contract it enforces is declared in
    # gui/controls_data.py, which already carries the rule and its own doc.
    "server/actions_api.py",
    # New 2026-08-12 (THE STRUCTURE LAW — web.py stood at the 1,000-line wall
    # again): the `config` frame's wire shape, the actions_api precedent (one
    # module owns one message's fields). Standard: it assembles fields other
    # modules build and adds two optional ones (codec, stream_region); the
    # region-crop decision it ships lives in h264_streamer/layout_api.
    "server/config_api.py",
    # New 2026-08-15 (THE STRUCTURE LAW — web.py at the wall a third time): the
    # `cursor` message's one sender, the config_api precedent. Standard.
    "server/cursor_api.py",
    # New 2026-08-15 (T106): the per-second stream descriptor beside every
    # traffic sample — six CSV cells and the hover card's words. Standard:
    # a reader/writer pair over values the encoder already resolved.
    "server/traffic_stream.py",
    "server/window_manager.py",
    # Split out of window_manager.py on 2026-08-09 (THE STRUCTURE LAW — the
    # pos-anchor round pushed it past 1,000 lines). The registry holds the
    # session's layout list and its policy; window_manager keeps driving the
    # real windows. Standard: the policy it carries (verified arrangement,
    # the pos anchor) is explained in its __about; the geometry itself lives
    # in grids.py and client/view-anchor.js, each with its own coverage.
    "server/layout_registry.py",
    # Split out of layout_registry.py on 2026-08-14 (THE STRUCTURE LAW — that
    # file stood at exactly 1,000 lines and `member_hwnds` could not land in
    # it). By responsibility: the registry owns the WINDOWS, this owns what a
    # connected phone is TOLD about them. Standard — it carries one real
    # decision (who is a parent, and which apps' torn-out content still
    # depends on its origin window) and that decision is explained in its
    # __about; everything else is assembling a frame from facts read live.
    "server/layout_state.py",
    # New 2026-08-08 (task 116 forced the split — window_manager.py sat at
    # exactly 1,000 lines). One function, one job: an exe path to a PNG data
    # URI. Standard, not Algorithmic — it carries no decision, only shell+GDI
    # plumbing, and its whole policy is "an icon is never a failure".
    "server/window_icons.py",
    "server/clipboard.py",
    "server/updates.py",
    # New 2026-08-16 (owner request — the use log's evidence-and-behaviour
    # record). Standard, not Algorithmic: rolling by day boundary or size and
    # footer-on-close are each one straightforward rule, explained in prose in
    # its __about — no state machine, no background thread, nothing a diagram
    # would tell better than the code.
    "server/session_log.py",
    # New 2026-08-16 (owner ruling — spans/totals arithmetic over one
    # session_log.py file, split out by RESPONSIBILITY: writing lines
    # correctly is session_log.py's job, reading them back into spans is a
    # different one with its own honest edge cases). Standard, not
    # Algorithmic: `spans()` is one straightforward walk-and-compare loop,
    # explained in prose in its __about — no state machine worth a diagram.
    "server/log_summary.py",
    # New 2026-08-16 (owner request — a finished log leaves the user's disk).
    # Standard, not Algorithmic: copy-verify-delete is one straightforward
    # ordering rule, explained in prose in its __about — no state machine
    # complex enough to need a diagram, just a rule that must never be
    # reordered.
    "server/log_shipper.py",
    "server/traffic.py",
    # New 2026-08-13 (owner request — the Traffic window's per-device list
    # and per-device chart colour). Standard, not Algorithmic: the one real
    # decision it carries ("a device is identified by its resolution, and a
    # name may only ever REPLACE that key — never change it") is one
    # sentence in its __about; there is no state machine and nothing worth a
    # flow diagram.
    "server/traffic_devices.py",
    # New 2026-08-13 (T74, owner decision — a model code becomes the name he
    # calls the phone, via ONE online lookup against Google's own Play device
    # list, cached forever). Standard, not Algorithmic: it is a fetch, a
    # dict lookup and a worker queue. The decisions it carries (WHY that
    # source survives "a new phone appears", and why a network failure is a
    # third answer rather than a negative) are prose in its __about — there
    # is no state machine and nothing worth a flow diagram.
    "server/device_names.py",
    # New 2026-08-09 (owner request, task 142 — the phone drew one fixed
    # arrow): the live HCURSOR matched against the system cursors and turned
    # into a name. Standard, not Algorithmic — the only decision it carries
    # ("an unmatched handle is `custom`, never a guess") is one sentence in
    # its __about; the drawing that name causes lives on the phone.
    "server/cursor_shape.py",
    # New 2026-08-07 (round R2): "Start with Windows" is a real Task Scheduler
    # task, read and written — one responsibility, no flow worth a diagram.
    "server/autostart.py",
    # New 2026-08-07 (build round R1): the SetWinEventHook listener thread.
    # Standard, not Algorithmic — it carries no decision of its own, only the
    # Win32 plumbing that tells focus_guard the foreground moved. The policy,
    # and the flow diagram, stay with the guard.
    "server/focus_hook.py",
    "client/index.html",
    "client/install.html",
    # New 2026-08-09 (owner decree — the position lives on the PHONE): the
    # fit-and-anchor math for the letterboxed picture, split into a pure
    # module so tests/test_view_anchor.py can run it whole (the caret.js
    # pattern). Standard: one formula, no flow worth a diagram — the WHY
    # lives in its header and its __about.
    "client/view-anchor.js",
    # New 2026-08-14 (owner report T76 — "why is downscaling done even when
    # the picture is zoomed"): the zoom's own crop — the layout FLOOR the crop
    # may never widen past, and the gesture SETTLE that keeps one region
    # change per finished gesture. Pure so tests/test_zoom_crop.py can run it
    # whole (the view-anchor.js pattern). Standard: two small rules, no flow
    # worth a diagram — the WHY lives in its header and its __about.
    "client/zoom-crop.js",
    # New 2026-08-12 (owner report — "native 20 Mbps still sends no
    # picture"): the device's own H.264 decode ceiling — level table, smooth-
    # fps pick, cap and runtime-backstop rules — split into a pure module so
    # tests/test_decode_caps.py can run it whole (the view-anchor.js pattern).
    # Standard: tables and threshold picks, no flow worth a diagram — the WHY
    # lives in its header and its __about; quality.js keeps the wiring.
    "client/decode-caps.js",
    # New 2026-08-09 (owner report, task 162 — he held a layout row and the
    # layout opened): when a press is a hold, a drag or a tap. Split into a
    # pure module so tests/test_hold_gesture.py can drive it with a realistic
    # jitter sequence — the old rule lived inline in a listener, which is why
    # it was never tested. Standard: one decision, no flow worth a diagram.
    "client/hold-gesture.js",
    # New 2026-08-15 (owner report — a finger landing on a language row could
    # not scroll the card): the ONE row activator, moved out of
    # layout-create.js where task 227b had fixed it for that panel alone.
    # Standard: one wiring function and the rule about where it belongs.
    "client/row-tap.js",
    # New 2026-08-09 (owner request, task 142 — the cursor must show what the
    # pixel under it does): the drawn silhouette per cursor name, split into a
    # pure module so tests/test_cursor_shape.py can run it whole (the
    # view-anchor.js pattern). Standard: one table and one translate, no flow
    # worth a diagram — the WHY lives in its header and its __about.
    "client/cursor-shapes.js",
    # Split out of layout-create.js on 2026-08-13, at the structure law's wall
    # and by responsibility: that file is the WIZARD (it owns `creating` and
    # ends in one layout_create), while this one is about the PC's own
    # programs — what they can OPEN and what the focused layout's app can DO.
    # Standard: two lists and two messages; every rule with teeth lives on the
    # server (server/recents.py, server/layout_acts.py).
    "client/layout-new.js",

    # New 2026-08-09 (owner request, task 164 — a row of the layout list said
    # nothing about its SHAPE): the drawn silhouette per (member count,
    # arrangement, orientation), split into a pure module so
    # tests/test_grid_icons.py can run it whole (the cursor-shapes.js pattern)
    # and so the partitions have ONE copy on this side. Standard, not
    # Algorithmic: it carries no decision the sheet did not already make — the
    # catalogue is the owner's drawing and the WHY lives in its header and its
    # __about; grids.js keeps the flow (which panel asks what).
    "client/grid-icons.js",
    # New 2026-08-09 (owner, task 175 — one common ⚙ instead of one icon per
    # act): the per-layout settings sheet and the panels it opens (rename,
    # aspect ratio, orientation, arrangement). Split out of layouts.js the day
    # that file crossed 1,000 lines. Standard, not Algorithmic — it is a MENU
    # and the panels behind it: the one rule it carries ("offer only what this
    # layout can take") is a sentence in its __about, and the flow it belongs
    # to is the layout list's, documented once in client/__flow/layouts.md.
    "client/layout-settings.js",
    # New 2026-08-11 (owner report, task 194 — the loading cube overstayed on
    # a busy screen). The settle-watcher's motion metric, split out of
    # loading.js into its own pure module so tests/test_loading_settle.py can
    # run it whole in node (the view-anchor.js pattern) — loading.js still
    # holds the DOM-touching watcher/cube plumbing and its own timing
    # constants. Standard, not Algorithmic: one formula (changed-pixel
    # fraction vs. a threshold), no flow worth a diagram — the WHY lives in
    # its header and its __about.
    "client/settle-motion.js",
    # New 2026-08-10 (owner decree, task 207 — a frozen "Downloading…"
    # ellipsis told him nothing about whether the app had hung). Split out of
    # controls.js the same round it crossed 1,000 lines: the in-app APK
    # update offer — version compare, show/hide, and the tap that swaps the
    # banner into an indeterminate progress bar. Standard, not Algorithmic:
    # one comparison and one DOM swap, no flow worth a diagram — the WHY
    # lives in its header and its __about.
    "client/update-banner.js",
    "client/update-banner.css",
    # New 2026-08-17: the loading cube's motion, extracted out of loading.js
    # so the update card's badge cube and the full overlay's cube can each
    # spin independently without a second copy of the face table and the
    # burst/decay maths (priority C — never write the same function twice).
    # Standard, not Algorithmic: one state object (view/tilt/angle/burst) and
    # one requestAnimationFrame step, no flow worth a diagram — the WHY lives
    # in its header and its __about.
    "client/cube.js",
    # New 2026-08-11 (owner amendment to task 202): the two-button chip that
    # asks where a window that just opened on the PC should go — show it in
    # the layout, or leave it on the desktop. Its own pair of files rather
    # than a block in controls.js (that file stands at the line ceiling), and
    # they share one doc the way layouts.css/layouts.js do. Standard: one
    # message in, one POST out, no rule of its own — the decision it carries
    # out lives on the server (server/layout_popup.py).
    "client/window-offer.js",
    "client/window-offer.css",
    "client/load_test.js",
    "client/state.js",
    "client/panels.js",
    # New 2026-08-13: the DICTATION LANGUAGE CARD, split out of panels.js when
    # the grouping pushed that file past 1,000 lines — by RESPONSIBILITY, not
    # line count: panels.js answers which controls ride on the phone, this card
    # answers what the DEVICE IN HIS HAND can hear and speak. Standard, not
    # Algorithmic: the arithmetic it renders lives in client/lang-groups.js;
    # what stays here is a card, its rows, and its honest limits.
    "client/dictation-card.js",
    # panels.css is the overlay CARDS' styling, split out of style.css on
    # 2026-08-09 (THE STRUCTURE LAW — the dictation card's listen control
    # pushed that file past 1,000 lines). It shares __about/panels.md with
    # panels.js, exactly as layouts.css shares its doc with layouts.js: one
    # feature, one doc, two files (the doc names both). Standard, not
    # Algorithmic like style.css: it carries no computed colour and no rule
    # worth a flow — it is the shape of a card and the rows in it.
    "client/panels.css",
    "client/icons.js",
    "client/region.js",
    "client/notify.js",
    "client/quality.js",
    # New 2026-08-13: the CATEGORY WHEEL, split off controls.js when the
    # rotation fix pushed that file past 1,000 lines. Standard, not
    # Algorithmic: the ring's real arithmetic (the derived radius and the
    # shrink ladder) lives in chrome.js, which already carries a flow page —
    # this module opens, fills, closes, and re-lays-out.
    "client/wheel.js",
    # New 2026-08-11 (owner ballot verdict — tasks 190/191/208): the DOM half
    # of the three Claude Code cards. Standard: it draws chips and rows and
    # sends; every rule it obeys lives in claude-state.js below, which is where
    # the flow is.
    "client/claude-panels.js",
    # New 2026-08-17 (T111). Two files, one doc — the panels.js/panels.css
    # precedent, and here it falls out for free: both files share the
    # basename "ledger-panel". Standard, same reading as claude-panels.js
    # right above: it draws a card, its rows and an answer field, and sends
    # one message; the grammar/state rules it renders live in
    # server/__about/session_ledger.md, which this doc links to.
    "client/ledger-panel.js",
    "client/ledger-panel.css",
    # New 2026-08-11 (owner tasks 161 + 218a): one card gathering the switches
    # that describe THIS device. Standard without argument — five rows over
    # helpers that already exist, and not one decision of its own.
    "client/phone-panel.js",
    # New 2026-08-12 (owner ballot — appearance is per device): the card where
    # a handset picks its own theme, colour and fill. Standard for the same
    # reason phone-panel.js is — three rows over helpers that already exist;
    # every rule about what a stored choice DOES lives in theme.js below,
    # which is the Algorithmic half of the pair.
    "client/appearance-panel.js",
    # New 2026-08-11 (owner 2026-08-04, task 218b): one set's own editor on the
    # phone — which pool commands ride and in which slot. Standard: it draws
    # rows and a preview and sends ONE message; every rule that decides whether
    # the edit is legal lives on the PC (server/actions_api.py), which is where
    # the ownership contract and the gate are.
    "client/set-editor.js",
    # Its two surfaces, sharing __about/set-editor.md with the script exactly as
    # panels.css shares one with panels.js: the arrangement preview and the edit
    # door on a picker row. Everything else it wears is panels.css's `.sets-*`.
    "client/set-editor.css",
    "setup/create_cert.py",
    "setup/agent_hook.py",
    # New 2026-08-17 (T111). Standard, same reading as agent_hook.py right
    # above it: a self-contained, dependency-free hook script with two modes
    # (prompt/stop) and a grammar-validity check that mirrors
    # session_ledger.py's parser — duplicated on purpose (this script must
    # run with nothing on sys.path but the standard library) rather than a
    # second algorithm. No new decision logic beyond what session_ledger.py
    # already documents.
    "setup/ledger_hook.py",
    "android/app/src/main/java/com/uvuruna/vibecoder/Notifier.kt",
    "android/app/src/main/java/com/uvuruna/vibecoder/OnboardingActivity.kt",
    "android/app/src/main/java/com/uvuruna/vibecoder/VoiceInput.kt",
    # Split out of MainActivity.kt on 2026-08-07 (THE STRUCTURE LAW): the JS
    # bridge is the PAGE's protocol surface, a different job from being the
    # window. Standard, not Algorithmic — it carries no decision of its own,
    # only the adapter between two sides that version independently.
    # New 2026-08-09 (THE STRUCTURE LAW): what the window's EDGES do — the
    # system bars we hide and the keyboard inset only the shell can measure.
    # Standard: one dependency (WindowInsets), no decision of its own; the
    # rule that USES the keyboard height lives on the page (client/caret.js).
    "android/app/src/main/java/com/uvuruna/vibecoder/Insets.kt",
    # New 2026-08-14 (T80a, THE STRUCTURE LAW): which layer is on screen and
    # whether the screen may stay lit — one question, one dependency (the
    # window). Standard: the decision it holds is four booleans and an
    # ownership rule, not an algorithm worth a flow diagram.
    "android/app/src/main/java/com/uvuruna/vibecoder/ScreenAwake.kt",
    "android/app/src/main/java/com/uvuruna/vibecoder/Bridge.kt",
    # New 2026-08-17: streams the PC's own /app.apk straight into a
    # PackageInstaller session's OutputStream — no file, no FileProvider, no
    # DownloadManager (see its __about for why). Standard, not Algorithmic:
    # one download loop plus one broadcast receiver reading the installer's
    # own status codes into a short sentence — no branching worth a diagram,
    # the ladder is the installer's own contract rather than one this file
    # invents.
    "android/app/src/main/java/com/uvuruna/vibecoder/Updater.kt",
    # Split out of MainActivity.kt on 2026-08-17 (THE STRUCTURE LAW): the
    # error card / network diagnosis moved verbatim as extension functions.
    # Standard: no NEW decision logic beyond what MainActivity's own doc
    # already carried — the diagnosis (no network / PC not on Tailscale /
    # Tailscale missing / Tailscale off / PC down) is read straight off the
    # code, and this is a pure structure-law move, not an algorithm change.
    # New 2026-08-18 (the owner's report: a successful self-update left him
    # hunting for the app on the home screen). A manifest-declared receiver
    # for MY_PACKAGE_REPLACED — its own responsibility precisely because it
    # runs when Updater.kt's process no longer exists. Standard, not
    # Algorithmic: two acts in a fixed order (a best-effort activity start,
    # then the notification that always goes out), no branching and no state
    # — the __about doc carries the WHY (the background-activity-start
    # restriction), which is the only thing here worth reading twice.
    "android/app/src/main/java/com/uvuruna/vibecoder/UpdateReturn.kt",
    "android/app/src/main/java/com/uvuruna/vibecoder/ConnectionError.kt",
    # New 2026-08-07 (build round G1 — the game controller): an ADAPTER, the
    # same reading as Bridge. Platform events in, three page callbacks out; the
    # whole mapping (which button, which curve) lives on the page, so this
    # file carries no decision of its own worth a flow diagram.
    "android/app/src/main/java/com/uvuruna/vibecoder/Gamepad.kt",
    # New 2026-08-07 (owner decree — the waiting channel): the foreground
    # service is Android lifecycle plus the permanent notification the
    # platform demands. The state machine lives in NoticeLink, below.
    "android/app/src/main/java/com/uvuruna/vibecoder/NoticeService.kt",
}

# Algorithmic: real algorithm, GUI window/widget, config/data table, or
# protocol. Needs __about/{name}.md AND __flow/{name}.md.
ALGORITHMIC = {
    "server/server_core.py",
    "server/uia.py",
    "server/config.py",
    "server/capture.py",
    "server/h264_streamer.py",
    "server/encoders.py",
    "server/input_injector.py",
    "server/web.py",
    # Split out of web.py 2026-08-18 (VC-R2): the phone's command registry,
    # one handler per `kind`, replacing a 366-line elif chain. Algorithmic —
    # it IS the protocol's dispatch table, and its flow doc is what the
    # chain's own diagram in __flow/web.md used to be.
    "server/ws_commands.py",
    # Split out of controls.js on 2026-08-06 (THE STRUCTURE LAW): which sets
    # ride the wheel is a rule set of its own — the cap of 8, the per-process
    # reserve, and the owner's per-layout app ticks.
    "client/sets.js",
    # Split out of controls.js on 2026-08-08 (THE STRUCTURE LAW, the same
    # 1,000-line wall sets.js was split off at): WHICH dictated words reach
    # the PC and WHEN. Algorithmic without argument — a settle rule over a
    # revising hypothesis plus the round-boundary overlap trim, and it is
    # kept pure so its gate can run it whole.
    "client/voice.js",
    # Split out of controls.js's `input` handler on 2026-08-13 (owner report:
    # typed text landed before a trailing fragment that no edit could remove,
    # freed only by a blur/refocus). Algorithmic without argument: the
    # mid-string erase-and-retype dance is a real decision that can silently
    # mis-place his text when its own assumption (the field's caret sits at
    # its own end) does not hold, and it is kept pure so its gate can run it
    # whole, the voice.js pattern.
    "client/kb-sync.js",
    # New 2026-08-13 (the 2026-08-13 MEASURED typing-loss defect, HALF 1):
    # `send()` dropped a typing message silently whenever the socket was not
    # OPEN, and a simulation driving the real controls.js + send() proved it
    # amplifies inside an ordinary backspace burst. Algorithmic without
    # argument: the bound (count + staleness) and the all-or-nothing giveup
    # rule are real decisions that trade one failure mode for another if
    # gotten wrong, and it is kept pure so tests/test_type_queue.py can run
    # it whole, the kb-sync.js/voice.js pattern.
    "client/type-queue.js",
    # New 2026-08-13 (owner: both language lists were one flat pile, and the
    # dictation one repeated the same choice). The grouping arithmetic BOTH
    # cards read, pure so tests/test_lang_groups.py runs it whole.
    # Algorithmic without argument: every function in it is a DECISION that
    # can be wrong in a way he would judge — what makes two locales the same
    # (language + RESOLVED script + region, which is why sr-RS and sr-Latn-RS
    # are one row and two choices), what makes an engine's variant a name
    # rather than machinery, and that the GROUP is the unit of that naming.
    # Two of those decisions shipped wrong in this very round and were caught
    # by running the module.
    "client/lang-groups.js",
    # New 2026-08-08 (owner: the keyboard must follow the caret, not a rule).
    # Algorithmic without argument — geometry that decides whether he can read
    # the row he is typing in, kept pure so its gate runs it whole.
    "client/caret.js",
    # New 2026-08-10 (task 151): the live-edge truth table plus the
    # slow-before-flush playbackRate regulator that recovers a starved player
    # without ever flushing the decoder more than once per 4s. Algorithmic —
    # real decision logic with its own state machine (degradedSince/rate),
    # kept pure so its gate (tests/test_live_clock.py) can drive it whole
    # against a realistic drift ramp.
    "client/live-clock.js",
    "client/grids.js",
    # New 2026-08-11 (owner ballot verdict — tasks 190/191/208). Algorithmic
    # without argument: it decides what the phone may CLAIM about a PC it may
    # not have heard from — three different kinds of truth that must never
    # wear each other's clothes — plus the Shift+Tab ring arithmetic, whose
    # honest answer for an unknown start is no answer at all. Kept pure so its
    # gate (tests/test_claude_panels.py) runs it whole.
    "client/claude-state.js",
    # New 2026-08-07 (build rounds G1/G2 — the game controller): the whole
    # mapping lives here, and it is real algorithm — a deadzone-and-power stick
    # curve, a frame-clock stepper, and the polar arithmetic that turns a stick
    # angle into a wheel index.
    "client/gamepad.js",
    # Split out of web.py on 2026-08-05 (THE STRUCTURE LAW): presence is a
    # state machine with its own rules and its own gate, layout_api is the
    # phone's layout protocol. Both are algorithmic — they carry a flow.
    "server/presence.py",
    "server/layout_api.py",
    # Split out of web.py on 2026-08-06 (THE STRUCTURE LAW): WHERE typed input
    # lands is a decision with its own rules (the layout fence, the desktop
    # pin, dialogs, what re-arms it) and its own gate — algorithmic.
    "server/focus_guard.py",
    # New 2026-08-11 (owner eruption, task 202 — an agent's report window
    # opened outside the layout he was watching, where he could see it and
    # not touch it). Algorithmic: an ATTRIBUTION chain with three tiers and
    # named limits (whose window is this?) plus a measured containment
    # decision (does it fit the region, or must it go full screen).
    "server/layout_popup.py",
    # Split out of layout_popup.py 2026-08-18 (VC-R5): WHERE an adopted
    # window is put. Algorithmic — the owner's ladder (parent, region, full
    # screen) is a real decision with a verified placement at every rung.
    "server/popup_contain.py",
    # Split out of layout_popup.py on 2026-08-13, when the popup module crossed
    # the structure law's wall — and by responsibility, not by line count: its
    # subject is a window HE opened (which nothing may touch until he says so),
    # the opposite of the popup module's (a window the LAYOUT'S work opened,
    # which the layout must contain). Sharing one file made them look like one
    # feature, and on 2026-08-12 that cost him a moved window. Algorithmic: a
    # double-click CORRELATION with named limits, and the rule deciding which
    # of the two features owns a window both can claim.
    "server/layout_birth.py",
    # New 2026-08-13 (owner report 2026-08-12 — the FIFTH on one failure: a
    # window that opened while his phone was locked stands off every screen
    # and can never be shown again). Algorithmic: a REACHABILITY test that is
    # deliberately about a title bar rather than about visible pixels, a
    # minimized window judged by where it would restore to, and the first
    # code here that moves a window it did not place.
    "server/lost_windows.py",
    # New 2026-08-08 (owner report 2026-08-07, screenshots again the next day
    # — the phone's keyboard covers the row he is typing into). Algorithmic:
    # a fallback chain across two Windows APIs, a duty-cycled throttle, a hold
    # against popups that steal focus, and the rule that an unknown caret is
    # reported as unknown and never as a position.
    "server/caret.py",
    # Split out of web.py 2026-08-08 (THE STRUCTURE LAW). Algorithmic without
    # argument: an image decode with an ordered fallback chain, and a paste
    # whose ORDER and whose withheld Enter are the whole feature.
    "server/content.py",
    "server/notify.py",
    # Split out of notify.py 2026-08-18 (THE STRUCTURE LAW, VC-R4): HOW a
    # notice travels. Algorithmic without argument — an ordered carrier
    # chain whose whole promise is "exactly one", a per-device channel table
    # displaced by its own sentinel, and an endless generator with a beat.
    "server/notice_channel.py",
    # New 2026-08-07 (owner report — installing killed the session he was
    # installing FROM). Algorithmic without argument: a sequence that spans a
    # process boundary, with an ordering that is the whole design, a rollback,
    # and a record that has to outlive the process being replaced.
    "server/update_handover.py",
    # Split out of traffic.py / gui/traffic_window.py on 2026-08-07 (BUILD
    # ROUND R4, THE STRUCTURE LAW): reading months of traffic.csv into a
    # bounded number of chart points is a real streaming algorithm (a
    # single-pass, O(bucket count) downsample) plus a background-thread
    # handoff — both concrete "earns its flow" signals from DOCS.md.
    "server/traffic_history.py",
    # New 2026-08-06: which agent tools are LIVE on this PC and in which
    # project. Algorithmic — a process table read, a session-id -> transcript
    # -> project mapping, and a cache, all of which have to be explained.
    "server/agents.py",
    # New 2026-08-17: the ⭐'s second source. Algorithmic — a SQLite memento
    # read, a generic grid walk, a title-then-bounds tie-break and a
    # remainder rule, all of which have to be explained.
    "server/vscode_windows.py",
    "server/grids.py",
    "client/loading.js",
    "server/gui/theme.py",
    # Split out of the three windows on 2026-08-06 (THE STRUCTURE LAW): the
    # same settle loop was copied three times and carried the same lie in
    # every copy — how a window declares its true minimum is one rule, and it
    # is algorithmic (a circular measurement that has to converge).
    "server/gui/sizing.py",
    "server/gui/traffic_window.py",
    # Split off traffic_window.py 2026-08-15 at the structure law's wall, by
    # responsibility: the window owns numbers/picker/footer, the chart owns
    # the PICTURE — and now the zoom (drag rectangle, wheel, buttons) and a
    # hover card that names device + stream. Algorithmic (a widget).
    "server/gui/traffic_chart.py",
    # New 2026-08-15 (T104/T105): the chart's time window as pure arithmetic
    # — clamped, floored, anchored zoom; pixels <-> seconds. Algorithmic.
    "server/gui/traffic_zoom.py",
    # Split off traffic_window.py 2026-08-14 at the structure law's wall,
    # by responsibility: how a byte count and a moment become the WORDS on
    # an axis. Algorithmic — the 1/2/5 gridline ladder is scored, not
    # picked, and "one axis, one unit" is a rule a grade already caught.
    "server/gui/traffic_axis.py",
    # Split off traffic_window.py 2026-08-14 (T80d), also by responsibility:
    # that window's subject is BYTES, which the PC counts at its own socket
    # and which therefore always exist; this one's is POWER, which only the
    # phone can measure about itself and which a large share of devices
    # refuse to report. Algorithmic because the RULES are the content — a
    # refusal must be stated in words and never as a zero, and one missing
    # property may never silence the other.
    "server/gui/traffic_battery.py",
    "server/gui/main_window.py",
    # New 2026-08-07 (round R2): the Settings window, and Windows' foreground
    # lock borrowed with a ledger (a state machine with a repair path —
    # algorithmic by the same reading as window_manager's topmost ledger).
    "server/gui/settings_window.py",
    "server/foreground_lock.py",
    # New 2026-08-07 (build round R3 — themes): the sun/moon pill and the
    # snapshot cover the theme changes under. A GUI widget module, same tier
    # as its siblings, and it carries a real flow of its own (grab every
    # window → swap the palette → fade the stale pictures out).
    "server/gui/switch.py",
    "server/gui/controls_editor.py",
    "server/gui/controls_widgets.py",
    # Split out of controls_editor.py / controls_widgets.py on 2026-08-07
    # (build round R5, THE STRUCTURE LAW): controls_data.py is the
    # shipped-pool MERGE and every actions.json path/parse rule — real
    # algorithm, no Qt; controls_order.py is the arrangement/order-editing
    # widgets (the per-set ladder, the new wheel-order ring) — a GUI
    # widget module, same tier as its siblings.
    "server/gui/controls_data.py",
    "server/gui/controls_order.py",
    # Split out of settings_window.py on 2026-08-12 (owner ballot, option A —
    # THE STRUCTURE LAW): the STREAM card, its four named quality steps and
    # the Custom disclosure behind them. A GUI widget module, same tier as its
    # siblings; the one rule it must not get wrong (Data saver IS the mobile
    # data profile) lives in config.DATA_SAVER and is gated.
    "server/gui/stream_card.py",
    # New 2026-08-07 (build round R3 — themes). One doc pair for the two
    # halves of one feature, exactly as layouts.css/layouts.js share theirs:
    # theme.css is every colour token in three themes and two fills, theme.js
    # decides which are in force and computes each set's ink. Algorithmic —
    # the ink is COMPUTED from luminance and the custom-set colours are
    # assigned from a pool, both of which have to be explained.
    "client/theme.css",
    "client/theme.js",
    "client/style.css",
    # layouts.css is the layout feature's own styling, split out of style.css
    # on 2026-08-05. It shares __about/__flow/layouts.md with layouts.js —
    # one feature, one doc, two files (the doc names both).
    "client/layouts.css",
    "client/render.js",
    "client/input-geometry.js",
    "client/controls.js",
    # New 2026-08-08: our own FURNITURE — the Hide button, the auto-hide rule
    # and the toast — split off controls.js when auto-hide crossed 1,000 lines.
    # Algorithmic: the auto-hide fence is a real rule with a list of states
    # that must never let it fire, and that list is the feature.
    "client/chrome.js",
    "client/layouts.js",
    # New 2026-08-08: the creation WIZARD, split off layouts.js when the ✕
    # chooser (task 116) pushed it past 1,000 lines. Algorithmic — it owns a
    # session across several taps, two sources reduce to one slot shape, and
    # every way it can end has to be written down.
    "client/layout-create.js",
    # New 2026-08-09 (owner request, task 168 — a tab is drawn INDENTED under
    # its window, in both of the creation panel's lists): the wizard's own
    # rows. It shares __about/__flow/layout-create.md with the JS, exactly as
    # layouts.css shares its doc with layouts.js and theme.css with theme.js —
    # one feature, one doc, two files.
    "client/layout-create.css",
    "client/gestures.js",
    "client/connection.js",
    "setup/svg_to_ico.py",
    "setup/build_apk.py",
    "setup/build.py",
    # Split out of build.py on 2026-08-12 (THE STRUCTURE LAW): the fail-closed
    # gate suite, which grows every round, apart from the packaging steps,
    # which barely change. Same tier as build.py — a list of subprocess calls,
    # each explained where it is added.
    "setup/gates.py",
    "android/app/src/main/java/com/uvuruna/vibecoder/MainActivity.kt",
    # New 2026-08-07 (owner decree — the waiting channel): one thread that
    # holds an idle socket open, a connect/read/backoff state machine with
    # its own timing rules against the PC's beat. Algorithmic — it earns a
    # flow the same way presence.py does.
    "android/app/src/main/java/com/uvuruna/vibecoder/NoticeLink.kt",
}

ALL_CLASSIFIED = TRIVIAL | STANDARD | ALGORITHMIC


def _is_tests_tier(rel_posix: str) -> bool:
    # Every source file under tests/ (guard modules included) needs no own
    # doc — the folder's ___tests.md covers it (DOCS.md tier table).
    return rel_posix == "tests" or rel_posix.startswith("tests/")


def _about_flow_paths(rel: Path) -> tuple[Path, Path]:
    """Where a source file's __about/__flow docs live. Normally beside the
    file's own folder; android/'s Kotlin sources are nested deep under a Java
    package path (android/app/src/main/java/com/...) with no ___folder.md of
    their own down there, so their docs live at the android/ top level next
    to android/___android.md instead (the migration session's deliberate
    choice — docs mirror the doc-folder tree, not the Java package tree)."""
    basename = rel.stem
    if rel.parts[0] == "android":
        folder = PROJECT_ROOT / "android"
    else:
        folder = PROJECT_ROOT / rel.parent
    return folder / "__about" / f"{basename}.md", folder / "__flow" / f"{basename}.md"


def test_every_source_file_is_classified():
    unclassified = []
    for path in iter_source_files():
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if _is_tests_tier(rel) or rel in ALL_CLASSIFIED:
            continue
        unclassified.append(rel)
    assert not unclassified, (
        "Source files with no tier assignment in test_docs_coverage.py "
        "(classify them: Trivial/Standard/Algorithmic — DOCS.md -> Tiers):\n"
        + "\n".join(unclassified)
    )


def test_standard_and_algorithmic_files_have_required_docs():
    missing = []
    for path in iter_source_files():
        rel_str = path.relative_to(PROJECT_ROOT).as_posix()
        if rel_str not in STANDARD and rel_str not in ALGORITHMIC:
            continue
        rel = path.relative_to(PROJECT_ROOT)
        about_path, flow_path = _about_flow_paths(rel)
        if not about_path.exists():
            missing.append(f"{rel_str}: missing {about_path.relative_to(PROJECT_ROOT).as_posix()}")
        if rel_str in ALGORITHMIC and not flow_path.exists():
            missing.append(f"{rel_str}: missing {flow_path.relative_to(PROJECT_ROOT).as_posix()} (Algorithmic tier)")
    assert not missing, "Docs coverage gaps:\n" + "\n".join(missing)


def test_trivial_and_tests_tier_files_have_no_stray_doc():
    # Not a hard requirement of DOCS.md, but a useful drift check: a Trivial
    # or tests-tier file that somehow grew its own __about/__flow doc means
    # either the tier is stale (promote it) or the doc is a leftover
    # (delete it) — either way this test should be updated in the same
    # commit as whichever fix applies.
    stray = []
    for path in iter_source_files():
        rel_str = path.relative_to(PROJECT_ROOT).as_posix()
        if rel_str not in TRIVIAL and not _is_tests_tier(rel_str):
            continue
        rel = path.relative_to(PROJECT_ROOT)
        about_path, flow_path = _about_flow_paths(rel)
        if about_path.exists():
            stray.append(str(about_path.relative_to(PROJECT_ROOT).as_posix()))
        if flow_path.exists():
            stray.append(str(flow_path.relative_to(PROJECT_ROOT).as_posix()))
    assert not stray, (
        "Trivial/tests-tier files with a stray __about/__flow doc "
        "(promote the tier or delete the doc):\n" + "\n".join(stray)
    )


def test_every_code_folder_has_a_folder_doc():
    # Every folder that contains at least one classified source file must
    # have its own ___{folder}.md entry point (DOCS.md -> Structure). android/
    # is the one exception: its Kotlin sources nest deep under a Java package
    # path with no folder doc of their own down there — android/___android.md
    # at the top level is their entry point instead (see _about_flow_paths).
    folders_with_code = set()
    for path in iter_source_files():
        rel = path.relative_to(PROJECT_ROOT)
        folders_with_code.add(PROJECT_ROOT / "android" if rel.parts[0] == "android" else path.parent)
    missing = []
    for folder in folders_with_code:
        expected = folder / f"___{folder.name}.md"
        if not expected.exists():
            missing.append(str(expected.relative_to(PROJECT_ROOT).as_posix()))
    assert not missing, "Code folders missing their ___folder.md entry point:\n" + "\n".join(missing)


if __name__ == "__main__":
    test_every_source_file_is_classified()
    test_standard_and_algorithmic_files_have_required_docs()
    test_trivial_and_tests_tier_files_have_no_stray_doc()
    test_every_code_folder_has_a_folder_doc()
    print("PASS — test_docs_coverage")
