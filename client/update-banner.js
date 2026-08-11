// --- In-app update (the PC carries the newer APK) --------------------------
// The phone never checks the internet for updates: `config.app_version` says
// what the PC runs, the bridge says what this shell is, and /app.apk on the
// SAME PC is the newer build (the desktop app updates itself from GitHub).
// Split out of controls.js (task 207, 2026-08-10) to keep that file under
// THE STRUCTURE LAW's 1,000-line ceiling — reads `IN_APP`, `keepFocus` and
// `showToast` as globals (plain scripts, no module system) and is called
// from connection.js's `config` handler.

const updateBanner = document.getElementById("update-banner");

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

function refreshUpdateBanner(apkVersion) {
  // Compare against the APK the PC actually SERVES (config.apk_version) —
  // comparing against the server version offered phantom updates whenever a
  // release changed only the desktop side (owner bug 2026-08-02).
  updateBanner.hidden = !(
    IN_APP && window.Android.appVersion && window.Android.update &&
    apkVersion && isNewer(apkVersion, window.Android.appVersion())
  );
}

// The banner swaps into an INDETERMINATE bar the instant it is tapped (task
// 207, owner decree 2026-08-10: "ne znam da li je blokirao ili radi" — the
// desktop's frozen "Downloading…" ellipsis, and this banner had the very
// same problem: a static toast, no ongoing sign of life at all). The APK
// download hands off to Android's OWN DownloadManager the moment `Android
// .update()` returns, so this page can never see real bytes moving — no new
// bridge method exists to ask it, and the shell is installed separately from
// this page (a page that needed one would go blank on an older shell). An
// animated stripe plus a sentence naming WHERE the download really lives is
// the honest answer; a frozen number here would be a LIE the desktop bug
// was not guilty of.
const updateBannerIcon = document.getElementById("update-banner-icon");
const updateBannerBar = document.getElementById("update-banner-bar");
const updateBannerText = document.getElementById("update-banner-text");

keepFocus(updateBanner, () => {
  if (updateBanner.classList.contains("downloading")) return; // one tap, ever
  window.Android.update(`${location.origin}/app.apk`);
  updateBanner.classList.add("downloading");
  updateBannerIcon.hidden = true;
  updateBannerBar.hidden = false;
  updateBannerText.textContent =
    "Downloading — check the notification shade, then open the file";
  showToast("Downloading — open the file to install the update");
});
