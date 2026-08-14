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

// --- THE RETURN STOPWATCH (task 203) ---------------------------------------
// "Coming back from the gallery takes about a minute" cannot be fixed by
// guessing which hop is slow, and only ONE of the hops is visible in the
// server's log (it cannot see the seconds before the socket exists, nor the
// ones after the last byte, which is exactly where the overlay lives). So the
// page times its own return and reports it ONCE per return, as a `client_log`
// line into the server log beside everything else — never a panel on the
// phone (the 2026-08-05 rule: diagnostics go to the log, the owner sees a
// working app or a named failure, never a debug toast).
//
// The marks, in order: `hidden` (the page came back), `open` (the socket
// opened), `served` (the PC answered anything at all), `config` (the encoder
// exists — this is the first-picture moment, since `config` carries the codec
// parsed from the live init segment) and `cube` (the loading overlay left,
// with the reason it left). Each is milliseconds since the return itself.
const RETURN = { t0: 0, marks: [], sent: true };

function markReturn(name) {
  if (RETURN.sent) return;
  RETURN.marks.push(`${name}=${Math.round(performance.now() - RETURN.t0)}ms`);
}

/** Called by loading.js when the overlay finally leaves — the last hop, and
 *  the one the owner actually watches. `why` distinguishes "the picture stood
 *  still" from "we gave up waiting", which are different bugs. */
