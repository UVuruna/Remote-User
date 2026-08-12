// THE DEVICE'S OWN DECODER IS A WALL THE PC CANNOT SEE (owner report
// 2026-08-12: "native 20 Mbps still sends no picture"). His server log told
// the real story: at 3840×2160@30 (level 5.1) the tablet played smoothly —
// behind=0.31s steady, jumps=0 for two minutes — and the moment the PC card
// went to 60 fps every session opened level 5.2 and the SAME tablet threw the
// picture forward ten times every 15 s, seconds behind. That is a decoder
// drowning, not a network: the bytes arrive faster than the SoC can turn them
// into frames, the live regulator can only slow and flush, and what the owner
// sees is a frozen or jumping picture he reads as "no stream at all".
//
// The PC cannot know what a phone's SoC decodes; the phone can ask its own
// `navigator.mediaCapabilities`. So the ceiling lives on the PAGE: probe what
// this device decodes SMOOTHLY at each resolution step, remember it, and cap
// the fps the quality panel requests — with the cap SAID in a toast and in
// the panel, never silent (quality.js owns the wiring; this module owns the
// rules). Pure by design — no DOM, no socket — so the gate can run it whole
// (the view-anchor.js / live-clock.js pattern, tests/test_decode_caps.py).
"use strict";

// The fps steps the quality panel offers, highest first — the probe walks
// these and the runtime backstop steps down through them.
const DECODE_FPS_STEPS = [60, 30, 15, 10];
// Forward jumps in one 15 s live-report window that mean the decoder is not
// keeping up (his drowning log windows counted 9–10; healthy ones 0).
const DECODE_BAD_JUMPS = 8;
// How many such windows IN A ROW before the backstop lowers the ceiling —
// one window can be a network burp, two consecutive is a state.
const DECODE_BAD_WINDOWS = 2;

// H.264 Main-profile level table — the same arithmetic the encoder's own
// level choice follows, verified against live sessions in the owner's log:
// 2560×1440@30 → avc1.4D4032 (5.0), 3840×2160@30 → 4D4033 (5.1),
// 3840×2160@60 → 4D4034 (5.2). Probing with the level the stream would
// really carry is the point: a 5.2 string asked about a 5.1 stream can
// false-negative `supported` on decoders that stop at 5.1.
const H264_LEVELS = [
  { hex: "1E", maxMbs: 1620, maxMbps: 40500 },     // 3.0
  { hex: "1F", maxMbs: 3600, maxMbps: 108000 },    // 3.1
  { hex: "20", maxMbs: 5120, maxMbps: 216000 },    // 3.2
  { hex: "28", maxMbs: 8192, maxMbps: 245760 },    // 4.0
  { hex: "2A", maxMbs: 8704, maxMbps: 522240 },    // 4.2
  { hex: "32", maxMbs: 22080, maxMbps: 589824 },   // 5.0
  { hex: "33", maxMbs: 36864, maxMbps: 983040 },   // 5.1
  { hex: "34", maxMbs: 36864, maxMbps: 2073600 },  // 5.2
  { hex: "3C", maxMbs: 139264, maxMbps: 4177920 }, // 6.0
];

/** The MSE codec string a w×h@fps H.264 Main stream really carries. */
function h264Codec(w, h, fps) {
  const mbs = Math.ceil(w / 16) * Math.ceil(h / 16);
  const mbps = mbs * fps;
  const row = H264_LEVELS.find((r) => mbs <= r.maxMbs && mbps <= r.maxMbps) ||
    H264_LEVELS[H264_LEVELS.length - 1];
  return `avc1.4D40${row.hex}`;
}

/** The width a panel resolution step actually encodes — mirrors the server's
 *  own derivation: "native" is the monitor, everything else scales the PC
 *  card's width. Unknown steps encode the base (the server's fallback too). */
function stepWidth(res, baseW, monitorW) {
  if (res === "native") return monitorW || baseW;
  if (res === "2/3") return Math.round((baseW * 2) / 3);
  if (res === "1/2") return Math.round(baseW / 2);
  return baseW;
}

/** Highest step this device marked smooth, from a probe's {fps: bool} map.
 *  A device that flatters NOTHING still answers the lowest step — the stream
 *  must keep living (a slideshow beats a black canvas), and the runtime
 *  backstop can take it from there. */
function smoothCeiling(smooth, steps) {
  for (const f of steps) if (smooth[f]) return f;
  return steps[steps.length - 1];
}

/** The fps the stream should actually run: the request capped by the device
 *  ceiling for this width. `want` 0 means "follow the PC" (base fps). When
 *  nothing is capped, `fps` echoes `want` untouched — the wire keeps saying
 *  "follow the PC" and an older server sees exactly the old message. A
 *  missing ceiling (0) or an unknown base caps nothing: never invent. */
