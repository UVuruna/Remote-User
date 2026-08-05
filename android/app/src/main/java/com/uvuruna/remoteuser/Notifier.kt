package com.uvuruna.remoteuser

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.speech.tts.TextToSpeech
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import java.util.Locale

/**
 * "The PC calls you" — the phone half of ROADMAP Phase H (owner 2026-08-05).
 *
 * The PC sends a notice naming the AGENT that finished, because the owner
 * runs several at once and a bare beep says nothing:
 *
 *   "nije dovoljno samo da kaže beep kad završi agent … najbolje od svega je
 *    da izbaci notifikaciju koja opisuje koji agent je završio"
 *
 * Two carriers live here, and each covers what the other cannot:
 *
 *  - a real system NOTIFICATION, which survives the app being backgrounded
 *    and the screen being off — the situation this whole feature is for. The
 *    agent's name is the notification TAG, so a second notice from the same
 *    agent replaces its own line while four agents keep four lines;
 *  - SPEECH (TextToSpeech), for when his eyes and hands are on the PC. The
 *    engine is opened lazily and kept, because the first `speak()` after a
 *    cold start otherwise lands after the sentence it was asked to say.
 *
 * The page decides which of the two to use (its own per-device switches) —
 * this class only knows how to deliver.
 */
class Notifier(private val ctx: Context) {

    companion object {
        private const val TAG = "Notifier"
        private const val CHANNEL_ID = "agents"
        // One id per agent name, so notifications REPLACE per agent instead of
        // stacking one line per finished turn. Hashing keeps that stable
        // across app restarts without keeping a table.
        private fun idFor(tag: String) = tag.hashCode() and 0x7fffffff
    }

    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private val pending = ArrayList<String>()

    init {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Agents on the PC",
                NotificationManager.IMPORTANCE_HIGH,   // heads-up: this is the point
            ).apply {
                description = "When a job on your PC finishes or needs you"
                enableVibration(true)
            }
            ctx.getSystemService(NotificationManager::class.java)
                ?.createNotificationChannel(channel)
        }
    }

    /** Raises (or replaces) one agent's notification. */
    fun post(title: String, text: String, tag: String) {
        val open = PendingIntent.getActivity(
            ctx, 0,
            Intent(ctx, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val builder = NotificationCompat.Builder(ctx, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle(title)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setCategory(Notification.CATEGORY_STATUS)
            .setDefaults(NotificationCompat.DEFAULT_ALL)   // sound + vibration
            .setAutoCancel(true)
            .setContentIntent(open)
        if (text.isNotEmpty()) {
            builder.setContentText(text)
            // A finished agent often has more to say than one line — the
            // expanded style is what keeps the whole sentence readable.
            builder.setStyle(NotificationCompat.BigTextStyle().bigText(text))
        }
        try {
            NotificationManagerCompat.from(ctx).notify(tag, idFor(tag), builder.build())
        } catch (e: SecurityException) {
            // POST_NOTIFICATIONS refused (Android 13+). Not fatal: the page
            // still speaks and toasts, and the log says why the banner is
            // missing instead of leaving a silent mystery.
            Log.w(TAG, "Notification refused — permission not granted", e)
        }
    }

    /** Says it out loud. Queues until the engine is ready, never drops. */
    fun speak(text: String) {
        if (text.isBlank()) return
        val engine = tts
        if (engine != null && ttsReady) {
            engine.speak(text, TextToSpeech.QUEUE_ADD, null, "agent")
            return
        }
        synchronized(pending) { pending.add(text) }
        if (engine != null) return          // still initialising — it will drain
        tts = TextToSpeech(ctx) { status ->
            ttsReady = status == TextToSpeech.SUCCESS
            if (!ttsReady) {
                Log.w(TAG, "TextToSpeech unavailable (status $status)")
                synchronized(pending) { pending.clear() }
                return@TextToSpeech
            }
            // The default locale is the phone's, which is what the owner
            // hears best; an engine without it falls back on its own.
            tts?.language = Locale.getDefault()
            val queued = synchronized(pending) {
                val copy = ArrayList(pending); pending.clear(); copy
            }
            queued.forEach { tts?.speak(it, TextToSpeech.QUEUE_ADD, null, "agent") }
        }
    }

    fun release() {
        tts?.stop()
        tts?.shutdown()
        tts = null
        ttsReady = false
    }
}
