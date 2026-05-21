// v65 / Unit 69 — Provider health dashboard (web).
//
// Lists each LLM provider with a red/green availability indicator
// and any error text. Backed by GET /runtime/providers/health. Each
// real provider gets a lightweight 1-token completion call server-
// side; the synthetic "mock" provider is always green.

import { useEffect, useState } from "react";
import {
  ApiError,
  getProviderHealth,
  type ProviderHealthResponse,
} from "../lib/api";

// Display order — matches runtime_providers.PROVIDERS_ORDER but with
// the synthetic "mock" first since it's always available.
const DISPLAY_ORDER: readonly string[] = [
  "mock", "anthropic", "openai", "gemini",
] as const;

export default function ProviderHealth() {
  const [data, setData] = useState<ProviderHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  async function fetchHealth() {
    setLoading(true);
    setError(null);
    try {
      const r = await getProviderHealth();
      setData(r);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void fetchHealth(); }, []);

  // Sort providers per DISPLAY_ORDER, then any extras alphabetically.
  const sortedKeys = (() => {
    if (!data) return [] as string[];
    const ordered: string[] = [];
    for (const k of DISPLAY_ORDER) {
      if (k in data) ordered.push(k);
    }
    for (const k of Object.keys(data).sort()) {
      if (!ordered.includes(k)) ordered.push(k);
    }
    return ordered;
  })();

  return (
    <div>
      <div className="panel">
        <h1>PROVIDER HEALTH</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Lightweight reachability check for each LLM provider. Real
          providers issue a 1-token completion against their HTTP
          endpoint (3-second timeout); the <code>mock</code> entry is
          the always-available deterministic fallback.
        </p>
        <div className="row" style={{ marginTop: 12, gap: 8, alignItems: "center" }}>
          <div style={{ flex: 1, fontSize: "0.85rem" }}>
            {lastChecked ? (
              <span className="muted">last checked {lastChecked}</span>
            ) : null}
          </div>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={fetchHealth}
            disabled={loading}
          >
            REFRESH
          </button>
        </div>
        {error ? (
          <div className="banner err" style={{ marginTop: 8 }}>{error}</div>
        ) : null}
      </div>

      <div className="panel" style={{ padding: 0 }}>
        {loading && !data ? (
          <div style={{ padding: 16 }}>
            <span className="spinner" /> Probing providers…
          </div>
        ) : !data ? (
          <div className="empty" style={{ padding: 16 }}>
            No data.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{
                borderBottom: "1px solid var(--os-border, rgba(255,255,255,0.1))",
              }}>
                <th style={thStyle}>Provider</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Error</th>
              </tr>
            </thead>
            <tbody>
              {sortedKeys.map((name) => {
                const entry = data[name];
                return (
                  <tr
                    key={name}
                    style={{
                      borderBottom: "1px solid var(--os-border, rgba(255,255,255,0.05))",
                    }}
                  >
                    <td style={{ ...tdStyle, fontFamily: "var(--font-mono)" }}>
                      {name}
                    </td>
                    <td style={tdStyle}>
                      <span
                        aria-label={entry.available ? "available" : "unavailable"}
                        style={{
                          display: "inline-block",
                          width: 10, height: 10, borderRadius: "50%",
                          marginRight: 8,
                          background: entry.available
                            ? "var(--os-ok, #10b981)"
                            : "var(--os-err, #ef4444)",
                        }}
                      />
                      <span style={{
                        color: entry.available
                          ? "var(--os-ok, #10b981)"
                          : "var(--os-err, #ef4444)",
                      }}>
                        {entry.available ? "available" : "unavailable"}
                      </span>
                    </td>
                    <td style={{
                      ...tdStyle,
                      color: "var(--os-text-secondary, #888)",
                      fontFamily: "var(--font-mono)",
                      fontSize: "0.8rem",
                    }}>
                      {entry.error || "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px 12px",
  fontWeight: 600,
  fontSize: "0.8rem",
  color: "var(--os-text-secondary, #888)",
};

const tdStyle: React.CSSProperties = {
  padding: "10px 12px",
  verticalAlign: "middle",
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
