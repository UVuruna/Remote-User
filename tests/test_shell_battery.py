r"""Gate: what this shell costs the phone when nobody is looking at it.

Two owner-approved changes of 2026-08-14, in one file because they are one
question — the two things this app does while no page of ours is on screen, and
what each of them spends on a battery it does not own. Its own file rather than
more of `tests/test_notice_channel.py` (which stands at the structure law's
wall): that gate asks whether a notice REACHES a phone whose page is closed;
this one asks what the shell must stop doing when there is no session at all.

T80a — FLAG_KEEP_SCREEN_ON had ONE owner and it was the page. The flag was
added in `onCreate` and cleared only by `Bridge.keepAwake(false)`, so whenever
the native error card was up — no network, PC unreachable, Tailscale off, i.e.
exactly when there is no page — nothing could clear it and the phone burned its
screen, the biggest consumer it has, over a card saying the session was dead.
The shell owns the flag now (`ScreenAwake.kt`); the page keeps its release as
one input among four.

T80b — the notice channel started at every launch and the only choice he had
was WHEN it stops. Its beat wakes the radio about 1440 times a day. There is an
OFF switch now: default ON so nothing changes for anyone who never touches it,
read at start so OFF means the service never starts, and acting immediately
through a NEW bridge method — never an extra argument on an existing one, since
the page is served by the PC while the shell is installed separately.

THE KOTLIN HALF CANNOT BE RUN HERE. There is no JVM test runner in this repo
and no device attached, so every shell check below READS THE SOURCE and asserts
the structural promise, exactly as the shell checks in test_notice_channel.py
do. What the phone really does with the flag and the service is proven only on
the owner's phone.

Run:  .venv\Scripts\python tests/test_shell_battery.py
"""

import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SRC = PROJECT / "android/app/src/main/java/com/uvuruna/vibecoder"


# ═══════ T80b (2026-08-14) — WHETHER IT LISTENS AT ALL ════════════════════
# `tests/test_notice_channel.py` answers WHEN this device listens (background
# only, or after a swipe too). Until this round there was no answer to WHETHER:
# `MainActivity.onCreate` started the service unconditionally, and the
# channel's beat wakes the radio ~1440 times a day on a handset he may not want
# notices on at all.


def check_the_channel_has_a_real_off_switch() -> bool:
    """Four promises, and each of them is a way the switch could ship dead:

      • the start is CONDITIONAL — an OFF setting means the service is never
        started at all, not merely stopped a moment later;
      • the choice is PERSISTED in the same per-device store `prefGet`/
        `prefSet` uses, since it is read before any page exists;
      • the DEFAULT is ON — an equality against the one literal the page
        writes for "off", never a truthiness test and never a default-false
        `getBoolean`, either of which would silence every phone in the world
        the moment this round lands;
      • the bridge method ACTS NOW, starting or stopping the service itself.
        A switch whose effect is "next time you restart the app" is not a
        switch he can trust, and it is precisely what he would report as
        broken."""
    ok = True
    main = (SRC / "MainActivity.kt").read_text(encoding="utf-8")
    if not re.search(r"if \(Prefs\.noticeChannel\(this\)\) NoticeService\.start\(this\)",
                     main):
        print("    MainActivity starts the notice service unconditionally — "
              "an OFF setting must mean it never starts (T80b)",
              file=sys.stderr)
        ok = False

    prefs = (SRC / "Prefs.kt").read_text(encoding="utf-8")
    body = prefs.split("fun noticeChannel(", 1)[1].split("\n    fun ", 1)[0] \
        if "fun noticeChannel(" in prefs else ""
    if "CLIENT_FILE" not in body or "p_noticeChannel" not in body:
        print("    the switch is not stored in the page's own per-device store "
              "(CLIENT_FILE / p_noticeChannel) — the service reads it with no "
              "page alive", file=sys.stderr)
        ok = False
    if '!= "off"' not in body:
        print("    the shell's question is not an equality against \"off\" — a "
              "truthiness test or a default-false read silences every device "
              "that never opened the card", file=sys.stderr)
        ok = False

    bridge = (SRC / "Bridge.kt").read_text(encoding="utf-8")
    setter = re.search(
        r"fun setNoticeChannel\(on: Boolean\)(?:.|\n)*?\n    }", bridge)
    if not setter:
        print("    Bridge has no setNoticeChannel — the page cannot reach the "
              "switch at all", file=sys.stderr)
        return False
    if "NoticeService.setEnabled" not in setter.group(0):
        print("    Bridge.setNoticeChannel does not reach the service's own "
              "act — Bridge is the PROTOCOL, and the one function allowed to "
              "stop that channel lives in the service companion where the "
              "no-lifecycle-stop rule can be read (the locked-phone check in "
              "test_notice_channel.py)", file=sys.stderr)
        ok = False
    service = (SRC / "NoticeService.kt").read_text(encoding="utf-8")
    act = re.search(
        r"fun setEnabled\(ctx: Context, on: Boolean\)(?:.|\n)*?\n        }",
        service)
    if not act:
        print("    NoticeService has no setEnabled — nothing acts on the "
              "switch", file=sys.stderr)
        return False
    abody = act.group(0)
    if "Prefs.setNoticeChannel" not in abody:
        print("    the switch does not persist the choice", file=sys.stderr)
        ok = False
    if "start(ctx)" not in abody or "stop(ctx)" not in abody:
        print("    the switch does not start/stop the service NOW — it would "
              "only act at the next launch (T80b)", file=sys.stderr)
        ok = False
    if "fun noticeChannelOn()" not in bridge:
        print("    Bridge has no noticeChannelOn getter — the page cannot "
              "light the row it draws", file=sys.stderr)
        ok = False
    return ok


