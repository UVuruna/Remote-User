package com.uvuruna.vibecoder

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.app.KeyguardManager
import android.os.Handler
import android.os.Looper
import android.os.PowerManager
import android.provider.Settings
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
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
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
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
 *  - the screen stays on; rotation never recreates the session; leaving the
 *    app pauses the page (its visibility rule closes the stream — owner
 *    security decision)
 *  - it starts NoticeService, the small waiting channel that lets an agent's
 *    notice reach this phone with no page at all (owner decree 2026-08-07)
 *
 *  The JS bridge itself — `window.Android`, every name the page calls — lives
 *  in Bridge.kt (split 2026-08-07, THE STRUCTURE LAW): being the window and
 *  being the page's protocol are two jobs, and only the second one is a
 *  compatibility surface that has to outlive both sides' versions.
 */
class MainActivity : AppCompatActivity() {

    // `internal`, not private: Insets.kt attaches the window-inset listener
    // to this view (split 2026-08-09).
    internal lateinit var web: WebView
    private lateinit var errorView: View
    private lateinit var errorTitle: TextView
    private lateinit var errorBody: TextView
    private lateinit var errorAction: Button
    private lateinit var loadingView: View
    private var fileCallback: ValueCallback<Array<Uri>>? = null

    private val handler = Handler(Looper.getMainLooper())
    private var connectivity: ConnectivityManager? = null
    private var resolveEpoch = 0 // UI thread only — voids stale resolver threads and timers
    // `internal` from here down = the shell capability surface Bridge.kt is
    // allowed to reach (split 2026-08-07). Nothing else in the app touches
    // them, and the short list is the point: if it grows, the seam moved.
    internal var onWifi = false // default network carries a Wi-Fi transport (UI thread only)
    @Volatile internal var onCellular = false // for the page's auto quality mode (any thread)
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
    internal var excursions = 0
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
        /** A NEW default network. This is the moment the loaded address may
         *  have stopped being the right one — home Wi-Fi to mobile data, a
         *  tunnel coming up, a foreign AP re-granting connectivity.
         *
         *  It used to re-resolve only `if (errorView.visibility == VISIBLE)`,
         *  and THAT is the owner's 2026-08-07 report. The error card is a
         *  cold-start state: it means no address answered before a page ever
         *  loaded. The state he is actually in is the opposite one — a page
         *  that loaded perfectly on the home Wi-Fi and is now retrying a
         *  192.168 host from a mobile network. In that state nothing here ran,
         *  nothing in the page could move it (its socket can only reach
         *  `location.host`), and the only code path that re-probes both
         *  addresses was a fresh process. So he killed the app, and it worked,
         *  every time — which is what made "Try again" look broken.
         *
         *  Resolving with a live page is safe by construction: `sessionHealthy`
         *  keeps a document whose own address still answers. */
        override fun onAvailable(network: Network) {
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                resolveAndLoad(silent = true)
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

    /** The page says it has lost the PC (Bridge.linkLost). Re-probe both
     *  addresses and move the document only if the other one is the live one.
     *
     *  Throttled, because the page asks after a RUN of failed connections and
     *  those runs can repeat while a network settles — and every resolve costs
     *  up to one ping timeout on each address. The throttle is deliberately
     *  shorter than the page's own escalation, so a real network change is
     *  never the one that gets swallowed. */
    private var lastPageAsk = 0L

    internal fun pageLostTheServer() {
        if (isFinishing || isDestroyed) return
        val now = android.os.SystemClock.elapsedRealtime()
        if (now - lastPageAsk < LINK_LOST_THROTTLE_MS) return
        lastPageAsk = now
        resolveAndLoad(silent = true)
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

    internal val audioPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            endExcursion()
            if (granted) voice.listen() else voice.deny()
        }

    /** The battery-optimisation dialog (owner decree 2026-08-07). A launcher
     *  rather than a bare startActivity for one reason that matters: it gives
     *  us the moment the user comes BACK, so the excursion count is balanced
     *  — an unbalanced one would make `hideReason()` answer "excursion"
     *  forever, and the PC would hold layout windows over his desk through
     *  every later screen lock. The page re-reads the state on return, so its
     *  card disappears the instant the exemption is granted. */
    private val batteryDialog =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
            endExcursion()
            if (::web.isInitialized) {
                web.evaluateJavascript(
                    "window.__noticeStateChanged && __noticeStateChanged()", null)
            }
        }

