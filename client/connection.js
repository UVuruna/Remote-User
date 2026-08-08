// WebSocket connection lifecycle: connect/reconnect, the `config`/`cursor`/
// `actions`/`toast` message handlers, visibility-gated session, and the
// initial connect() call. Loads LAST — this is where the page actually
// starts running. Part of the app.js split. See client/__about/connection.md.
"use strict";

// --- Connection -----------------------------------------------------------

// --- Proof of life --------------------------------------------------------
// How many connections in a row ended without ever being SERVED. Reset by the
// first `config` — the one message that proves the server on the other end is
// really serving US (see LINK_LOST_TRIES in state.js).
let deadTries = 0;

/** One connection is over and it was never served. Three of these in a row
 *  mean the address itself is wrong for where this phone now is — which the
 *  page cannot fix, because the page owns only the address it was loaded from
 *  (`location.host`). The shell owns both stored addresses, so the shell is
 *  asked. That is the whole difference between recovering and needing to be
 *  killed (owner report 2026-08-07).
 *
 *  Asking costs nothing when the address is fine: the shell re-probes, finds
 *  the current one still alive, and leaves this document exactly where it is
 *  (MainActivity.resolveAndLoad's `sessionHealthy`). */
function noteDeadConnection() {
  deadTries += 1;
  if (deadTries < LINK_LOST_TRIES) return;
  deadTries = 0;
  if (IN_APP && window.Android.linkLost) {
    try { window.Android.linkLost(); } catch (e) { /* older shell */ }
  }
}

/** Abandon a connection that is going nowhere and try again at once.
 *  `why` reaches the status pill, because a phone that quietly gives up while
 *  showing "Connected" is half the complaint. */
function abandon(sock, why) {
  if (sock !== ws) return;          // already replaced — nothing to abandon
  ws = null;                        // so ensureConnected does not skip it
  try { sock.close(); } catch (e) { /* already gone */ }
  setStatus("connecting", why);
  noteDeadConnection();
  ensureConnected();
}

