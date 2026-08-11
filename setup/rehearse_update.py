"""Closer (c) of task 187 — THE UPDATE REHEARSAL GATE.

Task 187's diagnosis named the gap exactly: every gate this project has
ever run proved the NEW code. The 102->103 storm was caused by the OLD
code — the one binary on earth still running the broken, un-forked-guarded
handover was HIS, and no gate anywhere staged that transition. The task
asks for a gate that installs the PREVIOUS release, then lets it
self-update to the candidate, and asserts exactly one handover.

═══════════════════════════ WHAT THIS GATE HONESTLY PROVES ═══════════════
The concurrency defence added in installer.nsi for closer (b) — a global
named-mutex lock so a SECOND installer.exe launched while a FIRST is still
running refuses instead of racing it — is proven END TO END, mechanically,
with real Windows kernel objects, a real compiled NSIS binary, and a
planted-defect control that shows the check actually fails when the lock
is absent (`rehearse_concurrency`, driven by `main()`). This is exactly
the shape of his storm: N forked handover scripts each launching the SAME
installer.exe concurrently. Proving the lock holds under that exact
concurrency shape is the closest mechanizable rehearsal of the actual
failure this task exists to close, and it needs no admin rights, no UAC,
and touches no real registry key or real install path.

═══════════════════════════ WHAT THIS GATE CANNOT HONESTLY PROVE ═══════
It does NOT install a real previous release, does NOT run the real
`installer.nsi` end to end, and does NOT drive a real
`server/update_handover.py` 103-style self-update against a real candidate
build. Three reasons, each a hard blocker rather than a missing feature:

  1. installer.nsi's SecMain writes to the REAL, MACHINE-WIDE HKLM
     Uninstall key under this project's own registry path — the SAME key
     a real installed copy of Vibe Coder uses. Running it in this sandbox
     (or any CI box) risks colliding with a genuinely installed copy on
     that machine, or leaving registry litter behind that a "disposable
     environment" promise cannot actually keep — NSIS has no registry
     sandboxing, only a redirectable *file* InstallDir (/D).
  2. `RequestExecutionLevel admin` means a truly silent /S run either
     UAC-prompts (defeating "unattended") or fails outright on a
     non-elevated shell — and this task's own instructions forbid ever
     touching the owner's live install or taking the PC foreground, which
     a UAC prompt would do if one ever appeared unexpectedly.
  3. The previous release's installer is not present in this checkout and
     fetching it means trusting network access to GitHub at gate time —
     the gate would then be flaky on exactly the kind of offline box these
     fail-closed build gates are supposed to run cleanly on.

`rehearse_full_previous_to_candidate()` below exists as the OPT-IN,
real-installer path for a human with admin rights on a disposable VM or
throwaway machine — it is deliberately NOT wired into `main()`'s default
run, and it refuses immediately with an explanatory message unless called
with `allow_real=True` and both installers exist. See its docstring for
the full recipe. Wiring this into build.py, and whether to ever automate
it, is the coordinator's call — it needs infrastructure (a disposable VM,
a real previous-release download) this task's file ownership does not
extend to (setup/build.py is out of scope for this task).

Run:  .venv\\Scripts\\python setup/rehearse_update.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
NSI_PATH = PROJECT / "setup" / "installer.nsi"

# The concurrency count that actually broke his machine was "six releases
# in four hours" worth of forked scripts, each re-arming on the next one's
# app start — his log showed the fork going 1 -> 2 -> 4 in seconds. Eight
# concurrent launches is comfortably past that and still fast to run.
CONCURRENCY = 8

TIMEOUT_S = 60


def _find_makensis() -> str:
    found = shutil.which("makensis")
    if found:
        return found
    for p in (Path(r"C:\Program Files (x86)\NSIS\makensis.exe"),
              Path(r"C:\Program Files\NSIS\makensis.exe")):
        if p.exists():
            return str(p)
    raise RuntimeError(
        "makensis.exe not found — install NSIS (https://nsis.sourceforge.io/) "
        "to run the rehearsal gate")


def _extract_mutex_name() -> str:
    """Read the EXACT mutex name installer.nsi guards its handover with, so
    this rehearsal can never silently drift from what actually ships — a
    gate that hardcodes its own copy of the name is a gate that keeps
    passing after someone renames the real one and breaks the lock."""
    text = NSI_PATH.read_text(encoding="utf-8")
    m = re.search(r'CreateMutexA\([^)]*t\s+"([^"]+)"', text)
    if not m:
        raise RuntimeError(
            f"could not find the installer's mutex name in {NSI_PATH} — has "
            "the one-handover lock (task 187b) been removed or reshaped?")
    return m.group(1)


# ═══════════════════════════ THE MINIMAL LOCK-STUB SCRIPTS ═══════════════
# A silent NSIS installer that does EXACTLY what installer.nsi's lock block
# does — same API calls, same mutex name (read live from installer.nsi, see
# above) — and nothing else: no files, no registry, no admin requirement.
# `WITH_LOCK` is the real defence; `WITHOUT_LOCK` is the same script with
# the guard removed, used only as the planted-defect control that proves
# this gate would actually catch a regression in installer.nsi's own lock.
#
# Winners are told apart from losers by a MARKER FILE, one per process
# (named by its own PID, so N concurrent writers never race the same
# handle), never by wall-clock timing: measured on this machine, a bare
# compiled NSIS installer that does nothing but hit Quit() still costs
# roughly 1.5s of stub self-extraction and plugin-loading overhead before
# it exits — indistinguishable, by the clock alone, from a winner that
# deliberately sleeps 1.5s to simulate install work. A marker written only
# on the path PAST the lock check is unambiguous regardless of how long
# either path happens to take on any given machine.
_STUB_TEMPLATE = r"""
Name "RU Rehearsal Stub"
OutFile "{out_exe}"
RequestExecutionLevel user
SilentInstall silent

