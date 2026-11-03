/** Small fetch wrapper + device key + connection polling, shared by all screens. */

export const ADMIN_TOKEN_KEY = "toelating_admin_token";
const DEVICE_TOKEN_KEY = "toelating_device_token";

/** De geheime sleutel die dit toestel kreeg bij het koppelen (zie het
 * hostscherm), of null. In de Android-app bewaart de app zelf de sleutel
 * (window.ToelatingApp): wat een pagina in localStorage zet, hoort bij het
 * adres van de server en zou dus verdwijnen zodra het IP van de pc
 * verandert. In een gewone browser is localStorage wel de juiste plek. */
export function getDeviceToken() {
  if (window.ToelatingApp) return window.ToelatingApp.getDeviceToken() || null;
  return localStorage.getItem(DEVICE_TOKEN_KEY);
}

export function setDeviceToken(token) {
  if (window.ToelatingApp) window.ToelatingApp.setDeviceToken(token);
  else localStorage.setItem(DEVICE_TOKEN_KEY, token);
}

export function clearDeviceToken() {
  if (window.ToelatingApp) window.ToelatingApp.clearDeviceToken();
  else localStorage.removeItem(DEVICE_TOKEN_KEY);
}

const DEVICE_NAME_KEY = "toelating_device_name";

/** Leesbare naam van dit toestel, of null als die nooit ingesteld werd. */
export function getDeviceName() {
  return localStorage.getItem(DEVICE_NAME_KEY);
}

export function setDeviceName(name) {
  localStorage.setItem(DEVICE_NAME_KEY, name.trim().slice(0, 40));
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(method, path, body) {
  const headers = {};
  const token = localStorage.getItem(ADMIN_TOKEN_KEY);
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const deviceToken = getDeviceToken();
  if (deviceToken) headers["X-Device-Token"] = deviceToken;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const isJson = (response.headers.get("content-type") || "").includes("application/json");
  const data = isJson ? await response.json().catch(() => null) : null;

  if (!response.ok) {
    const message = (data && data.detail) || `Fout (${response.status})`;
    throw new ApiError(message, response.status);
  }
  return data;
}

/** Fetches a binary/text response (e.g. the CSV export) with the auth header,
 * since a plain <a href> download can't carry an Authorization header.
 */
async function requestBlob(path) {
  const token = localStorage.getItem(ADMIN_TOKEN_KEY);
  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(path, { headers });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError((data && data.detail) || `Fout (${response.status})`, response.status);
  }
  return response.blob();
}

function toQueryString(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  health: () => request("GET", "/api/health"),
  // Hostscherm: het toestel stuurt zijn sleutel mee (X-Device-Token), de
  // server leidt daar zelf uit af welk toestel het is.
  pair: (code, name) => request("POST", "/api/host/pair", { code, name }),
  currentDevice: () => request("GET", "/api/host/device"),
  scan: (wristbandId) => request("POST", "/api/host/scan", { wristband_id: wristbandId }),
  verdict: (verdict) => request("POST", "/api/host/verdict", { verdict }),
  practiceAck: () => request("POST", "/api/host/practice-ack"),
  cancelScan: () => request("POST", "/api/host/cancel"),
  setDeviceName: (name) => request("PUT", "/api/host/device-name", { name }),
  gateScan: (wristbandId) => request("POST", "/api/gate/scan", { wristband_id: wristbandId }),

  login: (pincode) => request("POST", "/api/auth/login", { pincode }),
  logout: () => request("POST", "/api/auth/logout"),
  me: () => request("GET", "/api/auth/me"),

  wristbandStatus: (wristbandId) => request("GET", `/api/admin/wristbands/${encodeURIComponent(wristbandId)}`),
  wristbandHistory: (wristbandId) =>
    request("GET", `/api/admin/wristbands/${encodeURIComponent(wristbandId)}/history`),
  setWristbandStatus: (wristbandId, status, reason) =>
    request("POST", `/api/admin/wristbands/${encodeURIComponent(wristbandId)}/status`, { status, reason }),

  logs: (params) => request("GET", `/api/admin/logs${toQueryString(params)}`),
  exportLogsCsv: (params) => requestBlob(`/api/admin/logs/export.csv${toQueryString(params)}`),

  report: (reportDate) => request("GET", `/api/admin/report${toQueryString({ report_date: reportDate })}`),

  groups: () => request("GET", "/api/admin/pincodes"),
  setGroupPincode: (role, pincode) => request("PUT", `/api/admin/pincodes/${role}`, { pincode }),
  disableGroup: (role) => request("DELETE", `/api/admin/pincodes/${role}`),

  networkInfo: () => request("GET", "/api/admin/network"),
  createPairingCode: () => request("POST", "/api/admin/pairing-codes"),
  pairedDevices: () => request("GET", "/api/admin/devices"),
  unpairDevice: (deviceId) => request("DELETE", `/api/admin/devices/${encodeURIComponent(deviceId)}`),
  shutdown: () => request("POST", "/api/admin/shutdown"),
};

/** Polls /api/health and calls onStatusChange(true|false) whenever connectivity flips.
 *
 * Herlaadt ook de pagina zodra de server een nieuwe versie van de
 * schermbestanden heeft (na een update): een scherm dat open blijft staan,
 * zoals in de Android-app, zou anders oude code blijven draaien tegen een
 * nieuwe server. */
export function startHealthPolling(intervalMs, onStatusChange) {
  let online = null;
  let loadedVersion = null;
  async function check() {
    try {
      const health = await api.health();
      if (loadedVersion === null) {
        loadedVersion = health.frontend_version;
      } else if (health.frontend_version !== loadedVersion) {
        location.reload();
        return;
      }
      if (online !== true) {
        online = true;
        onStatusChange(true);
      }
    } catch {
      if (online !== false) {
        online = false;
        onStatusChange(false);
      }
    }
  }
  check();
  return setInterval(check, intervalMs);
}
