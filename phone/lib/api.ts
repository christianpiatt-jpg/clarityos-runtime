// Mobile mirror of web/assets/js/api.js. Same routes, same envelope,
// same X-Session-ID convention. The session token is held in
// AsyncStorage and cached in-memory after the first read.

import { API_BASE } from "./config";
import { storage, KEYS } from "./storage";

// Profile type lives here (top of file) so logout() can clear it without
// a forward-reference to the declaration further down.
export interface Profile {
  user: string;
  cohort: "founder" | "founder_exception" | "terrace_1" | null | undefined;
  operator_id: string | null | undefined;
  tier?: string;
  billing_expires_at?: number | null;
}

let memorySession: string | null = null;
let memoryUser: string | null = null;
let memoryProfile: Profile | null = null;
let baseOverride: string | null = null;

export async function getApiBase(): Promise<string> {
  if (baseOverride) return baseOverride.replace(/\/+$/, "");
  const stored = await storage.get(KEYS.apiBaseOverride);
  baseOverride = stored;
  return (stored || API_BASE).replace(/\/+$/, "");
}

export async function setApiBaseOverride(url: string | null) {
  if (url) {
    await storage.set(KEYS.apiBaseOverride, url);
    baseOverride = url;
  } else {
    await storage.remove(KEYS.apiBaseOverride);
    baseOverride = null;
  }
}

export async function loadSession() {
  memorySession = await storage.get(KEYS.session);
  memoryUser = await storage.get(KEYS.user);
  return { session: memorySession, user: memoryUser };
}

export function getSession() { return memorySession; }
export function getUser() { return memoryUser; }

async function setSession(sid: string, user: string) {
  memorySession = sid;
  memoryUser = user;
  await storage.set(KEYS.session, sid);
  await storage.set(KEYS.user, user);
}

// Public alias for non-login flows (invite redemption, finalize, etc.)
// Mirrors what login()/register() do internally so a freshly redeemed
// session is treated identically to one obtained via /login.
export const setSessionToken = setSession;

export async function logout() {
  memorySession = null;
  memoryUser = null;
  memoryProfile = null;
  await storage.multiRemove([KEYS.session, KEYS.user]);
}

export class ApiError extends Error {
  code: string;
  status: number;
  body: unknown;
  constructor(code: string, message: string, status: number, body?: unknown) {
    super(message);
    this.code = code;
    this.status = status;
    this.body = body;
  }
}

type ReqOpts = { method?: string; body?: unknown; auth?: boolean };

export async function request<T = any>(path: string, opts: ReqOpts = {}): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    if (!memorySession) throw new ApiError("missing_session", "Not signed in", 401);
    headers["X-Session-ID"] = memorySession;
  }
  const base = await getApiBase();
  let res: Response;
  try {
    res = await fetch(base + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e: any) {
    throw new ApiError("network_error", e?.message || "Network unreachable", 0);
  }
  let data: any = null;
  try { data = await res.json(); } catch { /* non-JSON or empty */ }
  if (!res.ok || (data && data.ok === false)) {
    const code = (data && data.error) || "http_error";
    const msg = (data && data.message) || `HTTP ${res.status}`;
    throw new ApiError(code, msg, res.status, data);
  }
  return data as T;
}

// ---------- Auth ----------
export async function login(username: string, password: string) {
  const data = await request<{ session_id: string; user: string }>("/login", {
    method: "POST",
    body: { username, password },
    auth: false,
  });
  await setSession(data.session_id, data.user);
  return data;
}

export async function register(username: string, password: string) {
  const data = await request<{ session_id: string; user: string }>("/register", {
    method: "POST",
    body: { username, password },
    auth: false,
  });
  await setSession(data.session_id, data.user);
  return data;
}

// ---------- Account ----------
export interface MeResponse {
  ok: true;
  user: string;
  session_id: string;
  cohort?: "founder" | "founder_exception" | "terrace_1" | null;
  operator_id?: string | null;
  tier?: string;
  billing_expires_at?: number | null;
}

export interface ConfigResponse {
  ok: true;
  data: {
    backend?: string;
    version?: string;
    library_bucket?: string;
    library_prefix?: string;
    session_ttl?: number;
    cors_origins?: string[];
    user?: string;
    gcs_available?: boolean;
    invite_only?: boolean;
    terrace_1_cap?: number;
    terrace_1_redeemed?: number;
    billing_configured?: boolean;
  };
}

export const me = () => request<MeResponse>("/me");
export const config = () => request<ConfigResponse>("/config");

// ---------- Profile cache (cohort + operator_id, populated by /me) ----------
// Profile type + memoryProfile slot declared at top of file.

export function getProfile(): Profile | null {
  return memoryProfile;
}

export function clearProfile(): void {
  memoryProfile = null;
}

/**
 * Pull /me and cache the full profile in memory. On 401/403, clears the
 * local session so the UI falls back to the unauth path. On network errors,
 * leaves the cached profile alone (a transient blip shouldn't sign the user out).
 */
export async function refreshProfile(): Promise<Profile | null> {
  if (!memorySession) {
    memoryProfile = null;
    return null;
  }
  try {
    const m = await me();
    memoryProfile = {
      user: m.user,
      cohort: m.cohort ?? null,
      operator_id: m.operator_id ?? null,
      tier: m.tier,
      billing_expires_at: m.billing_expires_at ?? null,
    };
    return memoryProfile;
  } catch (e) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      // Session is invalid server-side — clear local state.
      memoryProfile = null;
      await logout();
      return null;
    }
    // Network or 5xx — keep whatever we already cached.
    return memoryProfile;
  }
}

// ---------- Engines ----------
type Envelope<D> = { ok: true; engine: string; data: D };

export const markov = (text: string, meta?: Record<string, unknown>) =>
  request<Envelope<{ score: number; tags: string[]; interpretation: string; user: string }>>(
    "/markov", { method: "POST", body: { text, meta } });

export const galileo = (text: string, meta?: Record<string, unknown>) =>
  request<Envelope<{ clarity_level: number; summary: string; mode: string; user: string }>>(
    "/galileo", { method: "POST", body: { text, meta } });

export const tizzy = (text: string, meta?: Record<string, unknown>) =>
  request<Envelope<{ result: string; user: string }>>(
    "/tizzy", { method: "POST", body: { text, meta } });

export const library = (path: string, meta?: Record<string, unknown>) =>
  request<Envelope<{ path: string; bucket: string; prefix: string; size: number; content: string }>>(
    "/library", { method: "POST", body: { text: path, meta } });

// ---------- Public ----------
export const health = () =>
  request<{ ok: true; status: string; version: string }>("/health", { auth: false });

// ---------- Backend status probe + retry ----------
export interface BackendStatus {
  reachable: boolean;
  version?: string;
  error?: string;
  apiBase: string;
}

/**
 * Hit /health (public, no auth) to confirm the backend URL is reachable.
 * Used at app startup so the UI can show a banner if the backend is down
 * or the API_BASE placeholder hasn't been replaced.
 */
export async function probeBackend(): Promise<BackendStatus> {
  const apiBase = await getApiBase();
  try {
    const r = await withRetry(() => health(), { attempts: 2, baseDelayMs: 400 });
    return { reachable: true, version: r.version, apiBase };
  } catch (e: any) {
    const msg = e?.message || String(e);
    return { reachable: false, error: msg, apiBase };
  }
}

