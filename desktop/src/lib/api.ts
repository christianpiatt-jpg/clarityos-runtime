// ClarityOS desktop — API client.
//
// Same contract as web/src/lib/api.ts (v48 + v50). The desktop
// renderer talks directly to the Cloud Run backend over HTTPS via
// fetch() — same X-Session-ID auth, same JSON envelope, same routes.
//
// No localStorage on Windows file:// in some packaged Electron
// configurations, so session persistence happens in-memory + via the
// optional ``CLARITYOS_DESKTOP_SESSION`` env hook for now. A future
// pass can swap this for an Electron `app.getPath('userData')`
// JSON file via IPC.

const STORAGE_AVAILABLE = (() => {
  try {
    const k = "__clarityos_probe__";
    window.localStorage.setItem(k, "1");
    window.localStorage.removeItem(k);
    return true;
  } catch {
    return false;
  }
})();

const SESSION_KEY = "clarityos_session";
const USER_KEY = "clarityos_user";
// v51 — persist the last selected thread id so relaunching the desktop
// client resumes where the user left off (instead of always defaulting
// to the auto-created MSJ_OPPOSITION). Scoped per project.
const LAST_THREAD_KEY_PREFIX = "clarityos_desktop_last_thread:";

let memorySession: string | null = readStorage(SESSION_KEY);
let memoryUser: string | null = readStorage(USER_KEY);

function readStorage(k: string): string | null {
  if (!STORAGE_AVAILABLE) return null;
  try { return window.localStorage.getItem(k); } catch { return null; }
}
function writeStorage(k: string, v: string | null): void {
  if (!STORAGE_AVAILABLE) return;
  try {
    if (v === null) window.localStorage.removeItem(k);
    else window.localStorage.setItem(k, v);
  } catch { /* noop */ }
}

// ---------- Configuration ----------
const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ||
  "https://clarity-engine-PLACEHOLDER.run.app";

export function getApiBase(): string {
  return API_BASE;
}

// ---------- Error ----------
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
  writeStorage(SESSION_KEY, null);
  writeStorage(USER_KEY, null);
}

// v51 — last-active thread persistence. Scoped per project so each
// project remembers its own selection. Best-effort: localStorage
// failures (sandboxed Electron, etc.) silently no-op via writeStorage.
export function getLastActiveThreadId(project_id: string): string | null {
  if (!project_id) return null;
  return readStorage(LAST_THREAD_KEY_PREFIX + project_id);
}

export function setLastActiveThreadId(
  project_id: string, thread_id: string | null,
): void {
  if (!project_id) return;
  writeStorage(LAST_THREAD_KEY_PREFIX + project_id, thread_id);
}

// ---------- Core request ----------
type ReqOpts = { method?: string; body?: unknown; auth?: boolean };

async function request<T = unknown>(path: string, opts: ReqOpts = {}): Promise<T> {
  const { method = "GET", body, auth = true } = opts;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    if (!memorySession) {
      throw new ApiError("missing_session", "Not signed in", 401);
    }
    headers["X-Session-ID"] = memorySession;
  }
  const url = API_BASE + path;
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

// ---------- Auth routes ----------
export async function login(username: string, password: string) {
  const data = await request<{ session_id: string; user: string; expires_in: number }>(
    "/login",
    { method: "POST", body: { username, password }, auth: false },
  );
  setSession(data.session_id, data.user);
  return data;
}

export async function logout() {
  clearSession();
}

// ---------- /me probe (used by the auth screen on launch) ----------
export interface MeResponse {
  ok: true;
  user: string;
  session_id: string;
  cohort?: string | null;
}
export const me = () => request<MeResponse>("/me");

// ---------- v51 — Project layer (single-project hardwiring for now) ----------
//
// Single source of truth for the active project in the v51 desktop
// phase. The bootstrap flow in ChatWindow.tsx ensures the project
// with this id exists at launch (creating it via POST /me/projects
// if absent), then filters threads + tags messages with it.
// No multi-project UI yet — this is the only project the desktop
// client knows about.
export const ACTIVE_PROJECT_ID = "VA_LITIGATION" as const;

