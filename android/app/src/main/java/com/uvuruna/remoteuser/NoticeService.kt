package com.uvuruna.remoteuser

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.provider.Settings
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import org.json.JSONObject

/**
 * The small service the owner asked for (decree 2026-08-07).
 *
 * His report: *"notifikacije mi stižu tek kada podignem aplikaciju iako je sve
 * vreme otvorena u pozadini"*. The cause was not a bug in the notice code — it
 * was that the notice rode the STREAMING socket, and that socket is closed on
 * purpose the moment the page hides (project CLAUDE.md constraint 8: the
 * session lives only while the owner is looking). At the exact moment a notice
 * matters there was no channel at all.
 *
 * His decision, and the shape of this file: *"Radimo taj mali servis — samo je
 * važno da ta komunikacija koja mora da bude u pozadini bude minimalna …
 * android strana čeka signal, ne prima ništa od kompjutera, ali ostane u
 * stanju čekanja signala."*
 *
 * WHAT THIS IS NOT: it is not a second session. It never loads the page, never
 * opens the stream, never touches input, and the PC does not count it as a
 * present phone — `/notices` is a route of its own that never enters the
 * one-device slot presence is built on (server/notify.py). The security rule
 * and the topmost ledger and the layout defence all keep working exactly as
 * before: when the page hides, the session dies.
 *
 * WHY A FOREGROUND SERVICE AT ALL: a background thread would be killed within
 * minutes and its socket with it, and Android would defer its traffic long
 * before that. A foreground service is the only way to hold a socket open for
 * hours, and Android's price for it is a permanent notification the user
 * cannot dismiss. That notification is therefore written to be worth reading
 * (see `ongoing()`): it says what it is doing and it opens the app.
 *
 * FOREGROUND SERVICE TYPE — `connectedDevice`, and it is the honest one. This
 * service exists to hold a network connection to ONE specific paired device,
 * the owner's own PC, which is exactly what that type is for. `dataSync` would
 * be the lazy pick and is wrong twice over: nothing is being synchronised, and
 * Android 15 deprecated it with a six-hour cap that would kill this at the end
 * of every working day. `specialUse` is the escape hatch for things with no
 * honest type; this one has one.
 */
class NoticeService : Service() {