/**
 * Retry helper. Retries on network errors and 5xx; never retries 4xx
 * (those are deterministic — auth, validation, etc.). Exponential backoff.
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  opts: { attempts?: number; baseDelayMs?: number } = {}
): Promise<T> {
  const attempts = opts.attempts ?? 3;
  const baseDelayMs = opts.baseDelayMs ?? 500;
  let lastErr: unknown;
  for (let i = 0; i < attempts; i++) {
    try {
      return await fn();
    } catch (e) {
      lastErr = e;
      if (e instanceof ApiError) {
        // Deterministic client errors — don't retry.
        if (e.status >= 400 && e.status < 500) throw e;
      }
      if (i < attempts - 1) {
        await new Promise((r) => setTimeout(r, baseDelayMs * Math.pow(2, i)));
      }
    }
  }
  throw lastErr;
}

// ===========================================================================
// v28 — Surface + Distribution layer (mirrors web/lib/api.ts)
// ===========================================================================

export interface GElinsAnalysis {
  neighborhoods: Array<{
    neighborhood_id: string | null;
    name: string | null;
    similarity: number;
    curvature: number | null;
  }>;
  qc_summary: { pressure: number };
  elins_physics: Record<string, unknown>;
  universal_physics: {
    constraints: string[];
    phases: string[];
    operators: string[];
    scale_annotations: Record<string, string[]>;
  };
  persisted_membership_id: string | null;
  last_updated_ts: number;
}

export interface ElinsDeliveredReport {
  report_id: string;
  delivered_at: number;
  scenario_id: string;
  deliver_email: boolean;
  deliver_feed: boolean;
  analysis: GElinsAnalysis | { error: string; message: string };
}

export interface ContinuitySnapshot {
  user: string;
  now_ts: number;
  counts: Record<string, number>;
  last_updated_ts: Record<string, number | null>;
  memory_context: Record<string, unknown>;
  coherence_flags: Record<string, boolean>;
}

export interface MeshState {
  devices: Record<string, { metadata: Record<string, unknown>; last_seen_ts: number }>;
}

export const gElinsRun = (scenario_text: string) =>
  request<{ ok: true; analysis: GElinsAnalysis }>("/elins/g/run", {
    method: "POST",
    body: { scenario_text },
  });

export const elinsDailyQueue = (input: {
  scenario_text: string;
  deliver_email?: boolean;
  deliver_feed?: boolean;
  local_hour?: number;
  local_minute?: number;
}) =>
  request<{ ok: true; report_id: string; scheduled_for_ts: number }>(
    "/elins/daily/queue",
    { method: "POST", body: input },
  );

export const elinsDailyFeed = (limit = 50) =>
  request<{ ok: true; delivered: ElinsDeliveredReport[]; count: number }>(
    `/elins/daily/feed?limit=${encodeURIComponent(limit)}`,
  );

export const meshSync = (device_id: string, metadata: Record<string, unknown>) =>
  request<{ ok: true; device: { metadata: Record<string, unknown>; last_seen_ts: number } }>(
    "/mesh/sync",
    { method: "POST", body: { device_id, metadata } },
  );

export const meshState = () =>
  request<{ ok: true; state: MeshState }>("/mesh/state");

export const continuitySnapshot = () =>
  request<{ ok: true; snapshot: ContinuitySnapshot }>("/continuity/snapshot");

// ---------- v29 — Hardening + Onboarding helpers ----------
export type V29Flag =
  | "v28_surfaces"
  | "onboarding_v1"
  | "whats_new_v28"
  | "demo_data"
  | "rate_limit_logging"
  | "founder_tier_enabled"   // v30
  | "g_credits_enabled"      // v30
  | "membership_ui_enabled"; // v30

export interface V29FlagsResponse {
  ok: true;
  flags: Record<V29Flag, boolean>;
}

export const v29Flags = () => request<V29FlagsResponse>("/v29/flags");

export const v29OnboardingState = () =>
  request<{ ok: true; user: string; completed: string[]; next_step: string | null; done: boolean; steps: string[] }>(
    "/v29/onboarding/state",
  );

export const v29OnboardingComplete = (step: string) =>
  request<{ ok: true; onboarding: Record<string, number> }>(
    "/v29/onboarding/complete",
    { method: "POST", body: { step } },
  );

// ---------- v30 — Membership + #G credits + v31 billing additions ----------
export type V31BillingState =
  | "active"
  | "past_due"
  | "grace_period"
  | "cancelled"
  | "failed"
  | null;

export interface MembershipStateView {
  user: string;
  membership: {
    tier: string | null;
    status: "active" | "cancelled" | null;
    price_locked: number | null;
    started_ts: number | null;
    cancelled_ts: number | null;
    next_price: number;
    price_lock_forfeit: boolean;
  };
  billing: {
    state: V31BillingState;
    renewal_ts: number | null;
    renewal_retry_count: number;
    renewal_grace_until_ts: number | null;
    next_amount: number;
  };
  cohort: {
    cohort: string;
    active_count: number;
    cap: number | null;
    remaining: number | null;
    waitlist_count: number;
    is_full: boolean;
  };
  waitlist_position: number | null;
  g_credits: {
    balance: number;
    history_tail: Array<{ type: string; credits_delta: number; amount: number; ts: number }>;
  };
}

export interface PaymentIntentView {
  intent_id: string;
  client_secret: string | null;
  status: string;
  amount: number;
  kind: string;
  mode: string;
}

export interface PurchaseResult {
  ok: true;
  pending: boolean;
  balance: number;
  intent: PaymentIntentView;
  purchase: { units: number; amount: number; intent_id: string; mode: string };
}

export interface ActivateResult {
  ok: true;
  pending?: boolean;
  already_active?: boolean;
  waitlisted?: boolean;
  intent?: PaymentIntentView;
  state: MembershipStateView;
}

export interface BillingHistoryIntent {
  intent_id: string;
  amount: number;
  kind: string;
  status: string;
  mode: string;
  created_ts: number;
  confirmed_ts?: number;
  failed_ts?: number;
  failure_code?: string;
  description?: string;
}

export interface MembershipTransaction {
  user: string;
  type: string;
  amount: number;
  credits_delta: number;
  metadata: Record<string, unknown>;
  ts: number;
}

export const membershipState = () =>
  request<{ ok: true; state: MembershipStateView }>("/membership/state");

export const membershipActivate = (acceptTerms: boolean) =>
  request<ActivateResult>(
    "/membership/activate",
    { method: "POST", body: { accept_terms: acceptTerms } },
  );

export const membershipCancel = () =>
  request<{ ok: true; state: MembershipStateView }>("/membership/cancel", {
    method: "POST",
    body: {},
  });

export const gBuySingle = () =>
  request<PurchaseResult>("/membership/g/buy_single", { method: "POST", body: {} });

export const gBuyPack20 = () =>
  request<PurchaseResult>("/membership/g/buy_pack_20", { method: "POST", body: {} });

export const gHistory = (limit = 100) =>
  request<{ ok: true; transactions: MembershipTransaction[]; count: number }>(
    `/membership/g/history?limit=${encodeURIComponent(limit)}`,
  );

// ---------- v31 — Billing finalization helpers ----------
export const billingCreateIntent = (input: {
  amount: number;
  description: string;
  kind: string;
  metadata?: Record<string, unknown>;
}) =>
  request<{ ok: true; pending: boolean; intent: PaymentIntentView }>(
    "/billing/intent",
    { method: "POST", body: input },
  );

export const billingConfirmIntent = (intent_id: string) =>
  request<{ ok: true; intent: Record<string, unknown> }>(
    "/billing/intent/confirm",
    { method: "POST", body: { intent_id } },
  );

export const billingHistory = (limit = 100) =>
  request<{
    ok: true;
    transactions: MembershipTransaction[];
    intents: BillingHistoryIntent[];
    count: number;
  }>(`/billing/history?limit=${encodeURIComponent(limit)}`);

// ---------- v33 — Founder Console + ELINS standardization + #cmt ----------
export interface V33ELINSObject {
  input_phase: { scenario_id: string; text: string; word_count: number; ts: number; user?: string | null; domain_hint?: string | null };
  primitives: { intensities: Record<string, number>; raw_scores: Record<string, number>; primitive_keys: string[] };
  domain_mapping: { scores: Record<string, number>; top: string | null; hint: string | null; effective_top: string | null };
  ep_field_summary: { stress_total: number; relief_total: number; net: number; dominant: string; intensity_mean: number };
  causal_chain: { edges: Array<{ from: string; to: string; weight: number }>; edge_count: number; threshold: number };
  stress_relief: { signal: string; net_pressure: number; edge_count: number };
  forecast_5day: { days: Array<{ day: number; projected_net: number; phase: string }>; starting_net: number; ending_net: number; trend: string };
  forecast_engine?: {
    primitive_envelopes: Record<string, number[]>;
    multi_envelope: number[];
    domain_envelopes: Record<string, number[]>;
    chain: Array<{ key: string; intensity: number; lambda?: number; attenuation?: number }> | null;
    chain_envelope: number[] | null;
    days: number;
    version: string;
  };
  synthesis: { top_primitive: string; top_primitive_intensity: number; domain: string | null; signal: string; trend: string; stress_score: number; relief_score: number };
  qc_s_elins: { self_check: string; max_delta: number; deltas: Record<string, number> };
  output_object: { scenario_id: string; summary: Record<string, unknown>; ts: number; version: string };
  layer_names: string[];
}

export interface V33SELINSResult {
  ok: boolean;
  scenario_id: string;
  alignment_score: number;
  max_delta: number;
  deltas: Record<string, number>;
  fresh_primitives: Record<string, number>;
  passed: boolean;
  threshold: number;
  version: string;
  ts: number;
}

export interface V33CommentResult {
  ok: true;
  comment: string;
  detection: { attractor: string; domain: string | null; tone: string; primitive_intensities: Record<string, number>; domain_scores: Record<string, number>; input_word_count: number };
  construction: { structural_reframe: string; domain_alignment: string; identity_move: string; stabilizing_close: string };
  activation: { micro_thread_trigger: string; low_emotion: boolean; noun_density: number; char_count: number };
  version: string;
  ts: number;
}

export type V33DMChannel = "linkedin" | "facebook" | "email" | "manual";

export interface V33DM {
  id: string;
  user: string | null;
  external_id: string | null;
  channel: V33DMChannel;
  subject: string | null;
  snippet: string | null;
  ts: number;
  founder: string;
}

export interface V33DMNote {
  id: string;
  dm_id: string;
  founder: string;
  body: string;
  ts: number;
}

export const elinsPreview = (text: string, domain_hint?: string) =>
  request<{ ok: true; elins: V33ELINSObject }>("/elins/preview", {
    method: "POST",
    body: { text, ...(domain_hint ? { domain_hint } : {}) },
  });

export const elinsQC = (elins_object: V33ELINSObject) =>
  request<{ ok: true; s_elins: V33SELINSResult }>("/elins/qc", {
    method: "POST", body: { elins_object },
  });

// ---------- v34 — ELINS forecast engine ----------
export type V34DomainName =
  | "Economic_Markets"
  | "Geopolitical"
  | "Social_Cultural"
  | "Security_Military"
  | "Legal_Justice"
  | "Science_Technology"
  | "Environmental";

export const V34_DOMAIN_NAMES: V34DomainName[] = [
  "Economic_Markets", "Geopolitical", "Social_Cultural", "Security_Military",
  "Legal_Justice", "Science_Technology", "Environmental",
];

export interface V34ForecastPrimitive {
  key: string;
  intensity: number;
  lambda?: number;
  attenuation?: number;
}

export interface V34ForecastBlock {
  primitive_envelopes: Record<string, number[]>;
  multi_envelope: number[];
  domain_envelopes: Partial<Record<V34DomainName, number[]>>;
  chain: V34ForecastPrimitive[] | null;
  chain_envelope: number[] | null;
  days: number;
  version: string;
}

export interface V34ForecastExample {
  ok: true;
  example: {
    label: string;
    inputs: { intensities: Record<string, number>; edges: Array<{ from: string; to: string; weight: number }>; days: number };
    forecast: V34ForecastBlock;
  };
}

export const elinsForecast = (
  primitives: V34ForecastPrimitive[],
  opts: { chain?: V34ForecastPrimitive[]; domains?: V34DomainName[]; days?: number } = {},
) =>
  request<{ ok: true; forecast: V34ForecastBlock }>("/elins/forecast", {
    method: "POST",
    body: {
      primitives,
      ...(opts.chain ? { chain: opts.chain } : {}),
      ...(opts.domains ? { domains: opts.domains } : {}),
      days: opts.days ?? 5,
    },
  });

export const elinsForecastExample = () =>
  request<V34ForecastExample>("/elins/forecast/example");

// ---------- v35 — Regional ELINS ----------
export type V35RegionCode = "US" | "EU" | "MEA" | "APAC" | "Markets" | "Tech";

export const V35_REGION_CODES: V35RegionCode[] = ["US", "EU", "MEA", "APAC", "Markets", "Tech"];

export interface V35ExternalSignal {
  key: string;
  intensity: number;
  weight?: number;
  source?: string;
  anchor?: string;
}

export interface V35ExternalSignals {
  present: boolean;
  region_code: string | null;
  anchors: string[];
  signals: V35ExternalSignal[];
  contributions?: Record<string, number>;
  domain_bias?: Record<string, number>;
  version?: string;
  mock?: boolean;
}

export interface V35RegionalELINS extends V33ELINSObject {
  region_code: V35RegionCode;
  topic_hint: string | null;
  regional_run_ts: number;
  external_signals: V35ExternalSignals;
  regional_delta: {
    deltas: Record<string, number>;
    largest_shift_primitive: string | null;
    largest_shift_value: number;
    previous_scenario_id: string | null;
  } | null;
}

export interface V35RegionalListItem {
  region_code: V35RegionCode;
  latest:
    | null
    | {
        run_id: string; day: string; scenario_id: string;
        summary: Record<string, unknown>;
        domain_top: string | null;
        external_present: boolean;
        external_anchors: string[];
        saved_ts: number;
      };
}

export const elinsRegionalRun = (region_code: V35RegionCode, topic_hint?: string) =>
  request<{ ok: true; run_id: string; region_code: V35RegionCode; elins: V35RegionalELINS; eso_present: boolean }>(
    "/elins/regional/run",
    {
      method: "POST",
      body: { region_code, ...(topic_hint ? { topic_hint } : {}) },
    },
  );

export const elinsRegionalList = () =>
  request<{ ok: true; regions: V35RegionCode[]; items: V35RegionalListItem[] }>(
    "/elins/regional/list",
  );

// ---------- v36 — Macro-ELINS scheduler ----------
export type V36Cadence = "off" | "daily" | "3x_week" | "weekly";
export type V36SignalMode = "cloud_only" | "cloud_perplexity";

export interface V36SchedulerConfig {
  enabled: boolean;
  cadence: V36Cadence;
  external_signal_mode: V36SignalMode;
  system_user: string;
  last_run_ts: number;
}

export interface V36SchedulerStatus {
  ok: true;
  config: V36SchedulerConfig;
  running: boolean;
  tick_seconds: number;
  valid_cadences: V36Cadence[];
  valid_signal_modes: V36SignalMode[];
}

export interface V36MacroRun {
  run_id: string;
  ts: number;
  regions: string[];
  global_run_ref: { run_id?: string; scenario_id?: string };
  region_run_ids: Record<string, string>;
  external_signal_mode: V36SignalMode | null;
  notes: string | null;
}

export interface V36MacroRunDetail extends V36MacroRun {
  global_run?: Record<string, unknown> | null;
  regional_runs?: Record<string, Record<string, unknown> | null>;
}

export const founderSchedulerStatus = () =>
  request<V36SchedulerStatus>("/founder/elins/scheduler/status");

export const founderSchedulerConfig = (updates: Partial<V36SchedulerConfig>) =>
  request<{ ok: true; config: V36SchedulerConfig; running: boolean }>(
    "/founder/elins/scheduler/config",
    { method: "POST", body: updates },
  );

export const founderMacroRunNow = () =>
  request<{ ok: true; summary: { ran: boolean; run_id?: string; regions?: string[]; ts?: number; global_run_id?: string; external_signal_mode?: string } }>(
    "/founder/elins/macro/run_now",
    { method: "POST" },
  );

export const founderMacroRunsList = (limit = 20) =>
  request<{ ok: true; runs: V36MacroRun[]; count: number }>(
    `/founder/elins/macro/runs?limit=${encodeURIComponent(limit)}`,
  );

export const founderMacroRunDetail = (run_id: string) =>
  request<{ ok: true; run: V36MacroRunDetail }>(
    `/founder/elins/macro/run/${encodeURIComponent(run_id)}`,
  );

// ---------- v37 — Entity graph ----------
export interface V37EntitySearchHit {
  name: string;
  degree: number;
  ep_mean: number;
  top_domains: string[];
  clusters: string[];
}

export interface V37EntityNeighbor {
  name: string;
  weight: number;
  co_occurrences: number;
  first_ts: number;
  last_ts: number;
  top_domains: string[];
}

export interface V37EntitySummary {
  degree: number;
  clusters: string[];
  ep_mean: number;
  domains: Record<string, number>;
}

export interface V37EntityAppearance {
  ts: number;
  ep_mean: number;
  domains: Record<string, number>;
  cluster: string;
}

export const elinsEntitiesSearch = (q: string, limit = 50) =>
  request<{ ok: true; q: string; entities: V37EntitySearchHit[]; count: number; graph_updated_ts: number }>(
    `/elins/entities/search?q=${encodeURIComponent(q)}&limit=${encodeURIComponent(limit)}`,
  );

export const elinsEntityNeighbors = (entity: string, limit = 20) =>
  request<{ ok: true; entity: string; summary: V37EntitySummary; neighbors: V37EntityNeighbor[] }>(
    `/elins/entities/${encodeURIComponent(entity)}/neighbors?limit=${encodeURIComponent(limit)}`,
  );

export const elinsEntityTimeseries = (entity: string) =>
  request<{ ok: true; entity: string; timeseries: V37EntityAppearance[] }>(
    `/elins/entities/${encodeURIComponent(entity)}/timeseries`,
  );

// ---------- v38 — ELINS dashboard ----------
export interface V38DashboardSection {
  scenario_id: string | null;
  ep_mean: number;
  domains: Record<string, number>;
  top_primitives: Array<{ key: string; intensity: number }>;
  forecast: number[];
  has_eso: boolean;
  available: boolean;
  day?: string;
  user?: string;
}

export interface V38DashboardSnapshot {
  ts: number;
  date: string;
  global: V38DashboardSection;
  regional: Record<string, V38DashboardSection>;
  macro: {
    last_run_id: string | null;
    last_run_ts: number | null;
    ep_mean: number | null;
    regions_count: number | null;
    external_signal_mode: string | null;
  };
  entity_graph: {
    entity_count: number;
    edge_count: number;
    updated_ts: number;
    top_entities: Array<{ name: string; degree: number; ep_mean: number; top_domains: string[] }>;
    available: boolean;
  };
  continuity?: {
    last_topics: string[];
    preferred_domains: Array<{ name: string; weight: number }>;
    preferred_regions: Array<{ name: string; weight: number }>;
    external_signal_mode: "cloud_only" | "cloud_perplexity";
    history_count: number;
    g_count: number;
  };
  version: string;
}

export const elinsDashboard = () =>
  request<{ ok: true; snapshot: V38DashboardSnapshot }>("/elins/dashboard");

export const elinsDashboardForDate = (date: string) =>
  request<{ ok: true; snapshot: V38DashboardSnapshot }>(
    `/elins/dashboard/${encodeURIComponent(date)}`,
  );

// ---------- v39 — Operator state memory ----------
export type V39SignalMode = "cloud_only" | "cloud_perplexity";

export interface V39ElinsHistoryEntry {
  ts: number;
  elins_id: string;
  topic: string;
  region: string | null;
  kind: string;
}

export interface V39GHistoryEntry {
  ts: number;
  g_id: string;
  mode: string;
  topic: string;
}

export interface V39OperatorState {
  user_id: string;
  created_ts: number;
  last_active_ts: number;
  elins_history: V39ElinsHistoryEntry[];
  g_history: V39GHistoryEntry[];
  preferred_domains: Record<string, number>;
  preferred_regions: Record<string, number>;
  external_signal_mode: V39SignalMode;
  version: string;
}

export const meOperatorState = () =>
  request<{ ok: true; state: V39OperatorState }>("/me/operator_state");

export const meOperatorStateUpdate = (patch: { external_signal_mode?: V39SignalMode }) =>
  request<{ ok: true; state: V39OperatorState }>("/me/operator_state", {
    method: "POST", body: patch,
  });

// ---------- v42 — Billing state ----------
export type V42StripeMode = "test" | "live" | "disabled";

export interface V42MeBilling {
  ok: true;
  status: "none" | "active" | "past_due" | "canceled";
  plan: string | null;
  renewal_ts: number | null;
  mode: V42StripeMode;
  billing_enabled: boolean;
}

export const meBilling = () =>
  request<V42MeBilling>("/me/billing");

// ---------- v43 — Founder analytics ----------
export interface V43FounderAnalyticsSummary {
  users: { total: number; active_7d: number; active_30d: number };
  billing: {
    active_subscriptions: number;
    past_due: number;
    canceled: number;
    mode: "test" | "live" | "disabled";
  };
  intelligence: {
    elins_runs_7d: number;
    g_runs_7d: number;
    macro_runs_7d: number;
    eso_usage_rate_7d: number;
  };
  ts: number;
  version: string;
}

export const founderAnalyticsSummary = () =>
  request<{ ok: true; summary: V43FounderAnalyticsSummary }>(
    "/founder/analytics/summary",
  );

// ---------- v44 — Model router ----------
export type V44ModelId =
  | "openai:gpt-4.2"
  | "anthropic:claude-3.7"
  | "google:gemini-2.0"
  | "xai:groq-llama"
  | "local:llama3.1"
  | "auto";

export const V44_MODEL_IDS: V44ModelId[] = [
  "auto",
  "openai:gpt-4.2",
  "anthropic:claude-3.7",
  "google:gemini-2.0",
  "xai:groq-llama",
  "local:llama3.1",
];

export interface V44RouterStatus {
  version: string;
  supported_models: V44ModelId[];
  task_defaults: Record<string, V44ModelId>;
  founder_default_model: V44ModelId | null;
  providers: Record<string, { configured: boolean; path?: string | null }>;
  local_runtime?: {
    version?: string;
    configured: boolean;
    path: string | null;
    loaded: boolean;
    backend: string | null;
    mock: boolean;
    memory_footprint_mb: number;
    inference_count: number;
    loaded_at?: number | null;
    last_error?: string | null;
  };
}

export const meOperatorStateModel = (preferred_model: V44ModelId | null) =>
  request<{ ok: true; state: V39OperatorState }>(
    "/me/operator_state/model",
    { method: "POST", body: { preferred_model } },
  );

export const founderModelsStatus = () =>
  request<{ ok: true; router: V44RouterStatus }>(
    "/founder/models/status",
  );

// ---------- v45 — Local model runtime ----------
export const V45_LOCAL_MODEL_ID = "local:llama3.1" as const;

export interface V45LocalRuntimeStatus {
  version?: string;
  configured: boolean;
  path: string | null;
  loaded: boolean;
  backend: string | null;
  mock: boolean;
  memory_footprint_mb: number;
  inference_count: number;
  loaded_at?: number | null;
  last_error?: string | null;
  fallback?: string;
}

export interface V45LocalModelMe {
  ok: true;
  runtime: V45LocalRuntimeStatus;
  usage: {
    local_model_usage_count: number;
    last_model_used: string | null;
    preferred_model: string | null;
    is_local_preferred: boolean;
  };
  model_id: string;
}

export interface V45FounderLocal {
  ok: true;
  runtime: V45LocalRuntimeStatus & {
    bytes_estimate?: number;
    cached_handles?: number;
  };
  env_path: string | null;
  model_id: string;
  router_provider: { configured: boolean; path?: string | null };
}

export const meLocalModel = () =>
  request<V45LocalModelMe>("/me/local_model");

export const founderModelsLocal = () =>
  request<V45FounderLocal>("/founder/models/local");

// ---------- v46 — Memory Vault ----------
export interface V46VaultGlobal {
  version: string;
  enabled: boolean;
  backend: "mock" | "fs" | "sqlite";
  encrypted: boolean;
  namespaces: string[];
  users: number;
  keys: number;
  scheme: string;
  pbkdf2_iter: number;
}

export interface V46VaultUserStatus {
  user_id: string;
  vault_keys: number;
  notes_count: number;
  embeddings_count: number;
  operator_state_count: number;
  elins_count: number;
  g_runs_count: number;
}

export interface V46VaultStatusResponse {
  ok: true;
  global: V46VaultGlobal;
  user: V46VaultUserStatus;
}

export interface V46VaultNote { key: string; text: string }
export interface V46VaultEmbedding { key: string; dim: number }

export const meVaultStatus = () =>
  request<V46VaultStatusResponse>("/me/vault/status");

export const meVaultNotes = () =>
  request<{ ok: true; notes: V46VaultNote[]; count: number }>("/me/vault/notes");

export const meVaultNotesPut = (key: string, text: string) =>
  request<{ ok: true; key: string }>("/me/vault/notes", {
    method: "POST", body: { key, text },
  });

export const meVaultNotesDelete = (key: string) =>
  request<{ ok: true; key: string }>("/me/vault/notes/delete", {
    method: "POST", body: { key },
  });

export const meVaultEmbeddings = () =>
  request<{ ok: true; embeddings: V46VaultEmbedding[]; count: number }>(
    "/me/vault/embeddings",
  );

export const meVaultEmbeddingsDelete = (key: string) =>
  request<{ ok: true; key: string }>("/me/vault/embeddings/delete", {
    method: "POST", body: { key },
  });

// ---------- v47/v48/v50 — Threads (persistent threaded interactions) ----------
export interface ThreadMeta {
  thread_id: string;
  title: string | null;
  created_at: number;
  updated_at: number;
  message_count: number;
  archived: boolean;
  // v50 — kernel-generated summary + the millisecond timestamp at
  // which it was last computed. Both null until the first
  // ``POST /me/threads/{id}/summarize`` lands.
  summary: string | null;
  summary_ts_ms: number | null;
}

export interface ThreadMessage {
  role: "user" | "assistant" | "system";
  content: string;
  ts_ms: number;
  model: string | null;
}

export interface ThreadDetail {
  meta: ThreadMeta;
  messages: ThreadMessage[];
}

export interface ThreadMessageResult {
  meta: ThreadMeta;
  user_message: ThreadMessage;
  assistant_message: ThreadMessage;
  model_id?: string | null;
}

/** List every thread for the current user, newest-first by ``updated_at``. */
export async function listThreads(): Promise<ThreadMeta[]> {
  const r = await request<{ threads: ThreadMeta[] }>("/me/threads");
  return r.threads;
}

