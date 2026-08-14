# Traffic Battery

**Script:** [Traffic Battery (script)](../traffic_battery.py) ·
**Flow:** [diagram](../__flow/traffic_battery.md)

## Purpose

What this app costs the **phone's battery while it is running**, in the words
the Traffic window prints — and nothing else.

Owner request T80d, 2026-08-14. His framing is the requirement: the app must
be able to answer for the battery cost of **every** device, not only the one
on his desk, and the cost that matters most is the one **while the app is
running**, not the background one that
[Shell Battery](../../../tests/___tests.md) (T80a/T80b) already holds.

Its own module by **responsibility**, the same split
[Traffic Axis](traffic_axis.md) made from [Traffic Window](traffic_window.md)
next door. That window's subject is BYTES: how many crossed the socket, in
which direction, and whether any crossed while nobody was connected — counted
by the PC at its own socket, so they always exist. This module's subject is
POWER, which is a different measurement with a different source and a
different way of being unavailable: it can only ever be measured by the phone
about itself, and a large share of devices refuse.

That refusal is why there is a module here at all, and it is why the wording
is a **pure function** of (what the phone said, is anyone connected): its gate
can then prove every rule below without building a Qt window, exactly as
`traffic_window.history_since` is pure for the same reason.

## The rules it holds

**Simulation was refused and may not come back.** An Android emulator has no
battery: it reports a fixed fake value, so a simulated figure would look
authoritative and mean nothing. The number is measured on the handset
(`Bridge.batteryStats` — `BatteryManager`, no permission and no adb), rides
the existing `hb`/`away` beat exactly as the TrafficStats counters do, and
this module only ever repeats what it was told.

**A device that does not report SAYS so, in plain words** — never a blank,
never a dash, and above all never a zero. `0 mA` reads as "this app costs
nothing", the most flattering possible claim about a measurement that never
happened.

**The two silences are different sentences**, because they are different
facts: "nobody is connected" and "this phone refuses" would otherwise be read
as each other.

**One missing half never silences the other.**
`BATTERY_PROPERTY_CURRENT_NOW` is optional and widely stubbed, so a phone that
reports its level and refuses its draw must state the level it HAS and name
the half it lacks. The failure this prevents is the tidy one: an incomplete
reading dropped whole, and the owner told nothing at all.

**A span too short for a percentage prints none** (`MIN_DROP_SPAN_S`, found
2026-08-14 by PHOTOGRAPHING the window rather than reading the code — the
staged card read *"4% used in 0s with the app running"*). A level is an
integer percent, so the smallest step this can report is 1%, and 1% over a few
seconds is a rounding boundary being crossed rather than a rate any phone has.
Everything measurable — the level, the live draw — is still stated; only the
clause that would put a number on an unmeasurable span waits.

**`charging` is stated because it changes what every number MEANS.** A level
that is not falling while charging says nothing about the cost.

Full context, the sample line, and the honest limits that cannot be detected
from inside the app (the OEM sign convention; the microamp-versus-milliamp
unit) are in [Traffic Window](traffic_window.md) → *What it costs the phone's
BATTERY*.

## Connections

### Uses
- [Traffic Devices](../../__about/traffic_devices.md) — `human_duration`, so
  "1 h with the app running" is spelled the same way the session length one
  line above it is

### Used by
- [Traffic Window](traffic_window.md) — the battery line, refreshed every tick
  from [Traffic Meter](../../__about/traffic.md)'s `battery()`

## Functions
- `battery_sentence(battery, clients)`: the whole line, including both
  "this device does not report it" cases

## Gate

`tests/test_battery_report.py`, ten checks each proven by planting its own
defect, fail-closed in `setup/gates.py` (0b17/6). The Kotlin half is asserted
by READING the shell's source — there is no JVM test runner in this repo and
no device attached — so what a real handset reports is proven only on a real
handset.
