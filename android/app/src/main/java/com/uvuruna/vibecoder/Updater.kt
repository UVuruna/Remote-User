package com.uvuruna.vibecoder

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageInstaller
import android.os.Build
import android.util.Log
import java.io.IOException
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

/**
 * The in-app update path: stream `/app.apk` straight from the PC into a
 * [PackageInstaller] session's own [OutputStream], with no file ever written
 * to this app's storage.
 *
 * WHY NO FILE, NO FileProvider, NO DownloadManager: every one of those would
 * create something SHAREABLE — a path another app could be granted a URI to
 * — for the sole purpose of handing bytes to a system service that will
 * accept them directly over a stream. An install carries elevated trust by
 * definition, and a shareable copy of the APK sitting in cache is one more
 * surface a wrong grant, a backup, or a stray FileProvider path could point
 * at for no reason this feature needs. `PackageInstaller.Session.openWrite`
 * exists precisely so nothing has to touch disk outside the session Android
 * itself manages.
 *
 * `Bridge.updateInApp(url)` is the ONLY caller that starts a job; the
 * fallback `Bridge.update(url)` (opening `/app.apk` in the system browser)
 * is untouched and stays the path for a page served by a PC too old to know
 * about this one.
 *
 * THE MISSING SUCCESS STATE IS NOT AN OMISSION. A successful install of an
 * app over itself terminates this very process — there is no later moment
 * in which a "success" callback could still reach a page that no longer has
 * a process to run in. The page's own reload, once the new version restarts
 * it, is the only signal a successful update can ever produce.
 *
 * ONE JOB AT A TIME, ONE THREAD, ONE SESSION. `running` is the whole guard,
 * and it stays true from `start()` all the way through the system's confirm
 * dialog — not just through the download — because `PackageInstaller`'s
 * `commit()` is ASYNCHRONOUS: the dialog can still be on screen with the
 * receiver not yet fired, and a second `start()` in that window would open a
 * second download and a second session. Every terminal path — a real
 * failure, an abort, or a cancellation — clears it so a later tap always
 * works; a real SUCCESS never has to, because it terminates this very
 * process (see below), which is why that branch is the one asymmetric case.
 *
 * THE URL IS UNTRUSTED, EVEN THOUGH THE PAGE USUALLY ISN'T. This shell loads
 * its page over plain HTTP on the LAN (the QR encodes an `http://` address;
 * `MainActivity`'s own foreign-Wi-Fi warning already treats injected content
 * as a real threat this codebase accounts for), and every
 * `@JavascriptInterface` method is reachable from whatever script the
 * WebView currently holds — that is what "bridge" means. `update(url)`
 * always had this exposure, but it only ever opened a browser download the
 * user had to find and tap; this path downloads by itself and raises the
 * system's install-confirm dialog directly, so the distance from "script ran
 * in the WebView" to "an install dialog is up" is now one function call.
 * `start()` therefore accepts a url ONLY when it names one of THIS shell's
 * own two stored, paired addresses (`Prefs.lanUrl`/`Prefs.tsUrl`) and the
 * exact path `/app.apk` — compared by PARSED scheme/host/port, never by a
 * string prefix, because a prefix check is exactly what
 * `http://evil.com/?x=http://192.168.1.5/app.apk` or
 * `http://192.168.1.5.evil.com/app.apk` are built to defeat.
 *
 * VALIDATING THE URL WE ASKED FOR PROVES NOTHING ABOUT WHERE THE BYTES WE
 * GET BACK ACTUALLY CAME FROM. `isPairedApkUrl` checks the address this
 * class is about to REQUEST; `HttpURLConnection`'s own automatic redirect
 * following would then let whatever answered that request send back a 3xx
 * pointing anywhere at all, silently, with the bytes we install coming from
 * that new host instead — and the threat model here is exactly a party who
 * CAN answer on the LAN, so a redirect is a trivial bypass of the whole
 * check above it, not an edge case. `openValidated()` therefore never sets
 * `instanceFollowRedirects = true`; it follows redirects ITSELF, one hop at
 * a time, re-running `isPairedApkUrl` on every `Location` before it is
 * followed — see that function for the bound on how many hops are allowed.
 */