function capFps(want, baseFps, ceiling) {
  const target = want > 0 ? want : baseFps || 0;
  if (!ceiling || !target || target <= ceiling) return { fps: want, capped: false };
  return { fps: ceiling, capped: true };
}

/** The runtime backstop's answer: the first step BELOW the fps that is
 *  actually running, or 0 when the floor is already reached.
 *  mediaCapabilities answers from the decoder's spec sheet, not the live
 *  pipeline — a device can accept 4K@60 on paper and still drown in it. */
function struggleCeiling(runFps, steps) {
  for (const f of steps) if (f < runFps) return f;
  return 0;
}

/** Two ceilings act at once — the persisted probe result and the session's
 *  own struggle override — and the LOWER one wins. 0 means "no opinion". */
function combinedCeiling(probed, session) {
  if (probed && session) return Math.min(probed, session);
  return probed || session || 0;
}

/** "20M" / "4800k" / "12000000" → bits per second, for the probe's bitrate
 *  field. Unparseable input answers a sane default rather than 0 — a probe
 *  with bitrate 0 is a question about a stream that does not exist. */
function bitrateBits(text) {
  const raw = String(text || "").trim();
  const number = parseFloat(raw);
  if (!number || number <= 0) return 12e6;
  const unit = raw.slice(-1).toLowerCase();
  return unit === "m" ? number * 1e6 : unit === "k" ? number * 1e3 : number;
}

// THE PANEL IS A SECOND, DIFFERENT WALL (owner order 2026-08-12: "what is the
// point of the PC sending 4K if the Android device cannot receive it — a Redmi
// Pad is 1920x1200"). The decode ceiling above is about how FAST this SoC can
// turn bytes into frames; this is about how many pixels the glass can light up
// at all. They compose — neither replaces the other — and the SERVER is what
// applies this one (server/h264_streamer.py `_scale_size`, the same
// arithmetic). It is mirrored here for one reason: the decode ceiling must
// judge the size that is REALLY encoded, or a cap earned by a full 4K desktop
// would go on holding a small, already-downscaled stream at the capped fps.

/** This device's real panel pixels — CSS px x devicePixelRatio — or null when
 *  they cannot be read. Never guessed: null means "cap nothing". */
function devicePanel() {
  if (typeof window === "undefined" || !window.screen) return null;
  const dpr = window.devicePixelRatio || 1;
  const w = Math.round((window.screen.width || 0) * dpr);
  const h = Math.round((window.screen.height || 0) * dpr);
  return w > 1 && h > 1 ? { w, h } : null;
}

/** The width a w x h crop is really encoded at once the panel caps it — the
 *  mirror of the server's `_scale_size`: long side against long side, short
 *  against short (the phone's rotation is locked to the layout's orientation),
 *  never above 1 (a crop smaller than the panel is sent at its own size), and
 *  even for yuv420p. An unknown panel or an unknown crop caps nothing. */
function panelScaledWidth(w, h, panel) {
  if (!panel || !panel.w || !panel.h || !w || !h) return w;
  const factor = Math.min(1,
    Math.max(panel.w, panel.h) / Math.max(w, h),
    Math.min(panel.w, panel.h) / Math.min(w, h));
  if (factor >= 1) return w;
  return Math.max(2, Math.floor(Math.round(w * factor) / 2) * 2);
}

/** Ask the device's own decoder: {fps: smooth} for each step at w×h.
 *  Browser-only wrapper — a device without the API answers null and nothing
 *  is ever capped (no behaviour change), and a call that throws marks that
 *  step smooth: an API that errors must never lower anything. */
async function probeSmoothFps(w, h, bitrate, steps) {
  const mc = typeof navigator !== "undefined" && navigator.mediaCapabilities;
  if (!mc || !mc.decodingInfo) return null;
  const smooth = {};
  for (const fps of steps) {
    try {
      const info = await mc.decodingInfo({
        type: "media-source",
        video: {
          contentType: `video/mp4; codecs="${h264Codec(w, h, fps)}"`,
          width: w, height: h, bitrate, framerate: fps,
        },
      });
      smooth[fps] = !!(info && info.supported && info.smooth);
    } catch (e) {
      smooth[fps] = true;
    }
  }
  return smooth;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    DECODE_FPS_STEPS, DECODE_BAD_JUMPS, DECODE_BAD_WINDOWS,
    h264Codec, stepWidth, smoothCeiling, capFps, struggleCeiling,
    combinedCeiling, bitrateBits, devicePanel, panelScaledWidth,
  };
}
