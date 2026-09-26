/** Small fetch wrapper + device id + connection polling, shared by all screens. */

const DEVICE_ID_KEY = "toelating_device_id";
export const ADMIN_TOKEN_KEY = "toelating_admin_token";

export function getDeviceId() {
  let id = localStorage.getItem(DEVICE_ID_KEY);
  if (!id) {
    id = "toestel-" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem(DEVICE_ID_KEY, id);
  }
  return id;
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
  scan: (wristbandId, deviceId) =>
    request("POST", "/api/host/scan", { wristband_id: wristbandId, device_id: deviceId }),
  verdict: (deviceId, verdict) => request("POST", "/api/host/verdict", { device_id: deviceId, verdict }),
  practiceAck: (deviceId) => request("POST", "/api/host/practice-ack", { device_id: deviceId }),
  cancelScan: (deviceId) => request("POST", "/api/host/cancel", { device_id: deviceId }),
  gateScan: (wristbandId, deviceId) =>
    request("POST", "/api/gate/scan", { wristband_id: wristbandId, device_id: deviceId }),

  login: (pincode) => request("POST", "/api/auth/login", { pincode }),
  logout: () => request("POST", "/api/auth/logout"),
  me: () => request("GET", "/api/auth/me"),

  wristbandStatus: (wristbandId) => request("GET", `/api/admin/wristbands/${encodeURIComponent(wristbandId)}`),
  setWristbandStatus: (wristbandId, status, reason) =>
    request("POST", `/api/admin/wristbands/${encodeURIComponent(wristbandId)}/status`, { status, reason }),

  logs: (params) => request("GET", `/api/admin/logs${toQueryString(params)}`),
  exportLogsCsv: (params) => requestBlob(`/api/admin/logs/export.csv${toQueryString(params)}`),

  report: (reportDate) => request("GET", `/api/admin/report${toQueryString({ report_date: reportDate })}`),

  employees: () => request("GET", "/api/admin/employees"),
  createEmployee: (name, pincode, role) => request("POST", "/api/admin/employees", { name, pincode, role }),
  updateEmployee: (id, fields) => request("PATCH", `/api/admin/employees/${id}`, fields),

  shutdown: () => request("POST", "/api/admin/shutdown"),
};

/** Polls /api/health and calls onStatusChange(true|false) whenever connectivity flips. */
export function startHealthPolling(intervalMs, onStatusChange) {
  let online = null;
  async function check() {
    try {
      await api.health();
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