    companion object {
        private const val TAG = "NoticeService"
        private const val CHANNEL_ID = "notice_waiting"
        private const val ONGOING_ID = 4711

        /** Whether the service is up — read by the page's notice card.
         *  Written only by the service's own onCreate/onDestroy. */
        @Volatile
        var running = false
            internal set

        fun start(ctx: Context) {
            val intent = Intent(ctx, NoticeService::class.java)
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    ctx.startForegroundService(intent)
                } else {
                    ctx.startService(intent)
                }
            } catch (e: Exception) {
                // Android 12+ refuses a foreground start from the background.
                // We only ever start from MainActivity.onCreate, so this is
                // the pathological case — logged, never crashed: the app's
                // real job is the screen in front of him.
                Log.w(TAG, "Could not start the notice service", e)
            }
        }

        fun stop(ctx: Context) {
            ctx.stopService(Intent(ctx, NoticeService::class.java))
        }

        /** Is this app exempt from Doze's battery optimisation?
         *
         *  It matters more than it sounds. The foreground service keeps the
         *  PROCESS alive, but Doze can still defer an unexempted app's network
         *  traffic while the device is idle — which for us means a notice
         *  sitting on the wire until the phone next wakes, i.e. exactly the
         *  complaint this whole round is fixing. The exemption is the user's
         *  to grant and nobody else's, so the app explains and asks; it never
         *  pretends to have it. */
        fun batteryExempt(ctx: Context): Boolean {
            val power = ctx.getSystemService(Context.POWER_SERVICE) as? PowerManager
                ?: return false
            return power.isIgnoringBatteryOptimizations(ctx.packageName)
        }

        /** The system dialog that grants it. Directed at THIS app, so it is
         *  one tap; the page has already explained why by the time it opens. */
        fun batteryIntent(ctx: Context): Intent =
            Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                Uri.parse("package:${ctx.packageName}"))
    }

    // Built on the FIRST notice, not at start: an idle service must cost
    // nothing, and a text-to-speech engine bound all night for the sake of a
    // sentence that may never come is not nothing. The engine queues what it
    // is asked to say until it is ready, so the first notice is not lost —
    // only slightly late (Notifier.speak). A plain nullable rather than a
    // `by lazy`, because onDestroy must be able to ask "was one ever built?"
    // without BUILDING one to shut it down.
    private var notifier: Notifier? = null

    private fun notifier(): Notifier =
        notifier ?: Notifier(applicationContext).also { notifier = it }

    private val link = NoticeLink(
        addresses = { Prefs.addresses(applicationContext) },
        onNotice = { deliver(it) },
    )

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
        ServiceCompat.startForeground(
            this, ONGOING_ID, ongoing(),
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q)
                ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE else 0,
        )
        running = true
        link.start()
        Log.i(TAG, "Waiting for the PC to call")
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // START_STICKY: if Android reclaims the process under memory pressure
        // it brings the service back by itself, and the link reconnects. A
        // notice channel that quietly stayed dead until the next app launch
        // would be the same failure in a new place.
        link.start()
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        link.stop()
        notifier?.release()
        notifier = null
        super.onDestroy()
    }

    // ── One notice, arriving with nobody looking ─────────────────────────
    /** The frame is exactly what the page would have received, so what
     *  happens to it is exactly what client/notify.js does with it: raise a
     *  banner tagged with the agent, and say it out loud in the voice and at
     *  the pace the PC chose. The user's own switches are honoured too —
     *  they live in the page's preference store, and the page is not here to
     *  read them, so we read the same store it writes.
     *
     *  The page's third carrier, the toast, is deliberately absent: there is
     *  no page on screen to toast onto. */
    private fun deliver(msg: JSONObject) {
        val prefs = getSharedPreferences(Prefs.CLIENT_FILE, MODE_PRIVATE)
            .getString("p_notifyPrefs", "") ?: ""
        var banner = true
        var speak = true
        if (prefs.isNotBlank()) {
            try {
                val p = JSONObject(prefs)
                banner = p.optBoolean("banner", true)
                speak = p.optBoolean("speak", true)
            } catch (e: Exception) {
                Log.w(TAG, "Unreadable notify preferences — using the defaults", e)
            }
        }
        val agent = msg.optString("agent", "agent")
        val title = msg.optString("title").ifBlank { agent }
        val body = listOf(msg.optString("text"), whenWord(msg.optLong("at")))
            .filter { it.isNotBlank() }
            .joinToString(" · ")
        if (banner) notifier().post(title, body, agent)
        if (speak && msg.optBoolean("speak", true)) {
            notifier().speak(
                if (body.isBlank()) title else "$title. $body",
                msg.optString("voice"),
                msg.optDouble("rate", 1.0).toFloat(),
            )
        }
    }

    /** "8 min ago" — a notice held while the phone was unreachable must not
     *  pretend it has only this second arrived (owner 2026-08-06). Same rule
     *  and same wording as the page's `notifyWhen`. */
    private fun whenWord(at: Long): String {
        if (at <= 0) return ""
        val mins = (System.currentTimeMillis() / 1000 - at) / 60
        return when {
            mins < 1 -> ""
            mins < 60 -> "$mins min ago"
            else -> "${mins / 60} h ago"
        }
    }

    // ── The notification Android makes us show ───────────────────────────
    private fun createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        // MIN importance, no sound, no vibration, no badge: this line is a
        // legal requirement, not news. The AGENT notices come through the
        // separate high-importance "agents" channel (Notifier) and are the
        // only thing here that is ever allowed to make a sound.
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Waiting for your PC",
            NotificationManager.IMPORTANCE_MIN,
        ).apply {
            description = "The quiet line that lets agent notices reach this " +
                "phone while the app is closed. Android requires it to be shown."
            setShowBadge(false)
            enableVibration(false)
            setSound(null, null)
        }
        getSystemService(NotificationManager::class.java)?.createNotificationChannel(channel)
    }

    /** Android will not let this notification be hidden, so it is written to
     *  earn its place: it says what the app is doing and why, in the owner's
     *  plain language, and tapping it opens the app. Nothing about it is
     *  explained anywhere but on screen (owner principle). */
    private fun ongoing(): Notification {
        val open = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle(getString(R.string.notice_service_title))
            .setContentText(getString(R.string.notice_service_body))
            .setStyle(NotificationCompat.BigTextStyle()
                .bigText(getString(R.string.notice_service_body)))
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setOngoing(true)
            .setShowWhen(false)
            .setSilent(true)
            .setContentIntent(open)
            .build()
    }
}
