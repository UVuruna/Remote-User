// THE PAGE MUST NOT OUTLIVE ITS OWN PROTOCOL (T94, owner report 2026-08-14 —
// "the zoom does not survive two seconds", his third report on one feature).
// The PC updates ITSELF mid-evening (update_handover) while this page is a
// long-lived DOCUMENT: constraint 8 closes only the SOCKET on every hide, so
// the phone reconnects last hour's client to this hour's server. Measured
// live, in his own server log and reproduced byte for byte in a real-browser
// harness: the v0.0.205 page's zoom-echo guard against the v0.0.209 server
// erased every pinch within ~0.5 s (the old guard demanded a `stream_region`
// that echoes the pinched rect; the new server correctly never sends one, so
// the old page reset its view and its settle watcher then told the server to
// drop the zoom). No gate that imports only the current tree can even
// express that failure — two versions have to face each other — so the rule
// is structural instead: the page remembers the FIRST `config`'s
// app_version as the protocol it was served under, and ANY different version
// later — newer or older alike, a rollback changes the wire just as surely —
// means this document is stale and must re-fetch itself.
//
// Pure (the live-clock.js / zoom-crop.js pattern): no DOM, no socket — the
// gate runs the decision whole. connection.js owns the side effect
// (location.reload()) and carries the memory across calls.
"use strict";

/** One `config`'s worth of the decision. `servedVersion` is the version the
 *  document remembers being served under ("" before the first config);
 *  `configVersion` is what this frame claims the server runs.
 *
 *  Returns { servedVersion, reload }: the caller stores `servedVersion` back
 *  and reloads the document when `reload` is true. A frame with no version
 *  (an older server) decides nothing and never arms the memory — a later
 *  frame that does carry one must not compare against "". */
function pageVersionStep(servedVersion, configVersion) {
  const v = configVersion == null ? "" : String(configVersion);
  if (!v) return { servedVersion, reload: false };
  if (!servedVersion) return { servedVersion: v, reload: false };
  return { servedVersion, reload: v !== servedVersion };
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { pageVersionStep };
}
