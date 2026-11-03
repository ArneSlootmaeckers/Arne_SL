import { ADMIN_TOKEN_KEY, ApiError, api, startHealthPolling } from "../shared/api.js";
import { KeyboardWedgeReader, NativeBridgeReader } from "../shared/reader.js";
import { enhanceSelect } from "./picker.js";

const POLLING_INTERVAL_MS = 3000;
// Mirrors config.yaml's session_inactivity_timeout_seconds default; the
// server is authoritative (a 401 always triggers logout regardless), this
// just makes the UI itself drop back to the login screen at the same pace.
const INACTIVITY_TIMEOUT_MS = 120_000;
const INACTIVITY_CHECK_INTERVAL_MS = 5000;

const EMPLOYEE_LABEL_KEY = "toelating_admin_employee";

const STATUS_INFO = {
  NOG_NIET_GESPRONGEN: { kleur: "groen", tekst: "Nog niet gesprongen" },
  HERKANSING: { kleur: "oranje", tekst: "Herkansing" },
  GESLAAGD: { kleur: "groen", tekst: "Geslaagd" },
  NIET_GESLAAGD: { kleur: "rood", tekst: "Niet geslaagd" },
};

const EVENT_LABELS = {
  SCAN: "Scan",
  OORDEEL: "Oordeel",
  OEFENSPRONG: "Oefensprong",
  GEANNULEERD: "Geannuleerd",
  TIME_OUT: "Time-out",
  TOEGANG_SKI_JUMP: "Toegang Ski Jump",
  HANDMATIGE_WIJZIGING: "Handmatige wijziging",
  INLOGGEN: "Inloggen",
  INLOGGEN_MISLUKT: "Inloggen mislukt",
  INLOGGEN_GEBLOKKEERD: "Inloggen geblokkeerd (te veel foute pincodes)",
  UITLOGGEN: "Uitloggen",
  PINCODE_INGESTELD: "Pincode ingesteld",
  GROEP_UITGEZET: "Groep uitgezet",
  KOPPELCODE_AANGEMAAKT: "Koppelcode aangemaakt",
  TOESTEL_GEKOPPELD: "Toestel gekoppeld",
  TOESTEL_ONTKOPPELD: "Toestel ontkoppeld",
  KOPPELEN_MISLUKT: "Koppelen mislukt",
  KOPPELEN_GEBLOKKEERD: "Koppelen geblokkeerd (te veel foute codes)",
  SYSTEEM_AFSLUITEN: "Systeem afgesloten",
};

const VERDICT_LABELS = { GROEN: "geslaagd", ROOD: "gefaald" };

