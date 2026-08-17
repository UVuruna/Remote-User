// --- In-app update (the PC carries the newer APK) --------------------------
// The phone never checks the internet for updates: `config.app_version` says
// what the PC runs, the bridge says what this shell is, and /app.apk on the
// SAME PC is the newer build (the desktop app updates itself from GitHub).
// Split out of controls.js (task 207, 2026-08-10) to keep that file under
// THE STRUCTURE LAW's 1,000-line ceiling — reads `IN_APP`, `keepFocus` and
// `showToast` as globals (plain scripts, no module system) and is called
// from connection.js's `config` handler.
//
// REWRITTEN 2026-08-17: the shell now downloads the APK ITSELF and reports
// real progress, instead of handing the URL to Android's opaque own
// DownloadManager. The bridge contract (fixed by the round that built the
// shell half — nothing here invents a name not on this list):
//
//   PAGE  -> SHELL   Android.updateInApp(url)          -> bool, took the job
//   PAGE  -> SHELL   Android.updateInstallAllowed()    -> bool
//   PAGE  -> SHELL   Android.updateAllowInstall()      -> opens the OS screen
//   SHELL -> PAGE    window.__updateProgress(received, total)  -- bytes;
//                    total <= 0 means the length is unknown
//   SHELL -> PAGE    window.__updateState(state, detail)       -- state is
//                    exactly "permission" | "downloading" | "installing" |
//                    "failed"; detail is a short plain sentence
//
// THERE IS NO "success" STATE, ANYWHERE, EVER. A successful install replaces
// this app's running process — Android tears it down to install the new
// APK over it — so the one outcome the user actually wants is structurally
// unable to reach this page. `installing` is the last state this file can
// ever render for a run that goes well; the app simply reopens on its own,
// on the new version, same as any other Android app update.
"use strict";

const updateBanner = document.getElementById("update-banner");
const updateBannerIcon = document.getElementById("update-banner-icon");
const updateBannerCube = document.getElementById("update-banner-cube");
const updateBannerText = document.getElementById("update-banner-text");
const updateBannerBar = document.getElementById("update-banner-bar");
const updateBannerFill = document.getElementById("update-banner-fill");
const updateBannerPct = document.getElementById("update-banner-pct");

function versionNumbers(v) {
  return (String(v).match(/\d+/g) || []).slice(0, 3).map(Number);
}

function isNewer(server, app) {
  const s = versionNumbers(server);
  const a = versionNumbers(app);
  if (!s.length || !a.length) return false;
  for (let i = 0; i < 3; i++) {
    const d = (s[i] || 0) - (a[i] || 0);
    if (d) return d > 0;
  }
  return false;
}

// ONE cube, reused across every downloading/installing state of this card's
// life (never rebuilt per state — `createCube` keeps its own angle/burst, so
// tearing it down between "downloading" and "installing" would cost the
// spin its continuity for no reason, exactly the frozen-cube stutter
// loading.js's own fade-out comment warns against).
const updateCubeHandle = createCube(document.getElementById("update-cube"));

// SVG NEEDS THE ATTRIBUTE, NOT THE PROPERTY (grading round 2026-08-17, his
// second photograph: the ↻ icon was STILL drawn beside the spinning cube
// even after `#update-banner-icon[hidden]{display:none}` was added to
// update-banner.css). Root cause: `hidden` is an IDL property defined on
// HTMLElement — `#update-banner-icon` is an inline `<svg>`, an SVGElement,
// so `updateBannerIcon.hidden = true` sets a plain expando on the JS object
// and never touches the `hidden` ATTRIBUTE the `[hidden]` CSS selector
// matches. The code read correctly and did nothing, the exact shape of bug
// this whole round exists to close. `setAttribute`/`removeAttribute` reach
// the real DOM attribute regardless of which element interface owns the
// convenience property, so this one helper is safe to use on ANY element —
// used here for the icon, where it is required, not only where it happens
// to be.
function setHiddenAttr(el, hidden) {
  if (hidden) el.setAttribute("hidden", "");
  else el.removeAttribute("hidden");
}

// THE OFFER TRIGGER IS UNCHANGED (owner bug 2026-08-02: compare against the
// APK the PC actually SERVES, config.apk_version — comparing against the
// server version offered phantom updates whenever a release changed only
// the desktop side). This function only decides whether to show the card at
// all; it says nothing about which STATE the card opens on, which is always
// "offer" — a fresh `config` is the one signal this page cannot tell apart
// from "a brand-new update just became available", so a card frozen mid
// download from a stale earlier connection is never trusted to still apply.
function refreshUpdateBanner(apkVersion) {
  const should = !!(
    IN_APP && window.Android.appVersion &&
    (window.Android.updateInApp || window.Android.update) &&
    apkVersion && isNewer(apkVersion, window.Android.appVersion())
  );
  updateBanner.hidden = !should;
  if (should) setUpdateCardState("offer");
  syncUpdateBannerTop();
}