    /** Android 13+ asks before ANY app may raise a notification. Requested on
     *  the first notice rather than at startup: a user who never turns the
     *  feature on is never asked, and the ask arrives with its reason
     *  visible on screen (owner principle — nothing unexplained). */
    // A notice that arrived before the permission did (see `notify` below).
    // A named record rather than a Triple since 2026-08-08: it grew a fourth
    // field (where the tap leads), and `it.fourth` does not exist.
    internal data class Notice(val title: String, val text: String,
                               val tag: String, val jump: String = "")

    internal var pendingNotice: Notice? = null

    internal val notifyPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
            val held = pendingNotice
            pendingNotice = null
            if (granted) {
                held?.let { notifier.post(it.title, it.text, it.tag, it.jump) }
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
        // Task 204: re-assert the remembered rotation lock before the page has
        // even loaded — a fresh Activity instance (process reclaimed during an
        // excursion, an OEM quirk) otherwise starts unlocked and the page will
        // not call lockOrientation again unless the layout FOCUS itself changes.
        applyOrientationLock(Prefs.orientLock(this))
        askNotificationPermission()
        // The waiting channel (owner decree 2026-08-07). Started here and
        // never stopped by us: it outlives this Activity on purpose — the
        // whole point is that a notice reaches him when there is no page.
        // Started from onCreate because Android 12+ refuses a foreground
        // service start from the background, and this is the one moment the
        // app is certainly in the foreground.
        NoticeService.start(this)

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
            userAgentString = "$userAgentString VibeCoderApp"
        }
        // No framework focus rectangle over our content: the page's keyboard
        // capture field is deliberately invisible, and any highlight drawn
        // around it is a bright bar across the top of the stream (owner
        // reported it five times — the page kills the CSS focus ring, this
        // kills the platform one). API 26 = our minSdk, so no guard needed.
        web.defaultFocusHighlightEnabled = false
        web.addJavascriptInterface(Bridge(this), "Android")
        web.webViewClient = Client()
        web.webChromeClient = Chrome()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                moveTaskToBack(true) // back = background, never kill the session by accident
            }
        })

        connectivity = (getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager)
            .also { it.registerDefaultNetworkCallback(netCallback) }

        // A COLD start begun by tapping a notification: the layout to jump to
        // is on the intent that launched us, and it is parked here until the
        // page has a layout list to act on (task 110).
        watchImeInsets()
        readNoticeJump(intent)
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
    internal val voice by lazy {
        VoiceInput(this) { code ->
            if (::web.isInitialized) web.evaluateJavascript(code, null)
        }
    }

    // ── Game controller ── lives in Gamepad.kt (build round G1, owner spec
    // 2026-08-07): the pad pairs with the PHONE and the WebView does not
    // reliably expose the Gamepad API, so this shell forwards its keys and
    // sticks to the page — which owns the whole mapping.
    internal val pad by lazy {
        Gamepad { code -> if (::web.isInitialized) web.evaluateJavascript(code, null) }
    }

    /** Pad keys are taken BEFORE the view hierarchy sees them: the WebView's
     *  own D-pad focus handling would otherwise fight the mapping for every
     *  arrow press. Everything that is not a pad falls straight through. */
    override fun dispatchKeyEvent(event: KeyEvent): Boolean =
        pad.key(event) || super.dispatchKeyEvent(event)

    override fun dispatchGenericMotionEvent(event: MotionEvent): Boolean =
        pad.motion(event) || super.dispatchGenericMotionEvent(event)

    // ── Notifications ── lives in Notifier.kt (ROADMAP Phase H, owner
    // 2026-08-05): a job on the PC finished, and the phone says WHICH agent.
    // Lazy, because most sessions never receive one.
    internal val notifier by lazy { Notifier(this) }

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
                    // Compared by ORIGIN, never by the whole string. `web.url`
                    // is what the DOCUMENT reports — the server's own path, a
                    // fragment the page added, a token re-issued since pairing
                    // — while the candidates are the addresses as PAIRING
                    // stored them. Matching those two texts character for
                    // character answered "is this the address that just
                    // answered?" with a no far too often, and every no is a
                    // reload of a session that was working. Which address we
                    // are on is the host and the port; the rest is the page's
                    // business.
                    val here = origin(current)
                    val sessionHealthy = silent && pageAlive && here != null &&
                        results.any { origin(it.first) == here && it.second }
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

    /** Which ADDRESS a page URL is — scheme, host and port, nothing else.
     *  Null for anything unparseable (about:blank, a data: URL), which can
     *  never be "the address that answered". */
    private fun origin(url: String?): String? {
        if (url.isNullOrBlank()) return null
        val u = Uri.parse(url)
        val host = u.host ?: return null
        return "${u.scheme}://$host:${u.port}"
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

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus && ::web.isInitialized) hideSystemBars()
    }

    internal fun repair() {
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
        // Task 204: an excursion (picker, permission dialog, the battery
        // exemption sheet) can return to a RECREATED Activity instance if
        // Android reclaimed the process while we were away — that instance's
        // `requestedOrientation` starts at the manifest default, unlocked,
        // and the page never re-sends lockOrientation on its own unless the
        // layout FOCUS changes, which it did not. Re-assert every resume;
        // it is a no-op when nothing was ever locked ("").
        applyOrientationLock(Prefs.orientLock(this))
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
    internal fun beginExcursion() {
        excursions++
    }

    internal fun endExcursion() {
        if (excursions > 0) excursions--
    }

    /** Is the screen actually off, or the device locked? This is the fact the
     *  page could never know and kept guessing wrong. isInteractive() is false
     *  from the moment the screen goes dark; the keyguard covers "screen on,
     *  but locked" (a lock button press on some OEM builds, a smart-lock
     *  timeout). Either one is the end of the session, full stop. */
    internal fun screenIsAway(): Boolean {
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
        // Whatever the pad is holding goes UP with us (build round G1): a
        // release this shell never sees would leave a PC mouse button down for
        // the rest of the session.
        pad.releaseAll()
        if (::web.isInitialized) web.onPause()
        super.onPause()
    }

    // ── The page's API surface ── lives in Bridge.kt (split 2026-08-07, THE
    // STRUCTURE LAW). Every method there is a name the PAGE calls, and the
    // page is served by the PC while this shell is installed separately — so
    // that list is a compatibility contract, a different job from being the
    // window. What Bridge needs of this Activity is exactly the `internal`
    // members above and the three helpers below; that list IS the shell's
    // capability surface, and making it visible was half the point.

    /** The real work behind `Bridge.lockOrientation` (task 204) — split out so
     *  `onCreate`/`onResume` can re-assert the REMEMBERED mode (Prefs) as well
     *  as the bridge reacting to a fresh call from the page. Must run on the
     *  UI thread; callers on it already (onCreate/onResume) call it directly,
     *  Bridge posts it via runOnUiThread. */
    internal fun applyOrientationLock(mode: String) {
        requestedOrientation = when (mode) {
            "portrait" -> android.content.pm.ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
            "landscape", "wide" -> android.content.pm.ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
            // FULL_SENSOR, not UNSPECIFIED (owner report 2026-08-12, the
            // tablet never rotated at full desktop): UNSPECIFIED means "no
            // preference", which bows to the SYSTEM auto-rotate switch — on a
            // tablet with rotation lock engaged that is a permanent pin, and
            // the app hides the system bars so the switch is not even in
            // reach. Free rotation here is an app decision, like a video
            // player's: follow the sensor in all four directions regardless
            // of the system toggle.
            else -> android.content.pm.ActivityInfo.SCREEN_ORIENTATION_FULL_SENSOR
        }
    }

    /** Mic tap: the recogniser needs a runtime grant, and asking for one
     *  hides the page — which the shell must count as an EXCURSION or the PC
     *  hands the owner's windows back mid-sentence (presence). Kept here
     *  rather than in Bridge because permission launchers are the Activity's. */
    internal fun startVoiceInput() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        ) voice.listen()
        else {
            beginExcursion()   // the permission dialog hides the page
            audioPermission.launch(Manifest.permission.RECORD_AUDIO)
        }
    }

    /** One notice, arriving while the owner IS looking at the app. Same
     *  reason as above: the permission launcher lives here. */
    internal fun postNotice(title: String, text: String, tag: String,
                            jump: String = "") {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED) {
            // Ask, and REMEMBER what was being said — the notice used to be
            // dropped here ("this one is lost; the next lands"), which is how
            // the owner's first agent finish arrived as a toast and never
            // reached his notification tray (2026-08-06). It is posted the
            // moment he grants it.
            pendingNotice = Notice(title, text, tag, jump)
            notifyPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
            return
        }
        notifier.post(title, text, tag, jump)
    }

    // ── Where a tapped notice leads (owner 2026-08-08, task 110) ──────────
    // "da klikom na notifikaciju nas odvede do tog layouta … gde je zavrsio
    // taj sabagent ili glavni agent."
    //
    // The tap may COLD-START this app, so the answer cannot be pushed at a
    // page that does not exist yet. It is parked here and PULLED by the page
    // (Bridge.noticeJump) once it knows its layout list — and taken exactly
    // once, so a later reconnect cannot replay a jump he already made.
    private var noticeJump = ""

    internal fun takeNoticeJump(): String {
        val held = noticeJump
        noticeJump = ""
        return held
    }

    /** A tap arrived. Park it, and nudge the page in case one is already up —
     *  the nudge only tells it to LOOK; the answer still comes from the pull
     *  above, so there is one path and not two. */
    private fun readNoticeJump(intent: Intent?) {
        val jump = intent?.getStringExtra(Notifier.EXTRA_JUMP).orEmpty()
        if (jump.isBlank()) return
        noticeJump = jump
        intent?.removeExtra(Notifier.EXTRA_JUMP)   // never re-read on rotation
        if (::web.isInitialized) {
            web.evaluateJavascript("window.__noticeJump && __noticeJump()", null)
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        readNoticeJump(intent)
    }

    /** Ask Android to stop deferring this app (owner decree 2026-08-07). The
     *  foreground service keeps the notice socket's PROCESS alive, but Doze
     *  can still hold its traffic until the phone next wakes — which is the
     *  very complaint the service exists to fix. Only the user can grant
     *  this, so the page explains it in his own words and this opens the
     *  system dialog; a refusal is a state, never an error.
     *
     *  On a phone whose OEM has removed the dialog the intent resolves to
     *  nothing — the general battery-settings screen is the fallback, and the
     *  page's card still says what to look for there. */
    internal fun askBatteryExemption() {
        beginExcursion()   // a system dialog hides the page — not a leave
        try {
            batteryDialog.launch(NoticeService.batteryIntent(this))
        } catch (e: Exception) {
            try {
                batteryDialog.launch(
                    Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            } catch (e2: Exception) {
                endExcursion()
                Toast.makeText(this, R.string.notice_battery_no_screen,
                    Toast.LENGTH_LONG).show()
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
            // A new document has no `window.__imeHeight` history — the shell's
            // memo of the last pushed inset does, and it outlives the page.
            // Forget it and re-deliver, or a keyboard reopened at the same
            // height after a reload is never announced (see Insets.kt).
            forgetImeInset()
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
        // Floor between two page-driven re-probes (see pageLostTheServer).
        const val LINK_LOST_THROTTLE_MS = 5000L
        // Must match the manifest's <queries> entry and the page's Play Store
        // link (client/index.html) — one package name, three places.
        const val TAILSCALE_PKG = "com.tailscale.ipn"
    }
}
