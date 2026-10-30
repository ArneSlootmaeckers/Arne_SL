package com.sparkx.toelating.kiosk

import android.content.SharedPreferences
import android.net.http.SslCertificate
import android.os.Build
import java.security.MessageDigest
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLSocketFactory
import javax.net.ssl.X509TrustManager

private const val KEY_CERT_PIN = "server_certificate_sha256"

/** Het certificaat van de server is niet het vertrouwde: zie [ServerCertificate]. */
class UntrustedCertificateException : CertificateException("Ander certificaat dan het vertrouwde")

/**
 * Welk https-certificaat van de server deze app vertrouwt.
 *
 * De server maakt zelf een certificaat aan (zie backend/app/tls.py); dat is
 * door niemand "ondertekend", dus Android vertrouwt het niet vanzelf. De app
 * vertrouwt daarom het certificaat dat hij de eerste keer bij de ingestelde
 * server ziet, en daarna enkel nog precies dat ene certificaat ("pinnen").
 * Een ander toestel op het netwerk dat zich voordoet als de server, heeft dat
 * certificaat niet en wordt dus geweigerd -- ook als het het IP-adres van de
 * pc overneemt. Omgekeerd maakt een nieuw IP-adres voor de echte pc niets uit:
 * enkel het certificaat zelf telt, niet het adres.
 *
 * Toont de server ooit een ander certificaat (bv. na een volledige
 * herinstallatie), dan onthoudt dit welk ([rejected]); de instellingen tonen
 * dan de code ervan, zodat iemand die kan vergelijken met Beheer → Systeem
 * voor hij het vertrouwt ([trustRejected]).
 */
class ServerCertificate(private val prefs: SharedPreferences) {

    @Volatile
    var rejected: ByteArray? = null
        private set

    /** Voor de verbinding met de ingestelde server: vertrouwt het eerste
     * certificaat en onthoudt een afwijkend. */
    val pinningSocketFactory: SSLSocketFactory by lazy { socketFactory(pinOnFirstUse = true) }

    /** Voor het zoeken op het netwerk: legt niets vast (een willekeurig ander
     * https-toestel mag nooit vertrouwd worden), weigert enkel een ander
     * certificaat dan het al vertrouwde. */
    val discoverySocketFactory: SSLSocketFactory by lazy { socketFactory(pinOnFirstUse = false) }

    /** Het adres wordt niet gecontroleerd, enkel het certificaat zelf: dat
     * blijft gelijk als de pc een ander IP-adres krijgt. */
    val hostnameVerifier = HostnameVerifier { _, _ -> true }

    fun configure(connection: HttpsURLConnection, pinOnFirstUse: Boolean) {
        connection.sslSocketFactory = if (pinOnFirstUse) pinningSocketFactory else discoverySocketFactory
        connection.hostnameVerifier = hostnameVerifier
    }

    /** True als dit certificaat vertrouwd mag worden. Is er nog geen, dan
     * wordt dit het vertrouwde certificaat. */
    @Synchronized
    fun check(der: ByteArray): Boolean {
        val fingerprint = sha256Hex(der)
        val pinned = prefs.getString(KEY_CERT_PIN, null)
        if (pinned == null) {
            prefs.edit().putString(KEY_CERT_PIN, fingerprint).apply()
        } else if (pinned != fingerprint) {
            rejected = der
            return false
        }
        rejected = null
        return true
    }

    @Synchronized
    fun matchesOrUnpinned(der: ByteArray): Boolean {
        val pinned = prefs.getString(KEY_CERT_PIN, null)
        return pinned == null || pinned == sha256Hex(der)
    }

    @Synchronized
    fun trustRejected() {
        val der = rejected ?: return
        prefs.edit().putString(KEY_CERT_PIN, sha256Hex(der)).apply()
        rejected = null
    }

    /** "AB12 CD34 EF56 7890", dezelfde code als op Beheer → Systeem, of null. */
    fun pinnedCode(): String? = prefs.getString(KEY_CERT_PIN, null)?.let(::shortCode)

    fun rejectedCode(): String? = rejected?.let { shortCode(sha256Hex(it)) }

    private fun socketFactory(pinOnFirstUse: Boolean): SSLSocketFactory {
        val trustManager = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {
                throw CertificateException("Niet gebruikt")
            }

            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
                val leaf = chain.firstOrNull()?.encoded ?: throw CertificateException("Geen certificaat")
                val trusted = if (pinOnFirstUse) check(leaf) else matchesOrUnpinned(leaf)
                if (!trusted) throw UntrustedCertificateException()
            }

            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
        }
        return SSLContext.getInstance("TLS").apply { init(null, arrayOf(trustManager), null) }.socketFactory
    }

    companion object {
        /** De ruwe bytes van een certificaat dat de WebView meldt. */
        fun encoded(certificate: SslCertificate?): ByteArray? {
            if (certificate == null) return null
            return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                certificate.x509Certificate?.encoded
            } else {
                // Voor Android 10 geeft SslCertificate het certificaat enkel
                // zo prijs (vaste sleutel in Android zelf).
                SslCertificate.saveState(certificate).getByteArray("x509-certificate")
            }
        }

        private fun sha256Hex(der: ByteArray): String =
            MessageDigest.getInstance("SHA-256").digest(der).joinToString("") { "%02X".format(it) }

        private fun shortCode(fingerprint: String): String = fingerprint.take(16).chunked(4).joinToString(" ")
    }
}
