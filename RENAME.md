# RENAME — Remote User ➜ Vibe Coder

**Status:** approved and pending. Decreed by the owner 2026-08-08, reconfirmed
2026-08-10 with the naming rewrite ([START](../../rules/START.md#name) → Step 2).
**Not executed yet:** on 2026-08-10 a session was live in this folder, and
renaming a project folder under a running session breaks it — the session keeps
writing to a path that no longer exists. This file is the handover so whoever
runs it next does not have to rediscover any of it.

**Why the new name** — this text goes into `README.md` under the opening
paragraph as a `## Why "Vibe Coder"` section, and it is part of the rename, not
an optional extra:

> It turns your phone into the machine: you write code from the beach, from the
> bath, thumbing a controller like you are playing a game, and what comes out
> the other end is a running program.

*"Remote User" described the plumbing. "Vibe Coder" names what the product is
actually for, in the words the market already uses for it.*

## Table of Contents

- [Before you start](#before)
- [Step 1 — the mechanical sweep](#sweep)
- [Step 2 — the traps the tool will not solve](#traps)
- [Step 3 — the product's own name](#product)
- [Step 4 — outside this repository](#outside)
- [Step 5 — verify](#verify)

---

<a id="before"></a>

## Before you start

The rename is **complete or not at all** — folder, every reference, README
story, git repo, session history. A half-done rename was already reverted once
(2026-08-08, 69 lines across 49 files); do not start it in a session that
cannot finish it.

1. **No live session in this folder.** `rename_project.py` checks for you and
   refuses; do NOT pass `--force`.
2. **The desktop app must not be running** — a running `RemoteUser.exe` holds
   files and the folder move fails halfway.
3. **Close the editor window on this folder.** On Windows an open VS Code holds
   the directory handle and the move fails with "access denied"; the tool
   reports which process holds it.

---

<a id="sweep"></a>

## Step 1 — the mechanical sweep

From the monorepo root:

```bash
python rules/tools/rename_project.py "Applications/Remote User" "Applications/Vibe Coder" --dry-run
```

It rewrites `Remote User`, `Remote-User`, `Remote_User` and `RemoteUser` as
whole phrases only, moves the folder, and **carries the 35 Claude Code session
transcripts** to the new history directory (they are keyed off the project
PATH, so a manual `mv` orphans them — that is the whole reason this tool
exists). Measured on 2026-08-10: **272 references in 103 files**.

Run it for real only with these exclusions:

```bash
python rules/tools/rename_project.py "Applications/Remote User" "Applications/Vibe Coder" \
  --exclude "REPORT-2026-08-01.md" \
  --exclude "rules/START.md"
```

- `REPORT-2026-08-01.md` — a dated record. It describes what the project was
  CALLED that night; rewriting it falsifies the record.
- `rules/START.md` — its Step 2 documents this very rename as the reference
  case (`Remote User → Vibe Coder`). Swept blindly it becomes
  "Vibe Coder → Vibe Coder" and the example stops making sense.

---

<a id="traps"></a>

## Step 2 — the traps the tool will not solve

### The machine-wide hook (verified, breaks every session on this machine)

`~/.claude/settings.json` runs a Stop hook from
`%LOCALAPPDATA%\RemoteUser\agent_hook.py` — the app's *data* folder, outside
any repository. If the data folder is renamed and that path is not updated in
the same sitting, every Claude Code session on this machine fails at Stop.

### The data folder itself

`server/config.py:36` puts the frozen app's data in `%LOCALAPPDATA%/RemoteUser`
— settings, `actions.json`, logs, the notify state. Renaming it on disk
silently discards the owner's live settings. Two honest options:

| Option | What happens |
|--------|--------------|
| **Keep `RemoteUser` as the data-folder id** | Nothing breaks, nothing migrates, the hook path stays valid. The folder name is then an internal id that no longer matches the product name — write that down in `server/__about/config.md` so the next reader is not confused. |
| **Rename to `VibeCoder`** | Cleaner, but it must ship WITH: a one-time migration that moves the old folder's contents if the new one is absent, the `~/.claude/settings.json` hook path updated by hand, and the Task Scheduler autostart task (`config.py:217`, currently `"RemoteUser"`) re-registered — the old task otherwise stays behind pointing at an exe that no longer exists. |

Pick one deliberately and say which in the commit message.

### Build output is not source

`android/app/build/` and `dist/` are gitignored build artifacts full of
absolute paths and generated `values.xml` copies. Do not sweep them — delete
and rebuild.

### Quoted evidence stays quoted

Several tests quote the owner's own words and his own log path as literal
evidence (`tests/test_update_handover.py`, `test_quality_reset.py`,
`test_server_generation.py`, `test_stream_lifecycle.py`,
`test_user_settings.py`). If the data folder keeps the `RemoteUser` id, those
strings are still true and must NOT be rewritten. If it is renamed, the
fixtures change with the code — but his quoted Serbian sentence in
`test_update_handover.py:6` is a quotation of a real thing he said and stays
exactly as it is.

---

<a id="product"></a>

## Step 3 — the product's own name

These carry the name to the user and to Windows, and each needs a look rather
than a substitution:

| File | What is in it |
|------|---------------|
| `setup/app_info.json` | `name`, `exe_name`, `installer_name` (`RemoteUser*`) and `display_name` ("Remote User") |
| `RemoteUser.spec` | PyInstaller bundle name, twice — the **file itself** is renamed to `VibeCoder.spec` |
| `setup/installer.nsi` | `APP_NAME`, `APP_EXE` |
| `setup/build.py`, `setup/build_apk.py` | the bundled APK filename (`RemoteUser.apk`, `.apk.version`) — the server serves it at `/app.apk`, so an installed phone app keeps working, but a half-updated pair of scripts silently bundles nothing |
| `android/.../values/strings.xml` | `app_name`, `onboarding_title`, and **five strings of user-facing copy** that say "the Remote User window / app" — these read correctly after substitution, but read them once to be sure the sentence still flows |
| `android/.../values/themes.xml` | `Theme.RemoteUser` |
| `server/gui/main_window.py`, window titles, tray tooltip | what the owner sees on screen |

**Version and release:** the first build after the rename produces a
differently-named installer and exe. The previously installed app will not be
replaced by it — uninstall the old one first, or the machine ends up with both.
The in-app updater checks GitHub Releases, so the release that carries the new
name must go out from the renamed repo ([SHIP](../../rules/SHIP.md)).

---

<a id="outside"></a>

## Step 4 — outside this repository

- **GitHub:** rename `UVuruna/Remote-User` to `UVuruna/Vibe-Coder`; GitHub
  keeps the redirect, but update the local remote and the About text
  (`gh repo edit UVuruna/Vibe-Coder --description "<README opening paragraph>"`).
- **Monorepo root:** `PROJECTS.md` entry and anchor, the `README.md` compact
  list row, and `logos/RemoteUser.svg` ➜ `logos/VibeCoder.svg` (`git mv`) —
  the sweep rewrites the text pointing at the logo, not the file's name.
- **Icon Forge:** `Gadgets/Icon Forge/manifest.json` is swept automatically,
  but the old `Remote User.lnk` stays behind in the desktop `VSCode Projects`
  folder — delete it and re-run Icon Forge so the new shortcut is created.
- **Other projects cite this one as a reference implementation** for the visual
  proof and layout gates (RHMH, 3D Preview, Icon Forge, Ultra Vivid, Vitals,
  Input DNA, Watch Academy, PromptPainter, Aviator, Loading Cube). The sweep
  fixes the text; those are separate repositories, so each one needs its own
  commit — the rename is not finished while any of them still says "Remote User".

---

<a id="verify"></a>

## Step 5 — verify

```bash
grep -rn "Remote User\|RemoteUser" . --exclude-dir=.git --exclude-dir=build --exclude-dir=dist
```

Every surviving hit must be one of: a dated record, a quotation of something
the owner actually said or of a real log path, or the data-folder id if that
was the option chosen. Anything else is an unfinished rename.

Then: guard tests green, the app builds and starts, the phone still pairs, and
`~/.claude` sessions still stop cleanly (that last one proves the hook path).
Delete this file in the same commit that finishes the job.
