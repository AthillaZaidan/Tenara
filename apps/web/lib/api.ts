// Thin client for the Tenara API: unwraps the {data, error} envelope, carries the bearer token and
// turns every failure into an ApiError the UI can show.

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const BASE = `${API_URL}/api/v1`;
const TOKEN_KEY = "tenara.token";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public field?: string | null,
  ) {
    super(message);
  }
}

export const tokenStore = {
  get(): string | null {
    try {
      return window.localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string | null) {
    try {
      if (token) window.localStorage.setItem(TOKEN_KEY, token);
      else window.localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* private mode: the session simply will not persist */
    }
  },
};

type Options = {
  method?: string;
  body?: unknown;
  form?: FormData;
  token?: string | null;
  idempotencyKey?: string;
  signal?: AbortSignal;
};

export async function api<T = any>(path: string, opts: Options = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = opts.token === undefined && typeof window !== "undefined" ? tokenStore.get() : opts.token;
  if (token) headers.Authorization = `Bearer ${token}`;
  if (opts.idempotencyKey) headers["Idempotency-Key"] = opts.idempotencyKey;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: opts.method ?? (body ? "POST" : "GET"),
      headers,
      body,
      signal: opts.signal,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "network", "Server tidak dapat dihubungi. Coba lagi sebentar.");
  }
  let payload: any = null;
  try {
    payload = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok || payload?.error) {
    const err = payload?.error ?? {};
    throw new ApiError(res.status, err.code ?? "error", err.message ?? `Permintaan gagal (${res.status})`, err.field);
  }
  return payload?.data as T;
}

export const newKey = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

/** Public file URLs from the API are relative ("/api/v1/files/…"); make them absolute. */
export const fileUrl = (url?: string | null) => (!url ? "" : url.startsWith("http") ? url : `${API_URL}${url}`);

export const idr = (n: number | string | null | undefined) =>
  n == null ? "-" : `Rp${Math.round(Number(n)).toLocaleString("id-ID")}`;

export const when = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" }) : "-";
