package com.uvuruna.remoteuser

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.TrafficStats
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.app.KeyguardManager
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.view.View
import android.view.WindowManager
import android.webkit.JavascriptInterface
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit

/** The client shell: a full-screen WebView on the reachable pairing URL.
 *
 *  The page carries ALL the product UI and guidance; the shell adds only
 *  what a browser tab cannot:
 *  - two stored addresses (LAN from the QR, Tailscale learned from the page)
 *    are probed on every start and the reachable one is loaded — the app
 *    works at home AND on mobile data without the user picking anything
 *  - external links (Google Play from the in-page Tailscale wizard) open as
 *    real apps, not inside the WebView
 *  - the file chooser (phone → PC image upload) is wired up
 *  - a native error card when no address answers — a live state, not a dead
 *    end: it re-probes by itself on a timer and on every network change, and
 *    it names the actual CAUSE (no network / Tailscale missing / Tailscale
 *    off / PC down) with the one button that fixes THAT cause
 *  - a one-time heads-up when the session runs over an unfamiliar Wi-Fi
 *  - `Android.rescan()` / `Android.setTailscaleUrl()` JS bridge
 *  - the screen stays on; rotation never recreates the session; leaving the
 *    app pauses the page (its visibility rule closes the stream — owner
 *    security decision)
 */
