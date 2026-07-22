package com.uvuruna.remoteuser

import android.annotation.SuppressLint
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
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
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
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
 *  - a native error card when no address answers (retry / re-pair)
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

        resolveAndLoad()
    }

    /** Probes /ping on every stored address in parallel and loads the first
     *  reachable one — LAN preferred (lower latency), Tailscale the fallback
     *  (mobile data, away from home). Waiting on the WebView's own timeout
     *  (~2 min of blank screen) is exactly the failure this replaces; no
     *  probe answering shows the native card within ~3 s instead. */
    private fun resolveAndLoad() {
        errorView.visibility = View.GONE
        loadingView.visibility = View.VISIBLE // "Connecting…" until the page loads or an address fails
        val candidates = listOfNotNull(Prefs.lanUrl(this), Prefs.tsUrl(this)).distinct()
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
            val chosen = probes.firstOrNull { (_, probe) ->
                try {
                    // A slow-but-alive probe legitimately spends up to
                    // connectTimeout + readTimeout — waiting any less
                    // declares a reachable server dead (cold DERP relay).
                    probe.get(2L * PING_TIMEOUT_MS + 500L, TimeUnit.MILLISECONDS)
                } catch (e: Exception) {
                    false
                }
            }?.first
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                if (chosen != null) {
                    web.loadUrl(chosen) // loader stays until onPageFinished
                } else {
                    loadingView.visibility = View.GONE
                    errorView.visibility = View.VISIBLE
                }
            }
        }.start()
    }

    /** True when the server answers the auth-free reachability probe. */
    private fun pingOk(pageUrl: String): Boolean = try {
        val u = Uri.parse(pageUrl)
        val conn = URL("${u.scheme}://${u.host}:${u.port}/ping").openConnection() as HttpURLConnection
        conn.connectTimeout = PING_TIMEOUT_MS
        conn.readTimeout = PING_TIMEOUT_MS
        try {
            conn.responseCode in 200..299
        } finally {
            conn.disconnect()
        }
    } catch (e: Exception) {
        false
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
        val current = web.url ?: return
        Thread {
            if (!pingOk(current)) {
                runOnUiThread {
                    if (!isFinishing && !isDestroyed) resolveAndLoad()
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
                loadingView.visibility = View.GONE
                errorView.visibility = View.VISIBLE
            }
        }

        override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
            errorView.visibility = View.GONE
        }

        override fun onPageFinished(view: WebView, url: String?) {
            // The page is up; its own status pill takes over from here.
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
    }
}
