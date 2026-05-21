// v64 / Unit 67 — Operator model preferences UI (web).
//
// Read+set per-operator (provider, model). Backed by the v67 endpoints
// at /operator/model_preferences. Auth-gated; the page assumes the
// user is signed in (route is wrapped in RequireAuth in App.tsx).

import { useEffect, useState } from "react";
import {
  ApiError,
  getModelPreferences,
  getUser,
  setModelPreferences,
  type ModelPreferencesResponse,
} from "../lib/api";

// Operator-vocab providers, matching runtime_providers.PROVIDERS_ORDER.
const PROVIDERS: readonly string[] = [
  "anthropic", "openai", "gemini", "xai", "local",
] as const;

// Default model per provider — matches runtime_providers._PROVIDER_DEFAULT_MODEL.
const DEFAULT_MODELS: Record<string, string> = {
  anthropic: "claude-3.7",
  openai:    "gpt-4.2",
  gemini:    "gemini-2.0",
  xai:       "groq-llama",
  local:     "llama3.1",
};

export default function ModelPreferences() {
  const operatorId = getUser() || "(not signed in)";
  const [provider, setProvider] = useState("anthropic");
  const [model, setModel] = useState(DEFAULT_MODELS.anthropic);
  const [current, setCurrent] = useState<ModelPreferencesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  // On mount: load current preference.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await getModelPreferences();
        if (cancelled) return;
        setCurrent(r);
        setProvider(r.provider);
        setModel(r.model);
      } catch (e: unknown) {
        if (!cancelled) setError(formatError(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSavedAt(null);
    try {
      const r = await setModelPreferences(provider, model);
      setCurrent(r);
      setSavedAt(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setSaving(false);
    }
  }

  // When provider changes, snap model to that provider's default
  // (avoids submitting e.g. {provider: anthropic, model: gpt-4.2}).
  function handleProviderChange(next: string) {
    setProvider(next);
    setModel(DEFAULT_MODELS[next] || "");
  }

  return (
    <div>
      <div className="panel">
        <h1>MODEL PREFERENCES</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Per-operator (provider, model) used by the runtime loop.
          Stored in the vault — survives restarts. Falls back to the
          system default chain when unset.
        </p>
        <div className="row" style={{ marginTop: 12, alignItems: "center" }}>
          <div style={{ flex: 1, fontSize: "0.85rem" }}>
            <span className="muted">authed as </span>
            <span style={{ fontFamily: "var(--font-mono)" }}>{operatorId}</span>
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>CURRENT</h2>
        {loading ? (
          <div><span className="spinner" /> Loading…</div>
        ) : current ? (
          <div className="kv">
            <div className="k">provider</div>
            <div className="v">{current.provider}</div>
            <div className="k">model</div>
            <div className="v" style={{ fontFamily: "var(--font-mono)" }}>{current.model}</div>
            <div className="k">source</div>
            <div className="v">
              {current.source === "vault" ? "explicit (vault)" : "default (chain)"}
            </div>
          </div>
        ) : (
          <div className="empty">No preference loaded.</div>
        )}
      </div>

      <div className="panel">
        <h2>UPDATE</h2>
        <form onSubmit={handleSave}>
          <div className="field">
            <label htmlFor="pref-provider">Provider</label>
            <select
              id="pref-provider"
              className="input"
              value={provider}
              onChange={(e) => handleProviderChange(e.target.value)}
              disabled={saving}
            >
              {PROVIDERS.map((p) => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
          </div>
          <div className="field" style={{ marginTop: 8 }}>
            <label htmlFor="pref-model">Model</label>
            <input
              id="pref-model"
              className="input"
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={saving}
              placeholder={DEFAULT_MODELS[provider] || ""}
            />
          </div>
          <div className="row" style={{ marginTop: 12, gap: 8, alignItems: "center" }}>
            <button
              type="submit"
              className="btn"
              disabled={saving || !provider || !model.trim()}
            >
              {saving ? "SAVING…" : "SAVE"}
            </button>
            {savedAt ? (
              <span className="muted" style={{ fontSize: "0.8rem" }}>
                saved at {savedAt}
              </span>
            ) : null}
          </div>
        </form>
        {error ? (
          <div className="banner err" style={{ marginTop: 12 }}>{error}</div>
        ) : null}
      </div>
    </div>
  );
}

function formatError(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in (e.body as Record<string, unknown>)) {
      const d = (e.body as Record<string, unknown>).detail;
      if (typeof d === "string") return d;
    }
    return `${e.code}: ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}
