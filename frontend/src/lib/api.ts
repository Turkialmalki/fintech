/* Typed API client. Same-origin requests (Next.js rewrites /api/v1 to the FastAPI service). */

export class ApiError extends Error {
  status: number;
  code: string;
  messageAr: string;
  details: Record<string, unknown>;
  constructor(status: number, code: string, message: string, messageAr: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.messageAr = messageAr;
    this.details = details;
  }
}

const BASE = "/api/v1";
const ACCESS = "rip_access";
const REFRESH = "rip_refresh";

export const tokens = {
  get access() { return typeof window === "undefined" ? null : sessionStorage.getItem(ACCESS); },
  get refresh() { return typeof window === "undefined" ? null : sessionStorage.getItem(REFRESH); },
  set(access: string, refresh: string) { sessionStorage.setItem(ACCESS, access); sessionStorage.setItem(REFRESH, refresh); },
  clear() { sessionStorage.removeItem(ACCESS); sessionStorage.removeItem(REFRESH); },
};

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const rt = tokens.refresh;
  if (!rt) return false;
  refreshing ??= (async () => {
    try {
      const r = await fetch(`${BASE}/auth/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: rt }) });
      if (!r.ok) return false;
      const j = await r.json();
      tokens.set(j.access_token, j.refresh_token);
      return true;
    } catch { return false; } finally { setTimeout(() => { refreshing = null; }, 0); }
  })();
  return refreshing;
}

type Opts = { method?: string; body?: unknown; form?: FormData; query?: Record<string, unknown>; raw?: boolean; signal?: AbortSignal };

function qs(query?: Record<string, unknown>): string {
  if (!query) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, String(x)));
    else p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export async function api<T = unknown>(path: string, opts: Opts = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = {};
  if (tokens.access) headers.Authorization = `Bearer ${tokens.access}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}${qs(opts.query)}`, { method: opts.method ?? (body ? "POST" : "GET"), headers, body, signal: opts.signal });
  } catch {
    throw new ApiError(0, "NETWORK", "Couldn't reach the server", "تعذر الاتصال بالخادم");
  }
  if (res.status === 401 && !retried && path !== "/auth/login" && (await tryRefresh())) return api<T>(path, opts, true);
  if (res.status === 401 && path !== "/auth/login") {
    tokens.clear();
    if (typeof window !== "undefined" && !location.pathname.startsWith("/login")) location.href = `/login?next=${encodeURIComponent(location.pathname)}`;
  }
  if (!res.ok) {
    let e: { code?: string; message?: string; message_ar?: string; details?: Record<string, unknown> } = {};
    try { e = (await res.json()).error ?? {}; } catch { /* non-JSON error */ }
    throw new ApiError(res.status, e.code ?? "HTTP_ERROR", e.message ?? res.statusText, e.message_ar ?? e.message ?? res.statusText, e.details);
  }
  if (opts.raw) return (await res.blob()) as T;
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function openPdf(path: string) {
  const blob = await api<Blob>(path, { raw: true });
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function errorText(e: unknown, locale: "ar" | "en"): string {
  if (e instanceof ApiError) return locale === "ar" ? e.messageAr : e.message;
  return locale === "ar" ? "حدث خطأ غير متوقع" : "Something went wrong";
}
