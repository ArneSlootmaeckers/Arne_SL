import { ApiError, api, getDeviceId, startHealthPolling } from "../shared/api.js";
import { KeyboardWedgeReader, SimulatedReader } from "../shared/reader.js";
import { playFailureSound, playSuccessSound } from "../shared/sound.js";

const POLLING_INTERVAL_MS = 3000;
const RESULT_DISPLAY_MS = 3000;
const TEST_WRISTBANDS = ["TEST-001", "TEST-002", "TEST-003", "TEST-004"];

const deviceId = getDeviceId();

const els = {
  banner: document.getElementById("connection-banner"),
  waitingView: document.getElementById("waiting-view"),
  resultView: document.getElementById("result-view"),
  wristbandId: document.getElementById("wristband-id"),
  statusBanner: document.getElementById("status-banner"),
  statusText: document.getElementById("status-text"),
  statusReason: document.getElementById("status-reason"),
  simPanel: document.getElementById("sim-panel"),
};

let returnTimeout = null;
let busy = false;

function showWaiting() {
  if (returnTimeout) clearTimeout(returnTimeout);
  returnTimeout = null;
  els.resultView.classList.add("hidden");
  els.waitingView.classList.remove("hidden");
}

function renderResult(body) {
  els.wristbandId.textContent = body.wristband_id;
  if (body.allowed) {
    els.statusBanner.className = "status-banner status-groen";
    els.statusText.textContent = "Doorgaan";
    els.statusReason.textContent = "";
    playSuccessSound();
  } else {
    els.statusBanner.className = "status-banner status-rood";
    els.statusText.textContent = "Niet toegestaan";
    els.statusReason.textContent = body.reason || "";
    playFailureSound();
  }

  els.waitingView.classList.add("hidden");
  els.resultView.classList.remove("hidden");

  if (returnTimeout) clearTimeout(returnTimeout);
  returnTimeout = setTimeout(showWaiting, RESULT_DISPLAY_MS);
}

async function handleScan(wristbandId) {
  // Gate checks are one-shot (no server-side pending state), but ignore a
  // rapid-fire second scan client-side while the previous result is showing.
  if (busy) return;
  busy = true;
  try {
    const body = await api.gateScan(wristbandId, deviceId);
    renderResult(body);
  } catch (err) {
    console.error(err);
    playFailureSound();
  } finally {
    busy = false;
  }
}

new KeyboardWedgeReader().start(handleScan);

const params = new URLSearchParams(location.search);
if (params.get("sim") === "1") {
  document.body.classList.add("sim-mode");
  new SimulatedReader(els.simPanel, TEST_WRISTBANDS).start(handleScan);
}

startHealthPolling(POLLING_INTERVAL_MS, (online) => {
  els.banner.classList.toggle("hidden", online);
});