/** Create a new thread; ``title`` may be null/omitted. */
export async function createThread(title?: string | null): Promise<ThreadMeta> {
  return request<ThreadMeta>("/me/threads", {
    method: "POST",
    body: { title: title ?? null },
  });
}

/** Fetch ``(meta, messages)`` for a thread the caller owns. */
export async function getThread(thread_id: string): Promise<ThreadDetail> {
  return request<ThreadDetail>(
    `/me/threads/${encodeURIComponent(thread_id)}`,
  );
}

/**
 * Append a user message + dispatch the assistant reply via the kernel.
 * Returns both messages plus the updated meta.
 */
export async function postThreadMessage(
  thread_id: string,
  content: string,
): Promise<ThreadMessageResult> {
  return request<ThreadMessageResult>(
    `/me/threads/${encodeURIComponent(thread_id)}/message`,
    { method: "POST", body: { content } },
  );
}

/** Update the thread's title. */
export async function renameThread(
  thread_id: string,
  title: string,
): Promise<ThreadMeta> {
  return request<ThreadMeta>(
    `/me/threads/${encodeURIComponent(thread_id)}/rename`,
    { method: "POST", body: { title } },
  );
}

/** Drop the thread + every message. Idempotent on the backend. */
export async function deleteThread(thread_id: string): Promise<void> {
  await request<{ ok: true; thread_id: string }>(
    `/me/threads/${encodeURIComponent(thread_id)}/delete`,
    { method: "POST", body: {} },
  );
}

