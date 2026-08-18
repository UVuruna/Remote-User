r"""BATTERY REPORT GATE (T80d, owner request 2026-08-14) — what this app costs
the phone's battery WHILE IT IS RUNNING, on EVERY device.

His framing IS the requirement and it is why this gate exists: the app must be
able to answer for the battery cost of any handset, not only the one on his
desk — lang-ok: owner quote
"nije samo do mog uređaja već za svaki treba da predvidimo" — and what matters
most is the cost while the app RUNS, not the background one that
`test_shell_battery.py` next door already holds.

SIMULATION WAS REFUSED AND MAY NOT COME BACK. An Android emulator has no
battery: it reports a fixed fake value, so a simulated figure would look
authoritative and mean nothing. The build is therefore a MEASUREMENT — the
phone reads its own hardware (`Bridge.batteryStats`, no permission, no adb),
reports it on the EXISTING heartbeat, and the PC only repeats what it was
told. Every defence below guards one of the ways that measurement could
quietly turn back into a claim.

WHAT THIS GATE EXISTS TO PREVENT, and none of it is "the number prints":

  * A ZERO STANDING IN FOR "I DO NOT KNOW". `BATTERY_PROPERTY_CURRENT_NOW` is
    optional and widely stubbed: a refusing device answers `Integer.MIN_VALUE`
    or a flat 0. Either one rendered on the desktop as "0 mA" reads as "this
    app costs nothing" — the single most flattering thing this window could
    say, and a claim about a measurement that never happened. Absent must
    travel as ABSENT the whole way: shell → page → socket → meter → the words
    on his screen.
  * A SIGN TRUSTED THAT CANNOT BE. The property is documented positive while
    charging, and a known share of OEMs ship it inverted, with no way for the
    code to tell which. The shell therefore sends the MAGNITUDE and takes the
    direction from `BatteryManager.isCharging`, a plain boolean with no
    convention to get wrong.
  * A NEW FIELD ON AN OLD METHOD. The page is served by the PC while the shell
    is installed separately, so extending `netStats()` would simply stop
    resolving on the phone in his hand (CLAUDE.md's standing rule, the reason
    `speakAs` stands beside `speak`).
  * A NEW MESSAGE TYPE where the existing beat already carries exactly this
    kind of self-report (`net`).
  * ONE MISSING PROPERTY SILENCING THE OTHER. A phone that reports its level
    but not its draw must state the level it has and NAME the half it lacks.
  * A BATTERY LEVEL CARRIED ACROSS AN ABSENCE — "what the session cost"
    measured against a reading taken before the phone was charged is a
    different question answered with a confident number.

THE KOTLIN HALF CANNOT BE RUN HERE. There is no JVM test runner in this repo
and no device attached, so the shell checks READ THE SOURCE and assert the
structural promise — exactly the shape `tests/test_shell_battery.py` uses,
followed rather than re-invented. What the phone really reports is proven only
on a real handset.

Every check is proven by planting its own defect.

Run:  .venv\Scripts\python tests/test_battery_report.py
"""

import os
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC = PROJECT / "android/app/src/main/java/com/uvuruna/vibecoder"

import traffic  # noqa: E402
from gui.traffic_battery import battery_sentence  # noqa: E402


def _bridge() -> str:
    return (SRC / "Bridge.kt").read_text(encoding="utf-8")


def _battery_stats_body() -> str:
    m = re.search(r"fun batteryStats\(\): String \{(?:.|\n)*?\n    \}", _bridge())
    return m.group(0) if m else ""


# ═══════ THE SHELL — the only component that can measure ══════════════════


def check_the_shell_measures_through_a_new_method() -> bool:
    """The measurement must exist, on its OWN name, reading BOTH properties.

    A new method rather than more of `netStats()`: the page is served by the
    PC while the shell is installed separately, so changed arity stops
    resolving on the phone he already has. `netStats` is checked here too —
    it must be left exactly as it was, because the same rule that forbids
    extending it forbids quietly trimming it."""
    ok = True
    body = _battery_stats_body()
    if not body:
        print("    Bridge has no batteryStats() — nothing measures the "
              "battery, and the PC can only ever repeat what the phone says",
              file=sys.stderr)
        return False
    for prop in ("BATTERY_PROPERTY_CURRENT_NOW", "BATTERY_PROPERTY_CAPACITY"):
        if prop not in body:
            print(f"    batteryStats does not read {prop}", file=sys.stderr)
            ok = False
    net = re.search(r"fun netStats\(\): String \{(?:.|\n)*?\n    \}", _bridge())
    if not net or "current" in net.group(0) or "battery" in net.group(0).lower():
        print("    the battery rides on netStats() — a changed signature "
              "simply stops resolving on an older shell, which is why this is "
              "a NEW method (CLAUDE.md, the `speakAs` rule)", file=sys.stderr)
        ok = False
    return ok