// Body for POST /me/projects when the desktop client auto-creates
// the litigation workspace on first launch. Field shape matches
// V51CreateProjectRequest on the backend exactly.
export const ACTIVE_PROJECT_BOOTSTRAP = {
  project_id:    ACTIVE_PROJECT_ID,
  name:          "VA Litigation",
  description:   "Workspace for drafting MSJ Opposition and related filings",
  default_model: "claude",
  tags:          ["legal", "va", "litigation"],
} as const;

// Title of the auto-created starter thread inside the litigation
// workspace. Used by ChatWindow's STEP 5 bootstrap.
export const ACTIVE_PROJECT_DEFAULT_THREAD_TITLE = "MSJ_OPPOSITION" as const;

export interface ProjectMeta {
  project_id:     string;
  name:           string;
  description:    string;
  default_model:  string | null;
  allowed_models: string[] | null;
  tags:           string[];
  created_at:     number;
  updated_at:     number;
  summary:        string | null;
  summary_ts_ms:  number | null;
  thread_count:   number;
}

export interface CreateProjectRequest {
  project_id:      string;
  name:            string;
  description?:    string;
  default_model?:  string | null;
  // ``readonly`` accepted so callers can pass in an ``as const`` body
  // (matches ACTIVE_PROJECT_BOOTSTRAP) without a manual mutable copy.
  allowed_models?: readonly string[] | null;
  tags?:           readonly string[];
}

/** v51 — list every project the caller has. Newest-first by updated_at. */
export async function listProjects(): Promise<ProjectMeta[]> {
  const r = await request<{ projects: ProjectMeta[] }>("/me/projects");
  return r.projects;
}

/** v51 — create a project. 400 on duplicate or bad project_id format. */
export async function createProject(
  payload: CreateProjectRequest,
): Promise<ProjectMeta> {
  return request<ProjectMeta>("/me/projects", {
    method: "POST",
    body: payload,
  });
}