/**
 * v50 — fetch the cached summary for a thread (no model call).
 * Returns the freshest meta the server has; ``meta.summary`` is null
 * when no summary has been generated yet.
 */
export async function getThreadSummary(thread_id: string): Promise<ThreadMeta> {
  const r = await request<{ meta: ThreadMeta }>(
    `/me/threads/${encodeURIComponent(thread_id)}/summary`,
  );
  return r.meta;
}

/**
 * v50 — generate (or refresh) a summary. The server short-circuits
 * with the cached meta if the summary is < 10 minutes old and
 * ``force`` is not set.
 */
export async function summarizeThread(
  thread_id: string,
  force?: boolean,
): Promise<ThreadMeta> {
  const r = await request<{ meta: ThreadMeta }>(
    `/me/threads/${encodeURIComponent(thread_id)}/summarize`,
    { method: "POST", body: { force: force ?? false } },
  );
  return r.meta;
}

// ---------- v76/v77/v80 — Regression-First chains ----------
export interface RegressionFirstLayer {
  layer_index: number;
  status: "ok" | "issue" | "blocked" | "unknown";
  notes: string | null;
  updated_at: number;
}

export interface RegressionFirstChain {
  chain_id: string;
  created_at: number;
  closed_at: number | null;
  title: string;
  notes: string | null;
  layers: RegressionFirstLayer[];
  tags: Record<string, string>;
}