def check_a_device_that_will_not_say_reports_nothing() -> bool:
    """`Integer.MIN_VALUE` is the documented refusal and 0 is the one every
    stubbed implementation returns. BOTH must be excluded from the JSON — not
    clamped, not defaulted, LEFT OUT — because a zero on the desktop reads as
    "this app costs nothing". The level is bounded the same way: a refusing
    capacity read comes back negative and a percentage outside 0..100 is not
    a percentage."""
    ok = True
    body = _battery_stats_body()
    guard = re.search(
        r"if \(current != Int\.MIN_VALUE && current != 0\)(?:.|\n)*?\n        \}",
        body)
    if not guard or 'put("current_ua"' not in guard.group(0):
        print("    the draw is not gated on BOTH refusals (Int.MIN_VALUE and "
              "0) — a stubbed property would travel as a real zero and read "
              "as \"this app costs nothing\"", file=sys.stderr)
        ok = False
    # ...and nowhere else may put it, which is how a well-meaning `else`
    # branch would put the zero back.
    if body.count('put("current_ua"') != 1:
        print("    current_ua is written from more than one place — the "
              "second one is how the refusal gets a number again",
              file=sys.stderr)
        ok = False
    if "level in 0..100" not in body:
        print("    the level is not bounded to 0..100 — a refusing capacity "
              "read is negative and would be shown as a percentage",
              file=sys.stderr)
        ok = False
    return ok


def check_the_sign_is_never_trusted() -> bool:
    """The whole reason the direction is a separate field. The OEM convention
    for CURRENT_NOW's sign is not knowable from inside the app, so the shell
    sends a MAGNITUDE (`abs`) and reads the direction off `isCharging`, which
    has no convention to get wrong. Using the raw sign would put a plus sign
    on a phone that is emptying."""
    ok = True
    body = _battery_stats_body()
    if "Math.abs(" not in body:
        print("    the draw is sent with its raw sign — a known share of OEMs "
              "invert it, and nothing in the app can tell which convention a "
              "handset follows", file=sys.stderr)
        ok = False
    if "isCharging" not in body:
        print("    nothing reports the DIRECTION — with the sign discarded, "
              "isCharging is the only unambiguous source of it",
              file=sys.stderr)
        ok = False
    return ok


# ═══════ THE PAGE — feature-detected, and absent stays absent ═════════════


def check_the_page_asks_only_a_shell_that_can_answer() -> bool:
    """Feature-detected on the method itself (the shell is installed
    separately), and an EMPTY answer — a device that refused every property —
    must come back as null rather than as an object of nothing, or the PC
    would hold a reading that says nothing while claiming a phone reported."""
    ok = True
    page = (PROJECT / "client/state.js").read_text(encoding="utf-8")
    fn = page.split("function phoneBattery", 1)[1].split("\n}", 1)[0] \
        if "function phoneBattery" in page else ""
    if not fn:
        print("    the page has no phoneBattery()", file=sys.stderr)
        return False
    if 'typeof window.Android.batteryStats !== "function"' not in fn:
        print("    the page does not feature-detect the NEW bridge method — "
              "an older APK would throw on every heartbeat", file=sys.stderr)
        ok = False
    if "Object.keys(out).length" not in fn:
        print("    a reading with no properties at all is passed on as an "
              "object — the PC must see nothing, so it can say in words that "
              "this device does not report", file=sys.stderr)
        ok = False
    return ok


def check_it_rides_the_existing_beat() -> bool:
    """No new message type: `hb` and `away` already carry exactly this kind of
    phone-measured self-report (`net`), and `away` is the only moment a
    CLOSING reading of the session exists. In both, the field is attached only
    when there is one."""
    ok = True
    conn = (PROJECT / "client/connection.js").read_text(encoding="utf-8")
    if "if (bat) beat.bat = bat;" not in conn:
        print("    the heartbeat does not carry `bat` conditionally — the "
              "beat is where the RUNNING cost is measured from", file=sys.stderr)
        ok = False
    if "if (bat) bye.bat = bat;" not in conn:
        print("    the `away` word carries no battery reading — the parting "
              "message is the only moment the session's closing level exists",
              file=sys.stderr)
        ok = False
    if re.search(r'type:\s*"battery', conn):
        print("    a new message type was invented — this rides `hb`/`away` "
              "the way `net` does", file=sys.stderr)
        ok = False
    # The `hb` and `away` handlers moved to the command registry on
    # 2026-08-18 (VC-R2); the assertion is the same one.
    web = (PROJECT / "server/ws_commands.py").read_text(encoding="utf-8")
    if web.count('msg.get("bat")') != 2:
        print("    the server does not read `bat` on BOTH `hb` and `away`",
              file=sys.stderr)
        ok = False
    return ok


