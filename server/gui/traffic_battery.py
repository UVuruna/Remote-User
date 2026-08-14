"""What this app costs the PHONE'S BATTERY while it is running (T80d).

Its own module by RESPONSIBILITY, not by line count — the same split
`traffic_axis.py` made from `traffic_window.py` next door. That window's
subject is BYTES: how many crossed the socket, in which direction, and
whether any crossed while nobody was connected. This one's subject is POWER,
which is a different measurement with a different source and a different way
of being unavailable: the bytes are counted by the PC at its own socket and
therefore always exist, while the battery can only ever be measured by the
phone about itself and a large share of devices refuse.

That refusal is why there is a module here at all. The owner's requirement
was that EVERY device answers, not only his — so the number is measured on
the handset (`Bridge.batteryStats`) and rides the existing heartbeat, and a
device that will not answer must SAY so in words on his screen. Never a
blank, never a dash, and never a zero: "0 mA" reads as "this app costs
nothing", which is the most flattering possible claim about a measurement
that never happened.

A simulation was refused outright and may not come back: an Android emulator
has no battery and reports a fixed fake value, so a simulated figure would
look authoritative and mean nothing.

The wording is a PURE function of (what the phone said, is anyone connected)
so its gate can prove the rules without building a Qt window — the same
reason `traffic_window.history_since` is pure.
"""

import traffic_devices

# Below this, the session is too young for a percentage to MEAN anything and
# the clause is left off entirely (found 2026-08-14 by photographing the
# window, not by reading the code: the staged card read "4% used in 0s with
# the app running"). A battery level is an integer percent, so the smallest
# step this can ever report is 1% — and 1% over a few seconds implies a rate
# no phone has, i.e. the reading simply crossed a rounding boundary. The
# level itself and the live draw are still stated the whole time; what waits
# is only the sentence that would put a number on a span too short to carry
# one.
MIN_DROP_SPAN_S = 120


def battery_sentence(battery: dict | None, clients: int) -> str:
    """What this app costs the phone's battery WHILE IT IS RUNNING, in plain
    words (T80d, owner request 2026-08-14).

    A pure function of (what the phone said, is anyone connected) on purpose,
    exactly like `history_since` above: it is the one place the wording is
    decided, so its gate can prove the two rules that matter without building
    a window.

    THE TWO RULES:

    1. A device that does not report SAYS SO, in words. Never a blank, never
       a dash, and above all never a zero — "0 mA" reads as "this app costs
       nothing", the single most flattering thing this window could claim,
       and it would be a claim about a measurement that never happened.
    2. Each half is independent. A phone that reports its level but not its
       draw (a large share of them: `BATTERY_PROPERTY_CURRENT_NOW` is
       optional and widely stubbed) states the level it has and names the
       half it is missing — one absent property may never silence the other.
    """
    if not battery:
        if clients > 0:
            return ("Phone battery: this device does not report it — some "
                    "phones will not say, and an older app version cannot "
                    "ask.")
        return ("Phone battery: the phone reports its own level and draw "
                "while it is connected.")

    parts: list[str] = []
    level = battery.get("level")
    parts.append(f"Phone battery: {level}%" if level is not None
                 else "Phone battery: this device does not report its level")

    drop, seconds = battery.get("level_drop"), battery.get("seconds")
    if drop is not None and seconds and seconds >= MIN_DROP_SPAN_S:
        span = traffic_devices.human_duration(seconds)
        parts.append(f"{drop}% used in {span} with the app running" if drop > 0
                     else f"no drop yet in {span} with the app running")

    current, avg = battery.get("current_ua"), battery.get("avg_ua")
    if current is not None:
        now = f"drawing {current / 1000:.0f} mA now"
        if avg is not None:
            now += f", {avg / 1000:.0f} mA average while connected"
        parts.append(now)
    else:
        parts.append("this device does not report its draw")

    if battery.get("charging"):
        # Stated because it changes what every number above MEANS: a level
        # that is not falling while charging says nothing about the cost.
        parts.append("charging")
    return "  ·  ".join(parts)
