/**
 * Pocket API client — v0.3.1 (functional surface).
 *
 * Talks to the Python ``clarity-engine`` Cloud Run backend over HTTP
 * (no proxy, no Node mediation). The backend URL is injected at
 * build time via ``VITE_CLARITY_ENGINE_URL``; ``getBackendUrl()``
 * falls back to the live URL so local dev works without an
 * ``.env.local`` file.
 *
 * Session model:
 *   * ``POST /login`` returns ``{ session_id, expires_in, user, ok }``
 *   * The session id is stored in localStorage under
 *     ``clarityos_pocket_session``
 *   * Every subsequent request adds ``X-Session-ID: <id>``
 *   * A 401 from the backend clears the session AND throws
 *     ``AuthRequiredError`` so screens can route to /login
 *
 * Endpoint surface (backend-aligned to what actually exists today):
 *   * ``login(u, p)``        → POST /login          (no session header)
 *   * ``logout()``           → local clear only (no /logout endpoint)
 *   * ``health()``           → GET  /health         (public)
 *   * ``me()``               → GET  /me             (session required)
 *   * ``clarify(text)``      → POST /markov         (session required)
 *                              The card's ``/clarify`` does not exist on
 *                              the backend; ``/markov`` is the closest
 *                              semantic match (text in, LLM out).
 *   * ``runs()``             → GET  /elins/regression/runs
 *                              (session required; no bare ``/runs``)
 *   * ``run(id)``            → GET  /elins/regression/run/{id}
 *                              (session required)
 *
 * Status/stream/upload stubs from v0.3.0 stay as throw-stubs until
 * their backend contracts are defined.
 */

const LIVE_BACKEND_FALLBACK =
  "https://clarity-engine-736968277491.us-central1.run.app";

const SESSION_KEY = "clarityos_pocket_session";

// ---------------------------------------------------------------------------
// Config + session helpers
// ---------------------------------------------------------------------------

/** Resolve the backend URL the client will hit.
 *  ``VITE_CLARITY_ENGINE_URL`` wins if set (build-time inlined by Vite);
 *  otherwise we fall back to the known live URL so local dev works
 *  without an env file. The fallback is documented intentionally —
 *  see ``LIVE_BACKEND_FALLBACK`` above. */
export function getBackendUrl(): string {
  const raw =
    (import.meta.env.VITE_CLARITY_ENGINE_URL as string | undefined) ?? "";
  const trimmed = raw.trim();
  return trimmed || LIVE_BACKEND_FALLBACK;
}

/** True when the env var was explicitly supplied at build. Useful for
 *  the Runtime view to show "(env default)" vs the actual URL. */
export function isBackendUrlFromEnv(): boolean {
  const raw =
    (import.meta.env.VITE_CLARITY_ENGINE_URL as string | undefined) ?? "";
  return raw.trim().length > 0;
}