# ═══════ THE METER — nothing invented, nothing carried across a gap ═══════


def _fresh_meter():
    return traffic.TrafficMeter()


def check_the_meter_refuses_what_is_not_a_measurement() -> bool:
    """A zero or negative draw and an out-of-range level are refusals that
    reached us anyway (an older page, a device the shell's own guard did not
    catch). They must be dropped HERE too — a gate on one layer only holds
    that layer — and a reading of nothing but refusals must leave the meter
    with nothing to report at all."""
    ok = True
    m = _fresh_meter()
    m.note_battery({"current_ua": 0, "level": -1})
    if m.battery() is not None:
        print("    a reading of nothing but refusals became a battery report "
              f"({m.battery()}) — the desktop would print a zero draw",
              file=sys.stderr)
        ok = False
    m = _fresh_meter()
    m.note_battery({"level": 62, "current_ua": 0})
    got = m.battery()
    if not got or got["level"] != 62:
        print("    a valid level was lost alongside a refused draw",
              file=sys.stderr)
        ok = False
    elif got["current_ua"] is not None or got["avg_ua"] is not None:
        print("    a refused draw (0) was stored as a number — it is exactly "
              "the zero that reads as \"this app costs nothing\"",
              file=sys.stderr)
        ok = False
    return ok


def check_the_session_cost_is_measured_and_averaged() -> bool:
    """What he asked for: the cost WHILE THE APP RUNS. The drop is the first
    reading of this session against the newest one, and the draw is averaged
    over the readings that carried one — a single instantaneous sample swings
    with whatever the screen did that second."""
    ok = True
    m = _fresh_meter()
    m.set_clients(1)
    m.note_battery({"level": 80, "current_ua": 400_000, "charging": False})
    m.note_battery({"level": 74, "current_ua": 600_000, "charging": False})
    got = m.battery()
    if not got:
        print("    the meter reports nothing after two real readings",
              file=sys.stderr)
        return False
    if got["level_drop"] != 6:
        print(f"    the session's drop is {got['level_drop']}, not the 6 "
              "percent between the first and the newest reading",
              file=sys.stderr)
        ok = False
    if got["avg_ua"] != 500_000:
        print(f"    the average draw is {got['avg_ua']}, not the mean of the "
              "readings that carried one — a single instantaneous sample is "
              "not what the session cost", file=sys.stderr)
        ok = False
    if got["current_ua"] != 600_000:
        print("    `current_ua` is not the NEWEST reading", file=sys.stderr)
        ok = False
    return ok


def check_a_level_is_never_carried_across_an_absence() -> bool:
    """"What the session cost" measured against a reading taken before the
    phone went away — and was very possibly charged — is a different question
    answered with a confident number. The departure ends the accounting; the
    next session starts its own."""
    ok = True
    m = _fresh_meter()
    m.set_clients(1)
    m.note_battery({"level": 80, "current_ua": 400_000})
    m.set_clients(0)          # the phone is gone
    m.set_clients(1)          # ...and comes back charged
    m.note_battery({"level": 95, "current_ua": 300_000})
    got = m.battery()
    if got["level_drop"] not in (0, None):
        print(f"    the level drop is {got['level_drop']} — it was measured "
              "against a reading from BEFORE the phone went away, so a phone "
              "charged in between reports a nonsense session cost",
              file=sys.stderr)
        ok = False
    if got["avg_ua"] != 300_000:
        print(f"    the average draw is {got['avg_ua']} — the previous "
              "session's readings are still in it", file=sys.stderr)
        ok = False
    return ok


# ═══════ THE WORDS — a refusal is stated, never drawn as a blank ══════════