/**
 * v80 — POST a unified cognitive packet to
 * ``/me/regression_first/packet``. Mirrors the web helper exactly.
 */
export async function postRegressionFirstPacket(
  packet: Record<string, unknown>,
): Promise<RegressionFirstChain> {
  return request<RegressionFirstChain>(
    "/me/regression_first/packet",
    { method: "POST", body: { packet } },
  );
}

/**
 * v82 — POST `/me/regression_first/replay`. Mirrors the web helper.
 * Replays the original packet that drove the given chain as a NEW
 * chain (new chain_id, fresh timeline events). 404 if the chain has
 * no stored original packet.
 */
export async function replayRegressionFirstChain(
  chain_id: string,
): Promise<RegressionFirstChain> {
  return request<RegressionFirstChain>(
    "/me/regression_first/replay",
    { method: "POST", body: { chain_id } },
  );
}

export const cmtGenerate = (text: string, domain_hint?: string) =>
  request<V33CommentResult>("/cmt/generate", {
    method: "POST",
    body: { text, ...(domain_hint ? { domain_hint } : {}) },
  });

export const founderDMAdd = (input: { channel: V33DMChannel; user?: string; subject?: string; snippet?: string; external_id?: string }) =>
  request<{ ok: true; dm: V33DM }>(
    "/founder/dm/add",
    { method: "POST", body: input },
  );

