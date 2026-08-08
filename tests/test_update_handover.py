"""Gate: an update never costs him the session he is installing FROM.

The owner's report, 2026-08-07:

    *"dešava se da ja ne mogu da instaliram novu verziju ako nisam kući, zato
    što čim uđem u instalaciju on će meni ugasiti Remote User i više neću moći
    da komandujem odavde."*

Every fix this project ships reaches him only through an install, and starting
the install killed the remote session he was installing from. That is a bug
that eats the project: away from home, on an old build, unable to take the new
one. `server/update_handover.py` is the answer — one tap, nothing else asked of
anybody, and control comes back by itself.

What must hold, and what each check would let through if it were missing:

  1. Nothing is handed over unverified. A download cut short by a dropped
     Wi-Fi is an ordinary event; running that file is the ONE failure that can
     leave him with a PC he cannot reach until he is standing in front of it.
  2. The phone is told BEFORE the app can exit. He is about to watch a dead
     screen for a minute; the alternative is believing the update broke his PC.
  3. The app waits for its OWN pid to be gone before the installer starts — so
     the installer never has to shoot a process mid-write, and the always-on-top
     windows are released in order.
  4. THE ROLLBACK. Whatever the installer's exit code, an app is started again
     from the same path. A silent NSIS run that failed replaces nothing, so
     that path still holds the old app — success and rollback are one line.
  5. It PROVES the app came back, and tries once more when it did not.
  6. When there is genuinely nothing to start, it SAYS so instead of exiting
     quietly, and the next start tells the phone the update did not take.

The installer and the app are FAKED — no real install runs here, and no real
RemoteUser.exe is touched, waited on or killed (the harness refuses to run
otherwise; see `refuse_to_touch_the_real_app`). What IS real is the shipped
handover script itself: it is written from `update_handover.SCRIPT` and
executed, so the batch this project ships is the batch this gate proves.

Run:  .venv\\Scripts\\python tests/test_update_handover.py
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "server"))

import config  # noqa: E402
import notify  # noqa: E402
import update_handover  # noqa: E402
from config import SETTINGS  # noqa: E402

# Names nothing else on this machine can answer to. The gate's whole safety
# argument rests on them: every process it starts, waits for or kills carries
# one of these, and the real app carries none.
FAKE_APP = "RU_GATE_FAKE_APP.exe"
REAL_APP = "remoteuser.exe"

# A "good" installer for verify(): the smallest thing that is a complete
# Windows program as far as this module can tell.
GOOD_BYTES = b"MZ" + b"\0" * (update_handover.MIN_INSTALLER_BYTES + 10)

WORK = Path(tempfile.mkdtemp(prefix="ru_handover_gate_"))
started: list[subprocess.Popen] = []


# ═══════════════════════════ THE SAFETY RAIL ═══════════════════════════
def refuse_to_touch_the_real_app(env: dict) -> None:
    """The owner is AWAY and his RemoteUser.exe is serving his phone right
    now. This gate runs a script whose job is to wait for a pid to die and
    then start an exe — so before any of that, prove the pid and the exe are
    ours and nobody else's. A gate that could take his session down while
    proving his session is safe would be its own worst bug."""
    exe, name, pid = env["RU_EXE"], env["RU_NAME"], env["RU_PID"]
    assert REAL_APP not in exe.lower(), f"RU_EXE points at the real app: {exe}"
    assert name.lower() != REAL_APP, f"RU_NAME is the real app: {name}"
    assert str(WORK) in exe or not Path(exe).exists(), \
        f"RU_EXE is outside the gate's own temp dir: {exe}"
    listing = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, text=True).stdout.lower()
    assert REAL_APP not in listing, f"RU_PID {pid} IS the real app"


def wait_until(pred, timeout: float = 8.0) -> bool:
    """`start` is asynchronous — what the script launched may still be writing
    its marker when the script itself has already exited."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.1)
    return False


def alive(image: str) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {image}", "/NH"],
                         capture_output=True, text=True).stdout
    return image.lower() in out.lower()


