// web/src/routes/FounderAcceptanceStability.tsx
//
// Phase 3C addition. Renders aggregated stability metrics from all
// ingested runs. Reads:
//   GET /founder/acceptance/stability
//
// Simple table + list output; no new libraries.

import { useEffect, useState, useCallback } from "react";
import { Link, useLocation } from "react-router-dom";

// Phase 4E — Verification banner. Renders only when the URL contains
// ?verify=1. Existing behaviour of the page is unchanged otherwise.
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
      reading <code>/founder/acceptance/stability</code> live; compare
      against the aggregate of
      {" "}
      <code>tests/acceptance/reports/acceptance_runs.jsonl</code>.
    </div>
  );
}

interface StabilityResponse {
  runs_with_stability: number;
  monotonicity_pass_count: number;
  monotonicity_fail_count: number;
  iteration_mean_ms_avg: number | null;
  iteration_max_ms_max: number | null;
  iteration_stddev_ms_avg: number | null;
  note: string | null;
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

export default function FounderAcceptanceStability() {
  const [stability, setStability] = useState<StabilityResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await api<StabilityResponse>("/founder/acceptance/stability");
      setStability(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (error) {
    return (
      <main className="founder-acceptance-stability">
        <h1>Acceptance — stability metrics</h1>
        <p role="alert">error: {error}</p>
        <button onClick={() => void load()}>retry</button>
        <p><Link to="/founder/acceptance">back to surveillance</Link></p>
      </main>
    );
  }

  if (!stability) {
    return (
      <main className="founder-acceptance-stability">
        <h1>Acceptance — stability metrics</h1>
        <p>loading…</p>
      </main>
    );
  }

  const fmtMs = (n: number | null) =>
    n === null ? "—" : `${n.toFixed(0)} ms`;

  const monotonicityRate =
    stability.runs_with_stability === 0
      ? null
      : (
          stability.monotonicity_pass_count /
          (stability.runs_with_stability || 1)
        );

  return (
    <main className="founder-acceptance-stability">
      <h1>Acceptance — stability metrics</h1>

      <VerificationBanner />

      <p>
        <Link to="/founder/acceptance">← back to surveillance</Link>
        {" · "}
        <Link to="/founder/acceptance/runs">recent runs →</Link>
      </p>

      {stability.note && <p>{stability.note}</p>}

      <section>
        <h2>Aggregate (all ingested runs)</h2>
        <table>
          <tbody>
            <tr>
              <th>runs with stability data</th>
              <td>{stability.runs_with_stability}</td>
            </tr>
            <tr>
              <th>monotonicity pass / fail</th>
              <td>
                {stability.monotonicity_pass_count}
                {" / "}
                {stability.monotonicity_fail_count}
                {monotonicityRate !== null && (
                  <>
                    {" "}({(monotonicityRate * 100).toFixed(1)}% pass)
                  </>
                )}
              </td>
            </tr>
            <tr>
              <th>iteration mean (avg across runs)</th>
              <td>{fmtMs(stability.iteration_mean_ms_avg)}</td>
            </tr>
            <tr>
              <th>iteration max (max across runs)</th>
              <td>{fmtMs(stability.iteration_max_ms_max)}</td>
            </tr>
            <tr>
              <th>iteration stddev (avg across runs)</th>
              <td>{fmtMs(stability.iteration_stddev_ms_avg)}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>Interpretation</h2>
        <ul>
          <li>
            <strong>Monotonicity pass</strong> means scenario 05 confirmed
            artifact counts did not drop between iterations. Failures
            indicate state leakage and warrant a P1 incident.
          </li>
          <li>
            <strong>Iteration timing</strong> is the wall-clock per-iteration
            duration in scenario 05. Sustained growth in mean / max across
            consecutive runs indicates progressive slowdown.
          </li>
        </ul>
      </section>
    </main>
  );
}
