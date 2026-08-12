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
    # New 2026-08-11 (task 184 — a layout from a window that is not open yet).
    # Standard: three READS of places other apps keep their own recent lists,
    # plus a launch and a wait. The one rule with teeth — only a handle that
    # was NOT standing before the launch may be handed back — is a comparison,
    # not a flow, and it is gated in tests/test_layout_birth.py.
    "server/recents.py",
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
    "server/window_manager.py",
    # Split out of window_manager.py on 2026-08-09 (THE STRUCTURE LAW — the
    # pos-anchor round pushed it past 1,000 lines). The registry holds the
    # session's layout list and its policy; window_manager keeps driving the
    # real windows. Standard: the policy it carries (verified arrangement,
    # the pos anchor) is explained in its __about; the geometry itself lives
    # in grids.py and client/view-anchor.js, each with its own coverage.
    "server/layout_registry.py",
    # New 2026-08-08 (task 116 forced the split — window_manager.py sat at
    # exactly 1,000 lines). One function, one job: an exe path to a PNG data
    # URI. Standard, not Algorithmic — it carries no decision, only shell+GDI
    # plumbing, and its whole policy is "an icon is never a failure".
    "server/window_icons.py",
    "server/clipboard.py",
    "server/updates.py",
    "server/traffic.py",
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
    # New 2026-08-09 (owner request, task 142 — the cursor must show what the
    # pixel under it does): the drawn silhouette per cursor name, split into a
    # pure module so tests/test_cursor_shape.py can run it whole (the
    # view-anchor.js pattern). Standard: one table and one translate, no flow
    # worth a diagram — the WHY lives in its header and its __about.
    "client/cursor-shapes.js",
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
    # New 2026-08-11 (owner ballot verdict — tasks 190/191/208): the DOM half
    # of the three Claude Code cards. Standard: it draws chips and rows and
    # sends; every rule it obeys lives in claude-state.js below, which is where
    # the flow is.
    "client/claude-panels.js",
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
    "android/app/src/main/java/com/uvuruna/vibecoder/Bridge.kt",
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
    "server/grids.py",
    "client/loading.js",
    "server/gui/theme.py",
    # Split out of the three windows on 2026-08-06 (THE STRUCTURE LAW): the
    # same settle loop was copied three times and carried the same lie in
    # every copy — how a window declares its true minimum is one rule, and it
    # is algorithmic (a circular measurement that has to converge).
    "server/gui/sizing.py",
    "server/gui/traffic_window.py",
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