// ---------- Threads (v47/v48/v50) ----------
export interface ThreadMeta {
  thread_id: string;
  title: string | null;
  created_at: number;
  updated_at: number;
  message_count: number;
  archived: boolean;
  summary: string | null;
  summary_ts_ms: number | null;
  // v51 — project membership. ``null`` for legacy threads not tied to
  // any project. Filtering by project_id is server-side via the
  // ``GET /me/threads?project_id=X`` query.
  project_id: string | null;
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

/**
 * v47 + v51 — list threads. When ``project_id`` is supplied, the
 * server filters to threads whose ``ThreadMeta.project_id`` matches.
 * Threads without any project_id are excluded by a project filter.
 */
export async function listThreads(
  project_id?: string | null,
): Promise<ThreadMeta[]> {
  const path = project_id
    ? `/me/threads?project_id=${encodeURIComponent(project_id)}`
    : "/me/threads";
  const r = await request<{ threads: ThreadMeta[] }>(path);
  return r.threads;
}

/**
 * v47 + v51 — create a thread. When ``project_id`` is supplied, the
 * new thread is tagged with that project and added to the project's
 * threads index in one round-trip. The project must already exist
 * (404 otherwise).
 */
export async function createThread(
  title?: string | null,
  project_id?: string | null,
): Promise<ThreadMeta> {
  const body: { title: string | null; project_id?: string } = {
    title: title ?? null,
  };
  if (project_id) body.project_id = project_id;
  return request<ThreadMeta>("/me/threads", {
    method: "POST",
    body,
  });
}

export async function getThread(thread_id: string): Promise<ThreadDetail> {
  return request<ThreadDetail>(
    `/me/threads/${encodeURIComponent(thread_id)}`,
  );
}

/**
 * v47 + v51 — post a user turn into ``thread_id`` and dispatch the
 * assistant reply through the kernel.
 *
 * Body field name is ``content`` per v47 (NOT ``text`` — earlier
 * drafts of the v51 spec used the wrong field; the backend accepts
 * ``content`` only).
 *
 * When ``project_id`` is supplied, the server validates that the
 * thread belongs to that project (400 on mismatch) and routes the
 * assistant call through the project's ``default_model`` /
 * ``allowed_models``.
 */
export async function postThreadMessage(
  thread_id: string, content: string,
  project_id?: string | null,
): Promise<ThreadMessageResult> {
  const body: { content: string; project_id?: string } = { content };
  if (project_id) body.project_id = project_id;
  return request<ThreadMessageResult>(
    `/me/threads/${encodeURIComponent(thread_id)}/message`,
    { method: "POST", body },
  );
}

export async function renameThread(
  thread_id: string, title: string,
): Promise<ThreadMeta> {
  return request<ThreadMeta>(
    `/me/threads/${encodeURIComponent(thread_id)}/rename`,
    { method: "POST", body: { title } },
  );
}

export async function deleteThread(thread_id: string): Promise<void> {
  await request<{ ok: true; thread_id: string }>(
    `/me/threads/${encodeURIComponent(thread_id)}/delete`,
    { method: "POST", body: {} },
  );
}

export async function summarizeThread(
  thread_id: string, force?: boolean,
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
 * ``/me/regression_first/packet``. Mirrors the web/phone helpers
 * exactly: backend persists the chain (seeded with one ``unknown``
 * layer) and emits ``regression_chain_started`` +
 * ``regression_chain_layer_updated`` events.
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
 * v82 — POST `/me/regression_first/replay`. Mirrors the web/phone
 * helpers. Replays the original packet that drove the chain as a
 * NEW chain.
 */
export async function replayRegressionFirstChain(
  chain_id: string,
): Promise<RegressionFirstChain> {
  return request<RegressionFirstChain>(
    "/me/regression_first/replay",
    { method: "POST", body: { chain_id } },
  );
}

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
export async function runEmotionalPhysics(
  text: string,
): Promise<EmotionalPhysicsResponse> {
  return request<EmotionalPhysicsResponse>(
    "/me/emotional_physics/analyze",
    { method: "POST", body: { text } },
  );
}

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
export async function runElinsV2(
  text: string,
  region?: string | null,
): Promise<ElinsV2Envelope> {
  return request<ElinsV2Envelope>(
    "/elins/v2/run",
    {
      method: "POST",
      body: {
        region: region ?? null,
        input: { raw_text: text },
      },
    },
  );
}

// ---------- v62 / Unit 45 — Operator session runtime (desktop mirror) ----------
// Same contract as web/phone. Types duplicated by design — desktop
// uses Vite, no shared package between trees. Server endpoint is open
// (no X-Session-ID) so we pass auth: false.

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

// v65 / Unit 68 — auth-gated. Server uses authed identity from
// X-Session-ID; body operator_id retained for wire-compat only.

export function startSession(
  operatorId: string,
  opts: { resume?: boolean; sessionId?: string } = {},
): Promise<StartSessionResponse> {
  const body: Record<string, unknown> = { operator_id: operatorId };
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

// ---------- v63 / Units 47 + 48 — Read-only history + vault inspector ----------
// Types duplicated from web/phone per no-cross-tree-sharing rule.

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
  vault:        Record<string, unknown> | null;
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

// ---------- v64 / Unit 67 — Operator model preferences (desktop) ----------

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

// ---------- /health (desktop) ----------
//
// v71 / Unit 78 — Added so the EL/INS export shell can surface the
// running backend version in its footer. Unauth — same contract as
// web's `health` helper.

export interface HealthResponse {
  ok:      true;
  status:  string;
  version: string;
}

export function health(): Promise<HealthResponse> {
  return request<HealthResponse>(
    "/health",
    { method: "GET", auth: false },
  );
}


// ---------- v65 / Unit 69 — Provider health dashboard (desktop) ----------

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

// ---------- v68 / Unit 72 — Provider model registry (desktop) ----------
//
// Mirror of web/src/lib/api.ts. Backend lives at /runtime/providers/models
// (added v67/Unit 71). Returns the structured MODEL_REGISTRY + the flat
// SUPPORTED_MODELS allowlist with the "auto" routing sentinel appended.

export interface ProviderModelsResponse {
  /** Provider → list of model_id strings (no "auto"). */
  registry:  Record<string, string[]>;
  /** Flat allowlist; mirrors model_router.SUPPORTED_MODELS, includes
   *  the "auto" routing sentinel. */
  supported: string[];
}

export function getProviderModels(): Promise<ProviderModelsResponse> {
  return request<ProviderModelsResponse>(
    "/runtime/providers/models",
    { method: "GET", auth: true },
  );
}

// ---------- v68 / Unit 73 — Provider HTTP config (desktop) ----------
//
// Surfaces per-provider call + health timeouts and retry budgets from
// runtime_http_config. Backend lives at /runtime/providers/config (new
// in this pass — see ProviderDashboard).

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

// ---------- v70 / Unit 76 — Thread stability + TSI (desktop) ----------

export type ElInsStability =
  | "stable" | "drifting_el" | "drifting_ins" | "oscillating";

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
    `/el_ins/thread/${encodeURIComponent(thread_id)}/stability?window=${encodeURIComponent(window)}`,
    { method: "GET", auth: true },
  );
}

// ---------- v70 / Unit 77 — Operator summary (desktop) ----------

export type ElInsTrend = "improving" | "declining" | "stable";

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
    `/el_ins/operator/summary?sample_size=${encodeURIComponent(sample_size)}`,
    { method: "GET", auth: true },
  );
}