export const founderDMList = (params: { channel?: V33DMChannel; user?: string; limit?: number } = {}) => {
  const qp = new URLSearchParams();
  if (params.channel) qp.set("channel", params.channel);
  if (params.user) qp.set("user", params.user);
  if (params.limit !== undefined) qp.set("limit", String(params.limit));
  const qs = qp.toString();
  return request<{ ok: true; dms: V33DM[]; count: number }>(
    `/founder/dm/list${qs ? "?" + qs : ""}`,
  );
};

export const founderDMNote = (dm_id: string, body: string) =>
  request<{ ok: true; note: V33DMNote; notes: V33DMNote[] }>(
    "/founder/dm/notes",
    { method: "POST", body: { dm_id, body } },
  );

export const founderMembershipActivate = (user: string, opts: { price?: number; note?: string } = {}) =>
  request<{ ok: true; user: string; membership: Record<string, unknown>; already_active?: boolean }>(
    "/founder/membership/activate",
    { method: "POST", body: { user, ...opts } },
  );

export const founderMembershipCancel = (user: string, note?: string) =>
  request<{ ok: true; user: string; membership: Record<string, unknown> }>(
    "/founder/membership/cancel",
    { method: "POST", body: { user, ...(note ? { note } : {}) } },
  );

export const founderMembershipCredits = (user: string, delta: number, reason?: string) =>
  request<{ ok: true; user: string; balance: number; delta: number }>(
    "/founder/membership/credits",
    { method: "POST", body: { user, delta, ...(reason ? { reason } : {}) } },
  );

// ---------- Local-compute stub (mirrors web/console.js) ----------
// Mirrors the cloud envelope so screens can render either path uniformly.
export type EngineName = "markov" | "galileo" | "tizzy";

export function localCompute(name: EngineName, text: string) {
  const length = text.trim().length;
  const start = Date.now();
  const data: Record<string, any> = {
    markov: { tags: length > 80 ? ["long"] : [], score: Math.min(1, length / 200), interpretation: `(local-${name}) ${text.slice(0, 200)}` },
    galileo: { clarity_level: length > 200 ? 3 : length > 80 ? 2 : 1, summary: `(local-${name}) ${text.slice(0, 200)}` },
    tizzy: { result: `(local-${name}) ${text}` },
  }[name] || { result: `(local-${name}) ${text}` };
  return { ok: true as const, engine: name, data: { ...data, mode: "local", elapsed_ms: Date.now() - start } };
}

// ---------- v62 / Unit 45 — Operator session runtime (phone mirror) ----------
// Same contract as web/src/lib/api.ts. Types duplicated by design:
// phone uses Metro, web uses Vite, no shared package between them.
// Server endpoint is open (no X-Session-ID) so we pass auth: false.

export type SessionIntentType =
  | "query"
  | "action"
  | "plan"
  | "diagnostic";

export interface SessionHistoryEntry {
  timestamp:        string;
  intent_type:      SessionIntentType;
  text:             string;
  runtime_decision: "allow" | "warn" | "block";
  engine:           "copilot" | "claude" | "gemini" | "grok" | "local";
}

export interface SessionState {
  session_id:  string;
  operator_id: string;
  vault_state: Record<string, any>;
  history:     SessionHistoryEntry[];
}

export interface SessionUiResponse {
  headline: string;
  body:     string;
  severity: "info" | "warning" | "critical";
  tags:     string[];
}

export interface SessionModelResponse {
  ok:       boolean;
  model_id: string;
  provider: string;
  text:     string;
  mock:     boolean;
  ts:       number;
}

export interface SessionStepResult {
  session_id:  string;
  operator_id: string;
  timestamp:   string;
  runtime: {
    session_id:  string;
    operator_id: string;
    timestamp:   string;
    model_route: { engine: string; reason: string };
    runtime: {
      session_id:       string;
      operator_id:      string;
      timestamp:        string;
      runtime_decision: "allow" | "warn" | "block";
      runtime_events:   string[];
      elins_block:      Record<string, any>;
      vault_update:     Record<string, any>;
      operator_view: {
        headline: string;
        details:  Record<string, any>;
      };
    };
    ui_response: SessionUiResponse;
  };
  model: {
    engine:   string;
    request:  { model_id: string; task: string; prompt_preview: string };
    response: SessionModelResponse;
    metadata: { provider: string; mock: boolean; ts: number };
  };
  vault_update: Record<string, any>;
}

export interface StartSessionResponse {
  session_state: SessionState;
}

export interface StepSessionResponse {
  session_state: SessionState;
  step_result:   SessionStepResult;
}

// v65 / Unit 68 — auth-gated. Server uses authed identity from
// X-Session-ID; body operator_id retained for wire-compat only.

export function startSession(
  operatorId: string,
  opts: { resume?: boolean; sessionId?: string } = {},
): Promise<StartSessionResponse> {
  const body: Record<string, any> = { operator_id: operatorId };
  if (opts.resume) body.resume = true;
  if (opts.sessionId) body.session_id = opts.sessionId;
  return request<StartSessionResponse>("/operator/session/start", {
    method: "POST",
    body,
    auth: true,
  });
}