function connect() {
  setStatus("connecting", `Connecting to ${location.host}…`);
  // Every handler guards on `sock === ws`: instant reconnect can replace the
  // global while an abandoned socket is still CLOSING, and its late onclose
  // must never tear down the NEW connection's MSE pipeline or status.
  const sock = new WebSocket(`ws://${location.host}/ws`);
  ws = sock;
  sock.binaryType = "arraybuffer";
  // Two deadlines, because a socket can die in two silent ways (state.js).
  // Cleared the moment each one is answered.
  let openTimer = setTimeout(
    () => abandon(sock, "No route to the PC — retrying…"), CONNECT_TIMEOUT_MS);
  let servedTimer = null;
  // Was this connection ever answered? A link that flaps — opening and
  // dropping every couple of seconds on a weak mobile signal — never reaches
  // either deadline, so the count has to be kept here as well or the shell is
  // never asked and the page retries the dead address all evening.
  let served = false;

  sock.onopen = () => {
    clearTimeout(openTimer);
    if (sock !== ws) return;
    // Opened, but not yet SERVED. Everything below is a message into a socket
    // whose other end we have not heard from once.
    servedTimer = setTimeout(
      () => abandon(sock, "The PC is not answering — retrying…"), SERVED_TIMEOUT_MS);
    // `screen` feeds layout placement: the server sizes layout windows to
    // this device's aspect (tablet vs phone — owner 2026-08-02).
    sock.send(JSON.stringify({
      type: "auth", token,
      screen: { w: window.screen.width, h: window.screen.height },
    }));
    // The server starts every connection at default quality — restate the
    // saved overrides (a network switch reconnects, so auto-on-mobile-data
    // re-evaluates here too).
    // Nothing may reach the server before `auth` — the handler rejects the
    // whole connection if the first message is anything else. The heartbeat
    // and the `away` word therefore wait for this flag, never for readyState
    // alone (a timer task can run between the socket opening and this
    // handler).
    sock.authSent = true;
    // What THIS phone can speak with, once per connection (owner round R2).
    // The PC cannot enumerate another device's text-to-speech engine, so the
    // desktop Settings window's Voice dropdown has exactly one source: us.
    sendTtsInfo();
    // The one step Android will not let the app take for itself (owner decree
    // 2026-08-07): the notice service may only reach him with the app closed
    // if this phone stops deferring it. Explained on the page, granted in a
    // system dialog — and offered at most once per app version.
    offerNoticeSetup();
    if (qualityOverridden()) sendQuality();
    lastSentViewport = { x: 0, y: 0, w: 1, h: 1 };
    scheduleViewport();
    setStatus("connected", "Connected");
  };

  sock.onmessage = (e) => {
    if (sock !== ws) return;
    // PROOF OF LIFE, and it is the FIRST message of any kind — not `config`
    // specifically. Anything at all arriving here proves this address reaches
    // a PC that is serving US, which is the only question `deadTries` asks.
    // Waiting for `config` would have been wrong twice over: in H.264 mode it
    // comes only after ffmpeg has started (measured 1.3 s on his own machine,
    // and a cold DERP relay is slower), so a working session could be
    // abandoned for being slow — while the failure this defends against sends
    // nothing whatsoever, `actions` included.
    if (!served) {
      served = true;
      clearTimeout(servedTimer);
      deadTries = 0;
    }
    if (typeof e.data === "string") {
      const msg = JSON.parse(e.data);
      if (msg.type === "config") {
        // Full view reset — sent after auth and after every stream (re)start
        // (monitor switch, H.264 session reset).
        monitor = { w: msg.monitor_width, h: msg.monitor_height };
        const newMode = msg.stream || "jpeg";
        if (newMode !== streamMode) showToast(newMode === "h264" ? "H.264 stream" : "JPEG stream");
        streamMode = newMode;
        tailscaleUrl = msg.tailscale_url || null;
        if (IN_APP && window.Android.setTailscaleUrl) {
          // The shell stores the works-anywhere address (fresh token included)
          // and probes it on every start — the app then connects on mobile
          // data too, not only on the home Wi-Fi.
          window.Android.setTailscaleUrl(tailscaleUrl || "");
        }
        updateAnywhereBanner();
        refreshUpdateBanner(msg.apk_version || msg.app_version);
        // The PC's own quality settings — the quality panel can only go BELOW
        // them, so it shows them and greys out the unreachable steps.
        setStreamBase(msg.base || null);
        // How this phone should LOOK, decided on the DESKTOP (build round R3,
        // owner answer P4). Applied straight to CSS variables — the page
        // never asks the device and offers no menu of its own.
        //
        // `msg.ui` is handed over EXACTLY as it arrived, absence included: a
        // frame that says nothing about appearance must change nothing
        // (independent grader, 2026-08-07 — this line and theme.js's old
        // UI_DEFAULT fallback were the two halves of "the Filled choice does
        // nothing"). The decision of what silence means belongs in theme.js,
        // with the look itself and with the cache that remembers it, not here
        // in a `||` that turns "no opinion" into "dark, outlined".
        applyUi(msg.ui);
        refreshQualityButtons();
        detailRegion = { x: 0, y: 0, w: 1, h: 1 };
        if (baseBitmap) { baseBitmap.close(); baseBitmap = null; }
        if (detailBitmap) { detailBitmap.close(); detailBitmap = null; }
        lastSentViewport = { x: 0, y: 0, w: 1, h: 1 };
        cursorPos = null;
        if (streamMode === "h264") initMse(msg.codec);
        else teardownMse();
        computeBaseRect();
        resetViewHome(); // a stream reset must not drop the focused region
        redraw();
        scheduleViewport();
      } else if (msg.type === "cursor") {
        cursorPos = { x: msg.x, y: msg.y };
        if (streamMode !== "h264") redraw(); // h264 redraws every rAF anyway
      } else if (msg.type === "actions") {
        categories = msg.categories || [];
        appSets = msg.app_sets || [];
        customSets = msg.custom_sets || [];
        // Wheel order (owner build round R5, 2026-08-07): the desktop
        // Controls editor's "Wheel order…" list, a list of set NAMES —
        // client/sets.js sorts by it; missing/empty = today's order,
        // unchanged (a user who never opens the new list sees no change).
        wheelOrder = msg.wheel_order || [];
        // HIS CHOICE FIRST, the desktop default only when there is none
        // (owner 2026-08-08 — every excursion used to put the wheel back to
        // Mouse/Input). Resolved against the list that will actually ride,
        // by NAME: see sets.js -> restoredGroup.
        const riding = allCats();
        groups.left = restoredGroup("left", msg.left ?? 0, riding);
        groups.right = restoredGroup("right", msg.right ?? 0, riding);
        // The cap of 8 is a LAW over the STORED state too (owner 2026-08-06):
        // prefs saved before app sets started charging, and desktop defaults
        // that never asked, both used to sail past a check that only ran on a
        // tap — nine ticked, eight shown. Normalize here, where the sets are
        // finally known, and SAY what had to give way.
        const dropped = enforceWheelCap();
        if (dropped.length) {
          showToast(`The wheel holds ${WHEEL_MAX} sets — switched off ${dropped.join(", ")}`);
        }
        refreshCategories();
      } else if (msg.type === "toast") {
        showToast(msg.text);
      } else if (msg.type === "notify") {
        // A job on the PC finished and named itself (ROADMAP Phase H,
        // owner 2026-08-05) — the phone raises a real notification
        // with the AGENT's name, speaks it, and toasts if visible.
        handleNotify(msg);
      } else if (msg.type === "layout_state") {
        // The server is done — but the PC is not: windows are still restoring
        // and sliding into place. The loading animation stays up until the
        // STREAM stops moving (owner 2026-08-03).
        settleLayLoading();
        layouts = msg.layouts || [];
        layoutActive = msg.active ?? null;
        layoutRegion = msg.region || null;
        if (layoutActive === null && layoutRestore &&
            layouts[layoutRestore.index] &&
            layouts[layoutRestore.index].name === layoutRestore.name) {
          // The server says desktop but nobody CHOSE the desktop — this is a
          // fresh connection after an excursion (gallery, permission dialog:
          // the page hid, the socket closed, per-connection focus reset).
          // Go back into the layout the owner was working in (owner
          // 2026-08-04). One shot: the reply's layout_state re-arms it.
          const back = layoutRestore.index;
          layoutRestore = null;
          send({ type: "layout_focus", index: back });
        } else if (layoutActive !== null && layouts[layoutActive]) {
          layoutRestore = { index: layoutActive, name: layouts[layoutActive].name };
        }
        refreshCategories(); // app-aware sets appear/vanish with layout focus
        updateLayoutBar();
        applyOrientationLock();
        resetViewHome(); // every layout change starts fully zoomed out again
        scheduleViewport();
      } else if (msg.type === "layout_offer") {
        handleLayoutOffer(msg);
      } else if (msg.type === "layout_progress") {
        cubeNext(); // one window created on the PC = one cube turn
      }
    } else if (streamMode === "h264") {
      mseQueue.push(e.data);
      pumpMse();
    } else {
      onFrame(e.data);
    }
  };

  sock.onclose = (e) => {
    clearTimeout(openTimer);
    clearTimeout(servedTimer);
    if (sock !== ws) return; // an abandoned socket must not touch the live one
    teardownMse(); // free the decoder; reconnect starts a fresh stream
    if (e.code === 4401) {
      // The token is refused — retrying with the same one only hammers the
      // server and stomps this message every 2 s. Stop until re-paired.
      authRejected = true;
      layoutRestore = null;   // a dead link decides nothing about the layout
      if (IN_APP) {
        // In the APK the fix is one tap — the shell reopens the QR scanner.
        setStatus("disconnected", "Link expired — tap here to scan the new QR");
        // pointerup, not click: the pill sits at the top edge where the
        // system's bar-peek swipe can eat the click's touch sequence.
        statusEl.addEventListener("pointerup", () => window.Android.rescan(), { once: true });
        return;
      }
      setStatus("disconnected", "Invalid token — scan the fresh QR on the PC");
      return;
    }
    if (e.code === 4409) {
      // Another device opened the app — one device at a time (owner
      // 2026-08-02). No auto-reconnect: that would steal the session back
      // in a loop. A deliberate tap takes over again.
      takenOver = true;
      // This page is no longer the authority on what the session should show,
      // so it must not silently re-raise "its" layout on some later reconnect
      // and override whatever the other device chose (audit 2026-08-05).
      layoutRestore = null;
      setStatus("disconnected", "Another device took over — tap here to use this one");
      statusEl.addEventListener("pointerup", () => {
        takenOver = false;
        ensureConnected();
      }, { once: true });
      return;
    }
    setStatus(
      "disconnected",
      document.hidden ? "Paused — screen away" : `Disconnected (code ${e.code}) — retrying…`
    );
    // A connection that never carried a `config` was never a connection. On a
    // flapping link these arrive in a run, and the run is the signal that this
    // address no longer reaches the PC. 4401/4409 returned above: those are
    // answers from a server we CAN hear, and they must never be read as a lost
    // route — the shell would re-probe an address that is working perfectly.
    if (!served && !document.hidden) noteDeadConnection();
  };
}