def check_a_device_that_does_not_report_says_so() -> bool:
    """His rule 4, and the one a screenshot cannot catch until it is too late:
    a device that will not answer must SAY so in plain words. Never a blank,
    never a dash, and never a zero — and the two silences are different
    sentences, because "no phone is connected" and "this phone refuses" are
    different facts."""
    ok = True
    silent = battery_sentence(None, clients=1)
    if "does not report" not in silent:
        print(f"    a refusing device renders as {silent!r} — it must say so "
              "in plain words", file=sys.stderr)
        ok = False
    if "mA" in silent or "0%" in silent or silent.strip() in ("", "—", "-"):
        print(f"    a refusing device renders a number or a blank: {silent!r}",
              file=sys.stderr)
        ok = False
    idle = battery_sentence(None, clients=0)
    if idle == silent:
        print("    \"nobody is connected\" and \"this phone refuses\" are the "
              "same sentence — they are different facts and he would read the "
              "first as the second", file=sys.stderr)
        ok = False
    return ok


def check_one_missing_half_never_silences_the_other() -> bool:
    """A large share of handsets report a level and refuse a draw. That phone
    must show the level it HAS and name the half it lacks — the failure this
    catches is the tidy one, where an incomplete reading is dropped whole and
    he is told nothing at all."""
    ok = True
    words = battery_sentence(
        {"level": 62, "charging": False, "current_ua": None, "avg_ua": None,
         "level_drop": 4, "seconds": 3600}, clients=1)
    if "62%" not in words:
        print(f"    the level this device DID report is missing: {words!r}",
              file=sys.stderr)
        ok = False
    if "does not report its draw" not in words:
        print(f"    the missing half is not named: {words!r}", file=sys.stderr)
        ok = False
    if "mA" in words:
        print(f"    a draw was printed for a device that reported none: "
              f"{words!r}", file=sys.stderr)
        ok = False
    full = battery_sentence(
        {"level": 62, "charging": False, "current_ua": 512_000,
         "avg_ua": 480_000, "level_drop": 4, "seconds": 3600}, clients=1)
    if "512 mA" not in full or "480 mA" not in full:
        print(f"    a full reading does not state the draw now AND the "
              f"session average: {full!r}", file=sys.stderr)
        ok = False
    if "4%" not in full:
        print(f"    the running cost — the percent this session used — is "
              f"missing: {full!r}", file=sys.stderr)
        ok = False
    # ...and a session too YOUNG for a percentage does not print one. Found by
    # photographing the window rather than by reading the code: the staged
    # card read "4% used in 0s with the app running". A level is an integer
    # percent, so the smallest step this can report is 1%, and 1% over a few
    # seconds is a rounding boundary being crossed rather than a rate any
    # phone has. Everything measurable — the level, the live draw — is still
    # stated; only the clause that would put a number on an unmeasurable span
    # waits.
    young = battery_sentence(
        {"level": 62, "charging": False, "current_ua": 512_000,
         "avg_ua": 512_000, "level_drop": 4, "seconds": 3}, clients=1)
    if "in 0s" in young or "4%" in young:
        print(f"    a percentage was printed over a span too short to carry "
              f"one: {young!r}", file=sys.stderr)
        ok = False
    if "62%" not in young or "512 mA" not in young:
        print(f"    the young session lost what it CAN state: {young!r}",
              file=sys.stderr)
        ok = False
    return ok


def main() -> int:
    results = {
        "shell: the measurement exists, on its own new method":
            check_the_shell_measures_through_a_new_method(),
        "shell: a device that will not say reports nothing, never a zero":
            check_a_device_that_will_not_say_reports_nothing(),
        "shell: the sign is never trusted — magnitude plus isCharging":
            check_the_sign_is_never_trusted(),
        "page: feature-detected, and an empty answer stays empty":
            check_the_page_asks_only_a_shell_that_can_answer(),
        "protocol: it rides the existing hb/away beat":
            check_it_rides_the_existing_beat(),
        "meter: what is not a measurement is refused":
            check_the_meter_refuses_what_is_not_a_measurement(),
        "meter: the running cost is measured and the draw averaged":
            check_the_session_cost_is_measured_and_averaged(),
        "meter: a level is never carried across an absence":
            check_a_level_is_never_carried_across_an_absence(),
        "words: a device that does not report SAYS so":
            check_a_device_that_does_not_report_says_so(),
        "words: one missing half never silences the other":
            check_one_missing_half_never_silences_the_other(),
    }
    print("\n=== BATTERY REPORT GATE ===")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok in results.items() if not ok]
    if failed:
        print(f"\nBATTERY REPORT GATE FAILED — {len(failed)} check(s).",
              file=sys.stderr)
        return 1
    print("\nBATTERY REPORT GATE PASSED — every device answers for its own "
          "battery, and one that will not say says so.")
    return 0


def test_battery_report():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
