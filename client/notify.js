// "The PC calls you" (ROADMAP Phase H, owner 2026-08-05): a job on the PC
// finished, and the phone says WHICH one.
//
// The owner's refinement, and the reason this is not a beep: he runs several
// agents at once, so a sound carries no information —
//
//   *"nije dovoljno samo da kaže beep kad završi agent … najbolje od svega je
//   da izbaci notifikaciju koja opisuje koji agent je završio"*
//
// So the AGENT's name leads, and it arrives three ways, strongest first:
//   1. a real Android notification (the shell's bridge) — the only one that
//      still reaches him with the app in the background or the screen off,
//      which is the situation this feature exists for;
//   2. spoken aloud (TextToSpeech) — his "izgovori neku reč", and the one
//      that works while his hands and eyes are on the PC;
//   3. the page's own toast + a short tone, for when he IS looking at it.
//
// Loads after controls.js (uses showToast/prefGet/prefSet/send) and is called by
// connection.js on the `notify` frame. See client/__about/notify.md.
"use strict";

// Per-device switches. Defaults are ON for everything except the tone, which
// is the one that annoys when the phone sits on the desk beside the PC.
function notifyPrefs() {
  try {
    const p = JSON.parse(prefGet("notifyPrefs") || "{}");
    return {
      banner: p.banner !== false,
      speak: p.speak !== false,
      tone: p.tone === true,
    };
  } catch {
    return { banner: true, speak: true, tone: false };
  }
}

function saveNotifyPrefs(p) {
  prefSet("notifyPrefs", JSON.stringify(p));
}

// A short two-note chime. Built here rather than shipped as an audio file:
// the WebView plays it without a network fetch and without a decoder, and the
// page has long had the user gesture that autoplay policy asks for.
function notifyTone() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const now = ctx.currentTime;
    for (const [at, freq] of [[0, 880], [0.16, 1320]]) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = freq;
      osc.type = "sine";
      gain.gain.setValueAtTime(0.0001, now + at);
      gain.gain.exponentialRampToValueAtTime(0.22, now + at + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + at + 0.14);
      osc.connect(gain).connect(ctx.destination);
      osc.start(now + at);
      osc.stop(now + at + 0.16);
    }
    setTimeout(() => ctx.close(), 800);
  } catch (err) {
    // Sound is the least important of the three paths — never let it take
    // the notification down with it.
    send({ type: "client_log", text: `[notify] tone failed: ${err.message}` });
  }
}

// One incoming notice. `msg` is the server's `notify` frame:
// {agent, event, title, text, speak}.
// How long ago it happened, in words — only when that is not "just now".
// A notice held while the phone was away (server/notify.py) must not pretend
// it has only this second arrived (owner 2026-08-06).
function notifyWhen(at) {
  const mins = Math.floor((Date.now() / 1000 - Number(at || 0)) / 60);
  if (!Number.isFinite(mins) || mins < 1) return "";
  return mins < 60 ? `${mins} min ago` : `${Math.floor(mins / 60)} h ago`;
}

function handleNotify(msg) {
  const prefs = notifyPrefs();
  const title = String(msg.title || msg.agent || "Agent");
  const when = notifyWhen(msg.at);
  const body = [String(msg.text || ""), when].filter(Boolean).join(" · ");

  if (prefs.banner && window.Android && Android.notify) {
    try {
      // The TAG is the agent's name on purpose: a second notice from the same
      // agent REPLACES its own line instead of stacking, while four agents
      // keep four separate lines — which is the whole point of naming them.
      Android.notify(title, body, String(msg.agent || "agent"));
    } catch (err) {
      send({ type: "client_log", text: `[notify] banner failed: ${err.message}` });
    }
  }
  if (prefs.speak && msg.speak !== false && window.Android && Android.speak) {
    try {
      Android.speak(body ? `${title}. ${body}` : title);
    } catch (err) {
      send({ type: "client_log", text: `[notify] speech failed: ${err.message}` });
    }
  }
  if (prefs.tone) notifyTone();
  if (!document.hidden) showToast(body ? `${title} — ${body}` : title);
}