/** "SOME_CODE" -> "Some code", voor codes die (nog) geen eigen label hebben. */
function humanize(code) {
  const text = String(code).replaceAll("_", " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function eventLabel(eventType) {
  return EVENT_LABELS[eventType] ?? humanize(eventType);
}

/** Naam van de telefoon ("Host 1") als die ingesteld is, anders de code. */
function sourceLabel(event) {
  return event.device_name || event.source;
}

/** {"oude_status": "HERKANSING", "reden": "..."} -> "oude status: Herkansing · reden: ..."
 * Vrije tekst (zoals een reden) blijft ongewijzigd; enkel gekende codes worden vertaald. */
function formatDetail(detail) {
  if (!detail) return "";
  return Object.entries(detail)
    .map(([key, value]) => {
      let text;
      if (value === null || value === undefined) text = "—";
      else if (typeof value === "boolean") text = value ? "ja" : "nee";
      else if (STATUS_INFO[value]) text = STATUS_INFO[value].tekst;
      else if (VERDICT_LABELS[value]) text = VERDICT_LABELS[value];
      else text = String(value);
      return `${key.replaceAll("_", " ")}: ${text}`;
    })
    .join(" · ");
}

/** Tabelrij via textContent, zodat tekst uit de logs (bandje-ID's, redenen)
 * nooit als HTML geïnterpreteerd wordt. */
function tableRow(cells) {
  const row = document.createElement("tr");
  for (const value of cells) {
    const cell = document.createElement("td");
    cell.textContent = value;
    row.append(cell);
  }
  return row;
}

const els = {
  banner: document.getElementById("connection-banner"),
  loginView: document.getElementById("login-view"),
  adminView: document.getElementById("admin-view"),
  loginForm: document.getElementById("login-form"),
  pincodeInput: document.getElementById("pincode-input"),
  loginError: document.getElementById("login-error"),
  userLabel: document.getElementById("user-label"),
  logoutBtn: document.getElementById("logout-btn"),
  tabButtons: [...document.querySelectorAll(".tab-btn")],
  tabPanels: {
    bandje: document.getElementById("tab-bandje"),
    logs: document.getElementById("tab-logs"),
    rapport: document.getElementById("tab-rapport"),
    pincodes: document.getElementById("tab-pincodes"),
    systeem: document.getElementById("tab-systeem"),
  },

  wristbandLookupForm: document.getElementById("wristband-lookup-form"),
  wristbandInput: document.getElementById("wristband-input"),
  wristbandResult: document.getElementById("wristband-result"),
  wristbandResultId: document.getElementById("wristband-result-id"),
  wristbandStatusBadge: document.getElementById("wristband-status-badge"),
  overrideCard: document.getElementById("override-card"),
  overrideForm: document.getElementById("override-form"),
  overrideStatus: document.getElementById("override-status"),
  overrideReason: document.getElementById("override-reason"),
  overrideMessage: document.getElementById("override-message"),
  wristbandHistoryBody: document.querySelector("#wristband-history-table tbody"),

  logsFilterForm: document.getElementById("logs-filter-form"),
  logsFilterDate: document.getElementById("logs-filter-date"),
  logsFilterWristband: document.getElementById("logs-filter-wristband"),
  logsFilterGroup: document.getElementById("logs-filter-group"),
  logsFilterType: document.getElementById("logs-filter-type"),
  logsTableBody: document.querySelector("#logs-table tbody"),
  exportCsvBtn: document.getElementById("export-csv-btn"),

  reportForm: document.getElementById("report-form"),
  reportDate: document.getElementById("report-date"),
  reportStats: document.getElementById("report-stats"),
  statTotaal: document.getElementById("stat-totaal"),
  statGeslaagd: document.getElementById("stat-geslaagd"),
  statHerkansing: document.getElementById("stat-herkansing"),
  statNietGeslaagd: document.getElementById("stat-niet-geslaagd"),
  statOefensprongen: document.getElementById("stat-oefensprongen"),
  statGemiddelde: document.getElementById("stat-gemiddelde"),

  groupsTableBody: document.querySelector("#groups-table tbody"),
  groupsMessage: document.getElementById("groups-message"),
  groupPincodeForm: document.getElementById("group-pincode-form"),
  groupPincodeRole: document.getElementById("group-pincode-role"),
  groupPincode: document.getElementById("group-pincode"),
  groupPincodeConfirm: document.getElementById("group-pincode-confirm"),
  groupPincodeMessage: document.getElementById("group-pincode-message"),

  networkAddresses: document.getElementById("network-addresses"),
  networkNote: document.getElementById("network-note"),
  networkRefreshBtn: document.getElementById("network-refresh-btn"),
  networkFingerprint: document.getElementById("network-fingerprint"),
  networkFingerprintValue: document.getElementById("network-fingerprint-value"),
  pincodeWarning: document.getElementById("pincode-warning"),

  pairingCodeBtn: document.getElementById("pairing-code-btn"),
  pairingCodeResult: document.getElementById("pairing-code-result"),
  pairingCodeValue: document.getElementById("pairing-code-value"),
  pairingCodeExpiry: document.getElementById("pairing-code-expiry"),
  devicesMessage: document.getElementById("devices-message"),
  devicesTableBody: document.querySelector("#devices-table tbody"),

  shutdownBtn: document.getElementById("shutdown-btn"),
  shutdownMessage: document.getElementById("shutdown-message"),
};

let currentEmployee = null;
let lastActivityAt = Date.now();

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function formatTimestamp(iso) {
  return new Date(iso).toLocaleString("nl-BE");
}

// ---- Auth / session ------------------------------------------------------

function showLogin(message) {
  currentEmployee = null;
  localStorage.removeItem(ADMIN_TOKEN_KEY);
  localStorage.removeItem(EMPLOYEE_LABEL_KEY);
  els.adminView.classList.add("hidden");
  els.loginView.classList.remove("hidden");
  els.pincodeWarning.classList.add("hidden");
  els.pairingCodeResult.classList.add("hidden");
  els.pincodeInput.value = "";
  if (message) {
    els.loginError.textContent = message;
    els.loginError.classList.remove("hidden");
  } else {
    els.loginError.classList.add("hidden");
  }
}

function showAdmin(employee) {
  currentEmployee = employee;
  localStorage.setItem(EMPLOYEE_LABEL_KEY, JSON.stringify(employee));
  els.loginView.classList.add("hidden");
  els.adminView.classList.remove("hidden");
  // De naam is het label van de groep ("Vaste medewerkers"): er zijn geen
  // persoonlijke accounts.
  els.userLabel.textContent = employee.name;

  // Enkel de tabbladen van deze groep; de server weigert de rest sowieso.
  for (const btn of els.tabButtons) {
    btn.classList.toggle("hidden", !btn.dataset.roles.split(" ").includes(employee.role));
  }
  if (els.tabButtons.find((b) => b.dataset.tab === activeTab).classList.contains("hidden")) {
    switchTab("bandje");
  }
  // Studenten mogen een bandje enkel opzoeken, niet aanpassen.
  els.overrideCard.classList.toggle("hidden", employee.role === "student");

  lastActivityAt = Date.now();
}

els.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const result = await api.login(els.pincodeInput.value);
    localStorage.setItem(ADMIN_TOKEN_KEY, result.token);
    showAdmin({ id: result.employee_id, name: result.name, role: result.role });
    els.pincodeWarning.classList.toggle("hidden", !result.short_pincode);
  } catch (err) {
    showLogin(err instanceof ApiError ? err.message : "Aanmelden mislukt.");
  }
});

