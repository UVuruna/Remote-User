"""Build Remote User into a distributable installer (monorepo build spec).

Steps:
  0. Generate version_info.txt (app_info.json + root company.json)
  0b. INPUT GATE: tests/test_input_pipeline.py — real page + real server +
      headless Chromium touch; a broken click path fails the BUILD, never
      ships (fail-closed; "left click dead" shipped twice before this gate)
  1. Generate ICOs from assets/logo.svg (supersampled multi-resolution)
  2. Fetch vendor payloads (cached in setup/vendor/, gitignored):
       - ffmpeg.exe — BUNDLED into the app (H.264 encoding, zero user action)
       - tailscale-setup.exe — CHAIN-INSTALLED by the NSIS installer
  3. PyInstaller (--onedir, windowed) around server/gui_main.py + copy ffmpeg in
  3b. Smoke test: run the frozen exe with --selfcheck so a missing bundled
      module fails the BUILD, not the user's first launch (fail-closed)
  4. Sign the exe (self-signed cert — run create_cert.py once first)
  5. NSIS installer (+ sign it)

The build always runs under the project's .venv (it re-execs itself there if
launched with another interpreter) — otherwise PyInstaller bundles from an
incomplete env and silently drops deps (a system-Python build shipped v0.0.045
without `qrcode` and crashed on launch).

Prerequisites (dev machine, one-time):
  - .venv with requirements.txt + pip install pyinstaller pillow
  - pip install playwright && playwright install chromium (the input gate)
  - NSIS installed (https://nsis.sourceforge.io/)
  - python setup/create_cert.py (optional — unsigned build works, with warning)

Usage:
    python setup/build.py            (auto-re-execs under .venv)
    .venv\\Scripts\\python setup/build.py
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

# -- Paths ---------------------------------------------------------
SETUP_DIR = Path(__file__).parent
PROJECT_DIR = SETUP_DIR.parent
SERVER_DIR = PROJECT_DIR / "server"
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"
VENDOR_DIR = SETUP_DIR / "vendor"

ICON_PATH = SETUP_DIR / "icon.ico"
ICON_SETUP_PATH = SETUP_DIR / "icon-setup.ico"
PASSWORD_PATH = SETUP_DIR / "cert" / "password.txt"
NSI_PATH = SETUP_DIR / "installer.nsi"
APP_INFO_PATH = SETUP_DIR / "app_info.json"
AGENT_HOOK_PATH = SETUP_DIR / "agent_hook.py"
COMPANY_JSON_PATH = PROJECT_DIR.parent.parent / "company.json"
VERSION_INFO_PATH = SETUP_DIR / "version_info.txt"

# Vendor payloads. ffmpeg: gyan.dev "essentials" build, PINNED to 7.1.1 — the
# latest git builds need NVENC API 13.1 (NVIDIA driver >= 610), which silently
# knocks hardware encoding down to libx264 on machines with slightly older
# drivers (found on the dev PC itself). 7.1.1 keeps NVENC working across a wide
# driver range. Tailscale: the official stable-latest installer alias.
FFMPEG_ZIP_URL = ("https://github.com/GyanD/codexffmpeg/releases/download/"
                  "7.1.1/ffmpeg-7.1.1-essentials_build.zip")  # gyan.dev's GitHub mirror
FFMPEG_EXE = VENDOR_DIR / "ffmpeg" / "ffmpeg.exe"
TAILSCALE_URL = "https://pkgs.tailscale.com/stable/tailscale-setup-latest.exe"
TAILSCALE_EXE = VENDOR_DIR / "tailscale-setup.exe"

APP_INFO = json.loads(APP_INFO_PATH.read_text(encoding="utf-8"))
COMPANY = json.loads(COMPANY_JSON_PATH.read_text(encoding="utf-8"))
APP_NAME = APP_INFO["name"]
CERT_PATH = SETUP_DIR / "cert" / f"{APP_NAME}.pfx"
ENTRY_POINT = SERVER_DIR / "gui_main.py"
# The phone app (built by setup/build_apk.py) rides along when present — the
# installed server serves it at /app.apk (Android browsers get the install funnel).
ANDROID_APK = PROJECT_DIR / "android" / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"

# PyInstaller misses uvicorn's importlib-loaded backends without these.
HIDDEN_IMPORTS = [
    "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto", "uvicorn.loops.asyncio",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl", "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    # uia.py imports uiautomation LAZILY (per-thread COM init) — PyInstaller
    # cannot see it, and without these the frozen app would silently lose the
    # tab layer (window layouts still work — uia fails soft by design).
    "uiautomation", "comtypes", "comtypes.client", "comtypes.stream",
    "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan", "uvicorn.lifespan.on", "uvicorn.lifespan.off",
]

# Not used at runtime (numpy/cv2 ARE used — never exclude them).
EXCLUDE_MODULES = [
    "tkinter", "unittest", "pydoc", "xmlrpc", "setuptools", "pkg_resources",
    "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore",
    "PySide6.QtWebChannel", "PySide6.QtWebEngineQuick",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore",
]


def step(msg: str) -> None:
    print(f"\n{'=' * 60}\n  {msg}\n{'=' * 60}")


def reexec_under_venv() -> None:
    """Build with the project's own .venv so PyInstaller bundles the COMPLETE
    dependency set. Running under ANY other interpreter silently drops whatever
    that interpreter is missing — a system-Python build shipped v0.0.045 without
    `qrcode` and crashed on first launch. Re-exec once; the env sentinel guards
    against a loop and the missing-.venv case just proceeds (the smoke test then
    catches any gap)."""
    if os.environ.get("RU_BUILD_REEXEC"):
        return
    venv_py = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
    if not venv_py.exists() or venv_py.resolve() == Path(sys.executable).resolve():
        return
    print(f"Re-running the build under the project venv:\n  {venv_py}")
    env = {**os.environ, "RU_BUILD_REEXEC": "1"}
    raise SystemExit(
        subprocess.run([str(venv_py), str(Path(__file__).resolve()), *sys.argv[1:]], env=env).returncode
    )


def run(cmd: list[str], mask: str | None = None, **kwargs):
    """Run + print a command; on failure print the real stderr and exit.
    stdout stays inherited so PyInstaller/NSIS stream progress live.
    `mask` hides that argument (certificate password) in the printed line."""
    printable = ["***" if mask is not None and str(c) == mask else str(c) for c in cmd]
    print(f"  > {' '.join(printable)}")
    result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, **kwargs)
    if result.returncode != 0:
        print(f"  FAILED (exit code {result.returncode})")
        if result.stderr:
            print(f"  {result.stderr}")
        sys.exit(1)
    return result


def _powershell(script: str) -> str:
    result = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
    return result.stdout.strip()


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    nums = [int(p) for p in version.split(".")]
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


def generate_version_info() -> None:
    step("0/6  Generating version_info.txt")
    v = APP_INFO["version"]
    vt = _version_tuple(v)
    content = f"""\
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={vt},
    prodvers={vt},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'{COMPANY["company_name"]}'),
         StringStruct(u'FileDescription', u'{APP_INFO["description"]}'),
         StringStruct(u'FileVersion', u'{v}'),
         StringStruct(u'InternalName', u'{APP_INFO["name"]}'),
         StringStruct(u'LegalCopyright', u'{COMPANY["copyright_string"]}'),
         StringStruct(u'OriginalFilename', u'{APP_INFO["exe_name"]}'),
         StringStruct(u'ProductName', u'{APP_INFO["display_name"]}'),
         StringStruct(u'ProductVersion', u'{v}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [0x0409, 1200])])
  ]
)
"""
    VERSION_INFO_PATH.write_text(content, encoding="utf-8")
    print(f"  Version {v} · {COMPANY['company_name']}")


def input_gate() -> None:
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

    step("0ak/6  FREEZE OFFER GATE — the 4K@60 offer fires once and only "
         "once, and both answers persist (tests/test_freeze_offer.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_freeze_offer.py")])

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


def generate_icons() -> None:
    step("1/6  Generating ICOs from assets/logo.svg")
    run([sys.executable, str(SETUP_DIR / "svg_to_ico.py")])


def _download(url: str, dest: Path, label: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Downloading {label}…\n    {url}")
    start = time.time()
    tmp = dest.with_suffix(dest.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)  # noqa: S310 — fixed https URLs above
    tmp.replace(dest)
    print(f"    {dest.name}: {dest.stat().st_size / 1e6:.1f} MB in {time.time() - start:.0f}s")


def fetch_vendor() -> None:
    step("2/6  Vendor payloads (cached in setup/vendor)")
    if not FFMPEG_EXE.exists():
        zip_path = VENDOR_DIR / "ffmpeg-release-essentials.zip"
        if not zip_path.exists():
            _download(FFMPEG_ZIP_URL, zip_path, "ffmpeg (gyan.dev essentials)")
        print("  Extracting ffmpeg.exe…")
        with zipfile.ZipFile(zip_path) as z:
            member = next(n for n in z.namelist() if n.endswith("/bin/ffmpeg.exe"))
            FFMPEG_EXE.parent.mkdir(parents=True, exist_ok=True)
            FFMPEG_EXE.write_bytes(z.read(member))
        zip_path.unlink()  # keep only the exe (~90 MB zip is not worth caching)
    print(f"  ffmpeg.exe: {FFMPEG_EXE.stat().st_size / 1e6:.1f} MB")

    if not TAILSCALE_EXE.exists():
        _download(TAILSCALE_URL, TAILSCALE_EXE, "Tailscale installer")
    print(f"  tailscale-setup.exe: {TAILSCALE_EXE.stat().st_size / 1e6:.1f} MB")


def build_pyinstaller() -> Path:
    step("3/6  PyInstaller (--onedir, windowed)")
    for d in (DIST_DIR, BUILD_DIR):
        if d.exists():
            print(f"  Cleaning {d}")
            shutil.rmtree(d)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--onedir", "--windowed",
        # Elevated ALWAYS. Windows (UIPI) silently discards SendInput from a
        # non-elevated process whenever an elevated window has focus — the
        # 2026-07-29 live failure: every phone session completely dead (mouse,
        # click, scroll, keys), stream fine, zero errors anywhere. For an
        # input injector elevation IS the core function (root spec:
        # "--uac-admin only when required" — here it is). Autostart must use
        # Task Scheduler /RL HIGHEST (installer.nsi) — HKCU Run silently
        # refuses to start elevated apps.
        "--uac-admin",
        "--name", APP_NAME,
        "--icon", str(ICON_PATH),
        "--version-file", str(VERSION_INFO_PATH),
        "--paths", str(SERVER_DIR),
        # Bundled read-only data (config.py resolves these when frozen)
        "--add-data", f"{PROJECT_DIR / 'client'};client",
        "--add-data", f"{PROJECT_DIR / 'actions.json'};.",
        "--add-data", f"{PROJECT_DIR / 'assets'};assets",
        "--add-data", f"{APP_INFO_PATH};setup",
        # The notifier hook the Settings switch installs. It was missing from
        # the bundle, so the switch could not be turned on in the INSTALLED app
        # at all — it printed "[Errno 2] No such file or directory:
        # …\\_internal\\setup\\agent_hook.py" and stayed off (owner screenshot
        # 2026-08-06). notify._hook_module() looks for exactly this path.
        "--add-data", f"{AGENT_HOOK_PATH};setup",
    ]
    for mod in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", mod]
    for mod in EXCLUDE_MODULES:
        cmd += ["--exclude-module", mod]
    cmd.append(str(ENTRY_POINT))

    start = time.time()
    run(cmd)
    print(f"  PyInstaller completed in {time.time() - start:.1f}s")

    app_dir = DIST_DIR / APP_NAME
    exe_path = app_dir / APP_INFO["exe_name"]
    if not exe_path.exists():
        print(f"  ERROR: expected exe not found: {exe_path}")
        sys.exit(1)

    # PAYLOAD GATE — fail-closed on data that only the INSTALLED app misses.
    # A file left out of --add-data breaks nothing here and nothing in the
    # smoke test (which imports the module graph, not the data): it breaks on
    # the owner's PC, as a switch that cannot be turned on. Every path the
    # frozen code resolves under BUNDLE_DIR is listed here.
    missing = [rel for rel in ("client/index.html", "actions.json",
                               "assets/logo.svg", "assets/check.svg",
                               # …and its light-palette twin: QSS `image:`
                               # cannot re-tint, so each palette loads its own
                               # tick file (gui/theme.py token `checkAsset`)
                               # and its own combo caret (`caretAsset`).
                               "assets/check-light.svg",
                               "assets/caret.svg", "assets/caret-light.svg",
                               # The three door buttons on the main window
                               # (round R2). A missing icon does not crash —
                               # `theme.icon()` logs and returns an empty one
                               # — which is exactly why it needs a gate: the
                               # owner would just see three unlabelled-looking
                               # buttons and nobody would know why.
                               "assets/icon-controls.svg", "assets/icon-traffic.svg",
                               "assets/icon-settings.svg",
                               "setup/app_info.json", "setup/agent_hook.py")
               if not (app_dir / "_internal" / rel).exists()]
    if missing:
        print("  ERROR: bundled payload missing — the installed app would fail "
              "where this build cannot: " + ", ".join(missing))
        sys.exit(1)
    print("  OK: bundled payload complete (client, actions, assets, setup)")

    # ffmpeg next to the exe — config._default_ffmpeg() finds it there.
    (app_dir / "ffmpeg").mkdir()
    shutil.copy2(FFMPEG_EXE, app_dir / "ffmpeg" / "ffmpeg.exe")
    # Icon at dist root so NSIS shortcuts can reference $INSTDIR\icon.ico.
    shutil.copy2(ICON_PATH, app_dir / "icon.ico")
    if ANDROID_APK.exists():
        shutil.copy2(ANDROID_APK, app_dir / "RemoteUser.apk")
        shutil.copy2(ANDROID_APK, DIST_DIR / "RemoteUser.apk")  # dev server serves this one
        # The sidecar version rides along — config.apk_version tells the
        # phone what /app.apk actually is (update-banner truth).
        apk_ver = ANDROID_APK.with_name(ANDROID_APK.name + ".version")
        if apk_ver.exists():
            shutil.copy2(apk_ver, app_dir / "RemoteUser.apk.version")
            shutil.copy2(apk_ver, DIST_DIR / "RemoteUser.apk.version")
        print("  Bundled the phone app (RemoteUser.apk)")
    else:
        print("  NOTE: no phone APK found (run setup/build_apk.py) — shipping without it")
    print(f"  Output: {exe_path}")
    return exe_path


def smoke_test(exe_path: Path) -> None:
    """Fail-closed: run the FROZEN exe's --selfcheck so a missing bundled module
    fails the BUILD, not the user's first launch (the v0.0.045 qrcode crash). The
    exe imports its whole module graph and exits 0; anything missing → non-zero.
    Runs before signing — no point signing/packaging an exe that cannot import."""
    step("3b/6  Smoke test (frozen exe imports its module graph)")
    print(f"  > {exe_path} --selfcheck")
    try:
        result = subprocess.run(
            [str(exe_path), "--selfcheck"], timeout=180,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
    except subprocess.TimeoutExpired:
        print("  FAIL: --selfcheck timed out (the app hung on import)")
        sys.exit(1)
    if result.returncode != 0:
        print(f"  FAIL: --selfcheck exited {result.returncode} — a bundled module is missing:")
        for line in (result.stdout or "").strip().splitlines():
            print(f"    {line}")
        sys.exit(1)
    print("  OK: the frozen app imports its whole module graph")


def sign_file(file_path: Path) -> bool:
    """Sign one file with the project certificate; shared by exe + installer
    steps. Missing cert/signtool skips with a warning (build stays usable)."""
    if not CERT_PATH.exists():
        print(f"  WARNING: certificate not found: {CERT_PATH}")
        print("  Run 'python setup/create_cert.py' once. Skipping signing…")
        return False

    signtool = shutil.which("signtool")
    if not signtool:
        for sdk_base in (Path(r"C:\Program Files (x86)\Windows Kits\10\bin"),
                         Path(r"C:\Program Files\Windows Kits\10\bin")):
            if sdk_base.exists():
                candidates = sorted(sdk_base.glob("10.*/x64/signtool.exe"))
                if candidates:
                    signtool = str(candidates[-1])
                    break
    if not signtool:
        print("  WARNING: signtool.exe not found (install Windows SDK). Skipping signing…")
        return False

    password = PASSWORD_PATH.read_text(encoding="utf-8").strip()
    run([signtool, "sign", "/f", str(CERT_PATH), "/p", password,
         "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256",
         str(file_path)], mask=password)
    print(f"  Signed: {file_path.name}")
    return True


def build_installer() -> None:
    step("5/6  NSIS installer")
    makensis = shutil.which("makensis")
    if not makensis:
        for p in (Path(r"C:\Program Files (x86)\NSIS\makensis.exe"),
                  Path(r"C:\Program Files\NSIS\makensis.exe")):
            if p.exists():
                makensis = str(p)
                break
    if not makensis:
        print("  ERROR: makensis.exe not found — install NSIS (https://nsis.sourceforge.io/)")
        sys.exit(1)

    run([
        makensis,
        f"/DPROJECT_DIR={PROJECT_DIR}",
        f"/DDIST_DIR={DIST_DIR}",
        f"/DSETUP_DIR={SETUP_DIR}",
        f"/DVENDOR_DIR={VENDOR_DIR}",
        f"/DAPP_VERSION={APP_INFO['version']}",
        f"/DAPP_PUBLISHER={COMPANY['company_name']}",
        f"/DAPP_URL={COMPANY['website']}",
        str(NSI_PATH),
    ])

    installer_path = DIST_DIR / APP_INFO["installer_name"]
    if not installer_path.exists():
        print("  WARNING: installer not found at the expected location.")
        return
    print(f"  Installer: {installer_path} ({installer_path.stat().st_size / 1e6:.1f} MB)")

    step("6/6  Signing installer")
    sign_file(installer_path)


def verify_build(exe_path: Path, installer_path: Path) -> None:
    """Fail-closed gate: a build must not silently ship broken metadata or
    an unsigned installer. Cert/password absence is a normal skip (matches
    sign_file's own unsigned-build fallback), not a failure."""
    step("VERIFY  metadata + signatures (build fails if anything is missing)")
    problems = []
    info = _powershell(f"$v=(Get-Item '{exe_path}').VersionInfo; \"$($v.CompanyName)|$($v.FileVersion)\"")
    company, _, file_version = info.partition("|")
    expected_company = COMPANY["company_name"]
    if company != expected_company:
        problems.append(f"exe CompanyName is {company!r}, expected {expected_company!r}")
    app_version = APP_INFO["version"]
    if app_version not in file_version:
        problems.append(f"exe FileVersion is {file_version!r}, expected to contain {app_version!r}")
    if CERT_PATH.exists() and PASSWORD_PATH.exists():
        for label, target in (("exe", exe_path), ("installer", installer_path)):
            status = _powershell(f"(Get-AuthenticodeSignature '{target}').Status")
            if status in ("", "NotSigned"):
                problems.append(f"{label} is NOT signed (status {status or 'missing'!r})")
    if problems:
        for p in problems:
            print(f"  FAIL: {p}")
        sys.exit(1)
    print(f"  OK: CompanyName={company!r}  FileVersion={file_version!r}")
    if CERT_PATH.exists() and PASSWORD_PATH.exists():
        print("  OK: exe + installer signed")
    else:
        print("  NOTE: signing skipped (no certificate) — installer is UNSIGNED")


def main() -> None:
    reexec_under_venv()  # ensure PyInstaller runs under the complete .venv env
    # Task 187 closer (d): never build over an update in flight on this
    # machine — a refusal must cost nothing, so it runs before anything does.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from release_hygiene import assert_clear_to_release
    assert_clear_to_release()
    print(f"Building {APP_INFO['display_name']} v{APP_INFO['version']}")
    if not ENTRY_POINT.exists():
        print(f"ERROR: entry point not found: {ENTRY_POINT}")
        sys.exit(1)

    generate_version_info()
    input_gate()
    generate_icons()
    fetch_vendor()
    exe_path = build_pyinstaller()
    smoke_test(exe_path)
    step("4/6  Signing exe")
    sign_file(exe_path)
    build_installer()

    step("BUILD COMPLETE")
    print(f"  {DIST_DIR / APP_INFO['installer_name']}")

    verify_build(exe_path, DIST_DIR / APP_INFO["installer_name"])


if __name__ == "__main__":
    main()
