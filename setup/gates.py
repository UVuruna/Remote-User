"""THE FAIL-CLOSED GATE SUITE — every check a build must survive.

SPLIT OUT OF setup/build.py on 2026-08-12 (THE STRUCTURE LAW). build.py had
reached 1,000 lines and the overwhelming majority of them were this one
function: a gate is added to it in almost every round, while the steps that
actually assemble an installer — version info, icons, vendor payloads,
PyInstaller, signing, NSIS — have barely changed in months. That is two
responsibilities with two completely different rates of change sharing a file,
which is the seam THE STRUCTURE LAW exists to find.

So: this module answers "may this tree ship at all", build.py answers "how is
it packaged". Nothing here knows about PyInstaller or NSIS; nothing there
knows what a gate proves.

`step` and `run` are PASSED IN rather than imported. build.py owns the
console's voice and the subprocess policy (masking, failure handling), and a
gate module that imported them back would be a cycle for no gain — the two
parameters say plainly that this module borrows the caller's reporting.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent

def input_gate(step, run) -> None:
    """Fail-closed: the end-to-end input pipeline (touch → protocol →
    injection) must pass BEFORE anything is packaged. "Left click stopped
    working" shipped in a release more than once while every file looked
    right — this gate makes that impossible. A missing playwright/Chromium
    fails the build too (install it; never skip the gate silently)."""
    step("0b/6  INPUT GATE — end-to-end click path (tests/test_input_pipeline.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_input_pipeline.py")])
    # Same fail-closed reasoning for presence (owner 2026-08-05): layout
    # members are always-on-top while the phone watches them, so a release
    # that forgets to notice the phone leaving locks the owner's own desk
    # under hovering windows. Pure logic — no browser needed.
    step("0c/6  PRESENCE GATE — leaving work mode frees the desk (tests/test_presence.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_presence.py")])
    # And the same for the notices (owner 2026-08-05): the whole value of
    # "the PC calls you" is that it names WHICH agent finished. A release
    # where the name went missing, the token check slipped, or the phone
    # stopped raising a banner would be a feature the owner cannot trust —
    # and he only finds out by NOT being told something.
    step("0d/6  NOTIFY GATE — the PC names the agent, the phone says it (tests/test_notify.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_notify.py")])
    # ...and that the notice REACHES him when he is not looking at the phone
    # (owner report 2026-08-07: "notifikacije mi stižu tek kada podignem
    # aplikaciju"). The notice used to ride the streaming socket, which the
    # page closes on purpose the moment it hides — so a release where the
    # waiting channel regressed would be silently back to "be looking at it
    # already". Two defects this pins are invisible from the outside: a
    # notice delivered TWICE (two carriers instead of a chain of returns) and
    # a notice connection counted as a PRESENT phone, which would nail his
    # own windows always-on-top over his desk from a phone in his pocket.
    step("0d/6  NOTICE CHANNEL GATE — it reaches a closed page, once "
         "(tests/test_notice_channel.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_notice_channel.py")])
    # And for WHERE typed input lands (owner 2026-08-06): `SendInput` has no
    # target, so a release that lets the foreground decide sends the owner's
    # dictation into whatever window happened to take focus mid-sentence —
    # which is how a sentence for another project ended up in this one. He
    # cannot see it happen: the stream still shows the PC.
    step("0e/6  FOCUS GATE — typed input lands where he is looking (tests/test_focus_guard.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_focus_guard.py")])
    # ...and the machinery that carries it there, split out on 2026-08-07 when
    # the two subjects crossed THE STRUCTURE LAW's 1,000 lines. This half is
    # where the dangerous defects live: a hook callback that blocks Windows'
    # own dispatch (measured 2.99 s — the owner felt it as a juddering mouse)
    # and a stop() that orphans its thread with the hook still installed.
    step("0e/6  FOCUS HOOK GATE — instant, and it leaves nothing behind (tests/test_focus_hook.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_focus_hook.py")])
    # And the phone's whole LAYOUT protocol (owner report 2026-08-06: "layout,
    # kreiraj iz liste, ništa se ne dešava"). One shadowed name in
    # layout_list — `mon_rect = mon_rect(stream)` — raised UnboundLocalError
    # before a single byte was sent, so the loading cube spun forever. Four
    # guards and four gates were green over it, because NO TEST WALKED THE
    # PATH. Every layout message the phone can send is driven through the real
    # dispatcher here, and a handler that raises or answers nothing fails the
    # build.
    step("0f/6  LAYOUT GATE — every layout message answers the phone (tests/test_layout_protocol.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_layout_protocol.py")])
    # And the LIST's own two gestures, which had no gate at all until the owner
    # reported the whole thing dead (2026-08-09, task 162). `layout_merge` and
    # `layout_reorder` shipped on 2026-08-07 and no test in this project
    # mentioned either name for two days: dropping a row on another to make a
    # grid, dropping it in a gap to re-order. The client half — when a press
    # becomes a HOLD — is gated separately and purely, below.
    step("0f/6  LAYOUT DRAG GATE — a row dropped on another makes a grid "
         "(tests/test_layout_drag.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_layout_drag.py")])
    # And that a phone which has GONE takes its encoder with it (live failure
    # 2026-08-07). Cancelling `asyncio.to_thread(open_session)` does not stop
    # the thread, so one leaked session ran four hours at native 4K with
    # nobody watching — 12,924 s of ffmpeg CPU, 1,890 "stream backlog"
    # warnings, and the owner's own mouse juddering at his desk. Nothing in
    # the suite walked a connection's END, which is why every gate was green
    # over it for three days.
    step("0g/6  STREAM LIFECYCLE GATE — a client that is gone leaves nothing "
         "behind (tests/test_stream_lifecycle.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_stream_lifecycle.py")])
    # …and the same connection's OTHER end: a quality change (owner's #1 report
    # 2026-08-10). A bitrate can only be applied by a new encoder, and closing
    # the old one used to tear dxcam down with it — the new ffmpeg then had no
    # frame to encode, wrote no init segment, and the failed RE-open closed a
    # socket that also carries input, layouts and dictation.
    step("0r/6  QUALITY RESET GATE — changing the bitrate cannot kill the app "
         "(tests/test_quality_reset.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_quality_reset.py")])
    # …and its sibling one layer up: a whole server RUN that outlives the stop
    # that gave up on it. His log of 2026-08-09 has run A finishing 38 s after
    # run B was already serving, and writing state="stopped" over it — the
    # STOPPED pill he photographed under a live phone, plus the live layout
    # dropped out of the topmost band and the live encoder killed.
    step("0x/6  SERVER GENERATION GATE — a superseded run owns nothing "
         "(tests/test_server_generation.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_server_generation.py")])
    # And that what this build INVENTS actually reaches the owner's own
    # actions.json (owner report 2026-08-07, the fifth on one bug). His copy
    # is seeded once at install and never replaced, so the merge is the only
    # path a new field has into it — and the merge copied a hardcoded list of
    # field names. The Claude set's `agent` switch was invented on 2026-08-06,
    # never arrived, and left the set matchable only by a title Claude Code
    # never writes. Every guard was green over it for four releases because
    # every guard built its "user file" out of the SHIPPED file. A build must
    # not ship a field it cannot deliver.
    step("0h/6  ACTIONS MIGRATION GATE — a new version's fields reach HIS file "
         "(tests/test_actions_migration.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_actions_migration.py")])
    # And that taking THIS build does not cost him the session he takes it
    # from (owner report 2026-08-07). Everything above only matters if the
    # release can be installed at all, and until now it could not be — not
    # from away: entering the install killed the remote session that was
    # driving it, so an owner on the road sat on an old build watching fixed
    # bugs. This gate runs the SHIPPED handover script against a fake
    # installer and a fake app, and the check that must never go red is the
    # rollback: a failed install still has to give him his PC back.
    step("0i/6  UPDATE HANDOVER GATE — installing does not cost him the "
         "session (tests/test_update_handover.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_update_handover.py")])
    # And that a phone which loses its ROUTE comes back without being killed
    # (owner report 2026-08-07: "'Try again' retko kad pomogne ... nekad čak i
    # da zatvorimo celu aplikaciju"). A REPEAT — three mechanisms were already
    # written as the answer to this complaint and all three only run in states
    # he is not in. The one he IS in is a page that loaded fine and is now
    # retrying an address that no longer reaches the PC: the shell re-probed
    # only behind its error card, the page can only ever reach the address the
    # document came from, and on this side a socket the watchdog had declared
    # dead still held the one-device slot. Needs node (it runs the REAL
    # client/connection.js on a virtual clock) — never skip it silently.
    step("0j/6  LINK RECOVERY GATE — a lost route recovers without killing "
         "the app (tests/test_link_recovery.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_link_recovery.py")])
    # And that dictation never retypes across a ROUND BOUNDARY (task 75
    # REPEAT, 2026-08-08). 0.0.293 fixed a round re-typing its OWN growing
    # partial on retry; his log then showed 177 ERROR_CLIENTs in one session
    # and a NEW, smaller shred at the boundary BETWEEN two independent
    # rounds — a shape the old fix's own tests never asked about. The rule
    # now lives on the page (this repo has no JVM test runner, so a
    # Kotlin-only fix cannot be proven), and this gate drives the REAL
    # client/controls.js function in node.
    step("0k/6  VOICE DEDUP GATE — dictation never retypes across a round "
         "boundary (tests/test_voice_dedup.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_voice_dedup.py")])

    # A SETTING WE RETIRED IS OURS TO REMOVE (owner evidence, 2026-08-08: his
    # server.log warned about `hand` on every start, months after the offset
    # system was deleted — a key HE never typed). Same class as the
    # actions.json failure: we change ours, his copy keeps the dead field
    # forever because nothing rewrites a file he does not open. The gate
    # starts from the LITERAL text of his own settings.json, for the same
    # reason 0j does.
    step("0l/6  USER SETTINGS GATE — a retired key leaves his file quietly, a "
         "mistyped one is still reported (tests/test_user_settings.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_user_settings.py")])

    # THE KEYBOARD LIFTS ONLY IF NEEDED, ONLY BY THE SHORTFALL (owner
    # 2026-08-07, after asking for the opposite thing twice and being right
    # both times — a box at the bottom is covered unless the picture rises, a
    # box at the top leaves the screen if it does). No constant can settle it,
    # so the rule reads where the caret really is; this gate runs it whole.
    step("0m/6  CARET LIFT GATE — the picture rises only when the caret would "
         "be covered (tests/test_caret_lift.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_caret_lift.py")])

    # THE PC MUST SAY WHERE THE TYPING LANDS, OR SAY IT CANNOT (owner
    # 2026-08-07). The server half of the caret keyboard: a UIA read that is
    # throttled rather than run per poll, a caret refused when it names another
    # window, and an honest "unknown" for the apps that expose nothing. Without
    # this the phone half above has no input at all.
    step("0n/6  CARET GATE — the PC says where the typing lands, or says it "
         "cannot (tests/test_caret.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_caret.py")])

    # THE POSITION LIVES ON THE PHONE (owner decree 2026-08-09, the FOURTH
    # round of the Move handle). Three rounds moved windows on the PC monitor
    # and measured them there — a screen the owner never sees — while the
    # thing he judges, where the letterboxed picture sits on his tablet, was
    # computed by no check. The fit-and-anchor math is pure
    # (client/view-anchor.js) and this gate drives it whole in node with the
    # geometry HE grades: pos 0 flush to the near edge, 1 to the far, 0.5
    # centred, no effect when nothing is letterboxed — plus the wiring on
    # both ends, because a pure function nobody calls is a feature that does
    # not exist. Needs node, like 0j and 0k — never skip it silently.
    step("0o/6  VIEW ANCHOR GATE — the picture sits where the Move handle "
         "put it (tests/test_view_anchor.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_view_anchor.py")])

    # THE CURSOR SHOWS WHAT THE PIXEL UNDER IT DOES (owner request 2026-08-09,
    # task 142). The phone draws the pointer itself and drew one fixed arrow,
    # so a draggable window edge, a text box and plain background were the
    # same picture from the tablet. Three ends have to hold together and each
    # can break silently: the PC naming the live HCURSOR (driven here with
    # faked handles through the REAL resolver), the name riding the EXISTING
    # cursor message as an optional field on change only, and the page drawing
    # a distinct shape whose HOTSPOT lands on the commanded pixel — with
    # anything unknown falling back to the exact old arrow. Needs node, like
    # 0j/0k/0o — never skip it silently.
    step("0p/6  CURSOR SHAPE GATE — the phone draws the cursor the PC is "
         "really showing (tests/test_cursor_shape.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_cursor_shape.py")])

    # THE LIST SAYS WHICH SHAPE EACH LAYOUT IS (owner request 2026-08-09, task
    # 164). A row carried a name and nothing about its shape, so a solo window,
    # a two-split and a four-grid read identically until he opened one. The
    # catalogue is his own sheet (UV/grid_variations.png, 2026-08-07): six
    # arrangements plus solo, fourteen with the orientations. Two things can
    # break silently and both are checked — two variants drawing ONE picture
    # (the whole feature, gone, invisibly), and the drawing drifting from
    # `server/grids.py`, whose arithmetic actually places his windows. The
    # geometry is pure and is run WHOLE in node, like 0j/0k/0o/0p — never skip
    # it silently.
    step("0s/6  GRID ICON GATE — every row can say which shape it is "
         "(tests/test_grid_icons.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_grid_icons.py")])

    # ONE WINDOW OUT OF A GRID (owner request 2026-08-09, task 165). Until this
    # round a grid could only be built or removed WHOLE, so losing one window
    # of four meant deleting the layout and making it again. Fail-closed for
    # the same reason the ✕ chooser is: the window that leaves must NOT be
    # closed and must NOT be left stranded always-on-top — of everything in
    # this feature those are the only parts he cannot undo from the phone.
    step("0t/6  LAYOUT MEMBER GATE — a grid can lose one window, and the "
         "window keeps its life (tests/test_layout_member.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_layout_member.py")])

    # A LAYOUT CAN GROW, TOO (owner request, task 195). The mirror of the gate
    # above — solo→2, 2→3, 3→4 from the ⚙ sheet's "Add a window" — sharing the
    # same `_template_for` catalogue so growing and shrinking can never
    # disagree about what a three is, plus its own duplicate-membership and
    # topmost-ledger checks.
    step("0af/6 LAYOUT GROW GATE — a layout can gain one window, up to four "
         "(tests/test_layout_grow.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_layout_grow.py")])

    # ROUND 40's OWN GATES (2026-08-11), each fail-closed and planted-defect
    # proven by its builder, re-run by the coordinator before wiring:
    for _name, _title in [
        ("test_old_name", "no shipped file still carries the pre-rename name (2026-08-12)"),
        ("test_orientation_lock", "the lock survives a resume and the interim desktop (204)"),
        ("test_clipboard_sync", "the PC clipboard reaches the phone, held through an away (182)"),
        ("test_return_timing", "one return, one encoder, started first (203)"),
        ("test_raw_pixel_cost", "half the bytes, the right colours, before the pipe (130)"),
        ("test_capture_handover", "a restart never inherits a live camera (193)"),
        ("test_quality_raise", "the PC's card is a default and a raise blinks once (131)"),
        ("test_layout_birth", "a layout from a window that is not open yet (184/185)"),
        ("test_birth_radial", "the centered birth radial and the L2 grammar (186)"),
        ("test_release_hygiene", "no release over an update in flight (187)"),
        ("test_wheel_dropout", "a placed set leaves the wheel, cap 10 (181)"),
        ("test_wheel_geometry", "the wheel's ring fits the shorter side — nothing pushed off screen (238)"),
    ]:
        step(f"0ai/6 {_title} (tests/{_name}.py)")
        run([sys.executable, str(PROJECT_DIR / "tests" / f"{_name}.py")])

    # AND A GRID CAN COME APART (owner request, task 197): split into as many
    # solo layouts as it has members, or eject ONE member into its own new
    # layout — never to the desktop, the contrast with the member gate above.
    # Fail-closed on the same class of promise: the ejected window must not be
    # closed and must not be stranded always-on-top.
    step("0ag/6 LAYOUT DECOMPOSE GATE — a grid can come apart, whole or one "
         "window at a time (tests/test_layout_decompose.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_layout_decompose.py")])

    # AND A LAYOUT CAN BE TURNED (owner 2026-08-09, task 175). Every act on an
    # existing layout moved under one ⚙, and one of them could not be done at
    # all before: a layout built portrait had to be DELETED and made again to
    # become landscape. The message it rides has existed since 2026-08-07 and
    # NOTHING IN THIS PROJECT EVER DROVE IT — no test mentioned `layout_grid`
    # or `set_grid`, so "the server already has it" was a claim about a name.
    # It asserts the RECTS: a shape change the phone shows and the PC ignores
    # is the Move handle's bug in a new place, and a stored value he cannot see
    # proves nothing about a feature he judges by geometry.
    step("0u/6  LAYOUT SHAPE GATE — a layout can be turned and re-arranged, "
         "and the windows really move (tests/test_layout_shape.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_layout_shape.py")])

    # AND A WINDOW THE LAYOUT'S WORK OPENS STAYS REACHABLE (owner eruption
    # 2026-08-11, task 202 — his third report of this class). An agent's HTML
    # report opened outside the layout he was watching: under the members'
    # topmost band, so the phone could not raise it, and the only way to it —
    # Desktop — minimizes every member and takes his place of work with it.
    # Fail-closed on the half he cannot undo from the phone: a STRANGER'S
    # window must never be moved, resized or nailed above everything by this
    # session, and nothing we do raise may be left stranded up there
    # (constraint 10).
    step("0ad/6 LAYOUT POPUP GATE — a window the layout's work opens stays "
         "reachable, and a stranger's is still refused "
         "(tests/test_layout_popup.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_layout_popup.py")])

    # A RENAME SHOWS UP AT ONCE (owner report 2026-08-10, task 199): the Save
    # handler sent layout_rename and closed the sheet, touching nothing the
    # bar/list/header read — so the new name appeared only when the server's
    # layout_state echo happened to land, and reopening Rename "fixed" it by
    # reading fresh state. The fix is optimistic-local; the gate proves the
    # displayed name changes with send() sent to a black hole (no server trip).
    step("0z/6  LAYOUT RENAME GATE — a rename shows up without a second trip "
         "through Rename (tests/test_layout_rename_live.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_layout_rename_live.py")])

    # THE CUBE MAY NOT OVERSTAY (owner report, task 194: "traje predugo ...
    # radi kontra uslugu" — plus "misses places it should cover"). The settle
    # watcher's metric was a whole-frame MEAN that a busy screen (agents
    # actively typing/scrolling) kept above threshold for the whole watch
    # window even after the server had already verified placement; it moved
    # into a pure module (client/settle-motion.js, run whole in node) as a
    # changed-pixel FRACTION instead, with the hard cap shortened to a real
    # "a few seconds". Separately, connection.js's excursion-restore path
    # armed the watcher against an INTERIM frame and never re-armed it before
    # sending the real corrective layout_focus, so the overlay could close
    # before the actual restore was covered — fixed and pinned here too.
    step("0aa/6  LOADING SETTLE GATE — the cube leaves on real motion, not a "
         "washed-out mean (tests/test_loading_settle.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_loading_settle.py")])

    # AND IT MAY NOT COVER WHAT HE ASKED TO SEE (owner decree 2026-08-12). He
    # named two kinds — full screen, and "samo CUBE bez background" — and the
    # split is decided by what is happening BEHIND: windows really moving must
    # be covered, while an app opening is the only progress there is to watch
    # and covering it hides everything. Every call site declares its kind in
    # the code AND in a comment, and the gate holds the two to each other,
    # because a stale inventory comment is worse than none (this repo has met
    # that failure before). The inventory is also what the move to the shared
    # Loading Cube gadget will be read off.
    # THE APP DOES ITS OWN RETRYING (owner report 2026-08-12, with his
    # screenshot of "Update download failed — retry"): "ovo mi se u zadnje
    # vreme dešava pa treba par puta da se klikne button". Two defects sat
    # behind it — the download never retried, and every click threw away the
    # ~113 MB already fetched (`open(dest, "wb")`). It now retries four times
    # with a Range resume, and the gate also pins the truncation case the gate
    # itself discovered: a CDN that drops mid-transfer ends the stream
    # CLEANLY, so a short file used to be reported as a finished download.
    # THE RING FOLLOWS THE SCREEN, AND ITS CIRCLES DO NOT TOUCH (two owner
    # reports 2026-08-13). With a set open, rotating the desktop slid the wheel
    # half off the edge — `wheelPoints` returns ABSOLUTE pixels and nothing
    # recomputed them. And the radius was a flat 118 px that knew nothing about
    # how many items it arranged: at task 181's ten-item cap the circles
    # overlapped by 17 px. The gate drives every count on every screen in both
    # orientations through the pure module, and pins the LADDER rather than the
    # shrink he asked for — a check that only asked "did they get smaller"
    # would pass an implementation that shrinks on a tablet with room to spare.
    step("0ad/6  WHEEL GEOMETRY GATE — the ring follows the screen and its "
         "circles keep their gap (tests/test_wheel_geometry.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_wheel_geometry.py")])

    step("0ac/6  UPDATE DOWNLOAD GATE — it retries and resumes by itself, and "
         "names the failure (tests/test_update_download.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_update_download.py")])

    step("0ab/6  LOADING KIND GATE — every animation declares full-screen or "
         "cube-only, in code and comment (tests/test_loading_kind.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_loading_kind.py")])

    # THE ARRANGEMENT FOLLOWS HIS CHOICE, NOT THE ORIENTATION (owner ruling
    # 2026-08-09, task 177): portrait defaults to the column and landscape to
    # the cross exactly as before, but an explicit per-orientation choice
    # (padShapePort/padShapeLand, per device through the prefs bridge)
    # outranks the default, and the old padCross key is READ as the portrait
    # seed — a saved choice is translated, never reset. The CSS keys off the
    # DECISION (body.pad-column), never off a media query: the media query WAS
    # the weld this task removes.
    # THE PHONE EDITS A SET'S INTERIOR (owner 2026-08-04, delivered as task
    # 218b after a week with no task number of its own). It writes the SAME
    # actions.json the desktop Controls editor writes, so the gate is fail-
    # closed here: it proves the edit reaches a USER file of an OLDER shape
    # (never `copy(shipped)` — that shortcut is what let four releases pass
    # while a field never reached his %LOCALAPPDATA% copy), that a key outside
    # the merge's owner-owned set is refused WHOLE, that an id outside the pool
    # is refused, and that the `actions` re-broadcast really re-draws the live
    # D-pad — the last one in a real Chromium walking his own path, because a
    # module nobody calls is a feature that does not exist.
    step("0ah/6  SET EDITOR GATE — the phone edits a set's buttons and their "
         "positions, and the PC writes HIS file (tests/test_set_editor.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_set_editor.py")])

    step("0v/6  PAD SHAPE GATE — the arrangement follows his choice in both "
         "orientations (tests/test_pad_shape.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_pad_shape.py")])

    # ON IS A LUMINANCE EVENT (owner report 2026-08-09, task 179, round two of
    # 135): the round-one rule signalled ON with accent HUES and the coloured
    # looks outranked every one of them in the cascade — the net signal on his
    # phone measured 1.05-1.58:1 against the OFF sibling. This gate PHOTOGRAPHS
    # the real page and measures ON-vs-OFF as a contrast ratio over the face
    # and the ring in ALL EIGHT looks, floor 3.0; the rule that shipped in
    # v0.0.103 was planted as the defect and went RED at 1.58. A check in one
    # look is how round one passed while his screen said otherwise.
    step("0w/6  ON STATE GATE — a switched-on button is a luminance event in "
         "all eight looks (tests/test_on_state.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_on_state.py")])

    # A HOLD IS A CONTACT THAT STAYED PUT (owner report 2026-08-09, task 162:
    # he held a layout row and the layout OPENED). The drag gesture had shipped
    # whole and was defeated at its first millisecond — the row cleared its
    # 380 ms hold timer on ANY movement, and a finger resting on a capacitive
    # digitizer never stands still. It shipped broken and STAYED broken because
    # the arming logic was not extractable and therefore never tested: no test
    # in this project mentioned `holdTimer`, `dragEnd`, `mergeLayouts`,
    # `layout_merge` or `layout_reorder`. The rule is a pure module now and
    # this gate drives it in node against a REALISTIC JITTER SEQUENCE — a rule
    # about jitter cannot be proven by one call. Needs node, like 0j/0k/0o/0p —
    # never skip it silently.
    step("0q/6  HOLD GESTURE GATE — a resting finger picks the row up, a "
         "travelling one never does (tests/test_hold_gesture.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_hold_gesture.py")])

    # THE PICTURE NEVER GOES BLANK, AND WHEN IT STOPS IT STARTS AGAIN BY
    # ITSELF (task 151, 2026-08-10 — the owner's own promise for this build).
    # Two earlier fixes for his freeze at 60fps/20Mbps (task 122) each went
    # back out the SAME night they shipped (0.0.375's revert, commit
    # 581244b): the starve-recovery seek (a9db36b) was real but flushed the
    # decoder on every recovery, and on a link that cannot keep up that fired
    # every second — the rate-limited fix for THAT (3b7b477) landed beside two
    # other streaming changes and the owner could not attribute any of it.
    # This build returns all of it as ONE mechanism: slow the player down
    # BEFORE ever reaching for a flush (client/live-clock.js `liveRegulate`),
    # and even the flush that does become necessary fires no more than once
    # per 4s. The pure module is driven WHOLE in node against a REALISTIC
    # DRIFT RAMP taken from his own server log — a rule about a ramp cannot be
    # proven by one call, the test_voice_dedup.py precedent. Needs node, like
    # 0j/0k/0o/0p/0q — never skip it silently.
    step("0y/6  LIVE CLOCK GATE — a starved player is caught, slowed before "
         "it is ever flushed, and never blank (tests/test_live_clock.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_live_clock.py")])

    # THE COMMAND GOES TO THE PROMPT, OR NOWHERE (owner order 2026-08-11, task
    # 200: a Claude command fails when the prompt is not selected — put the
    # caret there first). The delivery is the Command Palette running "Claude
    # Code: Focus input", and the danger is the delivery itself: Ctrl+Shift+P
    # is a GLOBAL chord, so firing it at a window that is not VS Code is
    # exactly the accident constraint 11 exists to prevent. Four things can
    # break in silence and each is checked — the palette landing AFTER the
    # command text (which would run whatever the palette filtered to), the
    # palette chord leaking into every other typed button, a stranger's window
    # being injected into at all, and an Enter crossing a gap the focus fence
    # no longer holds.
    step("0ab/6  CLAUDE FOCUS GATE — the prompt is focused before the command "
         "is typed (tests/test_claude_focus.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_claude_focus.py")])

    # THE PANEL SAYS WHAT IS RUNNING, NOT WHAT WAS TAPPED (his report
    # 2026-08-11, task 208: the Model panel named nothing as current, and
    # Thinking lit Medium while his PC was really on Max). The answer is read
    # from the live conversation's own transcript, and the SHAPE of that file
    # is the thing that can rot without anyone noticing — task 208's own note
    # said effort had no trail, which measurement proved false. This drives
    # the real reader over transcripts built like his: the newest assistant
    # record wins, a tool-call record still names model AND effort, [1m] is
    # one family with its id kept whole, the mode is the last record that HAS
    # permissionMode (a tool result is a `user` record and carries none), and
    # anything unreadable answers nulls instead of raising.
    step("0ac/6  CLAUDE STATE GATE — the phone is told what the conversation "
         "is really running (tests/test_claude_state.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_claude_state.py")])

    # AND THE PHONE'S HALF OF THE SAME SENTENCE (owner ballot verdict
    # 2026-08-11, tasks 190/191/208/219). Three reports, one family of defect:
    # a panel STATING SOMETHING IT DID NOT KNOW — nine model options nobody
    # official ever offered, a Thinking button that only raised a menu, and a
    # "Medium" chip that was this phone's own memory wearing a live-state look
    # while his PC ran on Max. So the rules live in a PURE module and this
    # gate runs them whole in node: the five official aliases, the five effort
    # levels, the Shift+Tab ring (whose honest answer for an unknown start is
    # no answer at all), and above all what each chip may CLAIM when the PC
    # has told it nothing. It also holds the wiring — a rule nobody calls is a
    # feature that does not exist — including `focus: "claude"` reaching the
    # server field that landed the same day, and the shipped wheel never
    # ticking past the cap of 8. Needs node; never skip it silently.
    step("0ae/6  CLAUDE PANELS GATE — the panels offer what the PC has and "
         "claim only what it said (tests/test_claude_panels.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_claude_panels.py")])

    # TASK 226, owner ballot verdict — all three of the settings-inventory
    # proposals landed in this build: notification-channel switches on the
    # phone's Phone card, the desktop's ADVANCED settings card, and the
    # one-time 4K@60 freeze offer. Fail-closed the same way test_voice_dedup.py
    # is: a rule about the LAST-RESORT fallback (muting all three carriers
    # must never mean silence) cannot be proven by one call, and needs node —
    # never skip it silently.
    step("0aj/6  NOTIFY CHANNELS GATE — a muted carrier is skipped, and "
         "muting all three still leaves the banner as the last resort "
         "(tests/test_notify_prefs.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_notify_prefs.py")])

    # ── TASK 227/228 (2026-08-11) ────────────────────────────────────────────
    step("0al/6  LAYOUT HISTORY GATE — a created layout is remembered across "
         "restarts, deduped by member set, and re-matched against what is "
         "open now (tests/test_layout_history.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_layout_history.py")])

    step("0am/6  ROW TAP GATE — a row in the creation panel selects only on "
         "release under slop; a drag over it scrolls and selects nothing "
         "(tests/test_row_tap.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_row_tap.py")])

    step("0an/6  CREATION FOOTER GATE — Cancel/Create stay inside the "
         "viewport with a long window list, at both target sizes "
         "(tests/test_creation_footer.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_creation_footer.py")])

    # THE DEVICE'S OWN DECODER IS A WALL (owner report 2026-08-12: "native
    # 20 Mbps still sends no picture"). His log: 3840x2160@30 played smoothly
    # (jumps=0 for two minutes); the moment the PC card went to 60 fps every
    # session opened level 5.2 and the same tablet threw the picture forward
    # ten times every 15 s — a decoder drowning, not a network, and nothing
    # anywhere asked the device what it can decode. The rules are a pure
    # module (client/decode-caps.js): probe mediaCapabilities per resolution
    # step, cap the requested fps at the device's smooth ceiling, SAY the cap,
    # and a runtime backstop lowers a session's ceiling when the live windows
    # keep counting jumps that the spec sheet promised away. Driven whole in
    # node with the codec strings from his real sessions. Needs node, like
    # 0j/0k/0o/0p/0q/0y — never skip it silently.
    step("0ao/6  DECODE CAPS GATE — the phone never requests a stream its "
         "own decoder cannot drink (tests/test_decode_caps.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_decode_caps.py")])

    # THE PHONE NEVER DECODES PIXELS IT DOES NOT SHOW (owner order
    # 2026-08-12, his own words — lang-ok: owner quote: "zašto bi telefon
    # dekodirao nešto što ne vidi"). H.264 used to stream the FULL monitor
    # always: a quarter-width layout still cost a full 4K@60 decode with
    # three quarters cropped away on the canvas. The per-client ffmpeg now
    # crops to the focused layout's region, `config.stream_region` tells the
    # page what the video covers, and a region change ends the mismatched
    # session at the layout choke point. Driven with the REAL session and
    # the REAL choke point, and the crop case is his own live layout from
    # his own log.
    step("0ap/6  REGION STREAM GATE — the encoder crops to the focused "
         "layout, and the page maps it back (tests/test_region_stream.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_region_stream.py")])

    # APPEARANCE IS PER DEVICE (owner ballot 2026-08-12). Theme, coloured or
    # plain controls, outlined or filled left the PC's Settings window for the
    # handset — he uses a tablet AND a phone, and one desktop dropdown could
    # only ever describe one of them. The PC's values stay as the DEFAULT, so
    # the promise has two halves and both are easy to break silently: a device
    # that never chose must render the frame BYTE FOR BYTE, and two devices
    # with different choices must render ONE frame differently. Driven in node
    # against the REAL client/theme.js, one fresh module per simulated device,
    # reading the attributes the page actually writes onto <body> — a check on
    # a stored preference would prove nothing about what he sees. Node is a
    # HARD requirement here (the test_view_anchor.py precedent).
    step("0as/6  APPEARANCE GATE — one frame, two devices, two looks; and a "
         "device that never chose is unchanged "
         "(tests/test_appearance_device.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_appearance_device.py")])

    # THE STREAM CARD'S FOUR STEPS, AND THE ONE DATA-SAVER PROFILE (owner
    # ballot 2026-08-12, option A, with his one condition: "just make sure you
    # connect Data saver to mobile data, the mechanic we already have"). Three
    # doors reach that profile — the desktop step, the phone's auto-on-cellular
    # switch and a legacy `quality {reduced:true}` — and this gate measures
    # every one of them against `config.DATA_SAVER`, including by READING the
    # literal out of client/quality.js, so the two languages cannot drift. It
    # also proves that removing Resolution from the front of the card did not
    # remove it from the wire.
    step("0at/6  STREAM CARD GATE — four honest quality steps, and Data saver "
         "is the profile mobile data already uses (tests/test_stream_card.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_stream_card.py")])

    # THE PC NEVER ENCODES MORE PIXELS THAN THE GLASS CAN SHOW (owner order
    # 2026-08-12, approved on a ballot): "what is the point of the PC sending
    # 4K if the Android device cannot receive it? A Redmi Pad is 1920x1200 and
    # we send it 4K in desktop mode." The page now sends its REAL panel pixels
    # on auth (a new field — `screen` stays CSS px and an aspect), the
    # per-client ffmpeg reconciles that ceiling with the phone's resolution
    # step into ONE scale filter right after the crop, and it never scales UP:
    # a crop smaller than the panel is sent at its own size, which is why a
    # focused layout is now sharper at the same bitrate. Driven with the REAL
    # session and the REAL client mirror in node (needs node, like 0ao).
    step("0aq/6  PANEL SCALE GATE — the encoder is capped by the device's own "
         "panel, and never scales up (tests/test_panel_scale.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_panel_scale.py")])

    # NOTHING IN THE RETURN PATH WAITS FOR ITS OWN SAKE (his instrumented log,
    # 2026-08-12: median 3,443 ms of loading overlay per layout return, of
    # which 1,800 ms came AFTER the server had logged that the windows had
    # landed). Three of those waits were the app's own — the encoder rebuild
    # queued behind the state frame, a DELIBERATE session end paying the
    # error-loop brake, and one user switch performed twice because the
    # interim frame invited the phone to redo the resume the server had
    # already started. Driven with the real choke point and the real
    # `_stream_h264` loop; the error-loop brake's own half is proven by a
    # planted storm, because that protection may not be lost while it is being
    # narrowed.
    step("0au/6  RETURN SPEED GATE — the layout return waits for the work and "
         "for nothing else (tests/test_return_speed.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_return_speed.py")])

    # AND THE SCREEN NEVER GOES AWAY WHILE IT DOES (same round). A quality or
    # region change rebuilds the encoder for 1.2–2.3 s and the canvas used to
    # blank to the theme colour for all of it — no overlay, no toast, the PC
    # simply gone. The last frame now HOLDS, which takes away the accident
    # that used to stop the settle watcher scoring on a stale picture, so the
    # watcher waits for the new session's own first painted frame instead.
    # Both halves are driven in node against the REAL client/loading.js: the
    # overlay must not leave over a frozen rebuild, and it must not linger
    # after the work either — the owner deleted the 700 ms floor by name on
    # 2026-08-12 and the 500 ms fade carries what it used to buy.
    step("0av/6  PICTURE HOLD GATE — the picture survives a session swap, and "
         "the cube leaves on evidence (tests/test_picture_hold.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_picture_hold.py")])

    # THE DESKTOP WINDOW'S OWN HEADER MUST BE TRUE (2026-08-12). It claimed
    # "the window never blocks" while the pairing probe (up to 4 s: a UDP
    # timeout plus the Tailscale CLI) ran on the 1 s refresh tick, and Quit
    # joined the server thread inline for up to 10 s. Both moved to
    # gui/offthread.py; what is measured here is TIME ON THE GUI THREAD,
    # against calls that deliberately take seconds.
    step("0aw/6  GUI NON-BLOCKING GATE — the pairing probe and the quit are "
         "off the window's thread (tests/test_gui_nonblocking.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_gui_nonblocking.py")])

    # AND THERE IS ALWAYS A WAY BACK (owner report 2026-08-12, his FIFTH on
    # one failure). A window that opened while his phone was LOCKED stands off
    # every screen and no phone can ever show it again: there is no taskbar
    # there, and until this round nothing in this codebase could move a window
    # it had not itself placed. Four earlier rounds could not even SEE the
    # case, because every rule in layout_popup.py is built on the baseline
    # taken when the phone connects — and a window born while nothing was
    # connected is filed by that baseline as already-known. server/
    # lost_windows.py therefore asks GEOMETRY (can he reach it) instead of
    # HISTORY (who opened it), which needs no connection to have existed.
    step("0ax/6  LOST WINDOW GATE — an unreachable window always has a way "
         "back, whoever opened it (tests/test_lost_windows.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_lost_windows.py")])

    # AND ONE WINDOW ASKS ONE QUESTION (his report 2026-08-12: "make a layout
    # with it" resized the window to the phone's shape and created no layout).
    # His own log dated it: `scan` (185) and the popup sweep (202/240) fired on
    # the SAME window inside one tick, five chips landed in 400 ms, and the
    # phone's single strip replaced each with the next — so his one tap
    # answered the sweep's question, whose yes runs `_contain` and PLACES the
    # window. Both halves gated; the phone half runs the REAL
    # client/window-offer.js in node.
    step("0ay/6  WINDOW OFFER GATE — one window asks one question, and the "
         "chip waits for his tap (tests/test_window_offer_queue.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_window_offer_queue.py")])

    # OWNER REPORT 2026-08-13, his point 4B: "LAYOUT FROM LIST from inside a
    # LAYOUT should offer TWO groups — first what it sees in that layout, then
    # the standard one; from the DESKTOP only the standard."
    #
    # A window in a layout is excluded from the creation list (his own rule of
    # 2026-08-03 — one window cannot be in two places), and excluding the
    # window silently took its TABS with it. But a tab is not its window: it
    # can be torn into a window of its own, which is exactly what the TAP
    # source could already do inside a layout. The list simply stopped hiding
    # what the tap could reach.
    step("0az/6  CREATION LIST GATE — the list from a layout shows that "
         "layout's own tabs first (tests/test_layout_list_groups.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_layout_list_groups.py")])

    # OWNER REPORT 2026-08-13: both language lists — the voice that SPEAKS
    # (Settings -> Voice) and the language he SPEAKS TO (the dictation card) —
    # were one flat pile, and the dictation one repeated the same choice
    # several times. Grouped by language now, opening into their variants.
    #
    # THE GATE'S REAL JOB IS THE SECOND HALF. Grouping is easy to get visibly
    # right and quietly wrong: the first plan was a dedupe BY LANGUAGE, which
    # he overruled ("da ali sa podgrupama" — the script decides what his
    # dictated text comes out AS), and keying a VOICE by its locale drops every
    # voice of a language but the first. Both make a tidier card that offers
    # him LESS, so the checks assert one row per language AND every real
    # variant still reachable. Both defects were caught by running the module
    # before it was wired; both are planted in the gate now.
    step("0b0/6  LANGUAGE GATE — language first, and grouping never costs a "
         "choice (tests/test_lang_groups.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_lang_groups.py")])

    # OWNER DECREE 2026-08-13, absolute: while the app is not up — closed,
    # minimized, backgrounded — NO manipulation of ours may remain on any
    # window. His report was a layout he could not raise after pressing the
    # Android home button, and the cause was MEASURED rather than reasoned: an
    # A/B over our own leave sequence with one variable (a modal dialog up or
    # not) showed the member coming back raisable and DISABLED. A modal
    # disables its owner until it is answered, and Windows hides the dialog
    # with the owner — so we minimized him into a window he could not click,
    # with the only thing that could unblock it parked where the layout had
    # wanted it. This gate is fail-closed because the class keeps returning:
    # constraint 10 answered the topmost half of it in 2026-08-05 and every
    # round since has found another residue the exit path never undid.
    step("0b1/6  SESSION RESIDUE GATE — nothing we force on a window outlives "
         "the session (tests/test_session_residue.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_session_residue.py")])

    # OWNER REQUEST 2026-08-13: the Traffic window's "this session X MB"
    # line gains session length, MB/h, and WHICH device(s) sent it — named
    # where a name was ever learned, else identified by resolution — with
    # the chart's line coloured differently per device. The identity must
    # be stable across a reconnect and across a server restart (persisted,
    # `layout_history.py`'s own precedent), and an older CSV row with no
    # `device` column must keep reading — the long-term record cannot break
    # on the day this shipped.
    step("0b2/6  TRAFFIC DEVICES GATE — a stable per-device identity, "
         "session length/rate, and the old-CSV-still-reads promise "
         "(tests/test_traffic_devices.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_traffic_devices.py")])

    # OWNER REPORT 2026-08-13, the correction of the round above: `focus()`
    # ignored `lay.adopted` entirely, and every path that stopped a layout
    # being shown (another layout focused, Desktop chosen) called
    # `release_adopted()` unconditionally — which treated a MERE SWITCH as
    # the popup's session ending, moving it home and forgetting it outright.
    # His words: switch to another layout or the desktop and come back, and
    # "this new window just stands there, nowhere put into a layout." Fixed
    # with `drop_adopted_topmost()` (lowers, keeps the adoption) for a
    # mid-session switch and `focus()` re-containing on the way back in;
    # `release_adopted()` now runs only where the adoption truly ends
    # (removed/pruned, or `presence.leave_session`). Its own file by
    # RESPONSIBILITY, same split as 0b1/6 above: that gate asks what must be
    # true once the phone is gone; this one asks what must be true when the
    # SAME layout is shown again, mid-session — plus the chip's wording
    # (defect 2), which used to read like an offer to create a layout when
    # its yes has only ever moved the window into the one already open.
    step("0b3/6  LAYOUT ADOPTION LIFECYCLE GATE — an adopted window survives "
         "a layout switch, not just the session (tests/test_layout_adoption.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_layout_adoption.py")])
