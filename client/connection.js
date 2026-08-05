// WebSocket connection lifecycle: connect/reconnect, the `config`/`cursor`/
// `actions`/`toast` message handlers, visibility-gated session, and the
// initial connect() call. Loads LAST — this is where the page actually
// starts running. Part of the app.js split. See client/__about/connection.md.
"use strict";

// --- Connection -----------------------------------------------------------

function connect() {
  setStatus("connecting", `Connecting to ${location.host}…`);
  // Every handler guards on `sock === ws`: instant reconnect can replace the
  // global while an abandoned socket is still CLOSING, and its late onclose
  // must never tear down the NEW connection's MSE pipeline or status.
  const sock = new WebSocket(`ws://${location.host}/ws`);
  ws = sock;
  sock.binaryType = "arraybuffer";

  sock.onopen = () => {
    if (sock !== ws) return;
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
    if (qualityOverridden()) sendQuality();
    lastSentViewport = { x: 0, y: 0, w: 1, h: 1 };
    scheduleViewport();
    setStatus("connected", "Connected");
  };

  sock.onmessage = (e) => {
    if (sock !== ws) return;
    if (typeof e.data === "string") {
      const msg = JSON.parse(e.data);
      if (msg.type === "config") {
        // Full view reset — sent after auth and after every stream (re)start
        // (monitor switch, H.264 session reset).
        monitor = { w: msg.monitor_width, h: msg.monitor_height };
        // config.hand is ignored since 2026-08-02 — the cursor-offset system
        // (handedness diagonal) is gone; the pointer sits under the finger.
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
        groups.left = Math.min(msg.left ?? 0, categories.length - 1);
        groups.right = Math.min(msg.right ?? 0, categories.length - 1);
        refreshCategories();
      } else if (msg.type === "toast") {
        showToast(msg.text);
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
    if (sock !== ws) return; // an abandoned socket must not touch the live one
    teardownMse(); // free the decoder; reconnect starts a fresh stream
    if (e.code === 4401) {
      // The token is refused — retrying with the same one only hammers the
      // server and stomps this message every 2 s. Stop until re-paired.
      authRejected = true;
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
  if (socketReady() && !document.hidden) ws.send(JSON.stringify({ type: "hb" }));
}, HEARTBEAT_MS);

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    // The LOCK button stops EVERYTHING that was switched ON (owner round 4,
    // 2026-08-05): mic and keyboard go OFF the moment the screen goes away —
    // the shell cancels its listening round too (belt and braces).
    inputOff();
    if (socketReady()) {
      // Say WHY we are going: an excursion (image picker, camera, voice) is
      // the owner still working with us — the PC holds the layout as it is;
      // anything else is the end of the session and the desk gets its
      // windows back immediately instead of after the heartbeat runs out.
      ws.send(JSON.stringify({ type: "away", excursion: inExcursion() }));
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

connect();
