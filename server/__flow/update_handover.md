# Update Handover — Flow

**About:** [description](../__about/update_handover.md)

## Who is alive at each step

The whole point is that at no moment is there NOBODY. He is a thousand
kilometres away and the app he is watching through is the app being replaced.

```
   the app          the .cmd          the installer       the new app
   ─────────────────────────────────────────────────────────────────────
1  downloads          –                    –                  –
2  VERIFIES           –                    –                  –        size + MZ; a truncated
   the file                                                            file is refused HERE
3  TELLS the          –                    –                  –        the last thing he hears
   phone                                                               for about a minute
4  spawns ─────────▶ waiting               –                  –
5  exits             waiting               –                  –        the LAST possible moment
6    –               running ─────────▶ replacing files       –        the ONLY thing alive
7    –               waiting            exits                 –
8    –               starts ────────────────────────────────▶ binding
9    –               proves it is up       –                serving
10   –               exits                 –                serving    the phone's own 2 s
                                                                       retry loop reconnects
```

Step 5 is what the owner asked for ("ugasi tek u onoj zadnjoj fazi"). Steps
4 and 8 are what he actually needs.

## `begin()` — the order IS the design

```
                begin(controller, installer, version, size)
                                 │
                    ┌────────────▼────────────┐
                    │  verify(installer)      │  exists? declared size?
                    └────────────┬────────────┘  ≥ 5 MB? starts with "MZ"?
                    bad          │        good
                     │           │
                     ▼           ▼
              return "stop"   tell_phone()  ── notify.deliver ─▶ page
              NOTHING was          │                          └▶ waiting channel
              written, spawned     │                          └▶ (queue: he is gone)
              or told              ▼
                            ┌──────────────┐
                            │ elevated()?  │  the packaged app always is
                            └──────┬───────┘  (--uac-admin)
                          no       │      yes
                           │       │
                           ▼       ▼
                    return      hand_over()
                    "manual"      ├─ write SCRIPT       → USER_DIR
                    (dev only:    ├─ write the record   → USER_DIR
                    show the      └─ _spawn(env)  CREATE_NO_WINDOW
                    installer)          │
                                        ▼
                                 return "quit"  → the window calls _quit()
```

Verify before he is told anything; tell him before anything can take his
screen away; arm the restart before giving up the ability to do anything at
all. Reorder any two of those and one of the failure modes comes back.

## The script

```
 env in:  RU_PID  RU_EXE  RU_NAME  RU_INSTALLER  RU_LOG  RU_VERSION
          RU_EXIT_TICKS  RU_UP_TICKS

  ┌─ 1. wait for the old app ────────────────────────────────────┐
  │   tasklist /FI "PID eq %RU_PID%"  every 1 s                  │
  │     gone            ──▶ on                                   │
  │     still there after RU_EXIT_TICKS ──▶ log it, go anyway    │
  │       (the installer's own taskkill is the backstop)          │
  └──────────────────────────────────────────────────────────────┘
                          │
  ┌─ 2. install ──────────▼──────────────────────────────────────┐
  │   call "%RU_INSTALLER%" /S        RC = %ERRORLEVEL%          │
  │   installer.nsi in silent mode: no pages, no Tailscale       │
  │   wizard, shortcut + autostart kept as they already are      │
  └──────────────────────────────────────────────────────────────┘
                          │
  ┌─ 3. THE ROLLBACK, WHICH IS ALSO THE SUCCESS PATH ────────────┐
  │   exe missing? ──▶ log FATAL, stop  (the one unrescuable case)│
  │   otherwise:    start "" /B "%RU_EXE%"        ← whatever RC   │
  │   a failed silent NSIS run replaced nothing, so that path     │
  │   still holds the OLD app                                     │
  └──────────────────────────────────────────────────────────────┘
                          │
  ┌─ 4. prove it ─────────▼──────────────────────────────────────┐
  │   tasklist /FI "IMAGENAME eq %RU_NAME%"  every 1 s           │
  │     found              ──▶ "the new app is running"          │
  │     nothing after RU_UP_TICKS ──▶ log it, start it once more │
  └──────────────────────────────────────────────────────────────┘
```

