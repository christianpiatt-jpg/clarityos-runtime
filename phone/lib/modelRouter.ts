// Model router — dispatches a query to the chosen model and returns raw
// text. v1 runs in STUB mode: no network, no API keys, deterministic
// mock replies. Real implementations slot into the per-model functions
// without changing the public contract.
//
// Card 19.1: ``selectModel`` (below) is an additive wrapper over the
// new backend /model/route endpoint. It returns a *selection* result
// (which model_id + why), not a completion. The mock completion path
// (``routeModelRequest``, ``sendTo*``, ``RouterResult``) is preserved
// because chat.tsx + ingest.tsx still depend on ``r.raw`` for their
// langbridg pipeline. The two surfaces will be reconciled in a later
// card once a real backend completion endpoint exists.

import { request } from "./api";
import { CLOUD_ROUTES } from "./cloud/config";

export interface ModelSelectionResult {
  model: string;
  reason: string;
  operator: boolean;
}

interface ModelRouteResponse extends ModelSelectionResult {
  ok: true;
}

/**
 * Call the backend /model/route adapter (Card 19) to resolve which
 * model_id to use for a given intent. Returns the canonical backend
 * model_id (e.g. ``"openai:gpt-4o"``), the precedence reason
 * (``"override" | "founder_default" | "user_preference" | "task_default" | "fallback"``),
 * and the Card 18 operator flag.
 *
 * Throws ``ApiError`` (from lib/api) on auth / network / 4xx / 5xx.
 * No callsites yet — exposed for future integration.
 */
export async function selectModel(
  intent: string,
  context: Record<string, unknown> = {},
  override?: string,
): Promise<ModelSelectionResult> {
  const res = await request<ModelRouteResponse>(CLOUD_ROUTES.modelProxy, {
    method: "POST",
    body: { intent, context, ...(override ? { override } : {}) },
  });
  return {
    model: res.model,
    reason: res.reason,
    operator: res.operator,
  };
}

/**
 * Card 19.3: probe result enriched with the simplified ``ModelId``
 * the backend's canonical id maps to (or ``null`` when no mapping
 * exists — surfaces backend additions that the phone hasn't taught
 * itself about yet).
 */
export interface ProbedModelSelection extends ModelSelectionResult {
  simplifiedModel: ModelId | null;
}

/**
 * Card 19.2: non-throwing observability probe over ``selectModel``.
 * Returns ``null`` on any failure (no session, network, 4xx/5xx). Use
 * fire-and-forget at callsites so the user-facing path is never
 * delayed or destabilised by the probe.
 *
 * Card 19.3: enriches the response with ``simplifiedModel`` so callers
 * see both the canonical backend id (``"openai:gpt-4o"``) and the
 * phone's simplified id (``"chatgpt"``) in one round-trip.
 */
export async function probeModelSelection(
  intent: string,
): Promise<ProbedModelSelection | null> {
  try {
    const res = await selectModel(intent);
    return { ...res, simplifiedModel: mapCanonicalToModelId(res.model) };
  } catch {
    return null;
  }
}

export type ModelId =
  | "copilot"
  | "claude"
  | "chatgpt"
  | "gemini"
  | "grok"
  | "local";

// Card 19.3: a canonical backend model id (e.g. ``"openai:gpt-4o"``).
// Kept as ``string`` for forward-compatibility so the backend can add
// new ids without a phone-side type update — the runtime mapping below
// gates which ones the phone knows how to translate.
export type CanonicalModelId = string;

/**
 * Card 19.3: authoritative map from canonical backend model ids →
 * phone's simplified ``ModelId`` enum.
 *
 * Entries are restricted to ids that actually exist in the backend's
 * ``MODEL_REGISTRY`` (model_router.py). Speculative entries (e.g.
 * future Claude / GPT versions) are deliberately omitted so that when
 * the backend ships a new id, ``mapCanonicalToModelId`` returns
 * ``null`` and the gap is visible in observability logs instead of
 * being silently masked.
 */
export const canonicalModelMap: Record<CanonicalModelId, ModelId> = {
  "openai:gpt-4o":          "chatgpt",
  "openai:gpt-4o-mini":     "chatgpt",
  "anthropic:claude-3.7":   "claude",
  "google:gemini-2.0-flash": "gemini",
  "xai:groq-llama":         "grok",
  "local:llama3.1":         "local",
};

/**
 * Card 19.3: forward lookup — backend canonical id → phone ``ModelId``.
 * Returns ``null`` when the backend id has no phone mapping yet
 * (intentional: surfaces drift instead of hiding it).
 */
export function mapCanonicalToModelId(
  canonical: CanonicalModelId,
): ModelId | null {
  return canonicalModelMap[canonical] ?? null;
}

/**
 * Card 19.3: reverse lookup — phone ``ModelId`` → every backend
 * canonical id that maps to it. Returns ``[]`` when the phone enum
 * has no matching backend id. Multiple-to-one is expected (e.g. both
 * ``openai:gpt-4o`` and ``openai:gpt-4o-mini`` map to ``"chatgpt"``).
 */
export function mapModelIdToCanonical(
  model: ModelId,
): CanonicalModelId[] {
  return Object.entries(canonicalModelMap)
    .filter(([, v]) => v === model)
    .map(([k]) => k);
}

export type RouterErrorCode =
  | "no_credentials"
  | "http"
  | "timeout"
  | "unknown";

export type RouterResult =
  | { ok: true; model: ModelId; raw: string; elapsedMs: number }
  | { ok: false; model: ModelId; error: string; code: RouterErrorCode };

const STUB_LATENCY_MS = 200;

function mockReply(model: ModelId, text: string): string {
  // Deliberately fixture-rich so langbridg's heuristics have something to
  // chew on: hedging words for Tizzy, an explicit "Decide:" for Markov,
  // a multi-sentence body for Galileo.
  return [
    `${model.toUpperCase()} considered: "${text.slice(0, 200)}".`,
    `It seems like the answer might be straightforward, but there are several angles to consider.`,
    `Decide: proceed with the simplest viable option first.`,
    `Note: this is a stub response — no real model was called.`,
  ].join(" ");
}

async function stub(model: ModelId, text: string): Promise<RouterResult> {
  const start = Date.now();
  await new Promise((r) => setTimeout(r, STUB_LATENCY_MS));
  return {
    ok: true,
    model,
    raw: mockReply(model, text),
    elapsedMs: Date.now() - start,
  };
}

// Per-model entry points. When you wire real APIs (Anthropic, OpenAI, Google,
// xAI, Microsoft Graph, on-device LLM), swap the body of the matching function
// — the signature stays the same.
export const sendToCopilot = (text: string) => stub("copilot", text);
export const sendToClaude  = (text: string) => stub("claude",  text);
export const sendToChatGPT = (text: string) => stub("chatgpt", text);
export const sendToGemini  = (text: string) => stub("gemini",  text);
export const sendToGrok    = (text: string) => stub("grok",    text);
export const sendToLocal   = (text: string) => stub("local",   text);

export async function routeModelRequest(
  model: ModelId,
  text: string
): Promise<RouterResult> {
  switch (model) {
    case "copilot": return sendToCopilot(text);
    case "claude":  return sendToClaude(text);
    case "chatgpt": return sendToChatGPT(text);
    case "gemini":  return sendToGemini(text);
    case "grok":    return sendToGrok(text);
    case "local":   return sendToLocal(text);
    default:
      return {
        ok: false,
        model,
        error: `unknown model: ${model}`,
        code: "unknown",
      };
  }
}
