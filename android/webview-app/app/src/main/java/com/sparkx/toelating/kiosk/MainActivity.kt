package com.sparkx.toelating.kiosk

import android.annotation.SuppressLint
import android.content.Context
import android.content.SharedPreferences
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Build
import android.os.Bundle
import android.text.InputType
import android.view.Gravity
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity

private const val PREFS_NAME = "toelating_kiosk"
private const val KEY_SERVER = "server_address"
private const val KEY_SCREEN = "screen_path"
private const val SCREEN_HOST = "/"
private const val SCREEN_ADMIN = "/admin/"

/**
 * Toont het bestaande, al geteste webhostscherm/beheerscherm (zie backend/ +
 * frontend/) als volwaardige Android-app: eigen icoon, geen adresbalk,
 * volledig scherm. De server (FastAPI) blijft draaien op een pc op het
 * lokale netwerk — deze app verandert niets aan hoe scannen of inloggen
 * werkt, enkel welk toestel de pagina toont.
 *
 * Een USB/Bluetooth-NFC-lezer die als toetsenbord werkt (zie
 * frontend/shared/reader.js: KeyboardWedgeReader) stuurt zijn toetsaanslagen
 * gewoon door naar de pagina in de WebView, net als in een gewone browser —
 * dit is niet met een echt toestel getest vanuit deze omgeving.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var prefs: SharedPreferences

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

        webView = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = true
            settings.setSupportZoom(false)
            settings.builtInZoomControls = false
            isLongClickable = false
            setOnLongClickListener { true }
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

        val settingsButton = TextView(this).apply {
            text = "⚙"
            textSize = 18f
            setTextColor(Color.WHITE)
            gravity = Gravity.CENTER
            background = GradientDrawable().apply {
                shape = GradientDrawable.OVAL
                setColor(Color.parseColor("#55000000"))
            }
            setOnClickListener { showSettingsDialog() }
        }

        val root = FrameLayout(this).apply {
            addView(
                webView,
                FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT),
            )
            addView(
                settingsButton,
                FrameLayout.LayoutParams(dp(40), dp(40), Gravity.BOTTOM or Gravity.END).apply {
                    setMargins(0, 0, dp(8), dp(8))
                },
            )
        }

        setContentView(root)
        applyFullscreen()

        val savedServer = prefs.getString(KEY_SERVER, null)
        if (savedServer.isNullOrBlank()) {
            showSettingsDialog(forceShow = true)
        } else {
            loadServer(savedServer, prefs.getString(KEY_SCREEN, SCREEN_HOST) ?: SCREEN_HOST)
        }
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) applyFullscreen()
    }

    private fun applyFullscreen() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window.setDecorFitsSystemWindows(false)
            window.insetsController?.let {
                it.hide(WindowInsets.Type.systemBars())
                it.systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            }
        } else {
            @Suppress("DEPRECATION")
            window.decorView.systemUiVisibility = (
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                    or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                    or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                    or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                    or View.SYSTEM_UI_FLAG_FULLSCREEN
                )
        }
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
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
        AlertDialog.Builder(this)
            .setTitle("Geen verbinding")
            .setMessage(
                "Kan de server niet bereiken. Controleer of de pc aan staat, " +
                    "de server draait, en het IP-adres klopt.",
            )
            .setPositiveButton("Instellingen") { _, _ -> showSettingsDialog(forceShow = true) }
            .setNegativeButton("Opnieuw proberen") { _, _ ->
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
