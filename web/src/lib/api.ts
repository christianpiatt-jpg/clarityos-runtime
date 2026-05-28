// API client — fetch wrapper with X-Session-ID, error envelope, retry.
// Mirrors phone/lib/api.ts intent: same routes, same envelope.

import { getApiBase } from "./config";

const SESSION_KEY = "clarityos_session";
const USER_KEY = "clarityos_user";

let memorySession: string | null = readStorage(SESSION_KEY);
let memoryUser: string | null = readStorage(USER_KEY);
let memoryProfile: Profile | null = null;

function readStorage(k: string): string | null {
  try { return localStorage.getItem(k); } catch { return null; }
}
function writeStorage(k: string, v: string | null): void {
  try {
    if (v === null) localStorage.removeItem(k);
    else localStorage.setItem(k, v);
  } catch { /* noop */ }
}

// ---------- Types ----------
export type Cohort = "founder" | "founder_exception" | "terrace_1";

export interface Profile {
  user: string;
  cohort?: Cohort | null;
  operator_id?: string | null;
  tier?: string;
  billing_expires_at?: number | null;
}

export interface MeResponse {
  ok: true;
  user: string;
  session_id: string;
  cohort?: Cohort | null;
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

export interface HealthResponse {
  ok: true;
  status: string;
  version: string;
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

// ---------- Auth state ----------
export function getSession(): string | null { return memorySession; }
export function getUser(): string | null { return memoryUser; }
export function getProfile(): Profile | null { return memoryProfile; }
export function isAuthed(): boolean { return memorySession !== null; }

function setSession(sid: string, user: string) {
  memorySession = sid;
  memoryUser = user;
  writeStorage(SESSION_KEY, sid);
  writeStorage(USER_KEY, user);
}

export function clearSession(): void {
  memorySession = null;
  memoryUser = null;
  memoryProfile = null;
  writeStorage(SESSION_KEY, null);
  writeStorage(USER_KEY, null);
}

// ---------- Core request ----------
type ReqOpts = { method?: string; body?: unknown; auth?: boolean };

async function request<T = unknown>(path: string, opts: ReqOpts = {}): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    if (!memorySession) throw new ApiError("missing_session", "Not signed in", 401);
    headers["X-Session-ID"] = memorySession;
  }
  const url = getApiBase() + path;
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
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

/** Exponential-backoff retry. Retries network errors and 5xx; never 4xx. */
export async function withRetry<T>(
  fn: () => Promise<T>,
  opts: { attempts?: number; baseDelayMs?: number } = {}
): Promise<T> {
  const attempts = opts.attempts ?? 3;
  const baseDelayMs = opts.baseDelayMs ?? 500;
  let lastErr: unknown;
  for (let i = 0; i < attempts; i++) {
    try { return await fn(); }
    catch (e) {
      lastErr = e;
      if (e instanceof ApiError && e.status >= 400 && e.status < 500) throw e;
      if (i < attempts - 1) {
        await new Promise((r) => setTimeout(r, baseDelayMs * Math.pow(2, i)));
      }
    }
  }
  throw lastErr;
}

// ---------- Auth routes ----------
export async function login(username: string, password: string) {
  const data = await request<{ session_id: string; user: string; expires_in: number }>("/login", {
    method: "POST",
    body: { username, password },
    auth: false,
  });
  setSession(data.session_id, data.user);
  return data;
}

export async function logout() {
  clearSession();
}

// ---------- Account ----------
export const me = () => request<MeResponse>("/me");
export const config = () => request<ConfigResponse>("/config");

/**
 * Pull /me and cache the full profile. On 401/403 clears the local
 * session. On network/5xx leaves cached profile alone (transient blips
 * shouldn't sign the user out).
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
      clearSession();
      return null;
    }
    return memoryProfile;
  }
}

// ---------- Engines ----------
export interface MarkovResult {
  ok: true;
  engine: string;
  data: {
    score: number;
    tags: string[];
    interpretation: string;
    user: string;
  };
}

export const markov = (text: string, meta?: Record<string, unknown>) =>
  request<MarkovResult>("/markov", { method: "POST", body: { text, meta } });

export const galileo = (text: string, meta?: Record<string, unknown>) =>
  request<{ ok: true; engine: string; data: any }>("/galileo", { method: "POST", body: { text, meta } });

export const tizzy = (text: string, meta?: Record<string, unknown>) =>
  request<{ ok: true; engine: string; data: any }>("/tizzy", { method: "POST", body: { text, meta } });

export const library = (path: string, meta?: Record<string, unknown>) =>
  request<{ ok: true; engine: string; data: { path: string; bucket: string; prefix: string; size: number; content: string } }>(
    "/library",
    { method: "POST", body: { text: path, meta } }
  );

// ---------- Storage Layer v1 (vault / library / timeline) ----------
export interface UsageEnvelope {
  bytes_used: number;
  quota: number;
}

export interface ServerVaultItem {
  id: string;
  user: string;
  type: "note" | "session";
  title?: string;
  content: string;
  tags: string[];
  metadata?: Record<string, unknown>;
  created_at: number;
  updated_at?: number;
  size_bytes: number;
}

export interface ServerLibraryItem {
  id: string;
  user: string;
  title: string;
  content: string;
  tags: string[];
  metadata?: Record<string, unknown>;
  created_at: number;
  updated_at: number;
  size_bytes: number;
}

export interface ServerTimelineEvent {
  id: string;
  user: string;
  kind: string;
  summary: string;
  ref?: string | null;
  ts: number;
  data?: Record<string, unknown>;
  created_at: number;
  size_bytes: number;
}

export const vaultList = (limit = 100) =>
  request<{ ok: true; items: ServerVaultItem[]; count: number }>(`/vault/list?limit=${limit}`);

export const vaultWrite = (input: {
  title?: string;
  content: string;
  tags?: string[];
  type?: "note" | "session";
  metadata?: Record<string, unknown>;
}) =>
  request<{ ok: true; item: ServerVaultItem; usage: UsageEnvelope }>("/vault/write", {
    method: "POST",
    body: input,
  });

export const vaultUpdate = (input: {
  id: string;
  title?: string;
  content?: string;
  tags?: string[];
  type?: "note" | "session";
  metadata?: Record<string, unknown>;
}) =>
  request<{ ok: true; item: ServerVaultItem; usage: UsageEnvelope }>("/vault/update", {
    method: "POST",
    body: input,
  });

export const vaultDelete = (id: string) =>
  request<{ ok: true; id: string; usage: UsageEnvelope }>("/vault/delete", {
    method: "POST",
    body: { id },
  });

export const libraryUserList = (limit = 100) =>
  request<{ ok: true; items: ServerLibraryItem[]; count: number }>(`/library/list?limit=${limit}`);

export const libraryUserWrite = (input: {
  title: string;
  content: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
}) =>
  request<{ ok: true; item: ServerLibraryItem; usage: UsageEnvelope }>("/library/write", {
    method: "POST",
    body: input,
  });

export const libraryUserUpdate = (input: {
  id: string;
  title?: string;
  content?: string;
  tags?: string[];
  metadata?: Record<string, unknown>;
}) =>
  request<{ ok: true; item: ServerLibraryItem; usage: UsageEnvelope }>("/library/update", {
    method: "POST",
    body: input,
  });

export const timelineList = (
  filters: { kind?: string; since?: number; until?: number; limit?: number } = {},
) => {
  const params = new URLSearchParams();
  if (filters.kind) params.set("kind", filters.kind);
  if (filters.since !== undefined) params.set("since", String(filters.since));
  if (filters.until !== undefined) params.set("until", String(filters.until));
  params.set("limit", String(filters.limit ?? 100));
  return request<{ ok: true; events: ServerTimelineEvent[]; count: number }>(
    `/timeline/list?${params.toString()}`,
  );
};

// ---------- Public ----------
export const health = () => request<HealthResponse>("/health", { auth: false });

// ---------- Invites (admin) ----------
export interface InviteCreated {
  ok: true;
  invite_id: string;
  token: string;
  url: string;
  cohort: Cohort;
  price: number;
  billing_required: boolean;
  expires_at: number;
}

export const createInvite = (cohort: "founder_exception" | "terrace_1", expires_in_days?: number) =>
  request<InviteCreated>("/invite/create", {
    method: "POST",
    body: { cohort, ...(expires_in_days ? { expires_in_days } : {}) },
  });

// ---------- Backend status probe ----------
export interface BackendStatus {
  reachable: boolean;
  version?: string;
  error?: string;
  apiBase: string;
}

export async function probeBackend(): Promise<BackendStatus> {
  const apiBase = getApiBase();
  try {
    const r = await withRetry(() => health(), { attempts: 2, baseDelayMs: 400 });
    return { reachable: true, version: r.version, apiBase };
  } catch (e: any) {
    return { reachable: false, error: e?.message || String(e), apiBase };
  }
}

// ===========================================================================
// v28 — Surface + Distribution layer helpers
// ---------------------------------------------------------------------------
// Six new routes added in app.py. All deterministic dicts; UI renders without
// summarization or inference.
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

export interface MarkovEnvelopeLatest {
  ok: boolean;
  state_vector?: number[];
  predictive_vector?: number[];
  qc_envelope?: Record<string, number>;
  envelope_metrics?: Record<string, number>;
  error?: string;
}

export const markovEnvelopeLatest = (session_id: string) =>
  request<MarkovEnvelopeLatest>(
    `/markov/envelope/latest?session_id=${encodeURIComponent(session_id)}`,
  );

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

// ===========================================================================
// v29 — Hardening + Onboarding helpers
// ---------------------------------------------------------------------------
// Six new endpoints; all read-only or single-step writes. The flags response
// is what the cockpit consults to gate the v28 surfaces; onboarding is the
// first-run wizard.
// ===========================================================================
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
  raw?: Record<string, { default: boolean; override_count: number }>;
}

export interface V29OnboardingState {
  ok: true;
  user: string;
  completed: string[];
  next_step: string | null;
  done: boolean;
  steps: string[];
}

export interface V29WhatsNew {
  ok: true;
  enabled: boolean;
  entries: Array<{
    id: string;
    title: string;
    highlights: string[];
    released_at: string;
  }>;
}

export const v29Flags = () => request<V29FlagsResponse>("/v29/flags");

export const v29OnboardingState = () =>
  request<V29OnboardingState>("/v29/onboarding/state");

export const v29OnboardingComplete = (step: string) =>
  request<{ ok: true; onboarding: Record<string, number> }>(
    "/v29/onboarding/complete",
    { method: "POST", body: { step } },
  );

export const v29OnboardingSeed = () =>
  request<{ ok: true; summary: { vault: number; timeline: number; skipped: boolean } }>(
    "/v29/onboarding/seed",
    { method: "POST", body: {} },
  );

export const v29WhatsNew = () => request<V29WhatsNew>("/v29/whats_new");

// ===========================================================================
// v30 — Founding Cohort Membership + #G Credits
// ===========================================================================
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
  // v31 — billing lifecycle metadata
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

// ===========================================================================
// v31 — Billing Finalization helpers
// ===========================================================================
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

// ===========================================================================
// v32 — Public website + Waitlist pipeline
// ===========================================================================
export type V32WaitlistSource = "website" | "linkedin" | "facebook" | "manual";
export type V32WaitlistStatus = "waiting" | "contacted" | "converted" | "dropped";

export interface V32WaitlistEntry {
  id: string;
  email: string;
  name: string | null;
  source: V32WaitlistSource;
  status: V32WaitlistStatus;
  note: string | null;
  user_id: string | null;
  created_ts: number;
  updated_ts: number | null;
  contacted_ts: number | null;
  converted_ts: number | null;
}

export interface V32CohortStatus {
  ok: true;
  cohort: string;
  active_count: number;
  cap: number | null;
  remaining: number | null;
  is_full: boolean;
  waitlist_count: number;
}

/** Public — no auth required. */
export const publicCohortStatus = () =>
  request<V32CohortStatus>("/public/cohort_status", { auth: false });

/** Public — no auth required. IP-rate-limited server-side. */
export const waitlistJoin = (input: {
  email: string;
  name?: string;
  source?: V32WaitlistSource;
  note?: string;
}) =>
  request<{ ok: true; id: string; status: V32WaitlistStatus }>(
    "/waitlist/join",
    { method: "POST", body: input, auth: false },
  );

/** Founder-only — auth required. */
export const founderWaitlistList = (params: { status?: V32WaitlistStatus; limit?: number } = {}) => {
  const qp = new URLSearchParams();
  if (params.status) qp.set("status", params.status);
  if (params.limit !== undefined) qp.set("limit", String(params.limit));
  const qs = qp.toString();
  return request<{
    ok: true;
    entries: V32WaitlistEntry[];
    counts: Record<string, number>;
  }>(`/founder/waitlist${qs ? "?" + qs : ""}`);
};

/** Founder-only — auth required. */
export const founderWaitlistUpdate = (input: {
  id: string;
  status: V32WaitlistStatus;
  note?: string;
  user_id?: string;
}) =>
  request<{ ok: true; entry: V32WaitlistEntry }>(
    "/founder/waitlist/update",
    { method: "POST", body: input },
  );

// ===========================================================================
// v33 — Standardized ELINS + #cmt + Founder Console
// ===========================================================================
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
  synthesis: { top_primitive: string; top_primitive_intensity: number; domain: string | null; signal: string; trend: string; stress_score: number; relief_score: number; external_anchors?: string[] };
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
  fresh_ep_summary: Record<string, number | string>;
  passed: boolean;
  threshold: number;
  version: string;
  ts: number;
}