// --- The five card states ---------------------------------------------------
//
// "offer"        the reload icon; tapping starts the update
// "permission"   Android needs a one-time OK to install packages from this
//                PC (Settings → "install unknown apps" for this browser/
//                webview); the primary tap opens that OS screen
// "downloading"  the cube spins with a real progress fill
// "installing"   the cube keeps spinning; Android's own installer runs
// "failed"       the reason sentence; tappable again, exactly like "offer"
//
// One element carries the state as a class (`updateBanner.classList`) so
// the CSS for each look lives beside the others in style.css rather than
// being toggled piecemeal from here — the same pattern window-offer.js uses
// for its own three-answer chip.
const UPDATE_STATES = ["offer", "permission", "downloading", "installing", "failed"];
let updateCardState = "offer";
// Remembered so a "failed" retry, or a "permission" state's own tap, can
// re-issue the SAME request without needing fresh context from the caller —
// the URL never changes within one card's life (it is always this PC's own
// /app.apk).
let updatePendingUrl = null;
// The last percentage WRITTEN to the fill, so `__updateProgress` can tell a
// small real-download tick from a big jump — see `setDeterminateFill()`
// below. `null` means "no determinate width has landed yet this state", the
// condition that makes even a small first number a jump (there is nothing
// to smoothly transition FROM).
let updateLastPct = null;
// A jump past this many percentage points snaps instead of sliding (grading
// round 2026-08-17: `__updateProgress(100, 100)` was photographed with the
// label reading "100%" while the fill sat at half the track, caught
// mid-transition). Android's own DownloadManager reports roughly once a
// second, so an ordinary tick on a real download is a small, steady creep —
// anything bigger is either the very first number (see updateLastPct above)
// or a chunky step that would otherwise spend 200ms visibly disagreeing
// with the number beside it. 8 points is comfortably above the tick size a
// ~1s-cadence, multi-second download produces, and comfortably below "the
// bar silently jumped most of its own length".
const UPDATE_PCT_JUMP_THRESHOLD = 8;

// Writes `pct` to the fill, choosing per-write whether the CSS transition
// (style.css/update-banner.css `.determinate #update-banner-fill`) may run.
// THE FILL MUST NEVER DISAGREE WITH ITS OWN LABEL, even for 200ms — the
// same "the move is instant" ruling constraint 35 already applied to the
// status pill's slide, applied here to a progress bar's width instead of a
// position. `.no-transition` is added and removed on the SAME element in
// the SAME tick — style.css's rule for it is declared after `.determinate`,
// so it wins on source order without needing extra specificity — and is
// used only long enough to defeat the transition for this one write; a
// later SMALL tick (no class) is free to slide as designed.
function setDeterminateFill(pct) {
  const bigJump = updateLastPct === null
    || Math.abs(pct - updateLastPct) > UPDATE_PCT_JUMP_THRESHOLD;
  if (bigJump) updateBannerBar.classList.add("no-transition");
  updateBannerBar.style.setProperty("--upd-pct", `${pct}%`);
  if (bigJump) {
    // Force the browser to COMPUTE style with the transition disabled
    // before it is re-enabled — without this read, the two class/property
    // writes could be batched into one frame and the transition would still
    // see the width change as a normal animatable step (the exact failure
    // this function exists to prevent).
    void updateBannerFill.offsetWidth;
    updateBannerBar.classList.remove("no-transition");
  }
  updateLastPct = pct;
}

