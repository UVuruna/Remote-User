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
// phone has one at all. Since 2026-08-12 the desktop no longer offers a voice
// dropdown (the choice moved onto the phone, below), so this list is the PC's
// diagnostic record of what the connected device can do — nothing on the
// desktop chooses from it any more. A dev browser simply sends nothing.
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

// THE LAST-RESORT RULE: muting a carrier must never lose the notice, only
// quiet it. Muting all three at once is not "no notice" — it is "give me
// back whichever carrier costs him the least", and that is the banner: it
// needs no sound and reaches him with the screen off, which speech and the
// toast cannot. So an all-off state is answered as banner-only, and the
// Phone card's banner switch is labelled the last resort so this is not a
// silent surprise (client/phone-panel.js).
function effectiveNotifyPrefs() {
  const p = notifyPrefs();
  if (!p.banner && !p.speak && !p.tone) return { banner: true, speak: false, tone: false };
  return p;
}

// ── WHICH VOICE, AND HOW FAST — THIS DEVICE'S OWN ANSWER (owner 2026-08-12)
// Round R2 put both on the DESKTOP, and his report is what that cost: he uses
// a tablet AND a phone, their engines carry different voices, and one dropdown
// on one PC cannot name a voice that exists on both. So the choice is per
// DEVICE, through the same SharedPreferences bridge every other per-device
// switch uses — never bare localStorage, which is keyed by ORIGIN and split
// this app's state across its LAN and Tailscale addresses once already
// (2026-08-05).
//
// THE FRAME'S VALUES REMAIN THE FALLBACK rather than being ignored, which is
// what keeps this a safe change in both directions: a device that has never
// opened the card behaves exactly as it did yesterday, and a PC that still
// carries a desktop choice is still obeyed by it. So an empty pref means "no
// opinion HERE", not "the engine default" — and the card says that in words
// (`renderNotifyVoiceCard`) instead of leaving him to infer it from silence.
// A rate is read as a NUMBER and only a positive one counts: an unset pref
// reads back as null, and a corrupted one must not silence the notice by
// handing TextToSpeech a NaN.
function notifyVoicePref() {
  return String(prefGet("notifyVoice") || "");
}

function notifyRatePref() {
  const saved = parseFloat(prefGet("notifyRate"));
  return saved > 0 ? saved : 0;
}