def ours_still_running() -> list[str]:
    """Every process on this PC whose command line names THIS run's temp dir.

    Why this exists, and it is the whole reason the gate could be trusted while
    it was not (owner, twice — 56 stray `cmd.exe` on his desktop and a
    "Not enough memory resources" that came from the exhausted desktop heap):
    the shipped script starts the app with `start "" /B "%RU_EXE%"`, and when
    the fake app is a `.cmd` Windows honours that with a `cmd.exe /K <file>`
    that NEVER EXITS. Those are grandchildren — spawned by the script, not by
    us — so they are in neither `started` nor under `FAKE_APP`, which is
    exactly what `cleanup()` measured. Six per run survived, and the check
    named "this gate left no process of its own running" passed over all six:
    a check that measures something other than what it claims is worth less
    than no check, because it also spends the credibility of the ones beside
    it.
    The match is the run's OWN temp directory, so it can never name a process
    that is not this gate's — not the owner's shells, not another session's.
    """
    # `-notlike '*Get-CimInstance*'` excludes THIS VERY QUERY: the PowerShell
    # process running it carries the folder name in its own command line, so
    # without that clause the probe reports itself and the gate fails on a
    # process that is the act of looking. Found by running it (the first
    # version failed with one leftover PID that was the probe).
    script = (
        "Get-CimInstance Win32_Process | Where-Object { "
        f"$_.CommandLine -like '*{WORK.name}*' -and "
        "$_.CommandLine -notlike '*Get-CimInstance*' } | "
        "ForEach-Object { \"$($_.ProcessId)\" }")
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    me = str(os.getpid())
    return [p for p in (line.strip() for line in out.splitlines())
            if p.isdigit() and p != me]


# ═══════════════════════════ THE FAKES ═══════════════════════════
def write_fakes(folder: Path) -> dict:
    """An installer that reports whether the OLD app was still running when it
    started, and an "app" that records every time it is launched."""
    folder.mkdir(parents=True, exist_ok=True)
    for name, code in (("installer_ok.cmd", 0), ("installer_bad.cmd", 1)):
        (folder / name).write_text(
            "@echo off\r\n"
            # Fully-qualified, for the same reason the shipped script is: a PC
            # with Git for Windows answers a bare `find` with GNU find.
            '"%SystemRoot%\\System32\\tasklist.exe" /FI "PID eq %RU_PID%" /NH '
            '2>nul | "%SystemRoot%\\System32\\find.exe" "%RU_PID%" >nul\r\n'
            'if errorlevel 1 (echo OLD_GONE>>"%~dp0installer.marker") '
            'else (echo OLD_ALIVE>>"%~dp0installer.marker")\r\n'
            f"exit /b {code}\r\n", encoding="ascii")
    (folder / "app.cmd").write_text(
        '@echo off\r\necho launched>>"%~dp0app.marker"\r\nexit /b 0\r\n',
        encoding="ascii")
    # A real, distinctly named executable image for the "did it come up?"
    # probe. cmd.exe is the only self-contained exe every Windows PC has.
    shutil.copy2(Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe",
                 folder / FAKE_APP)
    return {"ok": folder / "installer_ok.cmd",
            "bad": folder / "installer_bad.cmd",
            "app": folder / "app.cmd",
            "exe": folder / FAKE_APP}


def run_script(folder: Path, *, exe: Path, installer: Path, pid: int,
               exit_ticks: int = 8, up_ticks: int = 1) -> str:
    """Write the SHIPPED script into `folder` and run it exactly the way the
    app does — same spawn call, same environment contract. Returns the log."""
    log = folder / "update.log"
    config.apply(update_script_path=folder / "update_handover.cmd",
                 update_log_path=log,
                 update_record_path=folder / "update.json")
    SETTINGS.update_script_path.write_text(update_handover.SCRIPT, encoding="ascii")
    env = {**os.environ,
           "RU_PID": str(pid), "RU_EXE": str(exe), "RU_NAME": exe.name,
           "RU_INSTALLER": str(installer), "RU_LOG": str(log),
           "RU_VERSION": "0.0.999",
           "RU_EXIT_TICKS": str(exit_ticks), "RU_UP_TICKS": str(up_ticks)}
    refuse_to_touch_the_real_app(env)
    proc = update_handover._spawn(env)
    started.append(proc)
    proc.wait(timeout=180)
    return log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""


