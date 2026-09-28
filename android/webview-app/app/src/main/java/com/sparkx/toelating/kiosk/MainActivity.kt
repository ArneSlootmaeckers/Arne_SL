package com.sparkx.toelating.kiosk

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.res.ColorStateList
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
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
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.TextView
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
// Bewust op scherp gezet (1 mislukking is genoeg, elke 2 seconden gecheckt):
// bij dit systeem mag een onbereikbare server nooit onopgemerkt blijven, dus
// geen risico nemen met een aantal pogingen of een trage interval -- de
// automatische herstelfunctie (zie recoverFromConnectionError) zorgt dat een
// vals alarm bij een heel kort haperingetje vanzelf meteen weer verdwijnt.
private const val HEALTH_CHECK_INTERVAL_MS = 2000L
private const val HEALTH_CHECK_TIMEOUT_MS = 2500
private const val HEALTH_CHECK_FAILURES_BEFORE_ERROR = 1

// Bewust lang: een gewone lange druk (~0,5s) is te makkelijk per ongeluk te
// raken tijdens normaal gebruik van de knoppen op de pagina.
private const val SETTINGS_HOLD_DURATION_MS = 10000L

// Zelfde Sparkx-huisstijlkleuren als frontend/shared/style-base.css, voor het
// "Geen verbinding"-venster (zie showConnectionError).
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
 * (in onResume/onPause), en toont na een paar mislukkingen op rij hetzelfde
 * "Geen verbinding"-dialoogvenster als bij een mislukte eerste keer laden --
 * een duidelijk, actief signaal in plaats van enkel een bannertje.
 *
 * Die controle blijft ook doorlopen terwijl dat venster open staat, en sluit
 * het dan automatisch zodra de server weer bereikbaar is (bv. na een korte
 * wifi-onderbreking die vanzelf hersteld is) -- personeel hoeft dus niet
 * zelf op "Opnieuw proberen" te tikken. Was de allereerste paginalading zelf
 * mislukt (pageLoaded nog false, bv. de app werd gestart tijdens een storing),
 * dan laadt dat herstel de pagina meteen alsnog, want dan staat er nog
 * niets bruikbaars op het scherm om gewoon op verder te werken.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var prefs: SharedPreferences
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
    private var pageLoaded = false
    private var showingFallbackPage = false
    private var settingsDialogShowing = false

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
        if (reachable) {
            consecutiveHealthFailures = 0
            if (connectionErrorShowing) {
                recoverFromConnectionError()
            }
            return
        }
        consecutiveHealthFailures++
        if (consecutiveHealthFailures >= HEALTH_CHECK_FAILURES_BEFORE_ERROR && !connectionErrorShowing) {
            showConnectionError()
        }
    }

    /** De server is weer bereikbaar terwijl het "Geen verbinding"-venster nog
     * open stond -- sluit het vanzelf, zonder dat personeel moet tikken. Stond
     * de vervangende foutpagina nog op het scherm (nooit succesvol geladen,
     * of de app startte tijdens de storing), dan laadt dit de echte pagina
     * alsnog; anders bleef de pagina + haar eigen JS-status gewoon intact,
     * dus is enkel het venster wegnemen genoeg. */
    private fun recoverFromConnectionError() {
        connectionErrorDialog?.dismiss()
        connectionErrorDialog = null
        connectionErrorShowing = false
        Toast.makeText(this, "Verbinding hersteld", Toast.LENGTH_SHORT).show()
        if (!pageLoaded || showingFallbackPage) {
            loadServer(prefs.getString(KEY_SERVER, "") ?: "", prefs.getString(KEY_SCREEN, SCREEN_HOST) ?: SCREEN_HOST)
        }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    /** Zelfde in code opgebouwde Sparkx-stijl als showConnectionError, i.p.v.
     * het standaard grijze AlertDialog-uiterlijk. */
    private fun showSettingsDialog(forceShow: Boolean = false) {
        settingsDialogShowing = true
        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(28), dp(28), dp(28), dp(24))
            background = GradientDrawable().apply {
                cornerRadius = dp(20).toFloat()
                setColor(Color.parseColor(COLOR_ACHTERGROND_PANEEL))
            }
        }

        panel.addView(
            TextView(this).apply {
                text = "Serverinstellingen"
                textSize = 20f
                setTextColor(Color.WHITE)
                typeface = Typeface.DEFAULT_BOLD
                gravity = Gravity.CENTER
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ).apply { bottomMargin = dp(18) }
            },
        )

        val serverInput = EditText(this).apply {
            hint = "bv. 192.168.1.50:8000"
            setHintTextColor(Color.parseColor(COLOR_TEKST_GEDEMPT))
            setTextColor(Color.WHITE)
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_URI
            setText(prefs.getString(KEY_SERVER, ""))
            setPadding(dp(16), dp(14), dp(16), dp(14))
            background = GradientDrawable().apply {
                cornerRadius = dp(12).toFloat()
                setColor(Color.parseColor(COLOR_ACHTERGROND_DIEP))
            }
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { bottomMargin = dp(18) }
        }
        panel.addView(serverInput)

        val accentTint = ColorStateList.valueOf(Color.parseColor(COLOR_SPARKX_GEEL))
        val radioGroup = RadioGroup(this).apply {
            orientation = RadioGroup.VERTICAL
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT,
            ).apply { bottomMargin = dp(22) }
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

        lateinit var dialog: AlertDialog

        panel.addView(
            Button(this).apply {
                text = "Opslaan"
                isAllCaps = false
                textSize = 16f
                typeface = Typeface.DEFAULT_BOLD
                setTextColor(Color.parseColor(COLOR_ACHTERGROND_DIEP))
                setPadding(dp(20), dp(14), dp(20), dp(14))
                background = GradientDrawable(
                    GradientDrawable.Orientation.TL_BR,
                    intArrayOf(Color.parseColor(COLOR_SPARKX_GEEL), Color.parseColor(COLOR_SPARKX_ORANJE)),
                ).apply { cornerRadius = dp(14).toFloat() }
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ).apply { if (!forceShow) bottomMargin = dp(10) }
                setOnClickListener {
                    val address = serverInput.text.toString().trim()
                    val screenPath = if (adminRadio.isChecked) SCREEN_ADMIN else SCREEN_HOST
                    prefs.edit().putString(KEY_SERVER, address).putString(KEY_SCREEN, screenPath).apply()
                    dialog.dismiss()
                    loadServer(address, screenPath)
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
                    layoutParams = LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT,
                        LinearLayout.LayoutParams.WRAP_CONTENT,
                    )
                    setOnClickListener { dialog.dismiss() }
                },
            )
        }

        dialog = AlertDialog.Builder(this)
            .setView(panel)
            .setCancelable(!forceShow)
            .create()
        // Ongeacht hoe dit venster sluit (Opslaan, Annuleer, of terugknop/
        // buiten tikken bij niet-verplicht venster): de achtergrondcontrole
        // mag pas weer een "Geen verbinding"-venster tonen vanaf hier.
        dialog.setOnDismissListener { settingsDialogShowing = false }
        dialog.window?.setBackgroundDrawableResource(android.R.color.transparent)
        dialog.show()
    }

    private fun loadServer(address: String, screenPath: String) {
        showingFallbackPage = false
        val cleanAddress = address.trim().removeSuffix("/")
        val url = if (cleanAddress.startsWith("http://") || cleanAddress.startsWith("https://")) {
            "$cleanAddress$screenPath"
        } else {
            "http://$cleanAddress$screenPath"
        }
        webView.loadUrl(url)
    }

    /** Eigen, in code opgebouwd venster (i.p.v. het standaard grijze
     * AlertDialog-uiterlijk) in de Sparkx-huisstijl van de webpagina zelf
     * (donker petrolblauw paneel, geel-oranje verloopaccent -- zie
     * frontend/shared/style-base.css voor dezelfde kleuren). */
    private fun showConnectionError() {
        // Zolang het instellingenvenster open staat (bv. net geopend vanuit
        // dit venster om het serveradres te wijzigen) mag de achtergrond-
        // controle dit venster niet erover-tonen: de server is uiteraard nog
        // onbereikbaar zolang het juiste adres nog niet is ingevuld en
        // opgeslagen -- personeel moet hier onbeperkt de tijd voor krijgen.
        if (connectionErrorShowing || settingsDialogShowing) return
        connectionErrorShowing = true

        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(dp(28), dp(28), dp(28), dp(24))
            background = GradientDrawable().apply {
                cornerRadius = dp(20).toFloat()
                setColor(Color.parseColor(COLOR_ACHTERGROND_PANEEL))
            }
        }

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

        panel.addView(
            TextView(this).apply {
                text = "Geen verbinding"
                textSize = 20f
                setTextColor(Color.WHITE)
                typeface = Typeface.DEFAULT_BOLD
                gravity = Gravity.CENTER
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ).apply { bottomMargin = dp(10) }
            },
        )

        panel.addView(
            TextView(this).apply {
                text = "Kan de server niet bereiken. Controleer of de pc aan staat, " +
                    "de server draait, en het IP-adres klopt."
                textSize = 15f
                setTextColor(Color.parseColor(COLOR_TEKST_GEDEMPT))
                gravity = Gravity.CENTER
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ).apply { bottomMargin = dp(22) }
            },
        )

        lateinit var dialog: AlertDialog

        panel.addView(
            Button(this).apply {
                text = "Opnieuw proberen"
                isAllCaps = false
                textSize = 16f
                typeface = Typeface.DEFAULT_BOLD
                setTextColor(Color.parseColor(COLOR_ACHTERGROND_DIEP))
                setPadding(dp(20), dp(14), dp(20), dp(14))
                background = GradientDrawable(
                    GradientDrawable.Orientation.TL_BR,
                    intArrayOf(Color.parseColor(COLOR_SPARKX_GEEL), Color.parseColor(COLOR_SPARKX_ORANJE)),
                ).apply { cornerRadius = dp(14).toFloat() }
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                ).apply { bottomMargin = dp(10) }
                setOnClickListener {
                    connectionErrorShowing = false
                    connectionErrorDialog = null
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
            Button(this).apply {
                text = "Instellingen"
                isAllCaps = false
                textSize = 16f
                setTextColor(Color.WHITE)
                setPadding(dp(20), dp(14), dp(20), dp(14))
                background = GradientDrawable().apply {
                    cornerRadius = dp(14).toFloat()
                    setColor(Color.parseColor(COLOR_ACHTERGROND_DIEP))
                }
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                )
                setOnClickListener {
                    connectionErrorShowing = false
                    connectionErrorDialog = null
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

        dialog = AlertDialog.Builder(this)
            .setView(panel)
            .setCancelable(false)
            .create()
        // Transparante venster-achtergrond nodig, anders overschrijft Android's
        // eigen (rechthoekige, grijze) dialoogkader onze afgeronde paneelvorm.
        dialog.window?.setBackgroundDrawableResource(android.R.color.transparent)
        dialog.show()
        connectionErrorDialog = dialog
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
