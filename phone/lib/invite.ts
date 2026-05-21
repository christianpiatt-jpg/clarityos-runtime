// Invite + billing API client. Mirrors lib/api.ts patterns: fetch wrapper,
// envelope-aware error handling. None of these endpoints require an
// existing session — they're how a new user *gets* a session.

import { getApiBase, ApiError } from "./api";

export type Cohort = "founder_exception" | "terrace_1" | "founder";
export type Plan = "onetime" | "recurring";

export interface InviteMeta {
  cohort: Cohort;
  price: number;
  billing_required: boolean;
  expires_at: number;
}

interface RedeemResponse {
  ok: true;
  session_id: string;
  expires_in: number;
  user: string;
  cohort: Cohort;
  operator_id: string;
  plan?: Plan;
  billing_expires_at?: number;
}

async function request<T = any>(path: string, init?: RequestInit): Promise<T> {
  const base = await getApiBase();
  let res: Response;
  try {
    res = await fetch(base + path, {
      method: init?.method ?? "GET",
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      body: init?.body,
    });
  } catch (e: any) {
    throw new ApiError("network_error", e?.message || "Network unreachable", 0);
  }
  let data: any = null;
  try { data = await res.json(); } catch { /* empty / non-JSON */ }
  if (!res.ok || (data && data.ok === false)) {
    const code = (data && data.error) || "http_error";
    const msg = (data && data.message) || `HTTP ${res.status}`;
    throw new ApiError(code, msg, res.status, data);
  }
  return data as T;
}

export async function getInvite(token: string): Promise<InviteMeta> {
  const r = await request<{ data: InviteMeta }>(`/invite/${encodeURIComponent(token)}`);
  return r.data;
}

export function redeemFree(
  token: string,
  username: string,
  password: string
): Promise<RedeemResponse> {
  return request<RedeemResponse>(`/invite/${encodeURIComponent(token)}/redeem`, {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function startCheckout(
  token: string,
  username: string,
  password: string,
  plan: Plan
): Promise<{ ok: true; checkout_url: string; plan: Plan }> {
  return request(`/invite/${encodeURIComponent(token)}/checkout`, {
    method: "POST",
    body: JSON.stringify({ username, password, plan }),
  });
}

export function finalizeCheckout(
  token: string,
  stripeSessionId: string,
  username: string,
  password: string
): Promise<RedeemResponse> {
  return request<RedeemResponse>(`/invite/${encodeURIComponent(token)}/finalize`, {
    method: "POST",
    body: JSON.stringify({ session_id: stripeSessionId, username, password }),
  });
}
