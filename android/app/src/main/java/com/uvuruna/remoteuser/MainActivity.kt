package com.uvuruna.remoteuser

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
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
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
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
 *    end: it re-probes by itself on a timer and on every network change
 *  - a one-time heads-up when the session runs over an unfamiliar Wi-Fi
 *  - `Android.rescan()` / `Android.setTailscaleUrl()` JS bridge
 *  - the screen stays on; rotation never recreates the session; leaving the
 *    app pauses the page (its visibility rule closes the stream — owner
 *    security decision)
 */
class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView
    private lateinit var errorView: View
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
            fileCallback?.onReceiveValue(if (uri != null) arrayOf(uri) else arrayOf())
            fileCallback = null
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

        errorView = findViewById(R.id.error_view)
        loadingView = findViewById(R.id.loading_view)
        findViewById<Button>(R.id.btn_retry).setOnClickListener { resolveAndLoad() }
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
        handler.removeCallbacksAndMessages(null)
        super.onDestroy()
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
                    } else {
                        web.loadUrl(chosen) // loader (or card) stays until the page reacts
                    }
                } else {
                    loadingView.visibility = View.GONE
                    errorView.visibility = View.VISIBLE
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

    override fun onPause() {
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

        /** The page's auto quality mode: reduced stream only on mobile data
         *  (owner spec 2026-08-02). "cellular" / "wifi" / "". */
        @JavascriptInterface
        fun transport(): String = when {
            onCellular -> "cellular"
            onWifi -> "wifi"
            else -> ""
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

        /** Update tap: open /app.apk (on the SAME PC) in the system browser —
         *  it downloads and Android installs over this app (same signature).
         *  The WebView itself has no download pipeline; the browser here is
         *  only the download UI. */
        @JavascriptInterface
        fun update(url: String) {
            runOnUiThread {
                try {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                } catch (e: Exception) {
                    // no browser to hand the download to — the page's toast
                    // already told the user what should have happened
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
                errorView.visibility = View.VISIBLE
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
            filePicker.launch("image/*")
            return true
        }
    }

    private companion object {
        const val PING_TIMEOUT_MS = 3000
        const val RETRY_INTERVAL_MS = 4000L
    }
}
