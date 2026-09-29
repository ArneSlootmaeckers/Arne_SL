package com.sparkx.toelating.kiosk

import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.Inet4Address
import java.net.URL
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

// Moet overeenkomen met SERVER_APP_ID in backend/app/api/routes_health.py.
private const val SERVER_APP_ID = "toelatingssysteem"
private const val SERVER_PORT = 8000

private const val PARALLEL_PROBES = 64
private const val PROBE_CONNECT_TIMEOUT_MS = 500
private const val PROBE_READ_TIMEOUT_MS = 1500
private const val TOTAL_TIMEOUT_MS = 20_000L

// Groter dan /22 (~1000 adressen) duurt het afzoeken te lang, en ziet het er
// op een groot bedrijfsnetwerk uit als een poortscan -- dan enkel de /24
// rond het eigen adres.
private const val SMALLEST_SCANNED_PREFIX = 22
private const val FALLBACK_PREFIX = 24

/**
 * Zoekt de toelatingsserver op het lokale (wifi-)netwerk van de telefoon, door
 * elk adres in dat netwerk op poort 8000 naar /api/health te vragen en te
 * kijken of het antwoord van de toelatingsserver komt. Geen extra poort of
 * firewallregel op de pc nodig: dit gebruikt exact dezelfde poort als de app
 * zelf.
 */
class ServerDiscovery(private val connectivityManager: ConnectivityManager) {

    /** Blokkeert tot een paar seconden: nooit op de hoofdthread aanroepen.
     * Geeft "ip:poort" terug, of null als er niets gevonden werd. */
    fun findServer(): String? {
        val network = findLocalNetwork() ?: return null
        val ownAddress = connectivityManager.getLinkProperties(network)?.linkAddresses
            ?.firstOrNull { it.address is Inet4Address } ?: return null
        val hosts = candidateHosts(ownAddress.address as Inet4Address, ownAddress.prefixLength)
        if (hosts.isEmpty()) return null

        val pool = Executors.newFixedThreadPool(PARALLEL_PROBES)
        return try {
            pool.invokeAny(
                hosts.map { host -> Callable { probe(network, host) } },
                TOTAL_TIMEOUT_MS,
                TimeUnit.MILLISECONDS,
            )
        } catch (e: Exception) {
            null
        } finally {
            pool.shutdownNow()
        }
    }

    // Expliciet het wifi-netwerk, niet het "actieve": staat mobiele data aan,
    // dan zou dat anders het netwerk van de gsm-provider kunnen zijn.
    @Suppress("DEPRECATION")
    private fun findLocalNetwork(): Network? = connectivityManager.allNetworks.firstOrNull { network ->
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return@firstOrNull false
        capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ||
            capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
    }

    /** Gooit een uitzondering bij alles behalve de toelatingsserver: zo telt
     * invokeAny enkel een echte treffer als resultaat. */
    private fun probe(network: Network, host: String): String {
        val connection = network.openConnection(URL("http://$host:$SERVER_PORT/api/health")) as HttpURLConnection
        try {
            connection.connectTimeout = PROBE_CONNECT_TIMEOUT_MS
            connection.readTimeout = PROBE_READ_TIMEOUT_MS
            if (connection.responseCode != 200) throw IOException("Geen toelatingsserver op $host")
            val body = connection.inputStream.bufferedReader().use { it.readText() }
            if (JSONObject(body).optString("app") != SERVER_APP_ID) {
                throw IOException("Andere server op $host")
            }
            return "$host:$SERVER_PORT"
        } finally {
            connection.disconnect()
        }
    }

    private fun candidateHosts(ownAddress: Inet4Address, prefixLength: Int): List<String> {
        val prefix = if (prefixLength < SMALLEST_SCANNED_PREFIX) FALLBACK_PREFIX else prefixLength
        if (prefix > 30) return emptyList()

        val own = ownAddress.address.fold(0) { acc, byte -> (acc shl 8) or (byte.toInt() and 0xff) }
        val mask = -1 shl (32 - prefix)
        val first = (own and mask) + 1
        val last = (own or mask.inv()) - 1
        return (first..last).filter { it != own }.map(::toDottedQuad)
    }

    private fun toDottedQuad(value: Int): String =
        "${(value ushr 24) and 0xff}.${(value ushr 16) and 0xff}.${(value ushr 8) and 0xff}.${value and 0xff}"
}
