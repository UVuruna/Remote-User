package com.uvuruna.remoteuser

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.TrafficStats
import android.net.Uri
import android.os.Build
import android.view.WindowManager
import android.webkit.JavascriptInterface
import org.json.JSONObject

/** `window.Android` — everything the PAGE is allowed to ask of this shell.
 *
 *  Split out of MainActivity on 2026-08-07 (THE STRUCTURE LAW). The line is
 *  not "the file got long", it is that these are two different jobs:
 *
 *   - MainActivity is the WINDOW. It owns the WebView, the two stored
 *     addresses and the probe that picks one, the native error card, the
 *     system bars, and the Android lifecycle callbacks. Nothing in it is
 *     addressed by name from outside the app.
 *   - Bridge is the PROTOCOL. Every method here is a name the page calls, and
 *     the page is served by the PC while this shell is installed separately —
 *     so these signatures are a compatibility surface that outlives any one
 *     version of either side (hence `speakAs` beside `speak`, and `wide`
 *     still accepted by `lockOrientation`). A contract with that property
 *     deserves to be readable in one place, not buried at the bottom of an
 *     Activity.
 *
 *  It is a plain class holding its host rather than an inner class, and the
 *  host's members it reaches are `internal`: that list IS the shell's
 *  capability surface, and making it visible was half the point of the split.
 */
class Bridge(private val host: MainActivity) {

    @JavascriptInterface
    fun rescan() {
        host.runOnUiThread { host.repair() }
    }

    /** The page calls this on every `config` — the works-anywhere address
     *  (fresh token included) persists here. Blank = the PC lost Tailscale. */
    @JavascriptInterface
    fun setTailscaleUrl(url: String) {
        Prefs.setTsUrl(host, url.ifBlank { null })
    }

    /** The page has lost the PC and cannot get it back by itself (owner
     *  report 2026-08-07: *"dešava nam se prekid veze, i ovo 'Try again'
     *  dugme retko kad pomogne ... nekad čak i da zatvorimo celu
     *  aplikaciju"*).
     *
     *  The page's WebSocket can only ever go to the address the DOCUMENT was
     *  loaded from — `location.host`. When the phone changes network the
     *  document is still perfectly alive on an address that no longer reaches
     *  the PC, and nothing in the page can move it: it retries the dead host
     *  forever. The two stored addresses live HERE, so this is the only
     *  component that can answer, and until now it only ever answered at
     *  start, at onResume, or while the native error card was on screen —
     *  none of which is the state he is in. Restarting the app was therefore
     *  the only cure, because a restart is the one thing that re-probes.
     *
     *  The resolver decides what happens: the current address still answering
     *  leaves this document exactly where it is (`sessionHealthy` — the page's
     *  own JS reconnects in milliseconds and a reload would cost the session),
     *  the other one answering moves us there, neither answering brings up the
     *  error card with its own 4-second self-healing. */
    @JavascriptInterface
    fun linkLost() {
        host.runOnUiThread { host.pageLostTheServer() }
    }

    /** This shell's version — the page compares it with the server's
     *  `config.app_version` and offers the in-app update banner. */
    @JavascriptInterface
    fun appVersion(): String =
        host.packageManager.getPackageInfo(host.packageName, 0).versionName ?: "0"

    /** Origin-independent per-device storage for the page's preferences
     *  (sets picker, quality, one-time banners). localStorage is keyed
     *  by ORIGIN, and this shell deliberately alternates between two
     *  addresses (LAN / Tailscale) — pure localStorage silently split
     *  the page's saved state into two diverging copies (owner bug
     *  report 2026-08-05: the sets picker "rotated" between states).
     *  "" = absent, so the page can fall back to localStorage. */
    @JavascriptInterface
    fun prefGet(key: String): String =
        host.getSharedPreferences(Prefs.CLIENT_FILE, Context.MODE_PRIVATE)
            .getString("p_$key", "") ?: ""