export interface V33CommentResult {
  ok: true;
  comment: string;
  detection: {
    attractor: string;
    domain: string | null;
    tone: string;
    primitive_intensities: Record<string, number>;
    domain_scores: Record<string, number>;
    input_word_count: number;
  };
  construction: {
    structural_reframe: string;
    domain_alignment: string;
    identity_move: string;
    stabilizing_close: string;
  };
  activation: {
    micro_thread_trigger: string;
    low_emotion: boolean;
    noun_density: number;
    char_count: number;
  };
  version: string;
  ts: number;
}

export const elinsPreview = (text: string, domain_hint?: string) =>
  request<{ ok: true; elins: V33ELINSObject }>("/elins/preview", {
    method: "POST",
    body: { text, ...(domain_hint ? { domain_hint } : {}) },
  });

export const elinsGlobal = (text: string, domain_hint?: string) =>
  request<{ ok: true; run_id: string; elins: V33ELINSObject; baseline: Record<string, number> }>(
    "/elins/global",
    { method: "POST", body: { text, ...(domain_hint ? { domain_hint } : {}) } },
  );

export const elinsQC = (elins_object: V33ELINSObject) =>
  request<{ ok: true; s_elins: V33SELINSResult }>("/elins/qc", {
    method: "POST",
    body: { elins_object },
  });

