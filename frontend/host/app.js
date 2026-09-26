import { ApiError, api, getDeviceId, startHealthPolling } from "../shared/api.js";
import { KeyboardWedgeReader, SimulatedReader } from "../shared/reader.js";
import { playFailureSound, playNeutralSound, playSuccessSound } from "../shared/sound.js";

const POLLING_INTERVAL_MS = 3000;
const TEST_WRISTBANDS = ["TEST-001", "TEST-002", "TEST-003", "TEST-004"];
const CONFIRMATION_DISPLAY_MS = 3000;
const FINAL_RESULT_DISPLAY_MS = 30000;
const REJECTED_TOAST_MS = 2500;

const STATUS_INFO = {
  NOG_NIET_GESPRONGEN: { kleur: "groen", tekst: "1e poging" },
  HERKANSING: { kleur: "oranje", tekst: "2e poging – laatste kans" },
  GESLAAGD: { kleur: "groen", tekst: "Geslaagd – oefensprong" },
  NIET_GESLAAGD: { kleur: "rood", tekst: "Vandaag niet meer toegestaan" },
};

const FINAL_STATUSES = new Set(["GESLAAGD", "NIET_GESLAAGD"]);

const deviceId = getDeviceId();

const els = {
  banner: document.getElementById("connection-banner"),
  toast: document.getElementById("rejected-toast"),
  waitingView: document.getElementById("waiting-view"),
  resultView: document.getElementById("result-view"),
  wristbandId: document.getElementById("wristband-id"),
  statusBanner: document.getElementById("status-banner"),
  statusText: document.getElementById("status-text"),
  verdictActions: document.getElementById("verdict-actions"),
  cancelActions: document.getElementById("cancel-actions"),
  btnGroen: document.getElementById("btn-groen"),
  btnRood: document.getElementById("btn-rood"),
  btnCancel: document.getElementById("btn-cancel"),
  simPanel: document.getElementById("sim-panel"),
};

let countdownInterval = null;
let returnTimeout = null;

function clearTimers() {
  if (countdownInterval) clearInterval(countdownInterval);
  if (returnTimeout) clearTimeout(returnTimeout);
  countdownInterval = null;
  returnTimeout = null;
}

function showWaiting() {
  clearTimers();
  els.resultView.classList.add("hidden");
  els.waitingView.classList.remove("hidden");
}

function showRejectedToast(message) {
  playFailureSound();
  els.toast.textContent = message;
  els.toast.classList.remove("hidden");
  setTimeout(() => els.toast.classList.add("hidden"), REJECTED_TOAST_MS);
}

function applyStatusBanner(status, tekstOverride) {
  const info = STATUS_INFO[status];
  els.statusBanner.className = `status-banner status-${info.kleur}`;
  els.statusText.textContent = tekstOverride ?? info.tekst;
}

/** Stille veiligheidstimeout tijdens het beoordelen (testsprong/herkansing):
 * geen zichtbare balk — de sprong mag langer dan 30 seconden duren — maar
 * als de host echt geen oordeel geeft binnen scan_timeout_seconds, keert
 * het scherm alsnog terug naar "wacht op scan". */
function watchVerdictExpiry(expiresAtIso) {
  const expiresAt = new Date(expiresAtIso).getTime();
  clearTimers();
  countdownInterval = setInterval(() => {
    if (Date.now() >= expiresAt) showWaiting();
  }, 1000);
}

async function autoAcknowledgePractice() {
  try {
    await api.practiceAck(deviceId);
    playNeutralSound();
  } catch (err) {
    console.error(err);
  } finally {
    showWaiting();
  }
}

function renderScanResult(body) {
  els.wristbandId.textContent = body.wristband_id;
  applyStatusBanner(body.status);

  els.verdictActions.classList.toggle("hidden", !body.requires_verdict);
  els.cancelActions.classList.toggle("hidden", !body.requires_verdict);

  els.waitingView.classList.add("hidden");
  els.resultView.classList.remove("hidden");

  clearTimers();
  if (body.requires_verdict) {
    watchVerdictExpiry(body.expires_at);
  } else if (body.requires_practice_ack) {
    // GESLAAGD: bevoegd personeel hoeft niets te doen, dit sluit zichzelf af.
    returnTimeout = setTimeout(autoAcknowledgePractice, FINAL_RESULT_DISPLAY_MS);
  } else {
    // NIET_GESLAAGD: niets om af te ronden, gewoon tonen en dan terug.
    returnTimeout = setTimeout(showWaiting, FINAL_RESULT_DISPLAY_MS);
  }
}

async function handleScan(wristbandId) {
  try {
    const body = await api.scan(wristbandId, deviceId);
    renderScanResult(body);
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      showRejectedToast(err.message);
    } else {
      console.error(err);
      showRejectedToast("Er ging iets mis. Probeer opnieuw.");
    }
  }
}

async function handleVerdict(verdict) {
  clearTimers();
  try {
    const result = await api.verdict(deviceId, verdict);
    playSuccessSound();
    applyStatusBanner(result.status);
    els.verdictActions.classList.add("hidden");
    els.cancelActions.classList.add("hidden");
    const delay = FINAL_STATUSES.has(result.status) ? FINAL_RESULT_DISPLAY_MS : CONFIRMATION_DISPLAY_MS;
    returnTimeout = setTimeout(showWaiting, delay);
  } catch (err) {
    showRejectedToast(err instanceof ApiError ? err.message : "Er ging iets mis.");
    showWaiting();
  }
}

async function handleCancel() {
  // The visitor scanned but didn't actually jump (changed their mind, called
  // away, ...): discard the pending scan without any status change, instead
  // of waiting out the full time-out.
  clearTimers();
  try {
    await api.cancelScan(deviceId);
    playNeutralSound();
  } catch (err) {
    showRejectedToast(err instanceof ApiError ? err.message : "Er ging iets mis.");
  } finally {
    showWaiting();
  }
}

els.btnGroen.addEventListener("click", () => handleVerdict("GROEN"));
els.btnRood.addEventListener("click", () => handleVerdict("ROOD"));
els.btnCancel.addEventListener("click", handleCancel);

new KeyboardWedgeReader().start(handleScan);

const params = new URLSearchParams(location.search);
if (params.get("sim") === "1") {
  document.body.classList.add("sim-mode");
  new SimulatedReader(els.simPanel, TEST_WRISTBANDS).start(handleScan);
}

startHealthPolling(POLLING_INTERVAL_MS, (online) => {
  els.banner.classList.toggle("hidden", online);
});