Every system tool is called by its **full path**. `find` by name is GNU find on
any PC with Git for Windows, and GNU find reads `"12345"` as a file name, fails,
and answers "that process is gone" — instantly and wrongly, every time.

## What he sees on the phone

```
 tap Update on the PC window (through the stream)
      │
      ▼
 "Installing v0.0.093 — the picture goes for about a minute and comes
  back by itself."          Android banner + spoken + toast on the pill
      │                     (notify.deliver: page, or the waiting channel)
      ▼
 the stream stops; the pill says "Disconnected (code 1006) — retrying…"
      │
      │   client/connection.js: setInterval(ensureConnected, 2000)
      │   the WebView page is NEVER reloaded — MainActivity's pageAlive
      │   rule — so the token, the URL and the whole session state survive
      ▼
 "Connecting to …" → "Connected"      the first probe that lands wins
      │
      ▼
 "Remote User updated to v0.0.093 — the PC is back, nothing else to do."
      │                                    ← announce(), queued at start-up
      │                                      and drained by the phone's auth
      ▼
 …or, if it did not take:
 "Remote User is still on v0.0.091 — the update to v0.0.093 did not
  install. Everything works as before; the update log on the PC says why."
```

## What makes the phone find the PC again

Nothing new — the chain that already exists, and every link of it is why the
handover changes nothing on the phone:

| Link | Where | Why it survives |
|------|-------|-----------------|
| the address | the WebView's loaded page | never reloaded (`pageAlive`), so `location.host` is unchanged |
| the token | `%LOCALAPPDATA%/RemoteUser/token.txt` | `pairing.generate_token()` reuses it; the installer only writes to `$INSTDIR`, never to `USER_DIR` (only UNINSTALL removes it) |
| the port | the same `settings.json`, same folder | unchanged for the same reason |
| the retry | `client/connection.js` | `setInterval(ensureConnected, RECONNECT_MS = 2000)` |
| the notice link | `NoticeLink.kt` | its own reconnect (5 s, backing off), independent of the page |

## The blind gap, derived

```
  app exits (release windows, join the server thread) │  1 – 3 s
  script notices the pid is gone (1 s poll)           │  0 – 1 s
  NSIS /S: LZMA-solid unpack of a ~500 MB payload,    │ 15 – 60 s   ← dominant
     + netsh × 2, schtasks, GetSize                   │
  PyInstaller onedir + PySide6 cold start             │  3 – 10 s
  uvicorn binds, first /ws accepted                   │  0 – 2 s
  the phone's next retry tick                         │  0 – 2 s
  ────────────────────────────────────────────────────┼──────────────
  TOTAL                                               │ ~20 – 80 s
```

The unpack term is the one that is not ours: it is disk speed and whatever
antivirus does with 500 MB of freshly written files. Everything else is
measured or bounded by a constant in [Config](../__about/config.md)
(`update_wait_exit_s = 30`, `update_wait_up_s = 40`).

## Failure paths (none of them silent, none of them fatal)

```
truncated / not-a-program download → nothing touched, button says
                                     "The downloaded update was incomplete — retry"
not elevated (dev checkout)        → the installer is launched VISIBLY, as before
script cannot be written           → nothing touched, button says so, app stays up
the phone cannot be told           → logged; the update still goes ahead
the old app will not exit          → logged; the installer's taskkill is the backstop
the installer fails (any exit code)→ the OLD app is started again, same port,
                                     same token; the phone reconnects into it
the app does not come up           → one more attempt, then a line in update.log
there is no exe at all             → "FATAL: nothing to run at …" in update.log;
                                     the Start-menu shortcut and the autostart
                                     logon task are what is left
the install did not take           → the next start SAYS so on the phone
                                     (announce → notify.queue)
```
