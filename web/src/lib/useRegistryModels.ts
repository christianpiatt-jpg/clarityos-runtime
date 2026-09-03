/**
 * useRegistryModels — the model ids a picker may offer, from the SERVER.
 *
 * ★ WHY (#126). The web constant V44_MODEL_IDS said gpt-4.2 / claude-3.7 /
 * gemini-2.0 while the router registry (model_router.MODEL_REGISTRY) said
 * gpt-5.4 / claude-haiku-4-5 / gemini-2.5-flash. Two dropdowns offered ids
 * is_valid_model rejects. The registry is the source of truth and GET
 * /runtime/providers/models already returns it; this hook fetches it once
 * per mount and hands back `supported` (which includes the "auto" sentinel).
 *
 * The constant survives ONLY as the fallback when the fetch fails, and the
 * hook says so (`source: "fallback"`) so the picker can label it
 * "registry unavailable" instead of pretending.
 */
import { useEffect, useState } from "react";

import { getProviderModels, V44_MODEL_IDS } from "./api";

export type RegistrySource = "loading" | "registry" | "fallback";

export interface RegistryModels {
  ids: string[];
  source: RegistrySource;
  error: string | null;
}

export function useRegistryModels(): RegistryModels {
  const [state, setState] = useState<RegistryModels>({
    ids: [], source: "loading", error: null,
  });

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await getProviderModels();
        const ids = Array.isArray(r.supported)
          ? r.supported.filter((m): m is string => typeof m === "string" && m.length > 0)
          : [];
        if (!alive) return;
        if (ids.length === 0) {
          // A registry with nothing in it is not a registry; say so.
          setState({ ids: [...V44_MODEL_IDS], source: "fallback", error: "registry returned no models" });
          return;
        }
        // "auto" first, then the registry's own order.
        const ordered = ["auto", ...ids.filter((m) => m !== "auto")].filter(
          (m, i, arr) => arr.indexOf(m) === i,
        );
        setState({ ids: ordered, source: "registry", error: null });
      } catch (e) {
        if (!alive) return;
        setState({
          ids: [...V44_MODEL_IDS],
          source: "fallback",
          error: e instanceof Error ? e.message : String(e),
        });
      }
    })();
    return () => { alive = false; };
  }, []);

  return state;
}