    @JavascriptInterface
    fun prefSet(key: String, value: String) {
        host.getSharedPreferences(Prefs.CLIENT_FILE, Context.MODE_PRIVATE)
            .edit().putString("p_$key", value).apply()
    }

    /** The page's auto quality mode: reduced stream only on mobile data
     *  (owner spec 2026-08-02). "cellular" / "wifi" / "". */
    @JavascriptInterface
    fun transport(): String = when {
        host.onCellular -> "cellular"
        host.onWifi -> "wifi"
        else -> ""
    }

    /** WHY the page is being hidden — the question the page kept getting
     *  wrong on its own (owner failure 2026-08-05, twice: his Chrome and
     *  VSCode left hovering over his desk). Three answers, and the server
     *  treats anything it does not recognise as the end of the session:
     *
     *  "lock"      — the screen is off or the device is locked. ALWAYS the
     *                end, whatever else is going on: nothing of ours may
     *                stay above the owner's desk while he is not looking.
     *  "excursion" — THIS shell launched a picker / camera / voice /
     *                permission dialog and is still waiting for its
     *                result. The owner is with us; the PC holds the layout.
     *  ""          — the app was switched away or closed. The end.
     *
     *  The lock test comes first on purpose: a picker can be open when the
     *  screen goes off, and the screen wins.
     *
     *  None of this changed when the notice service arrived (2026-08-07) and
     *  that is deliberate: the streaming session must keep dying the moment
     *  the page hides. The service is a SECOND, separate channel that carries
     *  notices only — it never says the phone is present, and the PC would
     *  not believe it if it did (server/notify.py: `/notices` never touches
     *  the one-device slot). */
    @JavascriptInterface
    fun hideReason(): String = when {
        host.screenIsAway() -> "lock"
        host.excursions > 0 -> "excursion"
        else -> ""
    }

    /** What this phone has spent, straight from Android (cumulative since
     *  boot): our own UID and the whole device. The PC's Traffic window
     *  subtracts a reading taken before an absence from one taken after
     *  it — which is how "does it keep running while the screen is off"
     *  gets an answer measured BY THE PHONE instead of argued about
     *  (owner 2026-08-05). UNSUPPORTED (-1) is reported as 0. */
    @JavascriptInterface
    fun netStats(): String {
        fun ok(value: Long) = if (value == TrafficStats.UNSUPPORTED.toLong()) 0L else value
        val uid = host.applicationInfo.uid
        return JSONObject()
            .put("app_rx", ok(TrafficStats.getUidRxBytes(uid)))
            .put("app_tx", ok(TrafficStats.getUidTxBytes(uid)))
            .put("dev_rx", ok(TrafficStats.getTotalRxBytes()))
            .put("dev_tx", ok(TrafficStats.getTotalTxBytes()))
            .toString()
    }

