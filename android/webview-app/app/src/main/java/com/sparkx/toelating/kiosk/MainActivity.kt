package com.sparkx.toelating.kiosk

import android.annotation.SuppressLint
import android.app.ActivityManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.ConnectivityManager
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputFilter
import android.text.InputType
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

private const val PREFS_NAME = "toelating_kiosk"
private const val KEY_SERVER = "server_address"
private const val KEY_SCREEN = "screen_path"
private const val KEY_KIOSK = "kiosk_mode"
private const val KEY_DEVICE_NAME = "device_name"
private const val SCREEN_HOST = "/"
private const val SCREEN_ADMIN = "/admin/"

// Zelfde tagje binnen dit venster genegeerd: Android's foreground dispatch kan
// meerdere keren afvuren zolang het bandje tegen het toestel blijft liggen.
private const val NFC_DEDUPE_WINDOW_MS = 2000L

// Hoe vaak (en na hoeveel mislukkingen op rij) een verloren serververbinding
// gedetecteerd wordt, los van de pagina's eigen (JS-only) verbindingsbanner --
// zie de klasse-KDoc hieronder voor waarom dit apart, native moet gebeuren.
// Bewust op scherp gezet (1 mislukking is genoeg, elke 2 seconden gecheckt):
// bij dit systeem mag een onbereikbare server nooit onopgemerkt blijven, dus
// geen risico nemen met een aantal pogingen of een trage interval -- de
// automatische herstelfunctie (zie recoverFromConnectionError) zorgt dat een
// vals alarm bij een heel kort haperingetje vanzelf meteen weer verdwijnt.
private const val HEALTH_CHECK_INTERVAL_MS = 2000L
private const val HEALTH_CHECK_TIMEOUT_MS = 2500
private const val HEALTH_CHECK_FAILURES_BEFORE_ERROR = 1

// Zolang het "Geen verbinding"-venster open staat, wordt de server om de
// zoveel tijd opnieuw op het netwerk gezocht -- bv. voor als de pc na een
// herstart een ander IP-adres kreeg.
private const val DISCOVERY_RETRY_INTERVAL_MS = 15_000L

// Bewust lang: een gewone lange druk (~0,5s) is te makkelijk per ongeluk te
// raken tijdens normaal gebruik van de knoppen op de pagina.
private const val SETTINGS_HOLD_DURATION_MS = 10000L

// Zelfde Sparkx-huisstijlkleuren als frontend/shared/style-base.css, voor de
// eigen vensters van de app (zie brandedPanel e.a.).
private const val COLOR_ACHTERGROND_DIEP = "#071f29"
private const val COLOR_ACHTERGROND_PANEEL = "#0f3a4a"
private const val COLOR_TEKST_GEDEMPT = "#9fc3d1"
private const val COLOR_ROOD = "#b3221c"
private const val COLOR_SPARKX_GEEL = "#ffd400"
private const val COLOR_SPARKX_ORANJE = "#f7941d"

// Vervangt Android/Chromium's eigen (witte, met groen robotje) foutpagina
// zodra een paginalading mislukt -- zonder dit blijft die lelijke standaard-
// pagina zichtbaar rond de randen van het "Geen verbinding"-venster.
private const val FALLBACK_PAGE_HTML =
    "<!doctype html><html><head><meta name=\"viewport\" " +
        "content=\"width=device-width, initial-scale=1\"><style>html,body{" +
        "margin:0;height:100%;background:$COLOR_ACHTERGROND_DIEP;}</style>" +
        "</head><body></body></html>"