function handleNotify(msg) {
  const prefs = effectiveNotifyPrefs();
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
    // WHAT THE VOICE SAYS is now SHORT — project + conversation title only,
    // never the body (owner order, v0.0.107 screenshots: a long Serbian
    // notification body was read out loud in full). `speak_text` is built
    // server-side (server/notify.py -> speak_summary) so the same rule
    // covers every carrier — page, waiting channel, queued — since all
    // three forward this exact `notice` dict unchanged. A server that
    // predates this field sends none, and the fallback is the OLD
    // behaviour rather than silence: an older PC must keep speaking
    // something.
    const spoken = msg.speak_text || (body ? `${title}. ${body}` : title);
    try {
      // HOW it is said is THIS PHONE's own answer since 2026-08-12, with the
      // frame's values as the fallback — `notifyVoicePref` below says why.
      // `speakAs` is the newer shell; an older one still has plain `speak`,
      // and a notice must never be lost to a shell version.
      if (Android.speakAs) {
        Android.speakAs(spoken, notifyVoicePref() || String(msg.voice || ""),
                        notifyRatePref() || Number(msg.rate) || 1);
      } else {
        Android.speak(spoken);
      }
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

// A jump can only be ACTED on down a live socket (task 236). This is the
// exact ordering his THIRD report lives in: the tap arrives while the app is
// in the background, so the page is hidden and its socket is closed BY RULE
// (constraint 8), and the shell nudges the page the instant the intent lands
// (MainActivity.onNewIntent → __noticeJump) — before onResume, before the
// reconnect. Acting there spent the jump on a `send()` that state.js drops on
// a dead socket, and the reconnect that followed a second later resumed the
// layout the server remembered: the previous one, every time. So a jump the
// page cannot act on is LEFT WHERE IT IS — in the shell, unread, so even a
// WebView reload cannot lose it — and the first `layout_state` of the new
// connection is what pulls it.
function noticeCanJump() {
  return typeof ws !== "undefined" && ws && ws.readyState === WebSocket.OPEN;
}

// Returns whether a tap was CONSUMED — connection.js lets that outrank the
// auto-restore, because only one of the two is something he just did.
function applyNoticeJump() {
  if (!noticeCanJump()) return false;
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
  // Nothing is PULLED here unless it can be acted on right now (task 236):
  // reading the shell's copy clears it, and a jump cleared but not acted on
  // is a jump lost. A hidden page with a closed socket, or a page whose
  // layout list has not arrived yet, simply leaves it parked and lets
  // `applyNoticeJump` — called from the first `layout_state` of every
  // connection — do the pull when it can actually land.
  if (!noticeCanJump() || !Array.isArray(layouts) || !layouts.length) return;
  applyNoticeJump();
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
  card.className = "sets-card card-columns";
  card.innerHTML = `<h2>Notices while the app is closed</h2>
    <p class="sets-sub">Your PC tells this phone the moment an agent finishes
    or needs you — with Vibe Coder closed and the screen off. It is not a
    stream: the phone only listens, and it costs about as much as a chat app
    sitting idle.</p>
    <p class="sets-sub">Android holds messages back for apps it has put to
    sleep, so it has to be told to leave this one alone. One tap, one system
    dialog, and it is done for good.</p>` +
    (state && state.notifications === false
      ? `<p class="sets-sub">Notifications are also switched off for Vibe
         Coder right now. Android Settings → Apps → Vibe Coder →
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

// --- Settings → Voice: WHICH voice, on THIS device (owner 2026-08-12) ------
//
// His decision, and the reason he gave for it: he uses a tablet AND a phone,
// their text-to-speech engines carry different voices, and the desktop's one
// dropdown could not name a voice that exists on both — pick the tablet's and
// the phone falls back to its engine default, silently, with the Settings
// window still showing a name. So the two master switches stay on the PC
// ("Tell my phone when an agent finishes" and "Say it out loud", which are
// decisions about the JOB) and WHICH VOICE moved to the device that owns it.
//
// AND EVERY VOICE IS HEARABLE BEFORE IT IS CHOSEN, which is the same rule the
// dictation card already obeys (owner 2026-08-09: "treba da mogu da CUJEM da
// bih odabrao"). # lang-ok: owner quote  A list of engine voice names —
// "en-us-x-tpf-local", "sr-rs-x-ser-network" — tells nobody anything; the
// sound does.
//
// The panel's element is BUILT HERE rather than declared in index.html: the
// page's markup is served by the PC and this file is what owns the feature,
// so one file carries the whole thing. It joins panels.css's overlay selector
// lists like every other panel.

const voicePanel = document.createElement("div");
voicePanel.id = "notify-voice-panel";
voicePanel.hidden = true;
document.body.appendChild(voicePanel);
const voiceOpened = { t: 0 };
ghostClickArmor(voicePanel, voiceOpened);   // panels.js

// ONE short line, in English, and always the SAME one. The dictation card's
// samples are per-language because what it is choosing IS the language; here
// the language is fixed and the only thing that varies between two taps is
// the voice, so a changing sentence would be noise between the two things he
// is comparing. It says what a notice says, so he judges the voice on the job
// it will actually do.
const NOTIFY_SAMPLE = "An agent has finished — this is how notices will sound.";

// The paces the desktop used to offer, unchanged (Android's TextToSpeech rate,
// 1.0 being the engine's own normal pace).
const NOTIFY_RATES = [0.8, 1, 1.25, 1.5];
const NOTIFY_RATE_LABELS = ["0.8×", "1×", "1.25×", "1.5×"];

// ONE SAMPLE AT A TIME, NEVER A QUEUE — the dictation card's rule and the same
// reason (panels.js `dictListen`): the shell hands text to TextToSpeech with
// QUEUE_ADD and exposes no stop, and the voice is set per CALL but applies to
// the whole queue, so a second tap during a sample would speak BOTH in the
// second voice. The guard is local to this card rather than shared with the
// dictation one because only one full-screen panel can be reached at a time —
// each covers the controls that would open the other.
let voiceSpeakingName = null;
let voiceSpeakingTimer = null;

// WHICH language is open, or "" for the list of languages (owner 2026-08-13).
// Kept while the card is open and cleared when it closes, exactly like the
// dictation card's `dictMoreOpen`: re-opening the card should show the list, not
// wherever he happened to be standing last time. Its own variable rather than
// one shared with the dictation card — the two cards hold DIFFERENT languages
// (voices installed here vs languages he can dictate in), so one shared
// position would open a language in one card that the other does not have.
let voiceOpenLang = "";

/** Lights exactly the row that is speaking, and no other.
 *
 *  THE LAMP IS DRAWN FROM STATE, never remembered as a node. His report of
 *  2026-08-13: two or more rows often looked selected at once. The old code
 *  handed a `btn` to a timer and cleared the class on THAT node seconds
 *  later; any re-render in between — choosing a voice re-renders the whole
 *  card — left the class on a live button nobody would ever clear, so a lit
 *  speaker sat beside a chosen row and read as a second selection.
 *
 *  It re-classes in place rather than re-rendering: the list is as long as the
 *  engine makes it, and rebuilding it would throw away his scroll position on
 *  every tap — the rows he is comparing are the ones he just scrolled to. */
function voiceLamps() {
  if (!voicePanel) return;
  for (const b of voicePanel.querySelectorAll(".dict-listen")) {
    b.classList.toggle("busy", (b.dataset.voice || "") === voiceSpeakingName);
  }
}

/** A sample has really ended — finished, cut off by the next one, or failed.
 *  The shell calls this; nothing here decides it. */
function voiceSampleEnded() {
  clearTimeout(voiceSpeakingTimer);
  voiceSpeakingName = null;
  voiceLamps();
}
window.__ttsDone = voiceSampleEnded;

/** Plays one voice. A tap while another is speaking REPLACES it.
 *
 *  His report of 2026-08-13: a second voice could not be tapped until the
 *  first had finished. The old guard `if (voiceSpeakingName) return;` was not
 *  arbitrary — the engine queues (QUEUE_ADD) and its voice is set per call but
 *  applies to the whole queue, so a second tap would have spoken BOTH samples
 *  in the second voice, which is worse than refusing. The refusal was the
 *  right answer to the wrong question: the fix belongs in the shell, which can
 *  flush the queue, and it is there now (`Notifier.speakSample`).
 *
 *  AND NOTHING HERE ESTIMATES A DURATION any more (constraint 15). The lamp
 *  used to be released by a character-count guess, so it lied in both
 *  directions — dark while a slow network voice still spoke, lit for seconds
 *  after a short one stopped. The engine reports its own end.
 *
 *  An older shell has neither method; it keeps exactly the old behaviour, and
 *  its guess survives only as the give-up point for the lamp. */
function voicePreview(voice) {
  const name = String(voice.name || "");
  // At the pace he has chosen HERE: a voice at 1.5× is a different thing to
  // listen to than the same voice at 0.8×, and it is the pair he will hear.
  const rate = notifyRatePref() || 1;
  const bridge = window.Android;
  const canInterrupt = !!bridge && typeof bridge.speakSample === "function";
  if (!canInterrupt && voiceSpeakingName) return;   // old shell: as before
  try {
    if (canInterrupt) bridge.speakSample(NOTIFY_SAMPLE, name, rate);
    else bridge.speakAs(NOTIFY_SAMPLE, name, rate);
  } catch {
    showToast("This device could not play the sample");
    return;
  }
  clearTimeout(voiceSpeakingTimer);
  voiceSpeakingName = name;
  if (!canInterrupt) {
    voiceSpeakingTimer = setTimeout(voiceSampleEnded,
                                    dictSampleMs(NOTIFY_SAMPLE));
  }
  voiceLamps();
}

/** The label a voice wears.
 *
 *  INSIDE A LANGUAGE GROUP the language word is the heading above it, so the
 *  row wears only what tells it from its siblings — `lang-groups.js` decides
 *  that (the engine's own variant when it is a word, "Voice 1, 2, 3" when it
 *  is machinery: the owner's ruling of 2026-08-13). `grouped` is that label
 *  and is used verbatim when present.
 *
 *  Without one — the no-choice row, and any aria text built before grouping —
 *  it falls back to the engine's own label plus its locale, which is the shape
 *  this card had before groups and the shape the removed desktop dropdown had,
 *  so an old screenshot and a new one still name the same voice. */
function voiceLabel(voice, grouped) {
  if (grouped) return grouped;
  const locale = String(voice.locale || "");
  const label = String(voice.label || voice.name || "");
  return locale ? `${label} (${locale})` : label;
}

/** One row: the choice on the left, the speaker on the right.
 *
 *  The button is a SIBLING of the <label>, never a child — a click anywhere
 *  inside a label activates the control that label owns, so a speaker nested
 *  in the row would also CHOOSE that voice, and the tap meaning "let me hear
 *  it first" would have decided (the dictation card's own lesson). */
function voiceRow(voice, chosen, grouped) {
  const row = document.createElement("div");
  row.className = "dict-row";
  const label = document.createElement("label");
  const name = String(voice.name || "");
  label.className = "sets-row dict" + (name === chosen ? " sel" : "");
  const rb = document.createElement("input");
  rb.type = "radio";
  rb.name = "notify-voice";
  rb.checked = name === chosen;
  rb.addEventListener("change", () => {
    prefSet("notifyVoice", name);
    renderNotifyVoiceCard();      // the row re-lights, and the caption follows
  });
  const txt = document.createElement("span");
  txt.className = "dict-name";
  txt.textContent = voiceLabel(voice, grouped);
  label.append(rb, txt);
  row.appendChild(label);

  if (name) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "dict-listen" + (name === voiceSpeakingName ? " busy" : "");
    // WHICH voice this speaker plays, on the node itself — `voiceLamps` reads
    // it back to light exactly one row without rebuilding the list.
    btn.dataset.voice = name;
    btn.innerHTML = svg("listen");
    // Named for the VOICE, not "play": a screen reader saying "button" over a
    // speaker glyph says nothing about which row it belongs to. It names the
    // voice IN FULL — engine label and locale — rather than the group-relative
    // row text: read aloud out of the list, "male 1" alone says nothing, and a
    // screen-reader user has no heading in view to supply the language.
    btn.setAttribute("aria-label", `Listen to ${voiceLabel(voice)}`);
    btn.title = `Listen to ${voiceLabel(voice)}`;
    keepFocus(btn, () => voicePreview(voice));
    row.appendChild(btn);
  }
  return row;
}

function renderNotifyVoiceCard() {
  const voices = dictVoices();   // panels.js — the SAME source, never a second
  const chosen = notifyVoicePref();
  voicePanel.innerHTML = "";
  const card = document.createElement("div");
  // `card-split`, not `card-columns`: a voice list is as long as the engine
  // makes it, and a capped multicol answers "I do not fit" by growing a column
  // off the side of the screen instead of scrolling (task 217, panels.css).
  card.className = "sets-card card-split";
  card.innerHTML = `<h2>Notification voice</h2>
    <p class="sets-sub">How THIS device reads a notice out loud. Your other
       phone or tablet keeps its own answer — the PC only decides whether a
       notice is spoken at all.</p>`;

  const body = document.createElement("div");
  body.className = "sets-body";
  card.appendChild(body);

  // The pace first: it applies to every row below it, and to the previews.
  body.appendChild(segRow("Speaking pace", NOTIFY_RATES, NOTIFY_RATE_LABELS,
    notifyRatePref() || 1, (v) => {
      prefSet("notifyRate", String(v));
      renderNotifyVoiceCard();
    }));

  const list = document.createElement("div");
  list.className = "sets-list";
  // LANGUAGE FIRST, VOICE SECOND (owner 2026-08-13). The engine returns every
  // voice of every installed language in one run, which on his device is the
  // pile he reported — and every row wore its language word again, so the
  // same word ran down the whole column. `lang-groups.js` groups them and
  // names the rows inside a group; this card only decides what is on screen.
  const groups = groupVoicesByLanguage(voices);
  const open = groups.find((g) => g.key === voiceOpenLang) || null;

  if (open) {
    // Inside one language: a way back FIRST, then that language's voices.
    // The back row is a real button and the heading of what he is looking at,
    // so nothing else has to repeat the language name.
    list.appendChild(langBackRow(open.name, () => {
      voiceOpenLang = "";
      renderNotifyVoiceCard();
    }));
    for (const v of open.variants) {
      list.appendChild(voiceRow(v.row, chosen, v.label));
    }
  } else {
    // The no-choice row, first and always present, and never inside a
    // language — it is the absence of a choice, not a voice of one. Its label
    // is what it really means (this device has no opinion) and the caption
    // under the list spells out the consequence.
    list.appendChild(voiceRow({ name: "", label: "The phone's own default" },
                              chosen));
    for (const g of groups) {
      // A language with exactly ONE voice is offered flat — a drill-down into
      // a list of one is a tap that shows him nothing he could not already
      // see, and it would hide the only voice he has behind a door.
      if (g.variants.length === 1) {
        const only = g.variants[0];
        list.appendChild(voiceRow(only.row, chosen,
                                  `${g.name} — ${only.label}`));
      } else {
        const holdsChosen = !!chosen
          && g.variants.some((v) => String(v.row.name || "") === chosen);
        list.appendChild(langGroupRow(g, holdsChosen, () => {
          voiceOpenLang = g.key;
          renderNotifyVoiceCard();
        }));
      }
    }
  }
  body.appendChild(list);

  // THE HONEST LIMIT, said once and only when it is true — never a footnote
  // and never a per-row repetition (the dictation card's rule).
  const note = document.createElement("p");
  note.className = "sets-sub dict-note";
  if (!voices) {
    note.textContent = "The voices live on the phone itself, and this page is "
      + "open somewhere that has none to offer — open Vibe Coder on the phone "
      + "to choose one. Notices are still spoken there.";
  } else if (!voices.length) {
    note.textContent = "This device has no text-to-speech voice installed, so "
      + "there is nothing to choose between yet. A notice is still shown and "
      + "still tones.";
  } else if (!chosen) {
    note.textContent = "With no voice picked here, this device speaks in "
      + "whatever the PC last chose, and in its own engine default when the PC "
      + "chose nothing.";
  } else {
    note.textContent = "Chosen on this device. If it is ever missing — a "
      + "system update, a different engine — the phone falls back to its own "
      + "default rather than going quiet.";
  }
  body.appendChild(note);

  const done = document.createElement("button");
  done.type = "button";
  done.className = "sets-done";
  done.textContent = "Done";
  keepFocus(done, closeNotifyVoicePanel);
  card.appendChild(done);

  voicePanel.appendChild(card);
  voicePanel.hidden = false;
}

function openNotifyVoicePanel() {
  renderNotifyVoiceCard();
  voiceOpened.t = performance.now();
}

function closeNotifyVoicePanel() {
  voicePanel.hidden = true;
  voicePanel.innerHTML = "";
  clearTimeout(voiceSpeakingTimer);
  voiceSpeakingName = null;
  voiceOpenLang = "";      // next open starts at the list of languages
}

voicePanel.addEventListener("pointerdown", (e) => {
  if (e.target === voicePanel) closeNotifyVoicePanel();   // backdrop tap = done
});

// --- Settings → Notices: WHEN this phone listens (owner 2026-08-12) --------
//
// His words, in translation: *"You keep swinging between two extremes — one is
// that notifications arrive even when my app is closed, the other that they do
// not arrive even when my phone is locked. … I want an OPTION in settings
// where the user chooses whether notifications arrive ALWAYS, even when the
// app is shut down, or ONLY while the app is running in the background."*
//
// TWO STATES THAT KEPT BEING CONFUSED, and naming them apart IS the feature:
//   • the app RUNNING in the background — behind other apps, or with the phone
//     locked and the screen off. A notice must arrive in this state under BOTH
//     choices, always, and that is the case he actually reported as broken.
//   • the app CLOSED — swiped out of recents. This choice, and only this
//     choice, is about that state.
//
// The default is what 0.0.127 shipped this morning (his own rule of the same
// day): closing the app stops the channel, and the PC's queue holds whatever
// finishes for up to 30 minutes. A device that never opens this card behaves
// exactly as it did then — the pref is absent and `noticeMode()` answers
// "background".
//
// PER DEVICE, through the SharedPreferences bridge, never bare localStorage
// (keyed by ORIGIN, and the shell alternates between the LAN and Tailscale
// addresses — the "picker rotates" bug of 2026-08-05). Nothing about this rides
// the `config` frame: it is a fact about ONE handset's service, exactly like
// the voice above, and the service itself reads the same store this card writes
// (NoticeService.onTaskRemoved → Prefs.noticeAlways).

const noticeModePanel = document.createElement("div");
noticeModePanel.id = "notice-mode-panel";
noticeModePanel.hidden = true;
document.body.appendChild(noticeModePanel);
const noticeModeOpened = { t: 0 };
ghostClickArmor(noticeModePanel, noticeModeOpened);   // panels.js

const NOTICE_MODE_BACKGROUND = "background";
const NOTICE_MODE_ALWAYS = "always";

/** This device's answer. Anything that is not the explicit "always" — an
 *  unset pref, a corrupted one, an older store — is the safe, shipped
 *  behaviour, so the choice can only ever be widened by a deliberate tap. */
function noticeMode() {
  return prefGet("noticeWhen") === NOTICE_MODE_ALWAYS
    ? NOTICE_MODE_ALWAYS : NOTICE_MODE_BACKGROUND;
}

function setNoticeMode(mode) {
  prefSet("noticeWhen",
          mode === NOTICE_MODE_ALWAYS ? NOTICE_MODE_ALWAYS : NOTICE_MODE_BACKGROUND);
}

// The two choices, each a full row: a title he can act on and one plain line
// saying what it costs. A segmented strip could not hold either — these are
// sentences, not labels, and the whole complaint was that the short names for
// these two states read alike.
const NOTICE_MODES = [
  {
    value: NOTICE_MODE_BACKGROUND,
    title: "Only while the app is open in the background",
    detail: "Notices arrive while Vibe Coder is running behind other apps, "
      + "and while the phone is locked with the screen off. If you swipe the "
      + "app away out of recents they stop, and your PC holds them for up to "
      + "30 minutes — you get them the next time you open the app.",
  },
  {
    value: NOTICE_MODE_ALWAYS,
    title: "Always, even after I close the app",
    detail: "The phone keeps listening after you swipe Vibe Coder out of "
      + "recents, so a notice still reaches you with the app shut.",
  },
];

function noticeModeRow(mode, chosen) {
  const label = document.createElement("label");
  label.className = "sets-row dict" + (mode.value === chosen ? " sel" : "");
  const rb = document.createElement("input");
  rb.type = "radio";
  rb.name = "notice-mode";
  rb.checked = mode.value === chosen;
  rb.addEventListener("change", () => {
    setNoticeMode(mode.value);
    renderNoticeModeCard();          // the row re-lights, and the note follows
  });
  const txt = document.createElement("span");
  txt.className = "dict-name";
  txt.textContent = mode.title;
  const note = document.createElement("span");
  note.className = "dict-note";
  note.textContent = mode.detail;
  label.append(rb, txt, note);
  return label;
}

function renderNoticeModeCard() {
  const chosen = noticeMode();
  noticeModePanel.innerHTML = "";
  const card = document.createElement("div");
  card.className = "sets-card card-split";
  card.innerHTML = `<h2>Notices</h2>
    <p class="sets-sub">When this phone listens for your PC. Locking the phone
       is not closing the app — with Vibe Coder still running, a locked phone
       gets its notices either way. This choice is only about the app being
       swiped away.</p>`;

  const body = document.createElement("div");
  body.className = "sets-body";
  card.appendChild(body);

  const list = document.createElement("div");
  list.className = "sets-list";
  NOTICE_MODES.forEach((mode) => list.appendChild(noticeModeRow(mode, chosen)));
  body.appendChild(list);

  // THE HONEST LIMIT, in the card rather than in a comment nobody reads: the
  // waiting service does not come back by itself after the phone restarts, and
  // the word "Always" must not be allowed to promise that it does.
  const limit = document.createElement("p");
  limit.className = "sets-sub dict-note";
  limit.textContent = "After you restart the phone, notices start again only "
    + "once you have opened Vibe Coder one time — that is true of both "
    + "choices. Everything here is for this device alone; your other phone or "
    + "tablet keeps its own answer.";
  body.appendChild(limit);

  if (!IN_APP) {
    const browser = document.createElement("p");
    browser.className = "sets-sub dict-note";
    browser.textContent = "This page is open somewhere without the Vibe Coder "
      + "app, so there is no listening service here to set.";
    body.appendChild(browser);
  }

  const done = document.createElement("button");
  done.type = "button";
  done.className = "sets-done";
  done.textContent = "Done";
  keepFocus(done, closeNoticeModePanel);
  card.appendChild(done);

  noticeModePanel.appendChild(card);
  noticeModePanel.hidden = false;
}

function openNoticeModePanel() {
  renderNoticeModeCard();
  noticeModeOpened.t = performance.now();
}

function closeNoticeModePanel() {
  noticeModePanel.hidden = true;
  noticeModePanel.innerHTML = "";
}

noticeModePanel.addEventListener("pointerdown", (e) => {
  if (e.target === noticeModePanel) closeNoticeModePanel();  // backdrop = done
});