function noteReturnDone(why) {
  if (RETURN.sent) return;
  markReturn("cube");
  RETURN.sent = true;
  send({ type: "client_log", text: `[return] ${RETURN.marks.join(" ")} (${why})` });
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
    markReturn("open");
    // Opened, but not yet SERVED. Everything below is a message into a socket
    // whose other end we have not heard from once.
    servedTimer = setTimeout(
      () => abandon(sock, "The PC is not answering — retrying…"), SERVED_TIMEOUT_MS);
    // `screen` feeds layout placement: the server sizes layout windows to
    // this device's aspect (tablet vs phone — owner 2026-08-02).
    sock.send(JSON.stringify({
      type: "auth", token,
      // `model` (owner request 2026-08-13 — the Traffic window's per-device
      // list) reuses dictation-card.js's OWN UA-model arithmetic verbatim
      // rather than inventing a second one: same synchronous best-effort
      // read, same "no bridge method" reasoning (the page is served by the
      // PC, the shell installed separately), same honest "" when nothing
      // readable is found — never a guess. dictation-card.js loads before
      // this file (index.html), so `dictModelFromUa` is already defined.
      screen: { w: window.screen.width, h: window.screen.height,
                model: (typeof dictModelFromUa === "function") ? dictModelFromUa() : "" },
      // …and `panel` is the pixel BUDGET (owner order 2026-08-12): the real
      // panel pixels, CSS px x devicePixelRatio, which is what the PC's
      // encoder may never exceed. A NEW field rather than a new meaning for
      // `screen` — those are CSS px and an older PC reads them as an aspect;
      // silently changing what they say would be unreadable in both
      // directions. A PC that does not know the field ignores it and streams
      // exactly as before. Null (no screen object) sends nothing at all.
      panel: devicePanel(),
      // THIS DEVICE'S QUALITY OVERRIDES, IN THE FIRST MESSAGE (task 203).
      // The restatement below still goes — an older PC only understands that
      // one — but a PC that reads this opens its FIRST encoder already
      // correct. Sent before, it arrived after the whole connection setup,
      // so every return from an excursion built one ffmpeg at default
      // quality, tore it down and built a second (his log 10:08:08,773 →
      // 08,864 → 10,086 — 1.31 s of nothing, on top of everything else).
      quality: effectiveQuality(),
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
    // Whatever typing the outage queued (client/type-queue.js) goes out NOW —
    // after `auth`, never before it (nothing may reach the server first).
    flushTypeQueue();
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
      markReturn("served");
    }
    if (typeof e.data === "string") {
      const msg = JSON.parse(e.data);
      if (msg.type === "config") {
        markReturn("config"); // the encoder exists — the first picture is due
        // Full view reset — sent after auth and after every stream (re)start
        // (monitor switch, H.264 session reset).
        // IS THIS THE SAME SCREEN WE ARE ALREADY SHOWING? Asked BEFORE
        // `monitor` is overwritten, because the answer decides whether the
        // canvas keeps its last frame across the swap (render.js `initMse`,
        // 2026-08-12). A quality change and a layout region change both come
        // down this branch on the same monitor and both rebuild the encoder
        // for 1.2–2.3 s — that used to be a blank, flat-coloured screen with
        // nothing on the page to explain it. A monitor switch or a fresh
        // connection is a different picture and clears as it always did.
        const samePicture = streamMode === "h264" && everDrew
          && monitor.w === msg.monitor_width && monitor.h === msg.monitor_height
          && monitorIndex === (Number.isInteger(msg.monitor) ? msg.monitor : 0);
        monitor = { w: msg.monitor_width, h: msg.monitor_height };
        // THE MONITORS, AND WHICH ONE THIS IS (owner 2026-08-09, task 155).
        // Optional fields on a message that already exists: a server that does
        // not send them leaves the list empty, and the layout list falls back
        // to the single Desktop row it has always drawn. Read here rather than
        // asked for, because `config` is re-sent after EVERY stream restart —
        // a monitor switch included — so the phone's idea of which screen it is
        // looking at is refreshed by the very event that changes it.
        monitorList = Array.isArray(msg.monitors) ? msg.monitors : [];
        monitorIndex = Number.isInteger(msg.monitor) ? msg.monitor : 0;
        const newMode = msg.stream || "jpeg";
        if (newMode !== streamMode) showToast(newMode === "h264" ? "H.264 stream" : "JPEG stream");
        streamMode = newMode;
        // What this stream COVERS (owner order 2026-08-12): the encoder crops
        // to the focused layout, and this rect is where the video lands on
        // the monitor space. Absent/old server = full frame, unchanged.
        streamRegion = msg.stream_region || null;
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
        // …and what THIS device can decode of them (owner report 2026-08-12:
        // 4K@60 drowned the tablet's decoder and read as "no picture"). Async
        // and self-de-duplicating per PC shape; restates quality by itself if
        // the running stream turns out to be above the device's ceiling.
        if (streamMode === "h264") refreshDecodeCeilings();
        // A region change moves the decode ceiling's goalposts (a cropped
        // stream is a fraction of the width): if the effective quality now
        // differs from what the server holds for this connection, restate it
        // — the server re-applies the STORED value to every new session, so
        // a cap computed for the full desktop would otherwise outlive the
        // desktop and hold a small, easy layout stream at the capped fps.
        restateQualityIfChanged();
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
        if (streamMode === "h264") initMse(msg.codec, samePicture);
        else teardownMse();
        // The stream this page is judging has just been replaced — the settle
        // watcher must judge the NEW one's first decoded frame, never the
        // frozen gap between the two (client/loading.js).
        settleStreamReset();
        computeBaseRect();
        // A CONFIG THAT ECHOES OUR OWN ZOOM MUST NOT UNDO IT (T76 round 2,
        // owner report 2026-08-14, in translation: "zoom does not work at
        // all any more because it keeps throwing me back"). Every zoom-crop
        // rebuild ends here with a fresh `config`, and this branch used to
        // resetViewHome() + scheduleViewport() unconditionally — a
        // self-erasing loop: the reset snapped the view fully out AND
        // dropped `lastSentZoom`, the re-armed settle watcher then measured
        // that reset view as "he is looking at the whole frame" and sent it,
        // and the server obediently undid the very zoom it had just applied.
        // The zoom therefore never survived one second and the sharper crop
        // was never seen. A `stream_region` that is (within the wire's own
        // ZOOM_MIN_DELTA) the rect this page itself asked for changes the
        // picture's SHARPNESS, never his framing: keep the pinch exactly
        // where his fingers left it and tell the server nothing.
        const zoomEcho = streamMode === "h264" && lastSentZoom && streamRegion &&
          zoomRectDelta(lastSentZoom, streamRegion) < ZOOM_MIN_DELTA;
        if (zoomEcho) {
          computeViewHome();
          clampView();
          redraw();
        } else {
          resetViewHome(); // a stream reset must not drop the focused region
          redraw();
          scheduleViewport();
        }
      } else if (msg.type === "cursor") {
        cursorPos = { x: msg.x, y: msg.y };
        // `shape` is OPTIONAL (owner request 2026-08-09, task 142): the name
        // of the system cursor the PC is really showing, so the page can draw
        // a resize arrow at a window edge instead of one eternal arrow. A
        // server that predates it, or a moment the PC cannot read the cursor
        // at all, sends nothing here — and `undefined` is exactly what
        // cursor-shapes.js reads as "draw the arrow", never a guessed shape.
        // It is kept BESIDE cursorPos, not on it: the finger's own optimistic
        // moves (gestures.js, input-geometry.js) rebuild that object without
        // a shape, and the pointer must not flick back to an arrow every time
        // he drags along the very edge he is trying to grab.
        cursorShapeName = msg.shape;
        // THE CURSOR IS ITS OWN REASON TO REPAINT (2026-08-14). This used to
        // skip the redraw in h264 and lean on "h264 redraws every rAF anyway"
        // — which stopped being true the moment the render loop began drawing
        // on FRAME ARRIVAL instead of on every panel blink. Without this the
        // PC-side pointer would move only as often as the video does, so at
        // 10 fps the cursor would step ten times a second. `scheduleRedraw`
        // coalesces it to at most one paint per animation frame, so a moving
        // cursor is smooth and a still one costs nothing at all.
        scheduleRedraw();
      } else if (msg.type === "claude_state") {
        // What Claude Code is running RIGHT NOW (owner verdict 2026-08-11,
        // item 3) — asked for by the Model/Thinking/Mode panels and answered
        // only by a PC new enough to read the live conversation. A server
        // that never sends this is the ordinary case, not an error: the
        // panels are drawn with "unknown" chips and simply stay that way
        // (client/claude-state.js).
        onClaudeState(msg);
      } else if (msg.type === "actions") {
        categories = msg.categories || [];
        appSets = msg.app_sets || [];
        customSets = msg.custom_sets || [];
        // Wheel order (owner build round R5, 2026-08-07): the desktop
        // Controls editor's "Wheel order…" list, a list of set NAMES —
        // client/sets.js sorts by it; missing/empty = today's order,
        // unchanged (a user who never opens the new list sees no change).
        wheelOrder = msg.wheel_order || [];
        // Drop-out vs fixed wheel (owner decree 2026-08-11, task 181): a
        // set placed on either D-pad group sheds off BOTH wheels while it
        // rides there, and the wheel cap rises to 10 — the desktop's
        // "Wheel mode" control, beside "Wheel order…"; default drop-out.
        // Missing key = an older server or a fresh file — also drop-out.
        setWheelMode(msg.wheel_mode);
        // What Claude Code is SAVED as — the chooser marks it, and says
        // "saved" rather than "active" because it can be outranked by a
        // project settings file, an env var, a session-only switch or a
        // resumed transcript (server/agents.py -> claude_settings).
        claudeSaved = msg.saved || {};
        // HIS CHOICE FIRST, the desktop default only when there is none
        // (owner 2026-08-08 — every excursion used to put the wheel back to
        // Mouse/Input). Resolved against the list that will actually ride,
        // by NAME: see sets.js -> restoredGroup.
        const riding = allCats();
        // These two are still resolved independently — one side's remembered
        // set says nothing about the other's — and both prefs CAN name the
        // same set. `refreshCategories()` below runs `settleGroups()`, which
        // is where the no-duplicate invariant is kept (sets.js); this must
        // stay downstream of it, never the last word.
        groups.left = restoredGroup("left", msg.left ?? 0, riding);
        groups.right = restoredGroup("right", msg.right ?? 0, riding);
        // The cap of 8 is a LAW over the STORED state too (owner 2026-08-06):
        // prefs saved before app sets started charging, and desktop defaults
        // that never asked, both used to sail past a check that only ran on a
        // tap — nine ticked, eight shown. Normalize here, where the sets are
        // finally known, and SAY what had to give way.
        const dropped = enforceWheelCap();
        if (dropped.length) {
          showToast(`The wheel holds ${wheelCap()} sets — switched off ${dropped.join(", ")}`);
        }
        refreshCategories();
      } else if (msg.type === "caret") {
        // The PC found the typing caret, or said honestly that it could not.
        // `known:false` becomes null so the rule can tell that apart from a
        // caret at the top-left corner (server/caret.py -> unknown()).
        pcCaret = msg.known ? { x: msg.x, y: msg.y, w: msg.w, h: msg.h } : null;
        updateViewport();
      } else if (msg.type === "toast") {
        showToast(msg.text);
      } else if (msg.type === "clipboard") {
        // task 182 — hand it to the shell (client/clipboard.js).
        handleClipboardPush(msg.text);
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
        // WHAT THIS FRAME CHANGED decides what happens to the view below
        // (T76 round 2, the SECOND path of the same self-erasing loop — the
        // adversarial verify of the config-echo fix found it): the server's
        // zoom_region re-sends layout_state through the same choke point
        // BEFORE the encoder rebuild, so a frame that changed neither the
        // focus nor the region is the zoom's own echo (or a rename/reorder),
        // never a layout change — and resetting the view on it erased every
        // zoom a second way, unconditionally, on every single pinch.
        const prevFull = { x: 0, y: 0, w: 1, h: 1 };
        const focusUnchanged =
          (msg.active ?? null) === layoutActive &&
          zoomRectDelta(msg.region || prevFull, layoutRegion || prevFull) < 1e-6;
        layouts = msg.layouts || [];
        layoutActive = msg.active ?? null;
        layoutRegion = msg.region || null;
        // A NOTIFICATION TAP OUTRANKS THE AUTO-RESTORE (task 110). Both want
        // to choose a layout on a fresh connection, and only one of them is
        // something the owner just did with his thumb.
        if (applyNoticeJump()) {
          layoutRestore = null;
          orientationRestoring = false;
        } else if (layoutActive === null && msg.resuming !== undefined &&
                   msg.resuming !== null) {
          // THE SERVER IS ALREADY DOING IT (2026-08-12). This interim frame
          // says desktop, which is the restore branch's own trigger — but the
          // PC has read its remembered index and is placing those windows
          // right now, so asking for the same focus a round trip later is one
          // user switch done twice: two placement passes, two more state
          // frames, and a second encoder rebuild inside the loading overlay he
          // is watching. So: no send. Everything else the restore branch does
          // still has to happen, because the same seconds are still passing —
          // the rotation lock holds through them (task 204) and the overlay
          // re-arms so the watcher judges the REAL move's frame and not this
          // idle one (task 194). `layoutRestore` is left standing: if the
          // server's resume finds the window gone, its own next frame carries
          // neither `active` nor `resuming` and the final `else` clears it.
          orientationRestoring = true;
          // LOADING: FULL — the PC is re-focusing the layout — windows move
          showLayLoading("Back to your layout…", LOADING_FULL);
        } else if (layoutActive === null && layoutRestore &&
            layouts[layoutRestore.index] &&
            layouts[layoutRestore.index].name === layoutRestore.name) {
          // The server says desktop but nobody CHOSE the desktop — this is a
          // fresh connection after an excursion (gallery, permission dialog:
          // the page hid, the socket closed, per-connection focus reset).
          // Go back into the layout the owner was working in (owner
          // 2026-08-04). One shot: the reply's layout_state re-arms it.
          const back = layoutRestore.index;
          layoutRestore = null;
          // TASK 204: this INTERIM layout_state still says desktop —
          // applyOrientationLock() runs a few lines below and would read
          // that as "unlock rotation", clearing the lock for the seconds
          // this restore takes and letting the tablet spin sideways over a
          // portrait layout. orientationRestoring holds the lock through
          // this window; the restore's own later layout_state (landing
          // below with layoutActive set) clears it again, and a restore
          // that fails to verify next time falls to the final `else`,
          // which also clears it — a failed restore must not hold the lock
          // forever.
          orientationRestoring = true;
          send({ type: "layout_focus", index: back });
          // TASK 194 (the overlay "misses places it should cover"). This
          // `layout_state` is the INTERIM one — the server still shows
          // desktop, and `settleLayLoading()` a few lines above just armed
          // the watcher against THIS frame. Left alone, the watcher can
          // declare the (idle, unrelated) current picture "settled" and
          // hide the cube before the layout_focus above has moved a single
          // window — the real move's OWN later layout_state then finds
          // `layLoadingOpen` already false and settleLayLoading() is a no-op
          // (see its guard), so he watched the actual restore bare. Calling
          // showLayLoading() again re-arms a fresh cycle (it clears any
          // settle timer already ticking) that only the real move's
          // layout_state can satisfy — the same re-arm the visibilitychange
          // handler below already relies on for the sibling case.
          // LOADING: FULL — same re-focus, the retry arm — windows move
          showLayLoading("Back to your layout…", LOADING_FULL);
        } else if (layoutActive !== null && layouts[layoutActive]) {
          layoutRestore = { index: layoutActive, name: layouts[layoutActive].name };
          // A real focus landed (the restore's own reply, or an ordinary
          // layout_focus) — nothing left to wait for.
          orientationRestoring = false;
        } else {
          // Genuine desktop with no restore in flight, OR a restore that
          // failed to verify (the remembered layout is gone/renamed) — the
          // TASK 204 hold has nothing more to wait for either way, so the
          // lock is free to release on the line below.
          layoutRestore = null;
          orientationRestoring = false;
        }
        refreshCategories(); // app-aware sets appear/vanish with layout focus
        updateLayoutBar();
        applyOrientationLock();
        if (focusUnchanged) {
          // The same focus, the same region — the picture he framed is still
          // the picture: keep the pinch, drop nothing, re-arm no watcher.
          // The home is still re-derived (a `pos` change rides these frames)
          // and the clamp applies it the moment the view sits at home.
          computeBaseRect();
          computeViewHome();
          clampView();
          redraw();
        } else {
          resetViewHome(); // every layout CHANGE starts fully zoomed out again
          scheduleViewport();
        }
      } else if (msg.type === "window_offer") {
        // Something opened on the PC that belongs to this layout's work
        // (task 202). HE decides: show it in the layout, or leave it on the
        // desktop — the server moves nothing until he taps.
        showWindowOffer(msg);
      } else if (msg.type === "layout_offer") {
        // TASK 195 — the ⚙ sheet's "Add a window" reuses the same enumeration
        // (`layout_member_list`) and the same `layout_offer` shape, tagged
        // with `add_to` so it never falls into the fresh-creation flow
        // (`handleLayoutOffer`/`creating`) it shares nothing else with.
        // Routed here, additively, rather than inside handleLayoutOffer
        // itself — that function belongs to the creation wizard file.
        if (typeof msg.add_to === "number") {
          renderAddMemberPanel(msg);
        } else {
          // A tap always feeds the fresh-creation wizard now (owner
          // correction 2026-08-13) — `handleLayoutOffer` is where the
          // "already a member, nothing to create" refusal lives (a plain
          // `member_hwnds` check, no separate routing here).
          handleLayoutOffer(msg);
        }
      } else if (msg.type === "layout_progress") {
        cubeNext(); // one window created on the PC = one cube turn
      } else if (msg.type === "layout_acts") {
        // What the FOCUSED layout's own app can do (T29) — the group the New
        // panel draws ABOVE the standard list when it was opened from inside
        // a layout. Routed here like every other layout-panel reply; the
        // render lives in layout-create.js, which owns the wizard's panels.
        handleLayoutActs(msg);
      } else if (msg.type === "layout_recent") {
        // The Recent creation source's answer (task 228) — routed here like
        // every other layout-panel reply; the render itself lives in
        // layout-create.js, which owns the whole wizard's panels.
        handleLayoutRecent(msg);
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
      orientationRestoring = false; // nothing left for the lock to wait for
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
      orientationRestoring = false; // ditto — a takeover decides nothing here either
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
  // ...and, since T80d (owner 2026-08-14), what the phone's own battery is
  // doing WHILE THE APP IS RUNNING — which is the cost he actually cares
  // about. It rides the EXISTING beat exactly as `net` does rather than
  // inventing a message type, and it is absent whenever the device will not
  // say.
  const net = phoneNet();
  const bat = phoneBattery();
  const beat = { type: "hb" };
  if (net) beat.net = net;
  if (bat) beat.bat = bat;
  ws.send(JSON.stringify(beat));
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
      const bat = phoneBattery();
      const bye = { type: "away", reason, excursion: reason === "excursion" };
      if (net) bye.net = net;
      // The LAST battery reading of the session (T80d) — the level here
      // against the one at connect is what "this session cost N%" is made of,
      // and a leave is the only moment that closing reading exists.
      if (bat) bye.bat = bat;
      ws.send(JSON.stringify(bye));
    }
    if (ws) ws.close();
  } else {
    // COVER THE SEAM (owner 2026-08-08, task 119). His question was whether
    // the flicker out of the layout and back is necessary when he attaches a
    // file — and it is: an Android picker is another app, the page hides, and
    // a hidden page closes the socket by rule (constraint 8). That is the
    // excursion path, not a bug.
    //
    // What was owed is his second sentence: cover it with the same loading
    // animation used everywhere else. The return is not instant — the socket
    // reconnects, `layout_state` arrives, the page re-focuses the layout it
    // was in, and the PC re-places real windows. He watched all of that bare.
    //
    // Only when a layout was actually being shown: coming back to the plain
    // desktop has no seam to cover, and a cube over nothing is worse than
    // nothing. `settleLayLoading` drops it when the streamed screen really
    // stands still, exactly as it does for every other layout switch.
    // The stopwatch starts HERE, at the moment he can see the page again —
    // not at connect(), which is already a hop in (task 203).
    // Only a return INTO A LAYOUT is timed: that is the seam the owner
    // reported, and it is the only one with an overlay to end the measurement.
    // Coming back to the plain desktop has nothing to cover and nothing to
    // report — `sent` stays true there, which makes every mark a no-op.
    if (layoutRestore) {
      RETURN.t0 = performance.now();
      RETURN.marks = [];
      RETURN.sent = false;
      // LOADING: FULL — returning from an excursion re-focuses the layout
      showLayLoading("Back to your layout…", LOADING_FULL);
    }
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
