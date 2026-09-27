// Zuivere Kotlin-module (geen Android-afhankelijkheden): de statuslogica en
// dagwisseling, letterlijk overgezet van backend/app/domain/*.py. Staat
// bewust los van de Android-app (zie android/README.md) zodat dit altijd
// op zichzelf bouwt en test, ook zonder Android SDK.
plugins {
    kotlin("jvm") version "2.0.21"
}

repositories {
    mavenCentral()
}

dependencies {
    testImplementation(kotlin("test"))
    testImplementation("junit:junit:4.13.2")
}

tasks.test {
    useJUnit()
}

kotlin {
    // 21 is the only JDK available in the build/test sandbox this module was
    // verified in. If Android Studio's bundled JDK or your AGP version wants
    // an older bytecode target, lower this (17 is a safe, common choice).
    jvmToolchain(21)
}