    /** Hold the screen awake while the owner is actually working, release
     *  it when he stops. The flag used to be set once in onCreate and
     *  never cleared, so the tablet NEVER slept by itself: the presence
     *  signal the whole layout design rests on could only fire if he
     *  locked it by hand, and the screen burned battery over a stream
     *  nobody was watching (audit 2026-08-05). */
    @JavascriptInterface
    fun keepAwake(on: Boolean) {
        host.runOnUiThread {
            if (on) host.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            else host.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    /** Layout focus locks the phone's rotation to the layout's chosen
     *  orientation (owner 2026-08-02); "" unlocks (full-desktop view,
     *  rotation free). The page sends "landscape" or "portrait" — the owner
     *  banned the word "wide" on 2026-08-07: one name per thing. "wide" is
     *  still accepted so a page from an older PC keeps rotating.
     *
     *  Task 204: the mode is REMEMBERED in Prefs, not just set on this live
     *  Activity instance. `requestedOrientation` is not persisted by Android
     *  at all — an Activity recreation (the process reclaimed for memory
     *  during an excursion's picker, an OEM quirk) comes back with a FRESH
     *  instance defaulting to the manifest's unspecified orientation, and
     *  the page only calls this method when the layout FOCUS changes, so a
     *  recreated Activity that landed back on the same focused layout would
     *  never be told to lock again. `onCreate`/`onResume` re-assert the
     *  remembered mode before the page has even loaded. */
    @JavascriptInterface
    fun lockOrientation(mode: String) {
        Prefs.setOrientLock(host, mode)
        host.runOnUiThread { host.applyOrientationLock(mode) }
    }

    /** The page's Mic switcher (owner 2026-08-04): start one listening
     *  round. Results/round-end come back via __voiceResult/__voiceEnd;
     *  the page restarts rounds while its switcher stays ON. The whole
     *  subsystem lives in VoiceInput.kt. */
    @JavascriptInterface
    fun startVoice() {
        host.runOnUiThread { host.startVoiceInput() }
    }

    @JavascriptInterface
    fun stopVoice() {
        host.runOnUiThread { host.voice.cancel() }
    }

    /** The dictation setup card (owner round 2, 2026-08-05): candidate
     *  languages with their on-device status, the stored choice, and the
     *  download state that styles the Mic button. */
    @JavascriptInterface
    fun voiceLangs(): String = host.voice.candidates()

    @JavascriptInterface
    fun voiceChosen(): String = host.voice.chosenTag()

    @JavascriptInterface
    fun voiceSetLang(tag: String) {
        host.runOnUiThread { host.voice.setChosen(tag) }
    }

    @JavascriptInterface
    fun voiceState(): String = host.voice.state()

    /** Listening beeps (owner round 4, 2026-08-05): Android tones every
     *  round start/stop and rounds cycle on each silence — muted by
     *  default while dictating, the card's checkbox flips it. */
    @JavascriptInterface
    fun voiceMuteBeeps(): Boolean = host.voice.muteBeepsPref()

    @JavascriptInterface
    fun voiceSetMuteBeeps(on: Boolean) {
        host.runOnUiThread { host.voice.setMuteBeepsPref(on) }
    }

    /** A job on the PC finished (ROADMAP Phase H, owner 2026-08-05). The
     *  AGENT's name leads, and it is also the notification TAG, so the
     *  same agent replaces its own line while several agents keep one
     *  line each.
     *
     *  This is the path for a notice that arrives while the owner is LOOKING
     *  at the app. The same notice with the page closed never reaches this
     *  method at all — it goes to the phone over the notice service's own
     *  channel and is posted from there, which is what makes a double notice
     *  impossible: the PC picks exactly one carrier (server/notify.py). */
    @JavascriptInterface
    fun notify(title: String, text: String, tag: String) {
        host.runOnUiThread { host.postNotice(title, text, tag) }
    }

    /** The same notice, plus WHERE it happened — `jump` is the PC's
     *  `{index, name}` for the layout that agent's project is showing (owner
     *  2026-08-08, task 110). A tap then lands in that window instead of on
     *  whatever the app was last looking at.
     *
     *  A new method rather than a fourth argument on `notify`, for the reason
     *  written over `speakAs`: the page comes from the PC and the shell is
     *  installed separately, so a bridge method that changed arity would stop
     *  resolving for a page that has not been re-served yet — and the notice
     *  it was carrying would be lost, which is the one thing this feature
     *  exists to prevent. */
    @JavascriptInterface
    fun notifyAt(title: String, text: String, tag: String, jump: String) {
        host.runOnUiThread { host.postNotice(title, text, tag, jump) }
    }

    /** The layout the owner tapped a notification to reach, read ONCE.
     *
     *  A PULL, not a push, because the tap may have COLD-STARTED the app: at
     *  that moment there is no page, no socket and no layout list, so a
     *  pushed call would land in nothing. The shell holds the answer until
     *  the page knows enough to act on it, and clears it on the way out so a
     *  later reconnect cannot replay a jump the owner already took. */
    @JavascriptInterface
    fun noticeJump(): String = host.takeNoticeJump()

    /** Says the notice out loud (owner: "izgovori neku reč"). */
    @JavascriptInterface
    fun speak(text: String) {
        host.runOnUiThread { host.notifier.speak(text) }
    }

    /** The same, in the voice and at the pace the PC chose (owner round
     *  R2). A separate method rather than more arguments on `speak`: the
     *  page is served by the PC and the shell is installed separately, so
     *  the two versions drift, and a bridge method that changed arity
     *  would simply stop resolving for an older page. */
    @JavascriptInterface
    fun speakAs(text: String, voice: String, rate: Float) {
        host.runOnUiThread { host.notifier.speak(text, voice, rate) }
    }

    /** Every text-to-speech voice this DEVICE has, as JSON — sent to the
     *  PC once per connection so the desktop Settings window can offer
     *  them. The PC cannot enumerate them itself. */
    @JavascriptInterface
    fun ttsVoices(): String = host.notifier.voices()

    /** THE CLIPBOARD LIVES ON BOTH DEVICES (task 182): a NEW method, not an
     *  argument added to an existing one — the page is served by the PC
     *  while this shell is installed separately, so a changed signature
     *  would simply stop resolving for an older page.
     *
     *  Android lets only the FOREGROUND app write the system clipboard —
     *  true while this session streams, false during an away. The page
     *  already holds a push it could not deliver then (`_pending` in
     *  `server/clipboard_sync.py`) and only calls this once it is visible
     *  again, so no guard is needed here beyond what `ClipboardManager`
     *  itself already enforces. */
    @JavascriptInterface
    fun setClipboard(text: String) {
        host.runOnUiThread {
            val cm = host.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            cm.setPrimaryClip(ClipData.newPlainText("RemoteUser", text))
        }
    }

    // ── The waiting channel (owner decree 2026-08-07) ────────────────────
    // *"Radimo taj mali servis … android strana čeka signal, ne prima ništa
    //  od kompjutera, ali ostane u stanju čekanja signala."*
    //
    // The service itself needs no page and no user: it starts with the app.
    // What the page IS needed for is the one thing Android will not let an
    // app take for itself — the battery-optimisation exemption, without
    // which Doze defers our socket's traffic and a notice can sit unheard
    // until the phone next wakes. Asking for it needs an explanation, and
    // every explanation in this product lives in the page (owner principle,
    // stated angrily and binding). So the page reads the state here and
    // asks here; the words are its own.

    /** `{running, battery, notifications}` — what the page's notice card
     *  needs to decide whether to say anything at all. */
    @JavascriptInterface
    fun noticeState(): String = JSONObject()
        .put("running", NoticeService.running)
        .put("battery", NoticeService.batteryExempt(host))
        .put("notifications", Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            host.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED)
        .toString()

    /** The card's one button: ask Android to stop deferring this app. */
    @JavascriptInterface
    fun noticeSetup() {
        host.runOnUiThread { host.askBatteryExemption() }
    }

    /** Update tap: open /app.apk (on the SAME PC) in the system browser —
     *  it downloads and Android installs over this app (same signature).
     *  The WebView itself has no download pipeline; the browser here is
     *  only the download UI. */
    @JavascriptInterface
    fun update(url: String) {
        host.runOnUiThread {
            val view = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            try {
                host.startActivity(view)
            } catch (e: Exception) {
                // Some setups resolve no direct handler ("no app can open
                // this" — owner report 2026-08-02); the chooser always
                // offers whatever browsers exist.
                try {
                    host.startActivity(Intent.createChooser(view, "Download the update"))
                } catch (e2: Exception) {
                    // truly nothing to hand the download to — the page's
                    // toast already told the user what should have happened
                }
            }
        }
    }
}
