package com.sparkx.toelating.kiosk

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputType
import android.view.View
import android.view.WindowManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

private const val PREFS_NAME = "toelating_kiosk"
private const val KEY_SERVER = "server_address"
private const val KEY_SCREEN = "screen_path"
private const val SCREEN_HOST = "/"
private const val SCREEN_ADMIN = "/admin/"

// Zelfde tagje binnen dit venster genegeerd: Android's foreground dispatch kan
// meerdere keren afvuren zolang het bandje tegen het toestel blijft liggen.
private const val NFC_DEDUPE_WINDOW_MS = 2000L

// Hoe vaak (en na hoeveel mislukkingen op rij) een verloren serververbinding
// gedetecteerd wordt, los van de pagina's eigen (JS-only) verbindingsbanner --
// zie de klasse-KDoc hieronder voor waarom dit apart, native moet gebeuren.
private const val HEALTH_CHECK_INTERVAL_MS = 5000L
private const val HEALTH_CHECK_TIMEOUT_MS = 4000
private const val HEALTH_CHECK_FAILURES_BEFORE_ERROR = 3

/**
 * Toont het bestaande, al geteste webhostscherm/beheerscherm (zie backend/ +
 * frontend/) als volwaardige Android-app: eigen icoon, geen adresbalk. De
 * server (FastAPI) blijft draaien op een pc op het lokale netwerk — deze app
 * verandert niets aan hoe inloggen of de status-logica werkt, enkel welk
 * toestel de pagina toont en hoe een scan binnenkomt.
 *
 * Geen gedwongen volledig scherm (gewoon venster, met status-/navigatiebalk
 * zichtbaar) en geen zichtbare instellingenknop: een lange druk ergens op
 * de pagina opent het instellingenscherm (serveradres, host-/beheerscherm).
 *
 * Twee manieren om een bandje te scannen komen hier samen op dezelfde
 * pagina, via dezelfde reader-interface (zie frontend/shared/reader.js):
 * - Een USB/Bluetooth-lezer die als toetsenbord werkt (KeyboardWedgeReader)
 *   stuurt toetsaanslagen door naar de pagina in de WebView, net als in een
 *   gewone browser.
 * - De NFC-chip van de telefoon zelf (deze klasse, via Android's
 *   NfcAdapter + foreground dispatch): leest de hardware-UID van het
 *   tagje en geeft die door aan `window.ToelatingNativeBridge.onScan(id)`,
 *   die de reader.js-kant hier expliciet voor blootstelt (NativeBridgeReader).
 *   Bandjes registreren zichzelf automatisch bij de eerste scan (zie
 *   backend/app/services/common.py: get_or_create_wristband), dus de
 *   hardware-UID als ID gebruiken vergt geen vooraf ingestelde lijst.
 *
 * De NFC-chip-scan is bevestigd werkend met een echt toestel en een echt
 * tagje. Het externe USB/Bluetooth-lezerpad is niet apart getest.
 *
 * Verbindingsverlies: de pagina zelf toont al een banner via haar eigen
 * (JavaScript-only) polling (frontend/shared/api.js: startHealthPolling) --
 * maar dat blijft een passieve banner op een verder ongewijzigd scherm, wat
 * op een telefoon makkelijk over het hoofd gezien wordt of "bevroren" aanvoelt.
 * Deze klasse doet daarom zijn eigen, onafhankelijke polling van /api/health
 * (in onResume/onPause), en toont na een paar mislukkingen op rij hetzelfde
 * "Geen verbinding"-dialoogvenster als bij een mislukte eerste keer laden --
 * een duidelijk, actief signaal in plaats van enkel een bannertje.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var prefs: SharedPreferences
    private var nfcAdapter: NfcAdapter? = null
    private var lastNfcTagId: String? = null
    private var lastNfcTagAtMs: Long = 0L

    private val mainHandler = Handler(Looper.getMainLooper())
    private val healthCheckExecutor: ExecutorService = Executors.newSingleThreadExecutor()
    private var healthCheckRunnable: Runnable? = null
    private var consecutiveHealthFailures = 0
    private var connectionErrorShowing = false

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        nfcAdapter = NfcAdapter.getDefaultAdapter(this)

        webView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = true
            settings.setSupportZoom(false)
            settings.builtInZoomControls = false
            // Server draait lokaal op het netwerk (snel, geen bandbreedte-kosten),
            // dus geen reden om verouderde CSS/JS te blijven tonen na een update.
            settings.cacheMode = WebSettings.LOAD_NO_CACHE
            // Geen zichtbare instellingenknop (die nam ruimte in op het scherm) --
            // een lange druk ergens op de pagina opent hetzelfde dialoogvenster,
            // en onderdrukt meteen ook WebView's eigen tekstselectie-contextmenu.
            isLongClickable = true
            setOnLongClickListener { showSettingsDialog(); true }
            webViewClient = object : WebViewClient() {
                override fun onReceivedError(
                    view: WebView?,
                    request: WebResourceRequest?,
                    error: WebResourceError?,
                ) {
                    super.onReceivedError(view, request, error)
                    if (request?.isForMainFrame == true) {
                        showConnectionError()
                    }
                }
            }
        }

        setContentView(webView)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        val savedServer = prefs.getString(KEY_SERVER, null)
        if (savedServer.isNullOrBlank()) {
            showSettingsDialog(forceShow = true)
        } else {
            loadServer(savedServer, prefs.getString(KEY_SCREEN, SCREEN_HOST) ?: SCREEN_HOST)
        }
    }

    override fun onResume() {
        super.onResume()
        startHealthChecks()
        val adapter = nfcAdapter ?: return
        if (!adapter.isEnabled) {
            Toast.makeText(
                this,
                "NFC staat uit — zet dit aan in de toestelinstellingen om bandjes te kunnen scannen.",
                Toast.LENGTH_LONG,
            ).show()
            return
        }
        val intent = Intent(this, javaClass).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
        val piFlags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            PendingIntent.FLAG_MUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
        } else {
            PendingIntent.FLAG_UPDATE_CURRENT
        }
        val pendingIntent = PendingIntent.getActivity(this, 0, intent, piFlags)
        adapter.enableForegroundDispatch(this, pendingIntent, null, null)
    }

    override fun onPause() {
        super.onPause()
        stopHealthChecks()
        nfcAdapter?.disableForegroundDispatch(this)
    }

    override fun onDestroy() {
        super.onDestroy()
        healthCheckExecutor.shutdown()
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        val tag: Tag? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            intent.getParcelableExtra(NfcAdapter.EXTRA_TAG, Tag::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(NfcAdapter.EXTRA_TAG)
        }
        handleNfcTag(tag)
    }

    private fun handleNfcTag(tag: Tag?) {
        val tagId = tag?.id
        if (tagId == null || tagId.isEmpty()) return

        val hexId = tagId.joinToString("") { "%02X".format(it) }
        val now = System.currentTimeMillis()
        if (hexId == lastNfcTagId && now - lastNfcTagAtMs < NFC_DEDUPE_WINDOW_MS) return
        lastNfcTagId = hexId
        lastNfcTagAtMs = now

        webView.evaluateJavascript(
            "window.ToelatingNativeBridge && window.ToelatingNativeBridge.onScan(${JSONObject.quote(hexId)});",
            null,
        )
    }

    private fun startHealthChecks() {
        stopHealthChecks()
        val runnable = object : Runnable {
            override fun run() {
                checkHealthOnce()
                mainHandler.postDelayed(this, HEALTH_CHECK_INTERVAL_MS)
            }
        }
        healthCheckRunnable = runnable
        mainHandler.postDelayed(runnable, HEALTH_CHECK_INTERVAL_MS)
    }

    private fun stopHealthChecks() {
        healthCheckRunnable?.let { mainHandler.removeCallbacks(it) }
        healthCheckRunnable = null
    }

    private fun checkHealthOnce() {
        val server = prefs.getString(KEY_SERVER, null)
        if (server.isNullOrBlank()) return
        val healthUrl = buildHealthUrl(server)
        healthCheckExecutor.execute {
            val reachable = isServerReachable(healthUrl)
            mainHandler.post { onHealthCheckResult(reachable) }
        }
    }

    private fun buildHealthUrl(address: String): String {
        val clean = address.trim().removeSuffix("/")
        val base = if (clean.startsWith("http://") || clean.startsWith("https://")) clean else "http://$clean"
        return "$base/api/health"
    }

    private fun isServerReachable(healthUrl: String): Boolean {
        var connection: HttpURLConnection? = null
        return try {
            connection = URL(healthUrl).openConnection() as HttpURLConnection
            connection.connectTimeout = HEALTH_CHECK_TIMEOUT_MS
            connection.readTimeout = HEALTH_CHECK_TIMEOUT_MS
            connection.requestMethod = "GET"
            connection.responseCode in 200..299
        } catch (e: Exception) {
            false
        } finally {
            connection?.disconnect()
        }
    }

    private fun onHealthCheckResult(reachable: Boolean) {
        if (reachable) {
            consecutiveHealthFailures = 0
            return
        }
        consecutiveHealthFailures++
        if (consecutiveHealthFailures >= HEALTH_CHECK_FAILURES_BEFORE_ERROR && !connectionErrorShowing) {
            showConnectionError()
        }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun showSettingsDialog(forceShow: Boolean = false) {
        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(24), dp(16), dp(24), dp(16))
        }

        val serverInput = EditText(this).apply {
            hint = "bv. 192.168.1.50:8000"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            setText(prefs.getString(KEY_SERVER, ""))
        }
        container.addView(serverInput)

        val radioGroup = RadioGroup(this).apply { orientation = RadioGroup.VERTICAL }
        val hostRadio = RadioButton(this).apply { text = "Hostscherm"; id = View.generateViewId() }
        val adminRadio = RadioButton(this).apply { text = "Beheerscherm"; id = View.generateViewId() }
        radioGroup.addView(hostRadio)
        radioGroup.addView(adminRadio)
        if (prefs.getString(KEY_SCREEN, SCREEN_HOST) == SCREEN_ADMIN) {
            adminRadio.isChecked = true
        } else {
            hostRadio.isChecked = true
        }
        container.addView(radioGroup)

        val dialogBuilder = AlertDialog.Builder(this)
            .setTitle("Serverinstellingen")
            .setView(container)
            .setPositiveButton("Opslaan") { _, _ ->
                val address = serverInput.text.toString().trim()
                val screenPath = if (adminRadio.isChecked) SCREEN_ADMIN else SCREEN_HOST
                prefs.edit().putString(KEY_SERVER, address).putString(KEY_SCREEN, screenPath).apply()
                loadServer(address, screenPath)
            }
            .setCancelable(!forceShow)

        if (!forceShow) {
            dialogBuilder.setNegativeButton("Annuleer", null)
        }

        dialogBuilder.show()
    }

    private fun loadServer(address: String, screenPath: String) {
        val cleanAddress = address.trim().removeSuffix("/")
        val url = if (cleanAddress.startsWith("http://") || cleanAddress.startsWith("https://")) {
            "$cleanAddress$screenPath"
        } else {
            "http://$cleanAddress$screenPath"
        }
        webView.loadUrl(url)
    }

    private fun showConnectionError() {
        if (connectionErrorShowing) return
        connectionErrorShowing = true
        AlertDialog.Builder(this)
            .setTitle("Geen verbinding")
            .setMessage(
                "Kan de server niet bereiken. Controleer of de pc aan staat, " +
                    "de server draait, en het IP-adres klopt.",
            )
            .setPositiveButton("Instellingen") { _, _ ->
                connectionErrorShowing = false
                consecutiveHealthFailures = 0
                showSettingsDialog(forceShow = true)
            }
            .setNegativeButton("Opnieuw proberen") { _, _ ->
                connectionErrorShowing = false
                consecutiveHealthFailures = 0
                loadServer(prefs.getString(KEY_SERVER, "") ?: "", prefs.getString(KEY_SCREEN, SCREEN_HOST) ?: SCREEN_HOST)
            }
            .setCancelable(false)
            .show()
    }

    @Suppress("DEPRECATION")
    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        }
        // Anders bewust niets doen: een kiosk-app mag niet per ongeluk sluiten
        // via de terugknop.
    }
}