let authRejected = false;
let takenOver = false;

function ensureConnected() {
  if (document.hidden || authRejected || takenOver) return;
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  connect();
}

// The heartbeat IS how the PC knows we are still working (owner 2026-08-05).
// Layout windows are always-on-top while we watch them, so the moment this
// beat stops — screen locked, app closed, killed, network gone — the server
// hands those windows back to the desk and minimizes them. A page that is
// merely paused stops beating all by itself, which is exactly the point.
function socketReady() {
  return ws && ws.readyState === WebSocket.OPEN && ws.authSent;
}

setInterval(() => {
  if (!socketReady() || document.hidden) return;
  // The beat carries the phone's own traffic counters (Android TrafficStats).
  // The PC's Traffic window subtracts the reading before an absence from the
  // one after it, which is the only measurement that can answer "did the app
  // keep running while the screen was off" without either of us guessing
  // (owner 2026-08-05).
  const net = phoneNet();
  ws.send(JSON.stringify(net ? { type: "hb", net } : { type: "hb" }));
}, HEARTBEAT_MS);

// The screen is held awake while the owner is actually working, and released
// after KEEP_AWAKE_MS of no touch — the shell used to hold it forever, so the
// tablet never slept on its own, never sent the leave signal, and burned
// battery showing a stream nobody was looking at (audit 2026-08-05).
let awakeUntil = 0;
function touchedNow() {
  awakeUntil = performance.now() + KEEP_AWAKE_MS;
  if (IN_APP && window.Android.keepAwake) window.Android.keepAwake(true);
}
window.addEventListener("pointerdown", touchedNow, true);
window.addEventListener("keydown", touchedNow, true);
setInterval(() => {
  if (!awakeUntil || performance.now() < awakeUntil) return;
  awakeUntil = 0;
  if (IN_APP && window.Android.keepAwake) window.Android.keepAwake(false);
}, 5000);
touchedNow();

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    // The LOCK button stops EVERYTHING that was switched ON (owner round 4,
    // 2026-08-05): mic and keyboard go OFF the moment the screen goes away —
    // the shell cancels its listening round too (belt and braces).
    inputOff();
    if (socketReady()) {
      // Say WHY we are going, in the words of whoever actually knows —
      // hideReason() asks the shell first (screen off / keyguard / its own
      // picker) and only falls back to our timer in a dev browser. An
      // excursion means the owner is still working with us and the PC holds
      // the layout; ANYTHING else, above all a lock, hands his windows back
      // at once. Getting this word wrong is the whole 2026-08-05 failure.
      const reason = hideReason();
      const net = phoneNet();
      const bye = { type: "away", reason, excursion: reason === "excursion" };
      if (net) bye.net = net;
      ws.send(JSON.stringify(bye));
    }
    if (ws) ws.close();
  } else {
    // Reconnect the moment the user comes back (app switch, image picker,
    // screen unlock) — waiting out the retry interval swallowed the first
    // taps and read as "input randomly dies".
    ensureConnected();
  }
});
window.addEventListener("pageshow", ensureConnected);

setInterval(ensureConnected, RECONNECT_MS);

// ensureConnected, NOT connect (audit 2026-08-05): every other entry point
// checks document.hidden, and this one did not. The shell can load the page
// while the activity is paused (a network event fires its resolver), and an
// unguarded connect there opened a full 4K stream to a pocketed phone AND
// re-raised the owner's layout windows on top of his desk. If the page really
// is visible, this connects immediately, exactly as before.
ensureConnected();