def check_the_off_switch_row_is_feature_detected() -> bool:
    """The page is served by the PC while the shell is installed separately, so
    a phone running an older APK has no `setNoticeChannel` at all. The row must
    be feature-detected on the method itself and HIDDEN when it is absent — a
    row that cannot act is a promise the panel cannot keep — and it must state
    the CONSEQUENCE in plain words, because a switch that hides its cost is one
    he turns off once and then reports the result of as a bug."""
    ok = True
    page = (PROJECT / "client/notify.js").read_text(encoding="utf-8")
    det = page.split("function noticeChannelSupported", 1)[1].split("\n}", 1)[0] \
        if "function noticeChannelSupported" in page else ""
    if 'typeof window.Android.setNoticeChannel === "function"' not in det:
        print("    the page does not feature-detect the NEW bridge method — an "
              "older APK would draw a row that does nothing", file=sys.stderr)
        ok = False
    if "if (noticeChannelSupported()) list.appendChild(noticeChannelRow())" \
            not in page:
        print("    the row is not gated on the feature detection — it must be "
              "hidden entirely when the bridge method is absent",
              file=sys.stderr)
        ok = False
    row = page.split("function noticeChannelRow", 1)[1].split("\n}", 1)[0] \
        if "function noticeChannelRow" in page else ""
    if "30-minute queue" not in row:
        print("    the row does not say what OFF costs — with the channel off "
              "a notice arrives only when the app is opened, out of the PC's "
              "30-minute queue", file=sys.stderr)
        ok = False
    return ok


# ═══════ T80a (2026-08-14) — WHO OWNS FLAG_KEEP_SCREEN_ON ═════════════════
# The flag was added once in onCreate and cleared by exactly ONE thing: the
# page, through `Bridge.keepAwake(false)`. While the native error card is up
# there is no page, so nothing could ever clear it and the phone burned its
# screen — the biggest consumer it has — over a card saying the session is
# dead. It is in THIS file because the error card and the notice channel are
# the two things this shell does when no page is alive.


def check_the_screen_flag_has_exactly_one_writer() -> bool:
    """Ownership is the fix, so the shape of the ownership is what is asserted:
    every add/clear of the flag lives inside `applyKeepAwake`, and nothing else
    in the shell — onCreate included — touches it. Two writers is how the leak
    happened; a second one added later would bring it straight back."""
    ok = True
    awake = (SRC / "ScreenAwake.kt").read_text(encoding="utf-8")
    m = re.search(r"fun apply\(host: MainActivity\)(?:.|\n)*?\n    }", awake)
    if not m:
        print("    ScreenAwake has no apply() — the flag has no owner",
              file=sys.stderr)
        return False
    body = m.group(0)
    flag = "FLAG_KEEP_SCREEN_ON"
    if f"addFlags(WindowManager.LayoutParams.{flag})" not in body or \
            f"clearFlags(WindowManager.LayoutParams.{flag})" not in body:
        print("    ScreenAwake.apply does not both take and release the flag",
              file=sys.stderr)
        ok = False
    # Comments are stripped first: this file EXPLAINS the flag at length, and
    # a check that cannot tell a sentence about the flag from a line that sets
    # it would have to be silenced the first time anyone documented the rule.
    for name in sorted(f.name for f in SRC.glob("*.kt")):
        text = (SRC / name).read_text(encoding="utf-8")
        if name == "ScreenAwake.kt":
            text = text.replace(body, "")
        outside = "\n".join(
            line for line in text.splitlines()
            if not line.lstrip().startswith(("*", "//", "/*")))
        if flag in outside:
            print(f"    {name} touches {flag} outside ScreenAwake.apply — one "
                  "owner, or the 2026-08-14 leak returns", file=sys.stderr)
            ok = False

    bridge = (SRC / "Bridge.kt").read_text(encoding="utf-8")
    kb = bridge.split("fun keepAwake(", 1)[1].split("\n    }", 1)[0] \
        if "fun keepAwake(" in bridge else ""
    if "ScreenAwake.pageAsked" not in kb:
        print("    Bridge.keepAwake no longer reaches the owner — the page must "
              "KEEP its power to release the screen during a session",
              file=sys.stderr)
        ok = False
    return ok


