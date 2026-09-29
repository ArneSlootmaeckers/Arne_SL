import { ApiError, api, getDeviceId, getDeviceName, setDeviceName, startHealthPolling } from "../shared/api.js";
import { KeyboardWedgeReader, NativeBridgeReader, SimulatedReader } from "../shared/reader.js";
import { playFailureSound, playNeutralSound, playSuccessSound } from "../shared/sound.js";

const POLLING_INTERVAL_MS = 3000;
const TEST_WRISTBANDS = ["TEST-001", "TEST-002", "TEST-003", "TEST-004"];
const CONFIRMATION_DISPLAY_MS = 3000;
const FINAL_RESULT_DISPLAY_MS = 5000;
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
  finalResultBarTrack: document.getElementById("final-result-bar-track"),
  finalResultBar: document.getElementById("final-result-bar"),
  cancelActions: document.getElementById("cancel-actions"),
  btnGroen: document.getElementById("btn-groen"),
  btnRood: document.getElementById("btn-rood"),
  btnCancel: document.getElementById("btn-cancel"),
  simPanel: document.getElementById("sim-panel"),
};

let countdownInterval = null;
let returnTimeout = null;
// Bij NIET_GESLAAGD staat er geen openstaande scan meer om te annuleren
// (die is al opgelost) — de knop keert dan gewoon meteen terug naar
// "wacht op scan" zonder de server aan te spreken.
let hasPendingScanToCancel = false;

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

/** Zichtbare, leeglopende balk voor de eindresultaten GESLAAGD/NIET_GESLAAGD:
 * na `durationMs` roept dit `onExpire` op (auto-bevestiging of gewoon terug
 * naar "wacht op scan"). */
function startFinalResultCountdown(durationMs, onExpire) {
  clearTimers();
  els.finalResultBarTrack.classList.remove("hidden");
  const expiresAt = Date.now() + durationMs;

  function tick() {
    const remainingMs = expiresAt - Date.now();
    if (remainingMs <= 0) {
      clearInterval(countdownInterval);
      countdownInterval = null;
      els.finalResultBar.style.width = "0%";
      onExpire();
      return;
    }
    els.finalResultBar.style.width = `${Math.max(0, (remainingMs / durationMs) * 100)}%`;
  }
  els.finalResultBar.style.width = "100%";
  countdownInterval = setInterval(tick, 100);
}

function renderScanResult(body) {
  els.wristbandId.textContent = body.wristband_id;
  applyStatusBanner(body.status);

  hasPendingScanToCancel = body.requires_verdict || body.requires_practice_ack;
  els.verdictActions.classList.toggle("hidden", !body.requires_verdict);
  els.cancelActions.classList.remove("hidden");
  els.finalResultBarTrack.classList.toggle("hidden", body.requires_verdict);

  els.waitingView.classList.add("hidden");
  els.resultView.classList.remove("hidden");

  if (body.requires_verdict) {
    watchVerdictExpiry(body.expires_at);
  } else if (body.requires_practice_ack) {
    // GESLAAGD: bevoegd personeel hoeft niets te doen, dit sluit zichzelf af.
    startFinalResultCountdown(FINAL_RESULT_DISPLAY_MS, autoAcknowledgePractice);
  } else {
    // NIET_GESLAAGD: niets om af te ronden, gewoon tonen en dan terug.
    startFinalResultCountdown(FINAL_RESULT_DISPLAY_MS, showWaiting);
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
    hasPendingScanToCancel = false;
    if (FINAL_STATUSES.has(result.status)) {
      // Geen openstaande scan meer (die is net opgelost): annuleren betekent
      // hier gewoon meteen terug naar "wacht op scan".
      els.cancelActions.classList.toggle("hidden", result.status !== "NIET_GESLAAGD");
      startFinalResultCountdown(FINAL_RESULT_DISPLAY_MS, showWaiting);
    } else {
      // HERKANSING: geen eindresultaat, gewoon kort bevestigen en verder.
      els.cancelActions.classList.add("hidden");
      els.finalResultBarTrack.classList.add("hidden");
      returnTimeout = setTimeout(showWaiting, CONFIRMATION_DISPLAY_MS);
    }
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
  if (!hasPendingScanToCancel) {
    // NIET_GESLAAGD heeft geen openstaande scan (die is al opgelost) — hier
    // is deze knop gewoon een snelle terugkeer naar "wacht op scan".
    playNeutralSound();
    showWaiting();
    return;
  }
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
new NativeBridgeReader().start(handleScan);

const params = new URLSearchParams(location.search);
if (params.get("sim") === "1") {
  document.body.classList.add("sim-mode");
  new SimulatedReader(els.simPanel, TEST_WRISTBANDS).start(handleScan);
}

// De Android-app geeft de naam van dit toestel mee in het adres
// (?toestel=Host%201). Onthouden, want via "Profiel" → "← Host" komt de
// pagina ook zonder die parameter terug.
if (params.has("toestel")) setDeviceName(params.get("toestel"));

startHealthPolling(POLLING_INTERVAL_MS, (online) => {
  els.banner.classList.toggle("hidden", online);
  // Bij elke (her)verbinding opnieuw doorgeven: zo kent de server de naam
  // ook als hij onbereikbaar was toen de naam ingesteld werd.
  if (online && getDeviceName() !== null) {
    api.setDeviceName(deviceId, getDeviceName()).catch(() => {});
  }
});
