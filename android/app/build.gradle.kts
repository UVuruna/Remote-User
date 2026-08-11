// Vibe Coder Android shell — a native wrapper around the web client.
// Version comes from the build script (-PappVersion / -PappVersionCode,
// derived from setup/app_info.json); signing config from environment
// variables set by setup/build_apk.py (never committed).

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val appVersion: String = (project.findProperty("appVersion") as String?) ?: "0.0.0"
val appVersionCode: Int = ((project.findProperty("appVersionCode") as String?) ?: "1").toInt()

android {
    namespace = "com.uvuruna.vibecoder"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.uvuruna.vibecoder"
        minSdk = 26
        targetSdk = 35
        versionCode = appVersionCode
        versionName = appVersion
    }

    signingConfigs {
        create("release") {
            val ksPath = System.getenv("RU_KEYSTORE")
            if (ksPath != null) {
                storeFile = file(ksPath)
                storePassword = System.getenv("RU_KEYSTORE_PASS")
                // "remoteuser" is the key's slot inside the existing
                // release.jks, not a product name — see setup/build_apk.py.
                keyAlias = System.getenv("RU_KEY_ALIAS") ?: "remoteuser"
                keyPassword = System.getenv("RU_KEYSTORE_PASS")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            if (System.getenv("RU_KEYSTORE") != null) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.0")
    // NotificationCompat + NotificationManagerCompat (ROADMAP Phase H). It
    // already arrives transitively through appcompat; named explicitly
    // because Notifier.kt compiles against it directly, and a transitive
    // version bump must never be what decides whether the app builds.
    implementation("androidx.core:core-ktx:1.13.1")
    // Embedded QR scanner (no Google Play Services dependency)
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
}
