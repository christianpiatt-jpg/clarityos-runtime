/**
 * #147 / #161 -- the history row names the model that answered (the web's
 * routes/SessionHistory.tsx modelLabel, verbatim). A pre-#147 row carries no
 * model_id and reads "engine=<engine>" as it always did.
 */
import type { SessionHistoryEntry } from "./api";

const ENGINE_PROVIDER: Record<string, string> = {
  claude: "anthropic",
  gemini: "google",
  grok:   "xai",
  local:  "local",
};

export function modelLabel(
  entry: Pick<SessionHistoryEntry, "engine" | "model_id" | "mock">,
): string {
  const id = entry.model_id;
  if (!id) return `engine=${entry.engine}`;
  const provider = id.includes(":") ? id.slice(0, id.indexOf(":")) : id;
  const mock = entry.mock ? " \u00b7 mock" : "";
  if (ENGINE_PROVIDER[entry.engine] === provider) return `model=${id}${mock}`;
  return `engine ${entry.engine} \u2192 routed ${id}${mock}`;
}
