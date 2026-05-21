// web/src/routes/FounderAnalyticsQuality.tsx
//
// Phase 6B addition. Renders run-quality scoring (run_quality.py) as a
// table + inline-SVG trendline + warnings panel. Reads:
//   GET /founder/analytics/quality
//
// No new libraries. Layout matches the Phase 5C FounderAcceptanceCurve
// pattern.

import { useEffect, useState, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";

interface ScoreEntry {
  run_id: string | null;
  score: number;
  band: "healthy" | "warning" | "critical_fail";
  components: Record<string, number>;
  weights: Record<string, number>;
  reasons: string[];
}

interface QualityResponse {
  n_runs: number;
  scores: ScoreEntry[];
  summary: {
    mean: number | null;
    median: number | null;
    latest: number | null;
    trend: "improving" | "flat" | "degrading" | "insufficient data" | "error";
    n_healthy: number;
    n_warning: number;
    n_critical_fail: number;
  };
  error?: string;
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
      {" "}<code>/founder/analytics/quality</code>; math is in
      {" "}<code>run_quality.py</code> at repo root.
    </div>
  );
}

function ScoreTrendChart({ scores }: { scores: ScoreEntry[] }) {
  if (scores.length === 0) {
    return <p style={{ opacity: 0.7 }}>no scored runs yet.</p>;
  }
  const W = 800, H = 200;
  const padL = 48, padR = 12, padT = 12, padB = 24;
  const xs = scores.map((_, i) => i);
  const yLo = 0;
  const yHi = 100;
  const xRange = Math.max(1, xs.length - 1);
  const sx = (i: number) =>
    padL + (W - padL - padR) * (i / xRange);
  const sy = (y: number) =>
    padT + (H - padT - padB) * (1 - (y - yLo) / (yHi - yLo));
  const polyline = scores
    .map((s, i) => `${sx(i).toFixed(2)},${sy(s.score).toFixed(2)}`)
    .join(" ");

  // Band gridlines (50 = warning, 80 = healthy)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="run-quality trendline"
         style={{ width: "100%", maxWidth: 800, height: "auto" }}>
      {/* axes */}
      <line x1={padL} y1={padT} x2={padL} y2={H - padB}
            stroke="currentColor" strokeOpacity="0.3" />
      <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB}
            stroke="currentColor" strokeOpacity="0.3" />
      {/* band thresholds */}
      {[50, 80].map((y, i) => (
        <line key={i} x1={padL} x2={W - padR}
              y1={sy(y)} y2={sy(y)}
              stroke="currentColor" strokeOpacity="0.15"
              strokeDasharray="4 4" />
      ))}
      {/* y labels */}
      {[0, 50, 80, 100].map((y, i) => (
        <text key={i} x={padL - 6} y={sy(y) + 4} fontSize="10"
              textAnchor="end" fill="currentColor" opacity="0.6">{y}</text>
      ))}
      {/* line */}
      <polyline points={polyline} fill="none"
                stroke="currentColor" strokeWidth="1.5" />
      {/* points */}
      {scores.map((s, i) => (
        <circle key={i} cx={sx(i)} cy={sy(s.score)}
                r={s.band === "critical_fail" ? 4 : 2.5}
                fill={s.band === "critical_fail" ? "currentColor" : "transparent"}
                stroke="currentColor">
          <title>{s.run_id ?? "?"} — {s.score} ({s.band})</title>
        </circle>
      ))}
    </svg>
  );
}

export default function FounderAnalyticsQuality() {
  const [data, setData] = useState<QualityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await api<QualityResponse>("/founder/analytics/quality");
      setData(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (error) {
    return (
      <main className="founder-analytics-quality">
        <h1>Founder analytics — run quality</h1>
        <p role="alert">error: {error}</p>
        <button onClick={() => void load()}>retry</button>
        <p><Link to="/founder/acceptance">back to surveillance</Link></p>
      </main>
    );
  }
  if (!data) {
    return (
      <main className="founder-analytics-quality">
        <h1>Founder analytics — run quality</h1>
        <p>loading…</p>
      </main>
    );
  }

  const fmt = (v: number | null) => (v == null ? "—" : v.toFixed(1));

  return (
    <main className="founder-analytics-quality">
      <h1>Founder analytics — run quality</h1>
      <VerificationBanner />

      <p>
        <Link to="/founder/acceptance">← back to surveillance</Link>
        {" · "}
        <Link to="/founder/acceptance/curve">stability curve</Link>
        {" · "}
        <Link to="/founder/telemetry">telemetry →</Link>
      </p>

      {data.error && (
        <p role="alert" style={{ opacity: 0.8 }}>
          run_quality error: {data.error}
        </p>
      )}

      <section>
        <h2>Trendline (0–100)</h2>
        <p style={{ fontSize: "0.85rem", opacity: 0.7 }}>
          {data.n_runs} runs · trend: <strong>{data.summary.trend}</strong> ·
          mean {fmt(data.summary.mean)} · median {fmt(data.summary.median)} ·
          latest {fmt(data.summary.latest)}
        </p>
        <ScoreTrendChart scores={data.scores} />
      </section>

      <section>
        <h2>Band counts</h2>
        <table>
          <tbody>
            <tr><th>healthy (80–100)</th><td>{data.summary.n_healthy}</td></tr>
            <tr><th>warning (50–79)</th><td>{data.summary.n_warning}</td></tr>
            <tr><th>critical_fail (&lt; 50)</th>
                <td>{data.summary.n_critical_fail}</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>Warnings + critical fails (latest first)</h2>
        {data.scores.filter((s) => s.band !== "healthy").length === 0 ? (
          <p>no non-healthy runs</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>run id</th><th>score</th><th>band</th><th>reasons</th>
              </tr>
            </thead>
            <tbody>
              {[...data.scores]
                .reverse()
                .filter((s) => s.band !== "healthy")
                .map((s, i) => (
                  <tr key={i} data-run-id={s.run_id}>
                    <td><code>{s.run_id ?? "?"}</code></td>
                    <td>{s.score}</td>
                    <td>{s.band}</td>
                    <td>
                      <ul style={{ margin: 0, paddingLeft: "1rem" }}>
                        {s.reasons.map((r, j) => <li key={j}>{r}</li>)}
                      </ul>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2>All runs</h2>
        {data.scores.length === 0 ? (
          <p>no scored runs yet</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>run id</th>
                <th>score</th>
                <th>band</th>
                <th>timing</th>
                <th>monotonicity</th>
                <th>drift_proxy</th>
                <th>surface</th>
                <th>variance</th>
              </tr>
            </thead>
            <tbody>
              {[...data.scores].reverse().map((s, i) => (
                <tr key={i} data-run-id={s.run_id}>
                  <td><code>{s.run_id ?? "?"}</code></td>
                  <td>{s.score}</td>
                  <td>{s.band}</td>
                  <td>{s.components.timing_stability ?? "—"}</td>
                  <td>{s.components.monotonicity ?? "—"}</td>
                  <td>{s.components.drift_proxy ?? "—"}</td>
                  <td>{s.components.surface_health ?? "—"}</td>
                  <td>{s.components.scenario_variance ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}