// ===========================================================================
// v34 — ELINS forecast engine
// ===========================================================================
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
    inputs: {
      intensities: Record<string, number>;
      edges: Array<{ from: string; to: string; weight: number }>;
      days: number;
    };
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

export const founderElinsForecastRun = (text: string, opts: { domain_hint?: string; days?: number } = {}) =>
  request<{ ok: true; run_id: string; elins: V33ELINSObject; baseline: Record<string, number> }>(
    "/founder/elins/forecast/run",
    {
      method: "POST",
      body: {
        text,
        ...(opts.domain_hint ? { domain_hint: opts.domain_hint } : {}),
        days: opts.days ?? 5,
      },
    },
  );

// ===========================================================================
// v35 — Regional ELINS modules + ESO
// ===========================================================================
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

export interface V35RegionalRunResponse {
  ok: true;
  run_id: string;
  region_code: V35RegionCode;
  elins: V35RegionalELINS;
  eso_present: boolean;
}

export interface V35RegionalListItem {
  region_code: V35RegionCode;
  latest:
    | null
    | {
        run_id: string;
        day: string;
        scenario_id: string;
        summary: Record<string, unknown>;
        domain_top: string | null;
        external_present: boolean;
        external_anchors: string[];
        saved_ts: number;
      };
}

export interface V35RegionalListResponse {
  ok: true;
  regions: V35RegionCode[];
  items: V35RegionalListItem[];
}

export const elinsRegionalRun = (region_code: V35RegionCode, topic_hint?: string) =>
  request<V35RegionalRunResponse>("/elins/regional/run", {
    method: "POST",
    body: { region_code, ...(topic_hint ? { topic_hint } : {}) },
  });

export const elinsRegionalList = () =>
  request<V35RegionalListResponse>("/elins/regional/list");

export const founderElinsRegionalBatch = (
  regions: V35RegionCode[],
  topic_hint?: string,
) =>
  request<{ ok: true; results: Record<string, V35RegionalELINS>; run_ids: Record<string, string> }>(
    "/founder/elins/regional/batch",
    {
      method: "POST",
      body: { regions, ...(topic_hint ? { topic_hint } : {}) },
    },
  );

// ===========================================================================
// v36 — Macro-ELINS scheduler + run log
// ===========================================================================
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

// ===========================================================================
// v37 — Cross-cluster entity graph
// ===========================================================================
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

export interface V37EntityGraphSnapshot {
  id: string;
  ts: number;
  entity_count: number;
  edge_count: number;
  version: string;
}

