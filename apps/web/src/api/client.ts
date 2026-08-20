/* API client + auth token storage */
export const API = import.meta.env.VITE_API_URL ?? (typeof window !== "undefined" ? window.location.origin : "http://localhost:9020");

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

function buildRequestInit(init?: RequestInit): RequestInit {
  const token = getAuthToken();
  const headers = new Headers(init?.headers);
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!headers.has("Content-Type") && !isFormData) {
    headers.set("Content-Type", "application/json");
  }
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return {
    ...init,
    headers,
  };
}

function formatErrorDetail(detail: unknown, fallback: string): Error {
  if (typeof detail === "string") return new Error(detail);
  if (detail && typeof detail === "object") {
    const payload = detail as Record<string, any>;
    const action = typeof payload.recommended_action === "string" ? payload.recommended_action : "Request failed.";
    const warnings = Array.isArray(payload.warnings) && payload.warnings.length > 0
      ? ` Warnings: ${payload.warnings.join("; ")}`
      : "";
    const dependents = Array.isArray(payload.dependents) && payload.dependents.length > 0
      ? ` Dependents: ${payload.dependents.join(", ")}`
      : "";
    const policyViolations = payload.policy && Array.isArray(payload.policy.violations) && payload.policy.violations.length > 0
      ? ` Policy: ${payload.policy.violations.join("; ")}`
      : "";
    const error = new Error(`${action}${warnings}${dependents}${policyViolations}`) as Error & { detail?: unknown };
    error.detail = detail;
    return error;
  }
  return new Error(fallback || "Request failed.");
}

/** Authenticated response primitive for callers that need a non-JSON body. */
export async function apiResponse(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${API}${path}`, buildRequestInit(init));
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }));
    throw formatErrorDetail(payload?.detail, response.statusText);
  }
  return response;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await apiResponse(path, init);
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

/** Authenticated request helper for file/archive downloads. */
export async function apiBlob(path: string, init?: RequestInit): Promise<Blob> {
  const response = await apiResponse(path, init);
  return response.blob();
}
