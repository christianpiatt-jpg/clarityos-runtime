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
 * Card 19.2: non-throwing observability probe over ``selectModel``.
 * Returns ``null`` on any failure (no session, network, 4xx/5xx). Use
 * fire-and-forget at callsites so the user-facing path is never
 * delayed or destabilised by the probe.
 */
export async function probeModelSelection(
  intent: string,
): Promise<ModelSelectionResult | null> {
  try {
    return await selectModel(intent);
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