export interface V37EntityGraphRaw {
  entities: Record<string, {
    degree: number;
    clusters: string[];
    domains: Record<string, number>;
    ep_stats: { sum: number; count: number; mean: number };
    appearances: V37EntityAppearance[];
  }>;
  edges: Record<string, {
    a: string; b: string;
    weight: number; co_occurrences: number;
    first_ts: number; last_ts: number;
  }>;
  version: string;
  updated_ts: number;
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

export const founderEntityGraphRaw = () =>
  request<{ ok: true; graph: V37EntityGraphRaw; snapshot: V37EntityGraphSnapshot | null }>(
    "/founder/elins/entity_graph/raw",
  );

// ===========================================================================
// v38 — ELINS interactive dashboard
// ===========================================================================
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
    top_entities: Array<{
      name: string;
      degree: number;
      ep_mean: number;
      top_domains: string[];
    }>;
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

export interface V38FounderOverview {
  latest_date: string | null;
  macro_runs_count: number;
  entity_graph_snapshots: number;
  regional_coverage: Record<string, { runs: number; latest_day: string | null }>;
  scheduler_config: V36SchedulerConfig;
  version: string;
}

export const elinsDashboard = () =>
  request<{ ok: true; snapshot: V38DashboardSnapshot }>("/elins/dashboard");

export const elinsDashboardForDate = (date: string) =>
  request<{ ok: true; snapshot: V38DashboardSnapshot }>(
    `/elins/dashboard/${encodeURIComponent(date)}`,
  );

export const founderDashboardOverview = () =>
  request<{ ok: true; overview: V38FounderOverview }>(
    "/founder/elins/dashboard/overview",
  );

// ===========================================================================
// v39 — Operator state memory + continuity
// ===========================================================================
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

export interface V39ContinuitySection {
  last_topics: string[];
  preferred_domains: Array<{ name: string; weight: number }>;
  preferred_regions: Array<{ name: string; weight: number }>;
  external_signal_mode: V39SignalMode;
  history_count: number;
  g_count: number;
}

export const meOperatorState = () =>
  request<{ ok: true; state: V39OperatorState }>("/me/operator_state");

export const meOperatorStateUpdate = (patch: { external_signal_mode?: V39SignalMode }) =>
  request<{ ok: true; state: V39OperatorState }>("/me/operator_state", {
    method: "POST",
    body: patch,
  });

export const founderOperatorState = (user_id: string) =>
  request<{ ok: true; state: V39OperatorState }>(
    `/founder/operator/${encodeURIComponent(user_id)}/state`,
  );

// ===========================================================================
// v42 — Stripe billing observability
// ===========================================================================
export type V42StripeMode = "test" | "live" | "disabled";

export interface V42BillingStatus {
  mode: V42StripeMode;
  has_secret: boolean;
  has_webhook_secret: boolean;
  live_mode: boolean;
  billing_enabled: boolean;
  version: string;
}

export interface V42BillingEvent {
  ts: number;
  event_type: string;
  user_id: string | null;
  event_id: string | null;
  mode: string;
  payload_meta: Record<string, unknown>;
}

export interface V42FounderBillingStatus {
  ok: true;
  stripe: V42BillingStatus;
  live_mode: boolean;
  recent_events: V42BillingEvent[];
  last_event_ts: number | null;
  runtime_billing_mode: string;
}

export interface V42MeBilling {
  ok: true;
  status: "none" | "active" | "past_due" | "canceled";
  plan: string | null;
  renewal_ts: number | null;
  mode: V42StripeMode;
  billing_enabled: boolean;
}

export const founderBillingStatus = () =>
  request<V42FounderBillingStatus>("/founder/billing/status");

export const meBilling = () =>
  request<V42MeBilling>("/me/billing");

// ===========================================================================
// v43 — Founder analytics
// ===========================================================================
export interface V43FounderAnalyticsSummary {
  users: {
    total: number;
    active_7d: number;
    active_30d: number;
  };
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

// ===========================================================================
// v44 — Multi-model router
// ===========================================================================
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

export interface V44ProviderStatus {
  configured: boolean;
}

export interface V44RouterStatus {
  version: string;
  supported_models: V44ModelId[];
  task_defaults: Record<string, V44ModelId>;
  founder_default_model: V44ModelId | null;
  providers: Record<string, V44ProviderStatus & { path?: string | null }>;
  // v45 — on-device runtime block. Optional so older clients keep
  // working when the server hasn't been bumped yet.
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

export const founderModelsOverride = (default_model: V44ModelId | null) =>
  request<{ ok: true; default_model: V44ModelId | null; router: V44RouterStatus }>(
    "/founder/models/override",
    { method: "POST", body: { default_model } },
  );

// ===========================================================================
// v45 — Local model runtime (on-device inference)
// ===========================================================================
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

// ===========================================================================
// v46 — Memory Vault
// ===========================================================================
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
  fs_dir?: string | null;
  sqlite_path?: string | null;
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

export interface V46VaultNote {
  key: string;
  text: string;
}

export interface V46VaultEmbedding {
  key: string;
  dim: number;
}

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

export const meVaultEmbeddingsPut = (key: string, vector: number[]) =>
  request<{ ok: true; key: string; dim: number }>("/me/vault/embeddings", {
    method: "POST", body: { key, vector },
  });

export const meVaultEmbeddingsDelete = (key: string) =>
  request<{ ok: true; key: string }>("/me/vault/embeddings/delete", {
    method: "POST", body: { key },
  });

export const founderVaultUsers = () =>
  request<{ ok: true; users: { user_id: string; keys: number }[]; count: number }>(
    "/founder/vault/users",
  );

export const founderVaultKeys = (user_id: string) =>
  request<{
    ok: true; user_id: string; count: number; keys: string[];
    by_namespace: Record<string, { count: number; keys: string[] }>;
  }>(`/founder/vault/${encodeURIComponent(user_id)}/keys`);

export const founderVaultItem = (user_id: string, key: string) =>
  request<{
    ok: boolean; user_id: string; key: string; value: unknown;
    namespace?: string; error?: string;
  }>(`/founder/vault/${encodeURIComponent(user_id)}/item/${encodeURIComponent(key)}`);

// ===========================================================================
// v47/v48/v50 — Threads (persistent threaded interactions + summaries)
// ===========================================================================
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
//
// The chain shape exposed by the backend (V76RegressionChainModel).
// Field types mirror the Pydantic model: ms-epoch ints for
// timestamps, free-form key/value dict for tags.
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
  archived: boolean;
}

/**
 * v80 — POST a unified cognitive packet to
 * ``/me/regression_first/packet``. The backend wraps it as a chain
 * (seeded with the last skeleton layer marked ``unknown``) and
 * emits ``regression_chain_started`` + ``regression_chain_layer_updated``
 * timeline events.
 *
 * Throws ``ApiError`` on 401 (no session), 422 ``packet_rejected``
 * (malformed packet), or 422 ``regression_not_required`` (packet
 * valid but no chain to build).
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
 * v82 — POST `/me/regression_first/replay` to replay the original
 * packet that originated a chain as a NEW chain. The backend looks
 * the original packet up under the operator's vault partition (404
 * if no original packet exists — e.g. chain was created manually
 * via /start) and dispatches it through the same kernel + seed
 * policy as /packet, emitting the same timeline events.
 *
 * The original chain is NOT modified.
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

// ---------- Founder DM pipeline ----------
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
  seq?: number;
}

export const founderDMAdd = (input: {
  channel: V33DMChannel;
  user?: string;
  external_id?: string;
  subject?: string;
  snippet?: string;
}) =>
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

// ---------- Founder membership ops ----------
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

// ---------- v52 — Emotional Physics (Path C-compliant kernel) ----------
export interface EmotionalPhysicsLayers {
  field_curvature:       Record<string, unknown>;
  edge_pressure:         Record<string, unknown>;
  relational_primitives: Record<string, unknown>;
  external_expression:   Record<string, unknown>;
}
export interface EmotionalPhysicsResponse extends EmotionalPhysicsLayers {
  _meta: {
    model_id:    string | null;
    ts_ms:       number;
    parse_error: string | null;
  };
}
export const runEmotionalPhysics = (text: string) =>
  request<EmotionalPhysicsResponse>(
    "/me/emotional_physics/analyze",
    { method: "POST", body: { text } },
  );

// ---------- v53 — ELINS v2 (Path C view adapter) ----------
export type ElinsAttractor       = "S1" | "S2" | "S3" | "S4";
export type ElinsCollapseState   = "none" | "soft" | "hard";
export type ElinsGeographyTier   = "T1" | "T2" | "T3" | "T4" | null;

export interface ElinsV2Outputs {
  collapse_state:     ElinsCollapseState;
  attractor:          ElinsAttractor;
  state_distribution: Record<ElinsAttractor, number>;
  P0_P8:              Record<string, number>;
  geography_tier:     ElinsGeographyTier;
  timeline: {
    short_term_days: number;
    mid_term_days:   number;
    long_term_days:  number;
  };
  multiplier: number;
}
export interface ElinsV2Envelope {
  elins_version: string;
  region:        string | null;
  input?:        Record<string, unknown>;
  pipeline?:     Record<string, unknown>;
  outputs:       ElinsV2Outputs;
  meta?:         Record<string, unknown>;
}
export const runElinsV2 = (text: string, region?: string | null) =>
  request<ElinsV2Envelope>(
    "/elins/v2/run",
    {
      method: "POST",
      body: {
        region: region ?? null,
        input: { raw_text: text },
      },
    },
  );

// ---------- v61 / Unit 44 — Operator session runtime ----------
// Mirrors the FastAPI /operator/session/* surface added at v60 / Unit 41
// and extended at v61 / Unit 43 with persistence (resume flag).
// Open endpoint — no X-Session-ID required.

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
  vault_state: Record<string, unknown>;
  history:     SessionHistoryEntry[];
}

export interface SessionUiResponse {
  headline: string;
  body:     string;
  severity: "info" | "warning" | "critical";
  tags:     string[];
}

export interface SessionModelResponse {
  ok:         boolean;
  model_id:   string;
  provider:   string;
  text:       string;
  mock:       boolean;
  ts:         number;
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
      elins_block:      Record<string, unknown>;
      vault_update:     Record<string, unknown>;
      operator_view: {
        headline: string;
        details:  Record<string, unknown>;
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
  vault_update: Record<string, unknown>;
}

export interface StartSessionResponse {
  session_state: SessionState;
}

export interface StepSessionResponse {
  session_state: SessionState;
  step_result:   SessionStepResult;
}

// v65 / Unit 68 — both endpoints are now auth-gated. The body.operator_id
// field is kept for backward wire-compat but the server ignores it and
// uses the authed identity from X-Session-ID. Callers that pass a stale
// or anonymous-looking operator_id won't break anything — the server
// rewrites session_state.operator_id to the authed value on /step.

export function startSession(
  operatorId: string,
  opts: { resume?: boolean; sessionId?: string } = {},
): Promise<StartSessionResponse> {
  const body: Record<string, unknown> = { operator_id: operatorId };
  if (opts.resume) body.resume = true;
  if (opts.sessionId) body.session_id = opts.sessionId;
  return request<StartSessionResponse>(
    "/operator/session/start",
    { method: "POST", body, auth: true },
  );
}

export function stepSession(
  sessionState: SessionState,
  text: string,
  intentType: SessionIntentType = "query",
): Promise<StepSessionResponse> {
  return request<StepSessionResponse>(
    "/operator/session/step",
    {
      method: "POST",
      body: {
        session_state: sessionState,
        text,
        intent_type:   intentType,
      },
      auth: true,
    },
  );
}

// ---------- v63 / Units 47 + 48 — Read-only session history + vault inspector ----------
// Three GET endpoints, all open (auth: false), mirroring v60 posture.

export interface SessionSummary {
  session_id:  string;
  operator_id: string;
  history_len: number;
  timestamp:   string;     // most-recent step timestamp, "" if untouched
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
  vault:        Record<string, unknown> | null;
  last_updated: string;
}

// v64 / Unit 66 — these three GETs are now auth-gated. The
// ``operatorId`` argument is preserved in the signature for source
// compatibility but is ignored server-side (the authed identity
// determines whose data is returned). Callers can pass the empty
// string or any value — kept here only so existing call sites don't
// have to change.

export function listOperatorSessions(
  operatorId: string = "",
): Promise<SessionListResponse> {
  // operatorId is decorative under v66 — server uses authed identity.
  // Keeping the query string for OpenAPI / wire backward compat;
  // server ignores it.
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
  // operatorId is decorative under v66 — server uses authed identity.
  const oid = encodeURIComponent(operatorId || "self");
  return request<VaultInspectorResponse>(
    `/operator/vault/${oid}`,
    { method: "GET", auth: true },
  );
}

// ---------- v64 / Unit 67 — Operator model preferences ----------

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

// ---------- v65 / Unit 69 — Provider health dashboard ----------

export interface ProviderHealthEntry {
  available: boolean;
  error:     string | null;
}

export type ProviderHealthResponse = Record<string, ProviderHealthEntry>;

export function getProviderHealth(): Promise<ProviderHealthResponse> {
  return request<ProviderHealthResponse>(
    "/runtime/providers/health",
    { method: "GET", auth: true },
  );
}

// ---------- v66 / Unit 71 — Provider model registry ----------
//
// Mirrors GET /runtime/providers/models. The endpoint is auth-gated
// the same way as /runtime/providers/health. UI consumption is not
// wired yet — the helper exists so clients can fetch the catalogue
// (model-picker dropdowns, validation hints) without hardcoding the
// list locally.

export interface ProviderModelsResponse {
  /** Provider → list of model_id strings. */
  registry:  Record<string, string[]>;
  /** Flat allowlist; mirrors model_router.SUPPORTED_MODELS. Includes
   *  the "auto" routing sentinel which never appears in `registry`. */
  supported: string[];
}

export function getProviderModels(): Promise<ProviderModelsResponse> {
  return request<ProviderModelsResponse>(
    "/runtime/providers/models",
    { method: "GET", auth: true },
  );
}

// ---------- v68 / Unit 73 — Provider HTTP config ----------
//
// Surfaces per-provider call + health timeouts and retry budgets from
// runtime_http_config. The dashboard surface (Unit 73) joins this with
// /providers/health + /providers/models to render the full per-provider
// snapshot.

export interface ProviderConfigEntry {
  call:   number;
  health: number;
}

export interface ProviderConfigResponse {
  /** Per-provider {call, health} timeouts in seconds. */
  timeouts: Record<string, ProviderConfigEntry>;
  /** Per-provider retry budget. Currently zero across the board. */
  retries:  Record<string, number>;
  /** Defaults applied when a provider is unknown to the registry. */
  defaults: {
    call_timeout:   number;
    health_timeout: number;
    retries:        number;
  };
}

export function getProviderConfig(): Promise<ProviderConfigResponse> {
  return request<ProviderConfigResponse>(
    "/runtime/providers/config",
    { method: "GET", auth: true },
  );
}

// ---------- v69 / Unit 74 — EL/INS reasoning-stability operator ----------
//
// Mirrors the four kernel endpoints under /el_ins. Helpers + types are
// intentionally minimal — the dashboard at /operator/el_ins composes
// them with local React state. Storage shape matches the backend
// ElInsRecord TypedDict.

export type ElInsRatioClassification = "high_el" | "high_ins" | "balanced";
export type ElInsReasoningMode = "stabilize" | "expand" | "normal";
export type ElInsSource = "on_demand" | "per_turn" | "macro";
export type ElInsProviderMode = "llm" | "deterministic" | "auto";

export interface ElInsPrecedent {
  driver:    string;
  precedent: string;
  principle: string;
}

export interface ElInsAnalysis {
  el_components:        string[];
  ins_components:       string[];
  el_score:             number;
  ins_score:            number;
  ratio_classification: ElInsRatioClassification;
}

export interface ElInsRegressionChain {
  projection:      string | null;
  drivers:         string[];
  precedents:      ElInsPrecedent[];
  principle_stack: string[];
  invariant:       string | null;
}

export interface ElInsResult {
  analysis:         ElInsAnalysis;
  reasoning_mode:   ElInsReasoningMode;
  regression_chain: ElInsRegressionChain;
  stability_notes:  string | null;
}

export interface ElInsRecord {
  operator_id: string;
  thread_id:   string | null;
  timestamp:   number;
  source:      ElInsSource;
  result:      ElInsResult;
}

export interface ElInsAnalyzeRequest {
  text:           string;
  provider_mode?: ElInsProviderMode;
  thread_id?:     string | null;
}

export interface ElInsAnalyzeResponse {
  result:    ElInsResult;
  stored:    boolean;
  thread_id: string | null;
  timestamp: number;
}

export function postElInsAnalyze(
  body: ElInsAnalyzeRequest,
): Promise<ElInsAnalyzeResponse> {
  return request<ElInsAnalyzeResponse>(
    "/el_ins/analyze",
    { method: "POST", body, auth: true },
  );
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

export interface ElInsThreadResponse {
  operator_id: string;
  thread_id:   string;
  records:     ElInsRecord[];
}

export function getElInsThread(thread_id: string): Promise<ElInsThreadResponse> {
  return request<ElInsThreadResponse>(
    `/el_ins/thread/${encodeURIComponent(thread_id)}`,
    { method: "GET", auth: true },
  );
}

export interface ElInsMacroResponse {
  operator_id: string;
  since:       number | null;
  records:     ElInsRecord[];
}

export function getElInsMacro(since?: number | null): Promise<ElInsMacroResponse> {
  const qs = since !== undefined && since !== null
    ? `?since=${encodeURIComponent(since)}`
    : "";
  return request<ElInsMacroResponse>(
    `/el_ins/macro${qs}`,
    { method: "GET", auth: true },
  );
}

// ---------- v70 / Unit 76 — Thread stability + TSI ----------

export type ElInsStability =
  | "stable" | "drifting_el" | "drifting_ins" | "oscillating";

export interface ElInsThreadStabilityResponse {
  thread_id: string;
  stability: ElInsStability;
  tsi:       number;       // 0..100
  window:    number;       // actual sample size used
}

export function getElInsThreadStability(
  thread_id: string, window: number = 10,
): Promise<ElInsThreadStabilityResponse> {
  return request<ElInsThreadStabilityResponse>(
    `/el_ins/thread/${encodeURIComponent(thread_id)}/stability?window=${encodeURIComponent(window)}`,
    { method: "GET", auth: true },
  );
}

// ---------- v70 / Unit 77 — Operator-level summary + trend ----------

export type ElInsTrend = "improving" | "declining" | "stable";

export interface ElInsOperatorSummaryResponse {
  recent_classification_distribution: {
    high_el:  number;
    high_ins: number;
    balanced: number;
  };
  avg_tsi:     number;     // 0..100
  trend:       ElInsTrend;
  sample_size: number;
}

export function getElInsOperatorSummary(
  sample_size: number = 20,
): Promise<ElInsOperatorSummaryResponse> {
  return request<ElInsOperatorSummaryResponse>(
    `/el_ins/operator/summary?sample_size=${encodeURIComponent(sample_size)}`,
    { method: "GET", auth: true },
  );
}

// ---------- v71 / Unit 78 — Export endpoints ----------

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
    `/el_ins/export/json?limit=${encodeURIComponent(limit)}`,
    { method: "GET", auth: true },
  );
}