class Updater(
    context: Context,
    private val onProgress: (received: Long, total: Long) -> Unit,
    private val onState: (state: String, detail: String) -> Unit,
) {
    // The receiver and the install session both need to outlive any one
    // Activity instance's own lifetime concerns (this shell never recreates
    // MainActivity across rotation, but nothing here should assume that) —
    // applicationContext, not the Activity passed in, is what this class
    // actually holds on to.
    private val appCtx = context.applicationContext

    companion object {
        private const val TAG = "Updater"
        private const val CONNECT_TIMEOUT_MS = 10_000
        private const val READ_TIMEOUT_MS = 30_000
        private const val CHUNK_SIZE = 8 * 1024
        // The page's WebView bridge is not built for a call per chunk — 8 KB
        // steps on a fast LAN would be hundreds of calls a second. Reports
        // are gated by BOTH a byte step and a time step when the total size
        // is known (the "whichever is rarer" rule), and by time alone when
        // it is not (chunked transfer — Content-Length absent).
        private const val PROGRESS_MIN_INTERVAL_MS = 100L
        // A private action: this receiver answers ONLY our own session's
        // commit, nothing in the manifest declares it, and nothing outside
        // this process may ever trigger it.
        private const val ACTION_INSTALL = "com.uvuruna.vibecoder.action.INSTALL_UPDATE"
        // This app's own /app.apk is served as a plain static file and has
        // never needed a redirect — but assuming that stays true forever is
        // exactly the assumption `openValidated()` exists to not make. A
        // small bound, not zero: it lets a legitimate one-hop redirect (a
        // trailing slash, a scheme normalisation) still work while making a
        // redirect loop terminate quickly instead of spinning forever.
        private const val MAX_REDIRECTS = 3

        /** Builds the instance against `host`'s own `evaluateJavascript`
         *  sink — the same shape as the `notifier`/`pad` fields beside it in
         *  MainActivity, kept HERE rather than as a block in MainActivity's
         *  own `by lazy` so that file stays a one-liner: the update job,
         *  including its callback wiring, is entirely this class's
         *  responsibility. Every callback fires from a background thread
         *  (see `downloadAndInstall`), so each one hops to the UI thread
         *  itself before touching the WebView — `host::web.isInitialized`
         *  is the same lateinit guard the rest of the shell uses, checked
         *  through a property reference since `web` is not this class's own
         *  field. */
        fun attach(host: MainActivity): Updater = Updater(
            host,
            onProgress = { received, total ->
                host.runOnUiThread {
                    if (host::web.isInitialized) host.web.evaluateJavascript(
                        "window.__updateProgress && __updateProgress($received, $total)", null)
                }
            },
            onState = { state, detail ->
                host.runOnUiThread {
                    if (host::web.isInitialized) host.web.evaluateJavascript(
                        "window.__updateState && __updateState(" +
                            "${JSONObject.quote(state)}, ${JSONObject.quote(detail)})",
                        null)
                }
            },
        )
    }

    @Volatile private var running = false
    @Volatile private var activeConnection: HttpURLConnection? = null
    @Volatile private var session: PackageInstaller.Session? = null
    private var thread: Thread? = null
    private var receiverRegistered = false

    /** A download the page asked for while the "install unknown apps" grant
     *  was still missing. Held so `onAppResumed()` can finish the job the
     *  instant the user comes back from Settings having flipped it — never a
     *  second tap, per the project's "automatic continuation" rule. */
    @Volatile private var pendingUrl: String? = null

    fun canInstall(): Boolean = appCtx.packageManager.canRequestPackageInstalls()

    /** `Bridge.updateInApp`'s whole body. Returns whether THIS call put a job
     *  in flight — false when one already is, the url is not one of THIS
     *  shell's own paired addresses (see the class header — the page is
     *  untrusted input, not a trusted caller), or the permission is missing
     *  (in which case `onState("permission", "")` fires instead and the url
     *  is remembered for `onAppResumed()`). */
    fun start(url: String): Boolean {
        if (running) return false
        if (!isPairedApkUrl(url)) {
            Log.w(TAG, "Refused an update url that is not a paired PC's /app.apk: $url")
            onState("failed", "That update address does not belong to this app's paired PC.")
            return false
        }
        if (!canInstall()) {
            pendingUrl = url
            onState("permission", "")
            return false
        }
        pendingUrl = null
        beginDownload(url)
        return true
    }

    /** Is `url` one of THIS shell's own two stored, paired addresses
     *  (`Prefs.lanUrl`/`Prefs.tsUrl` — the same pair `MainActivity` probes)
     *  at the exact path `/app.apk`? Compared by PARSED scheme, host and
     *  port, never by a string prefix — see the class header for why a
     *  prefix check is not safe here. A stored address with no explicit port
     *  and the incoming url with one (or vice versa) must still match, so
     *  the comparison resolves each side's DEFAULT port for its scheme
     *  rather than comparing raw `-1` against a real number. */
    private fun isPairedApkUrl(url: String): Boolean {
        val target = try { URL(url) } catch (e: Exception) { return false }
        if (target.path != "/app.apk") return false
        val paired = listOfNotNull(Prefs.lanUrl(appCtx), Prefs.tsUrl(appCtx))
        return paired.any { stored ->
            val storedUrl = try { URL(stored) } catch (e: Exception) { return@any false }
            storedUrl.protocol.equals(target.protocol, ignoreCase = true) &&
                storedUrl.host.equals(target.host, ignoreCase = true) &&
                effectivePort(storedUrl) == effectivePort(target)
        }
    }

    private fun effectivePort(url: URL): Int = if (url.port == -1) url.defaultPort else url.port

    /** Opens `url` and follows redirects OURSELVES, hop by hop — this is
     *  the ONE place in this class allowed to follow one, and that is
     *  deliberate: `HttpURLConnection.instanceFollowRedirects = true` would
     *  let whatever answers the request send back a 3xx pointing ANYWHERE,
     *  silently, and the bytes this class then installs would come from
     *  that new host — a trivial bypass of `isPairedApkUrl`, which only
     *  ever validated the url we ASKED for, never the one that actually
     *  answered. So `instanceFollowRedirects` is always false here, and
     *  every `Location` is resolved against the CURRENT url (a relative
     *  `Location` is legal and common), re-checked through the SAME
     *  `isPairedApkUrl`, and only followed if it passes — exactly like the
     *  very first url was. `MAX_REDIRECTS` bounds the loop so a malicious or
     *  misconfigured redirect chain cannot spin forever.
     *
     *  This app's own PC serves `/app.apk` as a plain static file and has
     *  never actually needed a redirect — but that is not a reason to trust
     *  `instanceFollowRedirects`; it is the reason this path is exercised
     *  rarely enough that ANY shortcut here would ship untested. Handling it
     *  explicitly is the safe default regardless of what today's server
     *  does. */
    private fun openValidated(url: String): HttpURLConnection {
        var current = url
        var hops = 0
        while (true) {
            val conn = (URL(current).openConnection() as HttpURLConnection).apply {
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                instanceFollowRedirects = false
                useCaches = false
            }
            activeConnection = conn
            val code = conn.responseCode
            val isRedirect = code == HttpURLConnection.HTTP_MOVED_PERM ||   // 301
                code == HttpURLConnection.HTTP_MOVED_TEMP ||                // 302
                code == HttpURLConnection.HTTP_SEE_OTHER ||                 // 303
                code == 307 || code == 308                                  // no HttpURLConnection consts
            if (!isRedirect) return conn
            val location = conn.getHeaderField("Location")
            conn.disconnect()
            if (hops >= MAX_REDIRECTS) {
                Log.w(TAG, "Refused an update redirect chain longer than $MAX_REDIRECTS hops " +
                    "(started at $url)")
                throw IOException("The update redirected too many times.")
            }
            if (location.isNullOrBlank()) {
                throw IOException("The PC redirected the update with no destination.")
            }
            val resolved = try {
                URL(URL(current), location).toString()
            } catch (e: Exception) {
                throw IOException("The PC sent an unusable redirect.")
            }
            if (!isPairedApkUrl(resolved)) {
                Log.w(TAG, "Refused an update redirect to an unpaired address: $resolved")
                throw IOException("The update redirected somewhere that is not this app's paired PC.")
            }
            hops++
            current = resolved
        }
    }

    /** `MainActivity.onResume`'s hook: the one place a grant made in Settings
     *  is discovered. A no-op whenever nothing is waiting or the grant still
     *  is not there — cheap enough to call on every resume unconditionally. */
    fun onAppResumed() {
        val url = pendingUrl ?: return
        if (!canInstall() || running) return
        pendingUrl = null
        beginDownload(url)
    }

    /** The activity going away mid-download (owner's "never leak a session or
     *  a thread"). A session already COMMITTED cannot be recalled — the
     *  system's own confirm dialog is a fact by then — but everything still
     *  under our control is torn down: the socket, the write, the thread. */
    fun cancel() {
        running = false
        try {
            activeConnection?.disconnect()
        } catch (e: Exception) {
            Log.w(TAG, "Could not close the update download", e)
        }
        try {
            session?.abandon()
        } catch (e: Exception) {
            Log.w(TAG, "Could not abandon the install session", e)
        }
        session = null
        thread?.interrupt()
        thread = null
    }

    /** Undoes `ensureReceiver()`. Called once, from `MainActivity.onDestroy`,
     *  alongside `cancel()` — the receiver has application scope and nothing
     *  else in this class unregisters it. */
    fun release() {
        cancel()
        if (receiverRegistered) {
            try {
                appCtx.unregisterReceiver(installReceiver)
            } catch (e: Exception) {
                Log.w(TAG, "Could not unregister the install receiver", e)
            }
            receiverRegistered = false
        }
    }

    private fun beginDownload(url: String) {
        running = true
        thread = Thread({ downloadAndInstall(url) }, "apk-updater").apply {
            isDaemon = true
            start()
        }
    }

    /** Runs entirely on its own thread. Every callback it fires (`onProgress`,
     *  `onState`) is handed straight to the caller's lambda — hopping to the
     *  UI thread to reach the WebView is `MainActivity`'s job, since it is
     *  the one holding the `WebView` reference, not this class's. */
    private fun downloadAndInstall(url: String) {
        var installerSession: PackageInstaller.Session? = null
        var conn: HttpURLConnection? = null
        // Set the instant commit() succeeds. From then on `running` must
        // survive this function returning — the confirm dialog and the
        // system's own final broadcast are still ahead of us — so the
        // `finally` below must NOT clear it on the ordinary "we're done"
        // path the way every earlier version of this function did.
        var committed = false
        try {
            ensureReceiver()
            conn = openValidated(url)
            val code = conn.responseCode
            if (code != HttpURLConnection.HTTP_OK) {
                fail("The PC did not send the update (server said $code).")
                return
            }
            // -1 when the PC streams without a Content-Length (chunked
            // transfer) — PackageInstaller.openWrite treats -1 the same way,
            // as "size unknown", so this sentinel is passed straight through
            // rather than translated.
            val total = conn.contentLengthLong
            onState("downloading", "")
            onProgress(0, total)

            val installer = appCtx.packageManager.packageInstaller
            val params = PackageInstaller.SessionParams(
                PackageInstaller.SessionParams.MODE_FULL_INSTALL,
            )
            val sessionId = installer.createSession(params)
            installerSession = installer.openSession(sessionId)
            session = installerSession

            val received = streamInto(installerSession, conn, total)
            if (!running) {
                // Cancelled mid-stream — a half-written session must never be
                // left for PackageInstaller to trip over later.
                installerSession.abandon()
                return
            }
            onProgress(received, if (total > 0) total else received)

            val piFlags = PendingIntent.FLAG_UPDATE_CURRENT or
                (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S)
                    PendingIntent.FLAG_MUTABLE else 0)
            val statusIntent = Intent(ACTION_INSTALL).setPackage(appCtx.packageName)
            val pi = PendingIntent.getBroadcast(appCtx, sessionId, statusIntent, piFlags)
            installerSession.commit(pi.intentSender)
            committed = true
            // This THREAD's job ends here — what happens to the COMMITTED
            // session (the confirm dialog, a refusal, success) arrives later
            // on `installReceiver`, on whatever thread the system chooses to
            // deliver it on. `running` stays true; that receiver is the only
            // thing still allowed to clear it (defect 2 fix, 2026-08-17).
        } catch (e: IOException) {
            fail("Could not download the update: ${e.message ?: "a network error"}.")
            try {
                installerSession?.abandon()
            } catch (e2: Exception) { /* already gone */ }
        } catch (e: SecurityException) {
            fail("Android would not open an install session: " +
                (e.message ?: "permission denied") + ".")
            try {
                installerSession?.abandon()
            } catch (e2: Exception) { /* already gone */ }
        } catch (e: Exception) {
            Log.e(TAG, "Update download/install failed", e)
            fail("The update could not be prepared.")
            try {
                installerSession?.abandon()
            } catch (e2: Exception) { /* already gone */ }
        } finally {
            try {
                installerSession?.close()
            } catch (e: Exception) { /* already gone */ }
            try {
                conn?.disconnect()
            } catch (e: Exception) { /* already gone */ }
            activeConnection = null
            // Only clear `running` here when we did NOT reach a successful
            // commit — every exception path above returns/falls through with
            // `committed` still false, so this is exactly "the job ended
            // without handing off to the system". A committed job is still
            // in flight; `installReceiver`'s terminal branches (or `cancel`)
            // are what clear it from here on (defect 2 fix, 2026-08-17).
            if (!committed) running = false
        }
    }

    /** Copies the response body into the session's write stream, reporting
     *  progress as it goes. Returns the byte count actually written.
     *
     *  `fsync` MUST be called on the stream BEFORE it is closed — that is
     *  PackageInstaller's own contract, not a style choice, which is why the
     *  close lives in a `finally` around it rather than a `use {}` block that
     *  would close the stream first. */
    private fun streamInto(
        installerSession: PackageInstaller.Session,
        conn: HttpURLConnection,
        total: Long,
    ): Long {
        val out: OutputStream = installerSession.openWrite("update", 0, total)
        var received = 0L
        try {
            conn.inputStream.use { input ->
                var lastReportedBytes = 0L
                var lastReportedTime = System.currentTimeMillis()
                val byteGated = total > 0
                val onePercent = if (byteGated) (total / 100).coerceAtLeast(1L) else 0L
                val buf = ByteArray(CHUNK_SIZE)
                while (running) {
                    val n = input.read(buf)
                    if (n < 0) break
                    out.write(buf, 0, n)
                    received += n
                    val now = System.currentTimeMillis()
                    val timeDue = now - lastReportedTime >= PROGRESS_MIN_INTERVAL_MS
                    val byteDue = !byteGated || received - lastReportedBytes >= onePercent
                    if (timeDue && byteDue) {
                        onProgress(received, total)
                        lastReportedBytes = received
                        lastReportedTime = now
                    }
                }
            }
            if (running) installerSession.fsync(out)
        } finally {
            try {
                out.close()
            } catch (e: IOException) {
                Log.w(TAG, "Could not close the install session's write stream", e)
            }
        }
        return received
    }

    private fun fail(detail: String) {
        running = false
        onState("failed", detail)
    }

    private fun ensureReceiver() {
        if (receiverRegistered) return
        val filter = IntentFilter(ACTION_INSTALL)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            // Nothing outside this process may ever trigger our own
            // session's status broadcast — the action string is private and
            // Android 13+ lets us say so structurally instead of by
            // convention alone.
            appCtx.registerReceiver(installReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        } else {
            @Suppress("UnspecifiedRegisterReceiverFlag")
            appCtx.registerReceiver(installReceiver, filter)
        }
        receiverRegistered = true
    }

    /** The commit's own answer — registered at RUNTIME (never in the
     *  manifest: nothing needs to reach this from outside the app). Fires on
     *  whatever thread the system delivers a broadcast on, so every path out
     *  of it goes straight to `onState`/`onProgress`, which themselves are
     *  plain callbacks the owner hops to the UI thread from. */
    private val installReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            when (val status = intent.getIntExtra(
                PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)
            ) {
                PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                    val confirm = extraIntent(intent)
                    if (confirm == null) {
                        fail("The system did not offer an install screen.")
                        return
                    }
                    // We are not necessarily in an Activity context here (the
                    // broadcast can land after MainActivity is gone) —
                    // NEW_TASK is required and correct either way.
                    confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    try {
                        appCtx.startActivity(confirm)
                        onState("installing", "")
                    } catch (e: Exception) {
                        fail("Could not open the install confirmation screen.")
                    }
                }
                PackageInstaller.STATUS_SUCCESS -> {
                    // See the class header: a REAL success replaces this
                    // process before this line could ever run, which is
                    // exactly why `running` is left true on every other path
                    // until a terminal broadcast arrives — there is no
                    // "success" moment for that flag to wait for. Clearing
                    // it here anyway costs nothing and exists only so an
                    // unexpected extra broadcast (a platform quirk, a retry)
                    // can never fall into the failure branch below and
                    // report a lie.
                    running = false
                    session = null
                }
                else -> {
                    val msg = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE)
                    fail(readableFailure(status, msg))
                    session = null
                }
            }
        }
    }

    @Suppress("DEPRECATION")
    private fun extraIntent(intent: Intent): Intent? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java)
        } else {
            intent.getParcelableExtra(Intent.EXTRA_INTENT)
        }

    /** One short, plain-language sentence per PackageInstaller failure code —
     *  never the constant's own name, never a stack trace. A non-technical
     *  user reads this on the page's update card. */
    private fun readableFailure(status: Int, systemMessage: String?): String = when (status) {
        PackageInstaller.STATUS_FAILURE_ABORTED -> "The update was cancelled."
        PackageInstaller.STATUS_FAILURE_BLOCKED ->
            "The device blocked the install. Check for a restriction on unknown app sources."
        PackageInstaller.STATUS_FAILURE_CONFLICT ->
            "The update conflicts with something already on this device."
        PackageInstaller.STATUS_FAILURE_INCOMPATIBLE ->
            "This update is not compatible with this device."
        PackageInstaller.STATUS_FAILURE_INVALID -> "The downloaded update was not a valid app."
        PackageInstaller.STATUS_FAILURE_STORAGE -> "Not enough storage space for the update."
        else -> systemMessage?.takeIf { it.isNotBlank() }
            ?: "The update could not be installed."
    }
}
