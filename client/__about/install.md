# Install Funnel

**Script:** [Install Funnel (script)](../install.html)

## Purpose

The ONLY page a plain Android browser ever sees: the server routes Android
User-Agents here (the APK's WebView is excluded via its `VibeCoderApp`
marker) whenever a built APK exists — without one, Android browsers fall
through to the same [Page Shell](index.md) as everyone else. A self-contained,
two-step funnel: **Install** the app (first time only, downloads `/app.apk`),
then **Open the app** (`intent://pair?url=…`, handing over this exact tokened
URL so the APK pairs itself — nothing typed, nothing scanned). Self-contained
on purpose: its own inline `<style>` block and inline `<script>`, no
dependency on `style.css` or any of the client scripts — the one page an
app-less phone can reach must never break because of a mismatch elsewhere in
the client.

## Structure

- `.card` — the centered panel; logo (`/favicon.ico`), title, two `.step`
  blocks
- `#step-install` (active by default) — `#install`, an `<a href="/app.apk">`;
  its `click` handler marks step 1 done (green check) and highlights step 2
- `#step-open` — `#open`, an `<a>` whose `href` is built in-page from
  `location.href`:
  `intent://pair?url=<here>#Intent;scheme=remoteuser;package=com.uvuruna.remoteuser;S.browser_fallback_url=<here>;end`
  — launches the installed app with this page's URL, or reloads this same
  page if the app is missing

## Connections

### Uses

- Nothing project-internal — self-contained inline `<style>` and `<script>`

### Used by

- [Web Layer](../../server/__about/web.md) — served at `/` by User-Agent whenever a
  plain Android browser hits the server and `/app.apk` exists
- [Android (folder)](../../android/___android.md) — `OnboardingActivity` is
  the app-side half of the same handover: it receives the `intent://pair`
  link this page builds and stores the tokened URL