/** Fetch the PDF export as a Blob. The endpoint requires X-Session-ID
 *  auth, which a plain anchor navigation can't send — so we fetch via
 *  the same auth path as the other endpoints and let the caller
 *  trigger a download via an anchor element with the blob URL.
 *
 *  Throws ApiError on 401/etc. like the JSON helpers do. */
export async function fetchElInsExportPdfBlob(limit: number = 200): Promise<Blob> {
  if (!memorySession) throw new ApiError("missing_session", "Not signed in", 401);
  const url = `${getApiBase()}/el_ins/export/pdf?limit=${encodeURIComponent(limit)}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "GET",
      headers: { "X-Session-ID": memorySession },
    });
  } catch (e: any) {
    throw new ApiError("network_error", e?.message || "Network unreachable", 0);
  }
  if (!res.ok) {
    let data: unknown = null;
    try { data = await res.json(); } catch { /* not JSON */ }
    throw new ApiError("http_error", `HTTP ${res.status}`, res.status, data);
  }
  return await res.blob();
}

// ---------- v71 / Unit 79 — Reasoning-mode helper ----------

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


// ---------- v72 / Unit 80 — Anomalies ----------

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
    `/el_ins/anomalies?limit=${encodeURIComponent(limit)}`,
    { method: "GET", auth: true },
  );
}

export function getElInsAnomaly(id: string): Promise<ElInsAnomaly> {
  return request<ElInsAnomaly>(
    `/el_ins/anomalies/${encodeURIComponent(id)}`,
    { method: "GET", auth: true },
  );
}

// ---------- v72 / Unit 81 — Roll-up ----------

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
    `/el_ins/rollup/${window}`,
    { method: "GET", auth: true },
  );
}


// ---------- v73 / Unit 82 — Operator timeline ----------

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

export interface TimelineSinceResponse extends TimelineListResponse {
  since_ms: number;
}

export function getTimeline(limit: number = 200): Promise<TimelineListResponse> {
  return request<TimelineListResponse>(
    `/timeline?limit=${encodeURIComponent(limit)}`,
    { method: "GET", auth: true },
  );
}

export function getTimelineSince(timestamp_ms: number): Promise<TimelineSinceResponse> {
  return request<TimelineSinceResponse>(
    `/timeline/since/${encodeURIComponent(timestamp_ms)}`,
    { method: "GET", auth: true },
  );
}

export function getTimelineEvent(event_id: string): Promise<TimelineEvent> {
  return request<TimelineEvent>(
    `/timeline/${encodeURIComponent(event_id)}`,
    { method: "GET", auth: true },
  );
}

// ---------- v73 / Unit 83 — Org timeline ----------

export type OrgTimelineWindow = "24h" | "7d" | "30d";

export interface OrgTimelineEntry {
  timestamp_ms:    number;
  operator_id:     string;   // masked
  event_type:      TimelineEventType;
  payload_summary: Record<string, unknown>;
}

export interface OrgTimelineResponse {
  window:  OrgTimelineWindow;
  entries: OrgTimelineEntry[];
}

export function getOrgTimeline(window: OrgTimelineWindow): Promise<OrgTimelineResponse> {
  return request<OrgTimelineResponse>(
    `/org/timeline/${window}`,
    { method: "GET", auth: true },
  );
}

// ---------- v74 / Unit 84 — Founding 500 Subscription Gate ----------
//
// /membership/confirm binds the Beta-Terms acknowledgement after the
// WordPress signup + Stripe Checkout flow lands the operator with an
// active subscription. Distinct from /membership/activate (which
// creates a new PaymentIntent — wrong for this flow because payment
// has already happened on WordPress).

export type V74ConfirmErrorCode =
  | "subscription_inactive"
  | "cohort_full"
  | "terms_required"
  | "generic";

export interface V74MembershipConfirmResponse {
  ok: true;
  state: {
    user: string;
    membership: {
      tier?: string | null;
      status?: string | null;
      confirmed: boolean;
      confirmed_ts?: number | null;
      next_price?: number;
    };
    [k: string]: unknown;
  };
}

export function confirmMembership(): Promise<V74MembershipConfirmResponse> {
  return request<V74MembershipConfirmResponse>("/membership/confirm", {
    method: "POST",
    body: { accept_terms: true },
    auth: true,
  });
}


// ===========================================================================
// Engine V1 — canonical /engine/v1/run contract (Phase-1)
//
// Hand-mirrored from the Pydantic models in app.py per the established
// no-cross-tree-sharing rule (web uses Vite, phone uses Metro, desktop
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
    auth: true,
  });
}

// Card 22A — naming alias only. ``runEngineV1`` is the public name the
// upstream card vocabulary uses; ``EngineRequestV1`` is a type alias to
// the deployed ``EngineRunRequest`` Pydantic body. No new request shape
// is introduced; this is a compatibility shim, not a re-spec.
export type EngineRequestV1 = EngineRunRequest;

export async function runEngineV1(input: EngineRequestV1): Promise<EngineResponseV1> {
  return engineV1Run(input);
}

// Card 23 — Engine V1 Operator Debug Panel (Phase-1 minimal).
// Pure, side-effect-free introspection helper. No network, no UI,
// no session state. Returns a stable shape so dev tooling and tests
// can read Engine V1 responses without re-deriving counts/firsts.
export interface EngineV1DebugSnapshot {
  primitiveCount: number;
  overlayCount:   number;
  diagnostics:    EngineDiagnostics;
  firstPrimitive: EnginePrimitive      | null;
  firstOverlay:   EngineOverlayResult  | null;
}

export function debugEngineV1(response: EngineResponseV1): EngineV1DebugSnapshot {
  return {
    primitiveCount: response.primitives.length,
    overlayCount:   response.overlays.length,
    diagnostics:    response.diagnostics,
    firstPrimitive: response.primitives[0] ?? null,
    firstOverlay:   response.overlays[0]   ?? null,
  };
}

// Card 24 — Engine V1 input builder (Phase-1 minimal).
// Canonical, deterministic constructor for EngineRunRequest. TypeScript
// enforces shape at compile time; runtime is intentionally pass-through
// (no defensive copies, no field-level validation) so future operator
// tools, projection/regression controls, and overlays all build engine
// requests the same way without duplicating logic.
//
// Default projectionDays = 7 matches the Phase-1 example payload.
export function buildEngineRunRequest(
  primitives:     EnginePrimitiveInput[],
  projectionDays: number = 7,
): EngineRunRequest {
  return {
    primitives,
    projection_days: projectionDays,
  };
}

// Card 25 — Engine V1 output normalizer (Phase-1 minimal).
// Pure deterministic normaliser that downstream consumers (operator
// tools, future UI, regression/projection panels) call instead of
// poking at EngineResponseV1 directly. Defensive ``??`` fallbacks
// guard against malformed runtime payloads even though the type
// declares the fields non-nullable.
//
// EMPTY_ENGINE_DIAGNOSTICS is the principled default for the
// diagnostics fallback: the card spec's ``?? {}`` doesn't compile
// because EngineDiagnostics is strict-typed with 7 required fields.
// This constant supplies zero-value defaults so the fallback is
// honest, type-safe, and visible.
const EMPTY_ENGINE_DIAGNOSTICS: EngineDiagnostics = {
  observation_id:    "",
  observer_notes:    "",
  confidence_level:  0,
  validation_status: "unvalidated",
  early_warnings:    {},
  errors:            [],
  interventions:     [],
};

export interface NormalizedEngineV1 {
  primitives:     EnginePrimitive[];
  overlays:       EngineOverlayResult[];
  // Card 26A — top-level analytical outputs carried through unchanged
  // so downstream consumers (classifier, operator tools, future UI)
  // don't have to keep the raw EngineResponseV1 alongside the
  // normalized view.
  regression:     EngineRegressionResult | null;
  projection:     EngineProjectionResult | null;
  diagnostics:    EngineDiagnostics;
  primitiveCount: number;
  overlayCount:   number;
}

export function normalizeEngineResponse(
  response: EngineResponseV1,
): NormalizedEngineV1 {
  const primitives = response.primitives ?? [];
  const overlays   = response.overlays   ?? [];
  return {
    primitives,
    overlays,
    regression:     response.regression ?? null,
    projection:     response.projection ?? null,
    diagnostics:    response.diagnostics ?? EMPTY_ENGINE_DIAGNOSTICS,
    primitiveCount: primitives.length,
    overlayCount:   overlays.length,
  };
}

// Card 26A — Engine V1 classifier (Phase-1 minimal, contract-faithful).
// Pure deterministic categoriser keyed on the actual deployed
// fields: primitive_type (signal/entity/attitude/...) and overlay
// flow_regime + in_critical_zone + on_upper_branch. Regression and
// projection are top-level analytical outputs on EngineResponseV1
// (not overlay categories) and are passed through unchanged so
// downstream tools don't need to keep the raw response alongside.
export interface EngineV1Classification {
  signals:               EnginePrimitive[];
  entities:              EnginePrimitive[];
  attitudes:             EnginePrimitive[];
  relationships:         EnginePrimitive[];
  events:                EnginePrimitive[];
  temperatures:          EnginePrimitive[];

  laminarOverlays:       EngineOverlayResult[];
  transitionalOverlays:  EngineOverlayResult[];
  turbulentOverlays:     EngineOverlayResult[];
  criticalZoneOverlays:  EngineOverlayResult[];
  upperBranchOverlays:   EngineOverlayResult[];

  regression:            EngineRegressionResult | null;
  projection:            EngineProjectionResult | null;
  diagnostics:           EngineDiagnostics;
}

export function classifyEngineV1(
  normalized: NormalizedEngineV1,
): EngineV1Classification {
  return {
    signals:        normalized.primitives.filter((p) => p.metadata.primitive_type === "signal"),
    entities:       normalized.primitives.filter((p) => p.metadata.primitive_type === "entity"),
    attitudes:      normalized.primitives.filter((p) => p.metadata.primitive_type === "attitude"),
    relationships:  normalized.primitives.filter((p) => p.metadata.primitive_type === "relationship"),
    events:         normalized.primitives.filter((p) => p.metadata.primitive_type === "event"),
    temperatures:   normalized.primitives.filter((p) => p.metadata.primitive_type === "temperature"),

    laminarOverlays:      normalized.overlays.filter((o) => o.flow_regime === "laminar"),
    transitionalOverlays: normalized.overlays.filter((o) => o.flow_regime === "transitional"),
    turbulentOverlays:    normalized.overlays.filter((o) => o.flow_regime === "turbulent"),
    criticalZoneOverlays: normalized.overlays.filter((o) => o.in_critical_zone),
    upperBranchOverlays:  normalized.overlays.filter((o) => o.on_upper_branch),

    regression:  normalized.regression ?? null,
    projection:  normalized.projection ?? null,
    diagnostics: normalized.diagnostics,
  };
}

// Card 27 — Engine V1 one-shot pipeline (Phase-1 minimal).
// Pure composition of the Card 24/22A/25/26A helpers: builder → request
// → normalizer → classifier. Becomes the canonical operator-layer
// entry point for Engine V1 so callers don't have to wire the same
// four steps every time. No new semantics; no new logic.
export async function runEngineV1Pipeline(
  primitives:     EnginePrimitiveInput[],
  projectionDays?: number,
): Promise<EngineV1Classification> {
  const request    = buildEngineRunRequest(primitives, projectionDays);
  const response   = await runEngineV1(request);
  const normalized = normalizeEngineResponse(response);
  return classifyEngineV1(normalized);
}

// Card 28 — Engine V1 OperatorContext (Phase-1 minimal).
// Typed, immutable snapshot of a single engine run. Captures the
// inputs (primitives + projection window) alongside every layer of
// output (raw / normalized / classified) so Cards 29-40 operator
// tools (overlay inspectors, regression viewers, lineage tools, etc.)
// can reason about a run without re-passing primitives or recomputing
// intermediate results.
//
// projectionDays is normalised to the Card 24 builder default (7) so
// callers always see the actual window the engine ran against — not
// undefined when omitted at the call site.
export interface EngineV1OperatorContext {
  primitives:     EnginePrimitiveInput[];
  projectionDays: number;

  raw:        EngineResponseV1;
  normalized: NormalizedEngineV1;
  classified: EngineV1Classification;
}

export async function createEngineV1Context(
  primitives:     EnginePrimitiveInput[],
  projectionDays?: number,
): Promise<EngineV1OperatorContext> {
  const request    = buildEngineRunRequest(primitives, projectionDays);
  const raw        = await runEngineV1(request);
  const normalized = normalizeEngineResponse(raw);
  const classified = classifyEngineV1(normalized);
  return {
    primitives,
    projectionDays: projectionDays ?? 7,
    raw,
    normalized,
    classified,
  };
}

// Card 29 — Engine V1 multi-run context (Phase-1 minimal).
// Typed container + pure diff helpers for comparing multiple
// EngineV1OperatorContext snapshots. Foundation for Cards 30-35
// (operator diff tools, regression inspectors, multi-run overlays).
// Spec delta: card said match primitives by metadata.id; the
// deployed field is metadata.primitive_id (Card 20 cherry-pick).
export interface EngineV1MultiRunContext {
  runs: EngineV1OperatorContext[];
}

export function createMultiRunContext(
  runs: EngineV1OperatorContext[],
): EngineV1MultiRunContext {
  return { runs };
}

export function diffPrimitives(
  a: EngineV1OperatorContext,
  b: EngineV1OperatorContext,
): { added: EnginePrimitive[]; removed: EnginePrimitive[] } {
  const aIds = new Set(a.raw.primitives.map((p) => p.metadata.primitive_id));
  const bIds = new Set(b.raw.primitives.map((p) => p.metadata.primitive_id));
  const added   = b.raw.primitives.filter((p) => !aIds.has(p.metadata.primitive_id));
  const removed = a.raw.primitives.filter((p) => !bIds.has(p.metadata.primitive_id));
  return { added, removed };
}

export function diffOverlays(
  a: EngineV1OperatorContext,
  b: EngineV1OperatorContext,
): { changed: EngineOverlayResult[] } {
  const aMap = new Map(a.raw.overlays.map((o) => [o.primitive_id, o] as const));
  const changed = b.raw.overlays.filter((bo) => {
    const ao = aMap.get(bo.primitive_id);
    if (!ao) return false;  // overlay only in b counts as added, not changed
    return (
      ao.flow_regime      !== bo.flow_regime      ||
      ao.in_critical_zone !== bo.in_critical_zone ||
      ao.on_upper_branch  !== bo.on_upper_branch  ||
      ao.hysteresis       !== bo.hysteresis
    );
  });
  return { changed };
}

export function diffDiagnostics(
  a: EngineV1OperatorContext,
  b: EngineV1OperatorContext,
): Partial<EngineDiagnostics> {
  const diff: Partial<EngineDiagnostics> = {};
  const ad = a.raw.diagnostics;
  const bd = b.raw.diagnostics;
  if (ad.observation_id    !== bd.observation_id)    diff.observation_id    = bd.observation_id;
  if (ad.observer_notes    !== bd.observer_notes)    diff.observer_notes    = bd.observer_notes;
  if (ad.confidence_level  !== bd.confidence_level)  diff.confidence_level  = bd.confidence_level;
  if (ad.validation_status !== bd.validation_status) diff.validation_status = bd.validation_status;
  if (JSON.stringify(ad.early_warnings) !== JSON.stringify(bd.early_warnings)) diff.early_warnings = bd.early_warnings;
  if (JSON.stringify(ad.errors)         !== JSON.stringify(bd.errors))         diff.errors         = bd.errors;
  if (JSON.stringify(ad.interventions)  !== JSON.stringify(bd.interventions))  diff.interventions  = bd.interventions;
  return diff;
}

// Card 30 — Engine V1 unified delta object (Phase-1 minimal).
// Pure composition over the Card 29 diff helpers. Becomes the
// canonical "diff payload" higher-level operator tools (Cards 31-35:
// diff panels, regression inspectors, multi-run overlays, historical
// state tools) consume instead of calling the three helpers
// separately. No new logic, no new fields, no mutation.
export interface EngineV1Delta {
  primitives: {
    added:   EnginePrimitive[];
    removed: EnginePrimitive[];
  };
  overlays: {
    changed: EngineOverlayResult[];
  };
  diagnostics: Partial<EngineDiagnostics>;
}

export function computeEngineV1Delta(
  a: EngineV1OperatorContext,
  b: EngineV1OperatorContext,
): EngineV1Delta {
  return {
    primitives:  diffPrimitives(a, b),
    overlays:    diffOverlays(a, b),
    diagnostics: diffDiagnostics(a, b),
  };
}

// Card 31 — Primitive lineage extractor (Phase-1 minimal).
// Pure deterministic helper: given a multi-run context and a
// primitive id, return per-run presence + overlay of that primitive.
// Foundation for Cards 32-34 (lineage diffing, visualization,
// lineage-based operator tools).
//
// Spec deviation (implementation detail only): the card spec finds
// primitives by concatenating the 6 classified arrays. We look them
// up directly on ctx.normalized.primitives (the unpartitioned full
// set) — equivalent by construction since classified is a partition
// of normalized, simpler to read, and future-proof if a new
// primitive_type enum value is ever added before the classifier
// learns about it.
export interface EngineV1PrimitiveLineage {
  primitive_id: string;
  runs: Array<{
    index:     number;
    primitive: EnginePrimitive     | null;
    overlay:   EngineOverlayResult | null;
  }>;
}

export function extractPrimitiveLineage(
  multi:        EngineV1MultiRunContext,
  primitive_id: string,
): EngineV1PrimitiveLineage {
  return {
    primitive_id,
    runs: multi.runs.map((ctx, index) => ({
      index,
      primitive: ctx.normalized.primitives.find(
        (p) => p.metadata.primitive_id === primitive_id,
      ) ?? null,
      overlay: ctx.normalized.overlays.find(
        (o) => o.primitive_id === primitive_id,
      ) ?? null,
    })),
  };
}

// Card 32 — Primitive lineage diff (Phase-1 minimal).
// Pure deterministic helper that compares pairwise-adjacent runs in
// a lineage to surface: when the primitive appears / disappears, when
// its metadata changed, when its hydraulic state changed, and when
// its overlay changed. JSON.stringify equality is used for shape
// comparison — deterministic for the deployed Engine V1 field types.
export interface EngineV1PrimitiveLineageDiff {
  primitive_id: string;

  appearance: {
    added:   number[];
    removed: number[];
  };

  metadataChanges: Array<{
    from:      EnginePrimitive | null;
    to:        EnginePrimitive | null;
    indexFrom: number;
    indexTo:   number;
  }>;

  hydraulicChanges: Array<{
    from:      EnginePrimitive | null;
    to:        EnginePrimitive | null;
    indexFrom: number;
    indexTo:   number;
  }>;

  overlayChanges: Array<{
    from:      EngineOverlayResult | null;
    to:        EngineOverlayResult | null;
    indexFrom: number;
    indexTo:   number;
  }>;
}

export function diffPrimitiveLineage(
  lineage: EngineV1PrimitiveLineage,
): EngineV1PrimitiveLineageDiff {
  const { primitive_id, runs } = lineage;

  const appearance: EngineV1PrimitiveLineageDiff["appearance"] = {
    added:   [],
    removed: [],
  };
  const metadataChanges:  EngineV1PrimitiveLineageDiff["metadataChanges"]  = [];
  const hydraulicChanges: EngineV1PrimitiveLineageDiff["hydraulicChanges"] = [];
  const overlayChanges:   EngineV1PrimitiveLineageDiff["overlayChanges"]   = [];

  for (let i = 0; i < runs.length - 1; i++) {
    const a = runs[i];
    const b = runs[i + 1];

    // Appearance / disappearance.
    if (a.primitive === null && b.primitive !== null) appearance.added.push(b.index);
    if (a.primitive !== null && b.primitive === null) appearance.removed.push(b.index);

    // Metadata + hydraulic — only when the primitive is present on both sides.
    if (a.primitive && b.primitive) {
      if (JSON.stringify(a.primitive.metadata) !== JSON.stringify(b.primitive.metadata)) {
        metadataChanges.push({
          from: a.primitive, to: b.primitive,
          indexFrom: a.index, indexTo: b.index,
        });
      }
      if (JSON.stringify(a.primitive.hydraulic_state) !== JSON.stringify(b.primitive.hydraulic_state)) {
        hydraulicChanges.push({
          from: a.primitive, to: b.primitive,
          indexFrom: a.index, indexTo: b.index,
        });
      }
    }

    // Overlay change (covers null↔non-null transitions too).
    if (a.overlay || b.overlay) {
      if (JSON.stringify(a.overlay) !== JSON.stringify(b.overlay)) {
        overlayChanges.push({
          from: a.overlay, to: b.overlay,
          indexFrom: a.index, indexTo: b.index,
        });
      }
    }
  }

  return { primitive_id, appearance, metadataChanges, hydraulicChanges, overlayChanges };
}

// Card 33 — Primitive lineage overlay (Phase-1 minimal).
// Pure composition: pairs the Card 31 raw lineage with the Card 32
// diff into a single operator-layer artifact. Becomes the canonical
// "operator-ready" lineage payload for Cards 34-36 (lineage-based
// regression tools, hydraulic evolution analysis, primitive-centric
// debugging). No new logic, no inference.
export interface EngineV1PrimitiveLineageOverlay {
  primitive_id: string;
  lineage:      EngineV1PrimitiveLineage;
  diff:         EngineV1PrimitiveLineageDiff;
}

export function buildPrimitiveLineageOverlay(
  lineage: EngineV1PrimitiveLineage,
): EngineV1PrimitiveLineageOverlay {
  return {
    primitive_id: lineage.primitive_id,
    lineage,
    diff:         diffPrimitiveLineage(lineage),
  };
}
