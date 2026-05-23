const BASE = process.env.NEXT_PUBLIC_HUB_API_URL ?? "http://localhost:8003";

type FetchOptions = RequestInit & { params?: Record<string, string | number | boolean | undefined> };

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
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...rest.headers },
    ...rest,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export function wsUrl(path: string): string {
  const base = (process.env.NEXT_PUBLIC_HUB_API_URL ?? "http://localhost:8003")
    .replace(/^http/, "ws");
  return `${base}${path}`;
}