# ═══════════════════════════ THE CHECKS ═══════════════════════════
def check_nothing_unverified_is_ever_run() -> bool:
    """A truncated, empty or non-program download must never become the thing
    that replaces his only way into this PC."""
    folder = WORK / "verify"
    folder.mkdir(parents=True, exist_ok=True)
    good, short, tiny, junk = (folder / n for n in
                              ("good.exe", "short.exe", "tiny.exe", "junk.exe"))
    good.write_bytes(GOOD_BYTES)
    short.write_bytes(GOOD_BYTES[:-100])
    tiny.write_bytes(b"MZ" + b"\0" * 100)
    junk.write_bytes(b"<!doctype html>" + b"\0" * len(GOOD_BYTES))
    return (update_handover.verify(good, len(GOOD_BYTES)) == ""
            and update_handover.verify(good, None) == ""
            # a Wi-Fi drop mid-download — the realistic one
            and "incomplete" in update_handover.verify(short, len(GOOD_BYTES))
            # a captive portal's login page saved as "the installer"
            and update_handover.verify(tiny, None) != ""
            and "not a Windows program" in update_handover.verify(junk, None)
            and update_handover.verify(folder / "absent.exe", None) != "")


def check_a_damaged_download_stops_everything() -> bool:
    """`begin` must refuse before anything irreversible: no phone notice, no
    record, no script, no spawn, and the app stays up."""
    folder = WORK / "damaged"
    folder.mkdir(parents=True, exist_ok=True)
    bad = folder / "half.exe"
    bad.write_bytes(GOOD_BYTES[:-100])
    config.apply(update_record_path=folder / "update.json",
                 update_script_path=folder / "update_handover.cmd")
    events: list[str] = []
    real_tell, real_spawn = update_handover.tell_phone, update_handover._spawn
    update_handover.tell_phone = lambda *a, **k: events.append("told")
    update_handover._spawn = lambda env: events.append("spawned")
    try:
        action, text = update_handover.begin(None, bad, "0.0.999", len(GOOD_BYTES))
    finally:
        update_handover.tell_phone, update_handover._spawn = real_tell, real_spawn
    return (action == "stop" and text == update_handover.DAMAGED_TEXT
            and events == []
            and not (folder / "update.json").exists()
            and not (folder / "update_handover.cmd").exists())


def check_the_phone_is_told_before_the_app_can_go() -> bool:
    """Order is the design. He must hear "installing, back in a minute" while
    there is still a socket to hear it on — after the spawn is too late, and
    after the exit there is nothing at all."""
    folder = WORK / "order"
    folder.mkdir(parents=True, exist_ok=True)
    good = folder / "setup.exe"
    good.write_bytes(GOOD_BYTES)
    config.apply(update_record_path=folder / "update.json",
                 update_script_path=folder / "update_handover.cmd",
                 update_log_path=folder / "update.log")
    events: list[str] = []
    real_tell, real_spawn, real_elev = (update_handover.tell_phone,
                                        update_handover._spawn,
                                        update_handover.elevated)
    update_handover.tell_phone = lambda *a, **k: events.append("told")
    update_handover._spawn = lambda env: events.append("spawned")
    update_handover.elevated = lambda: True
    try:
        action, _ = update_handover.begin(None, good, "0.0.999", len(GOOD_BYTES))
    finally:
        (update_handover.tell_phone, update_handover._spawn,
         update_handover.elevated) = real_tell, real_spawn, real_elev
    record = (folder / "update.json").read_text(encoding="utf-8")
    return (action == "quit" and events == ["told", "spawned"]
            and '"to": "0.0.999"' in record and '"state": "handover"' in record
            and (folder / "update_handover.cmd").exists())


