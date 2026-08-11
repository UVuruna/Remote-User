# rehearse_update — proving the one-handover lock before a release

**Task 187 closer (c).** The install-loop storm of 2026-08-09 lived in the
binary the gates never run — the OLD release's handover. This rehearsal
attacks the defence that IS ours to test: `rehearse_concurrency()` compiles
two throwaway NSIS stubs — one carrying installer.nsi's REAL lock block (the
mutex name is read live from installer.nsi by regex, so a rename cannot
desync the gate), one with the guard stripped — and launches 8 copies of
each. Verdict comes from PID-named marker files written only past the lock
check, never from wall-clock (a bare NSIS stub costs ~1.5 s even on the Quit
path, so timing cannot tell winners from losers — measured, not assumed).
Expected: 1/8 win with the lock, 8/8 without.

## Honest limits

This does NOT install a real previous release or drive the real
GitHub-check → self-update path: `SecMain` writes the machine-wide HKLM
Uninstall key (NSIS has no registry sandbox), the installer requires
elevation (a silent run would UAC-prompt or steal the foreground), and the
previous release is not in the checkout. `rehearse_full_previous_to_candidate
(allow_real=True)` exists as the explicit, human-run path for a disposable
machine — it refuses by default with the reason.
