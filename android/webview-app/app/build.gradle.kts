plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.sparkx.toelating.kiosk"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.sparkx.toelating.kiosk"
        minSdk = 24
        targetSdk = 34
        // Verhogen bij elke Play Store-release. Heeft een nieuwe serverversie
        // deze app nodig, zet dan MIN_ANDROID_VERSION_CODE in
        // backend/app/version.py op dit getal.
        versionCode = 3
        versionName = "3.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
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
    implementation("androidx.core:core-ktx:1.13.1")
    // Updates uit de Play Store (venster als de server een nieuwere app vereist).
    implementation("com.google.android.play:app-update-ktx:2.1.0")
}
