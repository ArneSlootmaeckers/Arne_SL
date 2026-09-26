/** Small fetch wrapper + device id + connection polling, shared by all screens. */

const DEVICE_ID_KEY = "toelating_device_id";

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
  const token = localStorage.getItem("toelating_admin_token");
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

export const api = {
  health: () => request("GET", "/api/health"),
  scan: (wristbandId, deviceId) =>
    request("POST", "/api/host/scan", { wristband_id: wristbandId, device_id: deviceId }),
  verdict: (deviceId, verdict) => request("POST", "/api/host/verdict", { device_id: deviceId, verdict }),
  practiceAck: (deviceId) => request("POST", "/api/host/practice-ack", { device_id: deviceId }),
  gateScan: (wristbandId, deviceId) =>
    request("POST", "/api/gate/scan", { wristband_id: wristbandId, device_id: deviceId }),
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
