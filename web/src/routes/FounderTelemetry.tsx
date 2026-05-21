// web/src/routes/FounderTelemetry.tsx
//
// Phase 7C addition. Renders the combined trust-center + narrative-
// drift telemetry payload. Reads:
//   GET /founder/telemetry
//
// No new libraries. Inline SVG for the trust-signal gauge.

import { useEffect, useState, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";

interface TrustSignal {
  signal_score: number;
  level: "stable" | "degrading" | "critical";
  components: Record<string, number>;
  weights: Record<string, number>;
  thresholds: { stable_at: number; degrading_at: number };
  inputs?: Record<string, unknown>;
}

interface Alignment {
  alignment_score: number | null;
  surface_variance: number | null;
  n_scenarios: number;
  scenario_pass_rates?: Record<string, number>;
}

interface Warnings {
  n_runs: number;
  n_critical_fail: number;
  n_warning: number;
  n_healthy: number;
  trend: string;
}

interface DriftComponent {
  signal: string;
  drift_pct?: number;
  interpretation?: string;
  early_mean?: number;
  late_mean?: number;
  delta?: number;
}

interface DriftEarlySignal {
  signal: string;
  prior: number;
  recent: number;
  delta: number;
}

interface DriftBlock {
  drifting: boolean;
  drift_components: DriftComponent[];
  early_signals: DriftEarlySignal[];
  n_runs: number;
  note?: string;
}

interface TelemetryResponse {
  trust_signal: TrustSignal | Record<string, never>;
  alignment: Alignment | Record<string, never>;
  warnings: Warnings | Record<string, never>;
  drift: DriftBlock | Record<string, never>;
  drift_score: number;
  trust_center_error?: string;
  narrative_drift_error?: string;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...(init ?? {}),
  });
  if (!res.ok) throw new Error(`${path} → ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

function VerificationBanner() {
  const loc = useLocation();
  if (new URLSearchParams(loc.search).get("verify") !== "1") return null;
  return (
    <div
      role="status"
      className="acceptance-verify-banner"
      style={{
        padding: "0.5rem 0.75rem", marginBottom: "1rem",
        border: "1px solid currentColor", fontSize: "0.85rem",
      }}
    >
      Verification Mode — <code>?verify=1</code> active. Reading
      {" "}<code>/founder/telemetry</code>; math is in
      {" "}<code>trust_center_math.py</code> + <code>narrative_drift.py</code>{" "}
      at repo root.
    </div>
  );
}

function TrustGauge({ signal }: { signal: TrustSignal | Record<string, never> }) {
  const score =
    "signal_score" in signal && typeof signal.signal_score === "number"
      ? signal.signal_score
      : null;
  const level = "level" in signal ? signal.level : "—";
  if (score === null) {
    return <p style={{ opacity: 0.7 }}>no telemetry data yet.</p>;
  }
  const W = 360, H = 120;
  const padL = 24, padR = 24, padT = 16, padB = 32;
  const trackY = padT + (H - padT - padB) / 2;
  const trackH = 18;
  const xMin = padL;
  const xMax = W - padR;
  const xScore = xMin + (xMax - xMin) * (score / 100);
  const stableX = xMin + (xMax - xMin) * (signal.thresholds?.stable_at ?? 75) / 100;
  const degradingX = xMin + (xMax - xMin) * (signal.thresholds?.degrading_at ?? 50) / 100;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="trust signal gauge"
         style={{ width: "100%", maxWidth: 360, height: "auto" }}>
      {/* track */}
      <rect x={xMin} y={trackY - trackH / 2} width={xMax - xMin} height={trackH}
            fill="currentColor" fillOpacity="0.1" stroke="currentColor"
            strokeOpacity="0.3" />
      {/* threshold ticks */}
      <line x1={degradingX} x2={degradingX} y1={trackY - trackH} y2={trackY + trackH}
            stroke="currentColor" strokeOpacity="0.4" strokeDasharray="3 3" />
      <line x1={stableX} x2={stableX} y1={trackY - trackH} y2={trackY + trackH}
            stroke="currentColor" strokeOpacity="0.4" strokeDasharray="3 3" />
      {/* score marker */}
      <circle cx={xScore} cy={trackY} r="9" fill="currentColor" />
      {/* labels */}
      <text x={xMin} y={H - 12} fontSize="10" fill="currentColor" opacity="0.6">0</text>
      <text x={degradingX} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="middle">{signal.thresholds?.degrading_at ?? 50}</text>
      <text x={stableX} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="middle">{signal.thresholds?.stable_at ?? 75}</text>
      <text x={xMax} y={H - 12} fontSize="10" fill="currentColor"
            opacity="0.6" textAnchor="end">100</text>
      {/* score number, lifted 18px above the marker */}
      <text x={xScore} y={trackY - 18} fontSize="13" fontWeight="600"
            fill="currentColor" textAnchor="middle">
        {score.toFixed(1)} · {level}
      </text>
    </svg>
  );
}

function ComponentTable({
  components, weights,
}: {
  components: Record<string, number> | undefined;
  weights: Record<string, number> | undefined;
}) {
  if (!components) return <p>no components</p>;
  return (
    <table>
      <thead>
        <tr><th>component</th><th>score</th><th>weight</th></tr>
      </thead>
      <tbody>
        {Object.keys(components).map((k) => (
          <tr key={k}>
            <td>{k}</td>
            <td>{components[k]?.toFixed?.(1) ?? "—"}</td>
            <td>{weights?.[k]?.toFixed?.(2) ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function FounderTelemetry() {
  const [data, setData] = useState<TelemetryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await api<TelemetryResponse>("/founder/telemetry");
      setData(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (error) {
    return (
      <main className="founder-telemetry">
        <h1>Founder telemetry</h1>
        <p role="alert">error: {error}</p>
        <button onClick={() => void load()}>retry</button>
        <p><Link to="/founder/acceptance">back to surveillance</Link></p>
      </main>
    );
  }
  if (!data) {
    return (
      <main className="founder-telemetry">
        <h1>Founder telemetry</h1>
        <p>loading…</p>
      </main>
    );
  }

  const fmtPct = (v: number | null | undefined) =>
    typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "—";

  return (
    <main className="founder-telemetry">
      <h1>Founder telemetry</h1>
      <VerificationBanner />

      <p>
        <Link to="/founder/acceptance">← back to surveillance</Link>
        {" · "}
        <Link to="/founder/analytics/quality">run quality</Link>
        {" · "}
        <Link to="/founder/acceptance/curve">stability curve</Link>
      </p>

      {data.trust_center_error && (
        <p role="alert" style={{ opacity: 0.8 }}>
          trust_center_math error: {data.trust_center_error}
        </p>
      )}
      {data.narrative_drift_error && (
        <p role="alert" style={{ opacity: 0.8 }}>
          narrative_drift error: {data.narrative_drift_error}
        </p>
      )}

      <section>
        <h2>Trust signal</h2>
        <TrustGauge signal={data.trust_signal} />
        {"components" in data.trust_signal && (
          <ComponentTable
            components={(data.trust_signal as TrustSignal).components}
            weights={(data.trust_signal as TrustSignal).weights}
          />
        )}
      </section>

      <section>
        <h2>Alignment</h2>
        <table>
          <tbody>
            <tr>
              <th>alignment score</th>
              <td>
                {"alignment_score" in data.alignment &&
                typeof data.alignment.alignment_score === "number"
                  ? data.alignment.alignment_score.toFixed(1)
                  : "—"}
              </td>
            </tr>
            <tr>
              <th>scenarios examined</th>
              <td>
                {"n_scenarios" in data.alignment
                  ? (data.alignment as Alignment).n_scenarios
                  : "—"}
              </td>
            </tr>
            <tr>
              <th>surface variance</th>
              <td>
                {"surface_variance" in data.alignment &&
                typeof data.alignment.surface_variance === "number"
                  ? data.alignment.surface_variance.toFixed(4)
                  : "—"}
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>Warnings panel</h2>
        <table>
          <tbody>
            <tr>
              <th>runs scored</th>
              <td>{"n_runs" in data.warnings ? (data.warnings as Warnings).n_runs : 0}</td>
            </tr>
            <tr>
              <th>healthy</th>
              <td>{"n_healthy" in data.warnings ? (data.warnings as Warnings).n_healthy : 0}</td>
            </tr>
            <tr>
              <th>warning</th>
              <td>{"n_warning" in data.warnings ? (data.warnings as Warnings).n_warning : 0}</td>
            </tr>
            <tr>
              <th>critical_fail</th>
              <td>{"n_critical_fail" in data.warnings ? (data.warnings as Warnings).n_critical_fail : 0}</td>
            </tr>
            <tr>
              <th>quality trend</th>
              <td>{"trend" in data.warnings ? (data.warnings as Warnings).trend : "—"}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>Narrative drift</h2>
        <p>
          drift score: <strong>{data.drift_score.toFixed(3)}</strong>
          {" · "}
          status:{" "}
          <strong>
            {"drifting" in data.drift && (data.drift as DriftBlock).drifting
              ? "drifting"
              : "quiet"}
          </strong>
        </p>
        {"drift_components" in data.drift &&
          (data.drift as DriftBlock).drift_components.length > 0 && (
          <>
            <h3>Drift components</h3>
            <ul>
              {(data.drift as DriftBlock).drift_components.map((c, i) => (
                <li key={i}>
                  <code>{c.signal}</code>
                  {typeof c.drift_pct === "number" && (
                    <> · drift_pct {fmtPct(c.drift_pct)} ({c.interpretation})</>
                  )}
                  {typeof c.early_mean === "number" && (
                    <> · early {c.early_mean} → late {c.late_mean} (Δ {c.delta})</>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
        {"early_signals" in data.drift &&
          (data.drift as DriftBlock).early_signals.length > 0 && (
          <>
            <h3>Early signals (last quarter vs prior)</h3>
            <ul>
              {(data.drift as DriftBlock).early_signals.map((s, i) => (
                <li key={i}>
                  <code>{s.signal}</code>: prior {fmtPct(s.prior)} → recent
                  {" "}{fmtPct(s.recent)} (Δ {fmtPct(s.delta)})
                </li>
              ))}
            </ul>
          </>
        )}
        {"note" in data.drift && (data.drift as DriftBlock).note && (
          <p style={{ opacity: 0.7 }}>{(data.drift as DriftBlock).note}</p>
        )}
      </section>
    </main>
  );
}
