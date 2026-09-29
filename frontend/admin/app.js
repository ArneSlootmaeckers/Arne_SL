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
  UITLOGGEN: "Uitloggen",
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
    medewerkers: document.getElementById("tab-medewerkers"),
    systeem: document.getElementById("tab-systeem"),
  },

  wristbandLookupForm: document.getElementById("wristband-lookup-form"),
  wristbandInput: document.getElementById("wristband-input"),
  wristbandResult: document.getElementById("wristband-result"),
  wristbandResultId: document.getElementById("wristband-result-id"),
  wristbandStatusBadge: document.getElementById("wristband-status-badge"),
  overrideForm: document.getElementById("override-form"),
  overrideStatus: document.getElementById("override-status"),
  overrideReason: document.getElementById("override-reason"),
  overrideMessage: document.getElementById("override-message"),
  wristbandHistoryBody: document.querySelector("#wristband-history-table tbody"),

  logsFilterForm: document.getElementById("logs-filter-form"),
  logsFilterDate: document.getElementById("logs-filter-date"),
  logsFilterWristband: document.getElementById("logs-filter-wristband"),
  logsFilterEmployee: document.getElementById("logs-filter-employee"),
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

  createEmployeeForm: document.getElementById("create-employee-form"),
  newEmployeeName: document.getElementById("new-employee-name"),
  newEmployeePincode: document.getElementById("new-employee-pincode"),
  newEmployeeRole: document.getElementById("new-employee-role"),
  createEmployeeMessage: document.getElementById("create-employee-message"),
  employeesTableBody: document.querySelector("#employees-table tbody"),

  networkAddresses: document.getElementById("network-addresses"),
  networkNote: document.getElementById("network-note"),
  networkRefreshBtn: document.getElementById("network-refresh-btn"),

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
  els.userLabel.textContent = "";
  els.userLabel.append(document.createTextNode(`${employee.name} `));
  const roleSpan = document.createElement("span");
  roleSpan.className = "user-role";
  roleSpan.textContent = `(${employee.role})`;
  els.userLabel.append(roleSpan);

  for (const tab of ["medewerkers", "systeem"]) {
    const btn = els.tabButtons.find((b) => b.dataset.tab === tab);
    btn.classList.toggle("hidden", employee.role !== "admin");
  }
  if (employee.role !== "admin" && (activeTab === "medewerkers" || activeTab === "systeem")) {
    switchTab("bandje");
  }

  lastActivityAt = Date.now();
}

els.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const result = await api.login(els.pincodeInput.value);
    localStorage.setItem(ADMIN_TOKEN_KEY, result.token);
    showAdmin({ id: result.employee_id, name: result.name, role: result.role });
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
  const events = await api.logs({ wristband_id: wristbandId, event_date: todayIso(), limit: 100 });
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
    employee_id: els.logsFilterEmployee.value || undefined,
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
          event.employee_id ?? "",
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

// ---- Medewerkers tab ------------------------------------------------------

async function loadEmployees() {
  try {
    const employees = await api.employees();
    els.employeesTableBody.innerHTML = "";
    for (const employee of employees) {
      const row = tableRow([employee.name, humanize(employee.role), employee.active ? "Ja" : "Nee"]);
      const actions = document.createElement("td");
      const toggleBtn = document.createElement("button");
      toggleBtn.type = "button";
      toggleBtn.className = "btn-secondary";
      toggleBtn.dataset.action = "toggle";
      toggleBtn.dataset.id = employee.id;
      toggleBtn.dataset.active = employee.active;
      toggleBtn.textContent = employee.active ? "Intrekken" : "Heractiveren";
      const pincodeBtn = document.createElement("button");
      pincodeBtn.type = "button";
      pincodeBtn.className = "btn-secondary";
      pincodeBtn.dataset.action = "pincode";
      pincodeBtn.dataset.id = employee.id;
      pincodeBtn.textContent = "Nieuwe pincode";
      actions.append(toggleBtn, " ", pincodeBtn);
      row.append(actions);
      els.employeesTableBody.append(row);
    }
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    if (err instanceof ApiError && err.status === 403) return; // not admin, tab hidden anyway
    console.error(err);
  }
}

els.employeesTableBody.addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-action]");
  if (!btn) return;
  const id = Number(btn.dataset.id);

  if (btn.dataset.action === "toggle") {
    const active = btn.dataset.active === "true";
    try {
      await api.updateEmployee(id, { active: !active });
      await loadEmployees();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
      alert(err instanceof ApiError ? err.message : "Fout bij aanpassen.");
    }
  }

  if (btn.dataset.action === "pincode") {
    const newPincode = prompt("Nieuwe pincode voor deze medewerker:");
    if (!newPincode) return;
    try {
      await api.updateEmployee(id, { new_pincode: newPincode });
      alert("Pincode aangepast.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
      alert(err instanceof ApiError ? err.message : "Fout bij aanpassen.");
    }
  }
});

els.createEmployeeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api.createEmployee(
      els.newEmployeeName.value.trim(),
      els.newEmployeePincode.value.trim(),
      els.newEmployeeRole.value
    );
    els.createEmployeeMessage.textContent = "Medewerker aangemaakt.";
    els.createEmployeeMessage.className = "message success";
    els.createEmployeeMessage.classList.remove("hidden");
    els.createEmployeeForm.reset();
    await loadEmployees();
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) return handleUnauthorized();
    els.createEmployeeMessage.textContent = err instanceof ApiError ? err.message : "Fout bij aanmaken.";
    els.createEmployeeMessage.className = "message error";
    els.createEmployeeMessage.classList.remove("hidden");
  }
});

// Load the employee list the first time the tab is opened.
document.querySelector('.tab-btn[data-tab="medewerkers"]').addEventListener("click", loadEmployees, { once: false });

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

document.querySelector('.tab-btn[data-tab="systeem"]').addEventListener("click", loadNetworkInfo);
els.networkRefreshBtn.addEventListener("click", loadNetworkInfo);

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