export function stepSession(
  sessionState: SessionState,
  text: string,
  intentType: SessionIntentType = "query",
): Promise<StepSessionResponse> {
  return request<StepSessionResponse>("/operator/session/step", {
    method: "POST",
    body: {
      session_state: sessionState,
      text,
      intent_type:   intentType,
    },
    auth: true,
  });
}

// ---------- v63 / Units 47 + 48 — Read-only history + vault inspector (phone) ----------
// Types duplicated from web/desktop per established no-cross-tree-sharing
// rule (Metro bundler / Vite / Vite, no shared package).

export interface SessionSummary {
  session_id:  string;
  operator_id: string;
  history_len: number;
  timestamp:   string;
}

export interface SessionListResponse {
  operator_id: string;
  sessions:    SessionSummary[];
}

export interface SessionDetailResponse {
  session_state: SessionState;
}

export interface VaultInspectorResponse {
  operator_id:  string;
  vault:        Record<string, any> | null;
  last_updated: string;
}

// v64 / Unit 66 — auth-gated. operatorId is decorative; server uses
// authed identity. Kept in signature for caller compatibility.

export function listOperatorSessions(
  operatorId: string = "",
): Promise<SessionListResponse> {
  const q = encodeURIComponent(operatorId);
  return request<SessionListResponse>(
    `/operator/sessions?operator_id=${q}`,
    { method: "GET", auth: true },
  );
}

export function getSessionDetail(
  sessionId: string,
): Promise<SessionDetailResponse> {
  const sid = encodeURIComponent(sessionId);
  return request<SessionDetailResponse>(
    `/operator/session/${sid}`,
    { method: "GET", auth: true },
  );
}

export function getOperatorVault(
  operatorId: string = "",
): Promise<VaultInspectorResponse> {
  const oid = encodeURIComponent(operatorId || "self");
  return request<VaultInspectorResponse>(
    `/operator/vault/${oid}`,
    { method: "GET", auth: true },
  );
}

// ---------- v64 / Unit 67 — Operator model preferences (phone) ----------

export interface ModelPreferencesResponse {
  operator_id: string;
  provider:    string;
  model:       string;
  source:      "vault" | "default";
}

export function getModelPreferences(): Promise<ModelPreferencesResponse> {
  return request<ModelPreferencesResponse>(
    "/operator/model_preferences",
    { method: "GET", auth: true },
  );
}

export function setModelPreferences(
  provider: string, model: string,
): Promise<ModelPreferencesResponse> {
  return request<ModelPreferencesResponse>(
    "/operator/model_preferences",
    { method: "POST", body: { provider, model }, auth: true },
  );
}


// ---------- v69 / Unit 74 — EL/INS reasoning-stability operator ----------

export type ElInsRatioClassification = "high_el" | "high_ins" | "balanced";
export type ElInsReasoningMode = "stabilize" | "expand" | "normal";
export type ElInsSource = "on_demand" | "per_turn" | "macro";
export type ElInsProviderMode = "llm" | "deterministic" | "auto";

export interface ElInsAnalysis {
  el_components:        string[];
  ins_components:       string[];
  el_score:             number;
  ins_score:            number;
  ratio_classification: ElInsRatioClassification;
}

export interface ElInsResult {
  analysis:         ElInsAnalysis;
  reasoning_mode:   ElInsReasoningMode;
  regression_chain: {
    projection:      string | null;
    drivers:         string[];
    precedents:      { driver: string; precedent: string; principle: string }[];
    principle_stack: string[];
    invariant:       string | null;
  };
  stability_notes:  string | null;
}

export interface ElInsRecord {
  operator_id: string;
  thread_id:   string | null;
  timestamp:   number;
  source:      ElInsSource;
  result:      ElInsResult;
}

export interface ElInsRecentResponse {
  operator_id: string;
  records:     ElInsRecord[];
}

export function getElInsRecent(limit: number = 100): Promise<ElInsRecentResponse> {
  return request<ElInsRecentResponse>(
    `/el_ins/recent?limit=${encodeURIComponent(limit)}`,
    { method: "GET", auth: true },
  );
}

export function postElInsAnalyze(
  text: string, opts?: { provider_mode?: ElInsProviderMode; thread_id?: string },
): Promise<{ result: ElInsResult; stored: boolean; thread_id: string | null; timestamp: number }> {
  return request<{ result: ElInsResult; stored: boolean; thread_id: string | null; timestamp: number }>(
    "/el_ins/analyze",
    {
      method: "POST",
      body: {
        text,
        provider_mode: opts?.provider_mode || "auto",
        thread_id:     opts?.thread_id || null,
      },
      auth: true,
    },
  );
}


// ---------- v70 / Unit 76+77 — Stability + Operator Summary (phone) ----------

export type ElInsStability =
  | "stable" | "drifting_el" | "drifting_ins" | "oscillating";
export type ElInsTrend = "improving" | "declining" | "stable";

export interface ElInsThreadStabilityResponse {
  thread_id: string;
  stability: ElInsStability;
  tsi:       number;
  window:    number;
}

export function getElInsThreadStability(
  thread_id: string, window: number = 10,
): Promise<ElInsThreadStabilityResponse> {
  return request<ElInsThreadStabilityResponse>(
    "/el_ins/thread/" + encodeURIComponent(thread_id) + "/stability?window=" + encodeURIComponent(window),
    { method: "GET", auth: true },
  );
}

export interface ElInsOperatorSummaryResponse {
  recent_classification_distribution: {
    high_el:  number;
    high_ins: number;
    balanced: number;
  };
  avg_tsi:     number;
  trend:       ElInsTrend;
  sample_size: number;
}

export function getElInsOperatorSummary(
  sample_size: number = 20,
): Promise<ElInsOperatorSummaryResponse> {
  return request<ElInsOperatorSummaryResponse>(
    "/el_ins/operator/summary?sample_size=" + encodeURIComponent(sample_size),
    { method: "GET", auth: true },
  );
}


// ---------- v71 / Unit 78+79 — Export + Reasoning-Mode (phone) ----------

export type ElInsReasoningModeLabel =
  | "grounding"
  | "analysis"
  | "structured_reflection"
  | "stabilization"
  | "extended_reasoning"
  | "normal";

export interface ElInsReasoningModeResponse {
  operator_id:    string;
  reasoning_mode: ElInsReasoningModeLabel;
  el:             number | null;
  ins:            number | null;
  tsi:            number | null;
  timestamp:      number | null;
}

export function getElInsReasoningMode(): Promise<ElInsReasoningModeResponse> {
  return request<ElInsReasoningModeResponse>(
    "/el_ins/operator/reasoning_mode",
    { method: "GET", auth: true },
  );
}

export interface ElInsExportJsonRecord {
  timestamp:      string;
  thread_id:      string | null;
  el:             number;
  ins:            number;
  classification: ElInsRatioClassification;
  tsi:            number | null;
  source:         ElInsSource;
}

export interface ElInsExportJsonResponse {
  operator_id:  string;
  generated_at: string;
  records:      ElInsExportJsonRecord[];
}

export function getElInsExportJson(
  limit: number = 200,
): Promise<ElInsExportJsonResponse> {
  return request<ElInsExportJsonResponse>(
    "/el_ins/export/json?limit=" + encodeURIComponent(limit),
    { method: "GET", auth: true },
  );
}


