"""THE IN-APP UPDATE GATE — an install carries elevated trust, and every
promise this feature makes has to be provable from the SOURCE rather than
argued about, because Kotlin cannot be executed in this repo (no JVM test
runner, no device attached — the same honest limit test_shell_battery.py and
test_notice_channel.py's shell half already carry).

WHAT CHANGED (2026-08-17): the shell used to hand `/app.apk` to Android's own
`ACTION_VIEW` — a detour through the system browser that downloaded a file
the user then had to find and tap. It now streams the APK straight from the
PC into a `PackageInstaller` session's own `OutputStream` (`Updater.kt`) and
reports real progress to the page (`client/update-banner.js`), through three
new bridge methods (`Bridge.kt`).

EIGHT PROMISES, each proven by planting its own defect:

  1. THE OLD FALLBACK STILL EXISTS. A page served by THIS PC can meet a shell
     older than this round (the page and the shell version independently —
     the project's standing rule, restated in every bridge method's own
     comment). Deleting `Bridge.update(url)` or its caller in
     update-banner.js would strand that shell with no update path at all.
  2. THE NEW BRIDGE SURFACE IS EXACTLY THE THREE AGREED NAMES, spelled
     exactly, each `@JavascriptInterface`. The page is served by the PC while
     the shell installs separately — a renamed method is a silently DEAD
     feature, not a build error, because nothing on either side would ever
     say so.
  3. THE PERMISSION IS DECLARED. `REQUEST_INSTALL_PACKAGES` in the manifest —
     without it `canRequestPackageInstalls()` can never return true and the
     card would sit on "permission" forever.
  4. NO FILE-BASED INSTALL PATH CAME BACK. `Updater.kt` streams into the
     session directly; `DownloadManager` and a FileProvider-shared APK exist
     nowhere in `android/`. An install carries elevated trust by definition,
     and a shareable copy of the APK sitting in cache/Downloads is a surface
     this feature does not need — a wrong grant, a backup, or a stray
     FileProvider path could point at it for no reason.
  5. THE URL IS VALIDATED BEFORE ANYTHING IS INSTALLED, by PARSED components
     — never a string prefix. `http://1.2.3.4.evil.com/app.apk` and
     `http://evil.com/?x=http://192.168.1.5/app.apk` both defeat a
     `startsWith` check while failing a real `URL(...)` parse comparison; a
     gate that accepted any validation at all would miss the actual bug this
     promise exists to close.
  6. NO SUCCESS STATE IS EVER CLAIMED. The four LIVE page states are exactly
     `permission` / `downloading` / `installing` / `failed` — never
     `"success"` / `"done"` / `"installed"`, because a completed install
     kills this very process and no later call could ever tell a page that
     no longer has a process to run in.
  7. THE CUBE IS NOT WRITTEN TWICE (monorepo priority C — never write the
     same function twice). `client/cube.js` is the only place the face table
     and the burst/decay arithmetic live; `loading.js` and the update card
     both go through `createCube()`.
  8. THE PROGRESS SHOWN IS NEVER INVENTED. `update-banner.js` cannot print a
     percentage when the total is unknown (`total <= 0`) — a fabricated
     number is exactly the "frozen ellipsis pretending to track it" failure
     task 207's own comment in that file warns against.

THREE MORE (2026-08-18 — THE WAY BACK IN). A successful install replaces our
process and the app disappears off the screen; the owner had to reopen it by
hand. `UpdateReturn.kt` is a manifest-declared receiver for
`MY_PACKAGE_REPLACED` that tries to open the app and ALWAYS posts a
"tap to return" notification. Its three promises:

  9. THE RECEIVER IS DECLARED IN THE MANIFEST, `exported="false"`, filtering
     MY_PACKAGE_REPLACED. A runtime registration cannot work here — our
     process is dead at that moment, which is the whole point — so the
     manifest entry IS the feature. Losing it, or widening it to the broad
     `ACTION_PACKAGE_REPLACED`, is a silent failure: nothing would ever say
     that the way back in is gone.
 10. IT POSTS THROUGH `Notifier` AND BUILDS NO NOTIFICATION OF ITS OWN
     (monorepo priority C — inheritance over duplication). A second builder
     here would mean a second channel, a second PendingIntent shape and a
     second place for the tap target to drift away from `MainActivity`.
 11. THE ACTIVITY START IS INSIDE A `catch`. On Android 10+ a background
     activity start is normally FORBIDDEN, so the direct start is best effort
     ONLY; a throwing refusal must never crash the receiver and cost him the
     notification, which is the carrier that actually works.

Kotlin checks read the SOURCE and assert the structural promises — the same
shape test_shell_battery.py and test_battery_report.py use for the parts of
this app that cannot run here. What the shell really does on a real handset
is proven only on the owner's device.

Run:  .venv\\Scripts\\python tests/test_apk_update.py
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
ANDROID = PROJECT / "android"
CLIENT = PROJECT / "client"
KOTLIN_DIR = ANDROID / "app" / "src" / "main" / "java" / "com" / "uvuruna" / "vibecoder"

UPDATER_KT = KOTLIN_DIR / "Updater.kt"
UPDATE_RETURN_KT = KOTLIN_DIR / "UpdateReturn.kt"
BRIDGE_KT = KOTLIN_DIR / "Bridge.kt"
MANIFEST = ANDROID / "app" / "src" / "main" / "AndroidManifest.xml"
UPDATE_BANNER_JS = CLIENT / "update-banner.js"
CUBE_JS = CLIENT / "cube.js"
LOADING_JS = CLIENT / "loading.js"

# The forbidden words this feature must never say to the page — a state that
# claims the install is DONE is a lie no page can ever legitimately tell (see
# promise 6's header block for why the process that would say so is gone).
FORBIDDEN_STATE_WORDS = ("success", "done", "installed")

# The only four states a LIVE page render may be in — "offer" is the page's
# own resting state before any tap, never something the shell reports.
LIVE_STATES = {"permission", "downloading", "installing", "failed"}


def _text(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"{path} does not exist — the gate cannot check what is not there")
    return path.read_text(encoding="utf-8")


def _all_kotlin_files() -> list[Path]:
    return sorted(KOTLIN_DIR.glob("*.kt"))


# ─────────────────────────────────────────────────────────────────────────
# 1. THE OLD FALLBACK STILL EXISTS
# ─────────────────────────────────────────────────────────────────────────

def check_the_old_fallback_still_exists(problems: list[str]) -> None:
    bridge = _text(BRIDGE_KT)
    # The exact old signature, firing the exact old intent — not merely "a
    # method named update" but the ACTION_VIEW detour itself, since that is
    # what an older, unpatched shell already relies on existing.
    if not re.search(r"fun\s+update\s*\(\s*url\s*:\s*String\s*\)", bridge):
        problems.append(
            "android/.../Bridge.kt: no `fun update(url: String)` — the "
            "fallback for a shell too old to know about updateInApp is gone; "
            "a page served by this PC would strand that shell with no "
            "update path at all")
    else:
        body_start = bridge.index("fun update(")
        # Bound the search to roughly this one method's body — the next
        # `@JavascriptInterface` marks the start of the following method.
        next_marker = bridge.find("@JavascriptInterface", body_start)
        body = bridge[body_start:next_marker if next_marker != -1 else len(bridge)]
        if "ACTION_VIEW" not in body:
            problems.append(
                "android/.../Bridge.kt: `update(url)` no longer fires "
                "ACTION_VIEW — the browser-download fallback's own mechanism "
                "changed, which is exactly the risk of touching it at all")

    banner = _text(UPDATE_BANNER_JS)
    if "window.Android.updateInApp" not in banner:
        problems.append(
            "client/update-banner.js: no reference to window.Android.updateInApp "
            "— the page can no longer tell a new shell from an old one")
    if "window.Android.update(url)" not in banner:
        problems.append(
            "client/update-banner.js: the fallback branch no longer calls "
            "window.Android.update(url) — an old shell would get no update "
            "path at all when updateInApp is absent")


# ─────────────────────────────────────────────────────────────────────────
# 2. THE NEW BRIDGE SURFACE IS EXACTLY THE THREE AGREED NAMES
# ─────────────────────────────────────────────────────────────────────────

# name -> the exact signature shape, minus whitespace, that must appear
# directly under an @JavascriptInterface annotation. A renamed or re-typed
# method is a silently dead feature (the page calls a name that resolves to
# nothing and Android hands back `undefined`, no error anywhere).
BRIDGE_METHODS = {
    "updateInApp": re.compile(
        r"fun\s+updateInApp\s*\(\s*url\s*:\s*String\s*\)\s*:\s*Boolean"),
    "updateInstallAllowed": re.compile(
        r"fun\s+updateInstallAllowed\s*\(\s*\)\s*:\s*Boolean"),
    "updateAllowInstall": re.compile(
        r"fun\s+updateAllowInstall\s*\(\s*\)"),
}


def check_the_new_bridge_surface_is_exact(problems: list[str]) -> None:
    bridge = _text(BRIDGE_KT)
    # Every @JavascriptInterface annotation, and the method signature line(s)
    # that immediately follow it (KDoc comments may sit between — skipped by
    # searching a bounded window rather than the very next line).
    annotated_blocks = []
    for m in re.finditer(r"@JavascriptInterface", bridge):
        window = bridge[m.end():m.end() + 400]
        annotated_blocks.append(window)
    joined = "\n".join(annotated_blocks)

    for name, pattern in BRIDGE_METHODS.items():
        found_annotated = any(pattern.search(block) for block in annotated_blocks)
        if not found_annotated:
            # Distinguish "missing entirely" from "exists but not annotated"
            # — a bare Kotlin method callable from Java reflection is NOT
            # reachable from the WebView bridge; @JavascriptInterface is the
            # whole exposure mechanism, so a method that lost the annotation
            # is exactly as dead as one that was renamed.
            bare_name = re.search(r"fun\s+" + re.escape(name) + r"\s*\(", bridge)
            if bare_name:
                problems.append(
                    f"android/.../Bridge.kt: `{name}` exists but is not "
                    f"directly under an @JavascriptInterface annotation — "
                    f"the page cannot reach it at all")
            else:
                problems.append(
                    f"android/.../Bridge.kt: no @JavascriptInterface method "
                    f"named `{name}` with the agreed signature — a renamed "
                    f"bridge method is a silently dead feature")


# ─────────────────────────────────────────────────────────────────────────
# 3. THE PERMISSION IS DECLARED
# ─────────────────────────────────────────────────────────────────────────

def check_the_permission_is_declared(problems: list[str]) -> None:
    manifest = _text(MANIFEST)
    if 'android.permission.REQUEST_INSTALL_PACKAGES' not in manifest:
        problems.append(
            "android/.../AndroidManifest.xml: no "
            "<uses-permission android:name=\"android.permission."
            "REQUEST_INSTALL_PACKAGES\" /> — canRequestPackageInstalls() "
            "can never return true and the card would sit on \"permission\" "
            "forever")


# ─────────────────────────────────────────────────────────────────────────
# 4. NO FILE-BASED INSTALL PATH CAME BACK
# ─────────────────────────────────────────────────────────────────────────

def check_no_file_based_install_path(problems: list[str]) -> None:
    updater = _text(UPDATER_KT)
    if "openWrite(" not in updater:
        problems.append(
            "android/.../Updater.kt: no PackageInstaller.Session.openWrite() "
            "call — the streaming-into-a-session mechanism this whole "
            "promise depends on is gone")
    if not re.search(r"\bsession\b", updater):
        problems.append(
            "android/.../Updater.kt: no PackageInstaller session object in "
            "scope — nothing in this file looks like it is driving one")

    # DownloadManager anywhere in the REAL Kotlin sources (not a doc comment
    # explaining its absence — Updater.kt's own header names it BY DESIGN as
    # the thing it does not do, and that sentence must not itself trip this
    # check). WHY this matters: DownloadManager writes the APK to a location
    # another app can be granted a URI to — a surface this feature does not
    # need, since PackageInstaller.openWrite hands bytes to the installer
    # directly with nothing ever touching shared storage.
    for path in _all_kotlin_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                continue  # prose explaining the decision, not the decision reversing itself
            if "DownloadManager" in line:
                problems.append(
                    f"{path.relative_to(PROJECT)}:{lineno}: DownloadManager "
                    f"referenced in real code — the file-based install path "
                    f"this feature was built to remove is back: {stripped[:90]}")

    # A FileProvider URI built for the UPDATE path specifically. FileProvider
    # itself legitimately exists elsewhere in this shell (camera capture,
    # MainActivity.kt) — that is a different feature with a different need
    # (handing a picture to the page) and this check must not fire on it.
    # What matters here is narrower: Updater.kt itself must never construct
    # one for the APK, which would recreate exactly the shareable-copy
    # surface this feature exists to avoid.
    if "FileProvider" in _strip_kotlin_comments(updater):
        problems.append(
            "android/.../Updater.kt: references FileProvider — the update "
            "path must never create a shareable URI for the downloaded APK; "
            "see the class header for why (elevated trust needs no "
            "shareable copy)")


# ─────────────────────────────────────────────────────────────────────────
# 5. THE URL IS VALIDATED BEFORE ANYTHING IS INSTALLED, BY PARSED COMPONENTS
# ─────────────────────────────────────────────────────────────────────────

def check_the_url_is_validated_by_parsed_components(problems: list[str]) -> None:
    updater = _text(UPDATER_KT)

    # `start()` must refuse before doing any work — the check is on the
    # METHOD'S OWN GUARD, not merely on a helper existing unused somewhere.
    start_match = re.search(r"fun\s+start\s*\(\s*url\s*:\s*String\s*\)", updater)
    if not start_match:
        problems.append(
            "android/.../Updater.kt: no `fun start(url: String)` — cannot "
            "verify the url is checked before a download begins")
        return
    start_body = updater[start_match.start():start_match.start() + 600]
    if not re.search(r"if\s*\(\s*!\s*\w*isPairedApkUrl", start_body) and \
       "isPairedApkUrl" not in start_body:
        problems.append(
            "android/.../Updater.kt: start() does not call a paired-url "
            "check before beginning a download — an untrusted script in the "
            "WebView could point this at any host it likes")

    validator_match = re.search(
        r"fun\s+isPairedApkUrl\s*\(\s*url\s*:\s*String\s*\)\s*:\s*Boolean\s*\{",
        updater)
    if not validator_match:
        problems.append(
            "android/.../Updater.kt: no isPairedApkUrl(url: String): Boolean "
            "— cannot verify HOW the url is checked")
        return
    body_start = validator_match.end()
    # Bound the body to the next top-level `private fun` / `fun` at the same
    # indent — good enough for this file's own style (one function per
    # concern, no nesting of this depth).
    next_fun = re.search(r"\n    (private )?fun\s", updater[body_start:])
    body = updater[body_start:body_start + (next_fun.start() if next_fun else 2000)]

    # THE ACTUAL PROMISE: comparison is done on PARSED URL components
    # (.protocol / .host / .port, or an equivalent parsed accessor), never a
    # raw string prefix check. A prefix check is exactly what
    # `http://1.2.3.4.evil.com/app.apk` (a real prefix match on a stored
    # "http://1.2.3.4" string) and a decoy carried in a query parameter are
    # built to defeat — so this demands BOTH that URL(...) parsing happens
    # AND that the comparison reads parsed fields, and separately forbids
    # startsWith against the whole raw url string.
    parses_url = bool(re.search(r"\bURL\s*\(\s*(url|stored|target)\b", body))
    compares_host = ".host" in body and (".protocol" in body or ".getProtocol" in body)
    compares_port = "Port" in body  # effectivePort(...) or .port, either counts
    if not (parses_url and compares_host and compares_port):
        problems.append(
            "android/.../Updater.kt: isPairedApkUrl does not compare PARSED "
            "URL components (scheme/host/port) — a raw string comparison "
            "here would accept http://1.2.3.4.evil.com/app.apk or a decoy "
            "carried in a query parameter against the real paired address")

    if re.search(r"\bstartsWith\s*\(", body):
        problems.append(
            "android/.../Updater.kt: isPairedApkUrl calls startsWith — a "
            "prefix check on the raw url string is exactly what "
            "http://evil.com/?x=http://192.168.1.5/app.apk is built to "
            "defeat, even beside a parsed comparison")

    if "Prefs.lanUrl" not in body or "Prefs.tsUrl" not in body:
        problems.append(
            "android/.../Updater.kt: isPairedApkUrl does not check against "
            "BOTH of this shell's own stored, paired addresses "
            "(Prefs.lanUrl / Prefs.tsUrl) — a url could be accepted or "
            "refused for the wrong reason")

    if '"/app.apk"' not in body:
        problems.append(
            "android/.../Updater.kt: isPairedApkUrl does not pin the exact "
            "path /app.apk — a paired host serving something else entirely "
            "would be accepted")


# ─────────────────────────────────────────────────────────────────────────
# 6. NO SUCCESS STATE IS EVER CLAIMED
# ─────────────────────────────────────────────────────────────────────────

# Matches a state literal actually PASSED as an argument — never a comment
# mentioning the word, which is how promise 6's own reasoning gets written
# down in the source (the file headers explicitly discuss why "success"
# cannot exist, and that discussion must not trip this check).
_ONSTATE_CALL = re.compile(r'onState\(\s*"([a-zA-Z]+)"')
_UPDATE_STATE_CALL = re.compile(r'__updateState\(\s*"([a-zA-Z]+)"')


def _strip_kotlin_comments(src: str) -> str:
    # Good enough for this file: strips // line comments and /* */ blocks.
    # A false negative here would UNDER-report, never over-report, since a
    # forbidden word left inside a stripped comment simply is not scanned —
    # exactly the safe direction for a promise about REAL calls.
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//.*", "", src)
    return src


def check_no_success_state_is_ever_claimed(problems: list[str]) -> None:
    updater_code = _strip_kotlin_comments(_text(UPDATER_KT))
    called_states = set(_ONSTATE_CALL.findall(updater_code))
    forbidden_hit = called_states & set(FORBIDDEN_STATE_WORDS)
    if forbidden_hit:
        problems.append(
            f"android/.../Updater.kt: onState() called with forbidden "
            f"state(s) {sorted(forbidden_hit)} — a completed install kills "
            f"this process; no later call can ever legitimately reach a "
            f"page that no longer has a process to run in")
    unknown = called_states - LIVE_STATES
    if unknown:
        problems.append(
            f"android/.../Updater.kt: onState() called with state(s) not in "
            f"the agreed four {sorted(LIVE_STATES)}: {sorted(unknown)} — "
            f"the page's UPDATE_STATES list has no rendering for it")

    banner_code = re.sub(r"//.*", "", _text(UPDATE_BANNER_JS))
    # The page's own declared state list must be exactly the five renderable
    # states (four live + "offer", the page's own resting state) — no more,
    # no less. A sixth entry sneaking in unnoticed is exactly how a
    # "success" state would first arrive.
    states_list_match = re.search(r"const UPDATE_STATES = \[(.*?)\];", banner_code, re.S)
    if not states_list_match:
        problems.append(
            "client/update-banner.js: no `const UPDATE_STATES = [...]` — "
            "cannot verify the page's own state list")
    else:
        declared = set(re.findall(r'"([a-zA-Z]+)"', states_list_match.group(1)))
        expected = LIVE_STATES | {"offer"}
        if declared != expected:
            problems.append(
                f"client/update-banner.js: UPDATE_STATES is {sorted(declared)}, "
                f"expected exactly {sorted(expected)} — a state was added or "
                f"removed without this gate's promises being reconsidered")

    page_forbidden = set(_UPDATE_STATE_CALL.findall(banner_code)) & set(FORBIDDEN_STATE_WORDS)
    if page_forbidden:
        problems.append(
            f"client/update-banner.js: __updateState called with forbidden "
            f"state(s) {sorted(page_forbidden)} directly in this file")

    # The guard in window.__updateState must actually REFUSE anything not on
    # the list — the promise is not just "we don't call it with success", it
    # is "even if the shell someday did, the page would not render it".
    handler_match = re.search(
        r"window\.__updateState = function updateState\(state, detail\) \{(.*?)\n\};",
        banner_code, re.S)
    if not handler_match:
        problems.append(
            "client/update-banner.js: cannot find the window.__updateState "
            "handler body to verify its own guard")
    elif "UPDATE_STATES.includes(state)" not in handler_match.group(1):
        problems.append(
            "client/update-banner.js: window.__updateState does not check "
            "UPDATE_STATES.includes(state) — an unrecognised state string "
            "(a future \"success\") would fall through to setUpdateCardState "
            "and render something no page can honestly claim")


# ─────────────────────────────────────────────────────────────────────────
# 7. THE CUBE IS NOT WRITTEN TWICE
# ─────────────────────────────────────────────────────────────────────────

# The two things that make a cube a SECOND COPY rather than a caller of the
# one true implementation: its own face table, or its own burst/decay
# arithmetic (the `requestAnimationFrame` step doing the spin maths).
_CUBE_MARKERS = ("CUBE_VIEWS", "requestAnimationFrame(frame)", "burstSpeed")


def check_the_cube_is_not_written_twice(problems: list[str]) -> None:
    definers = []
    for path in sorted(CLIENT.glob("*.js")):
        if path.name == "cube.js":
            continue
        code = re.sub(r"//.*", "", path.read_text(encoding="utf-8"))
        hits = [marker for marker in _CUBE_MARKERS if marker in code]
        if hits:
            definers.append((path.name, hits))
    if definers:
        problems.append(
            "the cube's geometry/arithmetic appears outside client/cube.js: "
            + "; ".join(f"{name} ({', '.join(hits)})" for name, hits in definers))

    cube_code = _text(CUBE_JS)
    for marker in _CUBE_MARKERS:
        if marker not in cube_code:
            problems.append(
                f"client/cube.js: does not define {marker!r} — the gadget "
                f"this promise is about does not actually exist here")

    loading_code = _text(LOADING_JS)
    if "createCube(" not in loading_code:
        problems.append(
            "client/loading.js: does not call createCube() — the full-"
            "screen overlay's cube is not going through the shared gadget")

    banner_code = _text(UPDATE_BANNER_JS)
    if "createCube(" not in banner_code:
        problems.append(
            "client/update-banner.js: does not call createCube() — the "
            "update card's badge cube is not going through the shared "
            "gadget, which is exactly the second-copy risk this promise "
            "exists to close")


# ─────────────────────────────────────────────────────────────────────────
# 8. THE PROGRESS SHOWN IS NEVER INVENTED
# ─────────────────────────────────────────────────────────────────────────

def check_the_progress_shown_is_never_invented(problems: list[str]) -> None:
    banner_code = re.sub(r"//.*", "", _text(UPDATE_BANNER_JS))
    fn_match = re.search(
        r"window\.__updateProgress = function updateProgress\(received, total\) \{(.*?)\n\};",
        banner_code, re.S)
    if not fn_match:
        problems.append(
            "client/update-banner.js: cannot find the window.__updateProgress "
            "handler body to verify its own guard")
        return
    body = fn_match.group(1)

    # The guard must appear BEFORE the percentage arithmetic in source order
    # — a check that exists after the computation has already run would be
    # too late to matter (the number would already be on screen this tick).
    guard_idx = body.find("total > 0")
    pct_idx = body.find("received / total")
    if guard_idx == -1:
        problems.append(
            "client/update-banner.js: __updateProgress has no `total > 0` "
            "guard at all — a percentage could be computed from an unknown "
            "denominator")
    elif pct_idx == -1:
        problems.append(
            "client/update-banner.js: __updateProgress never computes a "
            "percentage at all — cannot verify it is gated (has the "
            "feature itself gone missing?)")
    elif guard_idx > pct_idx:
        problems.append(
            "client/update-banner.js: __updateProgress computes "
            "received/total BEFORE checking total > 0 — a fabricated "
            "percentage from an unknown total could reach the page for one "
            "tick before the guard would have refused it")

    if "updateBannerPct.hidden = true" not in body:
        problems.append(
            "client/update-banner.js: __updateProgress's unknown-total "
            "branch does not hide the percentage label — a stale or default "
            "number could be left showing while the total is unknown")


# ─────────────────────────────────────────────────────────────────────────
# 9. THE WAY BACK IN IS DECLARED IN THE MANIFEST
# ─────────────────────────────────────────────────────────────────────────

ANDROID_NS = "http://schemas.android.com/apk/res/android"
_RECEIVER_NAME = ".UpdateReturn"
_MY_PACKAGE_REPLACED = "android.intent.action.MY_PACKAGE_REPLACED"


def _attr(element, name: str) -> str | None:
    return element.get(f"{{{ANDROID_NS}}}{name}")


def check_the_way_back_in_is_declared(problems: list[str]) -> None:
    # Parsed, not grepped: the promise is about a real <receiver> element with
    # a real <intent-filter> inside <application>, and a string search would
    # be satisfied by the word appearing in one of this manifest's comments.
    tree = ET.fromstring(_text(MANIFEST))
    receivers = [r for r in tree.iter("receiver") if _attr(r, "name") == _RECEIVER_NAME]
    if not receivers:
        problems.append(
            f"android/.../AndroidManifest.xml: no <receiver "
            f"android:name=\"{_RECEIVER_NAME}\"> — the way back into the app "
            f"after it replaces itself is gone, and a runtime registration "
            f"cannot stand in for it: our process is DEAD at the moment that "
            f"broadcast is sent")
        return
    receiver = receivers[0]

    if _attr(receiver, "exported") != "false":
        problems.append(
            f"android/.../AndroidManifest.xml: {_RECEIVER_NAME} is not "
            f"android:exported=\"false\" — nothing outside this app has any "
            f"business reaching it, and the system delivers this protected "
            f"broadcast regardless")

    actions = [
        _attr(a, "name")
        for f in receiver.iter("intent-filter")
        for a in f.iter("action")
    ]
    if _MY_PACKAGE_REPLACED not in actions:
        problems.append(
            f"android/.../AndroidManifest.xml: {_RECEIVER_NAME} does not "
            f"filter {_MY_PACKAGE_REPLACED} — that is the action delivered to "
            f"our OWN package when this app is the one replaced, and it is "
            f"the only signal the app has that it must bring the owner back")
    stray = [a for a in actions if a != _MY_PACKAGE_REPLACED]
    if stray:
        problems.append(
            f"android/.../AndroidManifest.xml: {_RECEIVER_NAME} filters more "
            f"than MY_PACKAGE_REPLACED ({stray}) — ACTION_PACKAGE_REPLACED in "
            f"particular is the BROAD one and fires for every app the device "
            f"updates, none of which is this receiver's business")


# ─────────────────────────────────────────────────────────────────────────
# 10. THE RETURN NOTICE GOES THROUGH Notifier, AND IS NOT BUILT A SECOND TIME
# ─────────────────────────────────────────────────────────────────────────

# The markers of a SECOND notification implementation. Any of these inside
# UpdateReturn.kt means the app has grown a second builder, a second channel
# and a second tap target that can drift away from MainActivity.
_OWN_NOTIFICATION_MARKERS = (
    "NotificationCompat.Builder",
    "Notification.Builder",
    "NotificationChannel",
    "NotificationManagerCompat",
    "NotificationManager",
)


def check_the_return_notice_goes_through_notifier(problems: list[str]) -> None:
    code = _strip_kotlin_comments(_text(UPDATE_RETURN_KT))
    if not re.search(r"Notifier\s*\(\s*ctx\s*\)", code):
        problems.append(
            "android/.../UpdateReturn.kt: does not build a Notifier — the "
            "return notice is the ONLY carrier that reliably works here "
            "(a background activity start is normally refused on Android 10+)")
    if not re.search(r"\.post\s*\(", code):
        problems.append(
            "android/.../UpdateReturn.kt: never calls Notifier.post — the "
            "receiver would fire and leave the owner with nothing to tap")
    for marker in _OWN_NOTIFICATION_MARKERS:
        if marker in code:
            problems.append(
                f"android/.../UpdateReturn.kt: references {marker} — this "
                f"file must post through Notifier and build no notification "
                f"of its own (monorepo priority C: a second builder is a "
                f"second channel and a second tap target)")


# ─────────────────────────────────────────────────────────────────────────
# 11. THE BEST-EFFORT ACTIVITY START CAN NEVER CRASH THE RECEIVER
# ─────────────────────────────────────────────────────────────────────────

def _guarded_try_bodies(src: str) -> list[str]:
    """Every `try { … }` body in `src` that is actually followed by a
    `catch`. Brace-matched rather than regexed, because the body contains
    braces of its own (the Intent chain, a lambda) and a lazy pattern would
    stop at the first one."""
    bodies = []
    for match in re.finditer(r"\btry\s*\{", src):
        depth = 0
        for i in range(match.end() - 1, len(src)):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    body = src[match.end():i]
                    tail = src[i + 1:i + 40]
                    if re.match(r"\s*catch\s*\(", tail):
                        bodies.append(body)
                    break
    return bodies


def check_the_activity_start_cannot_crash_the_receiver(problems: list[str]) -> None:
    code = _strip_kotlin_comments(_text(UPDATE_RETURN_KT))
    if "startActivity" not in code:
        problems.append(
            "android/.../UpdateReturn.kt: no startActivity at all — the "
            "best-effort direct return is gone; the notification alone is "
            "the fallback, not the whole feature")
        return
    if not any("startActivity" in body for body in _guarded_try_bodies(code)):
        problems.append(
            "android/.../UpdateReturn.kt: startActivity is not inside a "
            "try/catch — on Android 10+ a background activity start is "
            "normally REFUSED, and a throwing refusal here would kill the "
            "receiver before it could post the notification, which is the "
            "carrier that actually works")


CHECKS = [
    ("the old fallback still exists",
     check_the_old_fallback_still_exists),
    ("the new bridge surface is exactly the three agreed names",
     check_the_new_bridge_surface_is_exact),
    ("the permission is declared",
     check_the_permission_is_declared),
    ("no file-based install path came back",
     check_no_file_based_install_path),
    ("the url is validated before anything is installed, by parsed components",
     check_the_url_is_validated_by_parsed_components),
    ("no success state is ever claimed",
     check_no_success_state_is_ever_claimed),
    ("the cube is not written twice",
     check_the_cube_is_not_written_twice),
    ("the progress shown is never invented",
     check_the_progress_shown_is_never_invented),
    ("the way back in is declared in the manifest",
     check_the_way_back_in_is_declared),
    ("the return notice goes through Notifier, and is not built a second time",
     check_the_return_notice_goes_through_notifier),
    ("the best-effort activity start can never crash the receiver",
     check_the_activity_start_cannot_crash_the_receiver),
]


def main() -> int:
    print("=== APK UPDATE GATE ===")
    problems: list[str] = []
    for label, check in CHECKS:
        before = len(problems)
        check(problems)
        status = "PASS" if len(problems) == before else "FAIL"
        print(f"  {status}  {label}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        print("\nAPK UPDATE GATE FAILED — an in-app install this shell "
              "started is one that must never be handed an untrusted url, "
              "never claim a success it cannot know, and never leave a "
              "downloaded copy of itself somewhere a stray grant could "
              "reach — and one that succeeds must never leave the owner "
              "hunting for his own app on the home screen.")
        return 1
    print("\nAPK UPDATE GATE PASSED — the fallback survives, the bridge "
          "surface is exact, the permission is declared, nothing touches "
          "disk outside the install session, the url is checked by parsed "
          "components, no state claims a success this page could never "
          "honestly know, the cube is written once, progress is never "
          "invented, and the way back into the app after it replaces itself "
          "is declared where a dead process can still be reached, posts "
          "through the one Notifier, and cannot be crashed by a refused "
          "activity start.")
    return 0


def test_apk_update():
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
