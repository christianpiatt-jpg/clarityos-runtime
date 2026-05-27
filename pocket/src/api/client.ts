/**
 * Pocket API client — v0.3.4 (session persistence + expiry hygiene).
 *
 * Talks to the Python ``clarity-engine`` Cloud Run backend over HTTP
 * (no proxy, no Node mediation). The backend URL is injected at
 * build time via ``VITE_CLARITY_ENGINE_URL``; ``getBackendUrl()``
 * falls back to the live URL so local dev works without an
 * ``.env.local`` file.
 *
 * Session model (v0.3.4):
 *   * ``POST /login`` returns ``{ session_id, expires_in, user, ok }``
 *   * The session id is stored in localStorage under
 *     ``clarityos_pocket_session``
 *   * A second key, ``clarityos_pocket_session_meta``, holds
 *     ``{ created_at, expires_at, user }`` so the surface can
 *     display session age and refuse to send expired sessions
 *   * Every request adds ``X-Session-ID: <id>``
 *
 * Auth hygiene:
 *   * Pre-flight: if the session is past ``expires_at``, clear it
 *     and hard-navigate to ``/login?from=<current_path>``. No
 *     backend round-trip needed.
 *   * 401 from the backend: same — clear + hard-navigate. Also
 *     throws ``AuthRequiredError`` as a backstop for code paths
 *     that catch synchronously (e.g. the login screen itself).
 *   * Infinite-loop guard: ``redirectToLogin`` no-ops when the
 *     user is already on ``/login``.
 *   * 401 is NEVER retried. Network errors retry ONCE after 300ms
 *     and ONLY for ``GET`` (POSTs may have executed server-side;
 *     re-issuing risks double-mutation).
 *
 * No backend ``/refresh`` endpoint exists, so silent reauth is
 * intentionally NOT implemented. Expired sessions route to /login.
 *
 * Endpoint surface (backend-aligned to what actually exists today):
 *   * ``login(u, p)``     → POST /login          (no session header)
 *   * ``logout()``        → local clear only (no /logout endpoint)
 *   * ``health()``        → GET  /health         (public)
 *   * ``me()``            → GET  /me             (session required)
 *   * ``clarify(text)``   → POST /markov         (session required)
 *   * ``runs()``          → GET  /elins/regression/runs
 *   * ``run(id)``         → GET  /elins/regression/run/{id}
 */

const LIVE_BACKEND_FALLBACK =
  "https://clarity-engine-736968277491.us-central1.run.app";

const SESSION_KEY = "clarityos_pocket_session";
const SESSION_META_KEY = "clarityos_pocket_session_meta";

const NETWORK_RETRY_DELAY_MS = 300;

// ---------------------------------------------------------------------------
// Config helpers
// ---------------------------------------------------------------------------

export function getBackendUrl(): string {
  const raw =
    (import.meta.env.VITE_CLARITY_ENGINE_URL as string | undefined) ?? "";
  const trimmed = raw.trim();
  return trimmed || LIVE_BACKEND_FALLBACK;
}

export function isBackendUrlFromEnv(): boolean {
  const raw =
    (import.meta.env.VITE_CLARITY_ENGINE_URL as string | undefined) ?? "";
  return raw.trim().length > 0;
}

// ---------------------------------------------------------------------------
// Session helpers
// ---------------------------------------------------------------------------

export interface SessionMeta {
  /** Epoch ms when ``login()`` set this session locally. */
  created_at: number;
  /** Epoch ms when the backend says this session expires.
   *  Derived from the login response: ``created_at + expires_in * 1000``. */
  expires_at: number;
  /** Username that owns the session. */
  user: string;
}