def check_it_waits_for_the_old_app_to_leave() -> bool:
    """The installer must never have to kill us. Proven by the installer
    itself: it looks the old pid up and writes down what it found."""
    folder = WORK / "wait"
    fakes = write_fakes(folder)
    old = subprocess.Popen(["cmd", "/c", "ping -n 4 127.0.0.1 >nul"],
                           creationflags=update_handover.CREATE_NO_WINDOW)
    started.append(old)
    start = time.time()
    log = run_script(folder, exe=fakes["app"], installer=fakes["ok"], pid=old.pid,
                     exit_ticks=20)
    waited = time.time() - start
    marker = (folder / "installer.marker").read_text(encoding="ascii", errors="replace")
    return ("OLD_GONE" in marker and "OLD_ALIVE" not in marker
            and waited >= 2.0                      # it really waited, not raced
            and "the old app is gone" in log
            and log.index("the old app is gone") < log.index("installing:"))


def check_a_failed_install_still_gives_him_his_pc_back() -> bool:
    """THE ROLLBACK. The installer exits non-zero — a silent NSIS run that
    failed replaced nothing, so the old app is still at that path and it is
    started anyway. An update that can brick his only way in, while he is at a
    beach, is worse than no update at all."""
    folder = WORK / "rollback"
    fakes = write_fakes(folder)
    log = run_script(folder, exe=fakes["app"], installer=fakes["bad"], pid=os.getpid() + 10**6)
    marker = folder / "app.marker"
    return ("the installer exited with code 1" in log
            and "started " in log
            and wait_until(marker.exists)
            and "launched" in marker.read_text(encoding="ascii"))


def check_it_proves_the_app_came_back() -> bool:
    """A start that did not take is a PC the phone cannot reach. With a live
    process of that image name the script says so and stops; the twin here
    stands in for the app that really did come up."""
    folder = WORK / "up"
    fakes = write_fakes(folder)
    twin = subprocess.Popen([str(fakes["exe"]), "/c", "ping -n 30 127.0.0.1 >nul"],
                            creationflags=update_handover.CREATE_NO_WINDOW)
    started.append(twin)
    for _ in range(40):                       # let the image appear in tasklist
        if alive(FAKE_APP):
            break
        time.sleep(0.1)
    log = run_script(folder, exe=fakes["exe"], installer=fakes["ok"],
                     pid=os.getpid() + 10**6, up_ticks=6)
    return ("the new app is running" in log
            and "starting it once more" not in log)


def check_it_tries_once_more_when_nothing_came_up() -> bool:
    """Nothing with that image name ever appears — the script must not shrug.
    It says so in the log he can read afterwards, and it starts it again."""
    folder = WORK / "retry"
    fakes = write_fakes(folder)
    log = run_script(folder, exe=fakes["app"], installer=fakes["ok"],
                     pid=os.getpid() + 10**6, up_ticks=2)
    marker = folder / "app.marker"
    twice = wait_until(
        lambda: marker.exists() and len(marker.read_text(encoding="ascii").split()) == 2)
    return ("starting it once more" in log and twice)


def check_nothing_to_start_is_SAID() -> bool:
    """The one case that cannot be rescued from a batch file. It must be loud
    in the log, and it must not pretend anything was started."""
    folder = WORK / "noexe"
    fakes = write_fakes(folder)
    log = run_script(folder, exe=folder / "not-there.exe", installer=fakes["ok"],
                     pid=os.getpid() + 10**6)
    return ("FATAL: nothing to run" in log and "started " not in log)


