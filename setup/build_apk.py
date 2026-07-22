"""Build the Remote User Android APK (the phone shell around the web client).

Steps:
  1. Toolchain: Android Studio's bundled JDK + the SDK in %LOCALAPPDATA%;
     Gradle from setup/vendor (downloaded by this script if missing) — the
     wrapper in android/ is generated on first run.
  2. Keystore: generated ONCE into android/keystore/ (gitignored — back it
     up; losing it means users must uninstall/reinstall on upgrades).
  3. gradlew assembleRelease with version props from setup/app_info.json.
  4. Copy the signed APK to dist/RemoteUser.apk — the server offers it at
     /app.apk ("Get the app" on the phone page), and the desktop installer
     bundles it when present.

Usage:
    .venv\\Scripts\\python setup/build_apk.py
"""

import json
import os
import secrets
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

SETUP_DIR = Path(__file__).parent
PROJECT_DIR = SETUP_DIR.parent
ANDROID_DIR = PROJECT_DIR / "android"
DIST_DIR = PROJECT_DIR / "dist"
VENDOR_DIR = SETUP_DIR / "vendor"

GRADLE_VERSION = "8.10.2"
GRADLE_DIR = VENDOR_DIR / f"gradle-{GRADLE_VERSION}"
GRADLE_URL = f"https://services.gradle.org/distributions/gradle-{GRADLE_VERSION}-bin.zip"

JBR = Path(r"C:\Program Files\Android\Android Studio\jbr")
SDK_DIR = Path(os.environ["LOCALAPPDATA"]) / "Android" / "Sdk"

KEYSTORE_DIR = ANDROID_DIR / "keystore"
KEYSTORE = KEYSTORE_DIR / "release.jks"
KEYSTORE_PASS_FILE = KEYSTORE_DIR / "password.txt"
KEY_ALIAS = "remoteuser"

APP_INFO = json.loads((SETUP_DIR / "app_info.json").read_text(encoding="utf-8"))


def step(msg: str) -> None:
    print(f"\n{'=' * 60}\n  {msg}\n{'=' * 60}")


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> None:
    print(f"  > {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=cwd, env=env, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"  FAILED (exit {result.returncode})")
        if result.stderr:
            print(result.stderr[-3000:])
        sys.exit(1)


def check_toolchain() -> None:
    step("1/4  Toolchain")
    if not (JBR / "bin" / "java.exe").exists():
        print(f"  ERROR: JDK not found at {JBR} — install Android Studio.")
        sys.exit(1)
    if not SDK_DIR.exists():
        print(f"  ERROR: Android SDK not found at {SDK_DIR}.")
        sys.exit(1)
    if not GRADLE_DIR.exists():
        VENDOR_DIR.mkdir(parents=True, exist_ok=True)
        zip_path = VENDOR_DIR / "gradle.zip"
        print(f"  Downloading Gradle {GRADLE_VERSION}…")
        urllib.request.urlretrieve(GRADLE_URL, zip_path)  # noqa: S310 — fixed https URL
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(VENDOR_DIR)
        zip_path.unlink()
    print(f"  JDK: {JBR}\n  SDK: {SDK_DIR}\n  Gradle: {GRADLE_DIR}")
    # local.properties tells Gradle where the SDK lives (gitignored).
    (ANDROID_DIR / "local.properties").write_text(
        "sdk.dir=" + str(SDK_DIR).replace("\\", "\\\\") + "\n", encoding="utf-8"
    )


def ensure_keystore(env: dict) -> str:
    step("2/4  Signing keystore")
    if KEYSTORE.exists():
        password = KEYSTORE_PASS_FILE.read_text(encoding="utf-8").strip()
        print(f"  Reusing {KEYSTORE}")
        return password
    KEYSTORE_DIR.mkdir(exist_ok=True)
    password = secrets.token_urlsafe(24)
    KEYSTORE_PASS_FILE.write_text(password, encoding="utf-8")
    run([
        str(JBR / "bin" / "keytool.exe"), "-genkeypair",
        "-keystore", str(KEYSTORE), "-alias", KEY_ALIAS,
        "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
        "-storepass", password, "-keypass", password,
        "-dname", "CN=UVuruna, O=UVuruna",
    ], env=env)
    print(f"  Created {KEYSTORE} — android/keystore/ is gitignored; BACK IT UP:")
    print("  losing it means phone upgrades require uninstall/reinstall.")
    return password


def build(env: dict, password: str) -> Path:
    step("3/4  gradlew assembleRelease")
    gradlew = ANDROID_DIR / "gradlew.bat"
    if not gradlew.exists():
        # One-time: generate the committed wrapper with the vendored Gradle.
        run([str(GRADLE_DIR / "bin" / "gradle.bat"), "wrapper",
             "--gradle-version", GRADLE_VERSION], cwd=ANDROID_DIR, env=env)
    version = APP_INFO["version"]
    version_code = str(int(version.split(".")[-1]))
    env = {**env,
           "RU_KEYSTORE": str(KEYSTORE),
           "RU_KEYSTORE_PASS": password,
           "RU_KEY_ALIAS": KEY_ALIAS}
    run([str(gradlew), "--no-daemon", "assembleRelease",
         f"-PappVersion={version}", f"-PappVersionCode={version_code}"],
        cwd=ANDROID_DIR, env=env)
    apk = ANDROID_DIR / "app" / "build" / "outputs" / "apk" / "release" / "app-release.apk"
    if not apk.exists():
        print(f"  ERROR: APK not found at {apk}")
        sys.exit(1)
    return apk


def main() -> None:
    print(f"Building Remote User APK v{APP_INFO['version']}")
    env = {**os.environ, "JAVA_HOME": str(JBR)}
    check_toolchain()
    password = ensure_keystore(env)
    apk = build(env, password)

    step("4/4  Publish to dist/")
    DIST_DIR.mkdir(exist_ok=True)
    target = DIST_DIR / "RemoteUser.apk"
    shutil.copy2(apk, target)
    print(f"  {target} ({target.stat().st_size / 1e6:.1f} MB)")
    print("  The server now offers it at /app.apk (phone page shows 'Get the app').")


if __name__ == "__main__":
    main()