// ---------- v72 / Units 80+81 — Anomalies + Roll-up (phone) ----------

export type ElInsAnomalyType = "high_el" | "low_ins" | "tsi_spike" | "quadrant_jump";

export interface ElInsAnomaly {
  id:          string;
  timestamp:   number;
  type:        ElInsAnomalyType;
  severity:    number;
  message:     string;
  record_id:   string;
  operator_id: string;
  thread_id:   string | null;
}

export interface ElInsAnomaliesResponse {
  operator_id: string;
  anomalies:   ElInsAnomaly[];
}

export function getElInsAnomalies(limit: number = 100): Promise<ElInsAnomaliesResponse> {
  return request<ElInsAnomaliesResponse>(
    "/el_ins/anomalies?limit=" + encodeURIComponent(limit),
    { method: "GET", auth: true },
  );
}

export type ElInsRollupWindow = "24h" | "7d" | "30d";

export interface ElInsRollupResult {
  avg_el:                       number;
  avg_ins:                      number;
  avg_tsi:                      number;
  reasoning_mode_distribution:  Record<string, number>;
  record_count:                 number;
  window_start:                 number;
  window_end:                   number;
}

export function getElInsRollup(window: ElInsRollupWindow): Promise<ElInsRollupResult> {
  return request<ElInsRollupResult>(
    "/el_ins/rollup/" + window,
    { method: "GET", auth: true },
  );
}


// ---------- v73 / Units 82+83 — Timeline + Org Timeline (phone) ----------

export type TimelineEventType = "record" | "anomaly" | "rollup" | "system";

export interface TimelineEvent {
  id:           string;
  timestamp_ms: number;
  event_type:   TimelineEventType;
  payload:      Record<string, unknown>;
  operator_id:  string;
}

export interface TimelineListResponse {
  operator_id: string;
  events:      TimelineEvent[];
}

export function getTimeline(limit: number = 200): Promise<TimelineListResponse> {
  return request<TimelineListResponse>(
    "/timeline?limit=" + encodeURIComponent(limit),
    { method: "GET", auth: true },
  );
}

export type OrgTimelineWindow = "24h" | "7d" | "30d";

export interface OrgTimelineEntry {
  timestamp_ms:    number;
  operator_id:     string;
  event_type:      TimelineEventType;
  payload_summary: Record<string, unknown>;
}

export interface OrgTimelineResponse {
  window:  OrgTimelineWindow;
  entries: OrgTimelineEntry[];
}

export function getOrgTimeline(window: OrgTimelineWindow): Promise<OrgTimelineResponse> {
  return request<OrgTimelineResponse>(
    "/org/timeline/" + window,
    { method: "GET", auth: true },
  );
}


// ===========================================================================
// Engine V1 — canonical /engine/v1/run contract (Phase-1)
//
// Hand-mirrored from the Pydantic models in app.py per the established
// no-cross-tree-sharing rule (phone uses Metro, web uses Vite, desktop
// uses Vite — no shared package). Field shapes must stay 1:1 with the
// engine; FastAPI's /openapi.json is the cross-language source of truth.
// ===========================================================================
export type EngineFlowRegime = "laminar" | "transitional" | "turbulent";

export type EnginePrimitiveType =
  | "entity"
  | "attitude"
  | "relationship"
  | "event"
  | "signal"
  | "temperature";

export interface EngineHydraulicState {
  pressure:   number;
  gradient:   number;
  flow:       number;
  resistance: number;
  timestamp:  string;
}

export interface EnginePrimitiveMetadata {
  primitive_id:   string;
  primitive_type: EnginePrimitiveType;
  timestamp:      string;
  version:        string;
  domain:         string;
  source:         string;
  parent_id:      string | null;
  // Card 20 cherry-pick: lineage + dependency graph fields.
  ancestors:      string[];
  depends_on:     string[];
  influences:     string[];
  confidence:     number;
  completeness:   number;
  reliability:    number;
}

export interface EnginePrimitive {
  metadata:        EnginePrimitiveMetadata;
  content:         Record<string, unknown>;
  hydraulic_state: EngineHydraulicState;
  // Card 20 cherry-pick: self-referential lineage. Both null / empty
  // in Phase-1 because there's no archive yet; shape locked early so
  // Phase-2 only changes values.
  origin_state:       EnginePrimitive | null;
  historical_states:  EnginePrimitive[];
}

export interface EngineOverlayResult {
  primitive_id:     string;
  reynolds_number:  number;
  flow_regime:      EngineFlowRegime;
  stability:        number;
  in_critical_zone: boolean;
  distance_to_fold: number;
  resilience:       number;
  // Card 20 cherry-pick: Godhard-curve fields.
  curve_position:   number;
  on_upper_branch:  boolean;
  sensitivity:      number;
  hysteresis:       number;
}

export interface EngineRegimeChange {
  day:    number;
  regime: EngineFlowRegime;
}

export interface EngineRegressionResult {
  primitive_id:           string;
  current_state:          EnginePrimitive;
  origin_state:           EnginePrimitive;
  path:                   EnginePrimitive[];
  reconstruction_error:   number;
  path_confidence:        number;
  deviation_from_origin:  number;
  historical_similarity:  number;
  attitude_match_score:   number;
}

export interface EngineProjectionResult {
  primitive_id:        string;
  source_state:        EnginePrimitive;
  projected_state:     EnginePrimitive;
  projection_days:     number;
  confidence:          number;
  uncertainty:         number;
  pressure_trajectory: number[];
  flow_trajectory:     number[];
  regime_changes:      EngineRegimeChange[];
}

export interface EngineDiagnostics {
  observation_id:    string;
  observer_notes:    string;
  confidence_level:  number;
  validation_status: string;
  early_warnings:    Record<string, number>;
  errors:            string[];
  // Card 20 cherry-pick: applied-interventions trace. Empty in
  // Phase-1; structured by a later card.
  interventions:     string[];
}

// Phase-2 / Phase-3 reserved placeholders. Empty by design; both
// engine and clients tolerate extra keys as the contract evolves.
export interface EngineValidationResult { [k: string]: unknown }
export interface EngineCrossRegressionResult { [k: string]: unknown }
export interface EngineBacktestResult { [k: string]: unknown }

export interface EngineResponseV1 {
  ok:               true;
  primitives:       EnginePrimitive[];
  overlays:         EngineOverlayResult[];
  regression:       EngineRegressionResult | null;
  projection:       EngineProjectionResult | null;
  diagnostics:      EngineDiagnostics;
  // Reserved — undefined or null until later cards land.
  validation?:       EngineValidationResult       | null;
  cross_regression?: EngineCrossRegressionResult  | null;
  backtest?:         EngineBacktestResult         | null;
}

export interface EnginePrimitiveInput {
  primitive_id?:   string;
  primitive_type?: EnginePrimitiveType;
  domain?:         string;
  source?:         string;
  content?:        Record<string, unknown>;
  pressure:        number;
  flow:            number;
  resistance:      number;
  gradient?:       number;
}

export interface EngineRunRequest {
  primitives:       EnginePrimitiveInput[];
  projection_days?: number;
}

export function engineV1Run(input: EngineRunRequest): Promise<EngineResponseV1> {
  return request<EngineResponseV1>("/engine/v1/run", {
    method: "POST",
    body: input,
  });
}
