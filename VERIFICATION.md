# VERIFICATION — Round 46 (2026-08-12): your 14 problems, and what to check

You reported 14 problems off your live test of v0.0.116 ("Ispravi 15
kritičnih problema" session — lang-ok: owner's session title). Install the
newest release ([Releases](https://github.com/UVuruna/VibeCoder/releases))
on the PC and BOTH devices — the APK changed too, so update the app from the
banner (or reinstall) on the tablet AND the phone. Per FIXED = VERIFIED,
only your eyes close these boxes; anything broken is a repeat — report it
with what you saw.

## The stream (your #13 — the big one)

- [ ] **A layout streams only ITS OWN pixels now.** Focus a layout on the 4K
  monitor at 60 fps — the picture must MOVE, sharp, with no jumping and no
  seconds of lag, on the tablet AND the S25. The server log will say
  `H.264 session opened … crop 968x2096+…` — the phone now decodes a
  quarter-width stream instead of the whole 4K desktop it never showed.
- [ ] **Full desktop at Native/60 on the tablet**: if the tablet's decoder
  genuinely cannot do full 4K@60 (it is the one screen where you really
  watch all 3840×2160), the app now SAYS so — a toast names the fps it
  drops to instead of freezing silently. On the S25 it should just run.
- [ ] **Quality panel** states the PC's live values; "Native ↑" is greyed
  when the PC card already streams full size (they are the same picture —
  that is the whole difference between Native and Full).

## Layouts & view (your #11)

- [ ] **Aspect ratio + Move handle**: shrink a layout's aspect, drag the
  picture off-center, Apply — the picture must land WHOLE (nothing cut at
  the bottom), immediately, without locking/unlocking the app.

## Controls & chrome (your #2, #3, #9, #10, #14)

- [ ] **Hide → Stays hidden**: everything vanishes EXCEPT the Hide button;
  tapping it brings everything back. "Comes back" behaves as before.
- [ ] **No layouts yet**: Layout(+) and Hide sit in the very top row — no
  empty reserved strip above them.
- [ ] **Layout bar, top**: centered, never wider than ~420 px on the tablet;
  on the phone (too narrow between the corners) it takes its own full row.
- [ ] **Layout bar, bottom**: sits DOWN in the bottom row, level with the
  button groups, between them — never mid-screen, in both orientations.
- [ ] **Layout(+) tap**: three small buttons fan out AROUND the button —
  New (right), Tap (diagonal), List (down) — no centered ring, no veil.
  Recent is gone from the fan (history still exists server-side).
- [ ] **Gamepad**: L2 hold opens the same fan, stick points E/SE/S, release
  confirms, release at nothing cancels, short L2 tap still arms tap-pick.

## Android shell (your #1, #8) — needs the new APK

- [ ] **QR scan opens in the orientation you HOLD the device** — portrait
  stays portrait.
- [ ] **Full desktop rotates freely on the tablet** — even with the system
  auto-rotate toggle off. A focused layout still locks to its orientation
  (your 204 rule, unchanged).

## Desktop (your #4)

- [ ] **Settings / Controls / Traffic windows** always open fully on-screen,
  even when the main window sits at the very top or bottom edge.

## Notifications voice (your #5) — per device now

- [ ] **Settings → Voice on the PHONE**: lists this device's own voices,
  every row has a speaker button that SPEAKS a sample before you choose,
  plus the speaking pace. Tablet and phone each keep their own choice.
- [ ] **Desktop Settings** keeps only the two master switches ("Tell my
  phone…", "Say it out loud") — the voice rows moved to the phone.

## Wheel (your #6, #7)

- [ ] **Drop-out mode really holds 10**: tick up to 10 sets in the phone's
  picker / desktop editor with drop-out mode on; the ring legend follows.
- [ ] **Claude set → Agents** has an icon everywhere (phone + desktop
  editor). What it does: `/agents` opens Claude Code's subagent manager —
  a config surface, so it stays in the pool unticked until you want it.

---
Everything above shipped through the full gate chain (fail-closed build
gates incl. the two new ones — REGION STREAM and DECODE CAPS, both driven
with data from YOUR server log — phone + Qt audits in both palettes,
independent visual grading). Per THE REPEAT LAW's ledger these are all [~]
until you confirm them from your devices.