els.logoutBtn.addEventListener("click", async () => {
  try {
    await api.logout();
  } catch {
    // best-effort
  }
  showLogin();
});

function handleUnauthorized() {
  showLogin("Sessie verlopen. Log opnieuw in.");
}

for (const eventName of ["click", "keydown", "touchstart"]) {
  document.addEventListener(eventName, () => {
    lastActivityAt = Date.now();
  });
}

setInterval(() => {
  if (currentEmployee && Date.now() - lastActivityAt > INACTIVITY_TIMEOUT_MS) {
    api.logout().catch(() => {});
    showLogin("Automatisch uitgelogd wegens inactiviteit.");
  }
}, INACTIVITY_CHECK_INTERVAL_MS);

// ---- Tabs ------------------------------------------------------------

let activeTab = "bandje";

function switchTab(tab) {
  activeTab = tab;
  for (const btn of els.tabButtons) {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  }
  for (const [name, panel] of Object.entries(els.tabPanels)) {
    panel.classList.toggle("hidden", name !== tab);
  }
}

for (const btn of els.tabButtons) {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
}

// ---- Bandje tab --------------------------------------------------------

async function lookupWristband(wristbandId) {
  if (!wristbandId) return;
  els.wristbandInput.value = wristbandId;
  try {
    const status = await api.wristbandStatus(wristbandId);
    renderWristbandStatus(status);
    await loadWristbandHistory(wristbandId);
    els.wristbandResult.classList.remove("hidden");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    els.overrideMessage.textContent = err instanceof ApiError ? err.message : "Fout bij opzoeken.";
    els.overrideMessage.className = "message error";
    els.overrideMessage.classList.remove("hidden");
  }
}

function renderWristbandStatus(body) {
  els.wristbandResultId.textContent = body.wristband_id;
  const info = STATUS_INFO[body.status];
  els.wristbandStatusBadge.textContent = info.tekst;
  els.wristbandStatusBadge.className = `status-badge status-${info.kleur}`;
  els.overrideStatus.value = body.status;
}

async function loadWristbandHistory(wristbandId) {
  const events = await api.wristbandHistory(wristbandId);
  els.wristbandHistoryBody.innerHTML = "";
  for (const event of events) {
    els.wristbandHistoryBody.append(
      tableRow([formatTimestamp(event.timestamp), eventLabel(event.event_type), sourceLabel(event), formatDetail(event.detail)])
    );
  }
}

