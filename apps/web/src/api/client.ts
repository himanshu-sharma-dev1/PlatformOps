/* API client + auth token storage */
export const API = import.meta.env.VITE_API_URL ?? (typeof window !== "undefined" ? window.location.origin : "http://localhost:9002");

export const AUTH_TOKEN_KEY = "platformops.auth.token.v1";

export function getAuthToken(): string {
  try {
    return localStorage.getItem(AUTH_TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setAuthToken(token: string) {
  try {
    if (token) localStorage.setItem(AUTH_TOKEN_KEY, token);
    else localStorage.removeItem(AUTH_TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = payload?.detail;
    if (typeof detail === "string") {
      throw new Error(detail);
    }
    if (detail && typeof detail === "object") {
      const action = typeof detail.recommended_action === "string" ? detail.recommended_action : "Request failed.";
      const warnings = Array.isArray(detail.warnings) && detail.warnings.length > 0
        ? ` Warnings: ${detail.warnings.join("; ")}`
        : "";
      const dependents = Array.isArray(detail.dependents) && detail.dependents.length > 0
        ? ` Dependents: ${detail.dependents.join(", ")}`
        : "";
      const policyViolations = detail.policy && Array.isArray(detail.policy.violations) && detail.policy.violations.length > 0
        ? ` Policy: ${detail.policy.violations.join("; ")}`
        : "";
      const error = new Error(`${action}${warnings}${dependents}${policyViolations}`) as Error & { detail?: unknown };
      error.detail = detail;
      throw error;
    }
    throw new Error(response.statusText);
  }
  return response.json();
}