def check_the_next_start_tells_him_how_it_went() -> bool:
    """He is holding a phone, not a log file. A handover that landed the new
    version says so; one that did not is announced just as loudly — silence is
    how a man ends up testing a build he never installed."""
    folder = WORK / "announce"
    folder.mkdir(parents=True, exist_ok=True)
    config.apply(update_record_path=folder / "update.json",
                 update_log_path=folder / "update.log")
    running = config.app_version()

    notify._pending.clear()
    update_handover._write_record(running, folder / "s.exe", folder / "a.exe")
    if not update_handover.announce():
        return False
    good = notify._pending[-1]
    if (good["event"] != "finished" or "updated to" not in good["title"]
            or SETTINGS.update_record_path.exists()):
        return False                          # a record read twice re-announces

    notify._pending.clear()
    update_handover._write_record("9.9.999", folder / "s.exe", folder / "a.exe")
    update_handover.announce()
    bad = notify._pending[-1]
    return (bad["event"] == "failed" and "9.9.999" in bad["text"]
            and running in bad["title"]
            and not update_handover.announce()   # consumed, never repeated
            and len(notify._pending) == 1)


# ═══════════════════════════ CLEANING UP AFTER OURSELVES ═══════════════════
def cleanup() -> tuple[bool, str]:
    """Kill anything of ours still breathing and PROVE it. This gate starts
    processes on a machine whose owner is a thousand kilometres away using it."""
    for proc in started:
        if proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True)
    subprocess.run(["taskkill", "/IM", FAKE_APP, "/F"], capture_output=True)
    # The grandchildren the SCRIPT started — see ours_still_running(). Killed
    # by the same measure the verdict below is read from, so the two can never
    # disagree again.
    for pid in ours_still_running():
        subprocess.run(["taskkill", "/PID", pid, "/T", "/F"], capture_output=True)
    for _ in range(30):
        if not alive(FAKE_APP) and not ours_still_running():
            break
        time.sleep(0.1)
    leftovers = [str(p.pid) for p in started if p.poll() is None]
    if alive(FAKE_APP):
        leftovers.append(FAKE_APP)
    # THE VERDICT IS READ FROM THE MACHINE, not from the handles we happen to
    # hold. This is the line that used to pass while six of the gate's own
    # processes were running.
    leftovers += ours_still_running()
    # Only after nothing of ours is breathing can the folder actually go: a
    # live `cmd /K` holds its own script open, and rmtree(ignore_errors=True)
    # then leaves the litter behind without a word. Thirteen of those had
    # piled up in his %TEMP% before anyone looked.
    shutil.rmtree(WORK, ignore_errors=True)
    if WORK.exists():
        leftovers.append(f"temp dir survived: {WORK}")
    return (not leftovers), ", ".join(leftovers)


def main() -> int:
    results: dict[str, bool] = {}
    try:
        results["nothing unverified is ever run"] = check_nothing_unverified_is_ever_run()
        results["a damaged download stops EVERYTHING, before anything is touched"] = (
            check_a_damaged_download_stops_everything())
        results["the phone is told before the app can go"] = (
            check_the_phone_is_told_before_the_app_can_go())
        results["it waits for the old app to leave on its own"] = (
            check_it_waits_for_the_old_app_to_leave())
        results["a FAILED install still gives him his PC back (rollback)"] = (
            check_a_failed_install_still_gives_him_his_pc_back())
        results["it proves the app came back"] = check_it_proves_the_app_came_back()
        results["it tries once more when nothing came up"] = (
            check_it_tries_once_more_when_nothing_came_up())
        results["nothing to start is SAID, never shrugged off"] = (
            check_nothing_to_start_is_SAID())
        results["the next start tells him how it went, good or bad"] = (
            check_the_next_start_tells_him_how_it_went())
    finally:
        clean, leftovers = cleanup()
        results["this gate left no process of its own running"] = clean

    print("\n=== UPDATE HANDOVER GATE ===")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok in results.items() if not ok]
    if failed:
        print(f"\nUPDATE HANDOVER GATE FAILED — {len(failed)} check(s).",
              file=sys.stderr)
        if not results.get("this gate left no process of its own running", True):
            print(f"  LEFTOVER PROCESSES: {leftovers}", file=sys.stderr)
        return 1
    print("\nUPDATE HANDOVER GATE PASSED — he can install from the beach: the "
          "app leaves last, the installer runs alone, and an app comes back "
          "whether it worked or not.")
    return 0


def test_update_handover():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