els.wristbandLookupForm.addEventListener("submit", (event) => {
  event.preventDefault();
  lookupWristband(els.wristbandInput.value.trim());
});

els.overrideForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const wristbandId = els.wristbandInput.value.trim();
  if (!wristbandId) return;
  try {
    const result = await api.setWristbandStatus(wristbandId, els.overrideStatus.value, els.overrideReason.value || null);
    renderWristbandStatus(result);
    await loadWristbandHistory(wristbandId);
    els.overrideMessage.textContent = "Status aangepast.";
    els.overrideMessage.className = "message success";
    els.overrideMessage.classList.remove("hidden");
    els.overrideReason.value = "";
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    els.overrideMessage.textContent = err instanceof ApiError ? err.message : "Fout bij aanpassen.";
    els.overrideMessage.className = "message error";
    els.overrideMessage.classList.remove("hidden");
  }
});

// A real/simulated scan while on the "Bandje" tab looks the wristband up directly.
new KeyboardWedgeReader().start((wristbandId) => {
  if (activeTab === "bandje") lookupWristband(wristbandId);
});
new NativeBridgeReader().start((wristbandId) => {
  if (activeTab === "bandje") lookupWristband(wristbandId);
});

// ---- Logs tab -----------------------------------------------------------

function currentLogFilters() {
  return {
    event_date: els.logsFilterDate.value || undefined,
    wristband_id: els.logsFilterWristband.value.trim() || undefined,
    role: els.logsFilterGroup.value || undefined,
    event_type: els.logsFilterType.value || undefined,
    limit: 500,
  };
}

async function searchLogs() {
  try {
    const events = await api.logs(currentLogFilters());
    els.logsTableBody.innerHTML = "";
    for (const event of events) {
      els.logsTableBody.append(
        tableRow([
          formatTimestamp(event.timestamp),
          eventLabel(event.event_type),
          event.wristband_id || "",
          sourceLabel(event),
          event.group ?? "",
          formatDetail(event.detail),
        ])
      );
    }
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    console.error(err);
  }
}

els.logsFilterForm.addEventListener("submit", (event) => {
  event.preventDefault();
  searchLogs();
});

els.exportCsvBtn.addEventListener("click", async () => {
  try {
    const blob = await api.exportLogsCsv(currentLogFilters());
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "logs.csv";
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    console.error(err);
  }
});

// ---- Dagoverzicht tab -----------------------------------------------------

async function showReport(dateStr) {
  try {
    const report = await api.report(dateStr);
    els.statTotaal.textContent = report.totaal_testsprongen;
    els.statGeslaagd.textContent = report.geslaagd;
    els.statHerkansing.textContent = report.herkansing;
    els.statNietGeslaagd.textContent = report.niet_geslaagd;
    els.statOefensprongen.textContent = report.oefensprongen;
    els.statGemiddelde.textContent =
      report.gemiddelde_tijd_tussen_sprongen_seconden != null
        ? `${Math.round(report.gemiddelde_tijd_tussen_sprongen_seconden)}s`
        : "–";
    els.reportStats.classList.remove("hidden");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    console.error(err);
  }
}

els.reportForm.addEventListener("submit", (event) => {
  event.preventDefault();
  showReport(els.reportDate.value || todayIso());
});

// ---- Pincodes tab ---------------------------------------------------------

const GROUP_PERMISSIONS = {
  admin: "Alles: ook pincodes, telefoons koppelen en afsluiten",
  supervisor: "Bandjes opzoeken en corrigeren, logs, dagoverzicht",
  student: "Enkel een bandje opzoeken",
};

function showMessage(el, text, kind) {
  el.textContent = text;
  el.className = `message ${kind}`;
  el.classList.toggle("hidden", !text);
}

