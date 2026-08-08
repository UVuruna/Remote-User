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

// What this device can SPEAK with — reported once per connection (owner round
// R2). Only the shell can ask Android's TextToSpeech engine, and only the
// phone has one at all, so the desktop Settings window's Voice dropdown is fed
// from here or it is empty. A dev browser simply sends nothing.
function sendTtsInfo() {
  if (!IN_APP || !window.Android.ttsVoices) return;
  try {
    const voices = JSON.parse(window.Android.ttsVoices() || "[]");
    if (voices.length) send({ type: "tts_info", voices });
  } catch (err) {
    send({ type: "client_log", text: `[notify] tts_info failed: ${err.message}` });
  }
}

// One incoming notice. `msg` is the server's `notify` frame:
// {agent, event, title, text, speak, voice, rate}.
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
      const tag = String(msg.agent || "agent");
      // WHERE it happened rides along when the PC could say so (owner
      // 2026-08-08, task 110). `notifyAt` is a NEWER bridge method, not a
      // fourth argument on `notify`: this page is served by the PC while the
      // shell is installed separately, so a changed arity would simply stop
      // resolving on an older shell and take the notice down with it.
      if (msg.layout && Android.notifyAt) {
        Android.notifyAt(title, body, tag, JSON.stringify(msg.layout));
      } else {
        Android.notify(title, body, tag);
      }
    } catch (err) {
      send({ type: "client_log", text: `[notify] banner failed: ${err.message}` });
    }
  }
  if (prefs.speak && msg.speak !== false && window.Android && Android.speak) {
    const spoken = body ? `${title}. ${body}` : title;
    try {
      // HOW it is said is the PC's decision and rides on every frame (owner
      // round R2) — nothing about the voice is stored on this phone, so a
      // reconnect can never leave it speaking in a voice the desktop no
      // longer selects. `speakAs` is the newer shell; an older one still has
      // plain `speak`, and a notice must never be lost to a shell version.
      if (Android.speakAs) Android.speakAs(spoken, String(msg.voice || ""), Number(msg.rate) || 1);
      else Android.speak(spoken);
    } catch (err) {
      send({ type: "client_log", text: `[notify] speech failed: ${err.message}` });
    }
  }
  if (prefs.tone) notifyTone();
  if (!document.hidden) showToast(body ? `${title} — ${body}` : title);
}

// --- A tap on the notice goes THERE (owner 2026-08-08, task 110) ----------
// *"da klikom na notifikaciju nas odvede do tog layouta … gde je zavrsio taj
// sabagent ili glavni agent."*
//
// The PC resolved the layout when it SENT the notice (server/notify.py ->
// layout_of, matched against the agent's own cwd — nothing is guessed). The
// shell parked it through the tap. This is the last step: act on it, once,
// and only when it still means what it meant.
//
// PULLED from the shell rather than pushed at us, because the tap may have
// cold-started the app: at that moment there is no page and no layout list,
// so a push would land in nothing. `applyNoticeJump` is called from the first
// `layout_state` of a connection, which is the earliest instant the answer
// can be checked against reality.

let noticeJump = null;   // {index, name} the shell handed over, not yet used

function takeNoticeJump() {
  if (!IN_APP || !window.Android.noticeJump) return null;
  try {
    const raw = window.Android.noticeJump();   // reads AND clears
    return raw ? JSON.parse(raw) : null;
  } catch (err) {
    send({ type: "client_log", text: `[notify] noticeJump failed: ${err.message}` });
    return null;
  }
}

// VERIFIED, not trusted. Between the notice going out and his thumb landing,
// a layout may have been removed — which slides every higher index down — or
// the whole list may have been rebuilt. So the NAME decides and the index is
// only a hint: right where it points, else the one layout carrying that name,
// else nothing at all. Jumping into the wrong window is worse than not
// jumping: he would be typing into a stranger.
function noticeTarget(jump) {
  if (!jump || !Array.isArray(layouts) || !layouts.length) return -1;
  const at = Number(jump.index);
  if (layouts[at] && layouts[at].name === jump.name) return at;
  const named = layouts.filter((l) => l.name === jump.name);
  return named.length === 1 ? layouts.indexOf(named[0]) : -1;
}

