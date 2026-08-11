# Build APK

**Script:** [Build APK (script)](../build_apk.py) ·
**Flow:** [diagram](../__flow/build_apk.md)

## Purpose

Builds the Android app (see [Android (folder)](../../android/___android.md))
into a signed release APK: locates the dev-machine toolchain (Android
Studio's bundled JDK + the local Android SDK + a vendored Gradle, downloaded
on first run), generates the release signing keystore once, runs
`gradlew assembleRelease` with version properties derived from
`setup/app_info.json`, and copies the signed APK to `dist/VibeCoder.apk` —
the server offers it at `/app.apk` and `build.py` bundles it into the
desktop installer when it exists. Must run BEFORE `build.py` so the
installer picks up a fresh APK: `.venv\Scripts\python setup/build_apk.py`.

**Tier note:** classed Algorithmic (not Standard), by the same reasoning as
`build.py` — it is a small multi-step build PROTOCOL with real conditional
decision logic, not straight-line glue: the keystore
generate-once-then-reuse branch, the on-first-run Gradle wrapper generation,
and the version-code derivation from the semantic version string.

## Connections

### Uses
- `setup/app_info.json` — `version`, passed to Gradle as `-PappVersion` /
  `-PappVersionCode`
- [Android (folder)](../../android/___android.md) — `android/gradlew.bat`
  (generated on first run from the vendored Gradle), `android/keystore/`
  (created here, gitignored), `android/local.properties` (written here)
- Android Studio's bundled JDK, hardcoded to
  `C:\Program Files\Android\Android Studio\jbr`
- The local Android SDK at `%LOCALAPPDATA%\Android\Sdk`
- Gradle 8.10.2, downloaded from `services.gradle.org` into
  `setup/vendor/gradle-8.10.2/` on first run only (cached afterward)

### Used by
- The owner / a build session, run manually before `build.py` — see
  [Build Orchestrator](build.md), whose `build_pyinstaller()` bundles
  `android/app/build/outputs/apk/release/app-release.apk` when it exists

## Functions

### `check_toolchain() -> None`
Verifies the JBR JDK and the Android SDK exist — hard `sys.exit(1)` if
either is missing (dev-machine prerequisites, never auto-installed).
Downloads and unzips Gradle into `setup/vendor/` if the pinned version isn't
cached yet. Writes `android/local.properties` (`sdk.dir=...`) so Gradle can
find the SDK — regenerated every run, never committed.

### `ensure_keystore(env) -> str`
Reuses `android/keystore/release.jks` and its persisted password if
present; otherwise generates a fresh 2048-bit RSA keystore via
`keytool -genkeypair` (10000-day validity, alias `vibecoder`,
`CN=UVuruna, O=UVuruna`) and a random 24-byte password, persisting both to
`android/keystore/`. The keystore is never regenerated once created —
losing it breaks upgrade signing for every phone that already has the app
installed.

### `build(env, password) -> Path`
Generates the Gradle wrapper on first run (when `gradlew.bat` is missing)
using the vendored Gradle directly. Derives `version_code` as the INTEGER
value of the version string's LAST dot-segment (e.g. `"0.0.051"` →
version code `51`) and runs
`gradlew --no-daemon assembleRelease -PappVersion=... -PappVersionCode=...`
with the keystore path/password/alias injected as the `RU_KEYSTORE` /
`RU_KEYSTORE_PASS` / `RU_KEY_ALIAS` environment variables. Exits 1 if the
expected release APK path doesn't exist afterward.

### `main() -> None`
Runs the three steps above in order, then copies the signed APK to
`dist/VibeCoder.apk`.