export function getSession(): string | null {
  try {
    return localStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

export function setSession(id: string): void {
  try {
    localStorage.setItem(SESSION_KEY, id);
  } catch {
    /* localStorage disabled — session stays in-memory only this tab */
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore */
  }
}

export function isAuthenticated(): boolean {
  return getSession() !== null;
}

// ---------------------------------------------------------------------------
// Error shapes
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number;
  readonly code: string | null;

  constructor(message: string, status: number, code: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** Thrown specifically on 401. Distinct subclass so screens can do
 *  ``if (e instanceof AuthRequiredError) redirect("/login")`` without
 *  string-matching status codes. */
export class AuthRequiredError extends ApiError {
  constructor() {
    super("Not signed in", 401, "auth_required");
    this.name = "AuthRequiredError";
  }
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

interface ApiFetchInit extends RequestInit {
  /** Skip the X-Session-ID header even if a session exists. Used by
   *  ``login()`` so a stale session never poisons the credentials
   *  POST. */
  skipSession?: boolean;
}

async function apiFetch<T>(
  path: string,
  init: ApiFetchInit = {},
): Promise<T> {
  const base = getBackendUrl();
  const url = `${base}${path}`;
  const { skipSession, ...rest } = init;
  const session = skipSession ? null : getSession();

  const wantsBody = rest.method === "POST" || rest.method === "PUT";
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(wantsBody ? { "Content-Type": "application/json" } : {}),
    ...(session ? { "X-Session-ID": session } : {}),
    ...((rest.headers as Record<string, string> | undefined) ?? {}),
  };

  let resp: Response;
  try {
    resp = await fetch(url, { ...rest, headers });
  } catch (e) {
    throw new ApiError((e as Error).message || "Network error", 0, "network");
  }

  if (resp.status === 401) {
    clearSession();
    throw new AuthRequiredError();
  }

  if (!resp.ok) {
    const bodyText = await resp.text().catch(() => "");
    let message = bodyText || `HTTP ${resp.status}`;
    let code: string | null = null;
    try {
      const j = JSON.parse(bodyText) as {
        detail?: { error?: string; message?: string } | string;
      };
      if (typeof j.detail === "object" && j.detail !== null) {
        code = j.detail.error ?? null;
        if (j.detail.message) message = j.detail.message;
      } else if (typeof j.detail === "string") {
        message = j.detail;
      }
    } catch {
      /* not JSON — keep raw body */
    }
    throw new ApiError(message, resp.status, code);
  }

  // 204 No Content path — return undefined as T (callers know).
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

export interface LoginResponse {
  ok: boolean;
  session_id: string;
  expires_in: number;
  user: string;
}

export interface HealthResponse {
  ok: boolean;
  status: string;
  version: string;
}

export interface MeResponse {
  ok: boolean;
  user: string;
  session_id: string;
  cohort: string | null;
  operator_id: string | null;
  tier: string;
  billing_expires_at: number | null;
  features: Record<string, boolean>;
}

export interface MarkovResponse {
  ok: boolean;
  surface: string;
  payload: unknown;
}

export interface RegressionRunRecord {
  run_id: string;
  created_at: string | null;
  source: string | null;
  evidence_dir: string | null;
  engine_version: string | null;
}

// ---------------------------------------------------------------------------
// Endpoint implementations
// ---------------------------------------------------------------------------

export async function login(
  username: string,
  password: string,
): Promise<LoginResponse> {
  // Don't carry a stale session into the credentials POST.
  clearSession();
  const data = await apiFetch<LoginResponse>("/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
    skipSession: true,
  });
  if (data?.session_id) setSession(data.session_id);
  return data;
}

export function logout(): void {
  // No backend endpoint to call; just drop the local session.
  clearSession();
}

export async function health(): Promise<HealthResponse> {
  // /health is public — works without a session.
  return apiFetch<HealthResponse>("/health", { skipSession: true });
}

export async function me(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/me");
}

/** Clarify (powered by /markov until a dedicated endpoint lands). */
export async function clarify(text: string): Promise<MarkovResponse> {
  return apiFetch<MarkovResponse>("/markov", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export async function runs(): Promise<RegressionRunRecord[]> {
  return apiFetch<RegressionRunRecord[]>("/elins/regression/runs");
}

export async function run(id: string): Promise<unknown> {
  return apiFetch<unknown>(
    `/elins/regression/run/${encodeURIComponent(id)}`,
  );
}

// ---------------------------------------------------------------------------
// Stubs kept from v0.3.0 — not yet contracted on the backend.
// ---------------------------------------------------------------------------

export async function status(): Promise<unknown> {
  throw new Error("Pocket api.status() not implemented yet");
}

export async function stream(_payload: unknown): Promise<unknown> {
  throw new Error("Pocket api.stream() not implemented yet");
}

export async function upload(_file: unknown): Promise<unknown> {
  throw new Error("Pocket api.upload() not implemented yet");
}
