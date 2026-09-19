import { authMode, firebaseAuth } from "./firebase";

const BASE = (import.meta.env.VITE_API_URL || "") + "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

async function authHeaders(): Promise<Record<string, string>> {
  if (authMode === "dev") {
    const email = localStorage.getItem("dev_user") || "";
    return email ? { "X-Dev-User": email } : {};
  }
  const u = firebaseAuth()?.currentUser;
  if (!u) return {};
  return { Authorization: `Bearer ${await u.getIdToken()}` };
}

export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(await authHeaders()), ...((init.headers as any) || {}) };
  if (!(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const res = await fetch(BASE + path, { ...init, headers });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    const msg = typeof data?.detail === "string" ? data.detail : Array.isArray(data?.detail) ? data.detail.map((d: any) => d.msg).join(", ") : `Request failed (${res.status})`;
    throw new ApiError(res.status, msg);
  }
  return data as T;
}

export const post = <T = any>(path: string, body?: any) => api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const patch = <T = any>(path: string, body: any) => api<T>(path, { method: "PATCH", body: JSON.stringify(body) });
export const del = (path: string) => api(path, { method: "DELETE" });
export const upload = <T = any>(path: string, file: File) => { const fd = new FormData(); fd.append("file", file); return api<T>(path, { method: "POST", body: fd }); };

export async function fetchBlobUrl(path: string): Promise<string> {
  const res = await fetch(BASE + path, { headers: await authHeaders() });
  if (!res.ok) throw new ApiError(res.status, "Could not load file");
  return URL.createObjectURL(await res.blob());
}
