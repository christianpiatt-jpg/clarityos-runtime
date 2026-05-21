// web/src/routes/FounderAcceptanceRuns.tsx
//
// Phase 3C addition. Renders the last N acceptance runs as a table with
// per-scenario pass/fail and timing. Reads:
//   GET /founder/acceptance/runs/recent?limit=N
//
// Uses the same fetch + credentials pattern as FounderAcceptance.tsx.
// No new dependencies introduced.

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
      reading <code>/founder/acceptance/runs/recent</code> live; compare
      against <code>tests/acceptance/reports/acceptance_runs.jsonl</code>.
    </div>
  );
}

interface ScenarioSummary {
  pass?: boolean;
  duration_ms?: number;
}

interface StabilityBlock {
  monotonicity_pass?: boolean | null;
  iterations?: number;
  pass_count?: number;
  mean_ms?: number;
  max_ms?: number;
  min_ms?: number;
  stddev_ms?: number;
}

interface RunRecord {
  run_id: string;
  mode?: string;
  pass?: boolean;
  started_at?: string;
  finished_at?: string;
  scenarios?: Record<string, ScenarioSummary>;
  stability?: StabilityBlock | null;
}

interface RecentResponse {
  limit: number;
  count: number;
  available_total: number;
  runs: RunRecord[];
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

export default function FounderAcceptanceRuns() {
  const [recent, setRecent] = useState<RecentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState<number>(10);

  const load = useCallback(async () => {
    setError(null);
    try {
      const r = await api<RecentResponse>(
        `/founder/acceptance/runs/recent?limit=${limit}`,
      );
      setRecent(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [limit]);

  useEffect(() => { void load(); }, [load]);

  if (error) {
    return (
      <main className="founder-acceptance-runs">
        <h1>Acceptance — recent runs</h1>
        <p role="alert">error: {error}</p>
        <button onClick={() => void load()}>retry</button>
        <p><Link to="/founder/acceptance">back to surveillance</Link></p>
      </main>
    );
  }

  if (!recent) {
    return (
      <main className="founder-acceptance-runs">
        <h1>Acceptance — recent runs</h1>
        <p>loading…</p>
      </main>
    );
  }

  return (
    <main className="founder-acceptance-runs">
      <h1>Acceptance — recent runs</h1>

      <VerificationBanner />

      <p>
        <Link to="/founder/acceptance">← back to surveillance</Link>
        {" · "}
        <Link to="/founder/acceptance/stability">stability →</Link>
      </p>

      <section>
        <label>
          show last:
          {" "}
          <input
            type="number"
            min={1}
            max={100}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          />
          {" "}of {recent.available_total}
        </label>
      </section>

      {recent.note && <p>{recent.note}</p>}

      {recent.runs.length === 0 ? (
        <p>no runs ingested yet</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>run id</th>
              <th>mode</th>
              <th>pass</th>
              <th>finished</th>
              <th>scenarios (pass / total)</th>
              <th>monotonicity</th>
              <th>mean iter (ms)</th>
            </tr>
          </thead>
          <tbody>
            {recent.runs.map((r) => {
              const total = r.scenarios ? Object.keys(r.scenarios).length : 0;
              const pass = r.scenarios
                ? Object.values(r.scenarios).filter((s) => s.pass).length
                : 0;
              const monotonicity = r.stability?.monotonicity_pass;
              const meanMs = r.stability?.mean_ms;
              return (
                <tr key={r.run_id} data-run-id={r.run_id}>
                  <td>{r.run_id}</td>
                  <td>{r.mode ?? "—"}</td>
                  <td>{r.pass === true ? "PASS" : r.pass === false ? "FAIL" : "—"}</td>
                  <td>{r.finished_at ?? "—"}</td>
                  <td>{pass} / {total}</td>
                  <td>
                    {monotonicity === true ? "ok"
                      : monotonicity === false ? "FAIL"
                      : "—"}
                  </td>
                  <td>
                    {typeof meanMs === "number"
                      ? meanMs.toFixed(0)
                      : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </main>
  );
}
