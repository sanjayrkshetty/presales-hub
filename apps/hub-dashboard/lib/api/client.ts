import { ApiError } from "../errors";

const BASE = process.env.NEXT_PUBLIC_HUB_API_URL ?? "http://localhost:8003";

type FetchOptions = RequestInit & { params?: Record<string, string | number | boolean | undefined> };

// Module-level token provider — set once during app init so apiFetch can inject auth
// without every call site needing to pass the token explicitly.
let _getToken: (() => string | null) | null = null;

export function initApiAuth(tokenGetter: () => string | null): void {
  _getToken = tokenGetter;
}

export async function apiFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const { params, ...rest } = opts;
  let url = `${BASE}${path}`;
  if (params) {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) q.set(k, String(v));
    }
    const qs = q.toString();
    if (qs) url += `?${qs}`;
  }

  // Inject auth token if available and not already set by caller
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(rest.headers as Record<string, string>),
  };
  const callerSetAuth = "authorization" in headers || "Authorization" in headers;
  if (!callerSetAuth && _getToken) {
    const token = _getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...rest, headers });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new ApiError(res.status, body || res.statusText, path);
  }
  return res.json() as unknown as T;
}

export function wsUrl(path: string): string {
  const base = (process.env.NEXT_PUBLIC_HUB_API_URL ?? "http://localhost:8003")
    .replace(/^http/, "ws");
  return `${base}${path}`;
}