export function getSession(): string | null {
  try {
    return localStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

export function getSessionMeta(): SessionMeta | null {
  try {
    const raw = localStorage.getItem(SESSION_META_KEY);
    if (!raw) return null;
    const j = JSON.parse(raw) as Partial<SessionMeta>;
    if (
      typeof j.created_at !== "number" ||
      typeof j.expires_at !== "number" ||
      typeof j.user !== "string"
    ) {
      return null;
    }
    return { created_at: j.created_at, expires_at: j.expires_at, user: j.user };
  } catch {
    return null;
  }
}

/** Writes both the session id and the metadata together. */
export function setSession(id: string, meta: SessionMeta): void {
  try {
    localStorage.setItem(SESSION_KEY, id);
    localStorage.setItem(SESSION_META_KEY, JSON.stringify(meta));
  } catch {
    /* localStorage disabled — session stays in-memory only this tab */
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(SESSION_META_KEY);
  } catch {
    /* ignore */
  }
}

/** True when the session id is present AND not past its expiry. */
export function isAuthenticated(): boolean {
  return getSession() !== null && !isSessionExpired();
}

/** True when the local metadata says the session is past expiry.
 *  Returns ``false`` when the session id exists but no metadata is
 *  stored (legacy session pre-v0.3.4); the backend will reject with
 *  401 in that case and the centralized handler will clean up. */
export function isSessionExpired(): boolean {
  const m = getSessionMeta();
  if (!m) return false;
  return Date.now() >= m.expires_at;
}

/** Age + remaining time for the current session. Returns ``null``
 *  if no metadata is stored (so callers can fall back to "unknown"). */
export function getSessionAge():
  | { ageMs: number; remainingMs: number }
  | null {
  const m = getSessionMeta();
  if (!m) return null;
  const now = Date.now();
  return {
    ageMs: Math.max(0, now - m.created_at),
    remainingMs: m.expires_at - now,
  };
}

/** Run once at app load (from main.tsx). Clears any expired session
 *  BEFORE React renders so the first paint shows the correct
 *  authed/unauthed state. Cheap; safe to call multiple times. */
export function hydrateSessionOnLoad(): void {
  if (isSessionExpired()) clearSession();
}

// ---------------------------------------------------------------------------
// Redirect helper (centralized 401 / expiry hygiene)
// ---------------------------------------------------------------------------

/** Hard-navigate to ``/login?from=<current_path>``. Used by the
 *  centralized 401 + expiry handlers in ``apiFetch``.
 *
 *  Guards:
 *    * No-op when ``window`` is undefined (SSR / tests).
 *    * No-op when already on ``/login`` (prevents the obvious
 *      loop: 401 -> redirect -> page reloads on /login -> /login
 *      submits credentials -> 401 -> ...).
 *    * Uses ``replace`` (not ``assign``) so the broken page isn't
 *      left in the browser history. */
function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  if (window.location.pathname === "/login") return;
  const from = window.location.pathname + window.location.search;
  const url = `/login?from=${encodeURIComponent(from)}`;
  window.location.replace(url);
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

/** Thrown specifically on 401 OR pre-flight expiry. Subclass so
 *  screens can branch on identity rather than status code. */
export class AuthRequiredError extends ApiError {
  constructor() {
    super("Not signed in", 401, "auth_required");
    this.name = "AuthRequiredError";
  }
}

/** Thrown after a fetch failure that doesn't resolve to an HTTP
 *  response (offline, DNS, TLS, CORS preflight reject, etc.).
 *  Distinct so the UI can offer a "Retry" affordance instead of a
 *  generic error block. */
export class NetworkError extends ApiError {
  constructor(message: string) {
    super(message, 0, "network");
    this.name = "NetworkError";
  }
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

interface ApiFetchInit extends RequestInit {
  /** Skip the X-Session-ID header even if a session exists, AND
   *  skip the pre-flight expiry check. Used by ``login()`` so a
   *  stale session never poisons the credentials POST. */
  skipSession?: boolean;
  /** v0.3.12 / Card 17 — Skip the centralized 401 handler
   *  (``clearSession`` + ``redirectToLogin``) AND still throw
   *  ``AuthRequiredError`` for the caller. Used by
   *  ``operatorState()`` so a bad Operator token does NOT log the
   *  user out of their session OR bounce the SPA to ``/login``. */
  skipAuthRedirect?: boolean;
}

async function apiFetch<T>(
  path: string,
  init: ApiFetchInit = {},
): Promise<T> {
  const base = getBackendUrl();
  const url = `${base}${path}`;
  const { skipSession, skipAuthRedirect, ...rest } = init;
  const method = (rest.method ?? "GET").toUpperCase();

  // ---- pre-flight: refuse to send an expired session ----------------
  if (!skipSession && isSessionExpired()) {
    clearSession();
    redirectToLogin();
    throw new AuthRequiredError();
  }

  const session = skipSession ? null : getSession();
  const wantsBody = method === "POST" || method === "PUT";
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(wantsBody ? { "Content-Type": "application/json" } : {}),
    ...(session ? { "X-Session-ID": session } : {}),
    ...((rest.headers as Record<string, string> | undefined) ?? {}),
  };

  const requestInit: RequestInit = { ...rest, headers, method };
  const doFetch = async (): Promise<Response> => fetch(url, requestInit);

  // ---- transport: with GET-only single retry on network error -------
  let resp: Response;
  try {
    resp = await doFetch();
  } catch (e) {
    // True transport failure (offline / DNS / TLS). Retry exactly
    // once for GET — POSTs may have already executed on the server
    // and re-issuing them risks double-mutation.
    if (method === "GET") {
      await new Promise((r) => setTimeout(r, NETWORK_RETRY_DELAY_MS));
      try {
        resp = await doFetch();
      } catch (e2) {
        throw new NetworkError(
          (e2 as Error).message || "Network error",
        );
      }
    } else {
      throw new NetworkError((e as Error).message || "Network error");
    }
  }

  // ---- 401: centralized clear + redirect, then throw as backstop ----
  if (resp.status === 401) {
    if (!skipAuthRedirect) {
      clearSession();
      redirectToLogin();
    }
    throw new AuthRequiredError();
  }

  // ---- other non-OK statuses: structured error parsing --------------
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

  // ---- OK ----
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
  /** v0.3.12 / Card 16 backend field. ``true`` when the request
   *  carries a valid Operator token in ``Authorization`` OR the
   *  user is in cohort ``founder_exception``. Pocket reads this
   *  directly — no cohort/tier inference. */
  operator?: boolean;
  /** v0.3.12 / Card 16 backend field. ``true`` when the v46
   *  memory vault is configured + the per-user key derivation
   *  succeeds. ``false`` means the engine's vault is degraded
   *  (typically ``CLARITYOS_VAULT_SECRET`` not set). */
  vault_ready?: boolean;
}

/** v0.3.12 / Card 17 — shape of GET /operator/state response. */
export interface OperatorState {
  ok: boolean;
  engine_revision: string;
  vault_status: string;
  active_sessions: number | string;
  uptime_seconds: number;
  cors_origins: string[];
  backend: string;
  version: string;
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
  if (data?.session_id) {
    const now = Date.now();
    const ttl = typeof data.expires_in === "number" ? data.expires_in : 0;
    setSession(data.session_id, {
      created_at: now,
      expires_at: now + ttl * 1000,
      user: data.user,
    });
  }
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
// v0.3.12 / Card 17 — operator token (in-memory only, no localStorage)
// ---------------------------------------------------------------------------

/** Module-local operator token. Intentionally NOT persisted to
 *  localStorage — the card mandates in-memory storage so the token
 *  dies on page reload. Trades UX (re-paste per session) for
 *  reduced exposure surface. */
let _operatorToken: string | null = null;

export function setOperatorToken(token: string): void {
  const trimmed = token.trim();
  _operatorToken = trimmed.length > 0 ? trimmed : null;
}

export function getOperatorToken(): string | null {
  return _operatorToken;
}

export function clearOperatorToken(): void {
  _operatorToken = null;
}

export function hasOperatorToken(): boolean {
  return _operatorToken !== null;
}

/**
 * GET /operator/state — requires an Operator token previously set
 * via ``setOperatorToken``. Sends ``Authorization: Operator <token>``
 * (not the user session). Skips the centralized 401 redirect so a
 * bad token does NOT log the user out OR bounce the SPA — the
 * caller surfaces the error inline.
 */
export async function operatorState(): Promise<OperatorState> {
  const token = _operatorToken;
  if (!token) {
    throw new ApiError(
      "No operator token set. Paste it on /operator/state.",
      0,
      "no_operator_token",
    );
  }
  return apiFetch<OperatorState>("/operator/state", {
    method: "GET",
    skipSession: true,
    skipAuthRedirect: true,
    headers: { Authorization: `Operator ${token}` },
  });
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
