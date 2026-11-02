/* Fetch wrapper for the Application API: JSON in and out, cookie session, errors as ApiError. */

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function messageFrom(data) {
  if (!data) return null;
  if (typeof data.message === "string") return data.message;
  if (Array.isArray(data.detail)) {
    return data.detail.map((item) => `${(item.loc || []).slice(1).join(".")}: ${item.msg}`).join("; ");
  }
  return null;
}

export async function api(path, { method = "GET", body } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach the Agentra server");
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && !location.pathname.endsWith("/login.html")) {
      location.assign(`login.html?next=${encodeURIComponent(location.pathname + location.search)}`);
    }
    throw new ApiError(response.status, data?.error ?? "error", messageFrom(data) ?? `Request failed (${response.status})`);
  }
  return data;
}
