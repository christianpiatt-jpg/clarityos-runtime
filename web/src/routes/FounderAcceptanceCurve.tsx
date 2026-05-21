// web/src/routes/FounderAcceptanceCurve.tsx
//
// Phase 5C addition. Renders the longitudinal stability projection:
// SVG line chart of mean_ms across runs, drift table, and surface
// health summary. Reads:
//   GET /founder/acceptance/stability/curve
//
// No new libraries. The chart is plain SVG drawn from the data points
// returned by the backend. Layout matches the existing
// FounderAcceptanceRuns.tsx and FounderAcceptanceStability.tsx
// patterns.

import { useEffect, useState, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";

interface CurvePoint {
  run_id: string | null;
  ts_finished: string | null;
  monotonicity_pass: boolean | null;
  mean_ms: number | null;
  max_ms: number | null;
  stddev_ms: number | null;
}

interface CurveBlock {
  n_runs: number;
  n_with_stability: number;
  points: CurvePoint[];
  summary: {
    monotonicity_pass_count?: number;
    monotonicity_fail_count?: number;
    monotonicity_pass_rate?: number | null;
  };
}

interface DriftBlock {
  n_runs_with_timing: number;
  baseline_window?: number;
  current_window?: number;
  baseline_ms?: number | null;
  current_ms?: number | null;
  drift_pct?: number | null;
  slope_ms_per_run?: number | null;
  interpretation: string;
}

interface SurfaceHealthBlock {
  n_runs_examined: number;
  window?: number;
  scenario_health: Record<
    string,
    {
      pass_rate: number;
      n_pass: number;
      n_total: number;
      mean_duration_ms: number | null;
    }
  >;
  surface_proxy_note: string;
}

interface CurveResponse {
  curve: CurveBlock;
  drift: DriftBlock;
  surface_health: SurfaceHealthBlock;
  error?: string;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...(init ?? {}),
  });
  if (!res.ok) {
    throw new Error(`${path} → ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

// Phase 4E pattern — verification banner; renders only when ?verify=1.
function VerificationBanner() {
  const loc = useLocation();
  const params = new URLSearchParams(loc.search);
  if (params.get("verify") !== "1") return null;
  return (
    <div
      role="status"
      aria-label="verification mode active"
      className="acceptance-verify-banner"
      style={{
        padding: "0.5rem 0.75rem",
        marginBottom: "1rem",
        border: "1px solid currentColor",
        fontSize: "0.85rem",
      }}
    >
      Verification Mode — <code>?verify=1</code> active. This page is
      reading <code>/founder/acceptance/stability/curve</code> live;
      the math runs in <code>stability_math.py</code> at repo root.
    </div>
  );
}

// SVG line chart for mean_ms over run index. No third-party libraries.
function MeanMsChart({ points }: { points: CurvePoint[] }) {
  const usable = points.filter((p) => typeof p.mean_ms === "number") as Array<
    CurvePoint & { mean_ms: number }
  >;

  if (usable.length === 0) {
    return (
      <p style={{ opacity: 0.7, fontSize: "0.85rem" }}>
        no scenario-05 timing data yet — run the harness in full mode to
        populate this chart.
      </p>
    );
  }

  const W = 800;
  const H = 240;
  const padL = 56;
  const padR = 12;
  const padT = 12;
  const padB = 28;

  const ys = usable.map((p) => p.mean_ms);
  const yMin = Math.min(...ys);
  const yMax = Math.max(...ys);
  const yPad = (yMax - yMin) * 0.1 || yMax * 0.1 || 1;
  const yLo = yMin - yPad;
  const yHi = yMax + yPad;

  const xRange = Math.max(1, usable.length - 1);
  const sx = (i: number) =>
    padL + (W - padL - padR) * (xRange === 0 ? 0 : i / xRange);
  const sy = (y: number) =>
    padT + (H - padT - padB) * (1 - (y - yLo) / (yHi - yLo));

  const polyline = usable
    .map((p, i) => `${sx(i).toFixed(2)},${sy(p.mean_ms).toFixed(2)}`)
    .join(" ");

  const yTicks = [yLo, (yLo + yHi) / 2, yHi];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="mean ms over runs"
      style={{ width: "100%", maxWidth: 800, height: "auto" }}
    >
      {/* axes */}
      <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="currentColor" strokeOpacity="0.3" />
      <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="currentColor" strokeOpacity="0.3" />

      {/* y ticks */}
      {yTicks.map((t, i) => (
        <g key={i}>
          <line
            x1={padL - 4}
            x2={padL}
            y1={sy(t)}
            y2={sy(t)}
            stroke="currentColor"
            strokeOpacity="0.4"
          />
          <text
            x={padL - 8}
            y={sy(t) + 4}
            fontSize="11"
            textAnchor="end"
            fill="currentColor"
            opacity="0.7"
          >
            {Math.round(t)}
          </text>
        </g>
      ))}

      {/* x labels: first / last run id (truncated) */}
      <text x={padL} y={H - 10} fontSize="10" fill="currentColor" opacity="0.6">
        {usable[0].run_id ? usable[0].run_id.slice(-12) : "—"}
      </text>
      <text
        x={W - padR}
        y={H - 10}
        fontSize="10"
        textAnchor="end"
        fill="currentColor"
        opacity="0.6"
      >
        {usable[usable.length - 1].run_id
          ? usable[usable.length - 1].run_id!.slice(-12)
          : "—"}
      </text>

      {/* line */}
      <polyline
        points={polyline}
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      {/* points */}
      {usable.map((p, i) => (
        <circle
          key={i}
          cx={sx(i)}
          cy={sy(p.mean_ms)}
          r={p.monotonicity_pass === false ? 4 : 2.5}
          fill={p.monotonicity_pass === false ? "currentColor" : "transparent"}
          stroke="currentColor"
        >
          <title>
            {p.run_id} — mean {p.mean_ms.toFixed(0)}ms
            {p.monotonicity_pass === false ? " (monotonicity FAIL)" : ""}
          </title>
        </circle>
      ))}
    </svg>
  );
}

export default function FounderAcceptanceCurve() {
  const [data, setData] = useState<CurveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await api<CurveResponse>("/founder/acceptance/stability/curve");
      setData(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) {
    return (
      <main className="founder-acceptance-curve">
        <h1>Acceptance — stability curve</h1>
        <p role="alert">error: {error}</p>
        <button onClick={() => void load()}>retry</button>
        <p>
          <Link to="/founder/acceptance">back to surveillance</Link>
        </p>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="founder-acceptance-curve">
        <h1>Acceptance — stability curve</h1>
        <p>loading…</p>
      </main>
    );
  }

  const fmtPct = (v: number | null | undefined) =>
    typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "—";
  const fmtMs = (v: number | null | undefined) =>
    typeof v === "number" ? `${v.toFixed(0)} ms` : "—";

  return (
    <main className="founder-acceptance-curve">
      <h1>Acceptance — stability curve</h1>

      <VerificationBanner />

      <p>
        <Link to="/founder/acceptance">← back to surveillance</Link>
        {" · "}
        <Link to="/founder/acceptance/runs">recent runs</Link>
        {" · "}
        <Link to="/founder/acceptance/stability">aggregate stability</Link>
      </p>

      {data.error && (
        <p role="alert" style={{ opacity: 0.8 }}>
          stability_math error: {data.error}
        </p>
      )}

      <section>
        <h2>Mean per-iteration timing (ms) over runs</h2>
        <p style={{ fontSize: "0.85rem", opacity: 0.7 }}>
          {data.curve.n_runs} runs total · {data.curve.n_with_stability} with
          scenario-05 stability data ·{" "}
          monotonicity pass rate {fmtPct(data.curve.summary.monotonicity_pass_rate)}
        </p>
        <MeanMsChart points={data.curve.points} />
      </section>

      <section>
        <h2>Drift</h2>
        <table>
          <tbody>
            <tr><th>runs with timing</th><td>{data.drift.n_runs_with_timing}</td></tr>
            <tr>
              <th>baseline window</th>
              <td>
                first {data.drift.baseline_window ?? "—"} runs:
                {" "}{fmtMs(data.drift.baseline_ms)}
              </td>
            </tr>
            <tr>
              <th>current window</th>
              <td>
                last {data.drift.current_window ?? "—"} runs:
                {" "}{fmtMs(data.drift.current_ms)}
              </td>
            </tr>
            <tr><th>drift</th><td>{fmtPct(data.drift.drift_pct ?? null)}</td></tr>
            <tr>
              <th>linear slope</th>
              <td>
                {typeof data.drift.slope_ms_per_run === "number"
                  ? `${data.drift.slope_ms_per_run.toFixed(2)} ms / run`
                  : "—"}
              </td>
            </tr>
            <tr><th>interpretation</th><td>{data.drift.interpretation}</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>
          Scenario health (last {data.surface_health.window ?? 20} runs)
        </h2>
        {Object.keys(data.surface_health.scenario_health).length === 0 ? (
          <p>no scenario data yet</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>scenario</th>
                <th>pass / total</th>
                <th>pass rate</th>
                <th>mean duration</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(data.surface_health.scenario_health)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([sid, h]) => (
                  <tr key={sid} data-scenario-id={sid}>
                    <td><code>{sid}</code></td>
                    <td>{h.n_pass} / {h.n_total}</td>
                    <td>{fmtPct(h.pass_rate)}</td>
                    <td>{fmtMs(h.mean_duration_ms)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        )}
        <p style={{ fontSize: "0.8rem", opacity: 0.7, marginTop: "0.5rem" }}>
          {data.surface_health.surface_proxy_note}
        </p>
      </section>
    </main>
  );
}
