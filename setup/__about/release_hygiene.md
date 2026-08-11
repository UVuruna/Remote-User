# release_hygiene — never publish over an update in flight

**Task 187 closer (d).** Publishing v0.0.104 while his 102→103 update was IN
FLIGHT is recorded in task 144's own text as the exact storm feeder. The rule
is now mechanical: `assert_clear_to_release()` reads
`%LOCALAPPDATA%/VibeCoder/update.json` and refuses (SystemExit 1) while
`state == "handover"` and the record is younger than 15 minutes (mirrors
`update_handover.LOCK_STALE_S`, duplicated as a literal because this script
must run standalone from `setup/` before `server` is importable). Wired at
the top of `build.py`'s main — a refusal must cost nothing, so it runs before
PyInstaller does.

Honest limit: it reads update.json on the machine that RUNS the check — a
release built anywhere but the owner's own PC always reads "clear".
