// v68 / Unit 73 — ProviderDashboard route.
//
// Single page that joins:
//   * GET /runtime/providers/health  — availability snapshot per provider
//   * GET /runtime/providers/models  — registry (provider → models) + flat allowlist
//   * GET /runtime/providers/config  — per-provider call/health timeouts + retries
//
// All three fire on mount; the table renders union-of-providers so the
// page works even when the three responses disagree on which providers
// appear (e.g. ``mock`` only appears in /health, never in /models or
// /config — those are HTTP-only).
//
// Auth-gated via RequireAuth at the route layer (App.tsx).

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  getProviderConfig,
  getProviderHealth,
  getProviderModels,
  type ProviderConfigResponse,
  type ProviderHealthResponse,
  type ProviderModelsResponse,
} from "../lib/api";

const DISPLAY_ORDER: readonly string[] = [
  "mock", "anthropic", "openai", "gemini", "xai", "local", "google",
] as const;

export default function ProviderDashboard() {
  const [health, setHealth] = useState<ProviderHealthResponse | null>(null);
  const [models, setModels] = useState<ProviderModelsResponse | null>(null);
  const [config, setConfig] = useState<ProviderConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, m, c] = await Promise.all([
        getProviderHealth(),
        getProviderModels(),
        getProviderConfig(),
      ]);
      setHealth(h);
      setModels(m);
      setConfig(c);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchAll(); }, [fetchAll]);

  // Union of provider keys across the three responses, sorted by
  // DISPLAY_ORDER first then alphabetical for anything new.
  const providers = (() => {
    const seen = new Set<string>();
    if (health) for (const k of Object.keys(health)) seen.add(k);
    if (models) for (const k of Object.keys(models.registry)) seen.add(k);
    if (config) for (const k of Object.keys(config.timeouts)) seen.add(k);
    const ordered: string[] = [];
    for (const k of DISPLAY_ORDER) if (seen.has(k)) ordered.push(k);
    for (const k of [...seen].sort()) if (!ordered.includes(k)) ordered.push(k);
    return ordered;
  })();

  return (
    <div>
      <div className="panel">
        <h1>PROVIDER DASHBOARD</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Per-provider availability, model registry, and HTTP timeout
          configuration. The synthetic <code>mock</code> provider only
          appears in health (it has no wire path so it carries no
          models or timeouts).
        </p>
        <div className="row" style={{ marginTop: 8, gap: 8, alignItems: "center" }}>
          <div className="muted" style={{ flex: 1, fontSize: 12 }}>
            {lastChecked ? `last checked ${lastChecked}` : ""}
          </div>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => void fetchAll()}
            disabled={loading}
            data-testid="provider-dashboard-refresh"
          >
            REFRESH
          </button>
        </div>
        {error ? (
          <div className="banner err" style={{ marginTop: 8 }} data-testid="provider-dashboard-error">
            {error}
          </div>
        ) : null}
      </div>

      <div className="panel">
        {loading && !health ? (
          <div><span className="spinner" /> Loading providers…</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }} data-testid="provider-dashboard-table">
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                <th style={thStyle}>Provider</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Call (s)</th>
                <th style={thStyle}>Health (s)</th>
                <th style={thStyle}>Retries</th>
                <th style={thStyle}>Models</th>
              </tr>
            </thead>
            <tbody>
              {providers.map((name) => {
                const h = health?.[name];
                const t = config?.timeouts[name];
                const r = config?.retries[name];
                const m = models?.registry[name];
                return (
                  <tr key={name} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                    <td style={{ ...tdStyle, fontFamily: "var(--font-mono)" }}>{name}</td>
                    <td style={tdStyle}>
                      {h ? (
                        <span style={{ color: h.available ? "var(--os-ok, #10b981)" : "var(--os-err, #ef4444)" }}>
                          {h.available ? "available" : "unavailable"}
                          {h.error ? (
                            <span className="muted" style={{ marginLeft: 6, fontSize: 11 }}>
                              {h.error}
                            </span>
                          ) : null}
                        </span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td style={tdStyle}>{t ? t.call : <span className="muted">—</span>}</td>
                    <td style={tdStyle}>{t ? t.health : <span className="muted">—</span>}</td>
                    <td style={tdStyle}>{r !== undefined ? r : <span className="muted">—</span>}</td>
                    <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                      {m && m.length > 0 ? m.join(", ") : <span className="muted">—</span>}
                    </td>
                  </tr>
                );
              })}
              {config ? (
                <tr style={{ borderTop: "2px solid rgba(255,255,255,0.15)" }}>
                  <td style={{ ...tdStyle, color: "var(--os-text-muted, #888)", fontStyle: "italic" }}>
                    (defaults)
                  </td>
                  <td style={tdStyle} className="muted">—</td>
                  <td style={tdStyle}>{config.defaults.call_timeout}</td>
                  <td style={tdStyle}>{config.defaults.health_timeout}</td>
                  <td style={tdStyle}>{config.defaults.retries}</td>
                  <td style={tdStyle} className="muted">—</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        )}
      </div>

      {models ? (
        <div className="panel">
          <h2>SUPPORTED MODEL IDS</h2>
          <p className="muted" style={{ marginTop: 4, marginBottom: 8 }}>
            Flat allowlist consumed by <code>is_valid_model</code> on the
            backend. Includes the <code>auto</code> routing sentinel which
            never appears under a provider in the registry.
          </p>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {models.supported.map((m) => (
              <li
                key={m}
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  padding: "3px 0",
                }}
              >
                {m}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left", padding: "8px 10px", fontWeight: 600,
  fontSize: 11, letterSpacing: "0.5px",
  color: "var(--os-text-muted, #888)",
};
const tdStyle: React.CSSProperties = {
  padding: "8px 10px", verticalAlign: "middle", fontSize: 12,
};

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
