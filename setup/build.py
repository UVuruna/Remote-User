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