// ---------- v71 / Unit 78 — Export (desktop) ----------

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

export async function fetchElInsExportPdfBlob(limit: number = 200): Promise<Blob> {
  if (!memorySession) throw new ApiError("missing_session", "Not signed in", 401);
  const url = `${API_BASE}/el_ins/export/pdf?limit=${encodeURIComponent(limit)}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method: "GET",
      headers: { "X-Session-ID": memorySession },
    });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Network unreachable";
    throw new ApiError("network_error", msg, 0);
  }
  if (!res.ok) {
    let data: unknown = null;
    try { data = await res.json(); } catch { /* not JSON */ }
    throw new ApiError("http_error", `HTTP ${res.status}`, res.status, data);
  }
  return await res.blob();
}

// ---------- v71 / Unit 79 — Reasoning-mode (desktop) ----------

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


// ---------- v72 / Unit 80 — Anomalies (desktop) ----------

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

// ---------- v72 / Unit 81 — Roll-up (desktop) ----------

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


// ---------- v73 / Unit 82 — Operator timeline (desktop) ----------

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
    `/timeline?limit=${encodeURIComponent(limit)}`,
    { method: "GET", auth: true },
  );
}

// ---------- v73 / Unit 83 — Org timeline (desktop) ----------

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


// ===========================================================================
// Engine V1 — canonical /engine/v1/run contract (Phase-1)
//
// Hand-mirrored from the Pydantic models in app.py per the established
// no-cross-tree-sharing rule (desktop uses Vite, web uses Vite, phone
// uses Metro — no shared package). Field shapes must stay 1:1 with the
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

// Card 34 — Multi-primitive lineage map (Phase-1 minimal).
// Pure deterministic helper: enumerate every primitive_id that
// appears in any run of a multi-run context, then build the lineage
// + diff + overlay for each. Foundation for Cards 35-37 (system-level
// hydraulic evolution tools, multi-primitive regression inspectors,
// system-wide change utilities).
//
// Spec deviation (same approved simplification as Card 31): the card
// spec enumerates primitive ids via the 6-way classified concat. We
// use ctx.normalized.primitives — equivalent by construction
// (classified is a partition of normalized) and future-proof if a
// new primitive_type enum value lands before the classifier learns
// about it. ID sort is default string-lexicographic for stable
// deterministic ordering.
export interface EngineV1LineageMap {
  primitive_ids: string[];
  lineages:      Record<string, EngineV1PrimitiveLineage>;
  diffs:         Record<string, EngineV1PrimitiveLineageDiff>;
  overlays:      Record<string, EngineV1PrimitiveLineageOverlay>;
}

export function buildLineageMap(
  multi: EngineV1MultiRunContext,
): EngineV1LineageMap {
  const primitive_ids = Array.from(
    new Set(
      multi.runs.flatMap((ctx) =>
        ctx.normalized.primitives.map((p) => p.metadata.primitive_id),
      ),
    ),
  ).sort();

  const lineages: Record<string, EngineV1PrimitiveLineage>        = {};
  const diffs:    Record<string, EngineV1PrimitiveLineageDiff>    = {};
  const overlays: Record<string, EngineV1PrimitiveLineageOverlay> = {};

  for (const id of primitive_ids) {
    const lineage = extractPrimitiveLineage(multi, id);
    lineages[id] = lineage;
    diffs[id]    = diffPrimitiveLineage(lineage);
    overlays[id] = buildPrimitiveLineageOverlay(lineage);
  }

  return { primitive_ids, lineages, diffs, overlays };
}

// Card 35 — Hydraulic evolution map (Phase-1 minimal).
// First system-level hydraulic diagnostic. Given a lineage map (Card
// 34), captures per-primitive hydraulic state across runs and rolls
// up per-run system-wide regime / critical-zone / upper-branch
// counts. Foundation for Cards 36-37 (system-level overlays + flow-
// regime regression inspectors).
//
// Spec adjustment (documented in source): the card spec types
// hydraulic_state as ``any | null``. Replaced with the deployed
// EngineHydraulicState type — same shape at runtime, full TS
// inference downstream.
export interface EngineV1HydraulicEvolutionMap {
  primitive_ids: string[];

  perPrimitive: Record<string, {
    primitive_id: string;
    runs: Array<{
      index:           number;
      hydraulic_state: EngineHydraulicState | null;
      overlay:         EngineOverlayResult  | null;
    }>;
  }>;

  perRun: Array<{
    index:         number;
    laminar:       number;
    transitional:  number;
    turbulent:     number;
    critical_zone: number;
    upper_branch:  number;
  }>;
}

export function buildHydraulicEvolutionMap(
  lineageMap: EngineV1LineageMap,
): EngineV1HydraulicEvolutionMap {
  const { primitive_ids, lineages } = lineageMap;

  const perPrimitive: EngineV1HydraulicEvolutionMap["perPrimitive"] = {};
  for (const id of primitive_ids) {
    const lineage = lineages[id];
    perPrimitive[id] = {
      primitive_id: id,
      runs: lineage.runs.map((r) => ({
        index:           r.index,
        hydraulic_state: r.primitive ? r.primitive.hydraulic_state : null,
        overlay:         r.overlay,
      })),
    };
  }

  // Card 31 lineages always cover every run in the source multi-run
  // context, so the first primitive's run count is the system-wide
  // run count. Empty primitive_ids → runCount = 0 → perRun = [].
  const runCount = primitive_ids.length > 0
    ? (lineages[primitive_ids[0]]?.runs.length ?? 0)
    : 0;

  const perRun: EngineV1HydraulicEvolutionMap["perRun"] = [];
  for (let i = 0; i < runCount; i++) {
    let laminar       = 0;
    let transitional  = 0;
    let turbulent     = 0;
    let critical_zone = 0;
    let upper_branch  = 0;
    for (const id of primitive_ids) {
      const overlay = perPrimitive[id].runs[i].overlay;
      if (!overlay) continue;
      if (overlay.flow_regime === "laminar")      laminar++;
      if (overlay.flow_regime === "transitional") transitional++;
      if (overlay.flow_regime === "turbulent")    turbulent++;
      if (overlay.in_critical_zone)               critical_zone++;
      if (overlay.on_upper_branch)                upper_branch++;
    }
    perRun.push({ index: i, laminar, transitional, turbulent, critical_zone, upper_branch });
  }

  return { primitive_ids, perPrimitive, perRun };
}

// Card 36 — System-level Engine V1 overlay (Phase-1 minimal).
// Top-level operator artifact: pure composition of the Card 34
// lineage map and the Card 35 hydraulic evolution map. Becomes the
// canonical "show me the whole system evolution" structure for
// Cards 37-40 (system-level regression tools, evolution inspectors,
// operator-surface integration).
export interface EngineV1SystemOverlay {
  primitive_ids:      string[];
  lineageMap:         EngineV1LineageMap;
  hydraulicEvolution: EngineV1HydraulicEvolutionMap;
}

export function buildSystemOverlay(
  multi: EngineV1MultiRunContext,
): EngineV1SystemOverlay {
  const lineageMap         = buildLineageMap(multi);
  const hydraulicEvolution = buildHydraulicEvolutionMap(lineageMap);
  return {
    primitive_ids: lineageMap.primitive_ids,
    lineageMap,
    hydraulicEvolution,
  };
}

// Card 37 — System-level regression diff (Phase-1 minimal).
// Given a system overlay and two run indices, summarises what changed
// between them: which primitives were added / removed / changed
// (changed = any non-empty Card 32 diff entry on the matching index
// pair) and how the system-wide hydraulic regime counts shifted.
// Foundation for Cards 38-40 (operator console integration, phone
// parity, multi-run evolution panels).
//
// Hardening (documented adjustments beyond the literal card spec):
//   1. Upfront RangeError on out-of-bounds indices — the card spec
//      reads perRun[badIndex].laminar which throws an opaque
//      TypeError instead of a clear contract violation.
//   2. Non-adjacent indices are accepted but `changed` is only
//      populated for ADJACENT pairs (toIndex === fromIndex + 1)
//      because Card 32 only records pairwise-adjacent diffs. For
//      non-adjacent comparisons, hydraulic deltas + added/removed
//      are still correct; `changed` returns []. Phase-2 can expand
//      the analytic to span-comparisons when the need lands.
export interface EngineV1SystemRegressionDiff {
  fromIndex: number;
  toIndex:   number;

  primitiveChanges: {
    added:   string[];
    removed: string[];
    changed: string[];
  };

  hydraulic: {
    laminarDelta:       number;
    transitionalDelta:  number;
    turbulentDelta:     number;
    criticalZoneDelta:  number;
    upperBranchDelta:   number;
  };
}

export function computeSystemRegressionDiff(
  overlay:   EngineV1SystemOverlay,
  fromIndex: number,
  toIndex:   number,
): EngineV1SystemRegressionDiff {
  const { primitive_ids, lineageMap, hydraulicEvolution } = overlay;
  const runCount = hydraulicEvolution.perRun.length;

  if (
    !Number.isInteger(fromIndex) || fromIndex < 0 || fromIndex >= runCount ||
    !Number.isInteger(toIndex)   || toIndex   < 0 || toIndex   >= runCount
  ) {
    throw new RangeError(
      `computeSystemRegressionDiff: indices out of range — fromIndex=${fromIndex}, ` +
      `toIndex=${toIndex}, runCount=${runCount}`,
    );
  }

  // Primitive-level: which ids gained / lost a primitive between the two runs.
  const fromPresent = new Set(
    primitive_ids.filter((id) => lineageMap.lineages[id].runs[fromIndex].primitive !== null),
  );
  const toPresent = new Set(
    primitive_ids.filter((id) => lineageMap.lineages[id].runs[toIndex].primitive !== null),
  );
  const added   = Array.from(toPresent).filter((id) => !fromPresent.has(id));
  const removed = Array.from(fromPresent).filter((id) => !toPresent.has(id));

  // `changed` — primitives with any Card 32 diff entry exactly matching
  // (fromIndex → toIndex). Card 32 only records adjacent pairs, so this
  // populates only when toIndex === fromIndex + 1.
  const changed = primitive_ids.filter((id) => {
    const diff = lineageMap.diffs[id];
    return (
      diff.metadataChanges.some((d)  => d.indexFrom === fromIndex && d.indexTo === toIndex) ||
      diff.hydraulicChanges.some((d) => d.indexFrom === fromIndex && d.indexTo === toIndex) ||
      diff.overlayChanges.some((d)   => d.indexFrom === fromIndex && d.indexTo === toIndex)
    );
  });

  // System-wide hydraulic regime deltas. Direct subtraction; positive
  // means the count grew, negative means it shrank.
  const fromRun = hydraulicEvolution.perRun[fromIndex];
  const toRun   = hydraulicEvolution.perRun[toIndex];
  const hydraulic = {
    laminarDelta:       toRun.laminar       - fromRun.laminar,
    transitionalDelta:  toRun.transitional  - fromRun.transitional,
    turbulentDelta:     toRun.turbulent     - fromRun.turbulent,
    criticalZoneDelta:  toRun.critical_zone - fromRun.critical_zone,
    upperBranchDelta:   toRun.upper_branch  - fromRun.upper_branch,
  };

  return {
    fromIndex,
    toIndex,
    primitiveChanges: { added, removed, changed },
    hydraulic,
  };
}
