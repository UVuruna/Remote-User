# Session Tasks — 2026-08-05 (owner-defined, enforced by the root Stop hook)

ISPORUKA: kod = mic language-agnostic debug/fix, layout Move handle, sets
picker fix, quality panel, layout zoom-font, build + GIT RELEASE · dokument =
docs of every changed module + this checklist.

WAITING_ON_OWNER: no

Round 2 SHIPPED as v0.0.075 (dictation setup card + Settings Language +
silent download state + client_log diagnostics to the server log; layout
audit 13/13 incl. the card). Task 1 stays open until the owner's on-device
round confirms recognition in his language — that round is what we wait on.

Round 2 (owner approved 2026-08-05): dictation setup CARD (first Mic tap) +
language CHANGE entry in the Settings set REPLACING the Anywhere button
(anywhere stays available in the actions pool — future preset combining, put
it in ROADMAP); while a model downloads, the Mic button wears an alternate
look and online recognition on the CHOSEN language serves; silent auto-switch
to on-device when the model lands; diagnostics go to the server log, never
the screen.

Rules: a task is checked ONLY when FIXED = VERIFIED (root cause named + fix +
evidence). WAITING_ON_OWNER may be `yes` ONLY when the turn genuinely ends
with questions/presentation the owner must answer; back to `no` the moment
work resumes. Enforced machine-wide by rules/hooks/session_tasks_guard.py.

- [ ] 1. Mic (Input set) non-English recognition — REAL debugging, not
      micro-tweaks. LANGUAGE-AGNOSTIC (owner, angrily): the app works with
      the PHONE'S languages, never hardcodes any language — remove the
      hardcoded "sr-RS" in voiceLanguages(). Instrument: status pill shows
      engine (on-device/cloud), languages, onError codes. Use
      checkRecognitionSupport() to KNOW what the device offers; fallback =
      cloud pinned to the phone's locale; offer on-device model download /
      guide the user to add their language when the API says it exists.
      Owner approves several debug rounds; a settings/guided step in the app
      for the user's language choice is welcome if immediate keyboard-grade
      recognition is impossible.
      ROUND 1 EVIDENCE (owner device, 2026-08-05): Serbian speech transcribed
      as English garbage ("Be a Valley key In football lalinesis") → the
      engine ran ENGLISH; primary-locale pinning is wrong when the phone's
      first language is English. The __voiceInfo toast UX was WRONG (owner,
      angrily): a transient multi-line cryptic panel that vanishes in a
      second — the requirement is a GUIDED, persistent, plain-language card
      that lets the user CHOOSE the dictation language and fix what's
      missing (Tailscale-error-card pattern). Diagnostics must go SILENTLY
      to the server log, never flashed at the user. Design presented,
      waiting on the owner's yes.
- [x] 2. Layout resize panel: center Move handle (✥) — drag repositions the
      shrunken region along the free axis; applied on Apply; double-tap
      re-centers. DONE 0.0.169: layout_aspect {pos} + Layout.pos/_fit_rect
      placement + preview drag (layouts.js dragMove). Evidence: guards +
      load test + INPUT GATE pass.
- [x] 3. Sets picker rotating state — DONE 0.0.169, two root causes:
      per-ORIGIN localStorage split across LAN/Tailscale addresses →
      Android.prefGet/prefSet SharedPreferences bridge; opening-tap ghost
      click → capture-phase armor. Evidence: guards + load test pass;
      device confirmation rides the owner's release round.
- [x] 4. Quality panel — DONE 0.0.169: FPS Max/10/15/30/60, res full/⅔/½,
      bitrate high/mid/low + auto-on-mobile-data; protocol
      quality {fps,res,bitrate}; per-client ffmpeg overrides; desktop
      Settings combos remain the defaults every level maps against.
- [x] 5. Font-zoom staircase (layout focus only) — DONE 0.0.169:
      pinch-out past fitted view → chord ctrl+minus per step; pinch-in
      restores with ctrl+plus before visual zoom; per-layout step counter;
      minus/plus OEM VKs added to the injector.
- [x] 6. Session close — DONE: APK 0.0.074 built (Kotlin compiled), full
      desktop build passed (INPUT GATE + PyInstaller + signed installer,
      "BUILD COMPLETE ... OK: exe + installer signed"), GIT RELEASE
      published: https://github.com/UVuruna/Remote-User/releases/tag/v0.0.074
      Docs updated (CLAUDE.md protocol, module __about docs, panels.md).
      Task 1 (mic) stays open pending the owner's on-device debug round with
      this release — the diagnostics in it exist exactly for that round.

## Round 3 (owner brief 2026-08-05, evening — LAYOUT fix)

- [x] 7. Layout custom NAME — DONE 0.0.175 — the auto name (target window title) stays the
      default, but the owner may type his own. Creation panel gets a Name
      field (prefilled from slot 1); existing layouts get a rename entry in
      the layout list. Server `create()` already takes `name`; new protocol
      `layout_rename {index, name}` for the rename.
- [x] 8. Z-ORDER — owner decided 2026-08-05 to KEEP the topmost band and
      instead take the right away the moment the phone stops working (see 9).
      Original — stop forcing permanent TOPMOST on layout members: the
      owner AT THE DESK cannot see any other window above them. Proposal
      presented: transient topmost pop (TOPMOST → NOTOPMOST +
      SetForegroundWindow) = guaranteed to come forward, then a normal
      window. Waiting on the owner's yes (consequence: a foreign
      always-on-top window may cover a member).
- [x] 9. DONE 0.0.174 (root cause: no liveness signal at all — the server
      only reacted to a clean socket close, which a locked phone rarely
      sends; heartbeat + away + watchdog + server-side resume pointer;
      evidence tests/test_presence.py 7/7, now a build gate). Phone leaves
      work mode (lock / app closed) → PC minimizes every
      layout member; phone comes back → the LAST used layout is restored,
      not the desktop. Server-side memory (survives the socket) + grace
      timer so an excursion (gallery/permission dialog) does not minimize.
- [x] 10. DONE 0.0.175. Aspect panel Move handle icon — the ✥ glyph renders as a fat cross
      on the owner's device; replace it with an inline SVG four-way arrow
      (real arrowheads, font-independent).
- [x] 11. Session close — DONE: APK 0.0.076 built, full desktop build passed
      (INPUT GATE + PRESENCE GATE + signed installer), layout audit 19/19,
      GIT RELEASE published. Session close — docs of every changed module, APK + desktop build,
      GIT RELEASE.
