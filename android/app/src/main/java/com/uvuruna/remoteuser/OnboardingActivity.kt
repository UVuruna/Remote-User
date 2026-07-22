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
 *  The manual card (scan the QR / paste the link) stays as the fallback and
 *  for re-pairing. Every later step, including the Tailscale "use from
 *  anywhere" setup, is guided by the loaded page itself, so the guidance
 *  exists exactly once (in the web client). */
class OnboardingActivity : AppCompatActivity() {

    private val scanner = registerForActivityResult(ScanContract()) { result ->
        result.contents?.let { tryConnect(it) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val handed = intent?.data?.takeIf { it.scheme == "remoteuser" }?.getQueryParameter("url")
        if (handed != null && handed.startsWith("http") && handed.contains("token=")) {
            tryConnect(handed) // the funnel's "Open the app" — paired, done
            return
        }
        Prefs.lanUrl(this)?.let {
            openClient()
            return
        }
        setContentView(R.layout.activity_onboarding)

        findViewById<Button>(R.id.btn_scan).setOnClickListener {
            scanner.launch(ScanOptions().apply {
                setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                setPrompt(getString(R.string.scan_qr))
                setBeepEnabled(false)
                setOrientationLocked(true)
            })
        }
        findViewById<Button>(R.id.btn_connect).setOnClickListener {
            tryConnect(findViewById<EditText>(R.id.link_input).text.toString().trim())
        }
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
        startActivity(Intent(this, MainActivity::class.java))
        finish()
    }
}