async function loadGroups() {
  try {
    const groups = await api.groups();
    els.groupsTableBody.textContent = "";
    for (const group of groups) {
      const row = tableRow([group.label, GROUP_PERMISSIONS[group.role] ?? "", group.active ? "Ingesteld" : "Uit"]);
      const actions = document.createElement("td");
      // De beheerder uitzetten kan niet: dan raakt niemand er nog in.
      if (group.active && group.role !== "admin") {
        const disableBtn = document.createElement("button");
        disableBtn.type = "button";
        disableBtn.className = "btn-secondary";
        disableBtn.dataset.role = group.role;
        disableBtn.dataset.label = group.label;
        disableBtn.textContent = "Uitzetten";
        actions.append(disableBtn);
      }
      row.append(actions);
      els.groupsTableBody.append(row);
    }
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    showMessage(els.groupsMessage, err instanceof ApiError ? err.message : "Kon de groepen niet ophalen.", "error");
  }
}

els.groupsTableBody.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-role]");
  if (!btn) return;
  const confirmed = confirm(
    `Toegang voor "${btn.dataset.label}" uitzetten? Niemand van die groep kan dan nog inloggen, ` +
      "tot je een nieuwe pincode instelt."
  );
  if (!confirmed) return;
  try {
    await api.disableGroup(btn.dataset.role);
    showMessage(els.groupsMessage, `"${btn.dataset.label}" kan niet meer inloggen.`, "success");
    await loadGroups();
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    showMessage(els.groupsMessage, err instanceof ApiError ? err.message : "Uitzetten mislukt.", "error");
  }
});

els.groupPincodeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const pincode = els.groupPincode.value.trim();
  if (pincode !== els.groupPincodeConfirm.value.trim()) {
    showMessage(els.groupPincodeMessage, "De pincodes komen niet overeen.", "error");
    return;
  }
  const label = els.groupPincodeRole.options[els.groupPincodeRole.selectedIndex].textContent;
  try {
    await api.setGroupPincode(els.groupPincodeRole.value, pincode);
    showMessage(els.groupPincodeMessage, `Nieuwe pincode voor "${label}" ingesteld.`, "success");
    els.groupPincode.value = "";
    els.groupPincodeConfirm.value = "";
    await loadGroups();
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    showMessage(els.groupPincodeMessage, err instanceof ApiError ? err.message : "Opslaan mislukt.", "error");
  }
});

document.querySelector('.tab-btn[data-tab="pincodes"]').addEventListener("click", loadGroups);

// ---- Systeem tab ----------------------------------------------------------

function showNetworkNote(text) {
  els.networkNote.textContent = text;
  els.networkNote.classList.toggle("hidden", !text);
}

async function loadNetworkInfo() {
  els.networkAddresses.textContent = "";
  showNetworkNote("");
  try {
    const info = await api.networkInfo();
    els.networkFingerprintValue.textContent = info.certificate_fingerprint ?? "";
    els.networkFingerprint.classList.toggle("hidden", !info.certificate_fingerprint);
    if (info.addresses.length === 0) {
      showNetworkNote(
        "Geen netwerkverbinding gevonden op deze pc. Controleer of de " +
          "netwerkkabel/wifi verbonden is en klik op Vernieuwen."
      );
      return;
    }
    info.addresses.forEach((address, index) => {
      const row = document.createElement("div");
      const value = document.createElement("span");
      value.className = "network-address";
      value.textContent = `${address}:${info.port}`;
      row.append(value);
      if (index === 0 && info.addresses.length > 1) {
        const hint = document.createElement("div");
        hint.className = "network-address-hint";
        hint.textContent = "Meest waarschijnlijk — probeer dit eerst.";
        row.append(hint);
      }
      els.networkAddresses.append(row);
    });
    if (info.addresses.length > 1) {
      showNetworkNote(
        "Deze pc heeft meerdere netwerkverbindingen. Werkt het eerste adres " +
          "niet in de app, probeer dan het volgende."
      );
    }
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    showNetworkNote(err instanceof ApiError ? err.message : "Kon het IP-adres niet ophalen.");
  }
}

function showDevicesMessage(text, kind = "error") {
  els.devicesMessage.textContent = text;
  els.devicesMessage.className = `message ${kind}`;
  els.devicesMessage.classList.toggle("hidden", !text);
}