function setUpdateCardState(state, detail) {
  updateCardState = state;
  for (const s of UPDATE_STATES) updateBanner.classList.toggle(s, s === state);
  // The cube badge takes the icon's slot for exactly the two states that are
  // real work in flight — showing both at once would compete for the same
  // handful of pixels and say nothing the icon alone did not already say in
  // "offer"/"permission"/"failed".
  const spinning = state === "downloading" || state === "installing";
  setHiddenAttr(updateBannerIcon, spinning); // SVG — see setHiddenAttr's own comment above
  updateBannerCube.hidden = !spinning; // a plain <div> — the real HTMLElement property is fine here
  if (spinning) updateCubeHandle.start(); else updateCubeHandle.stop();
  // Only "downloading" and "installing" are genuinely busy — "permission"
  // and "failed" must stay tappable, since both exist for a SECOND tap.
  updateBanner.classList.toggle("busy", spinning);

  switch (state) {
    case "offer":
      updateBannerText.textContent = "Update the app — new version is ready";
      updateBannerBar.hidden = true;
      updateBannerPct.hidden = true;
      break;
    case "permission":
      // Plain language, no jargon (root CLAUDE.md's guiding-language rule):
      // the OS term is "install unknown apps", which means nothing to
      // someone who did not build Android — say what it is FOR instead.
      updateBannerText.textContent =
        "Android needs your permission to update this app from this PC — tap to allow it";
      updateBannerBar.hidden = true;
      updateBannerPct.hidden = true;
      break;
    case "downloading":
      updateBannerText.textContent = "Downloading the update…";
      updateBannerBar.hidden = false;
      // Starts indeterminate (no byte count has arrived yet); the first
      // real `__updateProgress` call flips it determinate. Never determinate
      // by default — a 0% fill sitting still LOOKS identical to a hang, the
      // very complaint task 207 exists to end.
      updateBannerBar.classList.remove("determinate", "no-transition");
      updateBannerPct.hidden = true;
      // A fresh "downloading" is a fresh download — the FIRST real
      // percentage it reports must snap, never slide in from whatever
      // number happened to be left on the fill by a previous attempt.
      updateLastPct = null;
      break;
    case "installing":
      // No promise of completion — Android is doing the installing, and this
      // page will never be told it finished (see the file header). "will
      // reopen" states the mechanism truthfully without claiming a timeline
      // this page cannot know.
      updateBannerText.textContent = "Installing — the app will reopen when it's done";
      updateBannerBar.hidden = true;
      updateBannerPct.hidden = true;
      break;
    case "failed":
      updateBannerText.textContent = (detail && String(detail).trim())
        || "The update did not finish — tap to try again";
      updateBannerBar.hidden = true;
      updateBannerPct.hidden = true;
      break;
  }
  // Every state can change the card's own height (one line vs. two, a bar
  // appearing) — the status pill / window-offer chip measure THEMSELVES to
  // give this card room above it, and this card in turn must never sit
  // where its own height would put it under either of them. See
  // syncUpdateBannerTop() below.
  syncUpdateBannerTop();
}

// --- Real progress (2026-08-17) --------------------------------------------
//
// Called by the shell as `window.__updateProgress(received, total)` while a
// download it took ownership of (via updateInApp) is running. `total <= 0`
// means the server response carried no Content-Length — Android's own
// DownloadManager reports exactly that shape, and rather than lie with a
// guessed denominator this falls back to the same indeterminate sweep the
// old, whole-feature fallback already uses.
window.__updateProgress = function updateProgress(received, total) {
  if (updateCardState !== "downloading") return; // a stray/late tick after a state change
  if (!(total > 0)) {
    updateBannerBar.classList.remove("determinate");
    updateBannerPct.hidden = true;
    // Still worth a whip: bytes ARE moving even though the length is
    // unknown, and the burst is how the cube shows a step happened at all.
    updateCubeHandle.whip();
    return;
  }
  const pct = Math.max(0, Math.min(100, Math.round((received / total) * 100)));
  updateBannerBar.classList.add("determinate");
  setDeterminateFill(pct); // decides, per tick, whether the width may transition — see above
  updateBannerPct.hidden = false;
  updateBannerPct.textContent = `${pct}%`;
  // The momentum burst already exists for exactly this (loading.js's own
  // `cubeNext()` on every window the server creates) — one whip per real
  // step makes each progress tick visibly move the cube, not just the bar.
  updateCubeHandle.whip();
};

// --- State pushed from the shell --------------------------------------------
//
// `state` is exactly one of "permission" | "downloading" | "installing" |
// "failed" — never invented beyond that list, and never a "success" (see the
// file header for why one cannot exist). Anything else is logged and
// ignored rather than guessed at, the same discipline connection.js's own
// message handlers use for an unrecognised type.
window.__updateState = function updateState(state, detail) {
  if (!UPDATE_STATES.includes(state) || state === "offer") {
    // Silent diagnostics go to the SERVER log, never a phone panel (owner
    // 2026-08-05's rule for exactly this class of report) — guarded because
    // `send` is connection.js's, which loads after this file and may not
    // yet be connected the instant a stray call arrives.
    if (typeof send === "function") {
      send({ type: "client_log", text: `[update] unknown __updateState "${state}"` });
    }
    return;
  }
  setUpdateCardState(state, detail);
};

