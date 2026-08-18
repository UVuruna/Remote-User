package com.uvuruna.vibecoder

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log

/**
 * THE WAY BACK IN, after this app has replaced itself.
 *
 * `Updater.kt` streams `/app.apk` into a `PackageInstaller` session and
 * commits it. When that install SUCCEEDS, Android tears this process down and
 * starts the new version's package — but it starts no ACTIVITY: the app
 * simply vanishes off the screen and the owner has to find it and open it by
 * hand (his report, 2026-08-18). Updater itself can say nothing about this:
 * the success it would report happens after the process that would report it
 * is gone (see its class header, and the deliberately missing "success"
 * state). Only something the SYSTEM starts afterwards can bring him back, and
 * that is this receiver.
 *
 * `ACTION_MY_PACKAGE_REPLACED` is the right action and `ACTION_PACKAGE_REPLACED`
 * is not: the broad one fires for EVERY app the device updates (it would need
 * package visibility, an extra to filter on, and it would run us for work that
 * is none of our business), while MY_PACKAGE_REPLACED is delivered to OUR OWN
 * package only, exactly once, exactly when this app was the one replaced.
 *
 * TWO CARRIERS, AND ONLY ONE OF THEM IS RELIABLE — this is the whole reason
 * this file is shaped the way it is, and nobody may "simplify" it into one:
 *
 *  - `startActivity` is BEST EFFORT ONLY. Since Android 10 a process started
 *    by a background broadcast is FORBIDDEN from launching an activity
 *    (background activity starts). We are exactly that process — nothing of
 *    ours is in the foreground at this moment, because we were just replaced.
 *    Worse, the refusal is usually SILENT: the system logs it and drops the
 *    start, so no `catch` here can even detect it. Some OEM builds and some
 *    states (the app was in the foreground when the update landed) do allow
 *    it, which is why it is attempted at all — when it works he is simply
 *    back in the app with nothing to tap.
 *  - THE NOTIFICATION IS THE MECHANISM THAT WORKS, and it is therefore posted
 *    ALWAYS — never as an "else" behind the start above, because there is no
 *    reliable way to learn that the start was refused. A start that succeeded
 *    leaves him one notification he can swipe away; a start that was refused
 *    leaves him one tap from the app. Only the second case is the one this
 *    feature exists for.
 *
 * The notification goes through [Notifier] — the app's ONE notification
 * builder (monorepo priority C: inheritance over duplication). No second
 * builder, no second channel, no second PendingIntent shape lives here; the
 * tap lands in `MainActivity` because that is where `Notifier.post` always
 * sends it.
 *
 * DECLARED IN THE MANIFEST, NEVER REGISTERED AT RUNTIME: a runtime-registered
 * receiver lives in a process, and at the moment this broadcast is sent our
 * process is dead — it is the very thing the install killed. Only a manifest
 * entry can bring a package back from nothing.
 */
class UpdateReturn : BroadcastReceiver() {

    companion object {
        private const val TAG = "UpdateReturn"
        /** The notification TAG, i.e. its identity for replacement. Its own,
         *  distinct from any agent name the PC sends: an update notice must
         *  never replace an agent's line, and a second update (a later
         *  version) must replace its own predecessor rather than stack. */
        private const val NOTICE_TAG = "vibecoder-update"
    }

    override fun onReceive(ctx: Context, intent: Intent) {
        // A manifest receiver may only ever be handed the action it filtered
        // for; checking anyway costs nothing and means a widened filter can
        // never quietly make this fire for someone else's install.
        if (intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return

        // BEST EFFORT (see the header): usually refused, and usually refused
        // SILENTLY. The try/catch is here so the *throwing* refusals —
        // SecurityException, ActivityNotFoundException, an OEM's own — can
        // never crash the receiver and cost him the notification below, which
        // is the carrier that actually works.
        try {
            ctx.startActivity(
                Intent(ctx, MainActivity::class.java)
                    // Required: a receiver's context is not an activity, so
                    // there is no task for this to be placed into.
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            )
        } catch (e: Exception) {
            Log.i(TAG, "Could not open the app directly after the update — "
                       + "the notification is the way back", e)
        }

        // ALWAYS, never in an `else`.
        val notifier = Notifier(ctx)
        try {
            notifier.post(
                ctx.getString(R.string.update_done_title),
                ctx.getString(R.string.update_done_body),
                NOTICE_TAG,
            )
        } finally {
            // `Notifier` binds a TextToSpeech engine in its constructor (for
            // the notices it usually carries). Nothing is spoken here, and a
            // receiver is not allowed to keep anything alive after onReceive
            // returns, so the engine is handed straight back instead of being
            // left bound to a process the system is about to stop again.
            notifier.release()
        }
    }
}