// Returns whether a tap was CONSUMED — connection.js lets that outrank the
// auto-restore, because only one of the two is something he just did.
function applyNoticeJump() {
  const jump = noticeJump || takeNoticeJump();
  if (!jump) return false;
  noticeJump = null;
  const at = noticeTarget(jump);
  if (at < 0) {
    // Say so rather than silently doing nothing: he tapped expecting to move.
    showToast(`${jump.name} is not on the phone any more`);
    return false;
  }
  if (at === layoutActive) return true;   // already looking at it
  focusLayout(at);
  return true;
}

// The shell's nudge for a tap that arrived while a page was already up. It
// only says LOOK — the answer still comes through the pull above, so there is
// one path into this and not two.
window.__noticeJump = () => {
  noticeJump = takeNoticeJump();
  if (noticeJump && Array.isArray(layouts) && layouts.length) applyNoticeJump();
};

// --- "Notices while the app is closed" (owner decree 2026-08-07) -----------
// His report: *"notifikacije mi stižu tek kada podignem aplikaciju iako je sve
// vreme otvorena u pozadini"*. The shell now holds a small waiting channel of
// its own so a notice arrives with no page at all (NoticeService.kt) — and
// that service needs ONE thing only the user can give it: permission to run
// without Android deferring its traffic while the phone is idle.
//
// Everything a user must do is explained IN the app and nowhere else (hard
// owner principle), so the words live here, on the page, beside every other
// piece of guidance — the shell only opens the system dialog.

const noticePanel = document.getElementById("notice-panel");
const noticeOpened = { t: 0 };
ghostClickArmor(noticePanel, noticeOpened);   // panels.js, loaded before this

function noticeShellState() {
  if (!IN_APP || !window.Android.noticeState) return null;
  try {
    return JSON.parse(window.Android.noticeState());
  } catch (err) {
    send({ type: "client_log", text: `[notify] noticeState failed: ${err.message}` });
    return null;
  }
}

function renderNoticeCard(state) {
  noticePanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card";
  card.innerHTML = `<h2>Notices while the app is closed</h2>
    <p class="sets-sub">Your PC tells this phone the moment an agent finishes
    or needs you — with Remote User closed and the screen off. It is not a
    stream: the phone only listens, and it costs about as much as a chat app
    sitting idle.</p>
    <p class="sets-sub">Android holds messages back for apps it has put to
    sleep, so it has to be told to leave this one alone. One tap, one system
    dialog, and it is done for good.</p>` +
    (state && state.notifications === false
      ? `<p class="sets-sub">Notifications are also switched off for Remote
         User right now. Android Settings → Apps → Remote User →
         Notifications turns them back on — without that, notices can only be
         spoken.</p>`
      : "");

  const allow = document.createElement("button");
  allow.type = "button";
  allow.className = "sets-done";
  allow.textContent = "Allow it to run in the background";
  keepFocus(allow, () => {
    try {
      window.Android.noticeSetup();
    } catch (err) {
      send({ type: "client_log", text: `[notify] noticeSetup failed: ${err.message}` });
    }
  });
  card.appendChild(allow);

  const later = document.createElement("button");
  later.type = "button";
  later.className = "sets-row";
  later.textContent = "Not now";
  keepFocus(later, closeNoticeCard);
  card.appendChild(later);

  noticePanel.appendChild(card);
  noticePanel.hidden = false;
  noticeOpened.t = performance.now();
}

function closeNoticeCard() {
  noticePanel.hidden = true;
  noticePanel.innerHTML = "";
}

// Offered ONCE PER APP VERSION, not once per device: "Not now" has to mean
// something (a card that returns on every connect is the nagging the owner
// banned), but a permanent refusal recorded by one tap would silently disable
// the feature forever on a phone whose owner did not read the card. An update
// is the natural, self-limiting moment to ask again.
function offerNoticeSetup() {
  const state = noticeShellState();
  if (!state) return;                 // dev browser, or a shell without it
  if (state.battery) {
    closeNoticeCard();                // already granted — nothing to say
    return;
  }
  let version = "1";
  try { version = window.Android.appVersion() || "1"; } catch {}
  if (prefGet("noticeOffered") === version) return;
  prefSet("noticeOffered", version);
  renderNoticeCard(state);
}

// Called by the shell when the user comes back from the system dialog, so the
// card leaves the screen the instant the exemption is granted instead of
// waiting for a reconnect.
window.__noticeStateChanged = () => {
  const state = noticeShellState();
  if (!state || state.battery) closeNoticeCard();
};

noticePanel.addEventListener("pointerdown", (e) => {
  if (e.target === noticePanel) closeNoticeCard();   // backdrop tap = later
});
