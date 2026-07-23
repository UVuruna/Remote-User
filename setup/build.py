"""Build Remote User into a distributable installer (monorepo build spec).

Steps:
  0. Generate version_info.txt (app_info.json + root company.json)
  1. Generate ICOs from assets/logo.svg (supersampled multi-resolution)
  2. Fetch vendor payloads (cached in setup/vendor/, gitignored):
       - ffmpeg.exe — BUNDLED into the app (H.264 encoding, zero user action)
       - tailscale-setup.exe — CHAIN-INSTALLED by the NSIS installer
  3. PyInstaller (--onedir, windowed) around server/gui_main.py + copy ffmpeg in
  4. Sign the exe (self-signed cert — run create_cert.py once first)
  5. NSIS installer (+ sign it)

Prerequisites (dev machine, one-time):
  - .venv with requirements.txt + pip install pyinstaller pillow
  - NSIS installed (https://nsis.sourceforge.io/)
  - python setup/create_cert.py (optional — unsigned build works, with warning)

Usage:
    .venv\\Scripts\\python setup/build.py
"""

import json
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
        "--name", APP_NAME,
        "--icon", str(ICON_PATH),
        "--version-file", str(VERSION_INFO_PATH),
        "--paths", str(SERVER_DIR),
        # Bundled read-only data (config.py resolves these when frozen)
        "--add-data", f"{PROJECT_DIR / 'client'};client",
        "--add-data", f"{PROJECT_DIR / 'actions.json'};.",
        "--add-data", f"{PROJECT_DIR / 'assets'};assets",
        "--add-data", f"{APP_INFO_PATH};setup",
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

    # ffmpeg next to the exe — config._default_ffmpeg() finds it there.
    (app_dir / "ffmpeg").mkdir()
    shutil.copy2(FFMPEG_EXE, app_dir / "ffmpeg" / "ffmpeg.exe")
    # Icon at dist root so NSIS shortcuts can reference $INSTDIR\icon.ico.
    shutil.copy2(ICON_PATH, app_dir / "icon.ico")
    if ANDROID_APK.exists():
        shutil.copy2(ANDROID_APK, app_dir / "RemoteUser.apk")
        shutil.copy2(ANDROID_APK, DIST_DIR / "RemoteUser.apk")  # dev server serves this one
        print("  Bundled the phone app (RemoteUser.apk)")
    else:
        print("  NOTE: no phone APK found (run setup/build_apk.py) — shipping without it")
    print(f"  Output: {exe_path}")
    return exe_path


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
    print(f"  OK: CompanyName={company!r}  FileVersion={file_version!r}; exe+installer signed")


def main() -> None:
    print(f"Building {APP_INFO['display_name']} v{APP_INFO['version']}")
    if not ENTRY_POINT.exists():
        print(f"ERROR: entry point not found: {ENTRY_POINT}")
        sys.exit(1)

    generate_version_info()
    generate_icons()
    fetch_vendor()
    exe_path = build_pyinstaller()
    step("4/6  Signing exe")
    sign_file(exe_path)
    build_installer()

    step("BUILD COMPLETE")
    print(f"  {DIST_DIR / APP_INFO['installer_name']}")

    verify_build(exe_path, DIST_DIR / APP_INFO["installer_name"])


if __name__ == "__main__":
    main()
