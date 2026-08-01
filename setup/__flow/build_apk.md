# Build APK — Flow

**About:** [description](../__about/build_apk.md)

## Algorithm

```mermaid
flowchart TB
    A[main] --> B["1/4  check_toolchain()"]
    B --> C{JDK + SDK found?}
    C -- no --> X1[exit 1]
    C -- yes --> D{Gradle 8.10.2\ncached?}
    D -- no --> E[download + unzip Gradle\ninto setup/vendor]
    D -- yes --> F
    E --> F[write android/local.properties]
    F --> G["2/4  ensure_keystore()"]
    G --> H{release.jks\nexists?}
    H -- yes --> I[reuse keystore\n+ persisted password]
    H -- no --> J["keytool -genkeypair\nRSA 2048, 10000 days\npersist random password"]
    I --> K
    J --> K["3/4  build()"]
    K --> L{gradlew.bat\nexists?}
    L -- no --> M[generate wrapper\nfrom vendored Gradle]
    L -- yes --> N
    M --> N["version_code =\nint(version.split('.')[-1])"]
    N --> O["gradlew assembleRelease\n-PappVersion -PappVersionCode\n+ keystore env vars"]
    O --> P{app-release.apk\nexists?}
    P -- no --> X2[exit 1]
    P -- yes --> Q["4/4  copy to\ndist/RemoteUser.apk"]
```

Pseudocode (language-neutral):

    check the JDK and Android SDK exist, else fail the build
    IF the pinned Gradle version is not cached: download + unzip it
    write local.properties (SDK path) so Gradle can find the SDK

    IF a release keystore already exists: reuse it + its saved password
    ELSE: generate a 2048-bit RSA keystore, persist a fresh random password

    IF the Gradle wrapper is missing: generate it from the vendored Gradle
    version_code = integer value of the LAST dot-segment of app_info.version
    run "gradlew assembleRelease" with the version + keystore env vars
    IF the expected release APK path is missing afterward: fail the build

    copy the signed APK to dist/RemoteUser.apk
