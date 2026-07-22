package com.uvuruna.remoteuser

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions

/** First run: bind this phone to the PC. One screen, one job — scan the QR
 *  the PC window shows (or paste the link). Every later step, including the
 *  Tailscale "use from anywhere" setup, is guided by the loaded page itself,
 *  so the guidance exists exactly once (in the web client) for browser and
 *  app alike. */
class OnboardingActivity : AppCompatActivity() {

    private val scanner = registerForActivityResult(ScanContract()) { result ->
        result.contents?.let { tryConnect(it) }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
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
        openClient()
    }

    private fun openClient() {
        startActivity(Intent(this, MainActivity::class.java))
        finish()
    }
}