async function loadDevices() {
  try {
    const devices = await api.pairedDevices();
    els.devicesTableBody.textContent = "";
    if (devices.length === 0) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 4;
      cell.textContent = "Nog geen toestellen gekoppeld.";
      row.append(cell);
      els.devicesTableBody.append(row);
    }
    for (const device of devices) {
      const row = document.createElement("tr");
      // textContent, nooit innerHTML: de naam komt van de telefoon zelf.
      for (const text of [
        device.name || device.device_id,
        formatTimestamp(device.paired_at),
        formatTimestamp(device.last_seen_at),
      ]) {
        const cell = document.createElement("td");
        cell.textContent = text;
        row.append(cell);
      }
      const actions = document.createElement("td");
      const unpairBtn = document.createElement("button");
      unpairBtn.type = "button";
      unpairBtn.className = "btn-secondary";
      unpairBtn.dataset.id = device.device_id;
      unpairBtn.dataset.name = device.name || device.device_id;
      unpairBtn.textContent = "Ontkoppelen";
      actions.append(unpairBtn);
      row.append(actions);
      els.devicesTableBody.append(row);
    }
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    showDevicesMessage(err instanceof ApiError ? err.message : "Kon de toestellen niet ophalen.");
  }
}

els.pairingCodeBtn.addEventListener("click", async () => {
  showDevicesMessage("");
  try {
    const result = await api.createPairingCode();
    els.pairingCodeValue.textContent = result.code;
    const until = new Date(result.expires_at).toLocaleTimeString("nl-BE", { hour: "2-digit", minute: "2-digit" });
    els.pairingCodeExpiry.textContent = `Geldig tot ${until}, voor één toestel.`;
    els.pairingCodeResult.classList.remove("hidden");
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    showDevicesMessage(err instanceof ApiError ? err.message : "Kon geen koppelcode aanmaken.");
  }
});

els.devicesTableBody.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-id]");
  if (!btn) return;
  const confirmed = confirm(
    `Toestel "${btn.dataset.name}" ontkoppelen? Het kan dan meteen niet meer ` +
      "scannen tot het opnieuw gekoppeld wordt met een nieuwe code."
  );
  if (!confirmed) return;
  try {
    await api.unpairDevice(btn.dataset.id);
    showDevicesMessage(`"${btn.dataset.name}" is ontkoppeld.`, "success");
    await loadDevices();
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    showDevicesMessage(err instanceof ApiError ? err.message : "Ontkoppelen mislukt.");
  }
});

function loadSystemTab() {
  loadNetworkInfo();
  loadDevices();
}

document.querySelector('.tab-btn[data-tab="systeem"]').addEventListener("click", loadSystemTab);
els.networkRefreshBtn.addEventListener("click", loadSystemTab);

els.shutdownBtn.addEventListener("click", async () => {
  const confirmed = confirm(
    "Weet je zeker dat je de applicatie wil afsluiten? Het host- en " +
      "beheerscherm werken dan niet meer, ook niet op de telefoon. " +
      "Enkel via de pc zelf terug op te starten — dit kan niet vanaf de telefoon."
  );
  if (!confirmed) return;

  els.shutdownBtn.disabled = true;
  try {
    await api.shutdown();
    els.shutdownMessage.textContent = "Server wordt afgesloten… Je kan dit venster nu sluiten.";
    els.shutdownMessage.className = "message success";
    els.shutdownMessage.classList.remove("hidden");
    // Best effort: browsers alleen laten scripts een tabblad sluiten dat
    // zelf via script geopend is (start-app.bat opent via de OS, niet via
    // script) — dit werkt dus niet overal, vandaar ook de boodschap hierboven.
    setTimeout(() => window.close(), 400);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    els.shutdownMessage.textContent = err instanceof ApiError ? err.message : "Fout bij afsluiten.";
    els.shutdownMessage.className = "message error";
    els.shutdownMessage.classList.remove("hidden");
    els.shutdownBtn.disabled = false;
  }
});

// ---- Bootstrap --------------------------------------------------------

for (const select of document.querySelectorAll("#admin-view select")) {
  enhanceSelect(select);
}

els.reportDate.value = todayIso();

startHealthPolling(POLLING_INTERVAL_MS, (online) => {
  els.banner.classList.toggle("hidden", online);
});

(async function bootstrap() {
  const token = localStorage.getItem(ADMIN_TOKEN_KEY);
  if (!token) {
    showLogin();
    return;
  }
  try {
    const me = await api.me();
    showAdmin(me);
  } catch {
    showLogin();
  }
})();
