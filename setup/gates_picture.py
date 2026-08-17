"""THE PICTURE GATES — what proves the owner actually SEES something.

SPLIT OUT OF setup/gates.py on 2026-08-16 (THE STRUCTURE LAW), the same day
setup/gates_desktop.py was split for the same reason: gates.py had reached
1,000 lines again and the split was made by RESPONSIBILITY, not by where the
line count happened to fall. Everything left in gates.py proves a PROTOCOL
message answers, a layout behaves, input lands, an action reaches his file,
or a doc stays linked. These seven prove the capture/encode/decode/draw
path — that the camera is alive, the encoder crops right, the phone's own
decoder can drink what it is sent, and the page actually draws the frame
that arrives. That is exactly the failure class of 2026-08-16: his blue
canvas, where every control on the phone kept answering and there was no
picture behind any of them.

`step` and `run` are PASSED IN, exactly as gates.py takes them from build.py
and for the same reason: build.py owns the console's voice and the
subprocess policy, and a module that imported them back would be a cycle
for no gain.
"""

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent


def picture_gates(step, run) -> None:
    # And that a phone which has GONE takes its encoder with it (live failure
    # 2026-08-07). Cancelling `asyncio.to_thread(open_session)` does not stop
    # the thread, so one leaked session ran four hours at native 4K with
    # nobody watching — 12,924 s of ffmpeg CPU, 1,890 "stream backlog"
    # warnings, and the owner's own mouse juddering at his desk. Nothing in
    # the suite walked a connection's END, which is why every gate was green
    # over it for three days.
    step("0g/6  STREAM LIFECYCLE GATE — a client that is gone leaves nothing "
         "behind (tests/test_stream_lifecycle.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_stream_lifecycle.py")])
    # …and the same connection's OTHER end: a quality change (owner's #1 report
    # 2026-08-10). A bitrate can only be applied by a new encoder, and closing
    # the old one used to tear dxcam down with it — the new ffmpeg then had no
    # frame to encode, wrote no init segment, and the failed RE-open closed a
    # socket that also carries input, layouts and dictation.
    step("0r/6  QUALITY RESET GATE — changing the bitrate cannot kill the app "
         "(tests/test_quality_reset.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_quality_reset.py")])

    # THE DEVICE'S OWN DECODER IS A WALL (owner report 2026-08-12: "native
    # 20 Mbps still sends no picture"). His log: 3840x2160@30 played smoothly
    # (jumps=0 for two minutes); the moment the PC card went to 60 fps every
    # session opened level 5.2 and the same tablet threw the picture forward
    # ten times every 15 s — a decoder drowning, not a network, and nothing
    # anywhere asked the device what it can decode. The rules are a pure
    # module (client/decode-caps.js): probe mediaCapabilities per resolution
    # step, cap the requested fps at the device's smooth ceiling, SAY the cap,
    # and a runtime backstop lowers a session's ceiling when the live windows
    # keep counting jumps that the spec sheet promised away. Driven whole in
    # node with the codec strings from his real sessions. Needs node, like
    # 0j/0k/0o/0p/0q/0y — never skip it silently.
    step("0ao/6  DECODE CAPS GATE — the phone never requests a stream its "
         "own decoder cannot drink (tests/test_decode_caps.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_decode_caps.py")])

    # THE PHONE NEVER DECODES PIXELS IT DOES NOT SHOW (owner order
    # 2026-08-12, his own words — lang-ok: owner quote: "zašto bi telefon
    # dekodirao nešto što ne vidi"). H.264 used to stream the FULL monitor
    # always: a quarter-width layout still cost a full 4K@60 decode with
    # three quarters cropped away on the canvas. The per-client ffmpeg now
    # crops to the focused layout's region, `config.stream_region` tells the
    # page what the video covers, and a region change ends the mismatched
    # session at the layout choke point. Driven with the REAL session and
    # the REAL choke point, and the crop case is his own live layout from
    # his own log.
    step("0ap/6  REGION STREAM GATE — the encoder crops to the focused "
         "layout, and the page maps it back (tests/test_region_stream.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_region_stream.py")])

    # OWNER ORDER 2026-08-14, in his own words: "ako korisnik odabere 10 fps
    # onda je to dovoljno, nema potrebe 120 puta u sekundi da telefon iscrtava
    # sliku kada se ona menja samo 10 puta u sekundi" (lang-ok: owner quote).
    # render.js drew on EVERY animation frame — 120 Hz on his S25 Ultra against
    # a stream he may have set to 10 fps, so eleven of every twelve full-canvas
    # composites redrew a picture already on the screen. It draws on frame
    # ARRIVAL now, so the rate follows the encoder by construction and never a
    # number the panel claims about itself. A RATE cannot be read off a diff,
    # so this gate counts real redraws in real Chromium over a real second.
    step("0b18/6  REDRAW RATE GATE — the phone draws when there is a new "
         "picture, not when the panel blinks (tests/test_redraw_rate.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_redraw_rate.py")])

    # T76 + T79, owner report 2026-08-14, and he is angry because he asked for
    # this at the very start and was told yes. In translation: "why is
    # downscaling done even when the picture is zoomed — when we zoom on the
    # phone we are enlarging that downscaled resolution so the picture is
    # blurry, even though the whole screen does not need to be sent then
    # either, because we are in a slice just like in layout mode".
    #
    # The gap was one missing wire, not a missing feature: `H264Session`
    # cropped only from a region fed by a focused LAYOUT, and the `viewport`
    # message the pinch has always sent was DISCARDED in H.264 mode — a rule
    # the docs stated as deliberate ("JPEG mode only"), which is what made it
    # unfindable for a whole round. Fix: the settled visible rect feeds the
    # SAME region path (client/zoom-crop.js's floor + settle, pure and driven
    # whole here; `layout_api.stream_crop`, the ONE derivation both the
    # session opener and the choke point ask), with the focused layout's
    # region as a FLOOR the crop may never widen past.
    #
    # T79 rides the same function because T76 is what makes it matter: a crop
    # below the panel is sent at its own small size, where a flat `-b:v` spent
    # ~2.2x the reference's bits per pixel — an edge case until the zoom made
    # it the normal one. On cellular ONLY (read off the saving profile the
    # phone already sends — never a new field), the number follows the pixels,
    # downward only, with a floor.
    #
    # Fail-closed because every defect here is invisible in code review and
    # obvious on his screen: a blurry zoom looks exactly like a working one in
    # a diff, a crop that widens past a layout leaks windows he chose not to
    # show, a settle that fires mid-gesture is a blink storm nobody can read
    # off a variable, and a bitrate that is capped looks precisely like a
    # bitrate that was simply not spent.
    step("0b13/6  ZOOM CROP GATE — the zoom crops the encoder (never wider "
         "than the layout), settles before it blinks, and on cellular the "
         "bitrate follows the pixels (tests/test_zoom_crop.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_zoom_crop.py")])

    # T112, 2026-08-16: the blue-canvas failure — capture died silently
    # (dxcam parked inside an infinite output-recovery loop, 3.8 hours in his
    # own log) while every control kept answering, so the phone had no way to
    # tell a dead camera from a dead app. `server/capture_recovery.py` is the
    # rebuild ladder (abandon the parked camera without waiting for it,
    # reopen, re-enumerate DXGI), driven by a `CaptureGuard` that judges by
    # the frame clock alone (`server/capture.py`'s `frame_age`), wired into
    # `H264Manager` (`server/h264_streamer.py`) and told to the phone by
    # `server/web.py`. This proves the guard's judgement (healthy/stalled/
    # cooldown/not-wanted/recovered), the rebuild ladder's escalation and its
    # refusal to accept a camera that cannot grab (the "reports the blue
    # screen as fixed" trap), the `start()` escalation on a double dxcam
    # refusal, the manager's own wiring (`_picture_is_wanted`, the guard
    # stopped by `shutdown()`), and the phone notice — with NO real dxcam and
    # NO real desktop touched (`sys.modules["dxcam"]` replaced before capture
    # or capture_recovery import it), each check proven against its own
    # planted defect.
    step("0b23/6  CAPTURE RECOVERY GATE — a dead camera is replaced without "
         "asking the owner's desktop, and the phone is told "
         "(tests/test_capture_recovery.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_capture_recovery.py")])

    # Owner decision 2026-08-17, and the rule is his own idea: "how long it
    # stands visible depends on how much text is in it". Every toast used to
    # stand exactly 2500 ms — a glance's worth for "Reconnecting…" and half a
    # read for a sentence naming a window and what the PC refused to do with
    # it, so the cost fell entirely on the notices that actually say
    # something.
    #
    # IT LIVES WITH THE PICTURE GATES BY RESPONSIBILITY, not because gates.py
    # stood at the structure law's wall (it did, and that is not a reason to
    # put a gate anywhere in particular): these are the checks that prove he
    # actually SEES something, and a sentence that leaves the screen before it
    # can be finished is unseen exactly like a frame that never arrived.
    #
    # The gate holds the SHAPE of the curve and never its exact numbers —
    # longer text never means less time, a floor at the old constant so
    # nothing this app already says got shorter, and a ceiling because a pill
    # is a glance and not a page. The numbers are his to tune on the real
    # device, the same discipline the gamepad's stick curve is held with.
    step("0b30/6  TOAST TIMING GATE — a notice stands as long as there is to "
         "read (tests/test_toast_timing.py)")
    run([sys.executable, str(PROJECT_DIR / "tests" / "test_toast_timing.py")])