def check_the_screen_is_released_when_no_session_is_shown() -> bool:
    """The leak itself, and the three states it leaked in. The flag is held
    only while a live page is really on screen, so `applyKeepAwake` must weigh
    the error card, the loader, `pageAlive` and `started`; and the three
    moments those change — the card going up, the load callbacks, onStop — must
    each re-apply the rule, or the decision is right and never taken."""
    ok = True
    main = (SRC / "MainActivity.kt").read_text(encoding="utf-8")
    awake = (SRC / "ScreenAwake.kt").read_text(encoding="utf-8")
    body = re.search(r"fun apply\(host: MainActivity\)(?:.|\n)*?\n    }", awake)
    body = body.group(0) if body else ""
    for term in ("errorView.visibility", "loadingView.visibility",
                 "pageAlive", "started"):
        if term not in body:
            print(f"    ScreenAwake.apply ignores {term} — the flag would be "
                  "held over a state that is not a live session",
                  file=sys.stderr)
            ok = False

    # The funnel: every layer change re-applies the rule, so no call site can
    # raise the error card or the loader without the screen following it.
    layer = re.search(
        r"internal fun MainActivity.showLayer\((?:.|\n)*?\n}", awake)
    if not layer or "ScreenAwake.apply(this)" not in layer.group(0):
        print("    showLayer does not re-apply the rule — the error card could "
              "go up over a screen nothing releases, which IS the T80a leak",
              file=sys.stderr)
        ok = False

    # showErrorCard may live in either MainActivity.kt (a plain private method,
    # closing on the 4-space class indent) or ConnectionError.kt (the shape it
    # took on 2026-08-14 when the structure-law split moved the error-card /
    # network-diagnosis code out of MainActivity.kt into its own file, as an
    # `internal fun MainActivity.showErrorCard()` extension — a TOP-LEVEL
    # declaration, so its closing brace has no indent at all. Whichever file it
    # is in next, look in both and match both shapes — a regex tuned to one
    # file's indent silently stops finding its subject the next time this code
    # moves, which is worse than no check at all.
    connerr = (SRC / "ConnectionError.kt").read_text(encoding="utf-8") \
        if (SRC / "ConnectionError.kt").exists() else ""
    card = (
        re.search(r"private fun showErrorCard\(\)(?:.|\n)*?\n    }", main)
        or re.search(r"internal fun MainActivity\.showErrorCard\(\)(?:.|\n)*?\n}",
                     main)
        or re.search(r"private fun showErrorCard\(\)(?:.|\n)*?\n    }", connerr)
        or re.search(r"internal fun MainActivity\.showErrorCard\(\)(?:.|\n)*?\n}",
                     connerr)
    )
    if not card:
        print("    showErrorCard was not found in any shell file — checked "
              "MainActivity.kt and ConnectionError.kt for both the method and "
              "extension-function shapes", file=sys.stderr)
        ok = False
    elif "showLayer(error = true" not in card.group(0):
        print("    showErrorCard does not go through the funnel — no page is "
              "running there, so nothing else can release the screen",
              file=sys.stderr)
        ok = False

    for hook in ("override fun onStop", "override fun onStart"):
        m = re.search(hook + r"\(\)(?:.|\n)*?\n    }", main)
        if not m or "ScreenAwake.apply(this)" not in m.group(0):
            print(f"    {hook} does not re-apply the rule — backgrounded is "
                  "never awake, and coming back must take the screen again",
                  file=sys.stderr)
            ok = False

    finished = re.search(r"override fun onPageFinished\((?:.|\n)*?\n        }",
                         main)
    if not finished or "showLayer(" not in finished.group(0):
        print("    a page that finished loading never re-applies the rule — a "
              "recovered session would stay released forever", file=sys.stderr)
        ok = False
    return ok


def main() -> int:
    results = {
        "T80b: the channel has a real OFF switch, default ON":
            check_the_channel_has_a_real_off_switch(),
        "T80b: the row is feature-detected and names its cost":
            check_the_off_switch_row_is_feature_detected(),
        "T80a: the screen flag has exactly one writer":
            check_the_screen_flag_has_exactly_one_writer(),
        "T80a: the screen is released when no session is shown":
            check_the_screen_is_released_when_no_session_is_shown(),
    }
    print("\n=== SHELL BATTERY GATE ===")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok in results.items() if not ok]
    if failed:
        print(f"\nSHELL BATTERY GATE FAILED — {len(failed)} check(s).",
              file=sys.stderr)
        return 1
    print("\nSHELL BATTERY GATE PASSED — nothing of ours holds the screen or "
          "the radio while there is no session to hold them for.")
    return 0


def test_shell_battery():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