/**
 * Toont het bestaande, al geteste webhostscherm/beheerscherm (zie backend/ +
 * frontend/) als volwaardige Android-app: eigen icoon, geen adresbalk. De
 * server (FastAPI) blijft draaien op een pc op het lokale netwerk — deze app
 * verandert niets aan hoe inloggen of de status-logica werkt, enkel welk
 * toestel de pagina toont en hoe een scan binnenkomt.
 *
 * Geen gedwongen volledig scherm (gewoon venster, met status-/navigatiebalk
 * zichtbaar) en geen zichtbare instellingenknop: het scherm 10 seconden
 * ononderbroken ingedrukt houden (SETTINGS_HOLD_DURATION_MS) opent het
 * instellingenscherm (serveradres, host-/beheerscherm) -- bewust lang, zodat
 * dit niet per ongeluk gebeurt tijdens normaal gebruik van de knoppen.
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
 * (in onResume/onPause), en toont meteen het "Geen verbinding"-venster.
 *
 * Die controle blijft ook doorlopen terwijl dat venster open staat, en sluit
 * het dan automatisch zodra de server weer bereikbaar is (bv. na een korte
 * wifi-onderbreking die vanzelf hersteld is) -- personeel hoeft dus niet
 * zelf op "Opnieuw proberen" te tikken. Was de allereerste paginalading zelf
 * mislukt (pageLoaded nog false, bv. de app werd gestart tijdens een storing),
 * dan laadt dat herstel de pagina meteen alsnog, want dan staat er nog
 * niets bruikbaars op het scherm om gewoon op verder te werken.
 *
 * Serveradres automatisch vinden (ServerDiscovery): bij de allereerste start,
 * en telkens opnieuw zolang het "Geen verbinding"-venster open staat, zoekt de
 * app de server zelf op het wifinetwerk. Kreeg de pc een ander IP-adres, dan
 * wordt het nieuwe adres dus vanzelf gevonden, opgeslagen en geladen.
 * Handmatig invullen blijft altijd mogelijk via de instellingen.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var prefs: SharedPreferences
    private lateinit var serverDiscovery: ServerDiscovery
    private var nfcAdapter: NfcAdapter? = null
    private var lastNfcTagId: String? = null
    private var lastNfcTagAtMs: Long = 0L
    private var settingsHoldRunnable: Runnable? = null

    private val mainHandler = Handler(Looper.getMainLooper())
    private val healthCheckExecutor: ExecutorService = Executors.newSingleThreadExecutor()
    private var healthCheckRunnable: Runnable? = null
    private var consecutiveHealthFailures = 0
    private var connectionErrorShowing = false
    private var connectionErrorDialog: AlertDialog? = null
    private var connectionErrorStatus: TextView? = null
    private var pageLoaded = false
    private var showingFallbackPage = false
    private var settingsDialogShowing = false

    private val discoveryExecutor: ExecutorService = Executors.newSingleThreadExecutor()
    private var discoveryRunning = false
    private var lastDiscoveryAtMs = 0L
    private val discoveryCallbacks = mutableListOf<(String?) -> Unit>()

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        serverDiscovery = ServerDiscovery(getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager)
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
            // maar een gewone lange druk (~0,5s) is te makkelijk per ongeluk te
            // raken tijdens normaal gebruik (bv. een knop iets te lang ingedrukt
            // houden), dus dit dialoogvenster opent pas na SETTINGS_HOLD_DURATION_MS
            // (zie setOnTouchListener/handleSettingsHoldTouch hieronder). Deze
            // listener zelf onderdrukt enkel WebView's eigen ~0,5s-tekstselectie-
            // contextmenu.
            isLongClickable = true
            setOnLongClickListener { true }
            setOnTouchListener { _, event -> handleSettingsHoldTouch(event); false }
            webViewClient = object : WebViewClient() {
                override fun onReceivedError(
                    view: WebView?,
                    request: WebResourceRequest?,
                    error: WebResourceError?,
                ) {
                    super.onReceivedError(view, request, error)
                    if (request?.isForMainFrame == true) {
                        pageLoaded = false
                        showingFallbackPage = true
                        view?.loadDataWithBaseURL(null, FALLBACK_PAGE_HTML, "text/html", "UTF-8", null)
                        showConnectionError()
                    }
                }

                override fun onPageFinished(view: WebView?, url: String?) {
                    super.onPageFinished(view, url)
                    pageLoaded = true
                }
            }
        }

        setContentView(webView)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        val savedServer = prefs.getString(KEY_SERVER, null)
        if (savedServer.isNullOrBlank()) {
            searchServerOnFirstStart()
        } else {
            loadServer(savedServer, prefs.getString(KEY_SCREEN, SCREEN_HOST) ?: SCREEN_HOST)
        }
    }

    override fun onResume() {
        super.onResume()
        // Gepost i.p.v. meteen: startLockTask() faalt op sommige toestellen
        // als het venster nog niet volledig op de voorgrond staat.
        mainHandler.post { enterKioskIfEnabled() }
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
        discoveryExecutor.shutdownNow()
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

    /** Opent de instellingen pas nadat het scherm SETTINGS_HOLD_DURATION_MS
     * ononderbroken ingedrukt is gehouden -- lost het `false` op zodat de
     * WebView aanraakevents gewoon zelf blijft verwerken (scrollen, knoppen). */
    private fun handleSettingsHoldTouch(event: MotionEvent) {
        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                val runnable = Runnable { showSettingsDialog() }
                settingsHoldRunnable = runnable
                mainHandler.postDelayed(runnable, SETTINGS_HOLD_DURATION_MS)
            }
            MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                settingsHoldRunnable?.let { mainHandler.removeCallbacks(it) }
                settingsHoldRunnable = null
            }
        }
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
        // Een controle die nog onderweg was toen de app afsloot: geen vensters
        // of zoektocht meer starten op een afgesloten scherm.
        if (isFinishing || isDestroyed) return
        if (reachable) {
            consecutiveHealthFailures = 0
            if (connectionErrorShowing) {
                recoverFromConnectionError()
            }
            return
        }
        consecutiveHealthFailures++
        if (connectionErrorShowing) {
            maybeStartAutoDiscovery()
        } else if (consecutiveHealthFailures >= HEALTH_CHECK_FAILURES_BEFORE_ERROR) {
            showConnectionError()
        }
    }

    /** De server is weer bereikbaar terwijl het "Geen verbinding"-venster nog
     * open stond -- sluit het vanzelf, zonder dat personeel moet tikken. Stond
     * de vervangende foutpagina nog op het scherm (nooit succesvol geladen,
     * of de app startte tijdens de storing), of werd de server op een nieuw
     * adres gevonden, dan laadt dit de echte pagina (opnieuw); anders bleef
     * de pagina + haar eigen JS-status gewoon intact, dus is enkel het venster
     * wegnemen genoeg. */
    private fun recoverFromConnectionError(message: String = "Verbinding hersteld", forceReload: Boolean = false) {
        connectionErrorDialog?.dismiss()
        connectionErrorDialog = null
        connectionErrorStatus = null
        connectionErrorShowing = false
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
        if (forceReload || !pageLoaded || showingFallbackPage) {
            loadServer(prefs.getString(KEY_SERVER, "") ?: "", prefs.getString(KEY_SCREEN, SCREEN_HOST) ?: SCREEN_HOST)
        }
    }

    /** Zoekt de server op een achtergrondthread. Vraagt iemand een resultaat
     * terwijl er al gezocht wordt, dan krijgt die gewoon hetzelfde resultaat
     * in plaats van een tweede zoektocht ernaast. */
    private fun discoverServer(onResult: (String?) -> Unit) {
        discoveryCallbacks.add(onResult)
        if (discoveryRunning) return
        discoveryRunning = true
        lastDiscoveryAtMs = System.currentTimeMillis()
        discoveryExecutor.execute {
            val found = serverDiscovery.findServer()
            mainHandler.post {
                discoveryRunning = false
                val callbacks = discoveryCallbacks.toList()
                discoveryCallbacks.clear()
                if (isFinishing || isDestroyed) return@post
                callbacks.forEach { it(found) }
            }
        }
    }

    private fun maybeStartAutoDiscovery() {
        if (discoveryRunning || settingsDialogShowing) return
        if (System.currentTimeMillis() - lastDiscoveryAtMs < DISCOVERY_RETRY_INTERVAL_MS) return
        connectionErrorStatus?.text = "Server wordt automatisch gezocht op het netwerk…"
        discoverServer(::onAutoDiscoveryResult)
    }

    private fun onAutoDiscoveryResult(found: String?) {
        // Intussen al hersteld, of personeel is zelf het adres aan het invullen.
        if (!connectionErrorShowing || settingsDialogShowing) return
        if (found == null) {
            connectionErrorStatus?.text = "Server nog niet gevonden op het netwerk — er wordt verder gezocht."
            return
        }
        val changed = found != prefs.getString(KEY_SERVER, null)
        prefs.edit().putString(KEY_SERVER, found).apply()
        recoverFromConnectionError("Server gevonden op $found", forceReload = changed)
    }

    private fun searchServerOnFirstStart() {
        val panel = brandedPanel()
        panel.addView(brandedTitle("Server zoeken…", bottomMarginDp = 16))
        panel.addView(
            ProgressBar(this).apply {
                indeterminateTintList = ColorStateList.valueOf(Color.parseColor(COLOR_SPARKX_GEEL))
                layoutParams = LinearLayout.LayoutParams(dp(48), dp(48)).apply { bottomMargin = dp(16) }
            },
        )
        panel.addView(
            brandedText(
                "De app zoekt de toelatingsserver op het wifinetwerk. Dit duurt enkele seconden.",
                bottomMarginDp = 0,
            ),
        )
        val dialog = showBrandedDialog(panel, cancelable = false)

        discoverServer { found ->
            dialog.dismiss()
            if (found == null) {
                showSettingsDialog(
                    forceShow = true,
                    notice = "Server niet automatisch gevonden. Vul het adres in dat op de pc " +
                        "bij Beheer → Systeem staat.",
                )
                return@discoverServer
            }
            prefs.edit().putString(KEY_SERVER, found).putString(KEY_SCREEN, SCREEN_HOST).apply()
            Toast.makeText(this, "Server gevonden op $found", Toast.LENGTH_SHORT).show()
            loadServer(found, SCREEN_HOST)
        }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    // ---- Sparkx-stijl voor de eigen vensters (i.p.v. het standaard grijze
    // AlertDialog-uiterlijk), zelfde kleuren als frontend/shared/style-base.css.

    private fun brandedPanel(): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        gravity = Gravity.CENTER_HORIZONTAL
        setPadding(dp(28), dp(28), dp(28), dp(24))
        background = GradientDrawable().apply {
            cornerRadius = dp(20).toFloat()
            setColor(Color.parseColor(COLOR_ACHTERGROND_PANEEL))
        }
    }

    private fun fullWidth(bottomMarginDp: Int): LinearLayout.LayoutParams = LinearLayout.LayoutParams(
        LinearLayout.LayoutParams.MATCH_PARENT,
        LinearLayout.LayoutParams.WRAP_CONTENT,
    ).apply { bottomMargin = dp(bottomMarginDp) }

    private fun brandedTitle(label: String, bottomMarginDp: Int): TextView = TextView(this).apply {
        text = label
        textSize = 20f
        setTextColor(Color.WHITE)
        typeface = Typeface.DEFAULT_BOLD
        gravity = Gravity.CENTER
        layoutParams = fullWidth(bottomMarginDp)
    }

    private fun brandedText(
        label: String,
        bottomMarginDp: Int,
        color: String = COLOR_TEKST_GEDEMPT,
        sizeSp: Float = 15f,
    ): TextView = TextView(this).apply {
        text = label
        textSize = sizeSp
        setTextColor(Color.parseColor(color))
        gravity = Gravity.CENTER
        layoutParams = fullWidth(bottomMarginDp)
    }

    private fun gradientButton(label: String, bottomMarginDp: Int): Button = Button(this).apply {
        text = label
        isAllCaps = false
        textSize = 16f
        typeface = Typeface.DEFAULT_BOLD
        setTextColor(Color.parseColor(COLOR_ACHTERGROND_DIEP))
        setPadding(dp(20), dp(14), dp(20), dp(14))
        background = GradientDrawable(
            GradientDrawable.Orientation.TL_BR,
            intArrayOf(Color.parseColor(COLOR_SPARKX_GEEL), Color.parseColor(COLOR_SPARKX_ORANJE)),
        ).apply { cornerRadius = dp(14).toFloat() }
        layoutParams = fullWidth(bottomMarginDp)
    }

    private fun darkButton(label: String, bottomMarginDp: Int): Button = Button(this).apply {
        text = label
        isAllCaps = false
        textSize = 16f
        setTextColor(Color.WHITE)
        setPadding(dp(20), dp(14), dp(20), dp(14))
        background = GradientDrawable().apply {
            cornerRadius = dp(14).toFloat()
            setColor(Color.parseColor(COLOR_ACHTERGROND_DIEP))
        }
        layoutParams = fullWidth(bottomMarginDp)
    }

    private fun showBrandedDialog(panel: View, cancelable: Boolean): AlertDialog {
        // Scrollbaar: het instellingenvenster is op een kleine telefoon (of
        // met het toetsenbord open) hoger dan het scherm.
        val content = ScrollView(this).apply { addView(panel) }
        val dialog = AlertDialog.Builder(this)
            .setView(content)
            .setCancelable(cancelable)
            .create()
        // Transparante venster-achtergrond nodig, anders overschrijft Android's
        // eigen (rechthoekige, grijze) dialoogkader onze afgeronde paneelvorm.
        dialog.window?.setBackgroundDrawableResource(android.R.color.transparent)
        dialog.show()
        return dialog
    }

    private fun sectionHeader(label: String): TextView = TextView(this).apply {
        text = label
        textSize = 15f
        setTextColor(Color.parseColor(COLOR_SPARKX_GEEL))
        typeface = Typeface.DEFAULT_BOLD
        gravity = Gravity.START
        layoutParams = fullWidth(bottomMarginDp = 8)
    }

    private fun brandedInput(hintText: String, value: String, type: Int, bottomMarginDp: Int): EditText =
        EditText(this).apply {
            hint = hintText
            setHintTextColor(Color.parseColor(COLOR_TEKST_GEDEMPT))
            setTextColor(Color.WHITE)
            inputType = type
            setText(value)
            setPadding(dp(16), dp(14), dp(16), dp(14))
            background = GradientDrawable().apply {
                cornerRadius = dp(12).toFloat()
                setColor(Color.parseColor(COLOR_ACHTERGROND_DIEP))
            }
            layoutParams = fullWidth(bottomMarginDp)
        }

    /** Twee delen: "Server" (waar staat de pc) en "Dit toestel" (naam, welk
     * scherm, vastzetten). Alles wordt pas toegepast bij Opslaan. */
    private fun showSettingsDialog(forceShow: Boolean = false, notice: String? = null) {
        settingsDialogShowing = true
        val panel = brandedPanel()
        panel.addView(brandedTitle("Instellingen", bottomMarginDp = 18))

        val status = brandedText(notice ?: "", bottomMarginDp = 14, sizeSp = 14f).apply {
            visibility = if (notice == null) View.GONE else View.VISIBLE
        }
        panel.addView(status)

        // ---- Server
        panel.addView(sectionHeader("Server"))
        val serverInput = brandedInput(
            "Adres van de pc, bv. 192.168.1.50:8000",
            prefs.getString(KEY_SERVER, "") ?: "",
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI,
            bottomMarginDp = 10,
        )
        panel.addView(serverInput)

        val searchButton = darkButton("Automatisch zoeken", bottomMarginDp = 26)
        searchButton.setOnClickListener {
            searchButton.isEnabled = false
            searchButton.text = "Zoeken…"
            status.visibility = View.VISIBLE
            status.text = "De server wordt gezocht op het wifinetwerk…"
            discoverServer { found ->
                searchButton.isEnabled = true
                searchButton.text = "Automatisch zoeken"
                if (found == null) {
                    status.text = "Niet gevonden. Controleer of deze telefoon op hetzelfde netwerk " +
                        "zit als de pc, of vul het adres uit Beheer → Systeem in."
                } else {
                    serverInput.setText(found)
                    status.text = "Gevonden! Druk op Opslaan."
                }
            }
        }
        panel.addView(searchButton)

        // ---- Dit toestel
        panel.addView(sectionHeader("Dit toestel"))
        // Verschijnt in de logs op het beheerscherm i.p.v. een toestel-code.
        val nameInput = brandedInput(
            "Naam, bv. Host 1",
            prefs.getString(KEY_DEVICE_NAME, "") ?: "",
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_CAP_SENTENCES,
            bottomMarginDp = 12,
        ).apply { filters = arrayOf(InputFilter.LengthFilter(40)) }
        panel.addView(nameInput)

        val accentTint = ColorStateList.valueOf(Color.parseColor(COLOR_SPARKX_GEEL))
        val radioGroup = RadioGroup(this).apply {
            orientation = RadioGroup.VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply {
                gravity = Gravity.START
                bottomMargin = dp(if (forceShow) 22 else 8)
            }
        }
        val hostRadio = RadioButton(this).apply {
            text = "Hostscherm"
            setTextColor(Color.WHITE)
            buttonTintList = accentTint
            id = View.generateViewId()
        }
        val adminRadio = RadioButton(this).apply {
            text = "Beheerscherm"
            setTextColor(Color.WHITE)
            buttonTintList = accentTint
            id = View.generateViewId()
        }
        radioGroup.addView(hostRadio)
        radioGroup.addView(adminRadio)
        if (prefs.getString(KEY_SCREEN, SCREEN_HOST) == SCREEN_ADMIN) {
            adminRadio.isChecked = true
        } else {
            hostRadio.isChecked = true
        }
        panel.addView(radioGroup)

        // Niet in het verplichte venster (eerste start, of vanuit "Geen
        // verbinding"): daar moet eerst een werkend serveradres komen.
        val kioskWas = prefs.getBoolean(KEY_KIOSK, false)
        var kioskSwitch: Switch? = null
        if (!forceShow) {
            val states = arrayOf(intArrayOf(android.R.attr.state_checked), intArrayOf())
            kioskSwitch = Switch(this).apply {
                text = "App vastzetten"
                textSize = 16f
                setTextColor(Color.WHITE)
                isChecked = kioskWas
                thumbTintList = ColorStateList(
                    states,
                    intArrayOf(Color.parseColor(COLOR_SPARKX_GEEL), Color.parseColor(COLOR_TEKST_GEDEMPT)),
                )
                trackTintList = ColorStateList(
                    states,
                    intArrayOf(Color.parseColor(COLOR_SPARKX_ORANJE), Color.parseColor(COLOR_ACHTERGROND_DIEP)),
                )
                setPadding(dp(4), dp(8), 0, dp(8))
                layoutParams = fullWidth(bottomMarginDp = 22)
            }
            panel.addView(kioskSwitch)
        }

        lateinit var dialog: AlertDialog

        panel.addView(
            gradientButton("Opslaan", bottomMarginDp = if (forceShow) 0 else 10).apply {
                setOnClickListener {
                    val address = serverInput.text.toString().trim()
                    val screenPath = if (adminRadio.isChecked) SCREEN_ADMIN else SCREEN_HOST
                    val kioskWanted = kioskSwitch?.isChecked ?: kioskWas
                    prefs.edit()
                        .putString(KEY_SERVER, address)
                        .putString(KEY_SCREEN, screenPath)
                        .putString(KEY_DEVICE_NAME, nameInput.text.toString().trim())
                        .putBoolean(KEY_KIOSK, kioskWanted)
                        .apply()
                    dialog.dismiss()
                    loadServer(address, screenPath)
                    if (kioskWanted && !kioskWas) mainHandler.post { enterKioskIfEnabled() }
                    if (!kioskWanted && kioskWas) exitKiosk()
                }
            },
        )

        if (!forceShow) {
            panel.addView(
                Button(this).apply {
                    text = "Annuleer"
                    isAllCaps = false
                    textSize = 16f
                    setTextColor(Color.parseColor(COLOR_TEKST_GEDEMPT))
                    setPadding(dp(20), dp(12), dp(20), dp(12))
                    background = GradientDrawable().apply {
                        cornerRadius = dp(14).toFloat()
                        setColor(Color.TRANSPARENT)
                    }
                    layoutParams = fullWidth(bottomMarginDp = 0)
                    setOnClickListener { dialog.dismiss() }
                },
            )
        }

        dialog = showBrandedDialog(panel, cancelable = !forceShow)
        // Ongeacht hoe dit venster sluit (Opslaan, Annuleer, of terugknop/
        // buiten tikken bij niet-verplicht venster): de achtergrondcontrole
        // mag pas weer een "Geen verbinding"-venster tonen vanaf hier.
        dialog.setOnDismissListener { settingsDialogShowing = false }
    }

    // ---- Kioskmodus: Android's "app vastzetten" (screen pinning). Zolang dit
    // aanstaat, kan niemand de app verlaten via de thuis- of recente-apps-
    // knop. Losmaken kan enkel via de instellingen van deze app, of via het
    // systeemgebaar (terug + overzicht ingedrukt houden) -- dat laatste kan
    // je in de Android-instellingen extra beveiligen met de pincode van het
    // toestel.

    private fun isInLockTask(): Boolean =
        (getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).lockTaskModeState !=
            ActivityManager.LOCK_TASK_MODE_NONE

    private fun enterKioskIfEnabled() {
        if (!prefs.getBoolean(KEY_KIOSK, false) || isInLockTask() || isFinishing || isDestroyed) return
        try {
            startLockTask()
        } catch (e: Exception) {
            Toast.makeText(
                this,
                "Vastzetten lukt niet — zet \"App vastzetten\" aan in de Android-instellingen (Beveiliging).",
                Toast.LENGTH_LONG,
            ).show()
        }
    }

    private fun exitKiosk() {
        if (!isInLockTask()) return
        try {
            stopLockTask()
            Toast.makeText(this, "App losgemaakt", Toast.LENGTH_SHORT).show()
        } catch (e: Exception) {
            Toast.makeText(this, "Losmaken lukte niet.", Toast.LENGTH_SHORT).show()
        }
    }

    private fun loadServer(address: String, screenPath: String) {
        showingFallbackPage = false
        val cleanAddress = address.trim().removeSuffix("/")
        val base = if (cleanAddress.startsWith("http://") || cleanAddress.startsWith("https://")) {
            "$cleanAddress$screenPath"
        } else {
            "http://$cleanAddress$screenPath"
        }
        // Het hostscherm onthoudt deze naam en geeft hem door aan de server
        // (zie frontend/host/app.js); ook leeg, zodat wissen ook doorkomt.
        val deviceName = URLEncoder.encode(prefs.getString(KEY_DEVICE_NAME, "") ?: "", "UTF-8")
        webView.loadUrl("$base?toestel=$deviceName")
    }

    private fun showConnectionError() {
        // Zolang het instellingenvenster open staat (bv. net geopend vanuit
        // dit venster om het serveradres te wijzigen) mag de achtergrond-
        // controle dit venster niet erover-tonen: de server is uiteraard nog
        // onbereikbaar zolang het juiste adres nog niet is ingevuld en
        // opgeslagen -- personeel moet hier onbeperkt de tijd voor krijgen.
        if (connectionErrorShowing || settingsDialogShowing) return
        connectionErrorShowing = true

        val panel = brandedPanel()
        panel.addView(
            TextView(this).apply {
                text = "!"
                textSize = 26f
                setTextColor(Color.WHITE)
                typeface = Typeface.DEFAULT_BOLD
                gravity = Gravity.CENTER
                val size = dp(56)
                layoutParams = LinearLayout.LayoutParams(size, size).apply { bottomMargin = dp(16) }
                background = GradientDrawable().apply {
                    shape = GradientDrawable.OVAL
                    setColor(Color.parseColor(COLOR_ROOD))
                }
            },
        )
        panel.addView(brandedTitle("Geen verbinding", bottomMarginDp = 10))
        panel.addView(
            brandedText(
                "Kan de server niet bereiken. Controleer of de pc aan staat, " +
                    "de server draait, en het IP-adres klopt.",
                bottomMarginDp = 12,
            ),
        )
        val status = brandedText("", bottomMarginDp = 22, color = COLOR_SPARKX_GEEL, sizeSp = 13f)
        panel.addView(status)

        lateinit var dialog: AlertDialog

        panel.addView(
            gradientButton("Opnieuw proberen", bottomMarginDp = 10).apply {
                setOnClickListener {
                    connectionErrorShowing = false
                    connectionErrorDialog = null
                    connectionErrorStatus = null
                    consecutiveHealthFailures = 0
                    dialog.dismiss()
                    loadServer(
                        prefs.getString(KEY_SERVER, "") ?: "",
                        prefs.getString(KEY_SCREEN, SCREEN_HOST) ?: SCREEN_HOST,
                    )
                }
            },
        )
        panel.addView(
            darkButton("Instellingen", bottomMarginDp = 0).apply {
                setOnClickListener {
                    connectionErrorShowing = false
                    connectionErrorDialog = null
                    connectionErrorStatus = null
                    consecutiveHealthFailures = 0
                    // Meteen al aan, niet pas in showSettingsDialog(): anders
                    // kan de achtergrondcontrole in het (korte) gaatje tussen
                    // dit dismiss() en het instellingenvenster alsnog dit
                    // venster heropenen.
                    settingsDialogShowing = true
                    // Pas het instellingenvenster openen nadat dit venster
                    // écht weg is, anders overlappen de twee vensters even
                    // zichtbaar (dismiss() speelt nog een afsluitanimatie af).
                    dialog.setOnDismissListener { showSettingsDialog(forceShow = true) }
                    dialog.dismiss()
                }
            },
        )

        dialog = showBrandedDialog(panel, cancelable = false)
        connectionErrorDialog = dialog
        connectionErrorStatus = status
        maybeStartAutoDiscovery()
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
