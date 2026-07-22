package com.uvuruna.remoteuser

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions

/** First run: bind this phone to the PC.
 *
 *  The normal path is fully automatic: the install funnel page (what an
 *  Android browser sees on the QR link) launches us via
 *  `remoteuser://pair?url=…` with the tokened URL — one tap, connected.
 *  Because the activity is singleTask, that launch lands in onCreate OR
 *  onNewIntent (when an instance is already alive — e.g. the user tapped
 *  "Open" on the package installer first); both feed handlePairIntent.
 *  The manual card (scan the QR / paste the link) stays as the fallback and
 *  for re-pairing (EXTRA_FORCE skips the already-paired shortcut WITHOUT
 *  wiping the stored addresses — they survive until a NEW pairing succeeds).
 *  Every later step, including the Tailscale "use from anywhere" setup, is
 *  guided by the loaded page itself, so the guidance exists exactly once. */
class OnboardingActivity : AppCompatActivity() {

    private val scanner = registerForActivityResult(ScanContract()) { result ->
        result.contents?.let { tryConnect(it) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (handlePairIntent(intent)) return
        val forced = intent?.getBooleanExtra(EXTRA_FORCE, false) == true
        if (!forced) {
            Prefs.lanUrl(this)?.let {
                openClient()
                return
            }
        }
        setContentView(R.layout.activity_onboarding)

        findViewById<Button>(R.id.btn_scan).setOnClickListener {
            scanner.launch(ScanOptions().apply {
                setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                setPrompt(getString(R.string.scan_qr))
                setBeepEnabled(false)
                // false = follow the phone's orientation (portrait when held
                // upright); the default (true) forced the scanner to landscape.
                setOrientationLocked(false)
            })
        }
        findViewById<Button>(R.id.btn_connect).setOnClickListener {
            tryConnect(findViewById<EditText>(R.id.link_input).text.toString().trim())
        }
    }

    /** singleTask: a funnel launch while an instance is alive is delivered
     *  HERE, not to onCreate — without this override the tokened URL was
     *  silently dropped and the empty pairing card just came forward. */
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handlePairIntent(intent)
    }

    /** True when the intent carried a valid pairing URL and we acted on it. */
    private fun handlePairIntent(intent: Intent?): Boolean {
        val handed = intent?.data?.takeIf { it.scheme == "remoteuser" }?.getQueryParameter("url")
        if (handed != null && handed.startsWith("http") && handed.contains("token=")) {
            tryConnect(handed)
            return true
        }
        return false
    }

    private fun tryConnect(url: String) {
        if (!url.startsWith("http") || !url.contains("token=")) {
            Toast.makeText(this, R.string.bad_link, Toast.LENGTH_LONG).show()
            return
        }
        Prefs.setLanUrl(this, url)
        Prefs.setTsUrl(this, null) // may be a new PC/token — relearned on first connect
        openClient()
    }

    private fun openClient() {
        // CLEAR_TASK: a funnel re-pair arrives while an old MainActivity may
        // still be alive in the task — without this, every re-pair stacked
        // another full WebView instance that nothing ever finished.
        startActivity(
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK)
        )
        finish()
    }

    companion object {
        const val EXTRA_FORCE = "force_pairing"
    }
}