class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView
    private lateinit var errorView: View
    private lateinit var errorTitle: TextView
    private lateinit var errorBody: TextView
    private lateinit var errorAction: Button
    private lateinit var loadingView: View
    private var fileCallback: ValueCallback<Array<Uri>>? = null

    private val handler = Handler(Looper.getMainLooper())
    private var connectivity: ConnectivityManager? = null
    private var resolveEpoch = 0 // UI thread only — voids stale resolver threads and timers
    private var onWifi = false // default network carries a Wi-Fi transport (UI thread only)
    @Volatile private var onCellular = false // for the page's auto quality mode (any thread)
    private var warnedForeignWifi = false
    // Document health: a LIVE page must never be reloaded by the recovery
    // machinery — its own JS reconnects the WebSocket in milliseconds, while
    // a reload tears the whole session down (audit finding 2026-07-29: the
    // unlock-after-doze race turned every transient ping failure into a
    // guaranteed reload of a healthy session).
    private var pageAlive = false
    private var lastLoadFailed = false
    /** An EXCURSION is a trip THIS shell sent the user on — a file picker, the
     *  camera, the voice recogniser, a runtime permission dialog. It is the
     *  one kind of page-hide that means "still working with you, back in a
     *  second", and it is the only thing the PC is allowed to hold layout
     *  windows above the owner's desk for.
     *
     *  It used to be guessed in the page from a 90-second timer armed by the
     *  last Mic/picker tap, so locking the tablet moments after dictating was
     *  reported as an excursion and the owner's Chrome and VSCode hovered over
     *  his desk for five minutes (his report, twice, 2026-08-05). The shell is
     *  the only component that KNOWS, so the shell is what answers now. */
    private var excursions = 0
    /** The activity is between onStart and onStop — i.e. there is a window on
     *  screen to load a page into. */
    private var started = false

    /** Reconnect the moment the phone actually has a network again. Foreign
     *  Wi-Fi drops and re-grants connectivity constantly (AP kicks, power
     *  save, captive re-auth) — leaving recovery to a finger on "Try again"
     *  is what made the error card feel dead. Also tracks whether the default
     *  network is Wi-Fi at all: the foreign-Wi-Fi notice needs the transport,
     *  and a VPN network (Tailscale) lists its underlying transports in its
     *  capabilities. */
    private val netCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                if (errorView.visibility == View.VISIBLE) resolveAndLoad(silent = true)
            }
        }

        override fun onCapabilitiesChanged(network: Network, caps: NetworkCapabilities) {
            val wifi = caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)
            onCellular = caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)
            runOnUiThread {
                if (wifi != onWifi) {
                    onWifi = wifi
                    if (!wifi) warnedForeignWifi = false // the next foreign Wi-Fi warns again
                }
            }
        }
    }

    private val filePicker =
        registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
            endExcursion()
            fileCallback?.onReceiveValue(if (uri != null) arrayOf(uri) else arrayOf())
            fileCallback = null
        }

    /** Multi-select picker — the page's gallery/Files inputs carry `multiple`
     *  (owner 2026-08-04: more than one image/file may go to the PC at once). */
    private val multiPicker =
        registerForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
            endExcursion()
            fileCallback?.onReceiveValue(uris?.toTypedArray() ?: arrayOf())
            fileCallback = null
        }

    /** Camera capture for the page's `capture` input: the shot lands in this
     *  app's cache via FileProvider — no gallery detour, no storage permission. */
    private var cameraUri: Uri? = null
    private val cameraShot =
        registerForActivityResult(ActivityResultContracts.TakePicture()) { ok ->
            endExcursion()
            val uri = cameraUri
            fileCallback?.onReceiveValue(if (ok && uri != null) arrayOf(uri) else arrayOf())
            fileCallback = null
            cameraUri = null
        }

    /** CAMERA is declared in the manifest (the QR scanner), so the capture
     *  intent legally REQUIRES the runtime grant too. */
    private val cameraPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            // Granted -> the camera opens next, so the trip is not over yet;
            // refused -> it is, and the page comes straight back.
            if (granted) launchCamera()
            else {
                endExcursion()
                fileCallback?.onReceiveValue(arrayOf())
                fileCallback = null
            }
        }

    private val audioPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            endExcursion()
            if (granted) voice.listen() else voice.deny()
        }

    /** Android 13+ asks before ANY app may raise a notification. Requested on
     *  the first notice rather than at startup: a user who never turns the
     *  feature on is never asked, and the ask arrives with its reason
     *  visible on screen (owner principle — nothing unexplained). */
    // A notice that arrived before the permission did (see `notify` below).
    private var pendingNotice: Triple<String, String, String>? = null

    private val notifyPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            val held = pendingNotice
            pendingNotice = null
            if (granted) {
                held?.let { notifier.post(it.first, it.second, it.third) }
            } else {
                web.evaluateJavascript(
                    "window.__notifyDenied && __notifyDenied()", null)
            }
        }

    /** Android 13+ needs POST_NOTIFICATIONS before a single notice can be
     *  shown, and asking for it when the FIRST one arrives is too late twice
     *  over: that notice is spent on the dialog, and if the app is in the
     *  background the dialog cannot even appear. So it is asked for once, at
     *  start, while the owner is looking at the app. */
    private fun askNotificationPermission() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) ==
            PackageManager.PERMISSION_GRANTED) return
        notifyPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Prefs.lanUrl(this) == null) {
            repair()
            return
        }
        setContentView(R.layout.activity_main)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        hideSystemBars()
        askNotificationPermission()

        errorView = findViewById(R.id.error_view)
        errorTitle = findViewById(R.id.error_title)
        errorBody = findViewById(R.id.error_body)
        errorAction = findViewById(R.id.btn_action) // label + action set per cause
        loadingView = findViewById(R.id.loading_view)
        findViewById<Button>(R.id.btn_repair).setOnClickListener { repair() }

        web = findViewById(R.id.web)
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false // MSE video must start by itself
            // The server routes plain Android browsers to the install funnel;
            // this marker is how the app itself gets the real client page.
            userAgentString = "$userAgentString RemoteUserApp"
        }
        // No framework focus rectangle over our content: the page's keyboard
        // capture field is deliberately invisible, and any highlight drawn
        // around it is a bright bar across the top of the stream (owner
        // reported it five times — the page kills the CSS focus ring, this
        // kills the platform one). API 26 = our minSdk, so no guard needed.
        web.defaultFocusHighlightEnabled = false
        web.addJavascriptInterface(Bridge(), "Android")
        web.webViewClient = Client()
        web.webChromeClient = Chrome()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                moveTaskToBack(true) // back = background, never kill the session by accident
            }
        })

        connectivity = (getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager)
            .also { it.registerDefaultNetworkCallback(netCallback) }

        resolveAndLoad()
    }

    override fun onDestroy() {
        connectivity?.unregisterNetworkCallback(netCallback)
        connectivity = null
        voice.destroy()
        notifier.release()
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    // ── Voice input ── lives in VoiceInput.kt (split 2026-08-05, THE
    // STRUCTURE LAW): SpeechRecognizer rounds, the user-chosen dictation
    // language, on-device model download and the silent diagnostics chain.
    private val voice by lazy {
        VoiceInput(this) { code ->
            if (::web.isInitialized) web.evaluateJavascript(code, null)
        }
    }

    // ── Notifications ── lives in Notifier.kt (ROADMAP Phase H, owner
    // 2026-08-05): a job on the PC finished, and the phone says WHICH agent.
    // Lazy, because most sessions never receive one.
    private val notifier by lazy { Notifier(this) }

    private fun launchCamera() {
        val dir = File(cacheDir, "camera").apply { mkdirs() }
        val file = File(dir, "shot.jpg")
        val uri = FileProvider.getUriForFile(this, "$packageName.fileprovider", file)
        cameraUri = uri
        try {
            cameraShot.launch(uri)
        } catch (e: Exception) {
            // no camera app at all — hand back an empty pick, the page toasts
            endExcursion()   // nothing will hide the page after all
            fileCallback?.onReceiveValue(arrayOf())
            fileCallback = null
            cameraUri = null
        }
    }

    /** Probes /ping on every stored address in parallel and loads the first
     *  reachable one — LAN preferred (lower latency), Tailscale the fallback
     *  (mobile data, away from home). Waiting on the WebView's own timeout
     *  (~2 min of blank screen) is exactly the failure this replaces; no
     *  probe answering shows the native card within ~3 s instead.
     *
     *  The error card is a STATE, not a dead end: while it shows, the
     *  resolver re-runs by itself (timer + network-change events). On flaky
     *  foreign Wi-Fi the old one-shot probe always fired mid-flap — "Try
     *  again" looked broken and only an app restart, which happened to take
     *  long enough for the network/tunnel to settle, ever reconnected (owner
     *  report 2026-07-27). `silent` keeps whatever is on screen instead of
     *  flashing the loader during those background attempts. */
    private fun resolveAndLoad(silent: Boolean = false) {
        val epoch = ++resolveEpoch
        if (!silent) {
            errorView.visibility = View.GONE
            loadingView.visibility = View.VISIBLE // "Connecting…" until the page loads or an address fails
        }
        val lan = Prefs.lanUrl(this)
        val ts = Prefs.tsUrl(this)
        val candidates = listOfNotNull(lan, ts).distinct()
        if (candidates.isEmpty()) {
            repair()
            return
        }
        Thread {
            val probes = candidates.map { url ->
                val probe = FutureTask { pingOk(url) }
                Thread(probe).start()
                url to probe
            }
            val results = probes.map { (url, probe) ->
                url to try {
                    // A slow-but-alive probe legitimately spends up to
                    // connectTimeout + readTimeout — waiting any less
                    // declares a reachable server dead (cold DERP relay).
                    probe.get(2L * PING_TIMEOUT_MS + 500L, TimeUnit.MILLISECONDS)
                } catch (e: Exception) {
                    false
                }
            }
            val chosen = results.firstOrNull { it.second }?.first
            runOnUiThread {
                if (isFinishing || isDestroyed || epoch != resolveEpoch) return@runOnUiThread
                if (chosen != null) {
                    // Home LAN dead but the tunnel answered, over Wi-Fi =
                    // some network other than home — say so once per stay.
                    if (chosen == ts && chosen != lan) warnIfForeignWifi()
                    val current = web.url
                    val sessionHealthy = silent && pageAlive && current != null &&
                        results.any { it.first == current && it.second }
                    if (sessionHealthy) {
                        // The document is live and ITS address answers — the
                        // page's own JS reconnects the WebSocket; a loadUrl
                        // here would kill a healthy session (the unlock race).
                        errorView.visibility = View.GONE
                        loadingView.visibility = View.GONE
                    } else if (started) {
                        web.loadUrl(chosen) // loader (or card) stays until the page reacts
                    }
                    // Not started = no window on screen. Loading here is what
                    // let a background network event open a full stream to a
                    // phone in a pocket; onResume re-runs the resolver anyway.
                } else {
                    loadingView.visibility = View.GONE
                    showErrorCard()
                    scheduleRetry(epoch)
                }
            }
        }.start()
    }

    /** One pending background re-probe while the error card shows. A bumped
     *  epoch (manual Try again, onResume, a network event) or the card
     *  leaving the screen voids it — retries never stack and never touch a
     *  live page. */
    private fun scheduleRetry(epoch: Int) {
        handler.postDelayed({
            if (epoch == resolveEpoch && !isFinishing && !isDestroyed &&
                errorView.visibility == View.VISIBLE
            ) {
                resolveAndLoad(silent = true)
            }
        }, RETRY_INTERVAL_MS)
    }

    /** Why the connection failed, as far as the phone can honestly tell.
     *  Order matters — each state is only reached once the ones above it are
     *  ruled out (owner-approved decision flow 2026-08-04). */
    private enum class Fail { NO_NET, PC_NO_TUNNEL, TS_MISSING, TS_OFF, PC_DOWN }

    /** One generic message for five different causes was the whole problem
     *  (owner report 2026-08-04): every failure read "Try again", including
     *  the everyday one — phone away from the home Wi-Fi with Tailscale
     *  switched off — where tapping Try again can never work and the fix is
     *  two taps away in another app. The card now names the cause and its
     *  primary button IS the fix: install Tailscale / open Tailscale /
     *  re-probe now. Re-rendered on every failed resolve, so the card follows
     *  the phone's state live (tunnel comes up → the text moves on to the PC).
     *
     *  Nothing here replaces the self-healing: the 4 s timer and the network
     *  callback keep re-probing, so a user who flips Tailscale on and comes
     *  back finds the session already loading — no tap needed. */
    private fun showErrorCard() {
        when (classifyFailure()) {
            Fail.NO_NET -> renderErrorCard(
                R.string.err_nonet_title, R.string.err_nonet_body, R.string.try_again
            ) { resolveAndLoad() }
            Fail.PC_NO_TUNNEL -> renderErrorCard(
                R.string.err_pcts_title, R.string.err_pcts_body, R.string.try_again
            ) { resolveAndLoad() }
            Fail.TS_MISSING -> renderErrorCard(
                R.string.err_ts_missing_title, R.string.err_ts_missing_body,
                R.string.install_tailscale
            ) { installTailscale() }
            Fail.TS_OFF -> renderErrorCard(
                R.string.err_ts_off_title, R.string.err_ts_off_body, R.string.open_tailscale
            ) { openTailscale() }
            Fail.PC_DOWN -> renderErrorCard(
                R.string.error_title, R.string.error_body, R.string.try_again
            ) { resolveAndLoad() }
        }
        errorView.visibility = View.VISIBLE
    }

    private fun renderErrorCard(title: Int, body: Int, action: Int, onAction: () -> Unit) {
        errorTitle.setText(title)
        errorBody.setText(body)
        errorAction.setText(action)
        errorAction.setOnClickListener { onAction() }
    }

    /** The phone reads three things, all without a single extra permission:
     *  does it have a network at all, is a VPN tunnel up, is Tailscale even
     *  installed (needs the manifest `<queries>` entry on Android 11+).
     *
     *  Honest limits: Android exposes no "is Tailscale connected" API — only
     *  "some VPN is up" — and no way to tell the home Wi-Fi from a foreign one
     *  without the location permission just to read an SSID. So TS_OFF also
     *  catches "at home, Tailscale off, PC asleep"; its copy says so, and
     *  turning the tunnel on is the only move the phone has either way. */
    private fun classifyFailure(): Fail {
        if (!hasNetwork()) return Fail.NO_NET
        // The PC never reported a Tailscale address: nothing the phone does
        // can create a way in — the missing step is on the PC.
        if (Prefs.tsUrl(this) == null) return Fail.PC_NO_TUNNEL
        if (tailscaleLauncher() == null) return Fail.TS_MISSING
        if (!tunnelUp()) return Fail.TS_OFF
        return Fail.PC_DOWN
    }

    private fun activeCaps(): NetworkCapabilities? {
        val cm = connectivity ?: return null
        return cm.getNetworkCapabilities(cm.activeNetwork ?: return null)
    }

    private fun hasNetwork(): Boolean {
        val caps = activeCaps() ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    /** A VPN is up when the default network IS the tunnel — it carries the VPN
     *  transport and, being a VPN, lacks NOT_VPN. Either signal alone is
     *  enough; both are checked because OEM builds have been inconsistent. */
    private fun tunnelUp(): Boolean {
        val caps = activeCaps() ?: return false
        return caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN) ||
            !caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_NOT_VPN)
    }

    private fun tailscaleLauncher(): Intent? =
        packageManager.getLaunchIntentForPackage(TAILSCALE_PKG)

    /** Android gives no way to flip another app's VPN switch, so this opens
     *  Tailscale and the card's text tells the user the one thing to press.
     *  Coming back needs no tap here: the network callback fires the moment
     *  the tunnel is up and the resolver loads the session. */
    private fun openTailscale() {
        val launch = tailscaleLauncher()
        if (launch == null) {
            installTailscale()
            return
        }
        try {
            startActivity(launch)
        } catch (e: Exception) {
            Toast.makeText(this, R.string.tailscale_no_app, Toast.LENGTH_LONG).show()
        }
    }

    private fun installTailscale() {
        val store = Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$TAILSCALE_PKG"))
        try {
            startActivity(store)
        } catch (e: Exception) {
            // No Play Store app (or it refuses the market: scheme) — the web
            // listing opens in any browser and installs from there.
            try {
                startActivity(
                    Intent(
                        Intent.ACTION_VIEW,
                        Uri.parse("https://play.google.com/store/apps/details?id=$TAILSCALE_PKG")
                    )
                )
            } catch (e2: Exception) {
                Toast.makeText(this, R.string.tailscale_no_app, Toast.LENGTH_LONG).show()
            }
        }
    }

    /** Owner request 2026-07-27: the app must WORK on any Wi-Fi, with a
     *  security heads-up. Reading the SSID/security type (to call out open
     *  public networks specifically) needs the location permission plus
     *  location services — too much friction for a notice, so the signal is
     *  transport-level: home LAN dead + tunnel alive while on Wi-Fi means an
     *  unfamiliar network. Warned once per stay (re-armed when Wi-Fi drops). */
    private fun warnIfForeignWifi() {
        if (!onWifi || warnedForeignWifi) return
        warnedForeignWifi = true
        Toast.makeText(this, R.string.foreign_wifi_warning, Toast.LENGTH_LONG).show()
    }

    /** True when the server answers the auth-free reachability probe.
     *  ONLY the exact, redirect-free 204 counts (the /ping contract, pinned
     *  by the build gate): captive portals on foreign/public Wi-Fi answer
     *  ANY request with their login page — a 2xx or a redirect to one — and
     *  that false positive sent the WebView to a dead LAN address (live
     *  failure 2026-07-27). `Connection: close` forces a fresh socket per
     *  probe; pooled keep-alive sockets go stale across network changes and
     *  fail probes a freshly started process would pass. */
    private fun pingOk(pageUrl: String): Boolean = try {
        val u = Uri.parse(pageUrl)
        val conn = URL("${u.scheme}://${u.host}:${u.port}/ping").openConnection() as HttpURLConnection
        conn.connectTimeout = PING_TIMEOUT_MS
        conn.readTimeout = PING_TIMEOUT_MS
        conn.instanceFollowRedirects = false
        conn.useCaches = false
        conn.setRequestProperty("Connection", "close")
        try {
            conn.responseCode == 204
        } finally {
            conn.disconnect()
        }
    } catch (e: Exception) {
        false
    }

    /** Immersive: the status and navigation bars are HIDDEN while controlling
     *  the PC. targetSdk 35 draws the WebView edge-to-edge, so a visible nav
     *  bar sat ON TOP of the page's bottom controls and the system stole the
     *  touches aimed at them (owner report 2026-07-26 — "no button works").
     *  A swipe from the edge shows the bars transiently; they hide again by
     *  themselves. Re-applied on every focus gain — the system restores bars
     *  after dialogs, app switches and the keyboard. */
    private fun hideSystemBars() {
        val controller = WindowCompat.getInsetsController(window, window.decorView)
        controller.systemBarsBehavior =
            WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        controller.hide(WindowInsetsCompat.Type.systemBars())
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus && ::web.isInitialized) hideSystemBars()
    }

    private fun repair() {
        // The stored addresses SURVIVE until a new pairing succeeds
        // (OnboardingActivity.tryConnect overwrites them). Wiping them here
        // meant one mis-tap of "Scan a new QR" while away from home
        // permanently stranded the phone — nothing left to connect to and
        // no QR to scan until physically back at the PC.
        startActivity(
            Intent(this, OnboardingActivity::class.java)
                .putExtra(OnboardingActivity.EXTRA_FORCE, true)
        )
        finish()
    }

    /** Page pauses when the app does — the client's visibility rule then
     *  closes the WebSocket (nothing runs while nobody is looking).
     *
     *  On return, verify the loaded address still answers: the app often
     *  survives in RAM across a location change (home Wi-Fi → mobile data),
     *  and the page would retry its now-dead address forever. If it stopped
     *  answering, re-resolve — the other stored address takes over. */
    override fun onResume() {
        super.onResume()
        voice.onForeground()
        if (!::web.isInitialized) return
        web.onResume()
        val current = web.url
        if (current == null) {
            // Nothing ever loaded (cold start straight onto the error card) —
            // kick the resolver instead of waiting out the retry timer.
            if (errorView.visibility == View.VISIBLE) resolveAndLoad(silent = true)
            return
        }
        Thread {
            if (!pingOk(current)) {
                runOnUiThread {
                    // Silent: at unlock the Wi-Fi often is not back yet for
                    // 1-3 s, so this single ping fails on a perfectly healthy
                    // session — the silent resolver re-checks and keeps a
                    // live page untouched instead of flashing the loader and
                    // reloading it (the 2026-07-29 unlock race).
                    if (!isFinishing && !isDestroyed) resolveAndLoad(silent = true)
                }
            }
        }.start()
    }

    /** Called at the moment the shell itself launches something that will
     *  hide the page. Paired with endExcursion() in every result callback. */
    private fun beginExcursion() {
        excursions++
    }

    private fun endExcursion() {
        if (excursions > 0) excursions--
    }

    /** Is the screen actually off, or the device locked? This is the fact the
     *  page could never know and kept guessing wrong. isInteractive() is false
     *  from the moment the screen goes dark; the keyguard covers "screen on,
     *  but locked" (a lock button press on some OEM builds, a smart-lock
     *  timeout). Either one is the end of the session, full stop. */
    private fun screenIsAway(): Boolean {
        val power = getSystemService(Context.POWER_SERVICE) as? PowerManager
        if (power != null && !power.isInteractive) return true
        val keyguard = getSystemService(Context.KEYGUARD_SERVICE) as? KeyguardManager
        return keyguard?.isKeyguardLocked == true
    }

    override fun onStart() {
        super.onStart()
        started = true
    }

    override fun onStop() {
        // Nothing may keep probing, retrying or LOADING while there is no
        // window on screen: the resolver's 4 s timer and the network callback
        // used to run on regardless, and a loadUrl from either of them woke a
        // pocketed phone into a full session (audit 2026-08-05).
        started = false
        handler.removeCallbacksAndMessages(null)
        resolveEpoch++   // voids any resolver thread still in flight
        super.onStop()
    }

    override fun onPause() {
        // The LOCK button stops EVERYTHING (owner round 4, 2026-08-05):
        // the mic lives in this shell, not in the page, and its round loop
        // kept cycling and beeping under a locked screen. Cancel the running
        // round here and refuse new ones until onResume.
        voice.onBackground()
        if (::web.isInitialized) web.onPause()
        super.onPause()
    }

    private inner class Bridge {
        @JavascriptInterface
        fun rescan() {
            runOnUiThread { repair() }
        }

        /** The page calls this on every `config` — the works-anywhere address
         *  (fresh token included) persists here. Blank = the PC lost Tailscale. */
        @JavascriptInterface
        fun setTailscaleUrl(url: String) {
            Prefs.setTsUrl(this@MainActivity, url.ifBlank { null })
        }

        /** This shell's version — the page compares it with the server's
         *  `config.app_version` and offers the in-app update banner. */
        @JavascriptInterface
        fun appVersion(): String =
            packageManager.getPackageInfo(packageName, 0).versionName ?: "0"

        /** Origin-independent per-device storage for the page's preferences
         *  (sets picker, quality, one-time banners). localStorage is keyed
         *  by ORIGIN, and this shell deliberately alternates between two
         *  addresses (LAN / Tailscale) — pure localStorage silently split
         *  the page's saved state into two diverging copies (owner bug
         *  report 2026-08-05: the sets picker "rotated" between states).
         *  "" = absent, so the page can fall back to localStorage. */
        @JavascriptInterface
        fun prefGet(key: String): String =
            getSharedPreferences("client_prefs", MODE_PRIVATE)
                .getString("p_$key", "") ?: ""

        @JavascriptInterface
        fun prefSet(key: String, value: String) {
            getSharedPreferences("client_prefs", MODE_PRIVATE)
                .edit().putString("p_$key", value).apply()
        }

        /** The page's auto quality mode: reduced stream only on mobile data
         *  (owner spec 2026-08-02). "cellular" / "wifi" / "". */
        @JavascriptInterface
        fun transport(): String = when {
            onCellular -> "cellular"
            onWifi -> "wifi"
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
         *  screen goes off, and the screen wins. */
        @JavascriptInterface
        fun hideReason(): String = when {
            screenIsAway() -> "lock"
            excursions > 0 -> "excursion"
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
            val uid = applicationInfo.uid
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
            runOnUiThread {
                if (on) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            }
        }

        /** Layout focus locks the phone's rotation to the layout's chosen
         *  orientation (owner 2026-08-02); "" unlocks (full-desktop view,
         *  rotation free). "wide" = landscape, "portrait" = portrait. */
        @JavascriptInterface
        fun lockOrientation(mode: String) {
            runOnUiThread {
                requestedOrientation = when (mode) {
                    "portrait" -> android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
                    "wide" -> android.content.pm.ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
                    else -> android.content.pm.ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
                }
            }
        }

        /** The page's Mic switcher (owner 2026-08-04): start one listening
         *  round. Results/round-end come back via __voiceResult/__voiceEnd;
         *  the page restarts rounds while its switcher stays ON. The whole
         *  subsystem lives in VoiceInput.kt. */
        @JavascriptInterface
        fun startVoice() {
            runOnUiThread {
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) ==
                    PackageManager.PERMISSION_GRANTED
                ) voice.listen()
                else {
                    beginExcursion()   // the permission dialog hides the page
                    audioPermission.launch(Manifest.permission.RECORD_AUDIO)
                }
            }
        }

        @JavascriptInterface
        fun stopVoice() {
            runOnUiThread { voice.cancel() }
        }

        /** The dictation setup card (owner round 2, 2026-08-05): candidate
         *  languages with their on-device status, the stored choice, and the
         *  download state that styles the Mic button. */
        @JavascriptInterface
        fun voiceLangs(): String = voice.candidates()

        @JavascriptInterface
        fun voiceChosen(): String = voice.chosenTag()

        @JavascriptInterface
        fun voiceSetLang(tag: String) {
            runOnUiThread { voice.setChosen(tag) }
        }

        @JavascriptInterface
        fun voiceState(): String = voice.state()

        /** Listening beeps (owner round 4, 2026-08-05): Android tones every
         *  round start/stop and rounds cycle on each silence — muted by
         *  default while dictating, the card's checkbox flips it. */
        @JavascriptInterface
        fun voiceMuteBeeps(): Boolean = voice.muteBeepsPref()

        @JavascriptInterface
        fun voiceSetMuteBeeps(on: Boolean) {
            runOnUiThread { voice.setMuteBeepsPref(on) }
        }

        /** A job on the PC finished (ROADMAP Phase H, owner 2026-08-05). The
         *  AGENT's name leads, and it is also the notification TAG, so the
         *  same agent replaces its own line while several agents keep one
         *  line each. */
        @JavascriptInterface
        fun notify(title: String, text: String, tag: String) {
            runOnUiThread {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
                    checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
                    PackageManager.PERMISSION_GRANTED) {
                    // Ask, and REMEMBER what was being said — the notice used
                    // to be dropped here ("this one is lost; the next lands"),
                    // which is how the owner's first agent finish arrived as a
                    // toast and never reached his notification tray
                    // (2026-08-06). It is posted the moment he grants it.
                    pendingNotice = Triple(title, text, tag)
                    notifyPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
                    return@runOnUiThread
                }
                notifier.post(title, text, tag)
            }
        }

        /** Says the notice out loud (owner: "izgovori neku reč"). */
        @JavascriptInterface
        fun speak(text: String) {
            runOnUiThread { notifier.speak(text) }
        }

        /** Update tap: open /app.apk (on the SAME PC) in the system browser —
         *  it downloads and Android installs over this app (same signature).
         *  The WebView itself has no download pipeline; the browser here is
         *  only the download UI. */
        @JavascriptInterface
        fun update(url: String) {
            runOnUiThread {
                val view = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                try {
                    startActivity(view)
                } catch (e: Exception) {
                    // Some setups resolve no direct handler ("no app can open
                    // this" — owner report 2026-08-02); the chooser always
                    // offers whatever browsers exist.
                    try {
                        startActivity(Intent.createChooser(view, "Download the update"))
                    } catch (e2: Exception) {
                        // truly nothing to hand the download to — the page's
                        // toast already told the user what should have happened
                    }
                }
            }
        }
    }

    private inner class Client : WebViewClient() {
        override fun shouldOverrideUrlLoading(
            view: WebView, request: WebResourceRequest
        ): Boolean {
            val target = request.url
            val homePort = Uri.parse(Prefs.lanUrl(this@MainActivity) ?: return false).port
            // Our server (any of its addresses shares the port) stays inside;
            // everything else (Google Play, tailscale.com) opens as a real app.
            if (target.scheme?.startsWith("http") == true && target.port == homePort) {
                return false
            }
            return try {
                startActivity(Intent(Intent.ACTION_VIEW, target))
                true
            } catch (e: Exception) {
                true // no handler for the link — swallow rather than break the page
            }
        }

        override fun onReceivedError(
            view: WebView, request: WebResourceRequest, error: WebResourceError
        ) {
            if (request.isForMainFrame) {
                lastLoadFailed = true
                pageAlive = false
                loadingView.visibility = View.GONE
                showErrorCard()
                scheduleRetry(resolveEpoch) // a failed page load self-heals too
            }
        }

        override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
            lastLoadFailed = false
            pageAlive = false
            errorView.visibility = View.GONE
        }

        override fun onPageFinished(view: WebView, url: String?) {
            // The page is up; its own status pill takes over from here.
            // (onPageFinished fires after onReceivedError too — a failed
            // load must not count as a live document.)
            pageAlive = !lastLoadFailed
            loadingView.visibility = View.GONE
        }
    }

    private inner class Chrome : WebChromeClient() {
        override fun onShowFileChooser(
            webView: WebView,
            filePathCallback: ValueCallback<Array<Uri>>,
            fileChooserParams: FileChooserParams
        ): Boolean {
            fileCallback?.onReceiveValue(arrayOf())
            fileCallback = filePathCallback
            // The page's inputs say what they want (owner 2026-08-04):
            // capture -> the camera itself; multiple -> multi-select picker;
            // otherwise a single pick of the input's accept type.
            val accept = fileChooserParams.acceptTypes
                ?.firstOrNull { !it.isNullOrBlank() } ?: "*/*"
            beginExcursion()   // the page is about to be hidden BY US
            when {
                fileChooserParams.isCaptureEnabled ->
                    if (checkSelfPermission(Manifest.permission.CAMERA) ==
                        PackageManager.PERMISSION_GRANTED
                    ) launchCamera()
                    else cameraPermission.launch(Manifest.permission.CAMERA)
                fileChooserParams.mode == FileChooserParams.MODE_OPEN_MULTIPLE ->
                    multiPicker.launch(accept)
                else -> filePicker.launch(accept)
            }
            return true
        }
    }

    private companion object {
        const val PING_TIMEOUT_MS = 3000
        const val RETRY_INTERVAL_MS = 4000L
        // Must match the manifest's <queries> entry and the page's Play Store
        // link (client/index.html) — one package name, three places.
        const val TAILSCALE_PKG = "com.tailscale.ipn"
    }
}