// --- The tap -----------------------------------------------------------------
//
// One activator for every state that IS tappable ("offer", "permission",
// "failed" — "downloading"/"installing" are marked `.busy` and refuse taps
// via CSS `pointer-events: none`, the exact mechanism the old one-shot
// `.downloading` class used). `keepFocus`, not `keepRowTap`: this is an
// ordinary button, not a row inside a scrollable list (constraint 28).
keepFocus(updateBanner, () => {
  if (updateCardState === "downloading" || updateCardState === "installing") return;

  if (updateCardState === "permission") {
    // Opens Android's own settings screen. The card does NOT advance itself
    // from here — his instruction was that guidance continues automatically
    // when he comes back, driven by the next `__updateState` the shell sends
    // on resume (it re-checks the permission then). A second tap on this
    // same button before that arrives simply re-opens the same OS screen,
    // which is harmless and exactly what "not yet granted" should do.
    if (window.Android.updateAllowInstall) window.Android.updateAllowInstall();
    return;
  }

  // "offer" or "failed": (re)issue the same request.
  const url = updatePendingUrl || `${location.origin}/app.apk`;
  updatePendingUrl = url;

  if (window.Android.updateInApp) {
    // NEW PATH (2026-08-17): the shell owns the download and reports
    // progress. Whether the shell can start it right now, or must first ask
    // for the install permission, is ITS call — updateInApp() returning
    // false without a state change is the one case old-shell fallback logic
    // must not swallow, so a genuinely refused job still shows something.
    const took = window.Android.updateInApp(url);
    if (took) {
      setUpdateCardState("downloading");
    } else if (window.Android.updateInstallAllowed && !window.Android.updateInstallAllowed()) {
      setUpdateCardState("permission");
    } else {
      setUpdateCardState("failed", "Could not start the update — tap to try again");
    }
    return;
  }

  // FALLBACK — an older shell with no updateInApp: behave EXACTLY as this
  // page did before this round. The shell hands the URL to Android's own
  // DownloadManager and returns immediately; this page can never see a byte
  // of it (no bridge method existed to ask), so the honest answer stays the
  // ORIGINAL indeterminate stripe plus the sentence naming where the
  // download really lives. A page served by THIS round's server must still
  // work against a shell installed before it — the shell and the page are
  // two separate installs (see the root CLAUDE.md's protocol section).
  window.Android.update(url);
  updateBanner.classList.add("downloading"); // legacy visual hook only
  setHiddenAttr(updateBannerIcon, true); // SVG — see setHiddenAttr's own comment above
  updateBannerCube.hidden = true; // a plain <div>, the real HTMLElement property is fine here
  updateBannerBar.hidden = false;
  updateBannerBar.classList.remove("determinate");
  updateBannerPct.hidden = true;
  updateBannerText.textContent =
    "Downloading — check the notification shade, then open the file";
  showToast("Downloading — open the file to install the update");
  syncUpdateBannerTop();
});

// --- Nothing may overlap anything (owner decree 2026-08-17, constraint 35) -
//
// The status pill and the window-offer chip both already measure and
// publish their own real bottom edge (window-offer.js's `syncToastShift()`,
// writing `--status-top`) so the PILL never sits under the CHIP. This card
// sits BELOW both of them, and until this round it assumed a fixed 44px gap
// under the pill — true only while the pill was always exactly one line and
// the window-offer chip was never showing at the same time as an update.
// Neither is guaranteed: the chip stands for up to 30s (WINDOW_OFFER_MS in
// window-offer.js) and an update can become available at any moment inside
// that window, and a toast can wrap the pill onto two lines on a narrow
// phone. So this card's own top is MEASURED off whichever of the two really
// stands lower right now (constraint 13's rule, applied to our own page,
// same as window-offer.js already applies it to the pill) — never a
// constant, because both of those elements' heights depend on text this
// module does not control.
//
// A ResizeObserver on both elements (rather than hooking every place either
// one might change — a new toast, a chip queue advancing, a rotation) is
// the one measurement that cannot go stale: it fires on any size change,
// including hidden <-> shown (which collapses an element to a 0-height box),
// with no list of call sites for a future feature to forget to join.
const UPDATE_GAP_PX = 10;
const updateStatusEl = document.getElementById("status");
const updateOfferEl = document.getElementById("window-offer");

function syncUpdateBannerTop() {
  if (updateBanner.hidden) return; // nothing to place — leave the var alone for next time
  let bottom = 0;
  if (updateStatusEl && !updateStatusEl.hidden) {
    const box = updateStatusEl.getBoundingClientRect();
    if (box.height > 0) bottom = Math.max(bottom, box.bottom);
  }
  if (updateOfferEl && !updateOfferEl.hidden) {
    const box = updateOfferEl.getBoundingClientRect();
    if (box.height > 0) bottom = Math.max(bottom, box.bottom);
  }
  if (bottom > 0) {
    document.documentElement.style.setProperty(
      "--update-top", `${Math.round(bottom + UPDATE_GAP_PX)}px`);
  } else {
    // Neither is showing — style.css's own fallback (topbar + a fixed gap)
    // takes over, exactly the pre-2026-08-17 constant.
    document.documentElement.style.removeProperty("--update-top");
  }
}

if (typeof ResizeObserver !== "undefined") {
  const updateTopObserver = new ResizeObserver(syncUpdateBannerTop);
  if (updateStatusEl) updateTopObserver.observe(updateStatusEl);
  if (updateOfferEl) updateTopObserver.observe(updateOfferEl);
}