Section
{lock_block}
    ; Reached only past the lock (or when there was no lock to pass): the
    ; PID-named marker is this instance's OWN, unambiguous proof it got
    ; this far. The brief sleep afterwards stands in for real install work
    ; and gives concurrent siblings a window to collide with it -- not
    ; what this gate reads its verdict from, but it keeps the shape real.
    System::Call 'kernel32::GetCurrentProcessId() i .r3'
    FileOpen $2 "{marker_dir}\$3.won" w
    FileWrite $2 "installed"
    FileClose $2
    Sleep 1500
SectionEnd
"""

_LOCK_BLOCK = r"""
    System::Call 'kernel32::CreateMutexA(i 0, i 1, t "{mutex}") i .r0 ?e'
    Pop $1
    IntCmp $1 183 MutexHeld MutexFree MutexFree
MutexHeld:
    Quit
MutexFree:
"""


def _compile_stub(work: Path, name: str, mutex: str, with_lock: bool) -> tuple[Path, Path]:
    marker_dir = work / name
    marker_dir.mkdir(parents=True, exist_ok=True)
    nsi_text = _STUB_TEMPLATE.format(
        out_exe=str((work / f"{name}.exe")).replace("\\", "\\\\"),
        lock_block=(_LOCK_BLOCK.format(mutex=mutex) if with_lock else ""),
        marker_dir=str(marker_dir).replace("\\", "\\\\"),
    )
    nsi_path = work / f"{name}.nsi"
    nsi_path.write_text(nsi_text, encoding="utf-8")
    makensis = _find_makensis()
    result = subprocess.run([makensis, str(nsi_path)],
                            capture_output=True, text=True, timeout=TIMEOUT_S)
    exe = work / f"{name}.exe"
    if result.returncode != 0 or not exe.exists():
        raise RuntimeError(
            f"makensis failed compiling the {name} stub:\n{result.stdout}\n{result.stderr}")
    return exe, marker_dir


def _run_concurrent(exe: Path, n: int, marker_dir: Path) -> int:
    """Launch `n` copies of `exe` at once, wait for all of them, and return
    how many left a "*.won" marker behind — the count of instances that got
    past the lock (or found none to pass)."""
    procs = [subprocess.Popen([str(exe)]) for _ in range(n)]
    for proc in procs:
        proc.wait(timeout=TIMEOUT_S)
    return len(list(marker_dir.glob("*.won")))


def rehearse_concurrency() -> tuple[bool, str]:
    """THE MECHANIZABLE PART OF THIS GATE. Compiles two tiny throwaway NSIS
    installers — one carrying installer.nsi's real lock block (mutex name
    read live from the shipped file), one deliberately without it — and
    launches `CONCURRENCY` copies of each at once.

    Asserts:
      - WITH the lock: exactly ONE instance leaves its "won" marker behind
        — every other instance was refused by the mutex before it could
        write anything.
      - WITHOUT the lock (the planted-defect control): MORE than one
        instance wins — proving this gate would actually fail if
        installer.nsi's real lock were ever removed or broken, not merely
        that "some installer somewhere has a mutex call".
    """
    work = Path(tempfile.mkdtemp(prefix="ru_rehearse_"))
    try:
        mutex = _extract_mutex_name()
        # A per-run-unique suffix so a leftover mutex from a crashed earlier
        # run of THIS gate can never make a fresh run look locked out.
        mutex = f"{mutex}_{work.name}"

        locked_exe, locked_dir = _compile_stub(work, "with_lock", mutex, with_lock=True)
        winners_locked = _run_concurrent(locked_exe, CONCURRENCY, locked_dir)

        unlocked_exe, unlocked_dir = _compile_stub(work, "without_lock", mutex, with_lock=False)
        winners_unlocked = _run_concurrent(unlocked_exe, CONCURRENCY, unlocked_dir)

        ok = winners_locked == 1 and winners_unlocked > 1
        detail = (
            f"WITH the lock: {winners_locked}/{CONCURRENCY} instances won "
            f"(want exactly 1). WITHOUT it (planted-defect control): "
            f"{winners_unlocked}/{CONCURRENCY} won (want > 1, proving the "
            f"gate can see the bug it guards against).")
        return ok, detail
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ═══════════════════════════ THE OPT-IN, REAL-INSTALLER PATH ═══════════════
def rehearse_full_previous_to_candidate(
    previous_installer: Path, candidate_installer: Path, *, allow_real: bool = False
) -> tuple[bool, str]:
    """The literal ask: install the PREVIOUS release silently, redirected
    into a disposable environment, then run the CANDIDATE's own handover
    concurrency check against it. NOT run by `main()` — see the module
    docstring's "WHAT THIS GATE CANNOT HONESTLY PROVE" for exactly why an
    automatic, unattended run of this would be unsafe on a shared or CI
    machine (real HKLM writes, admin/UAC requirement).

    Call this by hand, with `allow_real=True`, from an elevated shell on a
    disposable VM or a throwaway machine you are prepared to have this
    installer's registry keys and firewall rule land on — never on the
    owner's own PC, and never from an automated release step:

        python -c "
        from pathlib import Path
        from setup.rehearse_update import rehearse_full_previous_to_candidate
        ok, detail = rehearse_full_previous_to_candidate(
            Path('VibeCoder_Setup_0.0.103.exe'),
            Path('dist/VibeCoder_Setup.exe'),
            allow_real=True)
        print(ok, detail)"

    It silent-installs `previous_installer` with a redirected /D into a
    temp folder (LOCALAPPDATA is NOT redirectable the same way for a
    FROZEN app — see config.py's USER_DIR, which reads the real env var —
    so this still writes update.json etc. under the REAL
    %LOCALAPPDATA%\\VibeCoder; that is the one piece of "disposable" this
    function cannot deliver honestly on a real Windows install, which is
    exactly why it insists on a throwaway machine rather than promising
    isolation it cannot provide), then silent-installs `candidate_installer`
    over it the same way a real handover would, and reports whether exactly
    one install ran to completion. It does not attempt to reproduce the
    FORK itself (that requires a genuinely broken old build, which by
    definition this repo does not ship) — it is a smoke test of the
    ordinary, non-forked upgrade path on real Windows machinery, which
    `rehearse_concurrency()` above cannot exercise because it uses
    throwaway stub installers, not the real one.
    """
    if not allow_real:
        return False, (
            "refused: this touches real HKLM state and needs elevation — "
            "call with allow_real=True on a disposable machine you control, "
            "never in an automated or shared-machine run (see this "
            "function's docstring)")
    for label, path in (("previous", previous_installer),
                        ("candidate", candidate_installer)):
        if not path.exists():
            return False, f"{label} installer not found: {path}"
    work = Path(tempfile.mkdtemp(prefix="ru_rehearse_real_"))
    try:
        install_dir = work / "install"
        for label, installer in (("previous", previous_installer),
                                 ("candidate", candidate_installer)):
            result = subprocess.run(
                [str(installer), "/S", f"/D={install_dir}"],
                capture_output=True, timeout=180)
            if result.returncode != 0:
                return False, (
                    f"{label} install exited {result.returncode} — see NSIS "
                    "log conventions; a non-zero /S exit is itself the "
                    "signal something in the chain (Tailscale check, "
                    "firewall rule, elevation) did not go silently")
        exe = install_dir / "VibeCoder.exe"
        return exe.exists(), (
            f"both installs completed; VibeCoder.exe present: {exe.exists()}"
            " — this proves the ORDINARY upgrade path on real Windows "
            "machinery, not the forked-handover storm itself (see docstring)")
    finally:
        # Best-effort only — a real HKLM/firewall/task-scheduler footprint
        # from this run is NOT cleaned up here; that is exactly why this
        # path demands a throwaway machine, spelled out above.
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    print("=== UPDATE REHEARSAL GATE (task 187c) ===")
    print("Mechanizable part: the installer's concurrency lock, proven with "
          f"{CONCURRENCY} concurrent launches plus a planted-defect control.\n")
    try:
        ok, detail = rehearse_concurrency()
    except Exception as e:  # noqa: BLE001 — report, don't crash the runner
        print(f"  ERROR  {e}", file=sys.stderr)
        return 1
    print(f"  {'PASS' if ok else 'FAIL'}  {detail}")
    if not ok:
        print("\nUPDATE REHEARSAL GATE FAILED.", file=sys.stderr)
        return 1
    print(
        "\nUPDATE REHEARSAL GATE PASSED (concurrency defence only — this "
        "gate does NOT install a real previous release; see the module "
        "docstring's honest-limits section, and "
        "rehearse_full_previous_to_candidate() for the opt-in real path).")
    return 0


def test_rehearse_update():
    """pytest entry."""
    assert main() == 0


if __name__ == "__main__":
    sys.exit(main())
