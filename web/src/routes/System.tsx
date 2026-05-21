// System diagnostics — the operator's eye view.
// Backend coupling: GET /health (always), GET /config (if authed).

import { useEffect, useState } from "react";
import {
  ApiError,
  config,
  health,
  isAuthed,
  type ConfigResponse,
  type HealthResponse,
} from "../lib/api";
import { APP_CONFIG, setApiBaseOverride } from "../lib/config";

interface Probe {
  status: "idle" | "running" | "ok" | "err";
  latencyMs?: number;
  detail?: string;
  result?: HealthResponse;
}

export default function System() {
  const [probe, setProbe] = useState<Probe>({ status: "idle" });
  const [cfg, setCfg] = useState<ConfigResponse["data"] | null>(null);
  const [cfgErr, setCfgErr] = useState<string | null>(null);
  const [overrideValue, setOverrideValue] = useState("");

  useEffect(() => { runProbe(); /* eslint-disable-next-line */ }, []);

  async function runProbe() {
    setProbe({ status: "running" });
    const t0 = performance.now();
    try {
      const r = await health();
      setProbe({
        status: "ok",
        latencyMs: Math.round(performance.now() - t0),
        result: r,
      });
    } catch (e: any) {
      setProbe({
        status: "err",
        latencyMs: Math.round(performance.now() - t0),
        detail: e?.message || String(e),
      });
    }
  }

  useEffect(() => {
    if (!isAuthed()) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await config();
        if (!cancelled) setCfg(r.data);
      } catch (e: any) {
        if (!cancelled) {
          setCfgErr(e instanceof ApiError ? e.message : (e?.message || "Could not load config"));
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  function applyOverride() {
    setApiBaseOverride(overrideValue.trim() || null);
  }

  function clearOverride() {
    setApiBaseOverride(null);
  }

  return (
    <div>
      <div className="panel">
        <h1>SYSTEM</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Backend probe, runtime configuration, environment, build info.
        </p>
      </div>

      {/* Probe */}
      <div className="panel">
        <div className="row row-between" style={{ marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>BACKEND PROBE</h2>
          <button className="btn btn-sm" onClick={runProbe}>RE-PROBE</button>
        </div>
        <div className="kv">
          <div className="k">api base</div>
          <div className="v">{APP_CONFIG.API_BASE}</div>
          <div className="k">status</div>
          <div className="v" style={{ color: probe.status === "ok" ? "var(--os-ok)" : probe.status === "err" ? "var(--os-err)" : "var(--os-text-secondary)" }}>
            {probe.status.toUpperCase()}
            {probe.latencyMs !== undefined ? `  ·  ${probe.latencyMs}ms` : ""}
          </div>
          <div className="k">version</div>
          <div className="v">{probe.result?.version || "—"}</div>
          {probe.detail ? (
            <>
              <div className="k">error</div>
              <div className="v" style={{ color: "var(--os-err)" }}>{probe.detail}</div>
            </>
          ) : null}
        </div>
      </div>

      {/* Runtime config (auth) */}
      <div className="panel">
        <h2>RUNTIME CONFIG</h2>
        {!isAuthed() ? (
          <div className="empty">Sign in to read /config.</div>
        ) : cfgErr ? (
          <div className="banner err">{cfgErr}</div>
        ) : !cfg ? (
          <div><span className="spinner" /> Loading…</div>
        ) : (
          <div className="kv">
            <div className="k">backend</div>
            <div className="v">{cfg.backend || "—"}</div>
            <div className="k">backend version</div>
            <div className="v">{cfg.version || "—"}</div>
            <div className="k">library bucket</div>
            <div className="v">{cfg.library_bucket || "—"}</div>
            <div className="k">library prefix</div>
            <div className="v">{cfg.library_prefix || "(none)"}</div>
            <div className="k">session ttl</div>
            <div className="v">{cfg.session_ttl ? `${cfg.session_ttl}s` : "—"}</div>
            <div className="k">gcs ready</div>
            <div className="v">{String(cfg.gcs_available ?? "—")}</div>
            <div className="k">cors origins</div>
            <div className="v">{(cfg.cors_origins || []).join(", ") || "(none)"}</div>
            <div className="k">invite-only</div>
            <div className="v">{String(cfg.invite_only ?? false)}</div>
            <div className="k">terrace-1</div>
            <div className="v">{cfg.terrace_1_redeemed ?? 0} / {cfg.terrace_1_cap ?? 500}</div>
            <div className="k">billing configured</div>
            <div className="v">{String(cfg.billing_configured ?? false)}</div>
          </div>
        )}
      </div>

      {/* Environment */}
      <div className="panel">
        <h2>ENVIRONMENT</h2>
        <div className="kv">
          <div className="k">frontend version</div>
          <div className="v">{APP_CONFIG.VERSION}</div>
          <div className="k">user agent</div>
          <div className="v">{navigator.userAgent}</div>
          <div className="k">language</div>
          <div className="v">{navigator.language}</div>
          <div className="k">origin</div>
          <div className="v">{location.origin}</div>
        </div>
      </div>

      {/* API base override */}
      <div className="panel">
        <h2>API BASE OVERRIDE</h2>
        <p className="muted" style={{ marginBottom: 12, fontSize: "0.85rem" }}>
          Per-browser override for the backend URL. Persists in localStorage; the
          page reloads after Save so resolution picks it up.
        </p>
        <div className="field">
          <label htmlFor="api-override">Override URL</label>
          <input
            id="api-override"
            className="input"
            type="url"
            placeholder={APP_CONFIG.API_BASE}
            value={overrideValue}
            onChange={(e) => setOverrideValue(e.target.value)}
          />
        </div>
        <div className="row">
          <button className="btn" onClick={applyOverride} disabled={!overrideValue.trim()}>
            SAVE
          </button>
          <button className="btn btn-secondary btn-sm" onClick={clearOverride}>
            CLEAR
          </button>
        </div>
      </div>
    </div>
  );
}
