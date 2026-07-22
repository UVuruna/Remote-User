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

/** The client shell: a full-screen WebView on the stored pairing URL.
 *
 *  The page carries ALL the product UI and guidance; the shell adds only
 *  what a browser tab cannot:
 *  - external links (Google Play from the in-page Tailscale wizard) open as
 *    real apps, not inside the WebView
 *  - the file chooser (phone → PC image upload) is wired up
 *  - a native error card when the PC is unreachable (retry / re-pair)
 *  - `Android.rescan()` JS bridge — the page offers re-pairing when the
 *    token is rejected
 *  - the screen stays on; rotation never recreates the session; leaving the
 *    app pauses the page (its visibility rule closes the stream — owner
 *    security decision)
 */
class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView
    private lateinit var errorView: View
    private var fileCallback: ValueCallback<Array<Uri>>? = null

    private val filePicker =
        registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
            fileCallback?.onReceiveValue(if (uri != null) arrayOf(uri) else arrayOf())
            fileCallback = null
        }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val url = Prefs.url(this)
        if (url == null) {
            repair()
            return
        }
        setContentView(R.layout.activity_main)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        errorView = findViewById(R.id.error_view)
        findViewById<Button>(R.id.btn_retry).setOnClickListener {
            errorView.visibility = View.GONE
            web.loadUrl(Prefs.url(this) ?: url)
        }
        findViewById<Button>(R.id.btn_repair).setOnClickListener { repair() }

        web = findViewById(R.id.web)
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false // MSE video must start by itself
        }
        web.addJavascriptInterface(Bridge(), "Android")
        web.webViewClient = Client()
        web.webChromeClient = Chrome()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                moveTaskToBack(true) // back = background, never kill the session by accident
            }
        })

        web.loadUrl(url)
    }

    private fun repair() {
        Prefs.setUrl(this, null)
        startActivity(Intent(this, OnboardingActivity::class.java))
        finish()
    }

    /** Page pauses when the app does — the client's visibility rule then
     *  closes the WebSocket (nothing runs while nobody is looking). */
    override fun onResume() {
        super.onResume()
        if (::web.isInitialized) web.onResume()
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
    }

    private inner class Client : WebViewClient() {
        override fun shouldOverrideUrlLoading(
            view: WebView, request: WebResourceRequest
        ): Boolean {
            val target = request.url
            val home = Uri.parse(Prefs.url(this@MainActivity) ?: return false)
            // Our server (any of its addresses shares the port) stays inside;
            // everything else (Google Play, tailscale.com) opens as a real app.
            if (target.scheme?.startsWith("http") == true && target.port == home.port) {
                return false
            }
            return try {
                startActivity(Intent(Intent.ACTION_VIEW, target))
                true
            } catch (e: Exception) {
                true // no handler for the link — swallow rather than break the page
            }
        }

        override fun doUpdateVisitedHistory(view: WebView, url: String?, isReload: Boolean) {
            // The in-page wizard navigates to the works-anywhere link — persist
            // whatever tokened URL we end up on as the new home.
            if (url != null && url.startsWith("http") && url.contains("token=")) {
                Prefs.setUrl(this@MainActivity, url)
            }
        }

        override fun onReceivedError(
            view: WebView, request: WebResourceRequest, error: WebResourceError
        ) {
            if (request.isForMainFrame) {
                errorView.visibility = View.VISIBLE
            }
        }

        override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
            errorView.visibility = View.GONE
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
}
